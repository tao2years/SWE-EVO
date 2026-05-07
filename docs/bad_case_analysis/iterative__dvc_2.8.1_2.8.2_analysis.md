# iterative__dvc_2.8.1_2.8.2 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_2.8.1_2.8.2`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_but_claude_closer`
- 一句话结论：
  这是一个超大 release bundle。`innercc` 从第一步起就被当前环境里的 `fsspec_loop` / async 兼容噪声带偏，只修了 `azure/http` 两个文件，`0/133 F2P`；`claude-code` 虽然也没对准 benchmark 主体，但至少命中了 `machine rename/status` 这一小簇，拿到 `8/133`。两边都没有真正根据 F2P 分布做任务拆分。
- 根因标签：
  - `task_understanding_error`
  - `hypothesis_lock_in`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement` 是一个极长的 bundle，包含：

- `dvc machine rename`
- `dvc machine status`
- `exp show md`
- `exp/metrics/params diff` 列名变更
- `set-param` 新参数限制
- `plots template/package` 相关改动
- `dvcfs` / objects tree / output meta / scm / pathspec / remote / UI 等大批兼容与功能修复

`FAIL_TO_PASS`: `133` 条。

其中从前几条就能看出这题至少横跨多簇：

- `tests/func/experiments/test_experiments.py::test_run_metrics`
- `tests/func/machine/test_machine_config.py::test_machine_rename_*`
- `tests/func/machine/test_machine_status.py::test_status`
- `tests/func/objects/db/test_index.py::*`
- `tests/func/test_add.py::*`
- `tests/func/test_data_cloud.py::*`
- `tests/func/test_import_url.py::*`
- `tests/unit/command/test_machine.py::*`
- `tests/unit/command/test_metrics.py::*`
- `tests/unit/command/test_params.py::*`
- `tests/unit/fs/test_dvc.py::*`
- `tests/unit/test_compare.py::*`
- `tests/unit/test_info.py::*`
- `tests/unit/test_pathspec_math.py::*`

`PASS_TO_PASS`: `662` 条。

这个 case 的关键不是某一个 API bug，而是：

- benchmark 是一个重型多子系统 bundle
- F2P 明显分布在 machine、experiments、metrics/params diff、dvcfs/objects/tree、remote/cloud 等多个簇
- 任何只修单一兼容点或单一 feature 的 patch，都不可能 resolve

### 2.2 runner-level user query

两个 CLI 实际收到的是完整 release note + `133` 条 failing tests 的组合。这里不再全文展开；关键是 prompt 明确给出了超大 F2P 集合，但两边都没有先做簇划分。

### 2.3 trace-level agent goals

- `innercc`
  - 从最开始就被环境噪声主导，核心目标逐步重写成：
    - “修掉 `fsspec.asyn.fsspec_loop` 兼容问题”
    - “让 Azure/HTTP FS 在当前环境下可工作”
- `claude-code`
  - 主要把任务重写成：
    - “实现 `dvc machine rename/status`”
  - 这至少对应了 release note 里的一个真实子功能，但只覆盖了整个 bundle 的极小一部分

### 2.4 official golden answer

官方 patch 触及 `70+` 个文件。对当前 F2P 更相关的主簇包括：

- `dvc/command/machine.py` 与 `dvc/machine/*`
  - 新增 `rename` / `status`
- `dvc/command/metrics.py` / `dvc/command/params.py`
  - `a_rev/b_rev` 列名与 diff 语义
- `dvc/fs/dvc.py`
  - `ls()` / `info()` / `walk()` / granular hash 行为
- `dvc/repo/experiments/__init__.py`
  - `--set-param` 新参数处理
- `dvc/repo/plots/template.py`
  - package templates
- `dvc/ignore.py`
  - pathspec 兼容
- 大量 objects/tree/output/meta/scm/remote/cloud 相关修复

当前最重要的事实不是某个 hunk 本身，而是：

- 官方答案明显是 bundle 级 patch
- 它绝不是只修 `azure/http`，也不是只修 `machine` 子命令

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `0/133` | `662/662` | `250245` | `47` | `46` | `5` |
| `claude-code` | `false` | `8/133` | `662/662` | `2166828` | `93` | `92` | `10` |

`claude-code` 过掉的 `8` 条 F2P 都是 `tests/unit/command/test_machine.py::*` 这一小簇，说明它至少命中了一个真实子任务；`innercc` 则 `0/133`。

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.8.1_2.8.2/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.8.1_2.8.2/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.8.1_2.8.2/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.8.1_2.8.2/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.8.1_2.8.2/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.8.1_2.8.2/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_2.8.1_2.8.2.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.8.1_2.8.2/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.8.1_2.8.2/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.8.1_2.8.2/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.8.1_2.8.2/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.8.1_2.8.2/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.8.1_2.8.2/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.8.1_2.8.2/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.8.1_2.8.2/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.8.1_2.8.2/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_2.8.1_2.8.2.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.8.1_2.8.2/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.8.1_2.8.2/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.8.1_2.8.2/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: environment-noise capture (`step 1-15`)

- 关键动作：
  - 跑 `test_machine.py::test_rename`
  - 检查 `fsspec` 版本
  - grep `fsspec_loop`
  - 对 `asyncio.run()` 与 `aiohttp.TCPConnector` 做本地 probe
- 阶段结论：
  - 很快把环境兼容噪声误认为 benchmark 主轴

#### Phase B: narrow fix on wrong subsystem (`step 15-47`)

- 修改文件：
  - `dvc/fs/azure.py`
  - `dvc/fs/http.py`
- 阶段结论：
  - patch 只覆盖当前环境里的 `fsspec_loop` 缺失
  - 完全没触及 machine、experiments、dvcfs、objects/tree 等真实 F2P 主簇

### 5.2 claude-code

#### Phase A: machine-cluster fixation (`step 2-30`)

- 关键动作：
  - 读 `dvc/command/machine.py`
  - 读 `dvc/machine/__init__.py`
  - 读 backend base
- 阶段结论：
  - 把任务压缩成“实现 machine rename/status”

#### Phase B: command-layer implementation (`step 30-93`)

- 修改文件：
  - `dvc/command/machine.py`
  - `dvc/machine/__init__.py`
  - `dvc/machine/backend/base.py`
- 阶段结果：
  - 成功修通 `tests/unit/command/test_machine.py::*` 的 `8` 条 F2P
  - 但对整个 `133` 条 bundle 来说，这只是极小一簇

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `1-15` | 当前问题主轴是 `fsspec_loop` 环境兼容 | import/probe、`fsspec` 版本、`fsspec_loop` grep | 环境里确实存在兼容报错 | 错误，只是局部噪声，不是 `133` 条 F2P 的主体 |
| `claude-code` | `2-30` | benchmark 主要想新增 `machine rename/status` | machine tests、release note 条目 | 这些条目是 release note 中最显眼的新 feature | 只对了一小簇，没做任务规模判断 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- patch 文件：
  - `dvc/fs/azure.py`
  - `dvc/fs/http.py`
- 与 official patch 的关系：
  - 命中了一些真实官方改动文件外的兼容点，但和 benchmark F2P 基本脱节
- 结果：
  - `0/133 F2P`

### 7.2 claude-code

- patch 文件：
  - `dvc/command/machine.py`
  - `dvc/machine/__init__.py`
  - `dvc/machine/backend/base.py`
- 与 official patch 的关系：
  - 的确命中了 bundle 里 machine 功能簇
  - 但没有触及大量其他 F2P 涉及的真实模块

## 8. Evaluation And Failure Evidence

来自 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.8.1_2.8.2/report.json)：

- `claude-code` 只过了：
  - `tests/unit/command/test_machine.py::test_add`
  - `tests/unit/command/test_machine.py::test_create`
  - `tests/unit/command/test_machine.py::test_destroy`
  - `tests/unit/command/test_machine.py::test_list`
  - `tests/unit/command/test_machine.py::test_modified`
  - `tests/unit/command/test_machine.py::test_remove`
  - `tests/unit/command/test_machine.py::test_ssh`
  - `tests/unit/command/test_machine.py::test_status`

而 machine 功能对应的 function / config tests 仍失败：

- `tests/func/machine/test_machine_config.py::test_machine_rename_*`
- `tests/func/machine/test_machine_status.py::test_status`

说明它连 machine 簇都只修到了 command/unit 表层。

`innercc` 则连这 `8` 条也没拿下，证明环境噪声修复与 benchmark 几乎无关。

## 9. Root Cause

- `direct_root_cause`
  - 两边都没有做 bundle case 的任务规模判断。
  - `innercc` 被环境兼容噪声带偏。
  - `claude-code` 被 release note 中单一显眼 feature 带偏。
- `contributing_factors`
  - `133` 条 F2P 没有被按模块聚类。
  - 没有用官方 patch 的文件分布反推“这不可能是单文件/单功能修复”。
- `non_root_but_misleading_signals`
  - `fsspec_loop` 兼容报错和 `machine rename/status` 都是真实问题，但都不是 benchmark 主体。

## 10. CLI Optimization Opportunities

1. 对 `FAIL_TO_PASS > 50` 的 case 强制进入 bundle mode，先做模块聚类，再决定优先级。验证方式是 trace 中必须出现按文件夹或模块名的 failing test 分簇。
2. 把“环境兼容噪声”从“benchmark target”里剥离。只因为当前环境有 import/runtime 报错，不代表它是官方 bundle 要求的主体。验证方式是要求 patch 前先对照官方 patch 文件分布。
3. 对大 bundle，不允许因为过了一个 unit 子簇就提前结束。这里 `claude-code` 的 `8/133` 正是典型的假进展。
