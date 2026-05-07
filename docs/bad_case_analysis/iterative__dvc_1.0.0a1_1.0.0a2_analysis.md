# iterative__dvc_1.0.0a1_1.0.0a2 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_1.0.0a1_1.0.0a2`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_but_claude_closer`
- 一句话结论：
  这是一个超大 bundle case。`innercc` 几乎完全被 Python 3.12/pathlib 兼容问题带偏，改了 `PathInfo`、`StageLoader` 和 `tests/dir_helpers.py`，不仅 `68/68 F2P` 全挂，还把 `242/242 P2P` 全打坏；`claude-code` 至少只做了 `Mapping -> collections.abc` 的窄修，没有引入额外回归，但同样完全没命中 benchmark 真正关心的 plots/diff/stage/run-cache 主簇。
- 根因标签：
  - `task_understanding_error`
  - `termination_error`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement` 是一个极长 release bundle，里面同时包含：

- `plots: add plot markers to DVC files`
- `plots: dont zero y axis`
- `repo: Support streaming and pulling files on RepoTree/DvcTree.open()`
- `run/repro: rename build cache -> run cache`
- `params/metrics diff: implement tabulated markdown output`
- `pipeline file: disallow punctuation characters in stage name`
- `update: --recursive flag`
- 大量 plots/diff/run/stage/path/remote/scm 相关行为

`FAIL_TO_PASS`: `68` 条，明显聚集在：

- `tests/func/metrics/test_diff.py::test_no_commits`
- `tests/func/params/test_diff.py::test_no_commits`
- `tests/func/plots/test_plots.py::*`
- `tests/func/test_diff.py::test_no_commits`
- `tests/func/test_run_multistage.py::test_run_with_invalid_stage_name[*]`
- `tests/unit/command/test_diff.py::*`
- `tests/unit/command/test_plots.py::*`
- `tests/unit/repo/plots/test_data.py::*`
- `tests/unit/repo/plots/test_diff.py::*`
- `tests/unit/stage/test_run.py::test_run_stage_dry`
- `tests/unit/stage/test_stage.py::*`

`PASS_TO_PASS`: `242` 条。

这个分布已经足够说明：benchmark 主体是 plots/diff/stage/run 一整簇，不是 Python 3.12 compatibility hotfix。

### 2.2 runner-level user query

完整 prompt 给了长 release note 和 `68` 条 F2P。核心问题不在于 prompt 不清楚，而在于两个 CLI 都没有按 F2P 聚类来缩任务。

### 2.3 trace-level agent goals

- `innercc`
  - 从 `turn 1` 起就把任务收缩成：
    - `Mapping` 从 `collections.abc`
    - `pathlib._from_parts` / `_cparts` 在 Python 3.12 失效
  - 后续一直围绕 `PathInfo`、`TmpDir` 和 test helper 做兼容修补
- `claude-code`
  - 也锁在 Python 3.10+/3.12 compatibility
  - 但更窄，只改了 `StageLoader` 的 `Mapping` 导入

### 2.4 official golden answer

官方 patch 触及 `100+` 个文件。和当前 F2P 更相关的核心簇是：

- `dvc/command/diff.py`
- `dvc/command/plots.py`
- `dvc/repo/plots/data.py`
- `dvc/repo/plots/diff.py`
- `dvc/repo/plots/show.py`
- `dvc/repo/run.py`
- `dvc/repo/reproduce.py`
- `dvc/stage/run.py`
- `dvc/stage/utils.py`
- `dvc/utils/diff.py`

当前两边的 patch 都没有真正进入这个簇。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `0/68` | `0/242` | `7811` | `1` | `96` | `7` |
| `claude-code` | `false` | `0/68` | `242/242` | `357506` | `31` | `30` | `0` |

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.0a1_1.0.0a2/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.0a1_1.0.0a2/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.0a1_1.0.0a2/cli_result.json)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.0a1_1.0.0a2/router_trace_bundle.json)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.0.0a1_1.0.0a2/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.0.0a1_1.0.0a2/test_output.txt)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.0a1_1.0.0a2/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.0a1_1.0.0a2/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.0a1_1.0.0a2/cli_result.json)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.0a1_1.0.0a2/router_trace_bundle.json)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.0.0a1_1.0.0a2/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.0.0a1_1.0.0a2/test_output.txt)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: immediate compatibility fixation (`turn 1`)

- 关键动作：
  - grep `from collections import`
  - 修改 `dvc/stage/loader.py`
  - 修改 `dvc/path_info.py`
  - 修改 `tests/dir_helpers.py`
- 阶段结论：
  - 它几乎没有任务拆分与再定位过程
  - 直接把整题当成 Python 3.12 兼容补丁

### 5.2 claude-code

#### Phase A: same noise, narrower patch (`step 2-12`)

- 关键动作：
  - 看 failing tests
  - 读 `StageLoader`
  - 判断 `Mapping` 迁移是核心问题
- 阶段结论：
  - 同样被环境兼容问题主导

#### Phase B: one-line patch + early stop (`step 25-32`)

- 修改文件：
  - `dvc/stage/loader.py`
- 阶段结论：
  - 它做了更窄的 compat patch，因此没引入新回归
  - 但与 `68` 条 F2P 的真实主轴几乎无关

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `turn 1` | 整题主因是 Python 3.12 `pathlib`/ABC 兼容 | import errors、`_from_parts`/`_cparts` 失效 | 当前环境噪声非常强 | 错，和 benchmark 主体严重错位 |
| `claude-code` | `2-25` | 只要修 `Mapping` 导入就能恢复多数功能 | `collections.Mapping` 兼容问题 | 这是最显眼的一条 import error | 错，完全不足以解决 plots/diff/stage 主簇 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- patch 触及：
  - `dvc/stage/loader.py`
  - `dvc/path_info.py`
  - `tests/dir_helpers.py`
- 问题：
  - 其中还直接改了测试辅助文件
  - 完全偏离官方 patch 的核心行为模块

### 7.2 claude-code

- patch 只改：
  - `dvc/stage/loader.py`
- 优点：
  - 没扩散、没回归
- 问题：
  - 对 `68` 条 F2P 主体没有帮助

## 8. Evaluation And Failure Evidence

来自 [claude-code test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.0.0a1_1.0.0a2/test_output.txt)：

- 依旧有大量 target-level失败，例如：
  - `tests/unit/command/test_diff.py` 导入失败
  - `tests/unit/repo/plots/test_data.py` / `test_diff.py` 失败
  - `tests/func/plots/test_plots.py::*` 全部失败

而 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.0.0a1_1.0.0a2/report.json) 显示：

- `FAIL_TO_PASS = 0/68`
- `PASS_TO_PASS = 242/242`

`innercc` 更糟，[report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.0.0a1_1.0.0a2/report.json) 显示：

- `FAIL_TO_PASS = 0/68`
- `PASS_TO_PASS = 0/242`

## 9. Root Cause

- `direct_root_cause`
  - 两边都把超大 bundle 错缩成 Python 兼容性修补。
- `contributing_factors`
  - 当前环境里 `pathlib`/`collections` 兼容错误过于显眼。
  - 没有先按 F2P 模块分布判断任务体量。
- `non_root_but_misleading_signals`
  - Python 3.12 兼容问题是真问题，但不是 benchmark 的决定性主轴。

## 10. CLI Optimization Opportunities

1. 对超大 bundle，一旦 patch 只触及环境兼容模块，而 F2P 却集中在业务模块，必须强制重定位。验证方式是比较 patch 文件分布与 failing tests 文件分布。
2. 禁止为修 benchmark 直接改测试辅助文件，除非 user 明确允许或官方 patch 命中 tests。这里 innercc 的 `tests/dir_helpers.py` 修改就是典型越界信号。
