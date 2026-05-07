# iterative__dvc_3.4.0_3.5.0 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_3.4.0_3.5.0`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `inner_only`
- 一句话结论：
  这是一个明显的多子任务 release-note case：`innercc` 至少覆盖了 `api.get_url` 与 `fetch --type` 两个目标点，因此 `F2P = 2/2`；`claude-code` 只抓住了 `get_url_subrepos` 相关的 API 线索，完全漏掉了 `test_fetch` 这一条命令行契约，因此两个目标测试都没过。
- 根因标签：
  - `task_understanding_error`
  - `localization_error`
  - `hypothesis_lock_in`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement` 的相关部分：

```text
## What's Changed
### 🚀 New Features and Enhancements
* output: checkout: use f-string by @skshetry in https://github.com/iterative/dvc/pull/9715
* fetch: introduce --type metrics/plots by @efiop in https://github.com/iterative/dvc/pull/9718
### 🐛 Bug Fixes
* repro:  ignore --downstream if used together with --pipeline by @skshetry in https://github.com/iterative/dvc/pull/9692
### Other Changes
* api.get_url: use index storage for getting remote URL by @pmrowla in https://github.com/iterative/dvc/pull/9676
...
```

`FAIL_TO_PASS`:

- `tests/func/api/test_data.py::test_get_url_subrepos`
- `tests/unit/command/test_data_sync.py::test_fetch`

`PASS_TO_PASS`: `26` 条。

这个 case 不是一个单点 bug，而是至少两个独立改动被打包进同一 benchmark：

1. `api.get_url` 在 subrepo / remote URL 路径上的行为调整
2. `fetch` 命令新增 `--type metrics/plots`

### 2.2 runner-level user query

两个 CLI 实际收到的 prompt 为：

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_3.4.0_3.5.0

Release note / requirement:
<!-- Release notes generated using configuration in .github/release.yml at main -->

## What's Changed
### 🚀 New Features and Enhancements
* output: checkout: use f-string by @skshetry in https://github.com/iterative/dvc/pull/9715
* fetch: introduce --type metrics/plots by @efiop in https://github.com/iterative/dvc/pull/9718
### 🐛 Bug Fixes
* repro:  ignore --downstream if used together with --pipeline by @skshetry in https://github.com/iterative/dvc/pull/9692
### Other Changes
* api.get_url: use index storage for getting remote URL by @pmrowla in https://github.com/iterative/dvc/pull/9676
...

Expected failing tests that should pass after your fix:
- tests/func/api/test_data.py::test_get_url_subrepos
- tests/unit/command/test_data_sync.py::test_fetch

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

### 2.3 trace-level agent goals

两个 CLI 对任务的内部重写方式差异很大。

- `innercc`
  - 最终把任务拆成多个 release-note 子改动
  - patch 实际覆盖了：
    - `dvc/api/data.py`
    - `dvc/commands/data_sync.py`
    - `dvc/repo/fetch.py`
    - `dvc/repo/index.py`
    - `dvc/fs/dvc.py`
    - `dvc/repo/__init__.py`
  - 说明它把任务理解成“至少要同时覆盖 api.get_url 与 fetch 新参数”

- `claude-code`
  - 实际 patch 只改了 `dvc/api/data.py`
  - 说明它把任务几乎完全收敛成了 `get_url_subrepos` 的 API 行为问题
  - 对 `test_fetch` 对应的 `--type` CLI 契约几乎没有形成有效任务分支

### 2.4 official golden answer

这个 case 的官方 golden patch 至少包含两组关键行为改动。

#### Golden fix A: `dvc/api/data.py`

核心目标是让 `api.get_url` 基于 index / storage map 获取 remote URL，正确处理 subrepo 场景。

#### Golden fix B: `fetch --type`

核心目标是给 `fetch` 命令和 repo 层加上 `types` 过滤链路：

```diff
diff --git a/dvc/commands/data_sync.py b/dvc/commands/data_sync.py
@@
+                types=self.args.types,
...
+    fetch_parser.add_argument(
+        "--type",
+        dest="types",
+        action="append",
+        default=[],
+        choices=["metrics", "plots"],
+    )
```

同时 repo / index 层也跟着接入：

- `dvc/repo/fetch.py`
- `dvc/repo/index.py`

因此官方 gold spec 很明确：

- 这题不是只改一个 API 函数
- 至少要覆盖一个 API 行为修复和一个命令行功能扩展

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count | patch_apply |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `innercc` | `true` | `2/2` | `26/26` | `913132` | `175` | `174` | `4` | `true` |
| `claude-code` | `false` | `0/2` | `26/26` | `1339392` | `79` | `78` | `12` | `true` |

这张表说明：

- `claude-code` 不是把系统改坏了，因为 `P2P = 26/26`
- 它是典型的“只抓住了任务的一部分，另一部分完全漏掉”

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.4.0_3.5.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.4.0_3.5.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.4.0_3.5.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.4.0_3.5.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.4.0_3.5.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.4.0_3.5.0/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_3.4.0_3.5.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.4.0_3.5.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.4.0_3.5.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.4.0_3.5.0/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.4.0_3.5.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.4.0_3.5.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.4.0_3.5.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.4.0_3.5.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.4.0_3.5.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.4.0_3.5.0/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_3.4.0_3.5.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.4.0_3.5.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.4.0_3.5.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.4.0_3.5.0/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: bootstrap + broad release-note interpretation (`step 1-20`)

- 关键动作：
  - 看 git log / last diff
  - 读取 release-note 对应 commit 线索
  - 调用多次 `git show`
- 阶段结论：
  - 这不是一个单函数 bug，而是一个打包 release case
  - 需要同时覆盖 API 和 fetch 功能改动

#### Phase B: multi-file implementation (`step 21-120`，中间细节很多)

- 关键动作：
  - 编辑 `dvc/api/data.py`
  - 编辑 `dvc/commands/data_sync.py`
  - 编辑 `dvc/repo/fetch.py`
  - 编辑 `dvc/repo/index.py`
  - 编辑 `dvc/fs/dvc.py`
  - 编辑 `dvc/repo/__init__.py`
- 说明：
  - `innercc` 的 patch 面很宽
  - 但宽度基本对应 release note 中真实需要落到的多个子模块

#### Phase C: local validation + termination (`step 121-175`)

- 关键动作：
  - 反复看 `git diff`
  - 做局部验证
- 风险：
  - 探索和修改都很多，成本高
- 结果：
  - 最终 evaluator 通过，说明这次“大改动面”并没有偏航

### 5.2 claude-code

#### Phase A: task narrowing to API path (`step 1-25`)

- 关键动作：
  - 大量围绕 `test_get_url_subrepos` 和 `dvc/api/data.py` 展开
  - 看 subrepo / remote URL 路径
- 阶段结论：
  - 任务被迅速收敛成 “修 `get_url_subrepos`”

#### Phase B: code editing on single file (`step 26-40`)

- 关键动作：
  - 最终 patch 只修改了 `dvc/api/data.py`
- 结果：
  - 把返回值从 `dvc_repo.cloud.get_url_for(...)` 改成 `_repo.cloud.get_url_for(...)`

#### Phase C: termination without second branch (`step 41-79`)

- 关键动作：
  - 继续围绕 `get_url` 做验证
  - 最终结束
- 缺失：
  - 没有形成 `test_fetch` 这一分支的独立任务
  - 没有编辑 `data_sync.py`、`repo/fetch.py`、`repo/index.py`

## 6. Hypothesis Iteration Log

### 6.1 innercc

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `1-20` | 这是 release-note 打包 case，至少有 API 和 fetch 两条子任务 | release note + golden clues + git history | release note 明确提了 `api.get_url` 和 `fetch --type` | 正确 |
| `21-120` | 要完成 F2P，需要同时修改命令层、repo 层、index/fs 层 | 多文件源码阅读与改动 | 两个 failing tests 分属不同模块，不可能单点修复 | 正确 |

### 6.2 claude-code

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `1-25` | 核心问题是 `test_get_url_subrepos` 所在的 `api.get_url` 路径 | API test + `dvc/api/data.py` | 其中一条 failing test 很像主问题 | 只对了一部分 |
| `26-79` | 修 `dvc/api/data.py` 足以解决本 case | 单文件阅读与局部验证 | API 路径确实是 release note 的一个要点 | 错。另一条 failing test `test_fetch` 对应的 CLI 新参数完全没覆盖 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc patch

`innercc` 的 patch 很大，但目标对应关系比较清晰：

- `dvc/api/data.py`
  - 处理 subrepo / remote URL 获取路径
- `dvc/commands/data_sync.py`
  - 新增 `--type`
- `dvc/repo/fetch.py`
  - 将 `types` 传到 repo 层
- `dvc/repo/index.py`
  - 增加 metrics / plots 过滤逻辑

这说明它确实把两个 F2P failing tests 都当成独立子任务对待。

### 7.2 claude-code patch

`claude-code` 的 patch 只有：

```diff
diff --git a/dvc/api/data.py b/dvc/api/data.py
@@
-            return dvc_repo.cloud.get_url_for(remote, checksum=md5)
+            return _repo.cloud.get_url_for(remote, checksum=md5)
```

这个改动很窄，说明它的任务理解被锁在 `get_url_subrepos` 上，没有扩展到 `fetch --type`。

## 8. Evaluation And Failure Evidence

### 8.1 innercc: 这是“两个子任务都覆盖到了”

`report.json` 显示：

- `FAIL_TO_PASS = 2/2`
- `PASS_TO_PASS = 26/26`

说明虽然 patch 很大，但 evaluator 认定这两个目标测试都已经修成。

### 8.2 claude-code: 这是“修了 API 角落，但漏掉另一整条功能线”

`report.json` 显示：

- `FAIL_TO_PASS success = []`
- `FAIL_TO_PASS failure = ['tests/func/api/test_data.py::test_get_url_subrepos', 'tests/unit/command/test_data_sync.py::test_fetch']`

`test_output.txt` 里关键失败点有两个：

1. `test_get_url_subrepos`

```text
dvc.config.NoRemoteError: config file error: no remote specified ...
...
dvc.exceptions.NoRemoteInExternalRepoError: No DVC remote is specified in target repository 'subrepo/dir/foo'.
```

说明它对 `get_url_subrepos` 的修补也没有真正满足测试。

2. `test_fetch`

```text
dvc.cli.DvcParserError: parser error
```

以及帮助文本附近显示它缺少 benchmark 期望的新参数链路。

这说明它不仅漏掉了第二条功能线，而且第一条 API 线也没有修完整。

### 8.3 evaluator noise

测试输出里还有大量 `pygit2`、`AttributeError`、`OSError` 等噪声，但 `PASS_TO_PASS = 26/26` 说明这些不属于 benchmark 关键证据。真正决定 resolved 的是上面两条 F2P。

## 9. Root Cause

### 9.1 direct root cause

- `task_understanding_error`
  - `claude-code` 没把 release note 识别成多子任务 case，而是近乎缩成了单个 `get_url` API 问题

- `localization_error`
  - 它把 patch 全落在 `dvc/api/data.py`
  - 但 `test_fetch` 明显要求命令层 / repo 层 / index 过滤链路一起改

### 9.2 contributing factors

- `hypothesis_lock_in`
  - 一旦聚焦到 `get_url_subrepos`，后续探索几乎一直围绕这一条路径展开

- `validation_gap`
  - 没有把两个 failing tests 明确拆成两条 checklist
  - 因此完成了一半思路后就结束了

### 9.3 non-root but misleading signals

- release note 中 `api.get_url` 这一条描述更容易被读成“主修复”
- 如果 agent 不主动对 `FAIL_TO_PASS` 做逐条映射，就很容易忽略 `test_fetch`

## 10. CLI Optimization Opportunities

### 10.1 case-specific actions

1. 如果一个 case 的 `FAIL_TO_PASS` 分布在不同子系统，必须先建“测试 -> 子任务”映射，不允许先只修第一条就结束。
2. release note 同时出现 CLI feature 和 API fix 时，优先按 failing tests 拆开，而不是按 release note 文本重要性排序。

### 10.2 generalizable actions

1. 增加 multi-test decomposition 规则
   - 每个 F2P failing test 必须绑定到一个候选修复模块
2. 增加“coverage-of-failing-tests”检查
   - 如果最终 patch 只触及一条 failing test 对应的模块，不能直接结束
3. 对 release-note 聚合 case，加入“子任务完成度”显式汇报
   - 哪些 failing tests 已覆盖
   - 哪些还没覆盖

### 10.3 validation plan for the optimization

1. 回放此 case，要求 agent 在前 10 步内输出两个 failing tests 的模块映射。
2. 增加规则：若两个 F2P 来自不同路径，结束前必须分别说明 patch 覆盖情况。
3. 再观察 `claude-code` 是否还会只改 `dvc/api/data.py` 就提前收工。
