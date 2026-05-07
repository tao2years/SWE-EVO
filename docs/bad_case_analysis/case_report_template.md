# Case Report Template

把 `<instance_id>` 替换成真实 case id，并按下面结构填写。

```md
# <instance_id> Analysis

本文遵循 [bad_case_analysis_design.md](./bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `<instance_id>`
- `repo`: `<repo>`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `<category>`
- 一句话结论：
  <一句完整结论，不要空泛>
- 根因标签：
  - `<tag_1>`
  - `<tag_2>`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
<原始 problem_statement>
```

`FAIL_TO_PASS`:

- `<failing_test_1>`
- `<failing_test_2>`

`PASS_TO_PASS`: `<数量>` 条

### 2.2 runner-level user query

```text
<build_prompt() 还原后的完整 prompt>
```

### 2.3 trace-level agent goals

- `innercc`
  - <内部任务重写>
- `claude-code`
  - <内部任务重写>

### 2.4 official golden answer

<官方 golden patch 关键 hunk 与解释>

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| `claude-code` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |

## 4. Artifact Index

### innercc

- [patch.diff](...)
- [preds.json](...)
- [cli_result.json](...)
- [router_trace_bundle.json](...)
- [report.json](...)
- [test_output.txt](...)

### claude-code

- [patch.diff](...)
- [preds.json](...)
- [cli_result.json](...)
- [router_trace_bundle.json](...)
- [report.json](...)
- [test_output.txt](...)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: <phase name>

- 工具分布：`...`
- 关键动作：
  - ...
- 阶段结论：
  - ...

### 5.2 claude-code

#### Phase A: <phase name>

- 工具分布：`...`
- 关键动作：
  - ...
- 阶段结论：
  - ...

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | <...> | <...> |
| `claude-code` | <...> | <...> |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

<patch 落点、层级、风险>

### 7.2 claude-code

<patch 落点、层级、风险>

## 8. Evaluation And Failure Evidence

<最关键的 traceback / failed assertion / F2P/P2P 证据>

## 9. Root Cause

- `direct_root_cause`
  - <...>
- `contributing_factors`
  - <...>
- `misleading_signals`
  - <...>

## 10. CLI Optimization Opportunities

1. <局部或通用优化建议>
2. <如何验证它是否有效>
```
