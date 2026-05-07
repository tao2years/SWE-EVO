# Bad Case Analysis Framework

这是 `bad_case_analysis` 目录的入口文档。

## 文档分工

- 方法论设计：
  [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md)
- 操作手册：
  [reusable_analysis_playbook.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/reusable_analysis_playbook.md)
- 综合分析方法：
  [synthesis_methodology.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/synthesis_methodology.md)
- 文档模板：
  [case_report_template.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/case_report_template.md)
- 综合分析报告：
  [cross_case_synthesis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/cross_case_synthesis.md)
- 共性问题摘要：
  [common_issues_summary.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/common_issues_summary.md)
- 候选案例池：
  [candidate_cases.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/candidate_cases.md)
- 单案例分析：
  `docs/bad_case_analysis/<instance_id>_analysis.md`

## 使用方式

新增 case 时，先按设计文档执行：

1. 从 benchmark JSON 提取任务、golden patch、golden test patch。
2. 从 runner 模板还原 CLI 实际收到的 query。
3. 从 `router_trace_bundle.json` 重建 step 和 phase 时间线。
4. 从 `report.json` / `test_output.txt` 提取真实失败证据。
5. 用 patch 证据、trace 证据、评测证据三线合并，写出根因与 CLI 优化项。

## 当前重点

优先继续完善和扩展这两类案例：

1. `innercc` 失败、`claude-code` 成功
2. `innercc` 成功、`claude-code` 失败

下一批建议案例见：

- [candidate_cases.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/candidate_cases.md)
