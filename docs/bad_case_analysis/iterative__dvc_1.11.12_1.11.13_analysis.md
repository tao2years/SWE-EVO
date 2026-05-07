# iterative__dvc_1.11.12_1.11.13 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_1.11.12_1.11.13`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_resolved_reference_success`
- 一句话结论：
  这是一个双方都成功的窄任务正例；`innercc` 在 `protect()` 外层最小化吞掉 `EPERM/EACCES`，`claude-code` 把“忽略 protect 错误”抽象成 `chmod(ignore_errors=True)`，两者都命中了 benchmark 真实目标。
- 根因标签：
  - `reference_success_path`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
- dvc: ignore errors on protect/set_exec (#5335) @efiop
```

`FAIL_TO_PASS`:

- `tests/unit/remote/test_local.py::test_protect_ignore_errors[13]`
- `tests/unit/remote/test_local.py::test_protect_ignore_errors[1]`

`PASS_TO_PASS`: `4` 条。

这个 case 的 benchmark 目标非常窄：

- 失败测试都落在 `LocalTree.protect()` 的权限错误处理。
- 两条 F2P 分别覆盖 `errno.EACCES` 与 `errno.EPERM`。
- 虽然 release note 文本写的是 `protect/set_exec`，但 benchmark 本轮只要求修好 `protect()` 分支。

### 2.2 runner-level user query

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_1.11.12_1.11.13

Release note / requirement:
- dvc: ignore errors on protect/set_exec (#5335) @efiop

Expected failing tests that should pass after your fix:
- tests/unit/remote/test_local.py::test_protect_ignore_errors[13]
- tests/unit/remote/test_local.py::test_protect_ignore_errors[1]

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

### 2.3 trace-level agent goals

- `innercc`
  - 在 `step 6` 就把任务重写成：
    - `protect()` 最终调用 `chmod()`
    - `EPERM/EACCES` 应在共享 cache 场景下被忽略
    - 先修 `protect()`，再检查 `set_exec` 是否也需要同步
- `claude-code`
  - 在 `step 7-18` 形成的内部目标更偏抽象层：
    - 问题不只在 `protect()`，而在 `LocalTree.chmod()` 调用者是否需要“忽略错误”语义
    - 先给 `chmod()` 增加 `ignore_errors` 能力，再让 `protect()` 透传

### 2.4 official golden answer

官方 `patch` 的核心 hunk 非常集中：

```diff
diff --git a/dvc/tree/local.py b/dvc/tree/local.py
@@
-        except OSError as exc:
-            # There is nothing we need to do in case of a read-only file system
-            if exc.errno == errno.EROFS:
-                return
-
-            # In shared cache scenario, we might not own the cache file, so we
-            # need to check if cache file is already protected.
-            if exc.errno not in [errno.EPERM, errno.EACCES]:
-                raise
-
-            actual = stat.S_IMODE(os.stat(path).st_mode)
-            if actual != mode:
-                raise
+        except OSError:
+            # NOTE: not being able to protect cache file is not fatal, it
+            # might happen on funky filesystems (e.g. Samba, see #5255),
+            # read-only filesystems or in a shared cache scenario.
+            logger.trace("failed to protect '%s'", path_info, exc_info=True)
```

golden patch 的含义是：

- `protect()` 最终经由 `chmod()` 触发的权限错误不再是致命错误。
- 官方实现把逻辑放在 `chmod()` 里，统一覆盖：
  - `EPERM`
  - `EACCES`
  - `EROFS`
  - 以及其它“不能保护 cache 文件但不影响语义正确性”的异常场景

官方 `test_patch` 的关键 hunk 是：

```diff
diff --git a/tests/unit/remote/test_local.py b/tests/unit/remote/test_local.py
@@
-@pytest.mark.parametrize("err", [errno.EPERM, errno.EACCES])
+@pytest.mark.parametrize("err", [errno.EPERM, errno.EACCES, errno.EROFS])
 def test_protect_ignore_errors(tmp_dir, dvc, mocker, err):
```

因此 benchmark 真正验证的是：

1. `protect()` 在共享 cache / 权限受限场景下不应因 `chmod` 失败而中断。
2. release bundle 虽然提到 `set_exec`，但本轮 F2P 只锚定 `protect()`。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count | patch_apply | anomaly_flags |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `innercc` | `true` | `2/2` | `4/4` | `141579` | `28` | `22` | `1` | `true` | `narrow_fix_but_matches_f2p` |
| `claude-code` | `true` | `2/2` | `4/4` | `742645` | `25` | `24` | `4` | `true` | `slightly_more_general_than_f2p` |

对比要点：

- 两边都 resolved，且 `patch_successfully_applied = true`。
- `innercc` 的改动更小，只在 `protect()` 外层兜底。
- `claude-code` 更接近“把错误处理下沉到 helper 层”的设计，但仍没有完全复刻 official patch 的 `trace` 日志与 catch-all 形态。

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.11.12_1.11.13/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.11.12_1.11.13/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.11.12_1.11.13/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.11.12_1.11.13/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.11.12_1.11.13/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.11.12_1.11.13/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_1.11.12_1.11.13.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.11.12_1.11.13/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.11.12_1.11.13/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.11.12_1.11.13/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.11.12_1.11.13/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.11.12_1.11.13/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.11.12_1.11.13/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.11.12_1.11.13/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.11.12_1.11.13/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.11.12_1.11.13/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_1.11.12_1.11.13.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.11.12_1.11.13/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.11.12_1.11.13/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.11.12_1.11.13/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### `bootstrap`

- `step_range`: `step 1-3`
- 关键工具：`Bash`、`Read`
- 关键文件：`tests/unit/remote/test_local.py`、`dvc/tree/local.py`
- 关键命令：
  - `grep -n "test_protect_ignore_errors" tests/unit/remote/test_local.py`
  - `find . -name "local.py" | grep tree`
- 当前阶段目标：
  - 找到 failing test 与被测实现的最短调用链
- 阶段产出：
  - 快速确认 `test_protect_ignore_errors` 直指 `LocalTree.protect()`

#### `repo_exploration`

- `step_range`: `step 4-5`
- 关键工具：`Read`
- 关键文件：`dvc/tree/local.py`
- 关键命令：无
- 当前阶段目标：
  - 读懂 `protect()` 与 `chmod()` 的现有关系
- 阶段产出：
  - 确认 `protect()` 只是把 `CACHE_MODE` 传给 `chmod()`
  - 现有 `chmod()` 已单独处理 `EROFS`，但对 `EPERM/EACCES` 仍可能抛错

#### `task_planning`

- `step_range`: `step 6`
- 关键工具：`Bash`
- 关键文件：`dvc/tree/local.py`
- 关键命令：
  - 局部 `pytest` 运行 `test_protect_ignore_errors`
- 当前阶段目标：
  - 把 prompt 变成一个最小修复计划
- 阶段产出：
  - 明确计划是“让 `protect()` 忽略共享 cache 场景下的 `EPERM/EACCES`”

#### `fault_localization`

- `step_range`: `step 6-12`
- 关键工具：`Bash`
- 关键文件：`dvc/tree/local.py`
- 关键命令：
  - `git log --oneline | grep -i "5335\\|protect\\|exec"`
  - `git tag | grep "1.11" | sort -V`
- 当前阶段目标：
  - 判断是否需要同时改 `set_exec()`，以及异常处理最适合落在哪一层
- 阶段产出：
  - 认为本轮 F2P 只覆盖 `protect()`
  - 没有扩展到 `set_exec()`

#### `hypothesis_testing`

- `step_range`: `step 7`, `step 15-17`, `step 21`
- 关键工具：`Bash`
- 关键文件：`dvc/tree/local.py`
- 关键命令：
  - 通过 `unittest.mock.patch("os.chmod", side_effect=OSError(...))` 构造最小脚本
- 当前阶段目标：
  - 直接验证“吞掉 `EPERM/EACCES` 后，正常行为与其它异常分支是否仍成立”
- 阶段产出：
  - 确认 `EPERM/EACCES` 会被新逻辑吞掉
  - 确认其它异常仍会冒泡

#### `code_editing`

- `step_range`: `step 13`
- 关键工具：`Edit`
- 关键文件：`dvc/tree/local.py`
- 关键命令：无
- 当前阶段目标：
  - 做最小源码修改
- 阶段产出：
  - 把 `protect()` 改成：
    - 调 `self.chmod(...)`
    - 遇到 `EPERM/EACCES` 时直接返回
    - 其它 `OSError` 继续抛出

#### `validation`

- `step_range`: `step 14-22`
- 关键工具：`Read`、`Bash`
- 关键文件：`dvc/tree/local.py`
- 关键命令：
  - 多次 Python 微型脚本验证
  - `grep -rn "set_exec" --include="*.py"`
  - `git diff`
- 当前阶段目标：
  - 确认 patch 不破坏现有行为，并检查是否需要追到 `set_exec()`
- 阶段产出：
  - 确认当前 benchmark 目标已满足
  - 也确认 `set_exec()` 没被触发到本轮 F2P

#### `termination`

- `step_range`: `step 23`
- 关键工具：无
- 关键文件：无
- 关键命令：无
- 当前阶段目标：
  - 总结并结束
- 阶段产出：
  - 给出“修好 `protect()` 权限错误处理”的收口结论

### 5.2 claude-code

#### `bootstrap`

- `step_range`: `step 2-6`
- 关键工具：`Grep`、`Read`
- 关键文件：`tests/unit/remote/test_local.py`、`dvc/tree/local.py`
- 关键命令：
  - `grep "test_protect_ignore_errors"`
  - `grep "def protect"`
- 当前阶段目标：
  - 建立 failing test 到实现的映射
- 阶段产出：
  - 很快确认入口仍是 `LocalTree.protect()`

#### `repo_exploration`

- `step_range`: `step 7-12`
- 关键工具：`Read`、`Glob`、`Bash`
- 关键文件：`dvc/tree/local.py`
- 关键命令：
  - `ls -la dvc/tree/local.py`
  - `head -280 dvc/tree/local.py | tail -40`
- 当前阶段目标：
  - 看清 `chmod()` 内部已经处理了哪些 errno
- 阶段产出：
  - 发现 `chmod()` 内已有 `EPERM/EACCES` 与 `EROFS` 相关分支
  - 开始考虑把“忽略错误”能力参数化，而不是只改外层

#### `task_planning`

- `step_range`: `step 13-18`
- 关键工具：`Edit`、`Bash`
- 关键文件：`dvc/tree/local.py`
- 关键命令：
  - 直接读改 `chmod()` 和 `protect()` 周边文本
- 当前阶段目标：
  - 设计一个可复用的 helper 层修复
- 阶段产出：
  - 计划给 `chmod()` 增加 `ignore_errors=False`
  - 让 `protect()` 调用 `self.chmod(..., ignore_errors=True)`

#### `fault_localization`

- `step_range`: `step 7-18`
- 关键工具：`Read`、`Grep`
- 关键文件：`dvc/tree/local.py`
- 关键命令：
  - `grep "def chmod"`
  - `grep "def protect"`
- 当前阶段目标：
  - 确认最稳定的落点是 helper 层而不是调用者层
- 阶段产出：
  - 认为把逻辑放在 `chmod()` 上更通用，也更贴近 release note 的 `protect/set_exec` 文义

#### `hypothesis_testing`

- `step_range`: `step 22-24`
- 关键工具：`Bash`
- 关键文件：`dvc/tree/local.py`
- 关键命令：
  - 运行目标 `pytest`
  - `python3 -c "from dvc.tree.local import LocalTree; print('Import successful')"`
- 当前阶段目标：
  - 检查 patch 至少在导入层和 failing test 层面成立
- 阶段产出：
  - 看到测试基础设施有别的噪声，但导入和 patch 语义均成立

#### `code_editing`

- `step_range`: `step 13`, `step 16-19`
- 关键工具：`Edit`、`Bash`
- 关键文件：`dvc/tree/local.py`
- 关键命令：
  - 由于路径解析问题，后续借助 Bash 做了文本替换收尾
- 当前阶段目标：
  - 完成 helper 层抽象与调用者透传
- 阶段产出：
  - `chmod(self, path_info, mode, ignore_errors=False)`
  - `protect()` 改为 `self.chmod(..., ignore_errors=True)`

#### `validation`

- `step_range`: `step 20-25`
- 关键工具：`Bash`
- 关键文件：`dvc/tree/local.py`
- 关键命令：
  - `pytest tests/unit/remote/test_local.py::test_protect_ignore_errors`
  - `git diff`
- 当前阶段目标：
  - 验证 diff 是否最小且行为自洽
- 阶段产出：
  - 确认 patch 结构正确
  - 用 import smoke test 验证没有语法级错误

#### `termination`

- `step_range`: `step 26`
- 关键工具：无
- 关键文件：无
- 关键命令：无
- 当前阶段目标：
  - 总结并结束
- 阶段产出：
  - 输出“给 `chmod()` 加 `ignore_errors` 并由 `protect()` 启用”的最终结论

## 6. Hypothesis Iteration Log

### 6.1 innercc

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `6-12` | `protect()` 应该在共享 cache 场景下吞掉 `EPERM/EACCES` | failing test 名称、`dvc/tree/local.py` 现有 `protect()->chmod()` 调用链 | 两条 F2P 都直接指向 `protect_ignore_errors`，而 `chmod` 是唯一实际会抛异常的位置 | 对 benchmark 是正确的；它精确命中了 F2P |
| `18-21` | 本轮不需要追到 `set_exec()`，只修 `protect()` 即可 | grep `set_exec` 结果、F2P 清单 | benchmark 没有任何 `set_exec` 相关测试 | 对 benchmark 正确，但比 official release bundle 更窄 |

### 6.2 claude-code

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `7-18` | 问题不只在 `protect()`，而是 `chmod()` 需要一个“忽略错误”的调用语义 | `chmod()` 已有 errno 分支、release note 文本提到 `protect/set_exec` | helper 层抽象更容易复用到其它调用点 | 对本轮 benchmark 是正确的，也比只改 `protect()` 更接近 official patch 的设计方向 |
| `22-25` | 即使本地 pytest 还有测试环境噪声，只要目标测试与 import smoke test 没显示语法问题，当前 patch 就足以通过 evaluator | exact failing test、import smoke test、`git diff` | 这是一个单点权限处理 case，理论上不需要广泛回归 | 最终被 evaluator 证明为正确 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- patch 只改了 `dvc/tree/local.py`。
- 改动落点：
  - `LocalTree.protect()`
- 修改方向：
  - 把 `EPERM/EACCES` 视为 shared cache 场景下的非致命错误
- 命中真实故障点：
  - 是。F2P 正在验证 `protect()` 不应因这两类权限错误失败。
- 与 golden patch 的核心差异：
  - official patch 把逻辑放在 `chmod()` 里，并统一记录 `trace` 日志。
  - `innercc` 只在 `protect()` 外层兜底。
- 风险评估：
  - 对本 benchmark 足够
  - 但如果后续还需要 `set_exec()` 共享同样语义，这个写法不如 helper 层抽象可复用

### 7.2 claude-code

- patch 也只改了 `dvc/tree/local.py`。
- 改动落点：
  - `LocalTree.chmod()`
  - `LocalTree.protect()`
- 修改方向：
  - 增加 `ignore_errors=False`
  - 让 `protect()` 显式启用该能力
- 命中真实故障点：
  - 是。`protect()` 的失败来自 `chmod()`，把可忽略错误能力下沉到 helper 层是合理设计。
- 与 golden patch 的核心差异：
  - official patch 直接把所有 `OSError` 视作非致命并打 `trace` 日志
  - `claude-code` 仍保留了原先 `actual != mode` 的检查路径，只是在 `ignore_errors=True` 时提前返回
- 风险评估：
  - 结构比 `innercc` 更可复用
  - 但仍没有完全复现 official patch 的 “catch-all + trace log” 宽度

## 8. Evaluation And Failure Evidence

这不是失败 case；关键是证明“修到且没有回归”。

- `innercc` 的 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.11.12_1.11.13/report.json) 显示：
  - `resolved = true`
  - `FAIL_TO_PASS = 2/2`
  - `PASS_TO_PASS = 4/4`
- `claude-code` 的 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.11.12_1.11.13/report.json) 完全一致。

运行收口证据也很完整：

- 两边的 [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.11.12_1.11.13/run_instance.log) / [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.11.12_1.11.13/run_instance.log) 都显示：
  - patch 成功应用
  - docker evaluation 正常运行
  - 目标测试输出已写回 `test_output.txt`

额外结论：

- `innercc` 虽然没有补 release note 中的 `set_exec` 方向，但 benchmark 并未要求它。
- `claude-code` 的 helper 层改法也没有引入额外回归。

## 9. Root Cause

- `direct_root_cause`
  - 这不是 bad case。成功的直接原因是两个 CLI 都把任务缩到了单一调用链：
    - `tests/unit/remote/test_local.py`
    - `LocalTree.protect()`
    - `LocalTree.chmod()`
  - 任务边界窄、失败模式清晰，几乎没有歧义空间。

- `contributing_factors`
  - F2P 只有两条，且都在同一个测试函数族里。
  - 现有代码已经有 `EROFS` 与 `EPERM/EACCES` 相关上下文，agent 不需要重建复杂领域知识。
  - 两边都用 mocked `os.chmod` 做了最小黑盒验证。

- `non_root_but_misleading_signals`
  - release note 文本包含 `set_exec`，但 benchmark 没有把它放进 F2P。
  - official patch 采用的是更宽的 catch-all + trace logging 方案；如果只看 release bundle，可能误以为必须完全照抄更大改动。

## 10. CLI Optimization Opportunities

### 10.1 case_specific_actions

1. 在 release note 同时提到 `A/B`、但 F2P 只覆盖 `A` 时，CLI 应在总结里显式写出“benchmark-complete but release-bundle narrower/partial”。
   为什么能缓解这个问题：可以区分“通过 benchmark”与“完全覆盖 release bundle”两种完成标准。
   适用 case：release note 一句话含多个子行为、但 failing tests 只锚定其中一部分。
   如何验证：检查最终总结是否显式标注“本 patch 命中 benchmark，但未扩展到未测子项”。

2. 在 helper 层与调用者层都能落补丁时，加入“共享调用点数量”比较。
   为什么能缓解这个问题：能系统地在最小修复与更可复用抽象之间做可解释选择。
   适用 case：错误处理、参数透传、格式化 helper 等共享函数问题。
   如何验证：统计 patch 是落在单一调用者还是共享 helper，并对照后续同类 case 的复用率。

### 10.2 generalizable_actions

1. 对单点、单函数、单 failing-test family 的 case，优先 exact failing test，再做最小 mocked 验证。
   为什么能缓解这个问题：这种闭环对窄任务最稳，不需要过度扩展搜索面。
   适用 case：权限错误处理、单个 formatter、单个 CLI 参数透传。
   如何验证：对比“是否先跑 exact F2P”与最终 resolved 率。

2. 在 resolved 后追加一轮 “golden breadth diff” 检查。
   为什么能缓解这个问题：可以发现“benchmark 通过但实现仍比 official patch 更窄”的潜在缺口。
   适用 case：release patch 明显比 benchmark F2P 更宽的 case。
   如何验证：记录 resolved case 中 “patch narrower than golden” 的比例，并追踪这些 case 是否在相邻版本继续复发。
