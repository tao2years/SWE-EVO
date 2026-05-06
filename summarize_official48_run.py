#!/usr/bin/env python3
import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path


def load_json(path: Path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def safe_div(num: int | float, den: int | float) -> float | None:
    if not den:
        return None
    return num / den


def fmt_rate(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{rate * 100:.1f}%"


def find_reports(run_eval_root: Path) -> dict[str, dict]:
    reports: dict[str, dict] = {}
    for report_path in sorted(run_eval_root.glob("**/report.json")):
        payload = load_json(report_path, {})
        if not isinstance(payload, dict) or not payload:
            continue
        if len(payload) == 1:
            instance_id, report_body = next(iter(payload.items()))
            if instance_id not in reports or report_path.stat().st_mtime > reports[instance_id]["path"].stat().st_mtime:
                reports[instance_id] = {"path": report_path, "body": report_body}
    return reports


def parse_body_maybe_json(body):
    if isinstance(body, dict):
        return body
    if not body or not isinstance(body, str):
        return None
    try:
        return json.loads(body)
    except Exception:
        return None


def parse_trace_metrics(bundle_path: Path) -> dict:
    if not bundle_path.exists():
        return {
            "trace_request_count": 0,
            "trace_http_error_count": 0,
            "trace_input_tokens_sum": None,
            "trace_output_tokens_sum": None,
            "trace_duration_ms_sum": None,
            "tool_use_count": None,
            "tool_error_count": None,
            "tool_counts_by_name": {},
        }

    payload = load_json(bundle_path, {})
    traces = payload.get("traces", [])
    if not isinstance(traces, list):
        traces = []

    tool_uses: dict[str, str] = {}
    tool_errors: dict[str, bool] = {}
    http_error_count = 0
    input_tokens_sum = 0
    output_tokens_sum = 0
    duration_sum = 0

    for trace in traces:
        status = trace.get("response_status")
        if status is not None and status != 200:
            http_error_count += 1
        input_tokens_sum += int(trace.get("tokens_input") or 0)
        output_tokens_sum += int(trace.get("tokens_output") or 0)
        duration_sum += int(trace.get("duration_ms") or 0)

        response_body = parse_body_maybe_json(trace.get("response_body"))
        if isinstance(response_body, dict):
            content = response_body.get("content", [])
            if not isinstance(content, list):
                content = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "tool_use" and item.get("id"):
                    tool_uses[item["id"]] = item.get("name", "unknown")

        request_body = parse_body_maybe_json(trace.get("request_body"))
        if isinstance(request_body, dict):
            for msg in request_body.get("messages", []) or []:
                content = msg.get("content", [])
                if not isinstance(content, list):
                    continue
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "tool_result" and item.get("tool_use_id"):
                        tool_use_id = item["tool_use_id"]
                        tool_errors[tool_use_id] = tool_errors.get(tool_use_id, False) or bool(item.get("is_error"))

    tool_name_counts = Counter(tool_uses.values())
    return {
        "trace_request_count": len(traces),
        "trace_http_error_count": http_error_count,
        "trace_input_tokens_sum": input_tokens_sum,
        "trace_output_tokens_sum": output_tokens_sum,
        "trace_duration_ms_sum": duration_sum,
        "tool_use_count": len(tool_uses),
        "tool_error_count": sum(1 for value in tool_errors.values() if value),
        "tool_counts_by_name": dict(sorted(tool_name_counts.items())),
    }


def parse_cli_metrics(cli_result_path: Path) -> dict:
    payload = load_json(cli_result_path, {})
    usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
    model_usage_map = payload.get("modelUsage", {}) if isinstance(payload, dict) else {}
    model_usage = next(iter(model_usage_map.values()), {}) if isinstance(model_usage_map, dict) else {}
    return {
        "cli_type": payload.get("type"),
        "cli_subtype": payload.get("subtype"),
        "cli_is_error": payload.get("is_error"),
        "cli_stop_reason": payload.get("stop_reason"),
        "cli_duration_ms": payload.get("duration_ms"),
        "cli_duration_api_ms": payload.get("duration_api_ms"),
        "cli_num_turns": payload.get("num_turns"),
        "cli_total_cost_usd": payload.get("total_cost_usd"),
        "cli_usage_input_tokens": usage.get("input_tokens"),
        "cli_usage_output_tokens": usage.get("output_tokens"),
        "cli_usage_cache_read_tokens": usage.get("cache_read_input_tokens"),
        "cli_usage_cache_creation_tokens": usage.get("cache_creation_input_tokens"),
        "cli_model_input_tokens": model_usage.get("inputTokens"),
        "cli_model_output_tokens": model_usage.get("outputTokens"),
        "cli_model_cache_read_tokens": model_usage.get("cacheReadInputTokens"),
        "cli_model_cache_creation_tokens": model_usage.get("cacheCreationInputTokens"),
        "cli_model_cost_usd": model_usage.get("costUSD"),
        "cli_errors": payload.get("errors", []),
    }


def parse_eval_log_signature(eval_log_path: Path) -> tuple[str | None, str | None]:
    if not eval_log_path.exists():
        return None, None
    text = eval_log_path.read_text(encoding="utf-8", errors="replace")
    if "pydantic-core version" in text:
        return "eval_env_pydantic_core_mismatch", "pydantic-core version mismatch in .deps"
    if "Traceback (most recent call last):" in text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "eval_traceback", lines[-1] if lines else "traceback"
    return None, None


def collect_case_rows(repo_root: Path, run_root: Path) -> tuple[list[dict], dict]:
    instances_dir = repo_root / "output_final"
    infer_root = run_root / "infer"
    run_eval_root = repo_root / "logs" / "run_evaluation" / f"eval_input_{run_root.name}"
    infer_summary = load_json(infer_root / "inference_summary.json", [])
    infer_by_id = {row["instance_id"]: row for row in infer_summary if isinstance(row, dict) and row.get("instance_id")}
    eval_state = load_json(run_root / "eval_worker_status.json", {})
    eval_completed = eval_state.get("completed", {}) if isinstance(eval_state, dict) else {}
    reports = find_reports(run_eval_root)

    rows: list[dict] = []
    aggregate_tool_names = Counter()

    for instance_path in sorted(instances_dir.glob("*.json")):
        instance = load_json(instance_path, {})
        instance_id = instance["instance_id"]
        run_dir = infer_root / "runs" / instance_id
        cli_result_path = run_dir / "cli_result.json"
        trace_bundle_path = run_dir / "router_trace_bundle.json"
        cli_exit_code_path = run_dir / "cli_exit_code.txt"
        eval_log_path = run_root / "eval_worker_logs" / f"{instance_id}.log"

        cli_metrics = parse_cli_metrics(cli_result_path)
        trace_metrics = parse_trace_metrics(trace_bundle_path)
        aggregate_tool_names.update(trace_metrics["tool_counts_by_name"])

        report_entry = reports.get(instance_id)
        report_body = report_entry["body"] if report_entry else None
        tests_status = report_body.get("tests_status", {}) if isinstance(report_body, dict) else {}

        f2p_total = len(instance.get("FAIL_TO_PASS", []))
        p2p_total = len(instance.get("PASS_TO_PASS", []))
        f2p_success = len(tests_status.get("FAIL_TO_PASS", {}).get("success", [])) if tests_status else None
        f2p_failure = len(tests_status.get("FAIL_TO_PASS", {}).get("failure", [])) if tests_status else None
        p2p_success = len(tests_status.get("PASS_TO_PASS", {}).get("success", [])) if tests_status else None
        p2p_failure = len(tests_status.get("PASS_TO_PASS", {}).get("failure", [])) if tests_status else None

        eval_entry = eval_completed.get(instance_id, {})
        eval_returncode = eval_entry.get("returncode")
        eval_signature, eval_signature_detail = parse_eval_log_signature(eval_log_path)

        anomaly_flags: list[str] = []
        if cli_metrics["cli_subtype"] == "timeout" or (run_dir / "cli_exit_code.txt").exists() and cli_exit_code_path.read_text(encoding="utf-8").strip() == "124":
            anomaly_flags.append("inference_timeout")
        if cli_metrics["cli_is_error"]:
            anomaly_flags.append("cli_reported_error")
        if not trace_bundle_path.exists():
            anomaly_flags.append("missing_router_trace_bundle")
        if report_body is None:
            anomaly_flags.append("missing_eval_report")
        if eval_signature:
            anomaly_flags.append(eval_signature)
        if report_body is not None and eval_returncode not in (None, 0):
            anomaly_flags.append("eval_rc_nonzero_with_report")

        if report_body is not None:
            eval_status = "report_available"
        elif eval_signature:
            eval_status = "eval_error"
        elif eval_returncode is not None:
            eval_status = "eval_completed_without_report"
        else:
            eval_status = "eval_missing"

        row = {
            "instance_id": instance_id,
            "repo": instance.get("repo"),
            "cli_returncode": infer_by_id.get(instance_id, {}).get("cli_returncode"),
            "cli_type": cli_metrics["cli_type"],
            "cli_subtype": cli_metrics["cli_subtype"],
            "cli_is_error": cli_metrics["cli_is_error"],
            "cli_stop_reason": cli_metrics["cli_stop_reason"],
            "resolved": report_body.get("resolved") if report_body else None,
            "eval_status": eval_status,
            "eval_returncode": eval_returncode,
            "eval_signature": eval_signature,
            "eval_signature_detail": eval_signature_detail,
            "patch_exists": report_body.get("patch_exists") if report_body else None,
            "patch_successfully_applied": report_body.get("patch_successfully_applied") if report_body else None,
            "f2p_total": f2p_total,
            "f2p_success": f2p_success,
            "f2p_failure": f2p_failure,
            "f2p_rate": safe_div(f2p_success, f2p_total) if f2p_success is not None else None,
            "p2p_total": p2p_total,
            "p2p_success": p2p_success,
            "p2p_failure": p2p_failure,
            "p2p_rate": safe_div(p2p_success, p2p_total) if p2p_success is not None else None,
            "regression_rate": safe_div(p2p_failure, p2p_total) if p2p_failure is not None else None,
            "cli_duration_ms": cli_metrics["cli_duration_ms"],
            "cli_duration_api_ms": cli_metrics["cli_duration_api_ms"],
            "cli_num_turns": cli_metrics["cli_num_turns"],
            "cli_total_cost_usd": cli_metrics["cli_total_cost_usd"],
            "cli_model_input_tokens": cli_metrics["cli_model_input_tokens"],
            "cli_model_output_tokens": cli_metrics["cli_model_output_tokens"],
            "cli_model_cache_read_tokens": cli_metrics["cli_model_cache_read_tokens"],
            "cli_model_cache_creation_tokens": cli_metrics["cli_model_cache_creation_tokens"],
            "trace_request_count": trace_metrics["trace_request_count"],
            "trace_http_error_count": trace_metrics["trace_http_error_count"],
            "trace_input_tokens_sum": trace_metrics["trace_input_tokens_sum"],
            "trace_output_tokens_sum": trace_metrics["trace_output_tokens_sum"],
            "trace_duration_ms_sum": trace_metrics["trace_duration_ms_sum"],
            "tool_use_count": trace_metrics["tool_use_count"],
            "tool_error_count": trace_metrics["tool_error_count"],
            "tool_counts_by_name": json.dumps(trace_metrics["tool_counts_by_name"], ensure_ascii=False, sort_keys=True),
            "anomaly_flags": json.dumps(sorted(set(anomaly_flags)), ensure_ascii=False),
        }
        rows.append(row)

    return rows, {
        "aggregate_tool_names": dict(sorted(aggregate_tool_names.items())),
        "infer_summary_rows": len(infer_summary),
        "eval_completed_rows": len(eval_completed),
        "report_found_rows": len(reports),
    }


def numeric_values(rows: list[dict], key: str) -> list[float]:
    values = [row[key] for row in rows if isinstance(row.get(key), (int, float))]
    return [float(v) for v in values]


def rate_values(rows: list[dict], key: str) -> list[float]:
    values = [row.get(key) for row in rows if isinstance(row.get(key), (int, float))]
    return [float(v) for v in values]


def summarize_rows(rows: list[dict], aux: dict) -> dict:
    total_cases = len(rows)
    report_rows = [row for row in rows if row["eval_status"] == "report_available"]
    eval_error_rows = [row for row in rows if row["eval_status"] == "eval_error"]
    resolved_rows = [row for row in report_rows if row["resolved"] is True]
    unresolved_rows = [row for row in report_rows if row["resolved"] is False]

    f2p_success_total = sum(row["f2p_success"] or 0 for row in report_rows)
    f2p_total_total = sum(row["f2p_total"] or 0 for row in report_rows)
    p2p_success_total = sum(row["p2p_success"] or 0 for row in report_rows)
    p2p_total_total = sum(row["p2p_total"] or 0 for row in report_rows)
    p2p_failure_total = sum(row["p2p_failure"] or 0 for row in report_rows)

    cli_costs = numeric_values(rows, "cli_total_cost_usd")
    cli_durations = numeric_values(rows, "cli_duration_ms")
    cli_turns = numeric_values(rows, "cli_num_turns")
    tool_counts = numeric_values(rows, "tool_use_count")
    tool_errors = numeric_values(rows, "tool_error_count")
    f2p_rates = rate_values(report_rows, "f2p_rate")
    p2p_rates = rate_values(report_rows, "p2p_rate")

    anomaly_counter = Counter()
    for row in rows:
        flags = json.loads(row["anomaly_flags"])
        anomaly_counter.update(flags)

    return {
        "total_cases": total_cases,
        "inference_completed_cases": aux["infer_summary_rows"],
        "evaluation_completed_tasks": aux["eval_completed_rows"],
        "evaluation_report_cases": len(report_rows),
        "evaluation_error_cases": len(eval_error_rows),
        "resolution_known_cases": len(report_rows),
        "resolved_true_cases": len(resolved_rows),
        "resolved_false_cases": len(unresolved_rows),
        "resolution_rate_known_only": safe_div(len(resolved_rows), len(report_rows)),
        "resolution_rate_lower_bound_all_cases": safe_div(len(resolved_rows), total_cases),
        "f2p_micro_rate_known_only": safe_div(f2p_success_total, f2p_total_total),
        "f2p_macro_rate_known_only": statistics.mean(f2p_rates) if f2p_rates else None,
        "p2p_micro_pass_rate_known_only": safe_div(p2p_success_total, p2p_total_total),
        "p2p_macro_pass_rate_known_only": statistics.mean(p2p_rates) if p2p_rates else None,
        "p2p_regression_total_known_only": p2p_failure_total,
        "total_cli_cost_usd": sum(cli_costs) if cli_costs else None,
        "avg_cli_cost_usd": statistics.mean(cli_costs) if cli_costs else None,
        "avg_cli_duration_ms": statistics.mean(cli_durations) if cli_durations else None,
        "median_cli_duration_ms": statistics.median(cli_durations) if cli_durations else None,
        "avg_cli_turns": statistics.mean(cli_turns) if cli_turns else None,
        "avg_tool_use_count": statistics.mean(tool_counts) if tool_counts else None,
        "avg_tool_error_count": statistics.mean(tool_errors) if tool_errors else None,
        "aggregate_tool_names": aux["aggregate_tool_names"],
        "anomaly_counts": dict(sorted(anomaly_counter.items())),
    }


def top_rows(rows: list[dict], key: str, limit: int = 5) -> list[dict]:
    filtered = [row for row in rows if isinstance(row.get(key), (int, float))]
    return sorted(filtered, key=lambda row: row[key], reverse=True)[:limit]


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict], columns: list[tuple[str, str]]) -> list[str]:
    lines = [
        "| " + " | ".join(title for _, title in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        values = []
        for key, _ in columns:
            value = row.get(key)
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def write_markdown_report(rows: list[dict], summary: dict, output_path: Path, run_root: Path) -> None:
    report_rows = [row for row in rows if row["eval_status"] == "report_available"]
    eval_error_rows = [row for row in rows if row["eval_status"] == "eval_error"]
    top_cost = top_rows(rows, "cli_total_cost_usd")
    top_duration = top_rows(rows, "cli_duration_ms")
    anomalies = [row for row in rows if json.loads(row["anomaly_flags"])]

    lines: list[str] = []
    lines.append("# official48 Run Summary")
    lines.append("")
    lines.append(f"- Run root: `{run_root}`")
    lines.append("- Data sources: `infer/inference_summary.json`, per-case `cli_result.json`, `router_trace_bundle.json`, `eval_worker_status.json`, `eval_worker_logs/*.log`, and any materialized `report.json` files.")
    lines.append("")
    lines.append("## Metric Design")
    lines.append("")
    lines.append("- `Resolved Rate (RR)`: case-level `resolved == true` from materialized `report.json`. This aligns with the paper's primary binary outcome and is only valid for cases with a real evaluator report.")
    lines.append("- `Fix Rate (FR)`: `FAIL_TO_PASS.success / FAIL_TO_PASS.total`. For aggregation, report both `micro` and `macro` FR on the subset with valid evaluator reports.")
    lines.append("- `Pass Retention Rate (PRR)`: `PASS_TO_PASS.success / PASS_TO_PASS.total`. This complements Fix Rate by showing how much previously passing functionality was preserved.")
    lines.append("- `Regression Rate`: `PASS_TO_PASS.failure / PASS_TO_PASS.total`.")
    lines.append("- `Evaluation Coverage`: cases with a real `report.json` divided by total cases. This must be tracked separately from “evaluation task completed”, because evaluator crashes can still produce a completed worker entry.")
    lines.append("- `Efficiency Metrics`: session wall time, API time, turns, total cost, model input/output tokens, LLM request count, unique tool use count, and unique tool-result error count.")
    lines.append("- `Anomaly Metrics`: timeout cases, missing reports, evaluator environment errors, and report/returncode inconsistencies.")
    lines.append("")
    lines.append("## Audit")
    lines.append("")
    lines.append(f"- Inference summary rows: `{summary['inference_completed_cases']}/{summary['total_cases']}`")
    lines.append(f"- Evaluation worker completed tasks: `{summary['evaluation_completed_tasks']}/{summary['total_cases']}`")
    lines.append(f"- Materialized evaluator reports: `{summary['evaluation_report_cases']}/{summary['total_cases']}`")
    lines.append(f"- Evaluator error cases: `{summary['evaluation_error_cases']}/{summary['total_cases']}`")
    lines.append(f"- Known resolved cases: `{summary['resolved_true_cases']}/{summary['resolution_known_cases']}`")
    lines.append("")
    lines.append("## Key Findings")
    lines.append("")
    lines.append(f"- The run-level monitor says `48/48 inference` and `48/48 evaluation tasks`, but only `{summary['evaluation_report_cases']}` cases produced a real `report.json` artifact.")
    lines.append(f"- `Resolved Rate` can currently be computed only on the `{summary['resolution_known_cases']}` report-backed cases: `{fmt_rate(summary['resolution_rate_known_only'])}`.")
    lines.append(f"- `Resolved Rate` lower bound over all 48 cases is `{fmt_rate(summary['resolution_rate_lower_bound_all_cases'])}` because the remaining cases are evaluator-unknown, not proven unresolved.")
    lines.append(f"- `Fix Rate (micro, report-backed subset)` is `{fmt_rate(summary['f2p_micro_rate_known_only'])}`; `Pass Retention Rate (micro)` is `{fmt_rate(summary['p2p_micro_pass_rate_known_only'])}`.")
    lines.append(f"- Top evaluator failure signature is expected to be visible in anomaly counts: `{summary['anomaly_counts']}`.")
    lines.append("")
    lines.append("## Efficiency")
    lines.append("")
    lines.append(f"- Total CLI cost USD (cases with model usage): `{summary['total_cli_cost_usd']}`")
    lines.append(f"- Average CLI cost USD: `{summary['avg_cli_cost_usd']}`")
    lines.append(f"- Average CLI duration ms: `{summary['avg_cli_duration_ms']}`")
    lines.append(f"- Median CLI duration ms: `{summary['median_cli_duration_ms']}`")
    lines.append(f"- Average CLI turns: `{summary['avg_cli_turns']}`")
    lines.append(f"- Average unique tool uses per case: `{summary['avg_tool_use_count']}`")
    lines.append(f"- Average unique tool-result errors per case: `{summary['avg_tool_error_count']}`")
    lines.append(f"- Aggregate unique tool mix: `{json.dumps(summary['aggregate_tool_names'], ensure_ascii=False, sort_keys=True)}`")
    lines.append("")
    lines.append("## Top Cost Cases")
    lines.append("")
    lines.extend(markdown_table(top_cost, [
        ("instance_id", "case_id"),
        ("cli_total_cost_usd", "cost_usd"),
        ("cli_duration_ms", "duration_ms"),
        ("cli_num_turns", "turns"),
        ("tool_use_count", "tool_uses"),
    ]))
    lines.append("")
    lines.append("## Top Duration Cases")
    lines.append("")
    lines.extend(markdown_table(top_duration, [
        ("instance_id", "case_id"),
        ("cli_duration_ms", "duration_ms"),
        ("cli_total_cost_usd", "cost_usd"),
        ("cli_num_turns", "turns"),
        ("trace_request_count", "llm_requests"),
    ]))
    lines.append("")
    lines.append("## Evaluator Error Samples")
    lines.append("")
    sample_errors = eval_error_rows[:10]
    if sample_errors:
        lines.extend(markdown_table(sample_errors, [
            ("instance_id", "case_id"),
            ("eval_status", "eval_status"),
            ("eval_signature", "signature"),
            ("eval_signature_detail", "detail"),
        ]))
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Report-Backed Cases")
    lines.append("")
    if report_rows:
        lines.extend(markdown_table(report_rows, [
            ("instance_id", "case_id"),
            ("resolved", "resolved"),
            ("f2p_success", "f2p_pass"),
            ("f2p_total", "f2p_total"),
            ("f2p_rate", "f2p_rate"),
            ("p2p_success", "p2p_pass"),
            ("p2p_total", "p2p_total"),
            ("p2p_rate", "p2p_rate"),
        ]))
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Anomaly Cases")
    lines.append("")
    if anomalies:
        lines.extend(markdown_table(anomalies[:20], [
            ("instance_id", "case_id"),
            ("cli_subtype", "cli_subtype"),
            ("eval_status", "eval_status"),
            ("anomaly_flags", "anomalies"),
        ]))
    else:
        lines.append("- none")
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--repo-root", default="")
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parent
    output_dir = Path(args.output_dir).resolve() if args.output_dir else run_root / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    rows, aux = collect_case_rows(repo_root, run_root)
    summary = summarize_rows(rows, aux)

    (output_dir / "summary.json").write_text(
        json.dumps({"summary": summary, "cases": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(rows, output_dir / "cases.csv")
    write_markdown_report(rows, summary, output_dir / "report.md", run_root)


if __name__ == "__main__":
    main()
