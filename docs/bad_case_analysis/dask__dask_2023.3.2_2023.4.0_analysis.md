# dask__dask_2023.3.2_2023.4.0 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `dask__dask_2023.3.2_2023.4.0`
- `repo`: `dask/dask`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_inner_closer`
- 一句话结论：
  这是另一个打包 release case。`innercc` 主要锁在 pandas 2.x / property / categorical / groupby cov 等兼容问题，修到 `3/61`；`claude-code` 基本也锁在同一簇，但只改了少数 dataframe compat 代码，最终 `0/61`。两边都没覆盖 HDF / parquet / IO 这一大簇 failing tests。
- 根因标签：
  - `task_understanding_error`
  - `hypothesis_lock_in`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

release note包含：

- `update_defaults`
- CLI config command
- `read_json` engine string
- revert grouper changes
- `GroupBy.cov` with non-numeric grouping column
- `Index` numeric dtype support
- parquet partitioning dtype preservation
- HDF annotation / IO family修复

`FAIL_TO_PASS`: `61` 条。

从 F2P 分布看，至少有两大簇：

1. dataframe/groupby/compat
2. HDF / IO / parquet

### 2.2 runner-level user query

两个 CLI 收到的是同一条 release-note 聚合 prompt，要求通过 `61` 条 F2P。

### 2.3 trace-level agent goals

- `innercc`
  - 明确关注 `get_named_args` / property object / pandas compat
  - 也改了 groupby / backends / IO 层的部分兼容代码

- `claude-code`
  - trace 里直接说“multiple issues”
  - 但实际 patch 几乎全落在 dataframe compat / groupby cov 一簇

### 2.4 official golden answer

官方 patch 很大，但两边共识命中的核心之一是：

- pandas 2.x / dtype API / property introspection 兼容

问题在于：

- benchmark 还包含 HDF / IO / parquet 等大簇
- 两边都没有完整覆盖这些簇

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `3/61` | `6241/6246` | `699400` | `170` | `169` | `1` |
| `claude-code` | `false` | `0/61` | `6246/6246` | `542167` | `47` | `82` | `24` |

两边都失败，但 `innercc` 至少拿下了 `groupby_cov_non_numeric_grouping_column` 和一条 `valid_divisions`。

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/dask__dask_2023.3.2_2023.4.0/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/dask__dask_2023.3.2_2023.4.0/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/dask__dask_2023.3.2_2023.4.0/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/dask__dask_2023.3.2_2023.4.0/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 85 / Read 58 / Edit 26`
- 核心假设：
  - `get_named_args` 在 property object 上的 `TypeError`
  - categorical / pandas dtype compatibility
  - groupby cov non-numeric grouping column
- 说明：
  - 它至少试图沿 dataframe compatibility 簇扩展开

### 5.2 claude-code

- 工具分布：`Bash 37 / Glob 18 / Grep 13 / Read 12`
- 核心假设：
  - “multiple issues” 但实际落笔仍集中在 dataframe compat 一簇
- 问题：
  - 对 HDF / IO failing tests 基本没有任务展开

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | pandas/property/groupby cov 是主故障簇 | 修到少量，但覆盖率仍不足 |
| `claude-code` | dataframe compat 簇足以代表整体 | 错，HDF/IO 簇完全漏掉 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

修改面覆盖：

- `_compat.py`
- `backends.py`
- `groupby.py`
- `io/json.py`

说明它并非只改一点，但仍然只覆盖到 dataframe compat 主簇。

### 7.2 claude-code

patch 基本没有覆盖 HDF / IO 主簇，因而 `F2P = 0/61` 很自然。

## 8. Evaluation And Failure Evidence

- `innercc` 修成：
  - `test_groupby_cov_non_numeric_grouping_column[disk]`
  - `... [tasks]`
  - `test_valid_divisions[divisions4-True]`
- 两边都未修成的大头是：
  - `tests/test_hdf.py::*`

这说明：

- 真正主导 resolved 的大簇在 HDF / IO
- 两边都把任务重心放错了

## 9. Root Cause

- `task_understanding_error`
  - 把 release bundle 理解成 dataframe compat 修复，而不是 HDF/IO 主导的混合问题
- `hypothesis_lock_in`
  - 一旦看见 property / dtype / groupby cov 相关失败，就在这一簇里持续迭代

## 10. CLI Optimization Opportunities

1. failing tests 如果明显分成 IO 簇和 dataframe compat 簇，必须显式拆任务。
2. 若已修成少量 F2P，但剩余失败集中在另一子系统，不允许用“已有进展”判断任务完成。
