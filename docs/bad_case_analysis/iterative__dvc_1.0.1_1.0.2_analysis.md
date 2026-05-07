# iterative__dvc_1.0.1_1.0.2 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_1.0.1_1.0.2`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `inner_closer_but_both_failed`
- 一句话结论：
  这题只有两条 F2P，但它们分属两个不同层次：`git-hook` 需要让 `CmdPrePush` 走 `CmdHookBase.run()` 的“非 DVC 仓库直接返回 0”路径，`run --file` 则要求在 repo 层给出特定的 multistage 拒绝语义。`innercc` 只修成了前者；`claude-code` 虽然也碰了两个点，但在 `git-hook` 上修错控制流，在 `repo.run()` 上给出了错误的报错文案，因此 `0/2`。
- 根因标签：
  - `localization_error`
  - `validation_gap`
  - `hypothesis_lock_in`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
* Enable pylint checks (#4092) @skshetry
* rpm/deb/osxpkg: add url and license (#4098) @efiop
* ui: remove: .gitignore in cmd description (#4097) @nik123
* git-hook: don't run when not in dvc repo (#4091) @efiop
* push/pull/fetch: unhide --run-cache (#4087) @efiop
* tests: use pytest-lazyfixture (#4089) @skshetry
* run: hide and forbid --file for multistage files (#4086) @efiop
```

`FAIL_TO_PASS`:

- `tests/unit/command/test_git_hook.py::test_out_of_repo[pre-push-CmdPrePush]`
- `tests/unit/repo/test_run.py::test_file`

`PASS_TO_PASS`: `19` 条。

这个 case 虽然 F2P 只有 `2` 条，但它不是单点修复：

1. `git-hook` 线验证的是：
   - 在非 DVC 仓库下执行 `dvc git-hook pre-push`
   - 应当短路返回 `0`
   - 不能实际进入 `dvc.main.main(["push"])`
2. `run --file` 线验证的是：
   - multistage pipeline 下 `fname + name` 的组合
   - 必须在 repo 层抛出特定 `InvalidArgumentError`
   - 报错文本也必须与测试契约一致

### 2.2 runner-level user query

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_1.0.1_1.0.2

Release note / requirement:
* Enable pylint checks (#4092) @skshetry
* rpm/deb/osxpkg: add url and license (#4098) @efiop
* ui: remove: .gitignore in cmd description (#4097) @nik123
* git-hook: don't run when not in dvc repo (#4091) @efiop
* push/pull/fetch: unhide --run-cache (#4087) @efiop
* tests: use pytest-lazyfixture (#4089) @skshetry
* run: hide and forbid --file for multistage files (#4086) @efiop

Expected failing tests that should pass after your fix:
- tests/unit/command/test_git_hook.py::test_out_of_repo[pre-push-CmdPrePush]
- tests/unit/repo/test_run.py::test_file

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

### 2.3 trace-level agent goals

- `innercc`
  - 早期就把任务拆成：
    - `CmdPrePush` 的 out-of-repo 行为
    - `--file` 在 multistage 下的禁用
  - 但后续把第二条线理解成“command 层应该拦掉 `--file`”
- `claude-code`
  - 也同时看了两条测试
  - 但在 `git-hook` 线上把问题理解成 `Repo.close()` 的异常处理
  - 在 `run` 线上虽然触及了 `repo/run.py`，却没有对齐测试要求的确切错误消息

### 2.4 official golden answer

官方 `patch` 的两个核心 hunk 很明确。

#### Golden fix A: `CmdPrePush` 应复用 `CmdHookBase.run()` 的仓库检测逻辑

```diff
diff --git a/dvc/command/git_hook.py b/dvc/command/git_hook.py
@@
-class CmdPostCheckout(CmdHookBase):
-    def run(self):
+class CmdPostCheckout(CmdHookBase):
+    def _run(self):
@@
-class CmdPrePush(CmdHookBase):
-    def run(self):
+class CmdPrePush(CmdHookBase):
+    def _run(self):
```

关键点不是“实现 `_run()` 本身”，而是：

- 让 `CmdPrePush` 不再绕过 `CmdHookBase.run()`
- 这样 `Repo()` 若在非 DVC 仓库下抛 `NotDvcRepoError`，就会统一返回 `0`

#### Golden fix B: multistage 下在 repo 层禁止 `fname`

```diff
diff --git a/dvc/repo/run.py b/dvc/repo/run.py
@@
+    if stage_name and fname:
+        raise InvalidArgumentError(
+            "`--file` is currently incompatible with `-n|--name` "
+            "and requires `--single-stage`"
+        )
```

关键点同样不是“隐藏 help”而是：

- `repo.run()` 的语义约束本身要成立
- 并且异常消息必须精确匹配测试

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `1/2` | `19/19` | `225826` | `48` | `47` | `4` |
| `claude-code` | `false` | `0/2` | `19/19` | `1791963` | `111` | `110` | `20` |

特点很鲜明：

- 两边都没有引入新的 P2P 回归
- `innercc` 至少修成了 `pre-push`
- `claude-code` 两条都没修成，而且花了更多 turns

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.1_1.0.2/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.1_1.0.2/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.1_1.0.2/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.1_1.0.2/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.1_1.0.2/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.1_1.0.2/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_1.0.1_1.0.2.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.0.1_1.0.2/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.0.1_1.0.2/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.0.1_1.0.2/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.1_1.0.2/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.1_1.0.2/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.1_1.0.2/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.1_1.0.2/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.1_1.0.2/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.1_1.0.2/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_1.0.1_1.0.2.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.0.1_1.0.2/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.0.1_1.0.2/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.0.1_1.0.2/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: focused dual-test exploration (`step 1-13`)

- 关键动作：
  - 直接跑两条 failing tests
  - 读 `tests/unit/command/test_git_hook.py`
  - 读 `tests/unit/repo/test_run.py`
  - 读 `dvc/command/git_hook.py`、`dvc/command/run.py`、`dvc/repo/run.py`
- 阶段结论：
  - 它很快识别出这是两个独立目标点

#### Phase B: hypothesis formation (`step 14-16`)

- 关键文本：
  - 明确把任务表述成 “fix git-hook + forbid `--file` for multistage”
- 问题：
  - 第二条线被收缩成 command 层输入校验，而不是 repo 层语义约束

#### Phase C: code editing (`step 15-18`)

- 修改文件：
  - `dvc/command/git_hook.py`
  - `dvc/command/run.py`
- 修改内容：
  - `CmdPrePush.run -> _run`
  - 在 `CmdRun.run()` 里提前报错 `--file` 只能和 `--single-stage` 搭配
  - 把 parser 中 `--file` 的 help 隐藏

#### Phase D: validation (`step 28-35`)

- 关键动作：
  - Python snippets 检查 `CmdPrePush` 继承结构
  - 读回修改文件
  - `git diff`
- 阶段结论：
  - 它确认了 `pre-push` 线
  - 但没有回到 `repo.run()` 的单元测试契约，所以漏掉了真正需要命中的层级和文案

### 5.2 claude-code

#### Phase A: long exploration with weak narrowing (`step 2-18`)

- 关键动作：
  - 跑两条 tests
  - 大量 `Glob` / `Grep` / `Read`
  - 反复看 command 与 repo 文件
- 阶段结论：
  - 虽然读得更多，但没有更快锁定真正的修复层

#### Phase B: wrong git-hook fix (`step 20-40`)

- 修改文件：
  - `dvc/command/git_hook.py`
- 核心假设：
  - 问题来自 `Repo.close()` 可能抛 `NoRemoteError`
- 为什么错：
  - `test_out_of_repo[pre-push]` 真正要求的是不要进入 `_run()`；官方 fix 是让 `CmdPrePush` 走 `CmdHookBase.run()` 的 `NotDvcRepoError` 短路路径

#### Phase C: partial repo.run fix (`step 40-60`)

- 修改文件：
  - `dvc/command/run.py`
  - `dvc/repo/run.py`
- 命中程度：
  - 至少触及了正确的 repo 层
- 问题：
  - 报错文案写成：
    - ``--file` is not supported for multistage pipelines, please use `--single-stage``
  - 与测试要求的：
    - ``--file` is currently incompatible with `-n|--name` and requires `--single-stage``
    不一致

#### Phase D: prolonged validation drift (`step 61-108`)

- 关键动作：
  - 大量 snippets 与 `grep`
  - `git diff`
- 阶段结论：
  - 工作量很大，但闭环没有真正围绕两条 exact tests 的断言文本收口

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `1-13` | 这是 `git-hook` 与 `--file` 的双点修复 | 两条 failing tests、对应源码文件 | 测试分布很清楚 | 正确 |
| `innercc` | `14-18` | `--file` 问题只需要在 command 层禁止即可 | `dvc/command/run.py` 与 CLI 语义 | 从用户角度看，命令层拦截似乎够了 | 错误，测试直接调用 `repo.run()`，需要 repo 层异常 |
| `claude-code` | `20-40` | `pre-push` 失败来自 `Repo.close()` 异常处理不足 | `CmdHookBase` / `Repo.close()` 阅读 | 看起来像 out-of-repo 清理逻辑问题 | 错误，真正问题是 `CmdPrePush` 绕过了基类 `run()` |
| `claude-code` | `40-60` | 只要在 repo 层禁止 multistage `fname` 就够了 | `tests/unit/repo/test_run.py`、`repo/run.py` | 命中正确层，比 innercc 更接近 | 部分正确，但报错消息不匹配，仍然失败 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- `dvc/command/git_hook.py`
  - 与 official patch 主轴一致
  - 成功修成 `pre-push`
- `dvc/command/run.py`
  - 只在 command 层做了日志错误返回
  - 还隐藏了 `--file` help
- 与 official patch 的差异：
  - 漏了 `dvc/repo/run.py` 的真正语义约束
- 结果：
  - `tests/unit/repo/test_run.py::test_file` 不会经过 command 层，必然继续失败

### 7.2 claude-code

- `dvc/command/git_hook.py`
  - 修改了 `CmdHookBase.run()` 的异常处理
  - 但没有采用官方 `CmdPrePush.run -> _run` 的控制流修复
- `dvc/repo/run.py`
  - 命中了正确层
  - 但错误消息不匹配测试正则
- 结果：
  - `pre-push` 没过
  - `test_file` 也因 message mismatch 没过

## 8. Evaluation And Failure Evidence

### 8.1 innercc

来自 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.0.1_1.0.2/report.json)：

- `test_out_of_repo[pre-push-CmdPrePush]` 成功
- `test_file` 失败

这与 patch 完全一致：只修了 `git_hook.py`，没修 `repo/run.py`。

### 8.2 claude-code

来自 [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.0.1_1.0.2/test_output.txt) 的两个决定性失败证据：

`pre-push` 仍然进入了 `dvc.main.main()`：

```text
E       AssertionError: assert <MagicMock name='main()' ...> == 0
```

`repo.run()` 虽然抛了异常，但消息不匹配：

```text
E           AssertionError: Regex pattern did not match.
E            Regex: '`--file` is currently incompatible with `-n|--name` and requires `--single-stage`'
E            Input: '`--file` is not supported for multistage pipelines, please use `--single-stage`'
```

## 9. Root Cause

- `direct_root_cause`
  - 两边都存在定位层级错误。
  - `innercc` 把 repo-level 契约修成了 command-level 交互限制。
  - `claude-code` 把 `git-hook` 的控制流 bug 修成了异常清理 bug，并且在正确层级上给出了错误消息。
- `contributing_factors`
  - 两边都没有用 exact failing assertion 作为最终收口标准。
  - `claude-code` 的探索过长，但没有提高命中率。
- `non_root_but_misleading_signals`
  - test output 里有大量与环境兼容相关的 `ImportError: cannot import name 'gcd' from 'fractions'` 噪声。
  - 但 official report 已经把这题收敛到两条 F2P，真正根因仍是 patch 未对齐测试契约。

## 10. CLI Optimization Opportunities

1. 如果 failing test 直接调用 repo API，就不能只在 command 层修。这个规则适用于 parser/command/repo 三层经常错位的 CLI 项目。验证方式是检查 failing test import 的对象层级，若是 `Repo` 或内部函数，就要求 patch 也至少命中同层或更深层。
2. 对异常型测试，错误消息应作为一等验证对象，而不是附属文本。`claude-code` 在正确层抛错仍失败，就是因为 message mismatch。验证方式是把 `pytest.raises(..., match=...)` 中的 regex 提取进验证 checklist。
3. 对继承式 command bug，优先检查是否绕过了基类控制流。`CmdPrePush.run` 与 `_run` 的差别就是这一类典型模式。验证方式是当测试名涉及 `CmdXxx` / inheritance hook 时，自动检查子类是否覆盖了关键模板方法。
