# Common Issues Summary

当前总结基于 `2026-05-06` 已完成的 `48 / 48` 篇单 case 文档，对应对照 run 为：

- `innercc`: `20260427-154634`
- `claude-code`: `20260429-114027`

如果只看最终一句话，现在最稳定的结论有 5 条：

1. 主矛盾不是“代码生成能力”，而是 `task sizing -> localization -> validation -> termination` 这一整条收敛链经常失真。
2. 全量 `48` 案里最常见的共性问题仍然是：
   - `validation_gap`
   - `task_understanding_error`
   - `hypothesis_lock_in`
3. `innercc` 的典型优势是多簇覆盖能力更强，尤其在 `iterative/dvc`、`dask/dask` 这种 multi-task 或 bundle case 上更容易命中更多目标点；典型代价是 patch 面更宽、回归或环境噪声误修风险更高。
4. `claude-code` 的典型优势是窄任务、强契约、单函数修复更稳；典型代价是大型 release-note case 容易过早锁在第一个 plausible cluster。
5. 真正值得沉淀成 CLI 规则的，不是某个 repo 特有技巧，而是 4 个跨 repo 规则：
   - 先做 F2P 聚类
   - 用失败证据交叉定位
   - 强制 exact F2P + 相邻 P2P 双验证
   - patch 覆盖面和任务规模不匹配时禁止结束

完整综合分析见：

- [cross_case_synthesis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/cross_case_synthesis.md)
- [final_conference_report.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/final_conference_report.md)
- [synthesis_methodology.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/synthesis_methodology.md)

## 1. 覆盖范围

- 已分析 case：`48 / 48`
- 剩余未分析 case：`0`
- 覆盖仓库：
  - `iterative/dvc`: `26`
  - `dask/dask`: `8`
  - `psf/requests`: `4`
  - `modin-project/modin`: `3`
  - `pydantic/pydantic`: `3`
  - `scikit-learn/scikit-learn`: `2`
  - `conan-io/conan`: `2`

## 2. Outcome Families

把全部 `comparison_category` 压缩成更稳定的 outcome family 后，当前 `48` 案可以分成：

- `inner_advantage`: `14`
  - `innercc` resolve，或者虽然双方都没 resolve，但它更接近 benchmark 主轴
- `claude_advantage`: `11`
  - `claude-code` resolve，或者失败时更接近目标簇
- `both_failed`: `11`
  - 两边都没真正对准 benchmark 主体
- `both_partial`: `6`
  - 两边都修到一部分，但仍因漏修或 P2P 回归未 resolve
- `both_resolved`: `6`
  - 当前最干净的参考成功集

这说明最后的全量结论仍然不是“谁绝对更强”，而是：

- `innercc` 与 `claude-code` 在不同任务形状上表现差异明显
- 真正决定结果的，是它们如何缩放任务和收口验证，而不是单一模型能力高低

## 3. 高频共性问题

### 3.1 `validation_gap` 仍然是第一大问题

出现次数：`41 / 48`

典型表现：

- 没有用 exact failing tests 做最终收口
- 只跑局部 probe，没有验证 evaluator 真正关心的行为
- F2P 过后没有检查相邻 P2P
- 使用会吞退出码、截断错误输出或只做表面 smoke test 的命令

代表案例：

- [psf__requests_v2.12.2_v2.12.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/psf__requests_v2.12.2_v2.12.3_analysis.md)
- [iterative__dvc_2.58.1_2.58.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.58.1_2.58.2_analysis.md)
- [scikit-learn__scikit-learn_0.21.1_0.21.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/scikit-learn__scikit-learn_0.21.1_0.21.2_analysis.md)

### 3.2 `task_understanding_error` 是第二大结构性问题

出现次数：`30 / 48`

补数据：

- 这 `30` 案里，`29` 案同时带有 `validation_gap`，`19` 案同时带有 `hypothesis_lock_in`
- 这 `30` 案的 `FAIL_TO_PASS` 中位数是 `12`；其中 `16 / 30` 案有 `>=10` 条 F2P，`9 / 30` 案有 `>=50` 条
- 但它不是“大题专属”问题；仍有 `7 / 30` 案只有 `<=2` 条 F2P，说明“小题被显眼 clue 带偏”同样常见

典型表现：

- 把 multi-task case 错当成 single-point bug
- 把大型 release bundle 错缩成一个显眼的 compatibility symptom
- 过度相信 release note 某一句显眼描述，而不是让 `FAIL_TO_PASS` 主导任务边界

具体看，当前至少稳定出现 3 种表现：

1. 大 bundle 被缩成一个显眼症状
   - [dask__dask_2024.1.0_2024.1.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.1.0_2024.1.1_analysis.md)：`2774` 条 F2P 被缩成单个 NumPy / property 兼容点
   - [iterative__dvc_2.8.1_2.8.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.8.1_2.8.2_analysis.md)：`133` 条 F2P 的 bundle 被压成 `azure/http` 局部 compat
2. 两簇或多簇任务只修到一半
   - [iterative__dvc_3.4.0_3.5.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.4.0_3.5.0_analysis.md)：真实目标是 `api.get_url` 和 `fetch --type` 两条线，`claude-code` 只抓住一半
   - [pydantic__pydantic_v2.7.0_v2.7.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/pydantic__pydantic_v2.7.0_v2.7.1_analysis.md)：多个独立 fix 混在一份 release note 里，`claude-code` 只修到很小一部分
3. benchmark 真目标被显眼 release-note 条目或环境噪声替代
   - [iterative__dvc_0.89.0_0.90.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_0.89.0_0.90.0_analysis.md)：真目标是 `HTTPURLInfo`、protected mode、`gc -c`，两边都被 `pathlib` 噪声带偏
   - [pydantic__pydantic_v2.7.1_v2.7.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/pydantic__pydantic_v2.7.1_v2.7.2_analysis.md)：只有 `3` 条 F2P，但两边都被 `TypeVar.__default__ == NoDefault` 这条显眼线索锁死

代表案例：

- [dask__dask_2024.1.0_2024.1.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.1.0_2024.1.1_analysis.md)
- [iterative__dvc_2.8.1_2.8.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.8.1_2.8.2_analysis.md)
- [iterative__dvc_3.43.1_3.44.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.43.1_3.44.0_analysis.md)

### 3.3 `hypothesis_lock_in` 紧随其后

出现次数：`27 / 48`

典型表现：

1. 很快锁定第一个“看起来像”的解释。
2. 后续 grep、读代码、probe 全围绕这个解释转。
3. 即使 evaluator 反证、golden patch 或最深项目帧已经出现，也不重置定位。

代表案例：

- [dask__dask_2024.3.1_2024.4.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.3.1_2024.4.0_analysis.md)
- [iterative__dvc_2.21.1_2.21.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.21.1_2.21.2_analysis.md)
- [iterative__dvc_3.13.3_3.14.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.13.3_3.14.0_analysis.md)

## 4. 次级但重要的问题

### 4.1 `localization_error`

出现次数：`11 / 48`

补数据：

- `11 / 11` 同时带有 `validation_gap`，`9 / 11` 同时带有 `hypothesis_lock_in`
- 这 `11` 案的 `FAIL_TO_PASS` 全都 `<=9`，其中 `8 / 11` 只有 `<=2` 条，说明 localization error 多发生在“任务规模已经不大，但最后一跳落错层”的场景
- 所以它多数不是“已经 locate 到了，后面忘了”，而是从一开始就停在了相邻层 / 相邻对象 / 相邻契约；只有 `2 / 11` 案更像“找到一条支线后没有继续扩到第二条”

典型表现：

- patch 落在相邻层而不是真实故障层
- 测试契约关心调用签名，patch 却只改内部语义
- 失败断言指向具体对象/字段，patch 却改到相邻对象

更细分的场景：

- 相邻函数 / 相邻对象修偏：
  - [dask__dask_2024.3.1_2024.4.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.3.1_2024.4.0_analysis.md)：修到了 `_value_counts`，真实故障层在 `_value_counts_aggregate`
  - [iterative__dvc_0.35.3_0.35.4_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_0.35.3_0.35.4_analysis.md)：入口处 `exists()/lexists()` 命中了一半，真正剩余故障在 `get_mtime_and_size()`
  - [modin-project__modin_0.24.0_0.24.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/modin-project__modin_0.24.0_0.24.1_analysis.md)：锁在 row/column cache，真实失败对象是 `_column_widths_cache`
- 外部契约和内部语义错层：
  - [iterative__dvc_1.0.0b6_1.0.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.0.0b6_1.0.0_analysis.md)：测试关心 `no_exec` 外部契约，`innercc` 却把语义映射回旧的 `dry`
  - [iterative__dvc_1.0.1_1.0.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.0.1_1.0.2_analysis.md)：`git-hook` 控制流和 `run --file` 报错语义分属两层，`claude-code` 两层都没对齐
  - [iterative__dvc_1.6.3_1.6.4_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.6.3_1.6.4_analysis.md)：command 层测通了，但 repo-level experiment 语义仍然修错
- 确实有“找到一条支线、漏掉第二条”的少数情况：
  - [iterative__dvc_1.1.7_1.1.8_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.1.7_1.1.8_analysis.md)
  - [iterative__dvc_2.7.2_2.7.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.7.2_2.7.3_analysis.md)

细节展开：

- 代表案：[dask__dask_2024.3.1_2024.4.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.3.1_2024.4.0_analysis.md)
- 为什么它最典型：
  - 这是一个只有 `2` 条 F2P 的小题
  - agent 已经把问题空间收得很小，也确实读到了正确层
  - 但最后 edit 仍然落在相邻函数 `_value_counts`，而不是 ground truth 的 `_value_counts_aggregate`
- trace 证据：
  - [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/dask__dask_2024.3.1_2024.4.0/router_trace_bundle.json)
  - trace `020-023`：已经读到 `_value_counts`、`_value_counts_aggregate` 和外围 flow
  - trace `027-076`：后面几十步的本地模拟基本都围绕“all-NaN partition 在 `_value_counts` 本地该怎么返回”
  - trace `088` 和 `093`：最终 edit 还是落在 `_value_counts`
  - trace `097`：结束时明确把 fix 定义成“在 `_value_counts` 里加 all-NaN guard”
- patch 证据：
  - [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/dask__dask_2024.3.1_2024.4.0/patch.diff)

```diff
def _value_counts(x, **kwargs):
    ...
    elif len(x.obj) == 0 or x.obj.isna().all():
        return pd.Series(dtype=int)
```

- ground truth 对照：
  - [official48_source/output_final/dask__dask_2024.3.1_2024.4.0.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_source/output_final/dask__dask_2024.3.1_2024.4.0.json)

```diff
def _value_counts_aggregate(series_gb):
    data = {k: v.groupby(level=-1).sum() for k, v in series_gb}
    if not data:
        data = [pd.Series(index=series_gb.obj.index[:0], dtype="float64")]
```

- evaluator 证据：
  - [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/dask__dask_2024.3.1_2024.4.0/run_instance.log)

```text
FAIL_TO_PASS failure:
- dask/dataframe/tests/test_groupby.py::test_groupby_value_counts_all_na_partitions[disk]
- dask/dataframe/tests/test_groupby.py::test_groupby_value_counts_all_na_partitions[tasks]
```

- 这题能直接回答你前面的追问：
  - 它不是“已经 locate 到了，后面忘了”
  - 而是读过正确层之后，仍然被局部模拟结果锁回了相邻函数
  - 所以真正缺的是 edit 前的层级交叉校验，而不是更多搜索量

### 4.2 `termination_error`

出现次数：`6 / 48`

补数据：

- `6 / 6` 同时带有 `task_understanding_error` 和 `validation_gap`
- 这 `6` 案的 `FAIL_TO_PASS` 中位数是 `40.5`；`4 / 6` 案有 `>=13` 条 F2P，`3 / 6` 案有 `>=68` 条
- 所以它不是 timeout 的同义词，而是“证据明显不够，但系统已经判定 done”；[iterative__dvc_0.91.2_0.91.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_0.91.2_0.91.3_analysis.md) 只有 `2` 条 F2P 也会中招，说明小题一样会因为交付物错位或局部通过而提前结束

典型表现：

- 任务规模远大于 patch 覆盖面时提前结束
- 因某个局部 probe 或表面 smoke test 通过就直接收工

具体例子：

- [dask__dask_2023.6.0_2023.6.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2023.6.0_2023.6.1_analysis.md)：`105` 条 F2P 的题被 `10` 行级兼容修补后就结束
- [dask__dask_2024.1.0_2024.1.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.1.0_2024.1.1_analysis.md)：`2774` 条 F2P 的整包任务被单一 compat hypothesis 取代
- [iterative__dvc_3.13.3_3.14.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.13.3_3.14.0_analysis.md)：`expanduser` 的局部补丁或空 patch 都被当成“可以交付”
- [pydantic__pydantic_v2.7.1_v2.7.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/pydantic__pydantic_v2.7.1_v2.7.2_analysis.md)：对 `TypeVar` 噪声做了大量局部验证，却没有回到真实的 `3` 条 F2P

细节展开：

- 代表案：[pydantic__pydantic_v2.7.1_v2.7.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/pydantic__pydantic_v2.7.1_v2.7.2_analysis.md)
- 为什么它最适合解释 termination：
  - 这题不是 timeout，也不是完全没验证
  - 相反，它做了不少局部验证，但 done condition 还是错了
- trace 证据：
  - [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/pydantic__pydantic_v2.7.1_v2.7.2/router_trace_bundle.json)
  - trace `001-006`：起手其实跑了 docs examples 和 generics 目标测试
  - trace `012-017`：很快锁定 `TypeVar.__default__ == NoDefault`
  - trace `018-019`：唯一 edit 落在 `_generate_schema.py`
  - trace `020-021`：generics test 一过，就开始把核心问题视为已解决
  - trace `023-024`：docs examples 不再用 exact target test 收口，而是改成手写 Python snippet
  - trace `026`：把 broader failure 解释成“与当前修复无关”
  - trace `029`：最终明确宣告 patch “clean and minimal”
- patch 证据：
  - [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/pydantic__pydantic_v2.7.1_v2.7.2/patch.diff)

```diff
-        if (bound is not None) + (len(constraints) != 0) + (default is not None) > 1:
+        if (bound is not None) + (len(constraints) != 0) + (default not in (None, NoDefault)) > 1:
...
-        if default is not None:
+        if default not in (None, NoDefault):
```

- evaluator 证据：
  - [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/pydantic__pydantic_v2.7.1_v2.7.2/report.json)

```text
FAIL_TO_PASS failure:
- tests/test_docs.py::test_docs_examples[docs/concepts/models.md:1049-1079]
- tests/test_docs.py::test_docs_examples[docs/concepts/models.md:952-982]
- tests/test_generics.py::test_serialize_unsubstituted_typevars_bound_default_supported
```

- 这里的 termination error 本质上是：
  - 局部证据给了 agent 足够强的心理确定感
  - 但这些证据并不等价于 benchmark target 已经收口
  - 所以后面的 final summary 会非常自信，甚至把剩余失败标成 unrelated noise

### 4.3 `tooling_or_harness_issue`

出现次数：`3 / 48`

典型表现：

- patch artifact 为空
- 评测与工作区状态错位
- 环境级噪声被错误吸收进 patch

## 5. 现在最重要的失败模式

### 5.1 Bundle collapse

定义：

- benchmark 本质是 bundle case
- agent 却把它缩成一两个显眼兼容点或单条 feature

代表案例：

- [dask__dask_2024.1.0_2024.1.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.1.0_2024.1.1_analysis.md)
- [iterative__dvc_2.8.1_2.8.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.8.1_2.8.2_analysis.md)
- [conan-io__conan_2.0.14_2.0.15_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/conan-io__conan_2.0.14_2.0.15_analysis.md)

细节展开：

- 代表案：[dask__dask_2024.1.0_2024.1.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.1.0_2024.1.1_analysis.md)
- 为什么它最典型：
  - `FAIL_TO_PASS = 2774`
  - `PASS_TO_PASS = 5778`
  - 但 `innercc` 最终 patch 只有 `dask/utils.py` 一个小 hunk
- trace 证据：
  - [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/dask__dask_2024.1.0_2024.1.1/router_trace_bundle.json)
  - trace `004`：先跑 `test_A_property`
  - trace `008-024`：连续十几步都在做 `inspect.signature` / pandas property probe
  - trace `025`：唯一 edit 落在 `dask/utils.py`
  - trace `038`：给出“`All 445 tests in test_array_core.py pass.`”
  - trace `039`：最终把问题收束成 `dask/utils.py` 的 Python 3.12 import error
- patch 证据：
  - [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/dask__dask_2024.1.0_2024.1.1/patch.diff)

```diff
-    except ValueError:
+    except (ValueError, TypeError):
```

- evaluator 证据：
  - [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/dask__dask_2024.1.0_2024.1.1/run_instance.log)

```text
report: ... 'resolved': False ... 'FAIL_TO_PASS': {'success': [], 'failure': [...]}, 'PASS_TO_PASS': {'success': [], 'failure': [...]}
Result for dask__dask_2024.1.0_2024.1.1: resolved: False
```

- 这个 pattern 的关键不是“agent 没探索”，而是“探索很勤，但任务边界从第一轮就收缩错了”

### 5.2 Partial coverage

定义：

- agent 方向不是全错
- 但只修到了多个目标簇中的一部分

代表案例：

- [dask__dask_2023.9.2_2023.9.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2023.9.2_2023.9.3_analysis.md)
- [iterative__dvc_3.4.0_3.5.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.4.0_3.5.0_analysis.md)
- [iterative__dvc_2.58.1_2.58.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.58.1_2.58.2_analysis.md)

细节展开：

- 代表案：[iterative__dvc_2.58.1_2.58.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.58.1_2.58.2_analysis.md)
- ground truth 要求两件事同时成立：
  - `pull=True` 遇到 `RunCacheNotSupported` 仍继续
  - `run_cache=False` 时根本不该 pull run cache
- ground truth hunk：
  - [official48_source/output_final/iterative__dvc_2.58.1_2.58.2.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_source/output_final/iterative__dvc_2.58.1_2.58.2.json)

```diff
-    if kwargs.get("pull", False):
+    if kwargs.get("pull", False) and kwargs.get("run_cache", True):
         logger.debug("Pulling run cache")
-        self.stage_cache.pull(None)
+        try:
+            self.stage_cache.pull(None)
+        except RunCacheNotSupported as e:
+            logger.warning("Failed to pull run cache: %s", e)
```

- trace 证据：
  - [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.58.1_2.58.2/router_trace_bundle.json)
  - trace `001-017`：围绕 `RunCacheNotSupported` 和 `stage_cache.pull()` 做定位
  - trace `018-023`：同时编辑 `dvc/repo/reproduce.py` 和 `dvc/repo/fetch.py`
  - trace `037`：最终总结把自己描述成 “fix has been implemented”
- patch 证据：
  - [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.58.1_2.58.2/patch.diff)
  - `reproduce.py` 里补了 `try/except RunCacheNotSupported`
  - 但缺了最关键的 `and kwargs.get("run_cache", True)` 条件
  - 还顺手扩散去改了 `fetch.py`
- evaluator 证据：
  - [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.58.1_2.58.2/report.json)

```text
FAIL_TO_PASS success:
- tests/func/test_repro_multistage.py::test_repro_pulls_continue_without_run_cache

FAIL_TO_PASS failure:
- tests/func/test_repro_multistage.py::test_repro_skip_pull_if_no_run_cache_is_passed
```

- 这就是典型的“方向没全错，但只修了一半目标语义”

### 5.3 Wrong-target repair

定义：

- agent 修了一个真实问题
- 但不是 benchmark 当前选中的目标问题

代表案例：

- [iterative__dvc_0.33.1_0.34.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_0.33.1_0.34.0_analysis.md)
- [iterative__dvc_3.43.1_3.44.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.43.1_3.44.0_analysis.md)
- [iterative__dvc_2.7.2_2.7.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.7.2_2.7.3_analysis.md)

细节展开：

- 代表案：[iterative__dvc_0.33.1_0.34.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_0.33.1_0.34.0_analysis.md)
- 这题的 `FAIL_TO_PASS` 其实只有一条：`tests/test_tag.py::TestTag::test`
- trace 证据：
  - [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.33.1_0.34.0/router_trace_bundle.json)
  - trace `011-017`：确实搜过 `tests/test_tag.py` 和 tag 相关代码
  - trace `025`：给出强结论“`dvc/cli.py` 里 `add` command 重复注册”
  - trace `034`：直接跑了 `python3 -m pytest tests/test_tag.py::TestTag::test -v`
  - trace `041`：即使 exact failing test 没打通，最后仍然收工
- patch 证据：
  - [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.33.1_0.34.0/patch.diff)

```diff
-    add,
```

- evaluator 证据：
  - [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.33.1_0.34.0/report.json)

```text
FAIL_TO_PASS failure:
- tests/test_tag.py::TestTag::test
```

  - [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.33.1_0.34.0/test_output.txt)

```text
FAILED tests/test_tag.py::TestTag::test - AssertionError: 254 != 0
```

- 这类 case 的危险点是：
  - agent 其实已经碰到了 exact failing test
  - 但没有用结果去重置目标，而是继续沿“真实但错靶”的 bug 收尾

### 5.4 F2P fixed but neighboring semantics regressed

代表案例：

- [psf__requests_v2.9.0_v2.9.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/psf__requests_v2.9.0_v2.9.1_analysis.md)
- [scikit-learn__scikit-learn_0.20.1_0.20.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/scikit-learn__scikit-learn_0.20.1_0.20.2_analysis.md)
- [scikit-learn__scikit-learn_0.21.1_0.21.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/scikit-learn__scikit-learn_0.21.1_0.21.2_analysis.md)

细节展开：

- 代表案：[psf__requests_v2.9.0_v2.9.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/psf__requests_v2.9.0_v2.9.1_analysis.md)
- 为什么它最典型：
  - 目标 F2P `test_binary_put` 确实修通了
  - 但共享函数 `_encode_params()` 的相邻语义路径被一起打坏
- trace 证据：
  - [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/psf__requests_v2.9.0_v2.9.1/router_trace_bundle.json)
  - trace `012-015`：明确分析 `_encode_params` 同时服务 body path 和 URL params path
  - trace `015`：把 `requests/models.py` 改成 `if isinstance(data, (str, bytes)): return data`
  - trace `017-021`：后续验证基本都围绕 binary body
  - trace `039`：最终总结已经把“两处 fix 都完成”当成 case closed
- patch 证据：
  - [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/psf__requests_v2.9.0_v2.9.1/patch.diff)

```diff
-            return to_native_string(data)
+            return data
```

- evaluator 证据：
  - [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/psf__requests_v2.9.0_v2.9.1/run_instance.log)

```text
FAIL_TO_PASS success:
- test_requests.py::TestRequests::test_binary_put

PASS_TO_PASS failure:
- test_requests.py::TestRequests::test_params_bytes_are_encoded
```

  - [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/psf__requests_v2.9.0_v2.9.1/test_output.txt)

```text
TypeError: Cannot mix str and non-str arguments
```

- 这类 case 最能说明：
  - F2P 过了不等于共享函数周围的语义安全
  - 如果 patch 改的是公共入口函数，必须补邻近调用路径的 smoke

## 6. 当前可以下的 CLI 风格结论

### 6.1 `innercc`

优势：

- 更愿意扩大搜索面
- 更容易同时碰多个子任务
- 在多簇命中型 case 上更容易接近官方主轴

代价：

- patch 更宽
- 更容易被环境噪声或相邻 feature 误导后一路扩散
- 一旦修偏，更容易带来 P2P 大面积回归

### 6.2 `claude-code`

优势：

- 单点、窄 patch、强契约 case 更稳
- 更少出现“明显写坏源码”式错误

代价：

- 大 bundle case 上更容易过早锁定单一簇
- 典型失败方式不是“写坏”，而是“修得太窄、修到一半”

## 7. 覆盖率策略补充

直接把“每次 edit 后都 full coverage”设成默认值并不合适。

- 全量 `48` 案里，`FAIL_TO_PASS` 中位数只有 `4`；`27 / 48` 案 `<=5`，`32 / 48` 案 `<=10`。这意味着 exact F2P gate 通常不重。
- 但 `PASS_TO_PASS` 中位数是 `106.5`；`13 / 48` 案 `>=500`，`9 / 48` 案 `>=1000`，最大值 `6246`。如果每次局部 edit 后都全量 cover，成本会迅速失控。
- 更合理的迭代逻辑是三层：
  1. 每次 candidate patch 后先跑 exact F2P
  2. 准备结束前，补 touched modules 的相邻 P2P smoke
  3. patch 稳定后，再交给当前 pipeline 的 case-level evaluator
- 当前仓库已经有 case 粒度的增量评测链路：[run_official48_eval_worker.py](/home/wt/sss_repos/sss_auto/SWE-EVO/run_official48_eval_worker.py) 会轮询 `inference_summary.json` 并调用 [SWE-bench/evaluate_instance.py](/home/wt/sss_repos/sss_auto/SWE-EVO/SWE-bench/evaluate_instance.py)。它适合“推理完成后的增量判分”，但还不是 agent 自身的 in-loop validator。

## 8. 当前最值得固化的 CLI 规则

1. 先按 `FAIL_TO_PASS` 聚类，再决定任务是 `single-point`、`multi-task` 还是 `bundle`。
2. 用 evaluator 失败断言、最深项目帧、golden patch hunk 做三线交叉定位。
3. exact failing tests 和相邻 P2P smoke 必须同时作为硬 gate。
4. patch 覆盖面明显小于任务规模时，禁止结束。
5. 环境噪声与 benchmark 主目标必须分离；不能因为兼容报错显眼就自动升格为主修复目标。

## 9. 推荐阅读顺序

1. [cross_case_synthesis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/cross_case_synthesis.md)
2. [synthesis_methodology.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/synthesis_methodology.md)
3. 正例：
   - [modin-project__modin_0.27.0_0.27.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/modin-project__modin_0.27.0_0.27.1_analysis.md)
   - [iterative__dvc_1.11.12_1.11.13_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.11.12_1.11.13_analysis.md)
   - [iterative__dvc_3.15.0_3.15.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.15.0_3.15.1_analysis.md)
4. 典型失败：
   - [dask__dask_2024.1.0_2024.1.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.1.0_2024.1.1_analysis.md)
   - [iterative__dvc_2.8.1_2.8.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.8.1_2.8.2_analysis.md)
   - [iterative__dvc_3.43.1_3.44.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.43.1_3.44.0_analysis.md)
