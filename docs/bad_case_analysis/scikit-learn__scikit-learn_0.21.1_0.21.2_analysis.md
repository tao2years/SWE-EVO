# scikit-learn__scikit-learn_0.21.1_0.21.2 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `scikit-learn__scikit-learn_0.21.1_0.21.2`
- `repo`: `scikit-learn/scikit-learn`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_fixed_f2p_but_regressed_p2p`
- 一句话结论：
  这题和上一个 scikit-learn case 很像：两边都命中了目标 F2P 的数值稳定性修复，但补丁副作用很大，最终都留下 `26` 条 P2P 回归。说明它们找到了 `CCA` 的一个稳定性热点，却没有验证 cross-decomposition 邻域的整体行为。
- 根因标签：
  - `validation_gap`
  - `overfitted_to_f2p`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement` 的 relevant 部分：

- `Fix a bug in cross_decomposition.CCA improving numerical stability when Y is close to zero`

`FAIL_TO_PASS`: `1` 条。

- `sklearn/cross_decomposition/tests/test_pls.py::test_scale_and_stability`

`PASS_TO_PASS`: `293` 条。

这是一个单模型数值稳定性修复，但它的相邻测试簇很多。

### 2.2 runner-level user query

CLI 收到的是单点数值稳定性修复 prompt。

### 2.3 trace-level agent goals

- `innercc`
  - 把问题看成：
    - `Y` 接近零时需要更稳地处理 `nipals`

- `claude-code`
  - 也锁定在 `_nipals_twoblocks_inner_loop`
  - 但加入的是更保守的 `pinv2` / zero-matrix 分支

### 2.4 official golden answer

从 patch 看，两边都改了 `sklearn/cross_decomposition/pls_.py`，说明目标落点没错。但 evaluator 结果表明：

- 单点修正不足以保持整个 `PLS/CCA` 邻域稳定

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `1/1` | `267/293` | `207872` | `33` | `32` | `2` |
| `claude-code` | `false` | `1/1` | `267/293` | `744473` | `48` | `50` | `3` |

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/scikit-learn__scikit-learn_0.21.1_0.21.2/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/scikit-learn__scikit-learn_0.21.1_0.21.2/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/scikit-learn__scikit-learn_0.21.1_0.21.2/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/scikit-learn__scikit-learn_0.21.1_0.21.2/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 21 / Read 10 / Edit 1`
- 核心路径：
  - 直接实现一个更稳定的 `Y` near-zero 分支

### 5.2 claude-code

- 工具分布：`Bash 30 / Read 8 / Grep 6 / Edit 4`
- 核心路径：
  - 同样围绕 `_nipals_twoblocks_inner_loop`
  - 在 `pinv2` 前加零范数保护

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | `Y` close to zero 需要在主外循环里做稳定性掩码处理 | F2P 修到了 |
| `claude-code` | `pinv2(X/Y)` 对近零矩阵不稳定，需要零矩阵替代 | F2P 也修到了 |

## 7. Patch And Code-Level Analysis

两边都命中了对的文件，但采用的局部修复策略不同；不管哪种，最终都没保住 `26` 条 P2P，说明只看目标测试还不够。

## 8. Evaluation And Failure Evidence

关键结果：

- `F2P = 1/1`
- `P2P = 267/293`

说明：

- 单点稳定性修复成立
- 但 cross-decomposition 邻域其它行为被破坏

## 9. Root Cause

- `validation_gap`
  - 没有围绕 `PLS/CCA` 相邻测试簇做补充验证
- `overfitted_to_f2p`
  - 过度针对 `test_scale_and_stability`

## 10. CLI Optimization Opportunities

1. 数值稳定性类单测修复后，必须补同模块邻近测试簇验证。
2. 若 F2P 全过但同模块 P2P 大量回归，应触发“局部修复过拟合”告警。
