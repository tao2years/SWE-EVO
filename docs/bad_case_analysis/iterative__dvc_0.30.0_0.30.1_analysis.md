# iterative__dvc_0.30.0_0.30.1 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_0.30.0_0.30.1`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `inner_only_with_timeout_noise`
- 一句话结论：
  这题是个单点 stage checksum bug。两个 CLI 都准确理解了 `wdir` default 导致 checksum 不一致的问题，但只有 `innercc` 最终修成，而且它是在出现 timeout / cli_reported_error 异常标记后仍然留下正确 patch 的特殊情况；`claude-code` 也定位到了相同问题，但 patch 形式不同，最终没通过 F2P，还引入了 1 条 P2P 回归。
- 根因标签：
  - `reference_success_with_runtime_noise`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement` 很短：

- `Fix stage checksum calculation when wdir is default`

`FAIL_TO_PASS`: `1` 条。

- `tests/test_stage.py::TestDefaultWorkingDirectory::test_ignored_in_checksum`

`PASS_TO_PASS`: `12` 条。

这是一个标准单点语义 bug。

### 2.2 runner-level user query

CLI 收到的是单点 checksum/wdir bug 的 prompt。

### 2.3 trace-level agent goals

- `innercc`
  - 明确认为：
    - `dumpd()` 里保存的 `wdir` 与 `_compute_md5()` 删除默认 `.` 的逻辑不一致
  - 其 patch 把 `wdir` 序列化成相对路径

- `claude-code`
  - 也认为 bug 在：
    - `load()` 把默认 `wdir` 变成绝对路径
    - `_compute_md5()` 仍在找字面量 `.`
  - 其 patch改的是 `_compute_md5()` 判断逻辑

### 2.4 official golden answer

这题的官方方向应是：

- 保持 default `wdir` 在 checksum 中被视作“无差异”

两边都抓到了这个语义核心。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | anomaly_flags |
| --- | --- | --- | --- | --- |
| `innercc` | `true` | `1/1` | `12/12` | `["cli_reported_error", "inference_timeout"]` |
| `claude-code` | `false` | `0/1` | `11/12` | `[]` |

这是一个很有价值的 case：

- `innercc` 有运行时异常标记，但最终 patch 是对的
- `claude-code` 没有异常标记，却没修成

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.30.0_0.30.1/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.30.0_0.30.1/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.30.0_0.30.1/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_0.30.0_0.30.1/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 25 / Read 9 / Edit 1`
- 核心假设：
  - `dumpd()` 存的是绝对/非规范默认 `wdir`
  - 应在序列化时把它规范成相对于 stage file 的路径

### 5.2 claude-code

- 工具分布：`Grep 14 / Read 13 / Bash 10 / Edit 1`
- 核心假设：
  - `_compute_md5()` 删除默认 `wdir` 的判断方式不对
  - 应在读取/比较时兼容绝对路径

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | 在 `dumpd()` 阶段就把默认 `wdir` 规范化 | 修成 |
| `claude-code` | 在 `_compute_md5()` 阶段兼容绝对路径判断 | 未修成 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

```diff
-                Stage.PARAM_WDIR: self.wdir,
+                Stage.PARAM_WDIR: os.path.relpath(self.wdir, os.path.dirname(self.path)),
```

### 7.2 claude-code

```diff
-        if d.get(self.PARAM_WDIR) == ".":
+        if os.path.realpath(d.get(self.PARAM_WDIR, "")) == os.path.realpath(os.path.dirname(self.path)):
```

`innercc` 选择在“写入表示”层修复；`claude-code` 选择在“比较/删除”层修复。

## 8. Evaluation And Failure Evidence

最关键的结果不是 traceback，而是：

- `innercc`: 有 timeout/anomaly，但最终 `resolved = true`
- `claude-code`: 无 anomaly，但 `F2P = 0/1`

这说明：

- anomaly flag 不能直接等价成最终失败
- patch 正确性和运行过程噪声要分开看

## 9. Root Cause

- `innercc`
  - 没有 bad case 根因；这是成功参考，但带有 runtime noise
- `claude-code`
  - `validation_gap`：没有证明自己的 `_compute_md5` 层修复真的覆盖了 stage dump/load 表示差异

## 10. CLI Optimization Opportunities

1. 对 serialization vs comparison 类 bug，优先明确故障发生在“写入表示”还是“读取/比较表示”。
2. 对 anomaly flag 的分析要区分“运行时过程噪声”和“最终 patch 正确性”。
