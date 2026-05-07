# iterative__dvc_0.89.0_0.90.0 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_0.89.0_0.90.0`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `wrong_target_both`
- 一句话结论：
  这个 case 的 benchmark target 是 `HTTPURLInfo`、protected mode 与 `gc -c` 语义等 6 条 release 变更，但两个 CLI 都被当前环境中的 `pathlib`/Python 兼容噪声带偏，只改了 `dvc/path_info.py` 与 `tests/dir_helpers.py`，完全没有覆盖真正的 release target；其中 `innercc` 还因为错误地同步 benchmark test patch，额外引入了 `183` 条 `PASS_TO_PASS` 回归。
- 根因标签：
  - `task_understanding_error`
  - `wrong_target`
  - `validation_gap`
  - `edit_safety_error`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
* version: add supported remotes (#3498) @efiop
* import-url: allow queries in URL (#3432) @casperdcl
* template: pr update (#3495) @casperdcl
* dvc: use protected mode by default (#3472) @efiop
* gc: do not work without specifier when using -c flag (#3493) @skshetry
* completion: add --summary flag on checkout (#3491) @skshetry
```

`FAIL_TO_PASS`: `27` 条，核心分成 5 个簇：

1. `protected mode` / `is_protected`：`tests/func/test_cache.py`, `tests/unit/remote/test_local.py`
2. `gc -c` 语义：`tests/func/test_gc.py::*`
3. `version` 支持 remotes 输出：`tests/func/test_version.py::*`
4. `HTTPURLInfo` / `allow queries in URL`：`tests/unit/test_path_info.py::test_https_url_info_str` 等
5. `path_info` / URLInfo 的新语义与 deepcopy：其余 `tests/unit/test_path_info.py::*`

`PASS_TO_PASS`: `282` 条，是一个非常强的回归保护网。

### 2.2 runner-level user query

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_0.89.0_0.90.0

Release note / requirement:
* version: add supported remotes (#3498) @efiop
* import-url: allow queries in URL (#3432) @casperdcl
* template: pr update (#3495) @casperdcl
* dvc: use protected mode by default (#3472) @efiop
* gc: do not work without specifier when using -c flag (#3493) @skshetry
* completion: add --summary flag on checkout (#3491) @skshetry

Expected failing tests that should pass after your fix:
- tests/func/test_cache.py::test_shared_cache[False-493]
- tests/func/test_cache.py::test_shared_cache[True-509]
- tests/func/test_gc.py::test_gc_cloud_with_or_without_specifier
- tests/func/test_gc.py::test_gc_cloud_without_any_specifier
- tests/func/test_version.py::test_info_in_repo
- tests/func/test_version.py::test_info_outside_of_repo
- tests/unit/remote/test_local.py::test_is_protected[hardlink]
- tests/unit/remote/test_local.py::test_is_protected[symlink]
- tests/unit/test_path_info.py::test_https_url_info_str
- tests/unit/test_path_info.py::test_path_info_as_posix[../../../../..-../../../../..-posix]
- tests/unit/test_path_info.py::test_path_info_as_posix[../some/rel/path-../some/rel/path-posix]
- tests/unit/test_path_info.py::test_path_info_as_posix[..\\..\\..\\..\\..-../../../../..-nt]
- tests/unit/test_path_info.py::test_path_info_as_posix[..\\windows\\rel\\path-../windows/rel/path-nt]
- tests/unit/test_path_info.py::test_path_info_as_posix[/some/abs/path-/some/abs/path-posix]
- tests/unit/test_path_info.py::test_path_info_as_posix[some/rel/path-some/rel/path-posix]
- tests/unit/test_path_info.py::test_path_info_as_posix[windows\\relpath-windows/relpath-nt]
- tests/unit/test_path_info.py::test_url_info_deepcopy[CloudURLInfo]
- tests/unit/test_path_info.py::test_url_info_deepcopy[HTTPURLInfo]
- tests/unit/test_path_info.py::test_url_info_deepcopy[URLInfo]
- tests/unit/test_path_info.py::test_url_info_eq[CloudURLInfo]
- tests/unit/test_path_info.py::test_url_info_eq[URLInfo]
- tests/unit/test_path_info.py::test_url_info_parent[CloudURLInfo]
- tests/unit/test_path_info.py::test_url_info_parent[URLInfo]
- tests/unit/test_path_info.py::test_url_info_parents[CloudURLInfo]
- tests/unit/test_path_info.py::test_url_info_parents[URLInfo]
- tests/unit/test_path_info.py::test_url_info_str[CloudURLInfo]
- tests/unit/test_path_info.py::test_url_info_str[URLInfo]

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

### 2.3 trace-level agent goals

- `innercc`
  - 几乎从一开始就把任务重写成“修 Python 3.12 / pathlib 内部 API 兼容性”。
  - 后续确实还跑了 `test_cache`, `test_gc`, `test_version`, `test_local`，但中心假设始终没变。
  - 结果是用一个错误的低层兼容解释去吸收本应独立的 5 个功能簇。
- `claude-code`
  - 更快锁定在 `dvc/path_info.py` 与 `tests/dir_helpers.py` 的 pathlib 构造逻辑。
  - 几乎没有进入 official patch 所指向的 `remote/http.py`, `remote/local.py`, `command/gc.py`, `command/version.py` 等真正目标文件。

### 2.4 official golden answer

官方 golden patch 的关键不在 pathlib 兼容，而在 6 条 release 语义：

#### Golden cluster A: `HTTPURLInfo` 支持 query/params

```diff
+class HTTPURLInfo(URLInfo):
+    def __init__(self, url):
+        p = urlparse(url)
+        stripped = p._replace(params=None, query=None, fragment=None)
+        super().__init__(stripped.geturl())
+        self.params = p.params
+        self.query = p.query
+        self.fragment = p.fragment
```

并且：

```diff
 class RemoteHTTP(RemoteBASE):
     scheme = Schemes.HTTP
+    path_cls = HTTPURLInfo
```

这对应 `import-url: allow queries in URL`。

#### Golden cluster B: `protected mode` 默认开启与 `is_protected`

```diff
+    def is_protected(self, path_info):
+        return False
```

以及 `RemoteLOCAL` 的：

```diff
+    CACHE_MODE = 0o444
...
+    def is_protected(self, path_info):
+        ...
+        return stat.S_IMODE(mode) == self.CACHE_MODE
```

这对应 `tests/func/test_cache.py` 与 `tests/unit/remote/test_local.py`。

#### Golden cluster C: `gc -c` 没有 specifier 时应报错

```diff
@@
-            cloud=self.args.cloud,
```

以及 `repo/gc.py` 相应移除 `cloud` 参数透传逻辑。这对应 `tests/func/test_gc.py::*`。

#### Golden cluster D: `version` 支持 remotes 信息与 CLI 补全

官方 patch 还改了 `dvc/command/version.py` 与 completion 脚本：

```diff
-_dvc_checkout='-d --with-deps -R --recursive -f --force --relink'
+_dvc_checkout='-d --with-deps -R --recursive -f --force --relink --summary'
```

因此 benchmark 真正要修的是一组 release 语义，而不是底层 pathlib internals。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count | patch_apply |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `innercc` | `false` | `0/27` | `99/282` | `549408` | `118` | `117` | `7` | `true` |
| `claude-code` | `false` | `0/27` | `282/282` | `578323` | `83` | `82` | `11` | `true` |

对比要点：

- 两边 F2P 都是 `0/27`，说明没有命中 benchmark target。
- `claude-code` 没有额外回归，但完全修错目标。
- `innercc` 不但修错目标，还把 `282` 条 P2P 里的 `183` 条打回去了，说明它对低层 pathlib / test helper 的修改破坏面很大。

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.89.0_0.90.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.89.0_0.90.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.89.0_0.90.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.89.0_0.90.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.89.0_0.90.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.89.0_0.90.0/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_0.89.0_0.90.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.89.0_0.90.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.89.0_0.90.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.89.0_0.90.0/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.89.0_0.90.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.89.0_0.90.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.89.0_0.90.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.89.0_0.90.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.89.0_0.90.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.89.0_0.90.0/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_0.89.0_0.90.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_0.89.0_0.90.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_0.89.0_0.90.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_0.89.0_0.90.0/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### `bootstrap` (`step 1-20`)

- `step_range`: `1-20`
- 关键工具：`Bash`
- 关键命令：局部 `pytest tests/unit/test_path_info.py`, `pytest tests/unit/remote/test_local.py`
- 当前阶段目标：找出最先报错的 failing test。
- 阶段产出：最早暴露的是 `path_info.py` / pathlib 兼容异常。

#### `repo_exploration` (`step 21-60`)

- `step_range`: `21-60`
- 关键工具：`Bash`, `Edit`
- 关键文件：`dvc/path_info.py`, `tests/dir_helpers.py`
- 关键命令：大量 `python3 -c` 探测 `_from_parts`, `_cparts`, `_tail`, `_load_parts`
- 当前阶段目标：理解 pathlib 内部 API 差异。
- 阶段产出：把问题框成“Python 3.12 兼容性”。

#### `task_planning` (`step 57-60`)

- `step_range`: `57-60`
- 关键工具：`Edit`
- 关键文件：`tests/dir_helpers.py`
- 当前阶段目标：为 pathlib 兼容性设计修补方案。
- 阶段产出：决定同时改 `dvc/path_info.py` 与 `tests/dir_helpers.py`。

#### `fault_localization` (`step 61-89`)

- `step_range`: `61-89`
- 关键工具：`Bash`, `Edit`
- 关键文件：`dvc/path_info.py`, `tests/dir_helpers.py`
- 关键命令：`pytest tests/func/test_version.py`, `pytest tests/func/test_cache.py`, `pytest tests/func/test_gc.py`
- 当前阶段目标：验证 pathlib 兼容改动是否能带动其余 failing tests。
- 阶段产出：即便开始跑 `cache/gc/version`，它仍然把所有失败都尝试解释成 pathlib helper 的副作用。

#### `hypothesis_testing` (`step 90-117`)

- `step_range`: `90-117`
- 关键工具：`Bash`
- 关键命令：大量 unit/func pytest 和 Python probe
- 当前阶段目标：确认 path helper 改动是否充分。
- 阶段产出：发现更多回归，但没有因此切换到 official patch 对应的真实功能簇。

#### `code_editing` (`step 57-89`)

- `step_range`: `57-89`
- 关键工具：`Edit`
- 关键文件：`dvc/path_info.py`, `tests/dir_helpers.py`
- 当前阶段目标：修复兼容性。
- 阶段产出：改动直接进入测试 helper 层，违反 prompt 的 non-test 约束。

#### `validation` (`step 90-117`)

- `step_range`: `90-117`
- 关键工具：`Bash`
- 当前阶段目标：验证是否通过更多 failing tests。
- 阶段产出：验证信号显示 P2P 在大量回归，但 agent 没把这当作错误目标的强反证。

#### `termination` (`step 118`)

- `step_range`: `118`
- 当前阶段目标：结束会话。
- 阶段产出：以“Python 3.12 compatibility fix 完成”收口，与 benchmark target 明显不匹配。

### 5.2 claude-code

#### `bootstrap` (`step 1-11`)

- `step_range`: `1-11`
- 关键工具：`Bash`
- 关键命令：`pytest tests/unit/test_path_info.py::...`, `pytest tests/unit/remote/test_local.py::...`
- 当前阶段目标：快速定位最早失败点。
- 阶段产出：也很快聚焦到 `dvc/path_info.py`。

#### `repo_exploration` (`step 12-40`)

- `step_range`: `12-40`
- 关键工具：`Bash`
- 关键文件：`dvc/path_info.py`
- 关键命令：大量 `python3 -c` 探索 `pathlib` 的 `__new__`, `_from_parts`, `_load_parts`
- 当前阶段目标：找到现代 pathlib 的可用构造方式。
- 阶段产出：完全被底层兼容噪声占满。

#### `task_planning` (`step 41-53`)

- `step_range`: `41-53`
- 关键工具：`Edit`
- 关键文件：`dvc/path_info.py`, `tests/dir_helpers.py`
- 当前阶段目标：实施 minimal compatibility fix。
- 阶段产出：同样改了测试 helper。

#### `fault_localization` (`step 54-67`)

- `step_range`: `54-67`
- 关键工具：`Bash`
- 关键命令：跑 `test_version`, `test_gc`, `test_cache`
- 当前阶段目标：检查是否还有相关失败。
- 阶段产出：虽然这些失败已经明显指向 protected mode / gc 行为，但 agent 仍未跳转到对应源码模块。

#### `hypothesis_testing` (`step 68-80`)

- `step_range`: `68-80`
- 关键工具：`Bash`
- 当前阶段目标：验证兼容性 patch。
- 阶段产出：确认 `path_info` 局部行为改善，但没有再建新假设。

#### `code_editing` (`step 41-59`)

- `step_range`: `41-59`
- 关键工具：`Edit`
- 关键文件：`dvc/path_info.py`, `tests/dir_helpers.py`
- 当前阶段目标：让 unit path tests 在当前环境下工作。
- 阶段产出：补了与 benchmark release note 不同层级的兼容性逻辑。

#### `validation` (`step 60-82`)

- `step_range`: `60-82`
- 关键工具：`Bash`
- 当前阶段目标：验证 path helper 改动。
- 阶段产出：只做了少量局部验证，没有对 `27` 条 F2P 分簇覆盖。

#### `termination` (`step 83`)

- `step_range`: `83`
- 当前阶段目标：结束会话。
- 阶段产出：把整个 case 错判为 minimal compatibility fix。

## 6. Hypothesis Iteration Log

### 6.1 innercc

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `1-60` | 本案主要是当前 Python/pathlib 内部 API 与旧版 DVC helper 不兼容 | `path_info` / `dir_helpers` 的早期异常 | 局部错误很强，而且能稳定复现 | 错；这只是环境噪声，不是 benchmark target |
| `61-89` | 只要修好 `dvc/path_info.py` 与 `tests/dir_helpers.py`，其余 failing tests 会连带恢复 | 多个相关 unit tests、Python probe | 很多 path tests 都依赖这些 helper | 错；`HTTPURLInfo`, `is_protected`, `gc -c`, `version` 都在别的模块 |
| `90-118` | 大量 P2P 失败是兼容性修复尚未完全收口，而不是目标方向错误 | `test_cache`, `test_gc`, `test_version` 的失败输出 | agent 已经在同一假设上投入了很多步，切换成本高 | 错；这正是强反证，说明 patch 已经开始破坏系统 |

### 6.2 claude-code

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `1-40` | 目标问题就是 `pathlib` internals 与旧 helper 的构造方式不兼容 | `test_path_info` 与 `dir_helpers` 的报错 | 局部上完全成立 | 错；它没有解释 `HTTPURLInfo`, `is_protected`, `gc`, `version` |
| `41-59` | 改 `dvc/path_info.py` 与 `tests/dir_helpers.py` 就是 minimal fix | 局部 unit tests | 看上去范围很小、风险可控 | 错；这是对 bundle/多簇任务的错误缩点 |
| `60-83` | 局部 path tests 好转即可结束 | 少量 path/version/gc 局部回看 | 单点兼容 bug 常见收口方式 | 错；对本案完全不足够 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

`innercc` 实际只改了：

- `dvc/path_info.py`
- `tests/dir_helpers.py`

源代码层面的问题有两个：

1. patch 与 official golden patch 的核心文件几乎无交集，完全没碰：
   - `dvc/remote/http.py`
   - `dvc/remote/local.py`
   - `dvc/remote/base.py`
   - `dvc/command/gc.py`
   - `dvc/command/version.py`
   - `scripts/completion/dvc.bash/zsh`
2. 它错误地编辑了测试 helper，导致回归面显著扩大。

因此 `innercc` 的 patch 既没命中真实故障点，也过度深入到底层兼容细节，造成系统性副作用。

### 7.2 claude-code

`claude-code` 的 patch 同样只改了：

- `dvc/path_info.py`
- `tests/dir_helpers.py`

与 `innercc` 相比，它的编辑更窄，所以没有引入 P2P 回归；但这不代表它更接近目标，而只是“更保守地修错了方向”。

与 golden patch 的核心差异：

1. 没有 `HTTPURLInfo`
2. 没有 `RemoteHTTP.path_cls = HTTPURLInfo`
3. 没有 `RemoteLOCAL.is_protected`
4. 没有 `gc -c` 约束变更
5. 没有 version/completion 更新

## 8. Evaluation And Failure Evidence

### innercc

`report.json` 显示：

- `FAIL_TO_PASS`: `0/27`
- `PASS_TO_PASS`: `99/282`

决定性失败证据来自 `test_output.txt` 的两类信号：

1. benchmark target 完全没被修到：

```text
ImportError: cannot import name 'HTTPURLInfo' from 'dvc.path_info'
```

2. patch 还引入了新的 helper 级破坏：

```text
AttributeError: 'PosixTmpDir' object has no attribute '_load_parts'
```

后者直接解释了为何 `183` 条 P2P 回归一起爆发。

### claude-code

`report.json` 显示：

- `FAIL_TO_PASS`: `0/27`
- `PASS_TO_PASS`: `282/282`

决定性失败证据则是官方目标相关错误仍原样存在：

```text
ImportError: cannot import name 'HTTPURLInfo' from 'dvc.path_info'
...
AttributeError: 'RemoteLOCAL' object has no attribute 'is_protected'
```

这说明它的 patch 既没给出 `HTTPURLInfo`，也没实现 protected mode 的核心语义。

## 9. Root Cause

- `direct_root_cause`
  - 两个 CLI 都把 benchmark target 错判成了“当前环境下的 pathlib 兼容性问题”，属于 `wrong_target`。
- `contributing_factors`
  - 当前环境噪声强，`path_info` 与 `dir_helpers` 的异常在最早阶段最显眼。
  - 两边都没有强制把 release note 与 F2P cluster 对齐，也没有检查 official patch 触及的核心模块。
  - 两边都违反了 non-test 约束，编辑了 `tests/dir_helpers.py`。
- `misleading_signals`
  - 局部 unit tests 很容易把 agent 吸到 helper 层。
  - `claude-code` 因为 P2P 全绿，表面上比 `innercc` “安全”，但实际上只是更窄地偏航。

## 10. CLI Optimization Opportunities

### 10.1 case_specific_actions

1. 当 release note 与 F2P 明显分布在多个功能簇时，必须优先构建“目标模块清单”。
   本案只要先列出 `remote/http`, `remote/local`, `command/gc`, `command/version`，就不会被 `path_info` 噪声绑架。
2. 对 benchmark 早期出现的环境兼容异常，应做“目标相关性二次判定”。
   如果它只解释少数 unit helper，而解释不了其余 F2P 簇，就不能让它主导整体计划。

### 10.2 generalizable_actions

1. 把 official patch / benchmark metadata 的 touched files 与 agent patch 做最小集合比对。
   如果 agent patch 完全不触及主要模块，应触发“可能修错目标”的告警。
2. 对 `PASS_TO_PASS` 很大的 case，把“新增回归数”作为高权重停止信号。
   `innercc` 在 `183` 条回归出现后仍继续沿旧假设推进，就是典型的 `hypothesis_lock_in`。
3. 对 non-test-only benchmark，测试文件编辑应默认被判为高风险并阻止 termination。
