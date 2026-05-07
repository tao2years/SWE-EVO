# iterative__dvc_0.35.3_0.35.4 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_0.35.3_0.35.4`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `partial_success_both`
- 一句话结论：
  两个 CLI 都正确识别了 broken symlink 需要把 `exists` 改成 `lexists`，也都修好了 `remove` 路径，但都没有沿 evaluator traceback 继续下钻到 `dvc/utils/fs.py:get_mtime_and_size()` 的目录遍历分支，因此 `checkout` 仍然在 broken symlink 场景下崩溃，最终都只做到 `1/2 F2P`。
- 根因标签：
  - `localization_error`
  - `validation_gap`
  - `hypothesis_lock_in`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
1) [Fix bug where `dvc checkout/remove` were not able to handle broken symlinks;](https://github.com/iterative/dvc/issues/1856)
```

`FAIL_TO_PASS`:

- `tests/test_checkout.py::TestCheckoutMovedCacheDirWithSymlinks::test`
- `tests/test_remove.py::TestRemoveBrokenSymlink::test`

`PASS_TO_PASS`: `26` 条，集中在 `tests/test_checkout.py` 与 `tests/test_remove.py` 的既有行为回归保护。

这个 case 是典型 `single_point`，但 failing tests 明确覆盖了两个调用路径：

1. `remove()` 是否能删除 broken symlink。
2. `checkout()` 在 cache dir 搬迁后，是否还能重新建立 symlink，而不是在目录遍历时崩溃。

### 2.2 runner-level user query

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_0.35.3_0.35.4

Release note / requirement:
1) [Fix bug where `dvc checkout/remove` were not able to handle broken symlinks;](https://github.com/iterative/dvc/issues/1856)

Expected failing tests that should pass after your fix:
- tests/test_checkout.py::TestCheckoutMovedCacheDirWithSymlinks::test
- tests/test_remove.py::TestRemoveBrokenSymlink::test

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

### 2.3 trace-level agent goals

- `innercc`
  - 很早就把任务解释为“broken symlink 需要 `lexists()` 而不是 `exists()`”。
  - 内部目标主要落在 `dvc/utils.remove()` 与 `dvc/remote/local.py::do_checkout()`。
  - 没有把 failing test 拆成 `remove path` 和 `directory mtime traversal path` 两个子目标。
- `claude-code`
  - 先从 `remove_unused_links()` 入手，随后扩展到 `dvc/utils.remove()` 与 `RemoteLOCAL.exists()`。
  - 内部目标比 `innercc` 更偏 “把所有显眼的 `exists()` 都换掉”。
  - 也没有沿 traceback 继续定位 `dvc/utils/fs.py`。

### 2.4 official golden answer

官方 golden patch 的核心不是单一 `exists -> lexists` 替换，而是同时补上三层 broken symlink 兼容。

#### Golden hunk A: `dvc/remote/local.py`

```diff
@@
-        return os.path.exists(path_info["path"])
+        return os.path.lexists(path_info["path"])
@@
-            if os.path.exists(path):
+            if self.exists(path_info):
@@
-                if os.path.exists(p):
+                if self.exists(entry_info):
```

这部分对应 `checkout` / relink 流程里“先判断工作区条目是否存在，再 safe_remove”的逻辑。

#### Golden hunk B: `dvc/utils/__init__.py`

```diff
@@
-def remove(path):
-    if not os.path.exists(path):
-        return
+def remove(path):
@@
-        perm = os.stat(p).st_mode
+        perm = os.stat(p).st_mode
+    except OSError as exc:
+        if exc.errno != errno.ENOENT:
+            raise
@@
-    if os.path.isfile(path):
-        _chmod(os.unlink, path, None)
-    else:
-        shutil.rmtree(path, onerror=_chmod)
+    try:
+        if os.path.isdir(path):
+            shutil.rmtree(path, onerror=_chmod)
+        else:
+            _chmod(os.unlink, path, None)
+    except OSError as exc:
+        if exc.errno != errno.ENOENT:
+            raise
```

这部分修的是 remove 路径对 broken symlink 的健壮性。

#### Golden hunk C: `dvc/utils/fs.py`

```diff
@@
-                stat = os.stat(entry)
+                try:
+                    stat = os.stat(entry)
+                except OSError as exc:
+                    if exc.errno != errno.ENOENT:
+                        raise
+                    continue
```

这一 hunk 才是 `TestCheckoutMovedCacheDirWithSymlinks::test` 仍然失败的直接原因：目录遍历过程中遇到 broken symlink 需要跳过，而不是抛 `FileNotFoundError`。

官方 `test_patch` 也清楚把目标拆成了两条：

- `TestRemoveBrokenSymlink` 验证 `remove` 能删掉 broken symlink。
- `TestCheckoutMovedCacheDirWithSymlinks` 验证 cache dir 搬迁后 `checkout -f` 能重新建立 symlink，而且链接目标从旧 cache dir 切换到新 cache dir。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count | patch_apply |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `innercc` | `false` | `1/2` | `26/26` | `192275` | `60` | `59` | `5` | `true` |
| `claude-code` | `false` | `1/2` | `26/26` | `603869` | `65` | `64` | `7` | `true` |

这个 case 的关键对比不是“谁更接近成功”，而是两者都停在同一个中间态：

- `remove` 侧成功，`TestRemoveBrokenSymlink` 通过。
- `checkout` 侧仍炸，`TestCheckoutMovedCacheDirWithSymlinks` 失败。
- 两边都没有引入 P2P 回归，说明 patch 范围不算过宽，但都漏掉了真正决定 `checkout` 成败的最后一层。

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.35.3_0.35.4/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.35.3_0.35.4/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.35.3_0.35.4/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.35.3_0.35.4/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.35.3_0.35.4/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.35.3_0.35.4/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_0.35.3_0.35.4.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.35.3_0.35.4/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.35.3_0.35.4/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.35.3_0.35.4/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.35.3_0.35.4/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.35.3_0.35.4/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.35.3_0.35.4/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.35.3_0.35.4/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.35.3_0.35.4/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.35.3_0.35.4/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_0.35.3_0.35.4.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_0.35.3_0.35.4/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_0.35.3_0.35.4/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_0.35.3_0.35.4/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### `bootstrap` (`step 1-4`)

- `step_range`: `1-4`
- 关键工具：`Read`, `Bash`
- 关键文件：`tests/test_checkout.py`, `tests/test_remove.py`
- 关键命令：`grep -n "TestCheckoutMovedCacheDirWithSymlinks|TestRemoveBrokenSymlink" ...`
- 当前阶段目标：确认 failing tests 的覆盖路径。
- 阶段产出：识别到 bug 与 broken symlink 相关，但尚未区分 `remove` 与 `checkout` 的不同失败面。

#### `repo_exploration` (`step 5-33`)

- `step_range`: `5-33`
- 关键工具：`Read`, `Bash`
- 关键文件：`dvc/repo/checkout.py`, `dvc/repo/remove.py`, `dvc/output/base.py`, `dvc/remote/local.py`, `dvc/utils/__init__.py`, `dvc/remote/base.py`
- 关键命令：大量 `grep -n "exists|lexists|safe_remove|def link"`
- 当前阶段目标：找到 broken symlink 在 checkout/remove 调用链中的入口。
- 阶段产出：把故障面聚焦到 `dvc/utils.remove()` 与 `RemoteLOCAL.do_checkout()`。

#### `task_planning` (`step 34`)

- `step_range`: `34`
- 关键工具：`Edit`
- 关键文件：`dvc/utils/__init__.py`
- 关键命令：无
- 当前阶段目标：形成修复假设。
- 阶段产出：明确提出“`exists()` 对 broken symlink 返回 False，应该改用 `lexists()`”。

#### `fault_localization` (`step 34-37`)

- `step_range`: `34-37`
- 关键工具：`Edit`
- 关键文件：`dvc/utils/__init__.py`, `dvc/remote/local.py`
- 关键命令：无
- 当前阶段目标：把 `lexists()` 假设映射到源码落点。
- 阶段产出：定位到 `remove()` 与 `do_checkout()` 的存在性判断。

#### `hypothesis_testing` (`step 38-49`)

- `step_range`: `38-49`
- 关键工具：`Bash`, `Edit`
- 关键文件：`dvc/utils/__init__.py`
- 关键命令：
  - `git diff`
  - 多个 `python3 -c` broken symlink probe
- 当前阶段目标：验证 `remove()` 的 broken symlink 行为。
- 阶段产出：修好了 unlink/chmod 对 symlink 的局部逻辑，但验证始终围绕 `remove`，没有复现 `checkout` traceback。

#### `code_editing` (`step 34-47`)

- `step_range`: `34-47`
- 关键工具：`Edit`
- 关键文件：`dvc/utils/__init__.py`, `dvc/remote/local.py`
- 关键命令：无
- 当前阶段目标：最小改动修复 broken symlink。
- 阶段产出：完成 `remove()` 与 `RemoteLOCAL.do_checkout()` 三处 `lexists()` 修改。

#### `validation` (`step 50-55`)

- `step_range`: `50-55`
- 关键工具：`Bash`
- 关键文件：无
- 关键命令：
  - `python3 -m pytest tests/test_remove.py -v`
  - 手写 `python3 -c` 本地 probe
- 当前阶段目标：验证修复是否生效。
- 阶段产出：拿到了 remove 侧的正反馈，但没有稳定跑通 `TestCheckoutMovedCacheDirWithSymlinks::test`。

#### `termination` (`step 56`)

- `step_range`: `56`
- 关键工具：无
- 关键文件：无
- 关键命令：无
- 当前阶段目标：结束会话。
- 阶段产出：在只验证到 remove 路径的情况下收口。

### 5.2 claude-code

#### `bootstrap` (`step 1-4`)

- `step_range`: `1-4`
- 关键工具：`Bash`
- 关键文件：测试文件与仓库根目录
- 关键命令：
  - `python -m pytest ... | head -100`
  - `python3 -m pytest ... | head -100`
- 当前阶段目标：直接看 failing test。
- 阶段产出：确认 checkout case 在当前环境下能稳定失败。

#### `repo_exploration` (`step 5-18`)

- `step_range`: `5-18`
- 关键工具：`Grep`, `Read`
- 关键文件：`dvc/state.py`, `dvc/utils/__init__.py`, `dvc/remote/local.py`
- 关键命令：`grep remove_unused_links`
- 当前阶段目标：找 broken symlink 被忽略的位置。
- 阶段产出：先盯上了 `remove_unused_links()`，随后扩展到 `remove()` 与 `RemoteLOCAL.exists()`。

#### `task_planning` (`step 19-20`)

- `step_range`: `19-20`
- 关键工具：`Edit`
- 关键文件：`dvc/state.py`
- 当前阶段目标：形成第一版修复计划。
- 阶段产出：把问题抽象成“所有 broken symlink 路径都要用 `lexists()`”。

#### `fault_localization` (`step 21-45`)

- `step_range`: `21-45`
- 关键工具：`Read`, `Edit`
- 关键文件：`dvc/state.py`, `dvc/utils/__init__.py`, `dvc/remote/local.py`
- 关键命令：`grep def remove`
- 当前阶段目标：把 `lexists()` 假设扩展到所有显眼入口。
- 阶段产出：新增 `state.py`, `utils/__init__.py`, `remote/local.py` 三个改点。

#### `hypothesis_testing` (`step 49-61`)

- `step_range`: `49-61`
- 关键工具：`Bash`
- 关键文件：无
- 关键命令：多段 `python3 -c` broken symlink / chmod / remove probe
- 当前阶段目标：验证 broken symlink 处理逻辑。
- 阶段产出：发现 `chmod` symlink 会报错，于是改成 `os.lstat()` + `islink()` 分支。

#### `code_editing` (`step 20-52`)

- `step_range`: `20-52`
- 关键工具：`Edit`
- 关键文件：`dvc/state.py`, `dvc/utils/__init__.py`, `dvc/remote/local.py`
- 当前阶段目标：补齐 remove/checkout 的显眼存在性判断。
- 阶段产出：比 `innercc` 多改了一处 `state.py::remove_unused_links()`，但仍未触及 `dvc/utils/fs.py`。

#### `validation` (`step 62-64`)

- `step_range`: `62-64`
- 关键工具：`Bash`
- 关键文件：无
- 关键命令：
  - `python3 -m pytest tests/test_checkout.py -v -k "TestCheckout"`
  - `git diff --stat`
- 当前阶段目标：收口验证。
- 阶段产出：验证被环境噪声打断，CLI 直接把失败归因成环境问题，没有继续对 evaluator traceback 做最小复现。

#### `termination` (`step 65`)

- `step_range`: `65`
- 关键工具：无
- 关键文件：无
- 当前阶段目标：结束会话。
- 阶段产出：在“逻辑上看起来已经补全”的判断下结束。

## 6. Hypothesis Iteration Log

### 6.1 innercc

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `1-33` | broken symlink 的核心就是 `exists()` 把 dangling link 判成不存在 | failing test 名称、`remove()`/`do_checkout()` 代码里的 `exists()` | `TestRemoveBrokenSymlink` 与 `TestCheckoutMovedCacheDirWithSymlinks` 都直接指向 symlink handling | 正确但不完整；它只解释了“入口判断为何跳过 broken symlink”，没解释 `checkout` 的后续目录遍历为何仍会抛 `FileNotFoundError` |
| `34-49` | 只要把 `remove()` 与 `RemoteLOCAL` 的显眼 `exists()` 改成 `lexists()`，两个 failing tests 都会过 | 手写 broken symlink probe、局部 diff | remove 路径本地 probe 直接变好，容易让人以为 checkout 也同样修复 | 错；`checkout` 最深项目帧落在 `dvc/utils/fs.py:get_mtime_and_size()`，该处没有被修改 |
| `50-56` | remove 局部 probe 和 `tests/test_remove.py` 的通过足以代表整体修复完成 | `pytest tests/test_remove.py`、`python3 -c` | 一个 F2P 已过且无回归，看起来风险不大 | 错；这是典型 `validation_gap`，没有 exact 对准另一个 failing test |

### 6.2 claude-code

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `1-20` | broken symlink 漏删是 `remove_unused_links()` / `exists()` 的问题 | failing test 输出、`remove_unused_links()` 代码 | broken symlink 场景里 `exists()` 的确是高频错误点 | 部分正确；解释了 cleanup/remove 的问题，但不是 checkout 崩溃的全部根因 |
| `21-45` | 把 `state.py`、`utils.remove()`、`RemoteLOCAL.exists()` 都改成 `lexists()` 就足够 | grep `exists`、手工代码检查 | 这是从调用链表面最自然的“全面扫描式”修复 | 仍然错误；决定性失败栈不在这三处，而在 `os.walk -> os.stat(entry)` |
| `49-64` | 只要 broken symlink 的本地 probe 都通过，剩余 pytest 失败就是环境噪声 | 多个 `python3 -c` probe、截断式 pytest | 本地 probe 覆盖了 symlink/chmod/unlink 行为 | 错；probe 没覆盖 `get_mtime_and_size()` 里的目录遍历分支 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

`innercc` 的 patch 落点是：

- `dvc/utils/__init__.py`
- `dvc/remote/local.py`

优点：

- 命中了 `remove()` broken symlink 删除的真实故障点。
- 没有改测试，也没有引入额外回归。

不足：

- 没改 `dvc/utils/fs.py`，因此 `checkout` 仍在 `os.walk()` 过程中对 broken symlink 执行 `os.stat(entry)`，直接抛异常。
- 没改 `dvc/repo/scm_context.py`，虽然这不是本次失败主因，但也说明它没有完全贴合 official patch。

与 golden patch 的核心差异：

1. 缺 `dvc/utils/fs.py` 的 `ENOENT -> continue` 逻辑。
2. 因为缺这层，`checkout` case 仍旧失败。

### 7.2 claude-code

`claude-code` 的 patch 落点是：

- `dvc/state.py`
- `dvc/utils/__init__.py`
- `dvc/remote/local.py`

优点：

- 同样修成了 `remove` 路径。
- 额外补了 `remove_unused_links()`，在“清理 broken symlink”这个子问题上更完整。

不足：

- 同样没命中 `dvc/utils/fs.py`。
- 补 `state.py` 是合理的相邻修复，但对本 benchmark 的决定性 F2P 并不起决定作用。

与 golden patch 的核心差异：

1. 同样缺 `dvc/utils/fs.py` hunk。
2. 新增的 `state.py` 修改并不能覆盖 `checkout` 的最深失败帧。

## 8. Evaluation And Failure Evidence

两个 CLI 的 evaluator 结论完全一致：

- `FAIL_TO_PASS`: `1/2`
- 通过：`tests/test_remove.py::TestRemoveBrokenSymlink::test`
- 失败：`tests/test_checkout.py::TestCheckoutMovedCacheDirWithSymlinks::test`
- `PASS_TO_PASS`: `26/26`

决定性失败证据来自 `test_output.txt`：

```text
ERROR: unexpected error - [Errno 2] No such file or directory: '.../data_dir/data'
...
File "/testbed/dvc/utils/fs.py", line 29, in get_mtime_and_size
    stat = os.stat(entry)
FileNotFoundError: [Errno 2] No such file or directory: '.../data_dir/data'
```

这说明评测失败不是“没删掉 broken symlink”，而是：

1. `checkout` 已经走到了 `state.update() -> get_mtime_and_size()`
2. 目录遍历遇到 broken symlink 时直接 `os.stat(entry)` 崩溃
3. 所以真正缺的不是更多 `lexists()`，而是 `os.walk()` 分支里的 `ENOENT` 容错

因此本案属于“修到一半”而不是“完全修错目标”。

## 9. Root Cause

- `direct_root_cause`
  - 两个 CLI 都把 broken symlink 问题过度收缩成“入口处的 `exists()` 判断错误”，没有跟着 evaluator traceback 继续定位到 `dvc/utils/fs.py:get_mtime_and_size()`，属于 `localization_error`。
- `contributing_factors`
  - 两边都主要依赖手写 Python probe 和局部 remove 验证，没有把 validation 对准 `tests/test_checkout.py::TestCheckoutMovedCacheDirWithSymlinks::test`。
  - `innercc` 更早锁定在 `remove()` / `do_checkout()`；`claude-code` 则把 `state.py` 也纳入 patch，但仍停留在同一层抽象。
- `misleading_signals`
  - `TestRemoveBrokenSymlink` 通过，容易造成“broken symlink 已整体修复”的错觉。
  - `26/26 P2P` 全绿也会让 patch 看起来“安全”，但它并不代表目标 F2P 已完成。

## 10. CLI Optimization Opportunities

### 10.1 case_specific_actions

1. 在多 F2P case 中，把每条 failing test 单独收口，而不是用一个抽象解释覆盖全部。
   这能避免像本案这样“remove 侧通过后误判整体完成”；适用于所有 `F2P > 1` 的 symlink / filesystem case。
2. 当 evaluator traceback 已给出最深项目帧时，要求 agent 必须沿该帧继续检查相邻 helper。
   本案里只要继续看 `dvc/utils/fs.py:get_mtime_and_size()`，就能直接发现 golden hunk C。

### 10.2 generalizable_actions

1. 把 “同一 release note 下多个 failing tests 是否共享同一最深项目帧” 做成强制检查项。
   如果不共享，就不能只靠一个统一解释收口。
2. 把 `exact failing test + traceback-derived nearest helper` 组合成默认验证闭环。
   这比手写小 probe 更不容易漏掉目录遍历、状态缓存、异常路径等非直观分支。
3. 对于 filesystem/symlink case，增加“目录遍历、stat/lstat、walk/rmtree”相邻 API 的 checklist。
   这能系统性降低只改入口 `exists()`、却漏掉后续 `stat()` / `walk()` 的概率。
