# dask__dask_2024.1.0_2024.1.1 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `dask__dask_2024.1.0_2024.1.1`
- `repo`: `dask/dask`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed`
- 一句话结论：
  这是一个超大规模 compatibility release case：官方 patch 63 万字符、`FAIL_TO_PASS = 2774`、`PASS_TO_PASS = 5778`。两边 CLI 都把任务极度缩小成了单个兼容症状修复，`innercc` 锁在 `dask/utils.py` 的 `inspect.signature/property` 问题，`claude-code` 锁在 `dtype.type()` 的 NumPy 2.0 兼容问题；两者都没有覆盖 benchmark 的主体变更，因此最终 `F2P = 0`、`P2P = 0`。
- 根因标签：
  - `task_understanding_error`
  - `hypothesis_lock_in`
  - `termination_error`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement` 的 relevant 部分：

```text
2024.1.1
--------

Released on January 26, 2024

Highlights
^^^^^^^^^^

Pandas 2.2 and Scipy 1.12 support
"""""""""""""""""""""""""""""""""
This release contains compatibility updates for the latest ``pandas`` and ``scipy`` releases.

...
  - Implement deterministic tokenization for hlg (:pr:`10817`)
  - Adjust tests for ``median`` support in ``dask-expr`` (:pr:`10839`)
  - Adjust tests for ``median`` support in ``groupby-aggregate`` in ``dask-expr`` (:pr:`10840`)
  - ``numpy`` 2.x: fix ``std()`` on ``MaskedArray`` (:pr:`10837`)
  - Activate ``query_planning`` when exporting tests (:pr:`10833`)
  - Expose dataframe tests (:pr:`10830`)
  - ``numpy`` 2: deprecations in n-dimensional ``fft`` functions (:pr:`10821`)
  - Generalize ``CreationDispatch`` for ``dask-expr`` (:pr:`10794`)
  - Remove circular import when ``dask-expr`` enabled (:pr:`10824`)
```

`FAIL_TO_PASS`: `2774` 条。

`PASS_TO_PASS`: `5778` 条。

这个 case 不像前面的小范围 bugfix。它本质上是一个“整包 compatibility + query-planning 调整”的大版本补丁集，被压缩成了一个 benchmark instance。任何把它理解成“修一个点”都会系统性失败。

### 2.2 runner-level user query

两个 CLI 实际收到的 prompt 为：

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: dask__dask_2024.1.0_2024.1.1

Release note / requirement:
2024.1.1
--------

Released on January 26, 2024

Highlights
^^^^^^^^^^

Pandas 2.2 and Scipy 1.12 support
"""""""""""""""""""""""""""""""""
This release contains compatibility updates for the latest ``pandas`` and ``scipy`` releases.

...

Expected failing tests that should pass after your fix:
- ... 共 2774 条

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

这个 prompt 的困难在于：

- 用户 query 里只给了 release notes 摘要
- 但 failing tests 数量极大，跨多个子系统
- 如果 agent 不先评估“任务规模异常大”，就会自然收缩到最显眼的一两个症状

### 2.3 trace-level agent goals

两个 CLI 都没有把任务识别成“大规模多子系统补丁”，而是快速收敛到了单点兼容假设。

- `innercc`
  - 内部目标最终变成：
    - 修 `dask/utils.py` 里 `derived_from` / `inspect.signature` 与 pandas property 的兼容问题
  - 这最多只能解释一类 import / accessor 失败

- `claude-code`
  - 内部目标最终变成：
    - 修 NumPy 2.0 下 `dtype.type()` 的弃用问题
  - 这最多只覆盖 array routines / dtype compatibility 的一个角落

两边都没有形成：

- “这是 2774 failing tests 的大规模回归包”
- “必须先按 failing tests 聚类”
- “需要明确主子系统清单再下手”

### 2.4 official golden answer

官方 patch 极其庞大：

- `patch_len = 630071`
- `test_patch_len = 206369`

而且前几个核心 diff 就已经跨了多个方向：

1. CI / dependency pinning
2. `dask-expr` 相关测试与行为调整
3. pandas/scipy/numpy 兼容修复
4. accessor / dataframe / array / IO / merge 等多个子系统联动

也就是说，这题的官方 gold spec 不是一个“单修复点”，而是一个整包回归修复集合。

这也是为什么：

- 只改 `dask/utils.py`
- 或只改 `dtype.type()`

都不可能让 `2774` 条 F2P 通过。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count | patch_apply |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `innercc` | `false` | `0/2774` | `0/5778` | `221479` | `42` | `41` | `4` | `true` |
| `claude-code` | `false` | `0/2774` | `0/5778` | `828763` | `122` | `147` | `21` | `true` |

这是一个极端 case：

- 两边都没有通过任何 F2P
- 两边都把全部 `PASS_TO_PASS` 打挂

这里的重点不是“patch 是否应用成功”，而是：

- patch 面相对官方任务规模几乎可以忽略
- 所以 evaluator 结果必然是整体性失败

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/dask__dask_2024.1.0_2024.1.1/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/dask__dask_2024.1.0_2024.1.1/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/dask__dask_2024.1.0_2024.1.1/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/dask__dask_2024.1.0_2024.1.1/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/dask__dask_2024.1.0_2024.1.1/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/dask__dask_2024.1.0_2024.1.1/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/dask__dask_2024.1.0_2024.1.1.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/dask__dask_2024.1.0_2024.1.1/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/dask__dask_2024.1.0_2024.1.1/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/dask__dask_2024.1.0_2024.1.1/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/dask__dask_2024.1.0_2024.1.1/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/dask__dask_2024.1.0_2024.1.1/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/dask__dask_2024.1.0_2024.1.1/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/dask__dask_2024.1.0_2024.1.1/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/dask__dask_2024.1.0_2024.1.1/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/dask__dask_2024.1.0_2024.1.1/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/dask__dask_2024.1.0_2024.1.1.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/dask__dask_2024.1.0_2024.1.1/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/dask__dask_2024.1.0_2024.1.1/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/dask__dask_2024.1.0_2024.1.1/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: bootstrap + immediate symptom focus (`step 1-10`)

- 关键动作：
  - 看 numpy / pandas / Python 版本
  - 跑局部 pytest
  - 读 `dask/utils.py`
- 阶段结论：
  - 很快把注意力集中到 `derived_from` / `inspect.signature` / pandas property 的兼容问题

#### Phase B: hypothesis testing on single compatibility issue (`step 11-24`)

- 关键动作：
  - 多次手写 Python probe，围绕 `inspect.signature` 与 property 对象
  - 读 `dask/dataframe/accessor.py`
- 阶段结论：
  - 形成假设：
    - `derived_from` 在 Python 3.12 / pandas accessor property 上抛 `TypeError`

#### Phase C: single-file edit (`step 25`)

- 关键动作：
  - 只编辑 `dask/utils.py`
- patch 内容：
  - 把
    - `except ValueError`
  - 改成
    - `except (ValueError, TypeError)`

#### Phase D: narrow validation (`step 26-39`)

- 关键动作：
  - 跑 `test_array_core.py` 等局部测试
  - 看 `git diff`
- 阶段结论：
  - “这个 compatibility fix works”

问题在于：

- 它没有重新回到“2774 failing tests 的大 case”这个事实
- 局部验证成功并不意味着 benchmark 主体被覆盖

### 5.2 claude-code

#### Phase A: bootstrap + premature issue narrowing (`step 1-20`)

- 关键动作：
  - 看 numpy / pandas / scipy 版本
  - 跑局部 pytest
  - 搜 `dtype.type()`
  - 读 `dask/utils.py`、`dask/dataframe/accessor.py`
- 阶段结论：
  - 很早就把问题归结为 NumPy 2.0 deprecation

#### Phase B: long hypothesis lock-in loop (`step 21-88`)

- 关键动作：
  - 大量 grep / local probe
  - 反复比较 `dtype.type()`, `result_type`, `uint64 slicing`
  - 扩展到 `numpy_compat.py`, `routines.py`, `einsumfuncs.py`
- 阶段结论：
  - 最终核心假设锁在：
    - `dtype.type()` deprecated 是主问题

#### Phase C: multi-file tiny-compat edits (`step 89-145`)

- 关键动作：
  - 编辑 `numpy_compat.py`
  - 编辑 `routines.py`
  - 尝试编辑 `einsumfuncs.py`
- 问题：
  - 虽然改了比 `innercc` 更多的文件
  - 但依然都围绕同一个小兼容假设

#### Phase D: termination (`step 146-148`)

- 关键动作：
  - 看 `git status` / `git diff`
  - 输出“minimal code-only fix is complete”

和 `innercc` 一样，核心问题不是 patch 语法错误，而是：

- 任务规模判断失败
- 局部症状修复被误当成 benchmark 全局修复

## 6. Hypothesis Iteration Log

### 6.1 innercc

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `1-10` | 问题是 `dask/utils.py` 中 `derived_from` 与 pandas property / `inspect.signature` 的兼容 | local pytest + accessor code + local Python probe | 它确实能解释一部分 import / accessor 失败 | 只对一个局部症状成立，不足以覆盖 benchmark 主体 |
| `25-39` | 把 `TypeError` 加进 except 即可结束 | single-file patch + local tests | 局部测试通过，形成了“问题已解决”的错觉 | 错，因为 benchmark 是 2774/5778 量级的大回归包 |

### 6.2 claude-code

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `1-20` | 主问题是 NumPy 2.0 / `dtype.type()` deprecation | release note 中 `numpy 2.x` 相关词 + local probes | 从 release notes 和局部 probe 看，这是显眼兼容点 | 只覆盖极小子集 |
| `21-88` | 只要把 `.dtype.type()` 的兼容层修好，主问题就会收敛 | 大量 dtype / `result_type` / `uint64` probe | 局部实验不断强化这一点 | 错，因为 benchmark 远超这一条兼容线 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc patch

`innercc` 的 patch 非常小：

```diff
-    except ValueError:
+    except (ValueError, TypeError):
```

它修的是一个局部异常分支，对一个大规模 compatibility release 来说远远不够。

### 7.2 claude-code patch

`claude-code` 的 patch 稍大一些，但仍然是“小兼容点集合”：

- `numpy_compat.py`
- `routines.py`

核心思想是把某些 `dtype.type()` 路径换成 `result_type` 或 helper。但 benchmark 主体远不止这些，所以从任务覆盖率上看仍然远远不足。

## 8. Evaluation And Failure Evidence

### 8.1 结果层证据

两边结果完全一致：

- `F2P = 0/2774`
- `P2P = 0/5778`

这说明不是“差一点”，而是两边都没有真正进入 benchmark 所需的修复面。

### 8.2 root failure pattern

这个 case 的关键证据不在某一条单独 traceback，而在整体规模失配：

- official patch: `630071` 字符
- official test patch: `206369` 字符
- 两边 agent patch:
  - `innercc`: 只改 1 个文件
  - `claude-code`: 只改 2-3 个局部兼容文件

也就是说，patch 覆盖面和 benchmark 需要覆盖的变更面根本不在一个数量级。

### 8.3 misleading evidence

两边 trace 里都有局部验证通过的迹象：

- `innercc` 在 `test_array_core.py` 上局部通过
- `claude-code` 在 dtype / deprecation 小实验上自洽

但这些都只是“局部 symptom fixed”，不是 benchmark 级修复。

## 9. Root Cause

### 9.1 direct root cause

- `task_understanding_error`
  - 两边都没有识别出这是一个“大规模多子系统 compatibility bundle”
  - 都把它收缩成了单个显眼症状

### 9.2 contributing factors

- `hypothesis_lock_in`
  - `innercc` 锁在 `derived_from/property`
  - `claude-code` 锁在 `dtype.type()` deprecation

- `termination_error`
  - 在局部修复看起来成立后，直接结束，没有回到 benchmark 全局规模检查

- `validation_gap`
  - 没有把“修复覆盖了多少 failing test 家族”作为结束条件

### 9.3 non-root but misleading signals

- release notes 本身列了很多 numpy/pandas/scipy compatibility 词条，容易诱导 agent 追一个最熟悉的兼容点
- 局部 pytest / local probe 成功，会进一步放大这种误判

## 10. CLI Optimization Opportunities

### 10.1 case-specific actions

1. 当 `FAIL_TO_PASS` 数量达到异常规模时，首先做任务规模判断，而不是立刻修第一个症状。
2. 如果 official patch / test patch 体量远大于 agent patch，必须触发“覆盖率不足”警报。

### 10.2 generalizable actions

1. 增加 `large-bundle-case` 检测
   - 例如 `FAIL_TO_PASS > 100` 或 official patch 超过某阈值时
   - 强制先做 failing tests 聚类
2. 增加“修复覆盖率”结束条件
   - 不能因为某个局部兼容点修通就结束
3. 增加 benchmark 规模感知
   - release note + failing tests 数量 + official patch 体量应共同影响策略

### 10.3 validation plan for the optimization

1. 回放此 case，要求 agent 在前 20 步先输出 failing test 聚类和子系统清单。
2. 若 patch 仅覆盖单文件或少量局部兼容点，而 benchmark 是千级 F2P，禁止结束。
3. 观察 agent 是否还会被第一个显眼 compatibility symptom 锁死。
