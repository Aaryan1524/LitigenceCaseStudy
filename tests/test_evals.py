import json
from pathlib import Path
import subprocess
import sys

import pytest

from evals import __main__ as runner
from tests.support import ALDER


def test_labelled_dataset_has_twenty_balanced_cases():
    cases = runner.load_cases(runner.DATA)
    assert len(cases) == 20
    assert sum(case["tenant"] == ALDER for case in cases) == 10
    assert {case["expected"]["filing_type"] for case in cases} == {
        None, "complaint", "motion", "order", "other",
    }


def test_real_eval_runs_through_shared_worker_path(monkeypatch):
    calls = []
    original = runner.run_extraction
    def spy(text, tenant, conn, **kwargs):
        calls.append((text, tenant))
        return original(text, tenant, conn, **kwargs)
    monkeypatch.setattr(runner, "run_extraction", spy)
    cases = runner.load_cases(runner.DATA)
    report = runner.evaluate(cases)
    assert calls == [(case["text"], case["tenant"]) for case in cases]
    assert report["passed"]
    assert report["accuracy"] == dict.fromkeys(runner.FIELDS, 1.0)


@pytest.mark.parametrize("wrong_count,passed", [(0, True), (2, True), (3, False)])
def test_threshold_uses_each_field_and_accepts_exactly_ninety_percent(wrong_count, passed):
    cases = [dict(id=str(i), tenant=ALDER, text=str(i), expected=dict(
        filing_type="order", matter_id="M-3108", filed_date=None,
    )) for i in range(20)]
    def fake(text):
        return dict(filing_type="motion" if int(text) < wrong_count else "order",
                    matter_id="M-3108", filed_date=None)
    report = runner.evaluate(cases, extractor=fake)
    assert report["passed"] is passed
    assert report["accuracy"]["filing_type"] == (20 - wrong_count) / 20
    assert report["accuracy"]["matter_id"] == 1.0
    assert len(report["failures"]) == wrong_count


def test_cli_exits_one_below_threshold(tmp_path):
    cases = runner.load_cases(runner.DATA)
    # Deliberately corrupt three labels; do not change the checked-in gold data.
    for case in cases[:3]:
        case["expected"]["filing_type"] = "other"
    path = tmp_path / "wrong-labels.jsonl"
    path.write_text("\n".join(json.dumps(case) for case in cases) + "\n")
    result = subprocess.run([sys.executable, "-m", "evals", "--data", str(path)],
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 1
    assert "filing_type: 17/20" in result.stdout
    assert "FAIL" in result.stdout


@pytest.mark.parametrize("bad", ["", "{}\n", "not json\n", "null\n"])
def test_bad_dataset_cannot_report_success(tmp_path, capsys, bad):
    path = tmp_path / "bad.jsonl"
    path.write_text(bad)
    assert runner.main(["--data", str(path)]) == 2
    assert "eval error:" in capsys.readouterr().err


def test_duplicate_ids_are_rejected(tmp_path):
    cases = runner.load_cases(runner.DATA)
    cases[1]["id"] = cases[0]["id"]
    path = tmp_path / "duplicates.jsonl"
    path.write_text("\n".join(json.dumps(case) for case in cases))
    with pytest.raises(ValueError, match="unique"):
        runner.load_cases(path)
