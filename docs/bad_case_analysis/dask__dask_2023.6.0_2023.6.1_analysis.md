# dask__dask_2023.6.0_2023.6.1 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `dask__dask_2023.6.0_2023.6.1`
- `repo`: `dask/dask`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed`
- 一句话结论：
  两边都把这个 case 过度缩小成 `dask/utils.py` 的 property/signature 兼容问题。`innercc` 甚至只用了 `2` 个 turns 就收工；`claude-code` 多做了一些验证，但最终也是一个 `dask/utils.py` 的 10 行级修复。结果是 `105` 条 F2P 全部没过，说明真实任务主体根本没被覆盖。
- 根因标签：
  - `task_understanding_error`
  - `hypothesis_lock_in`
  - `termination_error`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

release note包含：

- `fillna(method=...)` deprecation
- `first` / `last` deprecation
- `set_index(sort=False)`
- `header` in `read_csv`
- `GroupBy.var/std` with `dropna` / `observed`
- `bag.map total_mem_usage`
- rechunk validation

`FAIL_TO_PASS`: `105` 条。

代表性样例：

- `test_map_total_mem_usage`
- `test_header_int[2]`
- `test_pyarrow_conversion_dispatch[...]`

这很明显不是单点 bug，而是多子系统组合：

- bag
- dataframe IO
- dataframe core
- groupby
- warnings / compatibility

### 2.2 runner-level user query

两个 CLI 实际收到同一条包含大量 enhancement + bugfix 的 release-note prompt。

### 2.3 trace-level agent goals

- `innercc`
  - 几乎完全收缩成：
    - `_derived_from` / `get_named_args` 的 `TypeError` 兼容问题
  - 最终总结里也只讲这一点

- `claude-code`
  - 也集中在 `get_named_args` / `_derived_from`
  - 最终同样只提交了 `dask/utils.py` 的小修复

### 2.4 official golden answer

官方 patch 很大，至少涉及：

- `dask/dataframe/core.py`
- `dask/utils.py`
- `pyproject.toml`
- tests 侧对应 warning filter 和行为覆盖

尤其 release note 中明确提到：

- `fillna(method=...)` deprecation
- `first/last` deprecation
- `map_total_mem_usage`
- CSV header 行为

所以只修 `dask/utils.py` 注定覆盖不到主体。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `0/105` | `3327/3415` | `11734` | `2` | `122` | `1` |
| `claude-code` | `false` | `0/105` | `3415/3415` | `942648` | `75` | `74` | `3` |

其中 `innercc` 的一个异常信号是：

- `cli_duration_ms = 11734`
- `cli_num_turns = 2`

这说明它在极短时间内就收敛成了错误的小问题。

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/dask__dask_2023.6.0_2023.6.1/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/dask__dask_2023.6.0_2023.6.1/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/dask__dask_2023.6.0_2023.6.1/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/dask__dask_2023.6.0_2023.6.1/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 91 / Read 24 / Edit 7`
- 核心轨迹：
  - 很快定位到 `dask/utils.py`
  - 几乎没有展开其它 failing-test 家族
  - 最终 2 turns 就宣称完成

### 5.2 claude-code

- 工具分布：`Bash 44 / Grep 14 / Read 7 / Edit 4`
- 核心轨迹：
  - 花了更多步验证 `get_named_args` / `_derived_from`
  - 但仍然没有跳出这个局部兼容假设

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | 所有失败都能由 `_derived_from` / property introspection 解释 | 错，`105/105` F2P 全挂 |
| `claude-code` | 同一问题，只需更稳地改 `dask/utils.py` | 错，仍然 `0/105` |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

patch 主要就是：

```diff
-    except ValueError:
+    except (ValueError, TypeError):
```

### 7.2 claude-code

patch 比 `innercc` 稍宽：

- `get_named_args()` 对非 callable 直接返回空
- property 用 `.fget`
- `_derived_from` 更稳地处理 property

但本质上仍然是同一类小修补。

## 8. Evaluation And Failure Evidence

两边共同失败的关键不是某个单点 traceback，而是：

- `F2P = 0/105`
- 目标测试涉及 bag / csv / dataframe / groupby 多个子系统

也就是说，局部修复再“合理”，只要任务覆盖率为零，就不是正确解。

## 9. Root Cause

- `task_understanding_error`
  - 把大规模 release bundle 缩成单点兼容修复
- `termination_error`
  - 尤其是 `innercc`，在极少 turns 内就结束
- `hypothesis_lock_in`
  - 两边都被 `dask/utils.py` 这个局部问题锁住

## 10. CLI Optimization Opportunities

1. 若 `FAIL_TO_PASS > 50`，禁止在只改 1 个文件后直接结束。
2. 对极低 turn 数但极高任务规模的 case，触发“任务规模失配”告警。
3. 要求 agent 在早期输出 failing-test 家族映射，防止被单个显眼 traceback 绑架。
