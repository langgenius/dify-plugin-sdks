import json
import sys
from pathlib import Path

GATES = (
    ("SDK", ("src/dify_plugin/",), 85, 75),
    (
        "runtime",
        ("src/dify_plugin/core/runtime.py", "src/dify_plugin/core/server/"),
        90,
        85,
    ),
    (
        "HTTP",
        (
            "src/dify_plugin/interfaces/model/openai_compatible/",
            "src/dify_plugin/file/",
            "src/dify_plugin/invocations/file.py",
        ),
        90,
        85,
    ),
)


def check_coverage(report: dict) -> list[str]:
    if not report["meta"]["branch_coverage"]:
        return ["Branch coverage was not collected"]
    failures = []
    for name, prefixes, minimum_lines, minimum_branches in GATES:
        summaries = [
            data["summary"]
            for path, data in report["files"].items()
            if path.startswith(prefixes)
        ]
        if not summaries:
            failures.append(f"{name}: no matching source files in coverage report")
            continue
        for metric, covered_key, total_key, minimum in (
            ("lines", "covered_lines", "num_statements", minimum_lines),
            ("branches", "covered_branches", "num_branches", minimum_branches),
        ):
            covered = sum(summary[covered_key] for summary in summaries)
            total = sum(summary[total_key] for summary in summaries)
            percent = 100 * covered / total if total else 0
            sys.stdout.write(f"{name} {metric}: {percent:.2f}% (minimum {minimum}%)\n")
            if percent < minimum:
                failures.append(
                    f"{name} {metric}: {covered}/{total} ({percent:.4f}%) < {minimum}%"
                )
    return failures


if __name__ == "__main__":
    failures = check_coverage(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
    if failures:
        sys.stderr.write("\n".join(failures) + "\n")
    raise SystemExit(bool(failures))
