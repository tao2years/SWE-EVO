# pydantic__pydantic_v2.7.1_v2.7.2 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `pydantic__pydantic_v2.7.1_v2.7.2`
- `repo`: `pydantic/pydantic`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_same_misread`
- 一句话结论：
  这是一个非常典型的“被 release note 中单条修复误导”的失败案例。benchmark 真正关心的 `3` 条 F2P 都在 docs examples / generics / schema 行为上，但两个 CLI 都被 `TypeVar.__default__ == NoDefault` 这个 Python 3.12 兼容点锁死，结果都改成了 `_generate_schema.py` + `pyproject.toml`，而对真实 F2P 几乎零覆盖，最终还把数千条 P2P 一并打挂。
- 根因标签：
  - `task_understanding_error`
  - `hypothesis_lock_in`
  - `termination_error`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement` 的显眼修复项包括：

- `Replace __spec__.parent with __package__`
- `Fix validation of ints with leading unary minus`
- `Fix str subclass validation for enums`
- `Support BigInts in Literals and Enums`
- `Fix: uuid - allow str subclass as input`

但 benchmark `FAIL_TO_PASS` 实际是：

- `tests/test_docs.py::test_docs_examples[docs/concepts/models.md:1049-1079]`
- `tests/test_docs.py::test_docs_examples[docs/concepts/models.md:952-982]`
- `tests/test_generics.py::test_serialize_unsubstituted_typevars_bound_default_supported`

`PASS_TO_PASS`: `4584` 条。

关键点：

- release note 很长
- F2P 只有 `3` 条，但其中 2 条是 docs examples，1 条是 generics
- 如果 agent只盯 release note 中“看起来像 Python 3.12 兼容”的 `TypeVar` 条目，会直接偏航

### 2.2 runner-level user query

CLI 收到的是一条长 release-note prompt，但 F2P 清单其实非常窄，应该优先围绕 docs examples 与 generics 这 `3` 条测试倒推。

### 2.3 trace-level agent goals

- `innercc`
  - 核心假设迅速锁在：
    - `typing_extensions.TypeVar.__default__` 在 Python 3.12 下返回 `NoDefault`
    - `_generate_schema.py` 的 default/bound/constraints 冲突判断有问题

- `claude-code`
  - 和 `innercc` 几乎同一方向：
    - 认为主问题就是 `NoDefault`
    - 还顺手 bump 了 `pydantic-core==2.18.3`

这两条内部 goal 都和真实 F2P 只有非常弱的对应关系。

### 2.4 official golden answer

从两边 patch 可以看出它们都锁在：

- `pydantic/_internal/_generate_schema.py`
- `pyproject.toml`

但 benchmark F2P 包含：

- docs examples
- generics serialization

说明官方 gold spec 至少不止这一条 `_generate_schema` 小修复，或者说这条修复并不是 benchmark 唯一关键路径。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `0/3` | `403/4584` | `163879` | `36` | `35` | `0` |
| `claude-code` | `false` | `0/3` | `403/4584` | `457197` | `48` | `47` | `1` |

两边表现几乎一致：

- `F2P = 0/3`
- `P2P = 403/4584`

说明不是谁 patch 更好，而是两边都在错误问题上“稳定地收敛”了。

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/pydantic__pydantic_v2.7.1_v2.7.2/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/pydantic__pydantic_v2.7.1_v2.7.2/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/pydantic__pydantic_v2.7.1_v2.7.2/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/pydantic__pydantic_v2.7.1_v2.7.2/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 26 / Read 7 / Edit 2`
- 关键轨迹：
  - 很快得出 “`TypeVar.__default__` 在 Python 3.12 里是 `NoDefault` 而非 `None`”
  - 直接修改 `_generate_schema.py`
  - 再更新 `pyproject.toml` 里的 `pydantic-core`
- 说明：
  - 它几乎没有回到 F2P 的 docs examples / generics 上做聚类验证

### 5.2 claude-code

- 工具分布：`Bash 23 / Grep 11 / Glob 5 / Read 5 / Edit 3`
- 关键轨迹：
  - 同样很快锁定 `NoDefault`
  - 最终总结也完全围绕 `TypeVar` 这条修复
- 和 `innercc` 的差异：
  - 只是探索更长、验证更多
  - 但根本假设没有变

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | F2P 失败由 `TypeVar.__default__` / `NoDefault` 逻辑引起 | 错，`F2P = 0/3` |
| `claude-code` | 主问题是 Python 3.12 下 `NoDefault` sentinel 判断 | 同样错，`F2P = 0/3` |

## 7. Patch And Code-Level Analysis

两边 patch 几乎同构：

- 导入 `NoDefault`
- 修改 `_generate_schema.py` 中：
  - `default is not None`
  - -> `default not in (None, NoDefault)` 或 `has_default`
- `claude-code` 还 bump 了 `pydantic-core==2.18.3`

问题不在 patch 细节，而在 patch 目标和 benchmark 目标不匹配。

## 8. Evaluation And Failure Evidence

决定性证据不是某一条 traceback，而是整体失配：

- benchmark F2P 是 docs examples / generics
- 两边 patch 却都只改了 `_generate_schema.py`

最终结果：

- `F2P success = []`
- `P2P failure = 4181`

这说明：

- 任务方向错了
- patch 甚至引入了大规模额外破坏

## 9. Root Cause

- `task_understanding_error`
  - 被 release note 中单条显眼修复牵着走，没有按 F2P 真实分布组织任务
- `hypothesis_lock_in`
  - 一旦接受 `NoDefault` 解释，后续所有动作都只在这条线上迭代
- `termination_error`
  - 在 `0/3` F2P 的情况下仍结束

## 10. CLI Optimization Opportunities

1. 对 “release note 很长但 F2P 很少” 的 case，必须先以 F2P 为主、release note 为辅。
2. 如果 patch 只覆盖 1 个小修复点，但 benchmark P2P 规模巨大，必须触发 coverage mismatch 警报。
3. docs examples / generics 这类 F2P 需要直接定位到对应 test file 和 failing assertion，而不是只追 release note。
