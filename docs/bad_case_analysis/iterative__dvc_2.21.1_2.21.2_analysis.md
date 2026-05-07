# iterative__dvc_2.21.1_2.21.2 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_2.21.1_2.21.2`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_but_claude_closer`
- 一句话结论：
  这题只有 `1` 条 F2P，但要求很微妙：`api.params_show("untracked-file")` 本身应该能读到文件内容，而一旦再加上 `stages=` 或 `deps=True`，因为这个 target 不属于任何 tracked params，就必须抛 `No params found`。两个 CLI 都把问题理解成“让 untracked target 也能被读到”，结果把“不该出现的 file fallback”保留了下来；`innercc` 还顺手打坏了 3 条原本通过的 params_show 场景，所以 `claude-code` 更接近但仍未解题。
- 根因标签：
  - `task_understanding_error`
  - `validation_gap`
  - `hypothesis_lock_in`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
> Refer to https://dvc.org/doc/install for installation instructions.

## Changes

## 🐛 Bug Fixes 

- api: Fix `params_show` for untracked targets. (#8166) @daavoo
```

`FAIL_TO_PASS`:

- `tests/func/api/test_params.py::test_params_show_untracked_target`

`PASS_TO_PASS`: `8` 条。

这个 target test 的契约是三段式：

1. `api.params_show("params_foo.yaml") == {"foo": 1}`
2. `api.params_show("params_foo.yaml", stages="stage-0")` 应抛 `No params found`
3. `api.params_show("params_foo.yaml", deps=True)` 也应抛 `No params found`

所以它不是“让 untracked file 一律被包含”，而是：

- 在 plain target mode 下允许读取
- 在 `stages` / `deps` filter 收窄后，必须识别“这个 target 不属于任何 tracked params”

### 2.2 runner-level user query

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_2.21.1_2.21.2

Release note / requirement:
> Refer to https://dvc.org/doc/install for installation instructions.

## Changes

## 🐛 Bug Fixes 

- api: Fix `params_show` for untracked targets. (#8166) @daavoo

Expected failing tests that should pass after your fix:
- tests/func/api/test_params.py::test_params_show_untracked_target

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

### 2.3 trace-level agent goals

- `innercc`
  - 目标逐步收缩成：
    - `collect()` 不应该总是 `deps=True`
    - `fs_paths` 里不该重复加入 params
  - 但它最终把核心问题理解成“让 untracked target 同时参与 stages/deps 的配置收集”
- `claude-code`
  - 更直接地把问题理解成：
    - “显式指定的 target 即使没被 tracked，也应该加入 `fs_paths`”
  - 这正好命中第一段契约，却违背了后两段契约

### 2.4 official golden answer

官方 patch 很小，但语义非常精确：

```diff
diff --git a/dvc/repo/params/show.py b/dvc/repo/params/show.py
@@
     if not any(
         item.fs_path == default_params for item in params
     ) and default_params not in (
         fs_paths if deps or stages is not None else []
     ):
         fs_paths.append(default_params)

+    if targets and (deps or stages) and not params:
+        # A target has been provided but it is not used in the stages
+        fs_paths = []
     return params, fs_paths
```

关键点是：

- 当 `targets` 被显式传入
- 且同时加了 `deps` 或 `stages`
- 且 `collect()` 没找到任何匹配的 tracked params
- 就必须清空 `fs_paths`

这正是为了让第二段和第三段契约抛 `No params found`。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `0/1` | `5/8` | `121886` | `19` | `71` | `3` |
| `claude-code` | `false` | `0/1` | `8/8` | `1384672` | `56` | `55` | `18` |

所以：

- 两边都没过唯一 F2P
- `innercc` 还额外打坏了 3 条原本通过的 params_show tests
- `claude-code` 虽然没修对，但至少没引入额外回归

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.21.1_2.21.2/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.21.1_2.21.2/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.21.1_2.21.2/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.21.1_2.21.2/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.21.1_2.21.2/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.21.1_2.21.2/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_2.21.1_2.21.2.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.21.1_2.21.2/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.21.1_2.21.2/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.21.1_2.21.2/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.21.1_2.21.2/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.21.1_2.21.2/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.21.1_2.21.2/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.21.1_2.21.2/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.21.1_2.21.2/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.21.1_2.21.2/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_2.21.1_2.21.2.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.21.1_2.21.2/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.21.1_2.21.2/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.21.1_2.21.2/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: target reading + history fishing (`step 1-15`)

- 关键动作：
  - 读 `tests/func/api/test_params.py`
  - 读 `dvc/repo/params/show.py`
  - 大量 git log / tag / remote / stash 探索
- 阶段结论：
  - 它知道和 untracked target 有关
  - 但前半段花了不少力气在历史与远端信息，而不是直接最小化 F2P 契约

#### Phase B: wrong generalization (`step 15-48`)

- 核心假设：
  - 问题来自 `_collect_configs()` 过度固定 `deps=True`
  - 以及 `fs_paths` 中 tracked/untracked params 的重复处理
- 为什么看起来合理：
  - untracked target 的确会经过 `collect()` 与 `fs_paths`
- 为什么错：
  - benchmark 真正要求的是 “加了 `stages/deps` 后，如果 target 不属于任何 tracked params，就应清空 fallback”

#### Phase C: patch reuse anomaly (`step 49-55`)

- 关键现象：
  - `cli_result.json` 里直接写道 “The fix is already in place in the working directory”
  - trace 里还出现了 `git stash pop`
- 阶段结论：
  - 它更像是在验证一个工作区现成 diff，而不是从头形成新的最小 patch
  - 这也解释了为什么 patch 看起来像另一种“已存在方案”

### 5.2 claude-code

#### Phase A: fast narrowing (`step 2-16`)

- 关键动作：
  - 查 `params_show`
  - 读 `dvc/repo/params/show.py`
  - 看 API 入口
- 阶段结论：
  - 很快压缩到 `_collect_configs()` 的 target/filter 逻辑

#### Phase B: wrong fallback preservation (`step 16-50`)

- 修改内容：
  - 如果显式传入 target 且不在 `all_fs_paths` 中，就把它追加进 `fs_paths`
- 语义后果：
  - 第一段契约 `api.params_show("params_foo.yaml") == {"foo": 1}` 继续成立
  - 但第二、三段本该抛错的路径也继续读到了 untracked file

#### Phase C: cleanup validation (`step 50-57`)

- 关键动作：
  - 甚至通过 `cp ...bak` / 手写 python 方式改文件
  - `git diff`
- 阶段结论：
  - 验证做到了 patch 可读，但没有用 F2P 的三段契约逐条核对

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `1-48` | untracked target 问题来自 `deps=True` 固定值与 fs_paths 去重 | `params_show` 源码、历史探索 | 这些代码确实控制 tracked/untracked 汇总 | 只解决了“如何读到 untracked target”，没解决“何时不该读到它” |
| `claude-code` | `16-50` | 显式指定的 untracked target 应总是被保留到 fs_paths | API 目标测试的第一段断言 | `api.params_show("params_foo.yaml")` 的确需要返回 `{"foo":1}` | 错误，`stages`/`deps` 过滤后应抛 `No params found` |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- patch 内容：
  - `_collect_configs()` 里 `deps=True -> deps=deps`
  - `_read_params()` 里改 `fs_paths` 去重逻辑
- 问题：
  - 这是对整个 params_show 行为的更大范围改写
  - 结果既没过 F2P，又打坏了 3 条 P2P
- 与 official patch 差异：
  - 官方只在 “`targets and (deps or stages) and not params`” 这个极窄分支上清空 `fs_paths`
  - innercc 完全没命中这条 guard

### 7.2 claude-code

- patch 内容：
  - 把显式传入但不在 `all_fs_paths` 中的 target 强行追加到 `fs_paths`
- 问题：
  - 这是把 untracked fallback 永久保留
  - 恰好违背了带 `stages` / `deps` 过滤时应抛错的要求

## 8. Evaluation And Failure Evidence

来自两边 [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.21.1_2.21.2/test_output.txt) / [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.21.1_2.21.2/test_output.txt) 的关键失败都一样：

```text
with pytest.raises(DvcException, match="No params found"):
>   api.params_show("params_foo.yaml", stages="stage-0")
E   Failed: DID NOT RAISE <class 'dvc.exceptions.DvcException'>
```

这说明：

- 两边都保留了不该存在的 untracked file fallback
- 所以 filtered mode 下仍然读到了 `params_foo.yaml`

`innercc` 还额外在 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.21.1_2.21.2/report.json) 里打坏了：

- `test_params_show_no_args`
- `test_params_show_stages`
- `test_params_show_while_running_stage`

## 9. Root Cause

- `direct_root_cause`
  - 两边都误把问题理解成“如何让 untracked target 被读取”，而没有理解成“在加上 stages/deps 过滤后如何让 untracked target 不再被读取”。
- `contributing_factors`
  - 这是单条 F2P，但内部包含三段语义契约；两个 CLI 都只盯住了第一段。
  - `innercc` 还引入了更大范围的 params_show 语义改动。
- `non_root_but_misleading_signals`
  - 第一段断言 `api.params_show("params_foo.yaml") == {"foo": 1}` 很显眼，容易让 agent 以为目标就是“保证 untracked file 可以读”。

## 10. CLI Optimization Opportunities

1. 单条 F2P 不等于单一语义点。对单个 test function，必须拆出它内部的多段断言并逐段对齐。验证方式是要求 trace 中显式列出同一 test 函数的 sequential assertions，而不是只总结测试名。
2. 对 filter/fallback 逻辑，优先检查“何时应该清空 fallback”，而不是只检查“何时追加 fallback”。适用于 params/config/path resolution 类 case。验证方式是 patch review 时强制问一句：这个改动是否让 fallback 更宽了？如果更宽，是否会破坏 filtered mode。
3. 对 P2P 很少的 case，宁可做极窄 guard，也不要改全局收集逻辑。官方 patch 只动了 3 行 guard，正是这类问题的更优策略。
