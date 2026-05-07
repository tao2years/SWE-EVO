# scikit-learn__scikit-learn_0.20.1_0.20.2 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `scikit-learn__scikit-learn_0.20.1_0.20.2`
- `repo`: `scikit-learn/scikit-learn`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_fixed_f2p_but_regressed_p2p`
- 一句话结论：
  这题是很典型的“目标测试修到了，但没有保持相邻语义路径”的案例。两个 CLI 都正确给 `JaccardDistance` 增加了 `nnz == 0 -> return 0.0` 的保护，因此 `1/1` F2P 通过；但两边都仍然打出了 `2` 条 P2P 回归，说明它们对 Jaccard 语义与周边 pairwise/neighbors 行为的验证不足。
- 根因标签：
  - `validation_gap`
  - `overfitted_to_f2p`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement` 的 relevant 部分：

- `sklearn.neighbors when metric=='jaccard' (bug fix)`

`FAIL_TO_PASS`: `1` 条。

- `sklearn/neighbors/tests/test_dist_metrics.py::test_pdist_bool_metrics[jaccard]`

`PASS_TO_PASS`: `438` 条。

这是一个单点 metric bug，但周边 pairwise/neighbors 路径很多，容易出现“只修到一个入口”的情况。

### 2.2 runner-level user query

CLI 收到的 prompt 非常聚焦：修 `jaccard` metric 的一个 failing test。

### 2.3 trace-level agent goals

两个 CLI 的内部目标几乎完全一致：

- `JaccardDistance.dist()` 在两个全零向量上出现 `0/0`
- 需要在 `nnz == 0` 时返回 `0.0`

### 2.4 official golden answer

从 patch 看，官方核心 hunk 基本就是：

```diff
if nnz == 0:
    return 0.0
```

这是一个很窄的行为修复。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `1/1` | `436/438` | `73014` | `19` | `18` | `3` |
| `claude-code` | `false` | `1/1` | `436/438` | `218216` | `22` | `21` | `2` |

两边几乎完全对称：

- 都修到了 F2P
- 都留下 2 条 P2P 回归

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/scikit-learn__scikit-learn_0.20.1_0.20.2/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/scikit-learn__scikit-learn_0.20.1_0.20.2/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/scikit-learn__scikit-learn_0.20.1_0.20.2/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/scikit-learn__scikit-learn_0.20.1_0.20.2/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 9 / Read 7 / Edit 2`
- 关键路径：
  - 很快定位 `JaccardDistance.dist`
  - 确认 `nnz == 0` 导致除零
  - 直接补保护分支

### 5.2 claude-code

- 工具分布：`Bash 12 / Grep 6 / Edit 2`
- 关键路径：
  - 同样快速聚焦到 Jaccard 实现
  - 同样认为全零向量应返回 `0.0`

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | 两个全零向量比较时 Jaccard 距离应为 `0.0` | F2P 正确 |
| `claude-code` | 同上 | F2P 正确 |

## 7. Patch And Code-Level Analysis

两边 patch 一致：

```diff
if nnz == 0:
    return 0.0
```

说明定位和修复本身都对。

## 8. Evaluation And Failure Evidence

这题的关键信号在于：

- `F2P = 1/1`
- 但 `P2P = 436/438`

说明单测修复成功，但对周边 Jaccard / distance family 的影响没有进一步验证。

## 9. Root Cause

- `validation_gap`
  - 目标测试过了之后，没有对邻近 neighbors / pairwise 路径做额外回归检查
- `overfitted_to_f2p`
  - patch 只对单个 failing assertion 做了最小修复，没确认是否满足更广的 metric 语义

## 10. CLI Optimization Opportunities

1. 对“单 metric / 单 formula”类 bug，除了 exact F2P 外，至少要补一条邻近语义回归测试。
2. 如果 F2P 全过但仍有少量 P2P 回归，不能把任务视为完成。
