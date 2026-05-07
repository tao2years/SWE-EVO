# iterative__dvc_2.58.1_2.58.2 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_2.58.1_2.58.2`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `inner_closer_but_both_failed`
- 一句话结论：
  官方修复点很窄：`dvc.reproduce(pull=True)` 在 `RunCacheNotSupported` 时要继续，但 `run_cache=False` 时根本不该去 pull run cache。`innercc` 修成了前一半，还额外把逻辑扩散到 `fetch()`；`claude-code` 则把异常处理放错到 `dvc/stage/run.py`，既没拦住前一条，也没满足后一条。
- 根因标签：
  - `localization_error`
  - `validation_gap`
  - `hypothesis_lock_in`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
## What's Changed
### Other Changes
* (2.x) repro: Continue on RunCacheNotSupported by @mergify in https://github.com/iterative/dvc/pull/9511
* (2.x) deps: bumps dvc-azure>=2.21.2 by @mergify in https://github.com/iterative/dvc/pull/9526
```

`FAIL_TO_PASS`:

- `tests/func/test_repro_multistage.py::test_repro_pulls_continue_without_run_cache`
- `tests/func/test_repro_multistage.py::test_repro_skip_pull_if_no_run_cache_is_passed`

`PASS_TO_PASS`: `20` 条。

这里有两个紧密相关但不同的语义：

1. `pull=True` 且默认 `run_cache=True` 时，如果 `stage_cache.pull()` 抛 `RunCacheNotSupported`，应记录 warning 后继续 reproduce
2. `pull=True, run_cache=False` 时，根本不应该调用 `stage_cache.pull()`

### 2.2 runner-level user query

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_2.58.1_2.58.2

Release note / requirement:
## What's Changed
### Other Changes
* (2.x) repro: Continue on RunCacheNotSupported by @mergify in https://github.com/iterative/dvc/pull/9511
* (2.x) deps: bumps dvc-azure>=2.21.2 by @mergify in https://github.com/iterative/dvc/pull/9526

Expected failing tests that should pass after your fix:
- tests/func/test_repro_multistage.py::test_repro_pulls_continue_without_run_cache
- tests/func/test_repro_multistage.py::test_repro_skip_pull_if_no_run_cache_is_passed
```

### 2.3 trace-level agent goals

- `innercc`
  - 比较快就盯住了 `dvc.repo.reproduce()` 里的 run cache pull
  - 但又顺手去改了 `dvc/repo/fetch.py`
- `claude-code`
  - 把任务收缩成 `dvc/stage/run.py` 里的 run cache restore 异常处理
  - 没回到真正的 `reproduce()` 入口

### 2.4 official golden answer

官方 patch 完全只改 `dvc/repo/reproduce.py`：

```diff
diff --git a/dvc/repo/reproduce.py b/dvc/repo/reproduce.py
@@
+from dvc.stage.cache import RunCacheNotSupported
@@
-    if kwargs.get("pull", False):
+    if kwargs.get("pull", False) and kwargs.get("run_cache", True):
         logger.debug("Pulling run cache")
-        self.stage_cache.pull(None)
+        try:
+            self.stage_cache.pull(None)
+        except RunCacheNotSupported as e:
+            logger.warning("Failed to pull run cache: %s", e)
```

关键点是：

- 既加 `run_cache` gate
- 又在同一位置吞 `RunCacheNotSupported`

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `1/2` | `20/20` | `159774` | `48` | `47` | `4` |
| `claude-code` | `false` | `0/2` | `20/20` | `1015628` | `50` | `49` | `17` |

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.58.1_2.58.2/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.58.1_2.58.2/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.58.1_2.58.2/cli_result.json)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.58.1_2.58.2/router_trace_bundle.json)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.58.1_2.58.2/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.58.1_2.58.2/test_output.txt)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.58.1_2.58.2/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.58.1_2.58.2/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.58.1_2.58.2/cli_result.json)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.58.1_2.58.2/router_trace_bundle.json)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.58.1_2.58.2/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.58.1_2.58.2/test_output.txt)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: correct entrypoint localization (`step 1-14`)

- 关键动作：
  - grep `RunCacheNotSupported`
  - 读 `tests/func/test_repro_multistage.py`
  - 读 `dvc/repo/reproduce.py`
- 阶段结论：
  - 正确定位到 `reproduce()` 在 pull run cache 这一段

#### Phase B: over-expansion (`step 14-37`)

- 修改文件：
  - `dvc/repo/reproduce.py`
  - `dvc/repo/fetch.py`
- 问题：
  - 官方只需要改 `reproduce.py`
  - 它额外把 `RunCacheNotSupported` 吞到了 `fetch.py`

#### Phase C: partial success (`step 30-37`)

- 成功：
  - `test_repro_pulls_continue_without_run_cache`
- 失败：
  - 仍然在 `run_cache=False` 时调用了 `stage_cache.pull()`

### 5.2 claude-code

#### Phase A: wrong-layer fixation (`step 2-20`)

- 关键动作：
  - 读 `dvc/stage/run.py`
  - 认为异常应在 restore stage cache 处处理
- 阶段结论：
  - 它把问题放到了 `run_stage()` 的 restore 逻辑，而不是 `reproduce()` 的 pre-run-cache pull

#### Phase B: patch on wrong function (`step 20-51`)

- 修改文件：
  - `dvc/stage/run.py`
- 结果：
  - `stage_cache.pull(None)` 依旧会在 `reproduce()` 顶层抛 `RunCacheNotSupported`
  - `run_cache=False` 时也依然会被调用

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `1-14` | 问题在 `reproduce()` 的 run cache pull | F2P tests、`reproduce.py` | 两条 tests 都围绕 `dvc.reproduce(pull=True)` | 正确 |
| `innercc` | `14-37` | `fetch()` 也应一起吞 `RunCacheNotSupported` | 相邻 cache 拉取语义 | 看起来像一致性增强 | 对 benchmark 来说多余，且没解决 `run_cache=False` gate |
| `claude-code` | `2-20` | 问题在 `run_stage()` restore 阶段 | `RunCacheNotFoundError` 相邻代码 | restore 路径也处理 cache 相关异常 | 错，目标异常在 `reproduce()` 入口更早发生 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- `dvc/repo/reproduce.py`
  - 命中了官方的一半：
    - `try/except RunCacheNotSupported`
  - 漏掉：
    - `and kwargs.get("run_cache", True)` 这一 gate
- `dvc/repo/fetch.py`
  - 额外无关扩散

### 7.2 claude-code

- `dvc/stage/run.py`
  - 看起来合理，但完全不是官方 patch 命中的函数
- 结果：
  - 两条 F2P 都没被挡住

## 8. Evaluation And Failure Evidence

来自 [innercc test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.58.1_2.58.2/test_output.txt)：

```text
assert dvc.reproduce(pull=True, run_cache=False)
>       assert not spy_pull.called
E       assert not True
```

说明 `run_cache=False` gate 仍缺失。

来自 [claude-code test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.58.1_2.58.2/test_output.txt)：

```text
E   dvc.stage.cache.RunCacheNotSupported: foo
```

说明顶层 `stage_cache.pull(None)` 仍未被捕获。

## 9. Root Cause

- `direct_root_cause`
  - `innercc` 少了 `run_cache=False` 这个关键条件。
  - `claude-code` 修错层，把异常处理放到了 `run_stage()` 而不是 `reproduce()`.
- `contributing_factors`
  - 两边都没有用两条 F2P 的差异去约束 patch：
    - 一条测 “continue”
    - 一条测 “skip”
- `non_root_but_misleading_signals`
  - `RunCacheNotSupported` 在多个层出现，很容易让人修到相邻位置。

## 10. CLI Optimization Opportunities

1. 对一组共享异常类型但验证不同语义的 tests，必须显式列出每条 test 各自验证的行为。这里就是 “continue” vs “skip”。验证方式是计划里写出每个 F2P 的 expected behavior，而不是只写异常名。
2. 当官方 patch 只有一个文件时，优先证明为什么需要扩散到第二个文件；否则默认不扩散。可减少 `innercc` 这种看似一致、实则无关的补丁外溢。
