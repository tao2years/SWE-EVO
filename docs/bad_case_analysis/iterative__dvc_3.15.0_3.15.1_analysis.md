# iterative__dvc_3.15.0_3.15.1 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_3.15.0_3.15.1`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_resolved_reference_success`
- 一句话结论：
  这是一个双方都修成的外部输出正例。两个 CLI 都定位到了 `dvc/output.py::unprotect()` 对非缓存输出过度调用 `cache.unprotect()`，并都补上了“只有 cached output 才 unprotect”的守卫，只是守卫条件的写法不同。
- 根因标签：
  - `reference_success_path`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
<!-- Release notes generated using configuration in .github/release.yml at main -->

## What's Changed
### Other Changes
* don't unprotect outs if not cached by @dberenbaum in https://github.com/iterative/dvc/pull/9838
```

`FAIL_TO_PASS`:

- `tests/func/repro/test_repro.py::test_repro_external_outputs[True]`

`PASS_TO_PASS`: `66` 条。

目标测试的核心场景是：

- `dvc.run(..., outs_no_cache=[bar_path] / outs_persist_no_cache=[bar_path], no_exec=True)`
- 连续 `reproduce()` 与 `reproduce(force=True)`
- 外部输出 `bar` 应保持正常，不应触发 cache 相关 unprotect

### 2.2 runner-level user query

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_3.15.0_3.15.1

Release note / requirement:
<!-- Release notes generated using configuration in .github/release.yml at main -->

## What's Changed
### Other Changes
* don't unprotect outs if not cached by @dberenbaum in https://github.com/iterative/dvc/pull/9838

Expected failing tests that should pass after your fix:
- tests/func/repro/test_repro.py::test_repro_external_outputs[True]

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

### 2.3 trace-level agent goals

- `innercc`
  - 早期就把问题压到 `dvc/output.py::unprotect()`
  - 随后围绕 `use_cache`、`changed_cache()`、external outputs 的关系验证
- `claude-code`
  - 也很快定位到 `unprotect()` 过度调用 `self.cache.unprotect()`
  - 补了一个更显式的 cache/hash guard

### 2.4 official golden answer

官方 patch 非常小：

```diff
diff --git a/dvc/output.py b/dvc/output.py
@@
-        if self.exists:
+        if self.exists and self.use_cache:
             self.cache.unprotect(self.fs_path)
```

关键不是复杂状态机，而是：

- `no-cache` outputs 根本不应该触发 `cache.unprotect()`

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `true` | `1/1` | `66/66` | `205885` | `52` | `51` | `0` |
| `claude-code` | `true` | `1/1` | `66/66` | `299100` | `41` | `40` | `8` |

两边都完全 resolved。

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.15.0_3.15.1/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.15.0_3.15.1/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.15.0_3.15.1/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.15.0_3.15.1/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.15.0_3.15.1/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.15.0_3.15.1/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_3.15.0_3.15.1.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.15.0_3.15.1/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.15.0_3.15.1/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.15.0_3.15.1/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.15.0_3.15.1/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.15.0_3.15.1/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.15.0_3.15.1/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.15.0_3.15.1/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.15.0_3.15.1/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.15.0_3.15.1/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_3.15.0_3.15.1.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.15.0_3.15.1/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.15.0_3.15.1/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.15.0_3.15.1/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: exact failing-test scoping (`step 1-16`)

- 关键动作：
  - grep `test_repro_external_outputs`
  - 查 `unprotect` 在 tests 和源码中的出现位置
  - 读 `dvc/output.py`
- 阶段结论：
  - 很快把问题压到 `Output.unprotect()`

#### Phase B: guard selection (`step 8-35`)

- 关键动作：
  - 对照 `use_cache`、`changed_cache()`、external outputs 行为
  - 读 `dvc/stage/__init__.py`
- 阶段结论：
  - 认为只要 output 不在 cache 中，就不应 unprotect

#### Phase C: one-line fix (`step 36`)

- 修改文件：
  - `dvc/output.py`
- 修改内容：
  - `if self.exists` -> `if self.exists and not self.changed_cache()`

#### Phase D: sanity validation (`step 37-42`)

- 关键动作：
  - 回读 `changed_cache()` 定义
  - 跑少量相关 tests 与 `git diff`
- 阶段结论：
  - patch 与 benchmark 行为相容

### 5.2 claude-code

#### Phase A: narrow localization (`step 2-16`)

- 关键动作：
  - 读 target test
  - grep `unprotect`
  - 读 `dvc/output.py`
- 阶段结论：
  - 也很快定位到同一个函数

#### Phase B: explicit cache guard (`step 34-36`)

- 修改文件：
  - `dvc/output.py`
- 修改内容：
  - `if self.use_cache and self.hash_info and self.exists`

#### Phase C: lightweight validation (`step 37-41`)

- 关键动作：
  - `python -c "from dvc.output import Output"`
  - `git diff`
- 阶段结论：
  - patch 比 official 稍微更显式，但不影响语义

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `1-35` | 只有 cached output 才应该 unprotect；external no-cache output 不应该碰 cache 层 | target test、`unprotect` 调用点、`changed_cache()` | target test 就是外部 no-cache 输出复现 | 正确 |
| `claude-code` | `2-36` | `unprotect()` 需要在 cache/hash 存在时才调用 | target test、`use_cache` / `hash_info` 阅读 | 如果没有 cache/hash，调用 `self.cache.unprotect()` 没有意义 | 正确 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- patch：

```diff
-        if self.exists:
+        if self.exists and not self.changed_cache():
```

- 与官方差异：
  - 官方用 `self.use_cache`
  - innercc 用 `not self.changed_cache()`
- 评价：
  - 这不是字面一致，但在当前 case 上足以排除 no-cache external outputs

### 7.2 claude-code

- patch：

```diff
-        if self.exists:
+        if self.use_cache and self.hash_info and self.exists:
```

- 与官方差异：
  - 比官方 guard 更严格
- 评价：
  - 语义上仍然满足 benchmark 需要

## 8. Evaluation And Failure Evidence

这是一个双方都成功的 case。

- `innercc` 的 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.15.0_3.15.1/report.json) 显示：
  - `resolved = true`
  - `FAIL_TO_PASS = 1/1`
  - `PASS_TO_PASS = 66/66`
- `claude-code` 的 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.15.0_3.15.1/report.json) 完全一致。

## 9. Root Cause

- `direct_root_cause`
  - 这不是失败 case；成功的直接原因是两个 CLI 都把目标正确压缩成 `Output.unprotect()` 的 cache guard。
- `contributing_factors`
  - release note 与目标测试都高度聚焦。
  - patch 只需一个非常小的条件守卫。
- `non_root_but_misleading_signals`
  - workspace 里还有其他 `ImportError` / unrelated repro failures 噪声。
  - 但 target test 本身已经足够聚焦，没有把两边带偏。

## 10. CLI Optimization Opportunities

1. 这是“单函数 guard 修复”的正例。面对一个高聚焦 release note 和单条 func test，优先寻找最小 guard 比扩展到更大生命周期逻辑更稳。验证方式是看 patch 是否能收敛到单函数单条件。
2. 对成功正例也值得记录“语义等价而非字面一致”的现象。`innercc` 与 `claude-code` 都没完全按 official text 写 guard，但 evaluator 证明它们都命中了行为要求。这类案例适合用来避免把“与官方 patch 完全相同”误当成唯一成功标准。
