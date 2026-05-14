# project-coverage-7 多版本根因综合复盘（2026-05-11）

## 1. 范围与数据源

本次统一复盘 6 个 run：

| display name | run id | date | cli kind | cli bin |
| --- | --- | --- | --- | --- |
| `pc7-claude-2.1.116` | `20260508-213625` | 2026-05-08 | `claude` | `/usr/bin/claude` |
| `pc7-claude-2.1.138` | `20260511-095638-project-coverage-7-claude-2.1.138` | 2026-05-11 | `claude` | `/home/wt/.local/bin/claude` |
| `pc7-innercc-init` | `20260509-112102` | 2026-05-09 | `innercc` | `dist/innercc_0509_init` |
| `pc7-innercc-context` | `20260509-115738` | 2026-05-09 | `innercc` | `dist/innercc_0509_context` |
| `pc7-innercc-dcp` | `20260509-142112-project-coverage-7-innercc` | 2026-05-09 | `innercc` | `dist/innercc_0509_dcp` |
| `pc7-innercc-dcp+context` | `20260509-103105` | 2026-05-09 | `innercc` | `/home/wt/sss_repos/innerCC/cli` |

本分析实际核对了以下本地证据：

- `official48_runs/<run_id>/metadata.json`
- `official48_runs/<run_id>/analysis/summary.json`
- `official48_runs/<run_id>/analysis/cases.csv`
- `official48_runs/<run_id>/infer/runs/<instance_id>/cli_result.json`
- `official48_runs/<run_id>/infer/runs/<instance_id>/cli_stdout.log`
- `official48_runs/<run_id>/infer/runs/<instance_id>/patch.diff`
- `official48_runs/<run_id>/eval_worker_logs/<instance_id>.log`
- `logs/run_evaluation/eval_input_<run_id>/.../<instance_id>/report.json`
- `logs/run_evaluation/eval_input_<run_id>/.../<instance_id>/test_output.txt`
- `runtime/summarize_official48_run.py`

限制说明：

- 这批 run 的 `router_trace_bundle.json` 都为空。
- `router_session_id` / `router_run_id` 为 `null`。
- 所以这次无法还原逐轮 LLM message trace，只能用 `cli_stdout.log` / `cli_result.json` 的最终任务理解与收口文本，配合 patch、evaluator report 和 test output 复盘。

### 1.1 已整合的旧文档

这份主文档不是从零开始写的，而是在下面这些既有文档基础上重算和收束：

- 旧的全量方法论与宏观结论：
  - [cross_case_synthesis.md](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/docs/bad_case_analysis/cross_case_synthesis.md)
  - [common_issues_summary.md](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/docs/bad_case_analysis/common_issues_summary.md)
  - [official48_daily_report_2026-05-06.md](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/docs/bad_case_analysis/official48_daily_report_2026-05-06.md)
- 旧的单案复盘：
  - [dask__dask_2024.3.1_2024.4.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/docs/bad_case_analysis/dask__dask_2024.3.1_2024.4.0_analysis.md)
  - [pydantic__pydantic_v2.7.1_v2.7.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/docs/bad_case_analysis/pydantic__pydantic_v2.7.1_v2.7.2_analysis.md)
  - [iterative__dvc_1.0.0b6_1.0.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/docs/bad_case_analysis/iterative__dvc_1.0.0b6_1.0.0_analysis.md)
  - [conan-io__conan_2.0.2_2.0.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/docs/bad_case_analysis/conan-io__conan_2.0.2_2.0.3_analysis.md)
  - [scikit-learn__scikit-learn_0.20.1_0.20.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/docs/bad_case_analysis/scikit-learn__scikit-learn_0.20.1_0.20.2_analysis.md)
- 本轮过程中也有过更窄的中间分析草稿，但其中有效结论已经全部并入本文，不再单独保留。

这次整合的方式不是简单拼接，而是：

1. 继承旧文档里的稳定结论，例如 `validation_gap / task_understanding_error / hypothesis_lock_in` 这条宏观失败链。
2. 用当前 `pc7` 的 6 个 run 重新验证哪些旧结论仍成立。
3. 对和当前数据冲突的旧表述做修正，例如：
   - 不能把 `innercc-context` 的 `99.8% p2p` 简单写成“prompt 能力显著提升”
   - 不能把 `claude-2.1.138` 的提升写成“全面更强”，而应明确成 `dask + iterative` 两案驱动

## 2. 统计口径

### 2.1 `resolved`

- 直接取 `report.json` 中 `resolved == true` 的 case 数。
- 这里 6 个 run 都是 `7/7 eval reports`，所以 `resolved rate` 可直接按 7 个 case 算。

### 2.2 `f2p micro`

来自 `runtime/summarize_official48_run.py`：

- `f2p_micro_rate_known_only = 所有 case 的 FAIL_TO_PASS.success 总和 / FAIL_TO_PASS.total 总和`

这里总分母固定：

- `FAIL_TO_PASS total = 22`

### 2.3 `p2p micro`

同样来自 `runtime/summarize_official48_run.py`：

- `p2p_micro_pass_rate_known_only = 所有 case 的 PASS_TO_PASS.success 总和 / PASS_TO_PASS.total 总和`

这里总分母固定：

- `PASS_TO_PASS total = 9156`

所以：

- `micro` 不是“每个 case 先算百分比再平均”
- `micro` 是“把所有测试条目汇总后再算总通过率”

这点很关键，因为 run 级看板波动实际上经常只由 1 到 2 个 case 主导。

### 2.4 从旧文档继承什么，修正什么

从旧的 `official48` 全量文档里，可以直接继承的结论有两条：

1. 主问题常常不在“代码写不出来”，而在 `task sizing -> localization -> validation -> termination` 这条收敛链失真。
2. `innercc` 更容易覆盖多簇任务，`claude` 更擅长窄任务和强契约任务。

但当前 `pc7` 这组数据要求我们再加两条修正：

1. 在小子集上，run-level 数字往往是单案驱动，而不是系统性平均体现。
   - `init > claude-2.1.116` 基本就是 `dask` 单案驱动
   - `claude-2.1.138 > claude-2.1.116` 基本就是 `dask + iterative` 两案驱动
2. 环境 / 安装链路在小子集上可以完全盖过模型能力差异。
   - `pydantic` 一案就足以把 `p2p micro` 锁死在 `54.3%`
   - 同样的 `NoDefault` patch，是否真正生效，更取决于 `typing-extensions` 有没有成功升级

## 3. run 级结论

| run | resolved | f2p micro | 等价计数 | p2p micro | 等价计数 | p2p failure | total cost | turns | input tok | cache hit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `pc7-claude-2.1.116` | `2` | `40.9%` | `9 / 22` | `54.2923%` | `4971 / 9156` | `4185` | `$29.65` | `349` | `8630k` | `45.3%` |
| `pc7-claude-2.1.138` | `4` | `54.5%` | `12 / 22` | `54.2923%` | `4971 / 9156` | `4185` | `$42.63` | `328` | `7335k` | `48.2%` |
| `pc7-innercc-init` | `3` | `45.5%` | `10 / 22` | `54.2704%` | `4969 / 9156` | `4187` | `$19.88` | `294` | `6133k` | `14.6%` |
| `pc7-innercc-context` | `3` | `59.1%` | `13 / 22` | `99.8253%` | `9140 / 9156` | `16` | `$16.80` | `296` | `5110k` | `17.1%` |
| `pc7-innercc-dcp` | `3` | `45.5%` | `10 / 22` | `54.2704%` | `4969 / 9156` | `4187` | `$59.12` | `254` | `18623k` | `9.1%` |
| `pc7-innercc-dcp+context` | `3` | `50.0%` | `11 / 22` | `54.2923%` | `4971 / 9156` | `4185` | `$46.22` | `515` | `14577k` | `11.7%` |

### 3.1 run 级摘要

先给结论：

1. `pc7-claude-2.1.138` 的提升是真实的，但只来自两个 case：`dask` 和 `iterative`。
2. `pc7-innercc-context` 的 `99.8% p2p` 也是真实的，但不能直接解释成“context prompt 自身让模型全面更稳”，因为它强依赖 `pydantic` 评测时依赖环境被成功更新。
3. 多个 `54.3% p2p` 并不完全相同，只是四舍五入后看起来一样。
4. 所有 run 的 `p2p` 走势都被 `pydantic__pydantic_v2.7.1_v2.7.2` 一案主导。

## 4. case 级差异矩阵

| case | `claude-2.1.116` | `claude-2.1.138` | `innercc-init` | `innercc-context` | `innercc-dcp` | `innercc-dcp+context` |
| --- | --- | --- | --- | --- | --- | --- |
| `conan-io__conan_2.0.2_2.0.3` | `resolved=false`, `1/8`, `315/317` | 同左 | 同左 | 同左 | 同左 | 同左 |
| `dask__dask_2024.3.1_2024.4.0` | `resolved=false`, `0/2`, `2747/2747` | `resolved=true`, `2/2`, `2747/2747` | `resolved=true`, `2/2`, `2747/2747` | 同 init | 同 init | 同 init |
| `iterative__dvc_1.0.0b6_1.0.0` | `resolved=false`, `1/2`, `2/2` | `resolved=true`, `2/2`, `2/2` | `resolved=false`, `0/2`, `0/2` | 同 init | 同 init | `resolved=false`, `1/2`, `2/2` |
| `modin-project__modin_0.27.0_0.27.1` | `resolved=true`, `4/4`, `883/883` | 同左 | 同左 | 同左 | 同左 | 同左 |
| `psf__requests_v2.27.0_v2.27.1` | `resolved=true`, `2/2`, `185/185` | 同左 | 同左 | 同左 | 同左 | 同左 |
| `pydantic__pydantic_v2.7.1_v2.7.2` | `resolved=false`, `0/3`, `403/4584` | 同左 | 同左 | `resolved=false`, `3/3`, `4574/4584` | 同 `claude-2.1.116` | 同 `claude-2.1.116` |
| `scikit-learn__scikit-learn_0.20.1_0.20.2` | `resolved=false`, `1/1`, `436/438` | 同左 | 同左 | 同左 | 同左 | 同左 |

### 4.1 谁决定了 `resolved`

只看 `resolved`，driver cases 只有两个：

- `dask__dask_2024.3.1_2024.4.0`
- `iterative__dvc_1.0.0b6_1.0.0`

解释：

- `claude-2.1.116 -> claude-2.1.138` 的 `resolved 2 -> 4` 完全由这两案贡献
- `innercc-init -> innercc-context` 的 `resolved` 不变，说明 context 这次的巨大 `p2p` 改善没有转化成额外 resolved

### 4.2 谁决定了 `f2p micro`

最关键的三个 driver cases：

- `dask`
- `iterative`
- `pydantic`

拆开看：

- `claude-2.1.116 -> claude-2.1.138`：`dask +2`，`iterative +1`，合计 `9/22 -> 12/22`
- `innercc-init -> innercc-context`：`pydantic +3`，合计 `10/22 -> 13/22`
- `innercc-dcp+context`：只比 `claude-2.1.116` 多 `iterative +1`，但 `pydantic` 没好，所以只有 `11/22`

### 4.3 谁决定了 `p2p micro`

主导 case 非常明确：

- `pydantic__pydantic_v2.7.1_v2.7.2`

`PASS_TO_PASS.failure` 拆开后：

| case | `claude-2.1.116` | `claude-2.1.138` | `innercc-init` | `innercc-context` | `innercc-dcp` | `innercc-dcp+context` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `pydantic` | `4181` | `4181` | `4181` | `10` | `4181` | `4181` |
| `conan` | `2` | `2` | `2` | `2` | `2` | `2` |
| `scikit` | `2` | `2` | `2` | `2` | `2` | `2` |
| `iterative` | `0` | `0` | `2` | `2` | `2` | `0` |

结论：

- 几个 `54.3%` 的 run，真正的大头都是同一个地方：`pydantic = 4181`
- `conan` 和 `scikit` 固定各掉 `2`
- `iterative` 只解释尾数差异，不解释主趋势

也就是说：

- `54.2704%` 和 `54.2923%` 的区别，不是“稳定性层级不同”
- 只是 `iterative` 是否再多掉 `2` 个 P2P

### 4.4 谁决定了成本

成本驱动 case 与质量驱动 case 并不完全一致。

`claude-2.1.138` 相比 `claude-2.1.116`：

- `conan`: `$15.92 -> $27.83`，结果不变
- `modin`: `$0.90 -> $3.60`，结果不变
- `scikit`: `$0.18 -> $1.78`，结果不变
- `dask`: `$1.88 -> $3.16`，结果变好
- `iterative`: `$5.05 -> $2.29`，结果变好
- `pydantic`: `$5.37 -> $3.40`，结果不变

所以：

- 新版 `claude-2.1.138` 的质量收益集中在 `dask + iterative`
- 但成本涨幅最大的是 `conan`，而 `conan` 没有任何质量收益

## 5. driver case 深挖

## 5.1 `dask__dask_2024.3.1_2024.4.0`

### 当前状态

- `claude-2.1.116`: `resolved=false`, `F2P=0/2`, `P2P=2747/2747`
- `claude-2.1.138`: `resolved=true`, `F2P=2/2`, `P2P=2747/2747`
- 所有 innercc 版本：`resolved=true`, `F2P=2/2`, `P2P=2747/2747`

### 概览

这题是新版 `claude` 最明确的正向提升样例。

- 旧版修到了 `_value_counts` 的局部 special-case
- 新版修到了 `_value_counts_aggregate` 的真实故障层

### 判断

这是一次纯能力改进，不是环境因素。

### 证据

旧版 `cli_stdout.log` 的最终任务理解是：

- 问题在 `_value_counts` 的 special-case 返回 `RangeIndex`
- 方案是删掉 special-case，直接 `return x.value_counts(**kwargs)`

旧版 patch：

```diff
-    if not x.groups or all(...):
-        return pd.Series(dtype=int)
-    else:
-        return x.value_counts(**kwargs)
+    return x.value_counts(**kwargs)
```

但旧版 evaluator 失败栈清楚地指向：

```text
ValueError: No objects to concatenate
...
dask/dataframe/groupby.py:3214 in _value_counts_aggregate
```

新版 `cli_stdout.log` 的最终任务理解改成了：

- 问题在 `_value_counts_aggregate`
- 当所有 partition 为空时，`data` 为空，`pd.concat` 崩掉

新版 patch：

```diff
if not data:
    data = [pd.Series(index=series_gb.obj.index[:0], dtype="float64")]
```

新版 evaluator：

- `bonus_success = 2`
- `bonus_failure = 0`
- `Resolved rate = 100%`

### 为什么旧版错 / 新版对

旧版是局部解释正确、故障层级错误：

- 它看见了 “all-NA partition 返回空”
- 但没有继续追到 “真正报错发生在 aggregate concat”

新版则把 fault localization 提升到了真实故障层：

- 不再纠结 `_value_counts` 的局部行为
- 直接防住 `_value_counts_aggregate` 的空 concat

### 是否属于能力变化还是环境噪音

- 明确属于能力变化
- 不存在安装链路差异
- 不存在环境兼容差异
- patch 变化本身就足以解释结果变化

## 5.2 `iterative__dvc_1.0.0b6_1.0.0`

### 当前状态

- `claude-2.1.116`: `resolved=false`, `F2P=1/2`, `P2P=2/2`
- `claude-2.1.138`: `resolved=true`, `F2P=2/2`, `P2P=2/2`
- `innercc-init/context/dcp`: `resolved=false`, `F2P=0/2`, `P2P=0/2`
- `innercc-dcp+context`: `resolved=false`, `F2P=1/2`, `P2P=2/2`

### 概览

这题是“接口契约是否补完整”的典型样例。

### 判断

`claude-2.1.138` 的改进本质上是 contract alignment 改进，而不是更深层的 repo 推理。

### 证据

旧版 `claude-2.1.116` 已经非常接近正确：

- command 层加了 `--no-exec`
- repo 层也加了 `no_exec=False`
- `no_exec=True` 时会 `ignore_outs()`

但旧版 command 层只在 `self.args.no_exec` 为真时才注入参数：

```diff
kwargs = {"out": self.args.out, "fname": self.args.file}
if self.args.no_exec:
    kwargs["no_exec"] = True
self.repo.imp_url(self.args.url, **kwargs)
```

对应 report：

- `test_import_url` 通过
- `test_import_url_no_exec` 失败
- `F2P = 1/2`

新版 `claude-2.1.138` 的 command 层改成：

```diff
self.repo.imp_url(
    self.args.url,
    out=self.args.out,
    fname=self.args.file,
    no_exec=self.args.no_exec,
)
```

对应 report：

- `test_import_url` 成功
- `test_import_url_no_exec` 成功
- `F2P = 2/2`
- `resolved = true`

### 为什么旧版错 / 新版对

旧版的错误不是“不会实现 no_exec”，而是：

- 它把 `no_exec` 当成条件分支
- 没把它当成公开接口契约的一部分

新版则做了两件对的事情：

1. 默认路径也显式传 `no_exec=False`
2. `--no-exec` 路径传 `no_exec=True`

这正好匹配 unit test 对 mock call 的断言。

### 是否属于能力变化还是环境噪音

- 明确属于能力变化
- 环境日志里仍有 DVC 旧依赖噪音和 `fractions.gcd` 相关错误
- 但两版都面临同一批环境噪音，新版依然把目标测试打通了

所以这里的结果改善仍应归因给契约对齐能力，而不是环境差异。

## 5.3 `pydantic__pydantic_v2.7.1_v2.7.2`

### 当前状态

- `claude-2.1.116`: `resolved=false`, `F2P=0/3`, `P2P=403/4584`
- `claude-2.1.138`: 同旧版
- `innercc-init`: 同旧版
- `innercc-context`: `resolved=false`, `F2P=3/3`, `P2P=4574/4584`
- `innercc-dcp`: 同旧版
- `innercc-dcp+context`: 同旧版

### 概览

这题是整个 `pc7` 子集里最容易制造误判的 case：

- 看起来像“模型懂不懂 `NoDefault` sentinel”
- 但 run 间巨大差异的真正主因是安装链路是否把 `typing-extensions` 升到能导入 `NoDefault` 的版本

### 判断

这是当前全组对比里最强的环境噪音案例。

### 证据

`innercc-context` 与其他 5 个 run 的最终 patch 非常接近，核心都是：

```diff
from typing_extensions import ... NoDefault ...
...
if default is not None and default is not NoDefault:
```

但 evaluator 结果完全不同：

- `innercc-context`: `F2P=3/3`, `P2P failure=10`
- 其余 5 个 run: `F2P=0/3`, `P2P failure=4181`

真正分叉点出现在安装阶段。

`innercc-context` 的 `test_output.txt` 明确出现：

```text
Lock successful
Synchronizing working set with resolved packages
Update typing-extensions 4.10.0 -> 4.13.2 successful
...
collected 5150 items
```

而 `claude-2.1.138` 的 `test_output.txt` 则是：

```text
[ReadTimeout]: The read operation timed out
...
[PdmException]: Resolving from lockfile failed
make: *** [Makefile:15: install] Error 1
...
collecting ... collected 1019 items / 57 errors
...
ImportError: cannot import name 'NoDefault' from 'typing_extensions'
```

`claude-2.1.116` 和 `innercc-init` 也有相同模式：

- `ReadTimeout`
- `make install` 未完成
- collection 阶段大面积 `ImportError`

### 为什么旧版错 / 新版对

这题不能简单用“谁 patch 更好”解释。

更准确地说：

- `innercc-context` 赢，不是因为它的 patch 表面更复杂
- 而是因为它那次评测成功把 `typing-extensions` 升到了 `4.13.2`
- `NoDefault` 因此可导入，patch 才真的有机会生效

相反，`claude-2.1.116`、`claude-2.1.138`、`innercc-init`、`innercc-dcp`、`innercc-dcp+context` 都被安装阶段卡死：

- patch 仍然引用 `NoDefault`
- 环境却停留在不能导入 `NoDefault` 的旧依赖
- 结果在 collection 阶段就炸成 `57 errors`

### 能不能从推理 query 里定位 `context` 为什么成功

这里必须分成“能证明的”和“不能证明的”两部分。

#### 能证明的

1. `innercc-init` 和 `innercc-context` 在 `pydantic` 上最终 patch **相同**。

直接证据：

- `init` 的 `patch.diff`：`official48_runs/20260509-112102/infer/runs/pydantic__pydantic_v2.7.1_v2.7.2/patch.diff`
- `context` 的 `patch.diff`：`official48_runs/20260509-115738/infer/runs/pydantic__pydantic_v2.7.1_v2.7.2/patch.diff`

两边关键 hunk 完全一致，都是：

```diff
from typing_extensions import ... NoDefault ...
...
if default is not None and default is not NoDefault:
```

`patch_sanitization.json` 也一致，说明只是把 docs 格式化改动从最终 patch 里删掉了。

2. `context` 的 install 链路成功，而 `init` / `2.1.89` / `2.1.138` 都没有成功。

直接证据：

- `context`：
  - `Update typing-extensions 4.10.0 -> 4.13.2 successful`
  - `collected 5150 items`
- `init` / `2.1.89`：
  - `ReadTimeout`
  - `collected 1019 items / 57 errors`
  - `ImportError: cannot import name 'NoDefault'`
- `2.1.138`：
  - `ReadTimeout`
  - `PdmException`
  - `collected 1019 items / 57 errors`
  - `ImportError: cannot import name 'NoDefault'`

3. `context` 的 agent 自报更短、更克制，但不是 patch 方向更换。

`cli_result.json` 显示：

- `init`：`51` turns，`$1.75`
- `context`：`31` turns，`$0.92`

这说明 `context` run 的推理过程更短，但它并没有把问题修成另一份不同的代码。

#### 不能证明的

当前**没有**足够证据证明下面这些说法：

1. `history snip` 明确删掉了哪一段无关上下文。
2. `reactive compact` 明确保住了哪一条主线，避免了哪一次具体跑偏。
3. `context` 的成功主要来自 prompt/context 特性本身，而不是 install 成功这个更直接的分叉点。

原因很简单：

- 这批 innercc run 的 `router_trace_bundle.json` 为空
- 没有逐轮 message transcript
- 只能看到最终 `cli_stdout.log` / `cli_result.json` 摘要，而看不到“每一轮到底输入了什么、压掉了什么”

所以，如果一定要回答“是 snip 去掉了无关内容，还是更好地守住了主线”，目前最严谨的表述只能是：

- **有这种可能**
- **但本地证据不足以定位到具体哪段内容被 snip 掉，或哪次偏航被 compact 阻止**
- **当前唯一能坐实的硬分叉点，是依赖环境更新是否成功**

### 是否属于能力变化还是环境噪音

这里必须拆成两层：

第一层，环境噪音：

- `4181` 个 P2P 回归主要是环境兼容问题扩散出来的
- 不是 4181 个独立逻辑点全部被模型修坏

第二层，能力问题仍然存在：

- `claude-2.1.138` 的 `cli_stdout.log` 仍然自报“两个 F2P 已过，一个只是 black formatting”
- 但 evaluator 结果是 `0/3`
- 说明它仍然存在明显的 self-report optimism / validation gap

所以这题的最终判断是：

- 主要根因是环境/安装链路不确定性
- 次级根因是 agent 过度相信自测结果

## 5.4 `conan-io__conan_2.0.2_2.0.3`

### 当前状态

6 个 run 完全一致：

- `resolved=false`
- `F2P=1/8`
- `P2P=315/317`

### 概览

这题不是 run 间差异 driver，但它是成本黑洞。

### 判断

这题的根因不是“某个版本偶然失误”，而是所有版本都把一个多簇 bundle case 当成局部题修，导致长期停在 `1/8`。

### 证据

所有 run 的 report 都显示：

- 只修成了 `test_cache_integrity`
- `backup_sources_*` 主簇一直没过
- 固定 `2` 个 P2P 回归：
  - `test_cache_clean`
  - `test_multiple_options_patterns`

最重要的是，新版 `claude-2.1.138` 在这里：

- turns 没变，还是 `111`
- cost 从 `$15.92` 升到 `$27.83`
- 结果完全没变

### 是否属于能力变化还是环境噪音

- 不属于环境噪音
- 也不体现明确能力提升
- 更像是 bundle decomposition 失败 + 成本控制差

## 5.5 `scikit-learn__scikit-learn_0.20.1_0.20.2`

### 当前状态

6 个 run 完全一致：

- `resolved=false`
- `F2P=1/1`
- `P2P=436/438`

### 概览

这是一个“目标测试修到了，但没有做好邻近回归验证”的稳定样本。

### 证据

6 个 run 的固定回归都是：

- `sklearn/linear_model/tests/test_logistic.py::test_logreg_cv_penalty`
- `sklearn/utils/tests/test_validation.py::test_check_array_series`

### 是否属于能力变化还是环境噪音

- 不属于环境噪音
- 属于稳定的 `validation_gap`

## 6. 根因排序

### 1. 环境 / 安装链路不确定性

代表 case：

- `pydantic`

表现：

- `ReadTimeout`
- `PdmException`
- lockfile resolve 失败
- `typing_extensions.NoDefault` 无法导入

影响：

- 直接制造 `4181` 个 P2P 回归
- 把 run-level `p2p micro` 锁死在 `54.3%`
- 也是为什么不能把 `innercc-context` 的 `99.8% p2p` 纯归因给 context prompt

### 2. fault localization 能力差异

代表 case：

- `dask`

表现：

- 旧版 `claude` 停在 `_value_counts`
- 新版 `claude` 与 innercc 正确打到 `_value_counts_aggregate`

影响：

- 决定了 `resolved` 的关键跃迁之一

### 3. 接口契约对齐能力差异

代表 case：

- `iterative`

表现：

- 是否把 `no_exec=False` 也视为公开接口契约的一部分

影响：

- 决定了 `claude-2.1.116 -> 2.1.138` 的另一半 resolved 增量

### 4. bundle case 覆盖不足

代表 case：

- `conan`

表现：

- 所有版本都只修到局部簇
- `backup_sources` 主簇始终没打通

影响：

- 所有版本长期停在 `1/8`
- 还是最大成本黑洞之一

### 5. 验证没收口 / 自报过度乐观

代表 case：

- `pydantic`
- `scikit`
- 早期 `iterative`

表现：

- agent 自称“all tests pass”或“fix complete”
- evaluator 仍然不认

影响：

- 容易把环境问题误报成代码问题
- 容易把局部正确误报成任务完成

## 7. 最终判断

### 7.1 为什么 `innercc-init` 比 `claude-2.1.116` 好

不是全面优势，而是单案驱动：

- `dask` 上 `innercc-init` 命中了真实修复点
- `claude-2.1.116` 修偏
- 这 1 个 case 足以把 `resolved` 从 `2` 拉到 `3`

### 7.2 为什么 `innercc-context` 看起来最强

表面原因：

- `F2P=13/22`
- `P2P=9140/9156`
- `cost` 还是全组最低

真正原因要拆开说：

- `dask`、`modin`、`requests`、`scikit`、`conan` 并没有比其他 innercc 版本更强很多
- 巨大差异几乎全部来自 `pydantic`
- `pydantic` 的提升又强依赖 `typing-extensions` 成功升级

因此：

- 这组结果说明 `innercc-context` 这次 run 非常成功
- 但还不能把 `99.8% p2p` 直接解释成纯 prompt 能力收益

### 7.3 为什么 `claude-2.1.138` 的 `resolved` 明显更好但 `p2p` 没变

因为它只改善了两个 case：

- `dask`
- `iterative`

而主导 `p2p` 的 `pydantic` 完全没动，所以：

- `resolved` 和 `F2P` 变好
- `P2P` 原地踏步

### 7.4 为什么 `claude-2.1.138` 成本更高

不是因为所有 case 都更深更有效地探索了，而是：

- `dask` 和 `iterative` 的投入变得有效
- `conan/modin/scikit` 的额外投入没有转化成结果

其中 `conan` 的投入最不划算。

## 8. 建议

1. 把 `pydantic` 从模型能力评估里单独隔离出来，先固定依赖环境，再谈版本能力差异。
2. 把 `dask` 作为 fault localization 正例保留，后续专门比较不同版本是否能稳定命中 aggregate 层。
3. 把 `iterative` 作为接口契约正例保留，重点观察新版是否能持续做到“默认路径也显式满足 mock 契约”。
4. 对 `conan` 加一个成本门槛，如果探索超过某个 token / cost 还没有覆盖第二簇 F2P，就应该提前止损或重规划。
5. 对所有版本增加“自报成功 vs evaluator 结果”的一致性检查，避免把 `cli_stdout.log` 的乐观总结当真。

## 9. llm router 干净重跑后的 query 级补充结论

下面这部分只基于 `2026-05-11` 之后的**干净 llm router 重跑**，不再依赖早期 `cli_stdout.log` 摘要。

### 9.1 这次终于能看见什么

这次补跑后，至少以下 case 已经拿到了可读的 `router_trace_bundle.json`：

- `context / dask`
- `context / iterative`
- `context / pydantic`
- `latest claude / dask`
- `latest claude / iterative`
- `latest claude / pydantic`

因此，现在可以回答的已经不是“最终 patch 长什么样”，而是：

- agent 是先盯测试，还是先被别的线索吸走
- 是不是把 benchmark 的 3 条 F2P 都一直放在主线里
- 中途是否把“看起来更普适的解释”当成了真正任务目标

### 9.2 `context / pydantic`：真实上是把 3 条目标测试一直抓在手里

从 trace 看，`context` 在 `pydantic` 上的路径非常集中：

1. 一开始就抓：
   - `tests/test_generics.py::test_serialize_unsubstituted_typevars_bound_default_supported`
   - `tests/test_docs.py` 里的两个 `docs/concepts/models.md` 示例
2. 很快直接读：
   - `tests/test_generics.py`
   - `tests/test_docs.py`
   - `docs/concepts/models.md`
3. 然后马上做运行时验证：
   - 打印 `typing_extensions.TypeVar.__default__`
   - 检查它是否就是 `NoDefault`
4. 最终 patch 是：
   - `NoDefault -> None` 的最小规范化
   - 再补 docs black formatting

对应的最终 patch 是：

```diff
default = getattr(typevar, '__default__', None)
if default is NoDefault:
    default = None
```

再加一处 docs 改动：

```diff
-class ItemBase(BaseModel):
-    ...
+class ItemBase(BaseModel): ...
```

从 query 级别看，这案子的成功点不是“猜中了一个抽象 typing 语义”，而是：

- 一直把 3 条 benchmark 目标测试都留在主线里
- 把 docs failure 也当成**必须消掉的 benchmark 目标**，而不是“无关噪音”

### 9.3 `latest claude / pydantic`：也抓住了目标测试，但更快滑向“更广的 typing 语义解释”

最新版 `claude` 的干净 trace 前半段也不是乱跑，它同样：

1. 一开始就尝试跑两个 docs examples 和 generics test
2. 很快读到 `_generate_schema.py`

但它和 `context` 的分叉点出现在**patch 意图**上。

`latest claude` 当前 patch 不是：

- `NoDefault -> None`

而是把条件改写成：

```diff
- if (bound is not None) + (len(constraints) != 0) + (default is not None) > 1:
+ if bound is not None and constraints:
...
+ has_default = default is not None and default is not NoDefault
```

它在 trace 里还专门跑了：

- `tests/test_generics.py::test_mix_default_and_constraints`

并明确形成了一个更“语义泛化”的判断：

- Python typing 允许 `constraints + default`
- 老逻辑错在把这些组合同样挡掉了

这和 `context` 的差异很大：

- `context` 是围绕 benchmark 给的 3 条测试做最小闭环
- `latest claude` 更快滑向“更广义的 typing 语义修正”

更关键的一点：

- `latest claude` 没有像 `context` 一样去补 `docs/concepts/models.md` 的 black formatting
- 它在最终收口里明确把其中一个 docs failure 说成“pre-existing black formatting issue”

这就意味着：

- 在 query 层，`latest claude` 没有把 3 条 benchmark 目标当成同等重要的 done condition
- 它把其中 1 条归类成了“可以不修的环境/格式问题”

这解释了为什么就算它最终也摸到了 `NoDefault`，仍然不一定会拿到和 `context` 一样的 benchmark outcome。

### 9.4 `context / iterative`：这案子并没有体现“保持主线”

这是一个非常重要的反例。

从干净 trace 看，`context` 在 `iterative` 上并没有守住 `--no-exec` 主线，反而出现了明显的偏航：

1. 早期就出现了对规则的误解：
   - 因为 task 说“不改 tests”，它先试图说服自己不要补 `test_import_url_no_exec`
2. 很快被 `_from_parts` 这条 Python 3.12 兼容线索吸走
3. 最终收口直接变成了：

```diff
- return cls._from_parts(args)
+ return object.__new__(cls)
```

最终 `cli_stdout.log` 也完全围绕 `PathInfo.__new__` 收口。

这说明：

- 不能把 `context` 的成功泛化成“它总能保持主线”
- 至少在 `iterative` 这一案里，它同样会被环境兼容问题劫持主线

### 9.5 `latest claude / iterative`：也被 `_from_parts` 吸引，但没有完全丢掉 `no_exec`

最新版 `claude` 在 `iterative` 上的 trace 也很快进入 `_from_parts` 调查，这是和 `context` 的共性。

但它和 `context` 的不同点是：

- 当前 workspace diff 里，它**同时**保留了 `no_exec` 契约修复和 `path_info.py` 兼容修复

也就是说，它并不是只修 `_from_parts`，而是：

- 一边补 `no_exec=self.args.no_exec`
- 一边补 `repo.imp_url(..., no_exec=False)`
- 一边修 `PathInfo._from_parts`

这说明在 query 级别，它更像是在维持两条子目标并行推进，而不是彻底被兼容问题单线劫持。

### 9.6 现在能不能说是 `snip` 删掉了什么无关内容

仍然**不能**。

原因不是没有 trace，而是：

- 现在拿到的 trace 能看到 request / response body
- 但没有直接标出“哪一段是 history snip 前、哪一段是 snip 后”
- 也没有可直接归因到 `reactive compact` 的显式边界标签

所以现在最严谨的说法是：

- 能从 query 级 trace 看到**是否一直围绕目标测试推进**
- 能看到**是否被环境兼容或更广的语义解释带偏**
- 但仍然不能精确指出“snip 删掉了哪一段无关上下文”

### 9.7 目前最接近根因的话术

如果只围绕 `context` 领先的真实原因，当前最接近事实的话术是：

1. `context` 的领先不是普遍存在，而是几乎全部集中在 `pydantic`。
2. 在 `pydantic` 上，它的 query 级行为确实比 `latest claude` 更贴近 benchmark done condition：
   - 一直抓住 3 条目标测试
   - 把 docs formatting 也当成必须修掉的一部分
3. 但这仍不能脱离环境解释：
   - 同一案里，`typing-extensions` 是否成功升级仍然是决定 patch 能否真正生效的硬前提。
