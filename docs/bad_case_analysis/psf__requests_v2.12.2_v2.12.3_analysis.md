# psf__requests_v2.12.2_v2.12.3 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `psf__requests_v2.12.2_v2.12.3`
- `repo`: `psf/requests`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `claude_only`
- 一句话结论：
  `innercc` 在任务理解上接近正确，但在第二次编辑中把弯引号写进 Python 源码，并且没有用可靠验证及时发现；`claude-code` 把问题收敛到更窄的 early-return 条件，最终修成。
- 根因标签：
  - `edit_safety_error`
  - `validation_gap`
  - `hypothesis_lock_in`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
2.12.3 (2016-12-01)
-------------------

**Bugfixes**

-   Fixed regression from v2.12.1 for URLs with schemes that begin with
    "http". These URLs have historically been processed as though they
    were HTTP-schemed URLs, and so have had parameters added. This was
    removed in v2.12.2 in an overzealous attempt to resolve problems
    with IDNA-encoding those URLs. This change was reverted: the other
    fixes for IDNA-encoding have been judged to be sufficient to return
    to the behaviour Requests had before v2.12.0.
```

`FAIL_TO_PASS`:

- `tests/test_requests.py::TestPreparingURLs::test_parameters_for_nonstandard_schemes[http+unix://%2Fvar%2Frun%2Fsocket/path-params0-http+unix://%2fvar%2frun%2fsocket/path?key=value]`
- `tests/test_requests.py::TestPreparingURLs::test_parameters_for_nonstandard_schemes[http+unix://%2Fvar%2Frun%2Fsocket/path-params1-http+unix://%2fvar%2frun%2fsocket/path?key=value]`
- `tests/test_requests.py::TestPreparingURLs::test_url_mutation[http+unix://%2Fvar%2Frun%2Fsocket/path-http+unix://%2fvar%2frun%2fsocket/path0]`
- `tests/test_requests.py::TestPreparingURLs::test_url_mutation[http+unix://%2Fvar%2Frun%2Fsocket/path-http+unix://%2fvar%2frun%2fsocket/path1]`

`PASS_TO_PASS`: `109` 条，本分析只在需要时引用代表性样例。

### 2.2 runner-level user query

两个 CLI 实际收到的 query 都来自 `custom_cli_case/run_custom_cli_case.py` 的 `build_prompt()` 模板，渲染后为：

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: psf__requests_v2.12.2_v2.12.3

Release note / requirement:
2.12.3 (2016-12-01)
-------------------

**Bugfixes**

-   Fixed regression from v2.12.1 for URLs with schemes that begin with
    "http". These URLs have historically been processed as though they
    were HTTP-schemed URLs, and so have had parameters added. This was
    removed in v2.12.2 in an overzealous attempt to resolve problems
    with IDNA-encoding those URLs. This change was reverted: the other
    fixes for IDNA-encoding have been judged to be sufficient to return
    to the behaviour Requests had before v2.12.0.

Expected failing tests that should pass after your fix:
- tests/test_requests.py::TestPreparingURLs::test_parameters_for_nonstandard_schemes[http+unix://%2Fvar%2Frun%2Fsocket/path-params0-http+unix://%2fvar%2frun%2fsocket/path?key=value]
- tests/test_requests.py::TestPreparingURLs::test_parameters_for_nonstandard_schemes[http+unix://%2Fvar%2Frun%2Fsocket/path-params1-http+unix://%2fvar%2frun%2fsocket/path?key=value]
- tests/test_requests.py::TestPreparingURLs::test_url_mutation[http+unix://%2Fvar%2Frun%2Fsocket/path-http+unix://%2fvar%2frun%2fsocket/path0]
- tests/test_requests.py::TestPreparingURLs::test_url_mutation[http+unix://%2Fvar%2Frun%2Fsocket/path-http+unix://%2fvar%2frun%2fsocket/path1]

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

### 2.3 trace-level agent goals

两个 CLI 在 trace 里都把任务重写成了更具体的内部目标，但方向不同。

- `innercc`
  - 早期目标：修 `prepare_url` 的 early-return 条件
  - 中后期目标：把问题扩展成“两部分修复”，即同时修改 early-return 和 IDNA 分支
- `claude-code`
  - 内部目标一直比较稳定：只恢复“以 `http` 开头的 scheme 仍应继续 URL preparation”的行为

这也是后续分化的起点：

- `innercc` 把任务做宽了
- `claude-code` 把任务保持在更接近 release note 的范围内

### 2.4 official golden answer

官方 benchmark 给出的 `patch` 里包含版本号和 `HISTORY` 更新，但和行为修复直接相关的核心 hunk 只有：

```diff
diff --git a/requests/models.py b/requests/models.py
@@
-        if ':' in url and not url.lower().startswith(('http://', 'https://')):
+        if ':' in url and not url.lower().startswith('http'):
             self.url = url
             return
```

golden `test_patch` 对应验证点很明确：它新增了两类测试。

1. `test_url_mutation`
   - `http+unix://` 应该继续被 URL preparation 处理
2. `test_parameters_for_nonstandard_schemes`
   - 对 `http+unix://` 允许继续追加 query params
   - 对 `mailto:` 这类非 HTTP-like scheme 仍然保持 passthrough

所以这个 case 的官方目标不是“大改 URL 处理”，而是：

- 恢复 `scheme.startswith("http")` 的历史行为
- 同时不破坏真正非 HTTP-like scheme 的 passthrough 规则

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count | patch_apply |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `innercc` | `false` | `0/4` | `0/109` | `885042` | `56` | `55` | `4` | `true` |
| `claude-code` | `true` | `4/4` | `109/109` | `1037988` | `69` | `68` | `18` | `true` |

这里最重要的信号不是 `resolved=false`，而是：

- `innercc` 的 `PASS_TO_PASS` 从 `109/109` 直接掉到 `0/109`

这说明它不是“没修到”，而是把模块级行为整体打坏了。

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/psf__requests_v2.12.2_v2.12.3/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/psf__requests_v2.12.2_v2.12.3/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/psf__requests_v2.12.2_v2.12.3/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/psf__requests_v2.12.2_v2.12.3/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/psf__requests_v2.12.2_v2.12.3/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/psf__requests_v2.12.2_v2.12.3/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/psf__requests_v2.12.2_v2.12.3.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/psf__requests_v2.12.2_v2.12.3/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/psf__requests_v2.12.2_v2.12.3/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/psf__requests_v2.12.2_v2.12.3/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/psf__requests_v2.12.2_v2.12.3/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/psf__requests_v2.12.2_v2.12.3/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/psf__requests_v2.12.2_v2.12.3/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/psf__requests_v2.12.2_v2.12.3/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/psf__requests_v2.12.2_v2.12.3/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/psf__requests_v2.12.2_v2.12.3/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/psf__requests_v2.12.2_v2.12.3.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/psf__requests_v2.12.2_v2.12.3/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/psf__requests_v2.12.2_v2.12.3/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/psf__requests_v2.12.2_v2.12.3/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: bootstrap + repo exploration (`step 1-12`)

- 关键动作：
  - `ls` 仓库与 `requests/` 目录
  - `grep` failing tests
  - `Read tests/test_requests.py`
  - `grep` / `Read requests/models.py`
- 阶段目标：
  - 找出 URL preparation 实现与 failing tests 所在位置
- 阶段结论：
  - `prepare_url` 的 early-return 条件看起来是入口问题

#### Phase B: 初次定位与粗验证 (`step 13-17`)

- 关键动作：
  - 跑 `pytest` 子集
  - 检查 Python 版本
  - 看 `requests/models.py` git history
- 关键命令：
  - `python3 -m pytest ... 2>&1 | head -40`
- 问题：
  - 这里已经使用了会吞退出码和截断错误信息的验证模式

#### Phase C: 第一次编辑 (`step 18-21`)

- 关键动作：
  - 第一次 `Edit requests/models.py`
  - 发现“我改错了”，又读回文件再改一次
- 阶段结论：
  - 形成了“early-exit condition 需要放宽”的第一版假设

#### Phase D: 扩大假设范围 (`step 22-49`)

- 关键动作：
  - 多次回头读 `tests/test_requests.py`
  - 转去研究 `requote_uri`
  - 继续读 `requests/utils.py`
  - 继续读 `requests/packages/urllib3/util/url.py`
  - 手写多段 Python 脚本模拟 `parse_url` 和 URL reconstruction
- 关键阶段结论：
  - 在 `step 49` 左右，`innercc` 把问题扩展成“两部分修复”：
    1. 放宽 early-exit 条件
    2. 跳过 non-standard http scheme 的 IDNA 编码
- 这是后续偏航的开始，因为官方 golden patch 只要求第一部分

#### Phase E: 第二次编辑 (`step 50`)

- 关键动作：
  - 再次编辑 `requests/models.py`
- 结果：
  - patch 中引入了弯引号 `‘http’` / `‘https’`

#### Phase F: 伪验证与结束 (`step 51-56`)

- 关键动作：
  - `git diff`
  - 多个手写 Python 脚本做局部逻辑模拟
  - 最终输出“fix is complete”
- 缺失动作：
  - 没有重新跑 exact failing test
  - 没有做 `py_compile`
  - 没有做 `import requests`

### 5.2 claude-code

#### Phase A: bootstrap + repo exploration (`step 1-17`)

- 关键动作：
  - `Grep prepared.*request|prepare_url`
  - `Grep http+unix`
  - `Read requests/models.py`
  - `git status && git log`
- 阶段目标：
  - 定位 `prepare_url` 和测试文件

#### Phase B: 早期验证与环境噪声 (`step 18-23`)

- 关键动作：
  - 跑 exact pytest 子集
  - 检查 `python3` / `pytest`
- 关键命令：
  - `python3 -m pytest ... 2>&1 | head -80`
- 问题：
  - 和 `innercc` 一样，仍然使用了截断式验证命令

#### Phase C: 正确的任务收敛 (`step 24-41`)

- 关键动作：
  - 反复 grep/读 `prepare_url`
  - 看 `tests/test_requests.py` 相关段落
  - 读 `requests/models.py` 对应代码块
- 阶段结论：
  - 把问题收敛到“任何以 `http` 开头的 scheme 都不应被 early return 提前跳过”

#### Phase D: 编辑与路径混乱 (`step 42-52`)

- 关键动作：
  - 第一次 `Edit` 路径失败
  - 中间误编辑到 `.claude/projects/...jsonl`
  - 最终在正确 workspace 内完成 `requests/models.py` 修改
- 说明：
  - 这里有路径噪声，但没有影响最终补丁落点

#### Phase E: 局部 Python probe 验证 (`step 53-68`)

- 关键动作：
  - 用 Python 脚本验证：
    - `http+unix://` + params
    - `mailto:` passthrough
    - `url_mutation`
  - 再次看 `git diff` / `git status`
- 阶段结论：
  - 修复逻辑与 release note 一致

#### Phase F: 结束 (`step 69`)

- 关键动作：
  - 输出最终修复总结
- 风险：
  - 依旧没有正式重跑 exact failing test 形成闭环
- 但由于补丁足够窄，最终 evaluator 仍然通过

## 6. Hypothesis Iteration Log

### 6.1 innercc

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `1-17` | 问题在 `prepare_url` early-return 条件 | failing tests 名称、`requests/models.py` | failing tests 都围绕 nonstandard scheme URL mutation | 这一点是对的，但只覆盖了一半 |
| `22-49` | 还需要额外跳过 non-standard http scheme 的 IDNA 编码 | `requote_uri`、`parse_url`、局部 Python 模拟 | `http+unix://` 和 percent encoding 看起来像会在后续阶段继续出错 | 这是过度扩张。官方 golden patch 并不需要额外改 IDNA 分支 |
| `50-56` | patch 逻辑自洽即可结束 | `git diff`、手写模拟脚本 | 局部模拟都返回了“看似正确”的 URL | 错，因为它没有验证源码是否还能 import；真实失败是语法层面的 |

### 6.2 claude-code

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `1-23` | 问题在 `prepare_url` 对 `http+unix://` 的 early return | failing tests + `requests/models.py` | 与 release note 直接对齐 | 正确 |
| `24-41` | 修复只需要放宽为 `startswith('http')` | 代码阅读、测试命名、局部 grep | 最小变更即可恢复历史行为 | 正确 |
| `53-68` | 局部 Python probe 足以支撑补丁正确性 | ad hoc Python requests 构造 | 对这个 case 来说 probe 覆盖了关键分支 | 严格说验证不完整，但补丁最终是正确的 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc patch

`innercc` 的 patch 有两个核心问题：

1. 修改范围过宽
   - 不只改了 early-return
   - 还额外改了 IDNA 分支

2. 编辑安全性失控
   - 直接把弯引号写进源码：

```python
if scheme.lower() in (‘http’, ‘https’):
```

这不是业务逻辑错误，而是代码生成质量错误。

### 7.2 claude-code patch

`claude-code` 的 patch 只改了真正和任务相关的一行条件，行为上更接近官方 golden patch：

```diff
- if ':' in url and not url.lower().startswith(('http://', 'https://')):
+ if ':' in url:
+     scheme_candidate = url.split('://')[0].lower()
+     if not scheme_candidate.startswith('http'):
+         self.url = url
+         return
```

虽然形式不是和 golden patch 完全一样，但语义等价。

## 8. Evaluation And Failure Evidence

### 8.1 innercc: 这是“修坏了”

最关键证据来自 `test_output.txt`：

```text
ImportError while loading conftest '/testbed/tests/conftest.py'.
...
File "/testbed/requests/models.py", line 380
if scheme.lower() in (‘http’, ‘https’):
                        ^
SyntaxError: invalid character '‘' (U+2018)
```

这解释了为什么：

- `FAIL_TO_PASS = 0/4`
- `PASS_TO_PASS = 0/109`

因为 evaluator 甚至在导入 `requests` 时就失败了，后续大多数测试根本没有进入行为验证阶段。

### 8.2 claude-code: 这是“修到了”

`claude-code` 的评测结果是：

- `FAIL_TO_PASS = 4/4`
- `PASS_TO_PASS = 109/109`
- `resolved = true`

说明它既命中了 bug，也没有引入额外回归。

## 9. Root Cause

### 9.1 direct root cause

- `edit_safety_error`
  - `innercc` 在第二次编辑中把弯引号写进 Python 源码，直接触发 `SyntaxError`

### 9.2 contributing factors

- `validation_gap`
  - 没有做 `py_compile`
  - 没有做 `import requests`
  - 没有重跑 exact failing test
  - 多次使用 `pytest ... | head`

- `hypothesis_lock_in`
  - 在“需要同时改 IDNA 分支”的假设上越走越深，把简单任务做复杂了

### 9.3 non-root but misleading signals

- 局部 Python 模拟脚本返回了“逻辑上看似正确”的 URL
- 这容易让 agent 误以为 patch 已经可以结束
- 但这些 probe 没有覆盖“文件还能否 import”这个更基础的健康检查

## 10. CLI Optimization Opportunities

### 10.1 case-specific actions

1. 对 Python case，结束前强制跑：
   - `python -m py_compile <edited_files>`
   - `python -c "import <top_level_module>"`
2. 发现 diff 中出现非 ASCII 标点时直接拦截并要求重写。

### 10.2 generalizable actions

1. shell 验证模板禁用 `pytest ... | head`
   - 至少要保留完整退出码
2. 如果 patch 会影响 import path 上的核心模块，必须做 import smoke test。
3. 当任务只要求“最小 code-only fix”时，优先对齐 golden behavior，不鼓励顺手扩展修复面。

### 10.3 validation plan for the optimization

1. 给 `innercc` runner 增加 smart-quote 检查，回放此 case。
2. 给验证阶段增加 `py_compile` 与 `import requests`，观察能否在会话内阻止错误 patch 结束。
3. 去掉 `pytest | head` 后，再回放此 case，检查是否能显式暴露 import 失败并触发继续修复。
