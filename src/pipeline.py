"""YOUR PoC PIPELINE — this is the file your group owns.

Lab contract = 5 automated steps, run by `python -m src.main ...`:
    01 load      input + provenance check (manifest.csv)
    02 process   your algorithm / model (the research part)
    03 rank      prioritise for a fixed review budget B
    04 review    human-in-the-loop: queue -> reviewer decisions -> overrides + audit log
    05 decide    GO / HOLD / REWORK (or track equivalent) with reason_code + owner, write outputs

Required output: out/<pred_file> with the columns listed for your track in
docs/tracks/TXX.md (also in src/metrics/tracks.py::TRACKS). Then evaluate with
    python -m src.evaluate --track tXX --pred out/<pred_file>

Rules: never read fixtures/*/gt/ here (the GT guard will stop you); seed everything via ctx.rng;
no network calls; fail loudly on missing models instead of downloading.
See src/examples/random_baseline.py for a minimal end-to-end wiring example.
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from .common.contact_sheet import render_contact_sheet
from .common.context import RunContext
from .common.decision import Decision, write_decision
from .common.image_ops import brightness_stats, laplacian_variance, load_rgb
from .common.manifest import verify_manifest
from .common.review import load_review_decisions, make_review_queue, write_review_queue
from .metrics.tracks import get_track


# ---------------------------------------------------------------- 01 load
def load(ctx: RunContext) -> dict:
    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.exists() else [{"problem": "no_manifest"}]
    if problems:
        ctx.audit.log(actor="pipeline", action="provenance_problems", item_id=str(manifest), after=problems[:20])
        if ctx.config.get("strict_provenance", True):
            raise ValueError(f"provenance check failed ({len(problems)} problems), first: {problems[:3]}")
    data = {"manifest": pd.read_csv(manifest) if manifest.exists() else None}
    if ctx.track != "t02":
        raise NotImplementedError(f"This student PoC implements T02, not {ctx.track}")
    images_path = ctx.input_dir / "images.csv"
    images = pd.read_csv(images_path)
    required = {"image_id", "path", "camera_id", "light", "split"}
    missing = required - set(images.columns)
    if missing:
        raise ValueError(f"images.csv missing columns: {sorted(missing)}")
    if images["image_id"].duplicated().any():
        raise ValueError("images.csv contains duplicate image_id values")
    data["images"] = images
    return data


# ---------------------------------------------------------------- 02 process
def process(ctx: RunContext, data: dict) -> pd.DataFrame:
    """Score T02 images using four complementary, label-free QC signals.

    All normalisation references come from the ``dev`` split only.  This is
    deliberately unsupervised: the pipeline never reads hidden labels and
    does not tune against the eval split.
    """
    if ctx.track != "t02":
        raise NotImplementedError(f"This student PoC implements T02, not {ctx.track}")

    rows: list[dict] = []
    for item in data["images"].itertuples(index=False):
        image_path = ctx.input_dir / item.path
        if not image_path.exists():
            raise FileNotFoundError(f"image listed in images.csv is missing: {image_path}")
        image = load_rgb(image_path)
        b = brightness_stats(image)
        # JPEG block boundaries are unusually strong when an image has been
        # aggressively compressed.  The ratio makes this scale-independent.
        gray = (0.299 * image[..., 0] + 0.587 * image[..., 1] + 0.114 * image[..., 2]).astype(np.float32)
        vertical = np.abs(np.diff(gray, axis=1))
        horizontal = np.abs(np.diff(gray, axis=0))
        boundary = np.concatenate([vertical[:, 7::8].ravel(), horizontal[7::8, :].ravel()]).mean()
        non_boundary = np.concatenate([vertical[:, [i for i in range(vertical.shape[1]) if (i + 1) % 8 != 0]].ravel(),
                                       horizontal[[i for i in range(horizontal.shape[0]) if (i + 1) % 8 != 0], :].ravel()]).mean()
        rows.append({
            "image_id": item.image_id,
            "path": item.path,
            "camera_id": item.camera_id,
            "light": item.light,
            "split": item.split,
            "sharpness": laplacian_variance(image),
            "mean_brightness": b["mean"],
            "dark_fraction": b["frac_dark"],
            "saturated_fraction": b["frac_saturated"],
            "highlight_spread": max(0.0, b["p95"] - b["mean"]),
            "blockiness": float(boundary / max(non_boundary, 1e-6)),
        })
    features = pd.DataFrame(rows)

    # Robust reference values: group by the known capture conditions where
    # possible, then use the whole dev pool for rare groups.  Low sharpness
    # and brightness are suspicious; high saturation and blockiness are too.
    dev = features[features["split"].astype(str).str.lower() == str(ctx.param("dev_split", "dev")).lower()]
    if dev.empty:
        raise ValueError("no dev rows available for frozen feature calibration")
    keys = ["camera_id", "light"]
    cols = ["sharpness", "mean_brightness", "dark_fraction", "saturated_fraction", "highlight_spread", "blockiness"]
    global_median = dev[cols].median()
    global_mad = (dev[cols] - global_median).abs().median().clip(lower=1e-6)
    group_sizes = dev.groupby(keys).size().to_dict()
    group_median = dev.groupby(keys)[cols].median()
    group_mad = dev.groupby(keys)[cols].apply(lambda x: (x - x.median()).abs().median())
    # A camera/light combination can be absent by design because the split is
    # scene-based.  Fall back to light before the all-image reference so that
    # legitimate night captures are not automatically treated as defective.
    light_sizes = dev.groupby("light").size().to_dict()
    light_median = dev.groupby("light")[cols].median()
    light_mad = dev.groupby("light")[cols].apply(lambda x: (x - x.median()).abs().median())
    camera_sizes = dev.groupby("camera_id").size().to_dict()
    camera_median = dev.groupby("camera_id")[cols].median()
    camera_mad = dev.groupby("camera_id")[cols].apply(lambda x: (x - x.median()).abs().median())

    def reference(row: pd.Series) -> tuple[pd.Series, pd.Series]:
        key = (row["camera_id"], row["light"])
        if group_sizes.get(key, 0) >= 4:
            return group_median.loc[key], group_mad.loc[key].clip(lower=1e-6)
        if light_sizes.get(row["light"], 0) >= 4:
            return light_median.loc[row["light"]], light_mad.loc[row["light"]].clip(lower=1e-6)
        if camera_sizes.get(row["camera_id"], 0) >= 8:
            return camera_median.loc[row["camera_id"]], camera_mad.loc[row["camera_id"]].clip(lower=1e-6)
        return global_median, global_mad

    scores, reasons, predicted_types = [], [], []
    for _, row in features.iterrows():
        med, mad = reference(row)
        # 0.6745 makes MAD scores comparable to standard deviations without
        # assuming image features are normally distributed.
        z = (row[cols] - med) / (1.4826 * mad)
        components = {
            "blur": max(0.0, -float(z["sharpness"])),
            "dark": max(0.0, -float(z["mean_brightness"])) + 0.7 * max(0.0, float(z["dark_fraction"])),
            "glare": max(0.0, float(z["saturated_fraction"])) + 0.5 * max(0.0, float(z["highlight_spread"])),
            "compression": max(0.0, float(z["blockiness"])),
        }
        # A capped sum rewards independent symptoms, while avoiding one
        # outlier feature dominating every review slot.
        ordered = sorted(components.items(), key=lambda kv: kv[1], reverse=True)
        score = min(8.0, ordered[0][1]) + 0.35 * min(5.0, ordered[1][1])
        predicted_type, strongest = ordered[0]
        scores.append(float(score))
        predicted_types.append(predicted_type if strongest >= 0.75 else "none")
        reasons.append("; ".join(f"{name}={value:.2f}" for name, value in ordered if value >= 0.35) or "within dev reference")

    out = features.assign(
        score=scores,
        pred_defect_type=predicted_types,
        pred_action=np.where(np.asarray(scores) >= float(ctx.param("recapture_score", 1.25)), "RECAPTURE", "KEEP"),
        reason=reasons,
    )
    ctx.stats["feature_reference"] = "robust dev median/MAD; camera_id+light, then light, then camera, then global"
    ctx.stats["scoring"] = "blur + dark + glare + compression; frozen config threshold"
    if ctx.audit:
        ctx.audit.log(actor="pipeline", action="qc_scored", item_id="t02-batch",
                      after={"n_images": len(out), "n_recapture_candidates": int((out["pred_action"] == "RECAPTURE").sum())},
                      reason="offline multi-signal QC scoring with dev-only calibration")
    return out.sort_values(["score", "image_id"], ascending=[False, True], kind="mergesort").reset_index(drop=True)


# ---------------------------------------------------------------- 03 rank
def rank(ctx: RunContext, scored: pd.DataFrame) -> pd.DataFrame:
    """Default: top-B by `score`. Adapt id/score/reason columns to your track."""
    budget = int(ctx.param("budget", 20))
    if "score" not in scored.columns:
        raise ValueError("rank(): process() output needs a numeric `score` column (higher = review first), "
                         "or adapt rank() to your track")
    q = make_review_queue(scored, id_col="image_id", score_col="score", budget=budget,
                          reason_col="reason" if "reason" in scored.columns else None,
                          action_col="pred_action" if "pred_action" in scored.columns else None,
                          slice_col="light" if "light" in scored.columns else None,
                          evidence_col="path" if "path" in scored.columns else None)
    write_review_queue(q, ctx.out("review_queue.csv"))
    render_contact_sheet(q, ctx.out("contact_sheet.html"), image_root=ctx.input_dir,
                         title="T02 Raw QC — human review queue")
    return q


# ---------------------------------------------------------------- 04 review
def review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    """If a reviewed queue exists (out/review_queue_reviewed.csv), apply it. Otherwise pass through.

    TODO: decide what an `edit` / `reject` means for your track and apply it
    (e.g. via common.review.apply_overrides), logging every change to ctx.audit.
    """
    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    if reviewed_path.exists():
        reviewed = load_review_decisions(reviewed_path)
        ctx.stats["n_reviewed"] = len(reviewed)
        out = scored.copy()
        for item in reviewed.itertuples(index=False):
            mask = out["image_id"].astype(str) == str(item.item_id)
            if not mask.any():
                continue
            before = out.loc[mask, ["score", "pred_action"]].to_dict("records")
            if item.reviewer_decision == "reject":
                out.loc[mask, "score"] = -1.0
                out.loc[mask, "pred_action"] = "KEEP"
            elif item.reviewer_decision == "edit" and str(item.override_value).strip():
                value = str(item.override_value).strip().upper()
                if value in {"KEEP", "RECAPTURE"}:
                    out.loc[mask, "pred_action"] = value
                    out.loc[mask, "score"] = 2.0 if value == "RECAPTURE" else -1.0
                else:
                    try:
                        out.loc[mask, "score"] = float(value)
                    except ValueError as exc:
                        raise ValueError("T02 override_value must be KEEP, RECAPTURE, or a numeric score") from exc
            if ctx.audit:
                ctx.audit.log(actor=item.reviewer, action=f"review:{item.reviewer_decision}", item_id=item.item_id,
                              before=before, after=out.loc[mask, ["score", "pred_action"]].to_dict("records"),
                              reason=item.review_note)
        return out.sort_values(["score", "image_id"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    ctx.stats["n_reviewed"] = 0
    return scored


# ---------------------------------------------------------------- 05 decide
def decide(ctx: RunContext, final: pd.DataFrame) -> Decision:
    reviewed = int(ctx.stats.get("n_reviewed", 0))
    owner = str(ctx.config.get("owner", ""))
    evidence = [str(ctx.out("ranked_review.csv")), str(ctx.out("review_queue.csv")), str(ctx.out("audit_log.jsonl"))]
    if reviewed == 0:
        return Decision(status="HOLD", reason_code="HUMAN_REVIEW_PENDING",
                        reason="Automated QC ranking is complete; a named reviewer must validate the top review queue.",
                        owner=owner, scope="t02 batch", evidence=evidence, metrics={"n_reviewed": 0})
    recapture = int((final["pred_action"] == "RECAPTURE").sum())
    if recapture:
        return Decision(status="RECAPTURE", reason_code="QC_DEFECTS_CONFIRMED",
                        reason=f"Reviewer workflow completed; {recapture} image(s) remain flagged for recapture.",
                        owner=owner, scope="t02 batch", evidence=evidence,
                        metrics={"n_reviewed": reviewed, "recapture_candidates": recapture})
    return Decision(status="KEEP", reason_code="QC_REVIEW_COMPLETE",
                    reason="Reviewer workflow completed with no remaining recapture candidates.",
                    owner=owner, scope="t02 batch", evidence=evidence, metrics={"n_reviewed": reviewed})


def run(ctx: RunContext) -> None:
    spec = get_track(ctx.track)
    data = load(ctx)
    scored = process(ctx, data)
    ctx.stats["n_items"] = len(scored)
    queue = rank(ctx, scored)
    final = review(ctx, scored, queue)
    final[spec.pred_columns + [c for c in final.columns if c not in spec.pred_columns]].to_csv(ctx.out(spec.pred_file), index=False)
    write_decision(decide(ctx, final), ctx.out("decision.json"), ctx.out("decision_log.csv"))
