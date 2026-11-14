"""Frozen T02 baseline: rank only by global Laplacian sharpness.

This intentionally simple comparator follows the brief: it cannot detect a
sharp but overexposed image, a very dark image, or JPEG blocking reliably.
Run it with ``--pipeline src.baseline_t02`` before the multi-signal PoC.
"""
from __future__ import annotations

import pandas as pd

from .common.contact_sheet import render_contact_sheet
from .common.context import RunContext
from .common.decision import Decision, write_decision
from .common.image_ops import laplacian_variance, load_rgb
from .common.manifest import verify_manifest
from .common.review import make_review_queue, write_review_queue


def run(ctx: RunContext) -> None:
    if ctx.track != "t02":
        raise NotImplementedError("baseline_t02 only supports T02")
    problems = verify_manifest(ctx.input_dir / "manifest.csv")
    if problems:
        raise ValueError(f"provenance check failed: {problems[:3]}")
    images = pd.read_csv(ctx.input_dir / "images.csv")
    rows = []
    for item in images.itertuples(index=False):
        sharpness = laplacian_variance(load_rgb(ctx.input_dir / item.path))
        rows.append({"image_id": item.image_id, "path": item.path, "light": item.light,
                     "sharpness": sharpness, "score": -sharpness,
                     "pred_defect_type": "blur", "pred_action": "RECAPTURE",
                     "reason": "single global sharpness baseline"})
    ranked = pd.DataFrame(rows).sort_values(["score", "image_id"], ascending=[False, True], kind="mergesort")
    budget = int(ctx.param("budget", 20))
    queue = make_review_queue(ranked, "image_id", "score", budget, reason_col="reason",
                              action_col="pred_action", slice_col="light", evidence_col="path")
    write_review_queue(queue, ctx.out("review_queue.csv"))
    render_contact_sheet(queue, ctx.out("contact_sheet.html"), image_root=ctx.input_dir,
                         title="T02 baseline — global sharpness only")
    ranked.to_csv(ctx.out("ranked_review.csv"), index=False)
    ctx.stats.update({"n_items": len(ranked), "scoring": "negative global Laplacian variance only"})
    write_decision(Decision(status="HOLD", reason_code="BASELINE_REQUIRES_REVIEW",
                            reason="Single-feature baseline is an experiment, not a release decision.",
                            owner=str(ctx.config.get("owner", "")), scope="t02 baseline",
                            evidence=[str(ctx.out("ranked_review.csv")), str(ctx.out("review_queue.csv"))]),
                   ctx.out("decision.json"), ctx.out("decision_log.csv"))
