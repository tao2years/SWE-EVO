# iterative__dvc_1.6.3_1.6.4 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_1.6.3_1.6.4`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_partial_same_cluster`
- 一句话结论：
  两个 CLI 都意识到这题和 `dvc plots --experiment` 有关，也都修通了 command 层的 `test_plots_diff`，但都把真正的 repo-level 语义修成了错误的 `_revisions()` / experiment revision 推导逻辑：`innercc` 把官方的 `repo + baseline` 协议改成了基于 branch/stash 的复杂派生，`claude-code` 则只补了 command 层和一个不对等的 stash fallback，结果双方都停在 `1/9 F2P`。
- 根因标签：
  - `localization_error`
  - `hypothesis_lock_in`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
> Refer to https://dvc.org/doc/install for installation instructions.

## Changes

## 🚀 New Features and Enhancements 

- plots: add `dvc plots -e/--experiment` option (#4488) @pmrowla

## 🏇 Optimizations 

- external: avoid unnecessary hash computation (#4486) @efiop
```

`FAIL_TO_PASS`:

- `tests/unit/command/test_plots.py::test_plots_diff`
- `tests/unit/repo/plots/test_diff.py::test_revisions[arg_revisions0-False-expected_revisions0]`
- `tests/unit/repo/plots/test_diff.py::test_revisions[arg_revisions1-True-expected_revisions1]`
- `tests/unit/repo/plots/test_diff.py::test_revisions[arg_revisions2-False-expected_revisions2]`
- `tests/unit/repo/plots/test_diff.py::test_revisions[arg_revisions3-True-expected_revisions3]`
- `tests/unit/repo/plots/test_diff.py::test_revisions_experiment[arg_revisions0-v0-expected_revisions0]`
- `tests/unit/repo/plots/test_diff.py::test_revisions_experiment[arg_revisions1-None-expected_revisions1]`
- `tests/unit/repo/plots/test_diff.py::test_revisions_experiment[arg_revisions2-v0-expected_revisions2]`
- `tests/unit/repo/plots/test_diff.py::test_revisions_experiment[arg_revisions3-None-expected_revisions3]`

`PASS_TO_PASS`: `2` 条。

这个 case 的关键是：

- `test_plots_diff` 只验证 command 层是否把 `--experiment` 传下去
- 剩下 `8` 条真正决定 resolve 的测试都在 `dvc.repo.plots.diff._revisions()`
- 所以它不是 parser-only case，而是 “parser + repo semantics” 双层 case

### 2.2 runner-level user query

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_1.6.3_1.6.4

Release note / requirement:
> Refer to https://dvc.org/doc/install for installation instructions.

## Changes

## 🚀 New Features and Enhancements 

- plots: add `dvc plots -e/--experiment` option (#4488) @pmrowla

## 🏇 Optimizations 

- external: avoid unnecessary hash computation (#4486) @efiop

Expected failing tests that should pass after your fix:
- tests/unit/command/test_plots.py::test_plots_diff
- tests/unit/repo/plots/test_diff.py::test_revisions[arg_revisions0-False-expected_revisions0]
- tests/unit/repo/plots/test_diff.py::test_revisions[arg_revisions1-True-expected_revisions1]
- tests/unit/repo/plots/test_diff.py::test_revisions[arg_revisions2-False-expected_revisions2]
- tests/unit/repo/plots/test_diff.py::test_revisions[arg_revisions3-True-expected_revisions3]
- tests/unit/repo/plots/test_diff.py::test_revisions_experiment[arg_revisions0-v0-expected_revisions0]
- tests/unit/repo/plots/test_diff.py::test_revisions_experiment[arg_revisions1-None-expected_revisions1]
- tests/unit/repo/plots/test_diff.py::test_revisions_experiment[arg_revisions2-v0-expected_revisions2]
- tests/unit/repo/plots/test_diff.py::test_revisions_experiment[arg_revisions3-None-expected_revisions3]

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

### 2.3 trace-level agent goals

- `innercc`
  - 很快知道有 `--experiment`
  - 但后续把核心问题写成“如何从 baseline 找到 experiment revisions”，并引入了自己的 branch/stash 方案
- `claude-code`
  - 同样抓住了 `--experiment`
  - 但也把 repo 语义简化成 “experiment mode 下用 stash revisions 或原样保留 revs”

两边都没有围绕 `test_revisions()` 的函数签名和返回值协议做闭环。

### 2.4 official golden answer

官方 patch 的核心有两部分。

#### Golden fix A: command 层把 `--experiment` 传给 `repo.plots.diff()`

```diff
diff --git a/dvc/command/plots.py b/dvc/command/plots.py
@@
-        return self.repo.plots.diff(*args, revs=self.args.revisions, **kwargs)
+        return self.repo.plots.diff(
+            *args,
+            revs=self.args.revisions,
+            experiment=self.args.experiment,
+            **kwargs,
+        )
@@
+    plots_diff_parser.add_argument(
+        "-e",
+        "--experiment",
+        action="store_true",
+        default=False,
+        help=argparse.SUPPRESS,
+    )
```

#### Golden fix B: repo 层 `_revisions()` 的新协议

```diff
diff --git a/dvc/repo/plots/diff.py b/dvc/repo/plots/diff.py
@@
-def _revisions(revs, is_dirty):
+def _revisions(repo, revs, experiment):
+    revisions = revs or []
+    if experiment and len(revisions) == 1:
+        baseline = repo.experiments.get_baseline(revisions[0])
+        if baseline:
+            revisions.append(baseline[:7])
+    if len(revisions) <= 1:
+        if len(revisions) == 0 and repo.scm.is_dirty():
+            revisions.append("HEAD")
+        revisions.append("workspace")
+    return revisions
@@
-def diff(repo, *args, revs=None, **kwargs):
+def diff(repo, *args, revs=None, experiment=False, **kwargs):
+    if experiment:
+        kwargs["templates"] = repo.plot_templates
+        plots_repo = repo.experiments.exp_dvc
+    else:
+        plots_repo = repo
+    return plots_repo.plots.show(
+        *args, revs=_revisions(repo, revs, experiment), **kwargs
+    )
```

真正关键点是：

- `_revisions()` 的第一个参数变成 `repo`
- `experiment=True` 时只在单 revision 情况下补 baseline
- 不是去扫描 stash branches，也不是直接返回 experiment rev 列表

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `1/9` | `2/2` | `370938` | `66` | `65` | `0` |
| `claude-code` | `false` | `1/9` | `2/2` | `810690` | `89` | `88` | `13` |

两边都只过了：

- `tests/unit/command/test_plots.py::test_plots_diff`

剩余 `8` 条 repo-level `_revisions()` 相关测试全部没过。

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.6.3_1.6.4/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.6.3_1.6.4/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.6.3_1.6.4/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.6.3_1.6.4/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.6.3_1.6.4/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.6.3_1.6.4/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_1.6.3_1.6.4.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.6.3_1.6.4/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.6.3_1.6.4/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.6.3_1.6.4/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.6.3_1.6.4/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.6.3_1.6.4/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.6.3_1.6.4/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.6.3_1.6.4/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.6.3_1.6.4/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.6.3_1.6.4/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_1.6.3_1.6.4.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.6.3_1.6.4/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.6.3_1.6.4/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.6.3_1.6.4/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: task scoping (`step 1-16`)

- 关键动作：
  - 读 command test 与 repo test
  - 读 `dvc/command/plots.py`
  - 读 `dvc/repo/plots/diff.py`
  - 查 git log / commit `be2e077`
- 阶段结论：
  - 它知道既有 command 层 `--experiment`，也有 repo 层 revision 语义

#### Phase B: wrong repo-level model (`step 16-30`)

- 核心假设：
  - experiment plots diff 需要从 experiment branches / stash 里解析 revisions
- 为什么看起来合理：
  - release note 确实提 experiment
  - DVC 实验分支有 stash / baseline 等概念
- 为什么错：
  - 当前测试并不要求“列举 experiment revisions”
  - 只要求 `_revisions(repo, revs, experiment)` 按 baseline / workspace 规则扩展

#### Phase C: editing (`step 31-55`)

- 修改文件：
  - `dvc/command/plots.py`
  - `dvc/repo/plots/diff.py`
- 结果：
  - `test_plots_diff` 通过
  - `_revisions()` 签名与语义仍然错误

### 5.2 claude-code

#### Phase A: extended path exploration (`step 2-20`)

- 关键动作：
  - 大量 `Glob` / `Read` / `Grep`
  - 反复确认 workspace path
- 阶段结论：
  - 早期有较多路径与环境噪声，没有更快推进到 repo tests 主轴

#### Phase B: same command-level success, same repo-level miss (`step 20-60`)

- 修改文件：
  - `dvc/command/plots.py`
  - `dvc/repo/plots/diff.py`
- 核心假设：
  - experiment mode 下没有显式 revs 时，用 stash experiment revisions
- 问题：
  - 这不是当前 `_revisions()` 测试要求的行为

#### Phase C: validation drift (`step 83-90`)

- 关键动作：
  - 跑 `tests/unit/repo/plots/test_diff.py`
  - 继续围绕自己的 `_get_experiment_revisions()` 方案做 snippets
- 阶段结论：
  - 虽然 exact repo tests 已经给出反证，但没有重置定位

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `1-16` | 题目包含 command 层与 repo 层两部分 | unit command + unit repo tests | F2P 分布非常明确 | 正确 |
| `innercc` | `16-30` | repo 层需要“根据 experiment branches 推导 revisions” | commit history、experiment 关键词 | 贴近产品概念 | 错误，测试只要求 baseline / workspace 扩展 |
| `claude-code` | `20-60` | experiment 模式下用 stash revisions 作为 plots diff 输入 | experiments stash 概念、plots diff 行为 | 看起来像较自然的实验列表来源 | 错误，没命中 `_revisions()` 的协议 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- 命中：
  - command 层参数传递
- 漏掉：
  - official `_revisions(repo, revs, experiment)` 签名
  - `repo.experiments.get_baseline()` 这一简单协议
- 额外复杂度：
  - 引入 `_get_experiment_revisions()` 分支扫描

### 7.2 claude-code

- 命中：
  - command 层参数传递
- 漏掉：
  - `_revisions()` 的 repo 参数与 baseline 语义
- 额外复杂度：
  - 引入 stash-based experiment fallback，与官方实现完全不同

## 8. Evaluation And Failure Evidence

来自 [innercc test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.6.3_1.6.4/test_output.txt) 的决定性证据：

```text
E       TypeError: object of type 'Mock' has no len()
```

这说明 `_revisions()` 的函数签名还保持着旧的 `(revs, is_dirty, ...)` 习惯，而测试已经按 `(_repo, arg_revisions, False)` 调它。

同时 experiment 相关测试也直接显示：

```text
E       AssertionError: assert <Mock ...> == ['v1', 'v0']
```

说明函数把 `mock_repo` 当成返回值一路透传了，完全没进入官方的 baseline 逻辑。

`claude-code` 的 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.6.3_1.6.4/report.json) 与此一致：只过了 command test，repo tests 全挂。

## 9. Root Cause

- `direct_root_cause`
  - 两边都把 repo-level 修复理解错了层级与协议。
- `contributing_factors`
  - `--experiment` 这个词强烈诱导 agent 去思考 experiments branches/stash，而不是回到 `_revisions()` 的具体测试输入输出。
  - 验证虽覆盖到 repo tests，但没有触发重定位。
- `non_root_but_misleading_signals`
  - command test 先通过，会让 patch 看起来“主功能已打通”。
  - 但真正决定 resolve 的是那 8 条 repo tests。

## 10. CLI Optimization Opportunities

1. 当 command tests 和 repo helper tests 同时存在时，应优先以 repo helper 的函数签名与 I/O 协议为最终收口。适用于 parser 已通、底层 helper 仍错的 case。验证方式是要求 trace 在 command test 通过后继续对 helper tests 做单独对照。
2. 遇到 `experiment`、`branch`、`stash` 这类高语义词时，不要过早扩展到复杂系统模型；先看测试是否只要求一个小型协议扩展。验证方式是把 failing tests 的参数表和 expected values提取成最小 truth table，再对照 patch。
