"""Student-owned smoke and edge tests for the T02 multi-signal PoC."""
from __future__ import annotations

import json

import pandas as pd

from src import main as runner


def test_t02_poc_runs_offline_and_writes_review_artifacts(tmp_path):
    out = tmp_path / "poc"
    rc = runner.main(["--config", "configs/lab.yaml", "--track", "t02", "--output", str(out), "--offline", "--seed", "42"])
    assert rc == 0
    pred = pd.read_csv(out / "ranked_review.csv")
    assert len(pred) == 96
    assert {"image_id", "score", "pred_defect_type", "pred_action"}.issubset(pred.columns)
    assert pred.image_id.is_unique and pred.score.notna().all()
    assert pred.score.is_monotonic_decreasing
    assert len(pd.read_csv(out / "review_queue.csv")) == 20
    assert (out / "contact_sheet.html").exists()
    decision = json.loads((out / "decision.json").read_text())
    assert decision["canonical"] == "HOLD"
    assert decision["reason_code"] == "HUMAN_REVIEW_PENDING"


def test_t02_reject_review_lowers_score_and_is_audited(tmp_path):
    out = tmp_path / "poc"
    assert runner.main(["--config", "configs/lab.yaml", "--track", "t02", "--output", str(out), "--offline"]) == 0
    review = pd.read_csv(out / "review_queue.csv", dtype=str).fillna("")
    first = review.index[0]
    review.loc[first, ["reviewer", "reviewer_decision", "review_note"]] = ["QA reviewer", "reject", "clean image"]
    review.to_csv(out / "review_queue_reviewed.csv", index=False)
    assert runner.main(["--config", "configs/lab.yaml", "--track", "t02", "--output", str(out), "--offline"]) == 0
    pred = pd.read_csv(out / "ranked_review.csv")
    assert float(pred.loc[pred.image_id == review.loc[first, "item_id"], "score"].iloc[0]) == -1.0
    assert '"action": "review:reject"' in (out / "audit_log.jsonl").read_text()
