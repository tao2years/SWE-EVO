# modin-project__modin_0.24.0_0.24.1 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `modin-project__modin_0.24.0_0.24.1`
- `repo`: `modin-project/modin`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_same_target`
- 一句话结论：
  这是一个单目标 hotfix case，目标非常集中：`sort_values` 之后 cache 不正确。两边都把问题定位在 row/column length cache，但实际失败断言指向的是 `_column_widths_cache`，而两边的 patch 都没有真正修到这一点，所以 `1/1` F2P 继续失败。
- 根因标签：
  - `localization_error`
  - `hypothesis_lock_in`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

- `FIX-#6607: Fix incorrect cache after .sort_values() (#6608)`

`FAIL_TO_PASS`: `1` 条。

单测名：

- `modin/test/storage_formats/pandas/test_internals.py::test_sort_values_cache`

这是标准的单点 hotfix case。

### 2.2 runner-level user query

CLI 收到的是单点 hotfix prompt，目标非常明确：修复 `sort_values` 后 cache 错误。

### 2.3 trace-level agent goals

- `innercc`
  - 锁定在 `ModinIndex.maybe_specify_new_frame_ref`
  - 认为问题是 index callable 仍引用旧 frame

- `claude-code`
  - 锁定在 `sort_by` 没保留 row lengths cache
  - 认为问题是 `_row_lengths_cache` 被丢了

### 2.4 official golden answer

从 evaluator 失败断言看，真正关心的是：

```text
assert mf_res._column_widths_cache == [32, 32]
```

也就是说 golden behavior 针对的是 `column widths cache`，不是 index reference，也不是 row lengths cache。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `0/1` | `171/171` | `1225945` | `153` | `152` | `?` |
| `claude-code` | `false` | `0/1` | `171/171` | `824860` | `54` | `52` | `?` |

两边都没引入回归，但也都没修到目标。

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/modin-project__modin_0.24.0_0.24.1/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/modin-project__modin_0.24.0_0.24.1/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/modin-project__modin_0.24.0_0.24.1/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/modin-project__modin_0.24.0_0.24.1/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 98 / Read 53 / Edit 1`
- 核心假设：
  - `ModinIndex` 的 callable reference 没切到新 frame
- 问题：
  - trace 虽长，但始终围绕 index reference 展开

### 5.2 claude-code

- 工具分布：`Grep 28 / Read 12 / Bash 10 / Edit 1`
- 核心假设：
  - `_row_lengths_cache` 没被保留
- 问题：
  - evaluator 断言真正看的是 `_column_widths_cache`

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | index callable 仍指向旧 frame | 错层定位 |
| `claude-code` | row lengths cache 丢失 | 也错层定位 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

修改：

- `modin/core/dataframe/pandas/metadata/index.py`

### 7.2 claude-code

修改：

- `modin/core/dataframe/pandas/dataframe/dataframe.py`

两边都改了“看起来相关”的 cache / reference 点，但没有触到 evaluator 断言锁定的 `_column_widths_cache` 维护逻辑。

## 8. Evaluation And Failure Evidence

决定性失败断言：

```text
assert mf_res._column_widths_cache == [32, 32]
E assert [64] == [32, 32]
```

这说明：

- row-wise sort 不应该把 column widths collapse 成 `[64]`
- 两边 patch 都没命中这个真实故障点

## 9. Root Cause

- `localization_error`
  - 两边都修到了“附近”，但不是 evaluator 真正断言的 cache
- `hypothesis_lock_in`
  - 一旦形成 row lengths / index reference 假设，就没回到失败断言重新定位

## 10. CLI Optimization Opportunities

1. 对单测失败中直接出现私有字段断言的 case，优先以断言字段为定位锚点。
2. 单点 hotfix case 不应长时间停留在“相邻结构推理”，应直接逆向断言字段的写入路径。
