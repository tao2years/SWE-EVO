# Cross-Case Synthesis

本文是当前 `48 / 48` 篇单案文档的最终综合分析报告。它不替代单案文档，而是回答 4 个更高层的问题：

1. 全量样本里，失败主要集中在哪些执行阶段。
2. `innercc` 与 `claude-code` 的系统性差异到底是什么。
3. 哪些现象已经足够稳定，可以上升成 CLI 级优化项。
4. 哪些正例应当固化成回归集，防止优化反向破坏已有能力。

方法见 [synthesis_methodology.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/synthesis_methodology.md)。

如果你想直接看“某个 failure pattern 在 trace / patch / evaluator log 里到底长什么样”，现在细节都已经并回：

- [common_issues_summary.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/common_issues_summary.md)

## 1. 样本范围与边界

- 时间截面：`2026-05-06`
- 已分析单案：`48 / 48`
- 对照 run：
  - `innercc`: `20260427-154634`
  - `claude-code`: `20260429-114027`

现在这份 synthesis 已经不再是局部样本推断，而是 official48 当前全量对照的阶段性结论。

## 2. Outcome Family 全量分布

把全部 `comparison_category` 压缩成更稳定的 family 后，可以得到：

- `inner_advantage`: `14`
- `claude_advantage`: `11`
- `both_failed`: `11`
- `both_partial`: `6`
- `both_resolved`: `6`

这说明：

- `innercc` 和 `claude-code` 都有稳定优势区间
- 但最大的单一 family 不是“某一方全面成功”，而是：
  - 双方都没解对，或者
  - 一方更接近，但仍未 resolve

换句话说，当前主要矛盾仍然是任务收敛机制，而不是单一模型能力天花板。

## 3. 最高频标签与失败链

当前最高频标签是：

- `validation_gap`: `41`
- `task_understanding_error`: `30`
- `hypothesis_lock_in`: `27`
- `localization_error`: `11`
- `reference_success_path`: `6`
- `termination_error`: `6`

这基本构成了一个完整失败链：

1. **Task sizing/scoping 出错**
   - 把 bundle 当成 single-point
   - 或把 multi-task case 缩成其中一条最显眼的线
2. **Localization 过早锁死**
   - 过早相信第一个 plausible hypothesis
   - 后续所有 grep/read/probe 都围绕它转
3. **Validation 不足**
   - 没有用 exact F2P 收口
   - 没有补相邻 P2P
4. **Termination 过早**
   - 表面上“修到一点”就结束
   - patch 覆盖面与任务规模明显不匹配

## 4. 执行阶段视角：问题主要集中在哪

### 4.1 Phase 1: Task Sizing / Scoping

这是全量 `48` 案里最重要的失败源头。

如果用 case-level root-cause tag 落地，至少 `30 / 48` 个 case 含 `task_understanding_error`。其中 `29 / 30` 同时伴随 `validation_gap`，`19 / 30` 同时伴随 `hypothesis_lock_in`。从 benchmark 体量看，这 `30` 案的 `FAIL_TO_PASS` 中位数是 `12`：`16 / 30` 有 `>=10` 条 F2P，`9 / 30` 有 `>=50` 条，但也有 `7 / 30` 只有 `<=2` 条。这说明 task sizing/scoping 的失真主要在中大题上爆发，但“小题被显眼 clue 带偏”同样不可忽视。

典型症状：

- `FAIL_TO_PASS` 明明分布在多个目录/模块，agent 仍然当成单点 bug
- release note 很长，但没有先按 tests 聚类
- 没有用官方 patch 文件分布反查任务体量

稳定出现的不是单一模式，而是三类：

- bundle / multi-cluster case 被收缩成单个 compatibility symptom
- 双分支或多分支任务只修了一半
- benchmark 真目标被 release note 显眼条目或环境噪声替代

代表案例：

- [dask__dask_2024.1.0_2024.1.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.1.0_2024.1.1_analysis.md)
- [iterative__dvc_2.8.1_2.8.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.8.1_2.8.2_analysis.md)
- [iterative__dvc_3.43.1_3.44.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.43.1_3.44.0_analysis.md)

### 4.2 Phase 2: Fault Localization

这是第二高风险阶段。

从标签看，`localization_error` 出现在 `11 / 48` 个 case 中，且 `11 / 11` 都伴随 `validation_gap`，`9 / 11` 伴随 `hypothesis_lock_in`。和 task sizing 相反，这类 case 的 `FAIL_TO_PASS` 全都 `<=9`，其中 `8 / 11` 只有 `<=2` 条，说明它更多发生在“任务规模已经缩小，但最后一跳落错层”的场景，而不是超大 bundle 根本搜不动。

典型症状：

- patch 落在相邻层，而不是 evaluator 真正失败的层
- 参数签名 / mock contract 的测试，却只修内部语义
- 失败断言指向具体字段/对象，patch 却改相邻字段/对象

再往下看，可以稳定拆成 3 种偏移：

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

### 4.3 Phase 3: Code Editing

编辑错误的频次不算最高，但代价很大。

代表案例：

- [psf__requests_v2.12.2_v2.12.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/psf__requests_v2.12.2_v2.12.3_analysis.md)
- [iterative__dvc_1.0.0a1_1.0.0a2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.0.0a1_1.0.0a2_analysis.md)

这里更值得关注的是：

- 编辑安全 guard 价值很高
- 一旦 patch 开始直接改 tests/helper 或引入语法/字符问题，往往是偏航信号，而不是修复进展

### 4.4 Phase 4: Validation

这是频次最高、也最容易固化成工程规则的阶段。

`41 / 48` 的 `validation_gap` 说明：

- 很多失败本应更早暴露
- 只是 agent 缺了硬 gate

最常见缺口有 4 个：

1. 没有 exact failing tests gate
2. 没有相邻 P2P smoke gate
3. 没有 patch-vs-target 覆盖面 gate
4. 没有语法 / import smoke gate

这也解释了为什么“不加区分地 full coverage”不是合理默认值。全量 `48` 案的 `FAIL_TO_PASS` 中位数只有 `4`，`27 / 48` 案 `<=5`，`32 / 48` 案 `<=10`，所以 exact F2P gate 通常是便宜的；但 `PASS_TO_PASS` 中位数是 `106.5`，`13 / 48` 案 `>=500`，`9 / 48` 案 `>=1000`，最大值 `6246`，因此每次局部编辑后都跑完整 P2P / full evaluator 会很重。更合理的是三层闭环：先 exact F2P，再 touched-module 邻近 P2P smoke，最后在 patch 稳定后交给当前 pipeline 的 case-level evaluator。

当前仓库已经有 post-inference 的增量评测链路：[run_official48_eval_worker.py](/home/wt/sss_repos/sss_auto/SWE-EVO/run_official48_eval_worker.py) 会轮询 `inference_summary.json` 并调用 [SWE-bench/evaluate_instance.py](/home/wt/sss_repos/sss_auto/SWE-EVO/SWE-bench/evaluate_instance.py)。它解决的是“每题完成后尽快判分”，还不是 agent 自身的 in-loop 迭代验证。

### 4.5 Phase 5: Termination

`termination_error` 虽然只有 `6` 次，但几乎都出现在最重的 case 上。

从数据看，`termination_error` 的 `6` 案全部同时带有 `task_understanding_error` 和 `validation_gap`。它们的 `FAIL_TO_PASS` 中位数是 `40.5`，其中 `4 / 6` 有 `>=13` 条 F2P，`3 / 6` 有 `>=68` 条；唯一的小题例外是 [iterative__dvc_0.91.2_0.91.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_0.91.2_0.91.3_analysis.md)，它的问题也不是“时间不够”，而是交付物错位后仍被当成完成。这说明 termination error 不是 timeout 的同义词，而是 done-condition 失真。

代表案例：

- [dask__dask_2024.1.0_2024.1.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.1.0_2024.1.1_analysis.md)
- [pydantic__pydantic_v2.7.1_v2.7.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/pydantic__pydantic_v2.7.1_v2.7.2_analysis.md)
- [iterative__dvc_3.13.3_3.14.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.13.3_3.14.0_analysis.md)

## 5. `innercc` 与 `claude-code` 的系统差异

### 5.1 `innercc` 的典型优势

- 在 multi-task 或 bundle case 上更愿意扩展搜索空间
- 更容易同时碰多个目标簇
- 在 `iterative/dvc`、`dask/dask` 这种需要跨多个子系统同时命中的题上，优势更明显

代表案例：

- [dask__dask_2023.9.2_2023.9.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2023.9.2_2023.9.3_analysis.md)
- [iterative__dvc_3.4.0_3.5.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.4.0_3.5.0_analysis.md)
- [iterative__dvc_2.19.0_2.20.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.19.0_2.20.0_analysis.md)

### 5.2 `innercc` 的典型风险

- patch 宽度更容易失控
- 更容易被环境噪声或局部兼容问题挟持后一路扩散
- 一旦修偏，P2P 大面积回归的概率更高

代表案例：

- [iterative__dvc_1.0.0a1_1.0.0a2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.0.0a1_1.0.0a2_analysis.md)
- [iterative__dvc_3.43.1_3.44.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.43.1_3.44.0_analysis.md)
- [psf__requests_v2.4.0_v2.4.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/psf__requests_v2.4.0_v2.4.1_analysis.md)

### 5.3 `claude-code` 的典型优势

- 窄任务、单点修复、强契约 case 更稳
- 更少出现明显“写坏源码”的编辑问题
- 在参数签名 / mock contract / 输出格式这种任务上更强

代表案例：

- [iterative__dvc_1.0.0b6_1.0.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.0.0b6_1.0.0_analysis.md)
- [psf__requests_v2.12.2_v2.12.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/psf__requests_v2.12.2_v2.12.3_analysis.md)
- [iterative__dvc_1.11.12_1.11.13_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.11.12_1.11.13_analysis.md)

### 5.4 `claude-code` 的典型风险

- 大 case 上更容易停在第一个 plausible cluster
- 经常只修 release note 里最显眼的那一条 feature
- 更常见的失败方式不是“写坏”，而是“修得太窄、修到一半”

代表案例：

- [modin-project__modin_0.25.0_0.25.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/modin-project__modin_0.25.0_0.25.1_analysis.md)
- [iterative__dvc_3.43.1_3.44.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.43.1_3.44.0_analysis.md)
- [iterative__dvc_2.8.1_2.8.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.8.1_2.8.2_analysis.md)

## 6. 可以上升成 CLI 规则的内容

### 6.1 P0: Task Sizing Gate

必须在前几步判断：

- `single-point`
- `multi-task`
- `bundle`

建议硬规则：

1. 统计 `FAIL_TO_PASS` 数量与模块分布
2. patch 覆盖面若远小于任务体量，禁止结束
3. bundle case 必须显式列出目标簇

### 6.2 P0: Exact F2P + Adjacent P2P 双门槛

1. exact failing tests 作为硬 gate
2. patch 直接覆盖模块必须补相邻 P2P smoke

### 6.3 P0: Localization Cross-Check

定位前至少交叉核对三类证据：

1. evaluator 最深项目帧
2. failing assertion / test contract
3. golden patch 关键 hunk

### 6.4 P1: Environment Noise Demotion

如果某个兼容报错或依赖噪声没有与多数 F2P 文件分布重合，就默认降权，不允许直接成为主修复目标。

### 6.5 P1: Contract-Aware Verification

对 `pytest.raises(match=...)`、mock 调用签名、import path 这类外部契约，必须把“文案/导出位置/参数名”作为一等验证对象，而不是只看内部逻辑“差不多”。

## 7. 回归集建议

### 7.1 正例回归集

- [modin-project__modin_0.27.0_0.27.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/modin-project__modin_0.27.0_0.27.1_analysis.md)
- [psf__requests_v2.27.0_v2.27.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/psf__requests_v2.27.0_v2.27.1_analysis.md)
- [iterative__dvc_1.11.12_1.11.13_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.11.12_1.11.13_analysis.md)
- [iterative__dvc_3.15.0_3.15.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.15.0_3.15.1_analysis.md)

用途：

- 防止优化把窄 patch / 强契约路径打坏

### 7.2 Bundle failure 回归集

- [dask__dask_2024.1.0_2024.1.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.1.0_2024.1.1_analysis.md)
- [iterative__dvc_2.8.1_2.8.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.8.1_2.8.2_analysis.md)
- [conan-io__conan_2.0.14_2.0.15_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/conan-io__conan_2.0.14_2.0.15_analysis.md)

用途：

- 验证 task sizing / cluster planning 是否改进

### 7.3 Contract / Localization 回归集

- [iterative__dvc_1.0.0b6_1.0.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.0.0b6_1.0.0_analysis.md)
- [dask__dask_2024.3.1_2024.4.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.3.1_2024.4.0_analysis.md)
- [iterative__dvc_2.7.2_2.7.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_2.7.2_2.7.3_analysis.md)

用途：

- 验证定位与契约校验是否有效

## 8. 最终结论

全量 `48` 案看下来，最重要的结论仍然是：

- 真正要优化的不是“让模型多写点代码”，而是“让它更晚结束、更早聚类、更少被噪声带偏、更严格地用目标测试收口”。

如果只做一个最高优先级改动，应该先做：

- **Task sizing + exact F2P gate**

因为它同时能削弱：

- `task_understanding_error`
- `hypothesis_lock_in`
- `termination_error`

而这三者，正是当前全量失败中最具结构性的部分。
