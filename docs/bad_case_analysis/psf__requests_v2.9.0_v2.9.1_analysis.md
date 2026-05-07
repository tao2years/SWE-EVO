# psf__requests_v2.9.0_v2.9.1 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `psf__requests_v2.9.0_v2.9.1`
- `repo`: `psf/requests`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_partial_same_fix_same_regression`
- 一句话结论：
  两个 CLI 都准确修到了 release note 的两个显式 bugfix：binary body in Python 3 和 cookie expiration locale；但两边都犯了同一个副作用错误，把 `_encode_params()` 对所有 `str/bytes` 都直接返回原值，破坏了参数编码路径，因此共同引入了 `test_params_bytes_are_encoded` 这 1 条 P2P 回归。
- 根因标签：
  - `overgeneralized_fix`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

- resolve regression that made it impossible to send binary strings as bodies in Python 3
- fix cookie expiration dates in certain locales

`FAIL_TO_PASS`: `1` 条。

- `test_requests.py::TestRequests::test_binary_put`

`PASS_TO_PASS`: `85` 条。

### 2.2 runner-level user query

CLI 收到的是一个“小型双子任务” prompt，但 benchmark 实际只把 `test_binary_put` 放进 F2P。

### 2.3 trace-level agent goals

两个 CLI 都采取了相同策略：

1. 先修 `_encode_params()` 里 bytes body 问题
2. 再顺手修 `cookies.py` 的 locale 解析问题

这一步本身没错，但它们都忽略了：

- `_encode_params()` 同时还服务于 query params 编码

### 2.4 official golden answer

从 patch 形状看，golden 修复至少应区分两种路径：

- request body bytes
- params bytes encoding

而两边的 patch 实际把这两者混为一谈：

```diff
-            return to_native_string(data)
+            return data
```

这修好了 binary body，但也破坏了 params 编码。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `1/1` | `84/85` | `209726` | `39` | `38` | `3` |
| `claude-code` | `false` | `1/1` | `84/85` | `342940` | `43` | `43` | `5` |

两边都属于：

- 目标 F2P 修到了
- 但都引入了完全相同的 1 条 P2P 回归

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/psf__requests_v2.9.0_v2.9.1/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/psf__requests_v2.9.0_v2.9.1/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/psf__requests_v2.9.0_v2.9.1/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/psf__requests_v2.9.0_v2.9.1/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 19 / Read 13 / Edit 6`
- 核心假设：
  - `_encode_params` 中 `to_native_string(data)` 会把 bytes body 错误地 decode
  - cookie expires 需要临时切到 `LC_TIME=C`

### 5.2 claude-code

- 工具分布：`Grep 16 / Bash 12 / Read 9 / Edit 3`
- 核心假设：
  - 和 `innercc` 一样，先修 binary body，再顺手修 cookie locale

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | body bytes 和 params bytes 可用同一修复 | 错，导致 P2P 回归 |
| `claude-code` | 同样把 body / params 视为同一通路 | 同样错 |

## 7. Patch And Code-Level Analysis

两边 patch 几乎同构：

- `requests/models.py`
  - `if isinstance(data, (str, bytes)): return data`
- `requests/cookies.py`
  - locale 切到 `C` 再解析 `expires`

问题出在 `requests/models.py`：

- 这行修复对于 body bytes 是对的
- 但对于 params bytes 编码路径就过宽了

## 8. Evaluation And Failure Evidence

两边的共同 P2P 回归都是：

- `test_requests.py::TestRequests::test_params_bytes_are_encoded`

关键失败片段：

```text
TypeError: Cannot mix str and non-str arguments
```

这直接说明：

- body bytes 修好了
- params bytes 编码坏了

## 9. Root Cause

- `overgeneralized_fix`
  - 把 “binary body should remain bytes” 过度泛化成 “所有 str/bytes 输入都原样返回”
- `validation_gap`
  - 修完 F2P 后，没有检查 params 编码路径对应的回归测试

## 10. CLI Optimization Opportunities

1. 对共享函数 `_encode_params()` 这类多路径入口，修复前必须区分：
   - body path
   - params path
2. 如果 patch 改的是共用函数，结束前必须补一条“相邻语义路径”回归验证。
