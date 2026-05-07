# iterative__dvc_3.43.1_3.44.0 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_3.43.1_3.44.0`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_but_claude_closer`
- 一句话结论：
  这是一个中大型 feature bundle，官方主轴是“status/ls/get/data-cloud 在 import 场景下新增 skip-imports 与 check_updates 控制，并修复 DVC FS/ls/file-vs-dir 行为”。`claude-code` 只抓住了 `--skip-imports` 这一显眼 feature，虽然 `0/22 F2P`，但保持了 `104/104 P2P`；`innercc` 则被当前环境里的 pathspec `_DIR_MARK` 兼容噪声带偏，只改了 `dvc/ignore.py` 一行，结果同样 `0/22 F2P`，还把 `P2P` 打到 `3/104`。
- 根因标签：
  - `task_understanding_error`
  - `hypothesis_lock_in`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
## What's Changed
### 🚀 New Features and Enhancements
* status: add option to skip imports by @dberenbaum in https://github.com/iterative/dvc/pull/10277
...
```

`FAIL_TO_PASS`: `22` 条，主要分布在：

- `tests/func/test_data_cloud.py::*pull_git_imports*/*external_dvc_imports*/*push_pull_all*`
- `tests/func/test_get.py::*`
- `tests/func/test_ls.py::*`
- `tests/func/test_status.py::*`
- `tests/unit/command/test_status.py::*`
- `tests/unit/repo/test_repo.py::test_branch_config`

`PASS_TO_PASS`: `104` 条。

这说明 benchmark 主体不只是 command 层 `--skip-imports`：

- 还有 `status(check_updates=...)`
- DVC FS / repo ls 在 file/dir/broken-dir/import 场景下的行为
- data cloud/get/ls/status 跨模块 import 处理

### 2.2 runner-level user query

prompt 给的是一个 feature-looking release note，但 F2P 分布已经把真实任务放大到了 `status + ls + dvcfs + imports` 的组合修复。

### 2.3 trace-level agent goals

- `innercc`
  - 很快被 pathspec `_DIR_MARK` import 兼容问题带偏
  - 目标被重写成“修 pathspec 新版本导致的 ImportError”
- `claude-code`
  - 很快把任务压成 `dvc status --skip-imports`
  - 这是 release note 最显眼的一条，但不是 benchmark 全部

### 2.4 official golden answer

官方 patch 的真正主簇包括：

- `dvc/commands/status.py`
  - 新增 `check_updates=self.args.check_updates`
- `dvc/repo/status.py`
  - `_joint_status(..., check_updates=True)`
  - `_local_status(..., check_updates=True)`
- `dvc/fs/dvc.py`
  - `ls()` / `info()` 在 file vs dir / broken dir / dvc-only 场景下的修复
- `dvc/repo/ls.py`
  - file path handling
- `dvc/api/show.py`
  - `processed[rev] = processed[rev] | to_merge`
- `tests` 也覆盖了大量 get/ls/status/data_cloud import 相关行为

换句话说，官方 patch 绝不是只加一个 `--skip-imports` flag，也不是修 pathspec import。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `0/22` | `3/104` | `514871` | `99` | `98` | `1` |
| `claude-code` | `false` | `0/22` | `104/104` | `742986` | `76` | `75` | `7` |

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.43.1_3.44.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.43.1_3.44.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.43.1_3.44.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.43.1_3.44.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.43.1_3.44.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.43.1_3.44.0/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_3.43.1_3.44.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.43.1_3.44.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.43.1_3.44.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.43.1_3.44.0/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.43.1_3.44.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.43.1_3.44.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.43.1_3.44.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.43.1_3.44.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.43.1_3.44.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.43.1_3.44.0/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_3.43.1_3.44.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.43.1_3.44.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.43.1_3.44.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.43.1_3.44.0/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: noise-first exploration (`step 1-20`)

- 关键动作：
  - 看最近 commit `84b2e68`
  - 先跑 `test_pull_external_dvc_imports` 与 `test_branch_config`
  - 迅速被 pathspec / scmrepo / pygit2 / import 噪声包围
- 阶段结论：
  - 任务从一开始就没有按 F2P 模块分布收敛

#### Phase B: pathspec lock-in (`step 20-89`)

- 核心假设：
  - 根因是 `pathspec.patterns.gitwildmatch._DIR_MARK` 在新版本位置变化
- 修改文件：
  - `dvc/ignore.py`
- 问题：
  - 这只覆盖到 pathspec 噪声
  - 与 `22` 条 F2P 的真实主轴严重错位

### 5.2 claude-code

#### Phase A: feature-centric scoping (`step 2-20`)

- 关键动作：
  - 读 `tests/func/test_status.py`
  - 读 `dvc/repo/status.py`
  - 读 command status 路径
- 阶段结论：
  - 把任务压成“给 `dvc status` 增加 `--skip-imports`”

#### Phase B: status-only implementation (`step 20-76`)

- 修改文件：
  - `dvc/commands/data_sync.py`
  - `dvc/commands/status.py`
  - `dvc/repo/status.py`
- 结果：
  - patch 只覆盖了 release note 最显眼的一条 feature
  - 完全没触及 DVC FS / repo ls / api show / status check_updates 等主簇

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `1-89` | 根因是 pathspec 新版本 `_DIR_MARK` import 位置变化 | ImportError 噪声、`dvc/ignore.py` | 当前环境确实触发了这类错误 | 错，只是外围噪声，不解释 `22` 条 F2P 主体 |
| `claude-code` | `2-76` | 题目主轴就是 `--skip-imports` | release note、status tests | 这条 feature 很显眼且真实存在 | 只命中了 release-note 表层，没命中 benchmark 主体 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- patch：
  - 只改 `dvc/ignore.py` 一行 import
- 结果：
  - `0/22 F2P`
  - `3/104 P2P`
- 评价：
  - 典型的环境噪声驱动 patch

### 7.2 claude-code

- patch：
  - 只改 `status` command/repo 的 `skip_imports`
- 结果：
  - `0/22 F2P`
  - `104/104 P2P`
- 评价：
  - 虽然 feature 自身合理，但和 benchmark 的实际 F2P 覆盖面不一致

## 8. Evaluation And Failure Evidence

来自 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.43.1_3.44.0/report.json)：

- `22/22` F2P 全部失败
- 但 `PASS_TO_PASS = 104/104`

这说明 `claude-code` 不是“修坏了”，而是“完全修偏了”。

来自 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.43.1_3.44.0/report.json)：

- `0/22` F2P
- `3/104` P2P

这说明 `innercc` 不仅修偏，还引入了大规模回归。

## 9. Root Cause

- `direct_root_cause`
  - 两边都没有按 benchmark 的 `22` 条 F2P 分布来决定任务边界。
  - `innercc` 锁在 pathspec 噪声。
  - `claude-code` 锁在 `skip-imports` 单条 feature。
- `contributing_factors`
  - 这是“release note 显眼 feature”误导 case：release note 确实提 `skip-imports`，但 F2P 已经扩大到 data_cloud/get/ls/status/repo/dvcfs 组合修复。
  - `innercc` 又叠加了环境级 ImportError 噪声。
- `non_root_but_misleading_signals`
  - pathspec `_DIR_MARK` 和 `--skip-imports` 都是真实问题，但都不足以解释 `22` 条 F2P。

## 10. CLI Optimization Opportunities

1. 当 release note 只有一条显眼 feature、但 F2P 横跨多个功能目录时，必须优先信 F2P 而不是信 release note 文案。验证方式是要求 trace 中给出 “release note feature count vs failing module count” 的对比。
2. 对环境噪声（pathspec/scmrepo/pygit2/import 兼容）建立降权规则。它们可以作为解释 P2P / setup 噪声的线索，但不能自动升格成主修复目标。验证方式是若 patch 只命中噪声模块，必须给出它如何覆盖多数 F2P 的证据，否则禁止结束。
3. 对中大型 bundle，不允许以“单 feature 实现完成”作为结束条件。这里 `claude-code` 的 status-only patch 就是典型反例。
