# dask__dask_2022.9.2_2022.10.0 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `dask__dask_2022.9.2_2022.10.0`
- `repo`: `dask/dask`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_inner_closer`
- 一句话结论：
  这是一个中大型 release bundle case。`innercc` 虽然也失败，但至少修到 `13/44` F2P，覆盖了 `array copy noop`、部分 `groupby median`、`datetime.time tokenization` 等多条线；`claude-code` 只修到 `1/44`，主要锁在较小的 datetime tokenization / array copy / setitem 兼容点上，任务覆盖率明显更低。
- 根因标签：
  - `task_understanding_error`
  - `validation_gap`
  - `hypothesis_lock_in`

## 2. Task And Gold Spec

### 2.1 benchmark task

release note 同时包含：

- array/dataframe backend dispatch
- new CLI
- groupby median
- array copy no-op
- string timedelta in map_overlap
- tokenize datetime/time
- setitem `np.nan` to int
- CSV/demo projection fixes

`FAIL_TO_PASS`: `44` 条。

它不是一个单 bug，而是多条 enhancement + bugfix 的聚合。

### 2.2 runner-level user query

CLI 收到的 prompt 是同一条 release-note 聚合任务，要求通过 `44` 条 F2P。

### 2.3 trace-level agent goals

- `innercc`
  - 先后关注：
    - array copy no-op
    - setitem `np.nan` to int
    - CSV projection
    - index repr
    - groupby median
    - datetime/time tokenization
  - 至少形成了多子任务视角

- `claude-code`
  - 总结里主要只提：
    - datetime tokenization
    - array copy
    - float->int setitem
  - 覆盖面明显更窄

### 2.4 official golden answer

官方 patch 是大规模多文件改动。就从两边 patch 对比看：

- `innercc` 至少命中了：
  - `Array.copy()` no-op
  - `normalize_token(datetime.*)`
  - pandas manager API 兼容
  - dataframe/accessor/compat 多处更新
- `claude-code` 只在：
  - `array/core.py`
  - `base.py`
  - 少量 numpy/pandas 兼容点

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `13/44` | `2311/2861` | `1949384` | `370` | `516` | `14` |
| `claude-code` | `false` | `1/44` | `2859/2861` | `807157` | `72` | `71` | `4` |

`innercc` 覆盖面更大，但回归也更大；`claude-code` 更保守，但几乎没修到任务主体。

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/dask__dask_2022.9.2_2022.10.0/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/dask__dask_2022.9.2_2022.10.0/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/dask__dask_2022.9.2_2022.10.0/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/dask__dask_2022.9.2_2022.10.0/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 290 / Read 154 / Edit 72`
- 关键迹象：
  - trace 中明确提到 `CSV column projection`、`index repr`、`groupby median`、`array copy`
  - 甚至出现“我是否需要改测试”的犹豫，说明任务面过大、边界不稳

### 5.2 claude-code

- 工具分布：`Grep 31 / Bash 18 / Read 12 / Edit 4`
- 关键迹象：
  - 它主要围绕 array/core 局部兼容与 datetime tokenization 展开
  - 最终总结也只覆盖少数点

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | 这是多子任务 bundle，需要逐条补行为 | 修到一些，但改动过宽、回归较多 |
| `claude-code` | 修几个显眼的小兼容点即可 | 覆盖率严重不足 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- patch 广泛涉及 `array/core`, `base`, `dataframe/_compat`, `accessor`, `pyarrow compat` 等
- 这解释了为什么它能拿到 `13` 条 F2P
- 也解释了为什么会有 `550` 条 P2P 回归：改面过大、验证不稳

### 7.2 claude-code

- patch 主要落在：
  - `dask/array/core.py`
  - `dask/base.py`
- 对 bundle 主体覆盖太小

## 8. Evaluation And Failure Evidence

- `innercc` 修成样例：
  - `test_array_copy_noop[-1]`
  - 多条 `groupby median` 相关测试
- `claude-code` 唯一明显修成样例：
  - `test_tokenize_datetime_time`

这说明 `claude-code` 没能把 release-note 里的多条子任务展开。

## 9. Root Cause

- `innercc`
  - 主要问题是改面过大但验证不足
- `claude-code`
  - 主要问题是任务覆盖率太低

## 10. CLI Optimization Opportunities

1. 对 40+ F2P 的 case，必须先做 failing-test 聚类。
2. 若 patch 覆盖少数文件且 F2P 覆盖率极低，禁止结束。
3. 若 patch 覆盖率高但 P2P 回归暴增，也必须回退到更细粒度子任务验证。
