# Synthesis Methodology

本文定义“如何从一组单案分析文档，提炼出一份可复用的综合分析报告”。它解决的是 summary-level 分析，而不是单案分析本身。

单案方法见：

- [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md)
- [reusable_analysis_playbook.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/reusable_analysis_playbook.md)

## 1. 目标

综合分析必须回答：

1. 当前已分析 cohort 里，最常见的问题是什么。
2. 这些问题主要发生在执行流程的哪个阶段。
3. 哪些问题是 CLI 共性问题，哪些问题更偏某个 CLI 的收敛风格。
4. 哪些单案现象已经足够稳定，可以提升为 CLI 优化规则。

如果一份综合分析只是把 tag 计数重新排一遍，它是不合格的。综合分析必须把“频率”转成“机制”，再把“机制”转成“优化优先级”。

## 2. 输入材料

综合分析默认只使用本地材料：

1. `docs/bad_case_analysis/*_analysis.md`
2. 如需回查，允许回到对应单案引用的：
   - benchmark JSON
   - `router_trace_bundle.json`
   - `patch.diff`
   - `report.json`
   - `test_output.txt`

默认不重新从零看所有 trace。综合分析的主输入应当是已经写好的单案文档；只有当单案结论存在冲突或明显缺口时，才回查原始证据。

## 3. 输出层级

推荐把综合分析拆成 2 层：

### 3.1 `common_issues_summary.md`

用途：

- 给读者一个快速入口
- 总结当前覆盖数、主导标签、最重要的 3-5 个结论

### 3.2 `cross_case_synthesis.md`

用途：

- 做完整机制分析
- 写清楚 outcome family、阶段性失败模式、CLI 风格差异与优化路线

## 4. 标准工作流

### Step 1. 冻结 cohort 边界

先明确：

- 当前统计覆盖多少篇单案文档
- 截止日期
- 统计使用的是哪些 run

如果 cohort 没写清楚，后续所有比例和趋势都不可复现。

### Step 2. 先归 outcome family，再看标签

不要一上来只数 tag。先把案例按结果压缩成 outcome family，例如：

- `inner_advantage`
- `claude_advantage`
- `both_failed`
- `both_partial`
- `both_resolved`

原因：

- tag 只能告诉你“出了什么问题”
- family 才能告诉你“问题最终把结果推向了哪一类结局”

### Step 3. 把标签映射回执行阶段

标签不能只做频率统计，要映射回执行链条：

- `task_understanding_error`
  - 对应 task sizing / scoping
- `localization_error`
  - 对应定位阶段
- `hypothesis_lock_in`
  - 对应定位到验证之间的收敛动态
- `edit_safety_error`
  - 对应代码编辑阶段
- `validation_gap`
  - 对应验证阶段
- `termination_error`
  - 对应结束阶段

这样综合分析才能回答“问题主要出在哪一段流程”。

### Step 4. 单独分析 task shape

综合分析必须把 case 再按任务形状切一次：

- `single_point`
- `multi_task`
- `bundle_case`

原因：

- 同一个 CLI 在不同任务形状上可能表现完全不同
- 如果不拆 task shape，很容易把“适合窄任务”和“不适合大 bundle”误读成统一能力高低

### Step 5. 区分 CLI 共性问题和 CLI 风格问题

判断标准：

- 如果两个 CLI 在多个案例里反复出现相同失败模式，这是共性问题。
- 如果只有某一方在某类 case 上稳定占优或稳定偏航，这是风格问题。

写结论时要避免两种错误：

1. 看到一个 case 就给某个 CLI 贴总标签
2. 把双方共同失败的问题误写成某一方专属缺陷

### Step 6. 从“现象”提升到“机制”

例如：

- 现象：`validation_gap` 很多
- 机制：没有 exact F2P gate、没有相邻 P2P gate、没有 patch coverage gate

再例如：

- 现象：很多 release-note case 失败
- 机制：agent 没有做 task sizing 与 F2P clustering，直接被显眼 symptom 带走

综合分析必须完成这一步，否则输出仍然只是“统计摘要”。

### Step 7. 从“机制”提升到“优化优先级”

每个机制最后都要落成优化项，并回答：

1. 该规则拦截哪类失败
2. 为什么值得排在前面
3. 如何验证规则有效

没有优化优先级的综合分析，只能帮助理解，不能帮助改系统。

## 5. 证据规则

### 5.1 不能把 secondary tag 当成主要矛盾

单案文档里的 tag 可能同时包含直接根因和次级因素。综合分析时必须区分：

- “高频出现”
- “真正主导结果”

例如：

- `validation_gap` 高频，不代表每个 case 的第一性错误都是验证
- 但它确实是最常见的“让错误没有尽早暴露”的放大器

### 5.2 不能用单案支撑全局结论

全局结论至少需要：

- 多个 repo 复现，或
- 同一模式跨多个 case 重复出现

例如：

- 单独一个 `SyntaxError` 案例不能推出“innercc 普遍不会安全编辑”
- 但它可以推出“编辑安全 guard 是低成本高收益的必要兜底”

### 5.3 必须保留正例

综合分析不能只写失败，还要保留 reference success：

- 用来识别“什么情况下当前 CLI 已经工作得很好”
- 避免优化把原本有效的窄 patch 路径一起打坏

## 6. 建议的综合分析结构

完整综合报告推荐按这个顺序写：

1. 样本范围与边界
2. outcome family 分布
3. 高频标签与阶段映射
4. task shape 分析
5. 阶段性失败机制
6. CLI 风格差异
7. 可固化优化项
8. 推荐回归集
9. 当前结论的边界与待验证问题

## 7. 写作检查清单

写完一份综合分析后，至少自查下面 9 项：

1. 是否写清楚了当前覆盖多少篇 case。
2. 是否把结果先压成了 outcome family。
3. 是否把标签映射回执行阶段。
4. 是否单独讨论了 task shape。
5. 是否区分了共性问题与 CLI 风格问题。
6. 是否给出了正例，而不只是失败例。
7. 是否把现象提升成机制。
8. 是否把机制转成优化优先级。
9. 是否明确说明当前结论仍受未分析 case 数量限制。

## 8. 推荐配套文件

为了让综合分析可复用，建议始终维护这组文件：

- [analysis_framework.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/analysis_framework.md)
- [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md)
- [reusable_analysis_playbook.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/reusable_analysis_playbook.md)
- [case_report_template.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/case_report_template.md)
- [common_issues_summary.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/common_issues_summary.md)
- [cross_case_synthesis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/cross_case_synthesis.md)
