# official48 Run Summary

- Run root: `/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634`
- Data sources: `infer/inference_summary.json`, per-case `cli_result.json`, `router_trace_bundle.json`, `eval_worker_status.json`, `eval_worker_logs/*.log`, and any materialized `report.json` files.

## Metric Design

- `Resolved Rate (RR)`: case-level `resolved == true` from materialized `report.json`. This aligns with the paper's primary binary outcome and is only valid for cases with a real evaluator report.
- `Fix Rate (FR)`: `FAIL_TO_PASS.success / FAIL_TO_PASS.total`. For aggregation, report both `micro` and `macro` FR on the subset with valid evaluator reports.
- `Pass Retention Rate (PRR)`: `PASS_TO_PASS.success / PASS_TO_PASS.total`. This complements Fix Rate by showing how much previously passing functionality was preserved.
- `Regression Rate`: `PASS_TO_PASS.failure / PASS_TO_PASS.total`.
- `Evaluation Coverage`: cases with a real `report.json` divided by total cases. This must be tracked separately from “evaluation task completed”, because evaluator crashes can still produce a completed worker entry.
- `Efficiency Metrics`: session wall time, API time, turns, total cost, model input/output tokens, LLM request count, unique tool use count, and unique tool-result error count.
- `Anomaly Metrics`: timeout cases, missing reports, evaluator environment errors, and report/returncode inconsistencies.

## Audit

- Inference summary rows: `48/48`
- Evaluation worker completed tasks: `48/48`
- Materialized evaluator reports: `48/48`
- Evaluator error cases: `0/48`
- Known resolved cases: `12/48`

## Key Findings

- The run-level monitor says `48/48 inference` and `48/48 evaluation tasks`, but only `48` cases produced a real `report.json` artifact.
- `Resolved Rate` can currently be computed only on the `48` report-backed cases: `25.0%`.
- `Resolved Rate` lower bound over all 48 cases is `25.0%` because the remaining cases are evaluator-unknown, not proven unresolved.
- `Fix Rate (micro, report-backed subset)` is `2.9%`; `Pass Retention Rate (micro)` is `68.8%`.
- Top evaluator failure signature is expected to be visible in anomaly counts: `{'cli_reported_error': 1, 'inference_timeout': 1}`.

## Efficiency

- Total CLI cost USD (cases with model usage): `569.191248`
- Average CLI cost USD: `12.110452085106383`
- Average CLI duration ms: `414092.57446808513`
- Median CLI duration ms: `254649.0`
- Average CLI turns: `75.93617021276596`
- Average unique tool uses per case: `95.60416666666667`
- Average unique tool-result errors per case: `4.291666666666667`
- Aggregate unique tool mix: `{"Bash": 2843, "Edit": 427, "Read": 1319}`

## Top Cost Cases

| case_id | cost_usd | duration_ms | turns | tool_uses |
| --- | --- | --- | --- | --- |
| dask__dask_2022.9.2_2022.10.0 | 74.0782 | 1949384 | 370 | 516 |
| iterative__dvc_0.52.1_0.53.1 | 50.2519 | 14640 | 1 | 230 |
| pydantic__pydantic_v2.7.0_v2.7.1 | 46.5431 | 1506752 | 195 | 194 |
| conan-io__conan_2.0.14_2.0.15 | 37.6965 | 869964 | 209 | 208 |
| dask__dask_2023.8.0_2023.8.1 | 29.0286 | 808342 | 176 | 175 |

## Top Duration Cases

| case_id | duration_ms | cost_usd | turns | llm_requests |
| --- | --- | --- | --- | --- |
| dask__dask_2022.9.2_2022.10.0 | 1949384 | 74.0782 | 370 | 482 |
| pydantic__pydantic_v2.7.0_v2.7.1 | 1506752 | 46.5431 | 195 | 191 |
| modin-project__modin_0.24.0_0.24.1 | 1225945 | 27.6809 | 153 | 152 |
| iterative__dvc_1.10.2_1.11.0 | 1110805 | 20.4411 | 159 | 146 |
| conan-io__conan_2.0.2_2.0.3 | 956374 | 21.4250 | 129 | 114 |

## Evaluator Error Samples

- none

## Report-Backed Cases

| case_id | resolved | f2p_pass | f2p_total | f2p_rate | p2p_pass | p2p_total | p2p_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| conan-io__conan_2.0.14_2.0.15 | False | 0 | 72 | 0.0000 | 161 | 649 | 0.2481 |
| conan-io__conan_2.0.2_2.0.3 | False | 0 | 8 | 0.0000 | 315 | 317 | 0.9937 |
| dask__dask_2022.9.2_2022.10.0 | False | 13 | 44 | 0.2955 | 2311 | 2861 | 0.8078 |
| dask__dask_2023.3.2_2023.4.0 | False | 3 | 61 | 0.0492 | 6241 | 6246 | 0.9992 |
| dask__dask_2023.6.0_2023.6.1 | False | 0 | 105 | 0.0000 | 3327 | 3415 | 0.9742 |
| dask__dask_2023.6.1_2023.7.0 | False | 3 | 5 | 0.6000 | 707 | 707 | 1.0000 |
| dask__dask_2023.8.0_2023.8.1 | False | 2 | 11 | 0.1818 | 2793 | 2796 | 0.9989 |
| dask__dask_2023.9.2_2023.9.3 | True | 2 | 2 | 1.0000 | 1629 | 1629 | 1.0000 |
| dask__dask_2024.1.0_2024.1.1 | False | 0 | 2774 | 0.0000 | 0 | 5778 | 0.0000 |
| dask__dask_2024.3.1_2024.4.0 | True | 2 | 2 | 1.0000 | 2747 | 2747 | 1.0000 |
| iterative__dvc_0.30.0_0.30.1 | True | 1 | 1 | 1.0000 | 12 | 12 | 1.0000 |
| iterative__dvc_0.33.1_0.34.0 | False | 0 | 1 | 0.0000 | 57 | 77 | 0.7403 |
| iterative__dvc_0.35.3_0.35.4 | False | 1 | 2 | 0.5000 | 26 | 26 | 1.0000 |
| iterative__dvc_0.52.1_0.53.1 | False | 0 | 132 | 0.0000 | 0 | 0 | None |
| iterative__dvc_0.89.0_0.90.0 | False | 0 | 27 | 0.0000 | 99 | 282 | 0.3511 |
| iterative__dvc_0.91.2_0.91.3 | False | 0 | 2 | 0.0000 | 17 | 17 | 1.0000 |
| iterative__dvc_0.92.0_0.92.1 | True | 4 | 4 | 1.0000 | 6 | 6 | 1.0000 |
| iterative__dvc_1.0.0a1_1.0.0a2 | False | 0 | 68 | 0.0000 | 0 | 242 | 0.0000 |
| iterative__dvc_1.0.0b6_1.0.0 | False | 0 | 2 | 0.0000 | 2 | 2 | 1.0000 |
| iterative__dvc_1.0.1_1.0.2 | False | 1 | 2 | 0.5000 | 19 | 19 | 1.0000 |
| iterative__dvc_1.1.0_1.1.1 | True | 6 | 6 | 1.0000 | 28 | 28 | 1.0000 |
| iterative__dvc_1.1.7_1.1.8 | False | 5 | 8 | 0.6250 | 82 | 82 | 1.0000 |
| iterative__dvc_1.10.2_1.11.0 | False | 0 | 6 | 0.0000 | 70 | 150 | 0.4667 |
| iterative__dvc_1.11.12_1.11.13 | True | 2 | 2 | 1.0000 | 4 | 4 | 1.0000 |
| iterative__dvc_1.6.3_1.6.4 | False | 1 | 9 | 0.1111 | 2 | 2 | 1.0000 |
| iterative__dvc_2.19.0_2.20.0 | True | 14 | 14 | 1.0000 | 66 | 66 | 1.0000 |
| iterative__dvc_2.21.1_2.21.2 | False | 0 | 1 | 0.0000 | 5 | 8 | 0.6250 |
| iterative__dvc_2.5.0_2.5.1 | False | 0 | 5 | 0.0000 | 22 | 24 | 0.9167 |
| iterative__dvc_2.58.1_2.58.2 | False | 1 | 2 | 0.5000 | 20 | 20 | 1.0000 |
| iterative__dvc_2.7.2_2.7.3 | False | 0 | 4 | 0.0000 | 34 | 34 | 1.0000 |
| iterative__dvc_2.8.1_2.8.2 | False | 0 | 133 | 0.0000 | 662 | 662 | 1.0000 |
| iterative__dvc_3.12.0_3.13.0 | True | 33 | 33 | 1.0000 | 44 | 44 | 1.0000 |
| iterative__dvc_3.13.3_3.14.0 | False | 0 | 13 | 0.0000 | 36 | 36 | 1.0000 |
| iterative__dvc_3.15.0_3.15.1 | True | 1 | 1 | 1.0000 | 66 | 66 | 1.0000 |
| iterative__dvc_3.4.0_3.5.0 | True | 2 | 2 | 1.0000 | 26 | 26 | 1.0000 |
| iterative__dvc_3.43.1_3.44.0 | False | 0 | 22 | 0.0000 | 3 | 104 | 0.0288 |
| modin-project__modin_0.24.0_0.24.1 | False | 0 | 1 | 0.0000 | 171 | 171 | 1.0000 |
| modin-project__modin_0.25.0_0.25.1 | False | 0 | 68 | 0.0000 | 447 | 447 | 1.0000 |
| modin-project__modin_0.27.0_0.27.1 | True | 4 | 4 | 1.0000 | 883 | 883 | 1.0000 |
| psf__requests_v2.12.2_v2.12.3 | False | 0 | 4 | 0.0000 | 0 | 109 | 0.0000 |
| psf__requests_v2.27.0_v2.27.1 | True | 2 | 2 | 1.0000 | 185 | 185 | 1.0000 |
| psf__requests_v2.4.0_v2.4.1 | False | 2 | 2 | 1.0000 | 135 | 136 | 0.9926 |
| psf__requests_v2.9.0_v2.9.1 | False | 1 | 1 | 1.0000 | 84 | 85 | 0.9882 |
| pydantic__pydantic_v2.6.0b1_v2.6.0 | False | 0 | 1 | 0.0000 | 51 | 51 | 1.0000 |
| pydantic__pydantic_v2.7.0_v2.7.1 | False | 4 | 234 | 0.0171 | 1476 | 1477 | 0.9993 |
| pydantic__pydantic_v2.7.1_v2.7.2 | False | 0 | 3 | 0.0000 | 403 | 4584 | 0.0879 |
| scikit-learn__scikit-learn_0.20.1_0.20.2 | False | 1 | 1 | 1.0000 | 436 | 438 | 0.9954 |
| scikit-learn__scikit-learn_0.21.1_0.21.2 | False | 1 | 1 | 1.0000 | 267 | 293 | 0.9113 |

## Anomaly Cases

| case_id | cli_subtype | eval_status | anomalies |
| --- | --- | --- | --- |
| iterative__dvc_0.30.0_0.30.1 | timeout | report_available | ["cli_reported_error", "inference_timeout"] |
