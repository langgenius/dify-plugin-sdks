from copy import deepcopy

import pytest

from scripts.check_coverage import check_coverage


@pytest.fixture
def report() -> dict:
    return {
        "meta": {"branch_coverage": True},
        "files": {
            path: {
                "summary": {
                    "covered_lines": 90,
                    "num_statements": 100,
                    "covered_branches": 85,
                    "num_branches": 100,
                }
            }
            for path in (
                "src/dify_plugin/core/runtime.py",
                "src/dify_plugin/file/file.py",
                "src/dify_plugin/entities/model/llm.py",
            )
        },
    }


def test_coverage_accepts_exact_thresholds_without_mutating_report(
    report: dict,
) -> None:
    original = deepcopy(report)
    assert check_coverage(report) == []
    assert report == original


@pytest.mark.parametrize(
    ("field", "value", "metric"),
    [("covered_lines", 89, "lines"), ("covered_branches", 84, "branches")],
)
def test_coverage_checks_risk_groups_independently(
    report: dict, field: str, value: int, metric: str
) -> None:
    report["files"]["src/dify_plugin/core/runtime.py"]["summary"][field] = value

    failures = check_coverage(report)

    assert len(failures) == 1
    assert failures[0].startswith(f"runtime {metric}:")


def test_coverage_does_not_round_up_below_a_threshold(report: dict) -> None:
    summary = report["files"]["src/dify_plugin/file/file.py"]["summary"]
    summary.update(covered_lines=89999, num_statements=100000)

    assert check_coverage(report) == ["HTTP lines: 89999/100000 (89.9990%) < 90%"]


@pytest.mark.parametrize("branches", [False, True])
def test_coverage_rejects_missing_measurements(report: dict, branches: bool) -> None:
    report["meta"]["branch_coverage"] = branches
    report["files"] = {}

    assert check_coverage(report)
