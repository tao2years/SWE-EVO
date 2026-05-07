# dask__dask_2023.8.0_2023.8.1 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `dask__dask_2023.8.0_2023.8.1`
- `repo`: `dask/dask`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `inner_only`
- 一句话结论：
  `innercc` 把任务理解成多子任务 bundle，覆盖了 cgroup v2、groupby sort/split_out、`enforce_runtime_divisions`、`to_csv(single_file, mode='x')` 等多条线，因此拿到 `2/11` F2P；`claude-code` 主要锁在 dataframe backends / runtime divisions / groupby 一簇，却没有真正命中 evaluator 里的 CSV append / exclusive mode 主问题，最终 `0/11`。
- 根因标签：
  - `task_understanding_error`
  - `hypothesis_lock_in`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

release note关键点：

- cgroup v2 support to `cpu_count`
- multi-column `groupby(sort=True, split_out>1)`
- `DataFrame.enforce_runtime_divisions`
- `to_csv(..., mode="x", single_file=True)`
- `to_csv` append mode fix
- pyarrow `types_mapper`

`FAIL_TO_PASS`: `11` 条。

这是一个混合 case，至少包含：

1. runtime divisions / groupby
2. CSV single_file / append / exclusive mode
3. pyarrow backends

### 2.2 runner-level user query

两个 CLI 都收到同一条 release-note 聚合 prompt。

### 2.3 trace-level agent goals

- `innercc`
  - trace 中明确提到了：
    - cgroups v2
    - multi-column groupby
    - `mode="x"` + `single_file`
  - 说明它至少意识到任务有多条独立分支

- `claude-code`
  - trace 中主要围绕：
    - backends / types_mapper
    - `enforce_runtime_divisions`
    - groupby
  - 对 `to_csv(mode="x", single_file=True)` 这一条显得不够聚焦

### 2.4 official golden answer

从 patch 能看出的核心改动包括：

- `dask/dataframe/backends.py`
- `dask/dataframe/core.py`
- `dask/dataframe/groupby.py`
- `dask/dataframe/io/csv.py`
- `dask/system.py`

也就是说，这题不是单个 dataframe 方法修复，而是多个子系统联动。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `2/11` | `2793/2796` | `808342` | `176` | `175` | `?` |
| `claude-code` | `false` | `0/11` | `2796/2796` | `867878` | `76` | `125` | `?` |

`innercc` 有部分覆盖但伴随轻微回归；`claude-code` 零回归但完全没命中 F2P。

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/dask__dask_2023.8.0_2023.8.1/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/dask__dask_2023.8.0_2023.8.1/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/dask__dask_2023.8.0_2023.8.1/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/dask__dask_2023.8.0_2023.8.1/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 99 / Read 61 / Edit 15`
- 核心假设演化：
  - 一开始就显式关注 `mode="x"` + `single_file`
  - 也关注 groupby multi-column sort/split_out
  - 说明它至少覆盖了多个子任务

### 5.2 claude-code

- 工具分布：`Bash 57 / Read 42 / Grep 18`
- 核心假设演化：
  - 更偏 dataframe backends / dispatch / runtime divisions
  - 没有在 trace 里表现出对 CSV exclusive mode 问题的强关注

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | 这是多分支 case，需要同时补 CSV / groupby / system 兼容 | 修到少量，但不够 |
| `claude-code` | dataframe/groupby/backends 是主问题 | 完全漏掉关键 F2P |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

patch 覆盖：

- `backends.py`
- `core.py`
- `groupby.py`
- `io/csv.py`
- `system.py`

说明它确实按多子任务方向推进。

### 7.2 claude-code

patch 更聚焦于：

- backends / dispatch
- runtime divisions
- groupby

这解释了为什么在 evaluator 里会被 `to_csv(mode="x")` 相关失败直接击中。

## 8. Evaluation And Failure Evidence

`claude-code` 的 `test_output.txt` 里最有判别力的失败是：

```text
ValueError: must have exactly one of create/read/write/append mode
```

对应测试：

- `test_to_csv_single_file_exclusive_mode_no_overwrite`

这说明它没有覆盖 `single_file + mode="x"` 这一簇。

`innercc` 虽然也失败，但至少 trace 中有明确尝试这条线，因此比 `claude-code` 更接近任务面。

## 9. Root Cause

- `innercc`
  - 覆盖面较广但验证不足
- `claude-code`
  - 任务聚类错位，把关键 CSV 簇漏掉

## 10. CLI Optimization Opportunities

1. 当 release note 同时有 dataframe/backends 和 CSV 行为修复时，必须保证每个 F2P 簇至少有一条明确验证。
2. 零回归但零 F2P success 不代表“安全”；这通常是任务覆盖不足。
