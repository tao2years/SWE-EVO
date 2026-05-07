# SWE-EVO Official48 双 CLI 全量失效机理分析报告

## 摘要

本文对 SWE-EVO `official48` 基准上的两组 CLI 运行结果进行全量复盘分析，覆盖 `48/48` 个 benchmark case，并建立统一的单案复盘与跨案综合框架。研究对象为 `innercc` 与 `claude-code` 两条 CLI 路径，对照 run 分别为 `20260427-154634` 与 `20260429-114027`。我们基于 benchmark 原始任务定义、官方 golden patch、agent 推理轨迹、单案补丁、评测日志与最终 `report.json`，从任务理解、故障定位、代码编辑、验证闭环与结束策略五个阶段重建完整证据链。结果表明：全量 `48` 案中，最频繁的共性问题不是代码生成能力不足，而是任务收敛机制失效，具体表现为 `validation_gap`、`task_understanding_error` 与 `hypothesis_lock_in` 的高频组合。`innercc` 更擅长在 multi-task 与 bundle case 中进行多簇覆盖，但更容易出现 patch 扩散与环境噪声误修；`claude-code` 在单点、强契约、窄 patch 任务上更稳，但在大型 release-note case 中更容易过早锁定单一簇并提前结束。本文进一步抽象出一组可推广的 CLI 级优化规则，包括任务规模判定、exact F2P 与相邻 P2P 双门槛验证、三线交叉定位以及环境噪声降权策略。这些结论可直接服务于后续 agent 设计、评测协议改进与回归集构建。

如果需要把这些结论继续下钻到“单个 failure pattern 的代表案、关键 trace index、patch 落点和 evaluator log”，现在细节都已经并回：

- [common_issues_summary.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/common_issues_summary.md)

**关键词**：SWE-EVO；LLM agent；benchmark analysis；failure analysis；task sizing；validation

## 1. 研究背景与问题定义

面向软件演化任务的 LLM agent 评测，已经不再只关心最终是否通过 benchmark，而更关心 agent 在复杂工程环境中的收敛路径是否稳定、可解释、可优化。对这类系统而言，仅凭 “resolved 数量” 无法回答以下问题：

1. agent 失败时究竟是没理解任务、修错层、写坏代码，还是验证没有收口。
2. 多个 CLI 之间的差异来自模型能力，还是来自任务分解、工具使用与结束策略。
3. 哪些失败是个别 repo 特例，哪些已经足够稳定，值得上升成通用工程规则。

为回答这些问题，我们围绕 `official48` 全量构建了逐案分析体系，并进一步形成跨案综合报告。本文关注三个研究问题：

- **RQ1**：在全量 `48` 案中，失败主要集中在哪些执行阶段与失效类型？
- **RQ2**：`innercc` 与 `claude-code` 的系统差异体现在哪些任务形状上？
- **RQ3**：从软件工程与 agent 设计角度，哪些规则最值得沉淀为下一轮优化项？

## 2. 数据、对象与方法

### 2.1 数据来源

本文使用的主要证据全部来自本地评测环境：

- benchmark 输入：`official48_source/output_final/<instance_id>.json`
- `innercc` run：`official48_runs/20260427-154634`
- `claude-code` run：`official48_runs/20260429-114027`
- 单案推理产物：
  - `patch.diff`
  - `cli_result.json`
  - `router_trace_bundle.json`
- 单案评测产物：
  - `report.json`
  - `test_output.txt`
  - `run_instance.log`

### 2.2 单案分析框架

每个 case 都按统一结构分析：

1. `Case Metadata`
2. `Task And Gold Spec`
3. `Outcome Comparison`
4. `Artifact Index`
5. `Chronological Trace Reconstruction`
6. `Hypothesis Iteration Log`
7. `Patch And Code-Level Analysis`
8. `Evaluation And Failure Evidence`
9. `Root Cause`
10. `CLI Optimization Opportunities`

这一框架的关键是三线合证：

- **任务线**：benchmark task / runner query / official golden answer
- **轨迹线**：agent 在每一步读了什么、搜了什么、改了什么、如何改写内部目标
- **评测线**：evaluator 最终到底因何判定通过、未解或回归

### 2.3 综合分析方法

在全量 `48` 篇单案文档基础上，本文进一步做：

- `comparison_category` 到 outcome family 的压缩
- 根因标签统计
- 执行阶段映射
- task shape 分析
- CLI 风格差异归纳
- 优化项排序

## 3. 全量结果概览

### 3.1 覆盖范围

当前已完成：

- 单案报告：`48 / 48`
- 覆盖仓库：
  - `iterative/dvc`: `26`
  - `dask/dask`: `8`
  - `psf/requests`: `4`
  - `modin-project/modin`: `3`
  - `pydantic/pydantic`: `3`
  - `scikit-learn/scikit-learn`: `2`
  - `conan-io/conan`: `2`

### 3.2 Outcome Family 分布

将所有 `comparison_category` 压缩为更稳定的 family 后：

- `inner_advantage`: `14`
- `claude_advantage`: `11`
- `both_failed`: `11`
- `both_partial`: `6`
- `both_resolved`: `6`

这个结果有两个直接含义：

1. 没有哪一方在全量样本上形成压倒性优势。
2. 全量中最大的单一群体并不是“某一方全面成功”，而是：
   - 双方都未真正解对任务，或者
   - 一方更接近主轴，但仍未 resolve

### 3.3 最高频标签

全量标签频次如下：

- `validation_gap`: `41`
- `task_understanding_error`: `30`
- `hypothesis_lock_in`: `27`
- `localization_error`: `11`
- `reference_success_path`: `6`
- `termination_error`: `6`
- `tooling_or_harness_issue`: `3`

这一分布说明，失败首先是“收敛机制”问题，其次才是“代码修得不对”问题。

## 4. RQ1：失败主要集中在哪些阶段？

### 4.1 Task Sizing / Scoping 是首要矛盾

这是全量样本中最重要的失败源头。

如果用 case-level root-cause tag 落地，至少 `30 / 48` 个 case 含 `task_understanding_error`。其中 `29 / 30` 同时伴随 `validation_gap`，`19 / 30` 同时伴随 `hypothesis_lock_in`。从 benchmark 体量看，这 `30` 案的 `FAIL_TO_PASS` 中位数是 `12`：`16 / 30` 有 `>=10` 条 F2P，`9 / 30` 有 `>=50` 条，但也有 `7 / 30` 只有 `<=2` 条。这说明 task sizing/scoping 的失真主要在中大题上爆发，但“小题被显眼 clue 带偏”同样不可忽视。

典型现象包括：

- `FAIL_TO_PASS` 明明覆盖多个模块，agent 却按单点 bug 在修。
- release note 明显是 bundle，但 agent 没先做目标聚类。
- patch 覆盖面明显低于官方 patch 规模与 F2P 体量。

更具体地说，这类错误至少稳定表现为 3 种形式：

- bundle / multi-cluster case 被收缩成单个 compatibility symptom
- 双分支或多分支任务只修了一半
- benchmark 真目标被 release note 显眼条目或环境噪声替代

代表案例：

- [dask__dask_2024.1.0_2024.1.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.1.0_2024.1.1_analysis.md)
- [iterative__dvc_2.8.1_2.8.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.8.1_2.8.2_analysis.md)
- [iterative__dvc_3.43.1_3.44.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.43.1_3.44.0_analysis.md)

### 4.2 Fault Localization 紧随其后

第二高风险阶段是故障定位。

从标签看，`localization_error` 出现在 `11 / 48` 个 case 中，且 `11 / 11` 都伴随 `validation_gap`，`9 / 11` 伴随 `hypothesis_lock_in`。和 task sizing 相反，这类 case 的 `FAIL_TO_PASS` 全都 `<=9`，其中 `8 / 11` 只有 `<=2` 条，说明它更多发生在“任务规模已经缩小，但最后一跳落错层”的场景，而不是超大 bundle 根本搜不动。

典型问题有：

- evaluator 最深项目帧与 patch 落点不一致
- 测试契约关心外部 API / 参数签名，patch 却只改内部语义
- 失败断言指向某个具体字段，patch 却改到相邻对象

进一步看，可以稳定拆成 3 种偏移：

- 相邻函数 / 相邻对象修偏：
  - [dask__dask_2024.3.1_2024.4.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.3.1_2024.4.0_analysis.md)
  - [iterative__dvc_0.35.3_0.35.4_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_0.35.3_0.35.4_analysis.md)
  - [modin-project__modin_0.24.0_0.24.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/modin-project__modin_0.24.0_0.24.1_analysis.md)
- 外部契约和内部语义错层：
  - [iterative__dvc_1.0.0b6_1.0.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.0.0b6_1.0.0_analysis.md)
  - [iterative__dvc_1.0.1_1.0.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.0.1_1.0.2_analysis.md)
  - [iterative__dvc_1.6.3_1.6.4_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.6.3_1.6.4_analysis.md)
- 少数确实像“找到一条支线，第二条没继续扩”的 case：
  - [iterative__dvc_1.1.7_1.1.8_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.1.7_1.1.8_analysis.md)
  - [iterative__dvc_2.7.2_2.7.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.7.2_2.7.3_analysis.md)

代表案例：

- [dask__dask_2024.3.1_2024.4.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.3.1_2024.4.0_analysis.md)
- [iterative__dvc_1.0.0b6_1.0.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.0.0b6_1.0.0_analysis.md)
- [iterative__dvc_2.58.1_2.58.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.58.1_2.58.2_analysis.md)

### 4.3 Validation 不是配角，而是最高频放大器

`41/48` 案出现 `validation_gap`，这说明很多错误本来应该更早暴露。最常见的闭环缺口有：

1. 没有 exact failing tests gate
2. 没有相邻 P2P smoke gate
3. 没有 patch-vs-target 覆盖率 gate
4. 没有语法 / import smoke gate

尤其值得强调的是：许多 case 不是“完全没跑测试”，而是跑了与 benchmark 主体无关、或过于表面的验证。

这也解释了为什么“不加区分地 full coverage”不是合理默认值。全量 `48` 案的 `FAIL_TO_PASS` 中位数只有 `4`，`27 / 48` 案 `<=5`，`32 / 48` 案 `<=10`，所以 exact F2P gate 通常是便宜的；但 `PASS_TO_PASS` 中位数是 `106.5`，`13 / 48` 案 `>=500`，`9 / 48` 案 `>=1000`，最大值 `6246`，因此每次局部编辑后都跑完整 P2P / full evaluator 会很重。更合理的是三层闭环：先 exact F2P，再 touched-module 邻近 P2P smoke，最后在 patch 稳定后交给当前 pipeline 的 case-level evaluator。

当前仓库已经有 post-inference 的增量评测链路：[run_official48_eval_worker.py](/home/wt/sss_repos/sss_auto/SWE-EVO/run_official48_eval_worker.py) 会轮询 `inference_summary.json` 并调用 [SWE-bench/evaluate_instance.py](/home/wt/sss_repos/sss_auto/SWE-EVO/SWE-bench/evaluate_instance.py)。它解决的是“每题完成后尽快判分”，还不是 agent 自身的 in-loop 迭代验证。

### 4.4 Termination error 频次虽低，但代价极高

`termination_error` 只有 `6` 次，但几乎都出现在最重的 bundle case 上。

从数据看，`termination_error` 的 `6` 案全部同时带有 `task_understanding_error` 和 `validation_gap`。它们的 `FAIL_TO_PASS` 中位数是 `40.5`，其中 `4 / 6` 有 `>=13` 条 F2P，`3 / 6` 有 `>=68` 条；唯一的小题例外是 [iterative__dvc_0.91.2_0.91.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_0.91.2_0.91.3_analysis.md)，它的问题也不是“时间不够”，而是交付物错位后仍被当成完成。这说明 termination error 不是 timeout 的同义词，而是 done-condition 失真。

其共性是：

- patch 面积远小于任务规模
- 某个局部 probe 或局部 test 通过后就提前结束

这种错误频次不高，却是最影响 resolved 上限的一类。

## 5. RQ2：两个 CLI 的系统差异是什么？

### 5.1 `innercc`：多簇覆盖能力更强

`innercc` 的优势不是“更稳”，而是“更愿意扩展搜索面”。它的典型正面模式是：

- 更容易同时碰多个目标簇
- 在 multi-task / bundle case 上更愿意继续往下挖
- 在需要跨多个子系统共同命中的任务上更接近官方主轴

代表案例：

- [dask__dask_2023.9.2_2023.9.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2023.9.2_2023.9.3_analysis.md)
- [iterative__dvc_3.4.0_3.5.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.4.0_3.5.0_analysis.md)
- [iterative__dvc_2.19.0_2.20.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.19.0_2.20.0_analysis.md)

### 5.2 `innercc` 的代价：更容易扩散

`innercc` 的主要风险也来自这一特性：

- patch 面更宽
- 更容易吸收环境噪声或相邻 feature 误修
- 一旦修偏，更容易带来大面积 P2P 回归

代表案例：

- [iterative__dvc_1.0.0a1_1.0.0a2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.0.0a1_1.0.0a2_analysis.md)
- [iterative__dvc_3.43.1_3.44.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.43.1_3.44.0_analysis.md)

### 5.3 `claude-code`：窄任务与强契约更稳

`claude-code` 的优势主要体现在：

- 单点、窄 patch、强契约任务
- 参数签名、调用约束、返回格式这类外部行为契约
- 更少出现明显“写坏源码”的编辑问题

代表案例：

- [iterative__dvc_1.0.0b6_1.0.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.0.0b6_1.0.0_analysis.md)
- [psf__requests_v2.12.2_v2.12.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/psf__requests_v2.12.2_v2.12.3_analysis.md)
- [iterative__dvc_1.11.12_1.11.13_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.11.12_1.11.13_analysis.md)

### 5.4 `claude-code` 的代价：过早锁在单一簇

在大 bundle case 中，`claude-code` 的典型失败模式不是“写坏”，而是：

- 太快锁定第一个 plausible cluster
- 太早把局部 feature 实现当成整体任务完成
- 最终表现为“修得很像，但修得太窄”

代表案例：

- [modin-project__modin_0.25.0_0.25.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/modin-project__modin_0.25.0_0.25.1_analysis.md)
- [iterative__dvc_2.8.1_2.8.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.8.1_2.8.2_analysis.md)
- [iterative__dvc_3.43.1_3.44.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.43.1_3.44.0_analysis.md)

## 6. RQ3：哪些优化项最值得固化？

### 6.1 P0：Task sizing gate

这是最优先的规则。

建议：

1. 在前几步先统计 `FAIL_TO_PASS` 数量与模块分布。
2. 根据分布将任务分类为 `single-point`、`multi-task` 或 `bundle`。
3. 若 patch 覆盖面明显低于任务体量，禁止结束。

这条规则能同时削弱：

- `task_understanding_error`
- `hypothesis_lock_in`
- `termination_error`

### 6.2 P0：Exact F2P + Adjacent P2P 双门槛

建议：

1. exact failing tests 必须通过
2. patch 直接覆盖模块必须补相邻 P2P smoke

这条规则针对的是全量最高频标签 `validation_gap`。

### 6.3 P0：Localization cross-check

进入编辑前，至少交叉核对三类证据：

1. evaluator 最深项目帧
2. failing assertion / test contract
3. golden patch 关键 hunk

任何只靠 release note 文本完成的定位，都应当被视为低置信候选。

### 6.4 P1：Environment noise demotion

如果某个兼容报错、依赖噪声或工具链异常与多数 F2P 模块分布不重合，就应当默认降权，而不是自动升格为主修复目标。

这是 `iterative__dvc_1.0.0a1_1.0.0a2`、`iterative__dvc_2.5.0_2.5.1`、`iterative__dvc_3.43.1_3.44.0` 等 case 的直接教训。

### 6.5 P1：Contract-aware verification

对于以下类型的测试：

- `pytest.raises(..., match=...)`
- mock 调用签名
- `from x import y`
- API 返回格式

必须把“文案/导出位置/参数名/字段名”视为一等验证对象，而不是只看内部逻辑是否“差不多”。

## 7. 效度威胁

本文结论仍有以下边界：

1. 结论绑定于当前两组对照 run：
   - `innercc`: `20260427-154634`
   - `claude-code`: `20260429-114027`
2. 运行环境包含一定程度的依赖与兼容噪声，这会放大 agent 对环境问题的敏感性。
3. 虽然我们对每个 case 都做了三线合证，但 agent 内部潜在未记录状态仍不可见。

尽管如此，本文的核心结论并不依赖单个噪声案例，而是基于 `48` 案全量统计与跨 repo 重复模式，因此具有较强稳定性。

## 8. 结论

全量 `48` 案看下来，最重要的结论不是“如何让 agent 多写点代码”，而是：

- 如何让 agent 更早做任务规模判断
- 如何让 agent 更晚结束
- 如何让 agent 更少被环境噪声带偏
- 如何让 agent 用目标测试而不是局部直觉收口

如果只做一个最高优先级优化，应优先实现：

- **Task sizing + exact F2P gate**

因为它同时能削弱当前全量里最具结构性的三类失败：

- `task_understanding_error`
- `hypothesis_lock_in`
- `termination_error`

在软件工程 agent 的评测与迭代中，这类“收敛机制优化”比单纯堆叠更多局部 patch 技巧，更可能带来可持续的 resolved 提升。
