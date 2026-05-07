# iterative__dvc_2.19.0_2.20.0 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_2.19.0_2.20.0`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `inner_only`
- 一句话结论：
  这是一个典型的 multi-layer import/update bundle。`innercc` 不只是把 `--no-download` 加进 CLI 和 repo API，还把 partial import 的 stage 生命周期、`fetch()` 补下载路径、`update()` 的无下载语义一起补齐，因此 `14/14` F2P 全过；`claude-code` 主要只做了命令层与 `imp_url()/update()` 表面参数接线，并把 `no_download` 近似成 `ignore_outs()`，结果 unit parser 测试通过了，但真正依赖 dep hash、partial import、remote invalid combination 的 5 条 F2P 全部没过。
- 根因标签：
  - `task_understanding_error`
  - `hypothesis_lock_in`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
## What's Changed
* build: skip install fpm and ruby on Windows by @skshetry in https://github.com/iterative/dvc/pull/8169
* import-url/update: add --no-download flag by @dtrifiro in https://github.com/iterative/dvc/pull/8024
* fs: optimize dvc list --recursive by @rlamy in https://github.com/iterative/dvc/pull/8150
```

`FAIL_TO_PASS`:

- `tests/func/test_data_cloud.py::test_pull_partial_import`
- `tests/func/test_import_url.py::test_import_url_no_download`
- `tests/func/test_update.py::test_update_import_url_no_download`
- `tests/unit/command/test_imp.py::test_import`
- `tests/unit/command/test_imp.py::test_import_no_download`
- `tests/unit/command/test_imp.py::test_import_no_exec`
- `tests/unit/command/test_imp_url.py::test_import_url`
- `tests/unit/command/test_imp_url.py::test_import_url_no_exec_download_flags[--no-download-expected1]`
- `tests/unit/command/test_imp_url.py::test_import_url_no_exec_download_flags[--no-exec-expected0]`
- `tests/unit/command/test_imp_url.py::test_import_url_to_remote`
- `tests/unit/command/test_imp_url.py::test_import_url_to_remote_invalid_combination[--no-download]`
- `tests/unit/command/test_imp_url.py::test_import_url_to_remote_invalid_combination[--no-exec]`
- `tests/unit/command/test_update.py::test_update`
- `tests/unit/command/test_update.py::test_update_to_remote`

`PASS_TO_PASS`: `66` 条。

这题的关键不只是“加一个 CLI flag”，而是三层语义必须同时成立：

1. CLI / parser 层支持 `--no-download`
2. `imp_url()` / `update()` / command API 能把参数传下去
3. partial import 的运行时语义成立：
   - deps hash 应该先被保存
   - outs 可以为空
   - 后续 `pull()` / `update(no_download=True)` 要能继续工作
   - `--to-remote` 与 `--no-download` 的组合要统一报错

### 2.2 runner-level user query

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_2.19.0_2.20.0

Release note / requirement:
## What's Changed
* build: skip install fpm and ruby on Windows by @skshetry in https://github.com/iterative/dvc/pull/8169
* import-url/update: add --no-download flag by @dtrifiro in https://github.com/iterative/dvc/pull/8024
* fs: optimize dvc list --recursive by @rlamy in https://github.com/iterative/dvc/pull/8150

Expected failing tests that should pass after your fix:
- tests/func/test_data_cloud.py::test_pull_partial_import
- tests/func/test_import_url.py::test_import_url_no_download
- tests/func/test_update.py::test_update_import_url_no_download
- tests/unit/command/test_imp.py::test_import
- tests/unit/command/test_imp.py::test_import_no_download
- tests/unit/command/test_imp.py::test_import_no_exec
- tests/unit/command/test_imp_url.py::test_import_url
- tests/unit/command/test_imp_url.py::test_import_url_no_exec_download_flags[--no-download-expected1]
- tests/unit/command/test_imp_url.py::test_import_url_no_exec_download_flags[--no-exec-expected0]
- tests/unit/command/test_imp_url.py::test_import_url_to_remote
- tests/unit/command/test_imp_url.py::test_import_url_to_remote_invalid_combination[--no-download]
- tests/unit/command/test_imp_url.py::test_import_url_to_remote_invalid_combination[--no-exec]
- tests/unit/command/test_update.py::test_update
- tests/unit/command/test_update.py::test_update_to_remote

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

### 2.3 trace-level agent goals

- `innercc`
  - 很早就把任务理解成：
    - command parser 新 flag
    - repo 层参数传递
    - stage import/update 的 partial-import 生命周期
    - pull/fetch 对 partial import 的后续补下载路径
- `claude-code`
  - 把任务主要重写成：
    - 给 `import` / `import-url` / `update` 增加 `--no-download`
    - 让 `no_download` 看起来像 `no_exec` 的一个近邻语义
  - 后续几乎都在围绕这条更窄的解释展开

### 2.4 official golden answer

官方 `patch` 的关键不是单个 hunk，而是一个跨层闭环。

#### Golden fix A: command 层新增 `--no-download`

```diff
diff --git a/dvc/commands/imp.py b/dvc/commands/imp.py
@@
+                no_download=self.args.no_download,
@@
+    no_download_exec_group = import_parser.add_mutually_exclusive_group()
+    no_download_exec_group.add_argument("--no-exec", ...)
+    no_download_exec_group.add_argument("--no-download", ...)
```

同样的逻辑也出现在：

- `dvc/commands/imp_url.py`
- `dvc/commands/update.py`

#### Golden fix B: repo 层统一接收并校验 `no_download`

```diff
diff --git a/dvc/repo/imp_url.py b/dvc/repo/imp_url.py
@@
+    no_download=False,
@@
-    if to_remote and no_exec:
+    if to_remote and (no_exec or no_download):
@@
-        stage.run(jobs=jobs)
+        stage.run(jobs=jobs, no_download=no_download)
```

```diff
diff --git a/dvc/repo/update.py b/dvc/repo/update.py
@@
+    no_download=False,
@@
+    if to_remote and no_download:
+        raise InvalidArgumentError("--to-remote can't be used with --no-download")
@@
+            no_download=no_download,
```

#### Golden fix C: stage / imports / fetch 层实现 partial import 生命周期

```diff
diff --git a/dvc/stage/__init__.py b/dvc/stage/__init__.py
@@
+    def is_partial_import(self) -> bool:
+        return self.is_import and (not self.outs[0].hash_info)
@@
+            self._sync_import(dry, force, jobs, no_download, check_changed=self.frozen)
@@
+        if self.is_partial_import:
+            return {}
```

```diff
diff --git a/dvc/stage/imports.py b/dvc/stage/imports.py
@@
+def update_import(..., no_download=None, ...):
@@
+            stage.reproduce(no_download=no_download, jobs=jobs)
@@
+def sync_import(..., no_download=False, check_changed=False):
@@
+        if not no_download:
+            stage.deps[0].download(stage.outs[0], jobs=jobs)
```

```diff
diff --git a/dvc/repo/fetch.py b/dvc/repo/fetch.py
@@
+    d, f = _fetch_partial_imports(...)
+def _fetch_partial_imports(repo, targets, **kwargs):
+    for stage in repo.partial_imports(targets, **kwargs):
+        stage.run()
```

也就是说，官方答案的核心不是“加一个 flag”，而是“新增 partial import 状态机，并让 import / update / pull 都能理解这种状态”。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `true` | `14/14` | `66/66` | `524540` | `119` | `118` | `2` |
| `claude-code` | `false` | `9/14` | `66/66` | `2273317` | `63` | `62` | `3` |

`claude-code` 通过的 `9` 条基本都是 command/repo API 层测试；失败的 `5` 条全部需要真实 partial import 语义：

- `test_pull_partial_import`
- `test_import_url_no_download`
- `test_update_import_url_no_download`
- `test_import_url_to_remote_invalid_combination[--no-exec]`
- `test_import_url_to_remote_invalid_combination[--no-download]`

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.19.0_2.20.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.19.0_2.20.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.19.0_2.20.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.19.0_2.20.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.19.0_2.20.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.19.0_2.20.0/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_2.19.0_2.20.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.19.0_2.20.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.19.0_2.20.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.19.0_2.20.0/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.19.0_2.20.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.19.0_2.20.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.19.0_2.20.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.19.0_2.20.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.19.0_2.20.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.19.0_2.20.0/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_2.19.0_2.20.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.19.0_2.20.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.19.0_2.20.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.19.0_2.20.0/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: multi-layer scoping (`step 1-22`)

- 关键动作：
  - grep `no_download` / `no-download`
  - 同时读 command tests、func tests、repo 入口、stage 层
  - 尝试运行 unit tests，补装依赖后再回读源码
- 阶段结论：
  - 很快意识到这题不只是 parser patch，而是 import/update/stage/fetch 的跨层修改

#### Phase B: planner widens to lifecycle semantics (`step 23-45`)

- 关键动作：
  - 继续读 `dvc/repo/imp_url.py`、`dvc/repo/update.py`
  - 读 `dvc/stage/__init__.py`、`dvc/stage/imports.py`
  - 找 partial import 后续如何被 `pull()` / `fetch()` 感知
- 阶段结论：
  - 形成了正确假设：
    - `no_download` 需要保留 dep hash、outs 为空、后续可 fetch

#### Phase C: command/repo edits (`step 46-62`)

- 关键文件：
  - `dvc/commands/imp_url.py`
  - `dvc/commands/imp.py`
  - `dvc/commands/update.py`
  - `dvc/repo/imp_url.py`
  - `dvc/repo/update.py`
- 阶段产出：
  - 新增 `--no-download`
  - 与 `--no-exec` 做互斥或组合校验
  - repo API 接收并传递 `no_download`

#### Phase D: stage/fetch semantics (`step 64-95`)

- 关键文件：
  - `dvc/stage/__init__.py`
  - `dvc/stage/imports.py`
  - `dvc/stage/exceptions.py`
  - `dvc/output.py`
  - `dvc/repo/__init__.py`
  - `dvc/repo/index.py`
  - `dvc/repo/fetch.py`
- 阶段产出：
  - 引入 `is_partial_import`
  - 让 `run()/update()/sync_import()` 能理解 `no_download`
  - 给 `fetch()` 增加 partial import 补下载能力

#### Phase E: validation (`step 98-107`)

- 关键动作：
  - 多次 `py_compile`
  - 回读 `imp_url` 当前状态
  - `git diff`
- 阶段结论：
  - patch 虽宽，但围绕同一语义闭环，没有扩散到无关 release-note 项

### 5.2 claude-code

#### Phase A: narrow task framing (`step 2-21`)

- 关键动作：
  - 看 failing tests
  - grep `--no-download` 相关入口
  - 解析 parser 接受哪些参数
- 阶段结论：
  - 主要把任务理解成“给三个命令加上 `--no-download`”

#### Phase B: command/repo surface edits (`step 23-44`)

- 关键文件：
  - `dvc/commands/imp_url.py`
  - `dvc/repo/imp_url.py`
  - `dvc/commands/imp.py`
  - `dvc/commands/update.py`
  - `dvc/repo/update.py`
- 阶段产出：
  - parser 层通过
  - `imp_url()` / `update()` 接收 `no_download`
  - `to_remote + no_download` 组合有了单独报错

#### Phase C: shallow stage follow-up (`step 47-52`)

- 关键文件：
  - `dvc/stage/__init__.py`
  - `dvc/stage/imports.py`
- 阶段结论：
  - 它尝试让 `update_import(..., no_download=True)` 走 `stage.ignore_outs()`
  - 但没有继续把 dep hash 保存、partial import 拉取与 `fetch()` 生命周期补齐

#### Phase D: weak validation + termination (`step 55-64`)

- 关键动作：
  - 读 diff
  - 少量 Python snippets
  - `TodoWrite`
- 阶段结论：
  - 没有回到 function-level partial import 测试去验证“dep hash 是否存在”

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `1-22` | 这是 import/update/stage/fetch 联动题，不是单纯 parser patch | F2P 同时含 unit command tests 与 func partial-import tests | failing tests 明显跨 command 与 func 两层 | 正确 |
| `innercc` | `23-45` | `no_download` 必须建立 partial import 生命周期 | `test_pull_partial_import`、`test_update_import_url_no_download`、stage/imports 代码 | function tests 明确要求先保存 hash，再延后下载 | 正确 |
| `claude-code` | `2-21` | 任务主要是给三个命令加 flag，并让 repo 接收参数 | command tests、CLI parser probing | `9/14` F2P 的确都是这一层 | 只对了一半 |
| `claude-code` | `47-52` | `no_download` 可近似为 `ignore_outs()` | `no_exec` 现有语义、stage 层局部阅读 | 表面上都像“不生成本地输出” | 错误，`no_download` 仍需要保存 dep hash 并支持后续 fetch/update |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- 优点：
  - patch 与 official golden answer 的核心文件集合高度重合
  - 不只是改 `commands/*` 与 `repo/*`
  - 还补了：
    - `Stage.is_partial_import`
    - `sync_import(..., no_download=...)`
    - `Repo.partial_imports()`
    - `fetch()` 对 partial import 的补下载
- 评价：
  - 这是典型的“成功识别多层语义闭环”的大 patch

### 7.2 claude-code

- 命中的部分：
  - `commands/imp.py`
  - `commands/imp_url.py`
  - `commands/update.py`
  - `repo/imp_url.py`
  - `repo/update.py`
  - 少量 `stage/__init__.py`、`stage/imports.py`
- 缺失的部分：
  - 没有 `Repo.partial_imports()` / `Index.partial_imports()`
  - 没有 `fetch()` 对 partial import 的补下载
  - 没有 `Output.clear()` / `is_partial_import` 这一套完整状态机
- 关键误解：
  - 把 `no_download` 过度类比成 `no_exec`
  - 于是 `imp_url(no_download=True)` 没有生成测试要求的 dep hash

## 8. Evaluation And Failure Evidence

来自 [claude-code test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.19.0_2.20.0/test_output.txt) 的直接证据：

- `test_import_url_no_download` 与 `test_update_import_url_no_download` 都失败在 dep hash 缺失：

```text
E       AssertionError: assert None == 'd10b4c3ff123b26dc068d43a8bef2d23'
E        +  where None = Dependency: 'remote://workspace/file'.hash_info.value
```

- `test_import_url_to_remote_invalid_combination` 失败在错误消息仍然分裂成两套：

```text
E       assert '--no-exec/--no-download cannot be combined with --to-remote' in ...
E       ... InvalidArgumentError: --no-exec can't be combined with --to-remote
```

这和它的 patch 完全一致：

- 只在 `imp_url()` 中分别抛 `--no-exec can't ...` 与 `--no-download can't ...`
- 没有对齐 official patch 的统一错误语义

相反，`innercc` 的 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.19.0_2.20.0/report.json) 显示：

- `resolved = true`
- `FAIL_TO_PASS = 14/14`
- `PASS_TO_PASS = 66/66`

## 9. Root Cause

- `direct_root_cause`
  - `claude-code` 的直接根因是 task understanding 不足：把一个 partial-import 生命周期问题收缩成了“给命令加 `--no-download` 参数”。
- `contributing_factors`
  - 它把 `no_download` 近似成 `no_exec/ignore_outs()`，因此漏掉了 dep hash、partial import fetch、统一 invalid-combination 报错等行为。
  - 验证闭环没有回到 function-level F2P，没能及时发现 `hash_info.value is None` 这一决定性证据。
- `non_root_but_misleading_signals`
  - parser-level tests 和部分 unit command tests 会让 patch 看起来“已经差不多”
  - 但这只是表层成功，不代表运行时语义闭环已完成

## 10. CLI Optimization Opportunities

1. 对同时包含 unit command tests 与 func lifecycle tests 的 case，必须自动提升任务层级判断。只要 F2P 同时覆盖 parser API 与 runtime 生命周期，默认就不能把任务当成单纯命令行参数题。验证方式是要求 agent 在计划阶段明确写出“surface API + lifecycle semantics”两个层次。
2. 不要把新语义机械映射到现有近邻语义。`no_download` 与 `no_exec` 看起来相近，但它们对 dep hash、outs、后续 pull/update 的要求不同。适用于 flag semantic、schema option、cache policy 等相似接口 case。验证方式是增加一条规则：若新 flag 出现在 function tests 而不仅是 parser tests，必须检查其 downstream state transitions。
3. function-level F2P 必须优先于 parser-level F2P 收口。这个 case 里一旦验证 `test_import_url_no_download`，就会立刻暴露 `hash_info.value is None` 的真实缺口。验证方式是要求结束前至少覆盖一条最能反映运行时语义的 func test。
