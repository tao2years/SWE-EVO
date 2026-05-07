# psf__requests_v2.27.0_v2.27.1 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `psf__requests_v2.27.0_v2.27.1`
- `repo`: `psf/requests`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_resolved_reference_success`
- 一句话结论：
  这是一个双方都准确命中的 requests 小型修复案例。问题非常集中：`prepend_scheme_if_needed()` 在重建 URL 时把 `auth` 丢了。两个 CLI 都定位到 `requests/utils.py`，并在重建 `netloc` 时把 `auth` 补回去，因此 `2/2` F2P 全过、`185/185` P2P 全保。
- 根因标签：
  - `reference_success_path`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

- `Fixed parsing issue that resulted in the auth component being dropped from proxy URLs. (#6028)`

`FAIL_TO_PASS`: `2` 条，都是：

- `test_prepend_scheme_if_needed[http://user:pass@example.com/path?query-...]`
- `test_prepend_scheme_if_needed[http://user@example.com/path?query-...]`

`PASS_TO_PASS`: `185` 条。

这是一个典型的小型 URL reconstruction bug。

### 2.2 runner-level user query

CLI 收到的 prompt 明确指出：

- 修复 `auth` component dropped from proxy URLs
- failing tests 全在 `prepend_scheme_if_needed`

### 2.3 trace-level agent goals

- `innercc`
  - 很快把问题收敛为：
    - `parsed.netloc` 不包含 auth
    - 需要在返回前重建 netloc

- `claude-code`
  - 也明确得出：
    - `parsed.auth` 被丢了
    - `netloc` 需要把 `auth@host[:port]` 补回去

### 2.4 official golden answer

从两边 patch 可见，golden 修复核心就是：

- 在 `prepend_scheme_if_needed()` 中把 `auth` 纳回 `netloc`

两边实现略有形式差异，但语义一致。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `true` | `2/2` | `185/185` | `137462` | `30` | `29` | `2` |
| `claude-code` | `true` | `2/2` | `185/185` | `588498` | `28` | `27` | `7` |

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/psf__requests_v2.27.0_v2.27.1/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/psf__requests_v2.27.0_v2.27.1/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/psf__requests_v2.27.0_v2.27.1/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/psf__requests_v2.27.0_v2.27.1/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 23 / Read 5 / Edit 1`
- 关键路径：
  - 很快锁定 `requests/utils.py`
  - 明确识别 `auth` 存在 `parsed.auth` 而非 `parsed.netloc`
  - 单次修改完成

### 5.2 claude-code

- 工具分布：`Bash 13 / Grep 11 / Read 2 / Edit 1`
- 关键路径：
  - 先用 failing tests 锁定函数
  - 再直接修 `auth -> netloc` 重建

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | `parsed.netloc` 不含 auth，需要在返回前补回 | 正确 |
| `claude-code` | `parsed.auth` 在 netloc 重建时被遗漏 | 正确 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

```diff
+    netloc = (auth + '@' + host) if auth else host
+    if port:
+        netloc += ':' + str(port)
```

### 7.2 claude-code

```diff
+    if auth:
+        netloc = f"{auth}@{netloc}"
```

两边都命中同一逻辑核心。

## 8. Evaluation And Failure Evidence

关键结果：

- `F2P = 2/2`
- `P2P = 185/185`
- `resolved = true`

## 9. Root Cause

没有 bad case 根因；这是成功参考路径。

## 10. CLI Optimization Opportunities

1. 把这类“failing tests 精准指向单函数、单字段丢失”的 case 作为参考成功模式。
2. 对照失败 case 时，可以看是否同样具备：
   - 单函数定位
   - 单逻辑修复
   - 明确的 before/after state
