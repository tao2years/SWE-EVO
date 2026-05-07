# pydantic__pydantic_v2.6.0b1_v2.6.0 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `pydantic__pydantic_v2.6.0b1_v2.6.0`
- `repo`: `pydantic/pydantic`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_same_target_different_fix`
- 一句话结论：
  这题只有 `1` 条 F2P，但两个 CLI 仍然都没修到。目标测试要的是 JSON schema 中 discriminator mapping 的保留；`innercc` 锁在 `_extract_discriminator()` 的 `break -> continue`，`claude-code` 锁在 `generate_definitions()` 的 `$defs` garbage collection 顺序。两边都只抓到了表面机制，没有修到实际丢失 discriminator 的真正路径。
- 根因标签：
  - `localization_error`
  - `hypothesis_lock_in`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`FAIL_TO_PASS`: `1` 条。

- `tests/test_discriminated_union.py::test_presence_of_discriminator_when_generating_type_adaptor_json_schema_definitions`

`PASS_TO_PASS`: `51` 条。

这题是标准单目标 schema-generation case。

### 2.2 runner-level user query

CLI 收到的 prompt 非常简单，但真实要求是：

- 在生成 `TypeAdapter` JSON schema definitions 时，保留 `discriminator.mapping/propertyName`

### 2.3 trace-level agent goals

- `innercc`
  - 锁在 `_extract_discriminator()` 里：
    - 认为遇到非 list alias path 时不该 `break`

- `claude-code`
  - 锁在 `generate_definitions()` 的 `$defs` garbage collection：
    - 认为 discriminator refs 在 GC 顺序里被清掉了

### 2.4 official golden answer

从失败断言看，golden 关键在于：

- `CreateObjectDto.items.items.discriminator`
  - `mapping: {'item1': '#/$defs/CreateItem1', 'item2': '#/$defs/CreateItem2'}`
  - `propertyName: 'type'`

两边 patch 都没有真正恢复这整个 discriminator 结构。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `0/1` | `51/51` | `16860` | `3` | `133` | `11` |
| `claude-code` | `false` | `0/1` | `51/51` | `1226745` | `79` | `78` | `5` |

一个有意思的点：

- `innercc` 只用 `3` turns 就收工，但工具调用很多
- `claude-code` 花了很久，仍然没修成

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/pydantic__pydantic_v2.6.0b1_v2.6.0/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/pydantic__pydantic_v2.6.0b1_v2.6.0/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/pydantic__pydantic_v2.6.0b1_v2.6.0/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/pydantic__pydantic_v2.6.0b1_v2.6.0/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 104 / Read 28 / Edit 1`
- 核心假设：
  - `_extract_discriminator` 在遍历 `schema['discriminator']` 时，遇到非 list 就 `break`，导致后续合法 alias path 没被处理
- 特征：
  - 极快收敛到一个非常具体的点
  - 但没有充分反证

### 5.2 claude-code

- 工具分布：`Grep 38 / Read 19 / Bash 13 / Edit 3`
- 核心假设：
  - discriminator 定义在 `$defs` GC 阶段被错误清理
- 特征：
  - 走得更深，但一直围绕 definitions generation / garbage collection 打转

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | `_extract_discriminator` 的 `break` 提前中断了 alias path 解析 | 未修成 |
| `claude-code` | `$defs` GC 顺序吞掉了 discriminator refs | 也未修成 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

```diff
-                    break
+                    continue
```

这是一个很典型的“局部控制流修复”，但过于狭窄。

### 7.2 claude-code

主要改动：

- `json_schema.py`
  - 在 definitions 生成后做 `_garbage_collect_definitions`

它抓到了另一个可能的机制，但同样没有命中最终行为。

## 8. Evaluation And Failure Evidence

关键失败断言直接展示了缺的是什么：

```text
... 'items': {'oneOf': [...]}
!=
... 'items': {'discriminator': {'mapping': {...}, 'propertyName': 'type'}, 'oneOf': [...]}
```

也就是说，真正缺的是完整 discriminator schema 结构，而不是单个 alias path 或单个 GC 调用顺序本身。

## 9. Root Cause

- `localization_error`
  - 两边都定位到“可能相关的一层”，但都没抓到真正负责把 discriminator 写回 schema 的完整路径
- `hypothesis_lock_in`
  - 一个锁在 alias path 控制流
  - 一个锁在 `$defs` GC 顺序

## 10. CLI Optimization Opportunities

1. 对 JSON schema 生成类问题，应该直接以失败断言里的目标结构为锚，而不是只修内部推测机制。
2. 如果断言缺的是完整字段结构，就要逆向追踪“谁负责写这个字段”，而不是先改中间控制流。
