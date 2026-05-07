# iterative__dvc_1.10.2_1.11.0 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_1.10.2_1.11.0`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_but_claude_closer`
- 一句话结论：
  这题真实目标是 stage collection 与 missing-deps hint 的组合修复。`innercc` 被 `pathlib`/`TmpDir` 噪声带偏，做了大范围兼容性补丁，还打坏了 `80` 条 P2P；`claude-code` 至少命中了 `Repo.get_stages()` / `_collect_from_default_dvcfile()` 这一半，但漏掉了 `tree/base.py` 里的 missing-deps 提示语义，因此 `0/6`。
- 根因标签：
  - `task_understanding_error`
  - `validation_gap`
  - `hypothesis_lock_in`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement` 里最相关的是：

- `tree: update hint about missing deps`
- `parse: parse target correctly for generated stages`

`FAIL_TO_PASS`: `6` 条：

- `tests/func/test_stage_load.py::test_collect_with_not_existing_dvcfile[*]` `4` 条
- `tests/unit/tree/test_base.py::test_missing_deps[None-Please ...]`
- `tests/unit/tree/test_base.py::test_missing_deps[conda-conda ...]`

`PASS_TO_PASS`: `150` 条。

所以这题的主轴是：

1. 缺失 stage file 时要抛对异常
2. missing-deps hint 文案要正确生成

### 2.2 runner-level user query

完整 prompt 给的是长 release note，但 F2P 已经把目标收窄到：

- stage load / collect
- missing deps hint

### 2.3 trace-level agent goals

- `innercc`
  - 逐步把任务改写成 `pathlib` / `PathInfo` / `TmpDir` 兼容修复
- `claude-code`
  - 至少把前四条 missing dvcfile 测试压到 `Repo.get_stages()` / `_collect_from_default_dvcfile()`
  - 但没有继续覆盖 `tree/base.py::test_missing_deps`

### 2.4 official golden answer

官方 patch 分两簇：

1. `dvc/repo/__init__.py` / stage collect 相关
   - 缺失 dvcfile 时抛 `StageFileDoesNotExistError`
2. `dvc/tree/base.py` / utils
   - 改进 missing deps hint，给出 `"Please report this bug to"` 或 `"conda install"` 等更精确文案

当前两边都没有同时命中这两簇。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `0/6` | `70/150` | `1110805` | `159` | `158` | `18` |
| `claude-code` | `false` | `0/6` | `145/150` | `3256125` | `104` | `103` | `19` |

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.10.2_1.11.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.10.2_1.11.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.10.2_1.11.0/cli_result.json)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.10.2_1.11.0/router_trace_bundle.json)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.10.2_1.11.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.10.2_1.11.0/test_output.txt)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.10.2_1.11.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.10.2_1.11.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.10.2_1.11.0/cli_result.json)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.10.2_1.11.0/router_trace_bundle.json)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.10.2_1.11.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.10.2_1.11.0/test_output.txt)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: noise-dominated exploration (`step 1-40`)

- 关键动作：
  - 大量看 `PathInfo`、`TmpDir`、Python 3.12 兼容
  - 修改 `dvc/path_info.py`
  - 修改 `tests/dir_helpers.py`
- 阶段结论：
  - 很快从 benchmark 主轴偏到环境兼容

#### Phase B: sprawling patch (`step 40-146`)

- 修改文件：
  - `dvc/path_info.py`
  - `tests/dir_helpers.py`
  - 其它 compat 相关位置
- 结果：
  - 没修到 missing stage file
  - 也没修到 missing deps hint

### 5.2 claude-code

#### Phase A: partial correct localization (`step 2-30`)

- 关键动作：
  - 读 `tests/func/test_stage_load.py`
  - 读 `dvc/repo/__init__.py`
- 阶段结论：
  - 正确命中了 `StageFileDoesNotExistError` 这半边

#### Phase B: half patch (`step 30-105`)

- 修改文件：
  - `dvc/repo/__init__.py`
- 结果：
  - 给 `get_stages()` / `_collect_from_default_dvcfile()` 加了 exists check
  - 但完全没碰 `tree/base.py` 的 missing deps 文案

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `1-40` | 主问题是 Python 3.12 path/pathlib 兼容 | environment noise、TmpDir errors | 当前环境确实出现大量 `pathlib` 异常 | 错，和 6 条 F2P 主轴错位 |
| `claude-code` | `2-30` | 主问题是缺失 dvcfile 没抛对异常 | stage_load tests、`Repo.get_stages()` | 前四条 F2P 都直接指向这里 | 只对了一半，漏掉 missing_deps |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- patch 大量围绕 `path_info` / `TmpDir`
- 其中还改了测试辅助
- 与官方主簇差异巨大

### 7.2 claude-code

- patch 只改：
  - `dvc/repo/__init__.py`
- 优点：
  - 命中缺失 stage file 的正确层
- 问题：
  - `tree/base.py::test_missing_deps` 的 `"Please report this bug to"` / `"conda install"` 提示完全没覆盖

## 8. Evaluation And Failure Evidence

来自 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.10.2_1.11.0/report.json)：

- 缺失 stage file 的 4 条 F2P 仍失败
- `test_missing_deps[*]` 2 条也失败

来自 [innercc test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.10.2_1.11.0/test_output.txt)：

```text
FAILED tests/unit/tree/test_base.py::test_missing_deps[None-Please report this bug to]
FAILED tests/unit/tree/test_base.py::test_missing_deps[conda-conda install]
```

说明 missing-deps hint 完全没修。

## 9. Root Cause

- `direct_root_cause`
  - `innercc` 完全修偏。
  - `claude-code` 只修了一半。
- `contributing_factors`
  - 当前环境的 `pathlib` / `TmpDir` 噪声过强。
  - 没有按 F2P 分成 `stage_load` 与 `missing_deps` 两簇分别闭环。
- `non_root_but_misleading_signals`
  - missing dvcfile 异常是很显眼的一簇，但它并不是全部。

## 10. CLI Optimization Opportunities

1. 对小型 multi-task case 也要先做簇划分。这里 `4+2` 的分布非常明显。验证方式是计划里必须显式列出每个 F2P 子簇，而不是只盯最前面的那一组。
2. 禁止让环境 compat 噪声挟持任务。若 patch 文件集中在 path/pathlib/test helper，而 F2P 文件集中在 repo/tree/stage，就必须重定位。
