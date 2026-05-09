---
name: weekly-report-zh
description: 生成、改写或补充中文工程周报。用于用户要求写“周报”“本周工作/下周工作”“weekly report”“status update”，或要求基于 git diff、commit、评测结果、看板数据、设计文档、测试结果、零散笔记提炼一份适合团队同步的中文周报。默认输出中文，采用“本周工作先一句话总结再展开、下周工作少而具体”的风格，优先适配 SWE-EVO-subset-run 仓库中的 project-coverage-7、official48_runs、run_evaluation.py、dashboard 与 dist 版本实验。
---

# 中文工程周报

按下面流程生成周报，默认输出适合团队内部同步的中文版本。

## 信息收集

优先按以下顺序取材：

1. 用户明确提供的范围、材料和结论。
2. 当前仓库的 `git log`、`git diff`、提交说明、测试记录。
3. 当前项目的实验与汇总产物：
   - `official48_runs/<run_id>/analysis/summary.json`
   - `official48_runs/<run_id>/metadata.json`
   - `official48_runs/<run_id>/infer/inference_status.json`
   - `official48_runs/<run_id>/eval_worker_status.json`
4. 当前项目的配置和版本信息：
   - `dist/manifest.json`
   - `configs.json`
   - `README.md`
   - `docs/exec-plans/`
5. 如果这周涉及看板、汇总或链路改造，再补充：
   - `runtime/summarize_official48_run.py`
   - `webui/lib/dashboard-data.js`
   - `webui/components/dashboard-client.jsx`

如果信息已经足够，直接产出周报，不要先追问用户。

## 项目特定口径

这个仓库的周报经常同时包含“工程改造”和“实验结果”，默认把两类内容合并成 3 到 4 条工作项，不要拆成文件清单。

写实验结果时，优先使用 `analysis/summary.json` 的汇总字段，不要从截图人工抄数。常用指标：

- `resolved_true_cases` / `resolution_rate_known_only`
- `f2p_micro_rate`
- `p2p_micro_pass_rate`
- `total_cli_cost_usd`
- `avg_cli_duration_ms`
- `total_cli_turns`
- `total_cli_model_input_tokens`
- `total_cli_model_output_tokens`
- `total_cli_tokens`
- `cache_hit_rate`

口径说明：

- `avg_cli_duration_ms` 是 agent 推理平均耗时，不是推理加评测的总墙钟时间。
- `total_cli_cost_usd` 是 CLI 推理成本，不含 SWE-bench 评测成本。
- `cache_hit_rate` 可按 `cache_read / (input + cache_read)` 理解。

如果是多版本对比，优先把版本名、run id、子集名和 2 到 4 个关键指标写清楚，再给一句结论，例如“resolved 持平，但 context 版本成本更低”。

正文行文要求：

- 周报正文默认不要把版本名、实验名、能力名写成反引号样式，例如不要写成 `innercc_init`、`history snip`、`dcp`。
- 除非用户明确要求保留代码风格，否则正文尽量用自然中文表达，减少不必要的符号感，避免看起来像 AI 自动拼装的技术摘要。
- 如果必须解释版本差异，优先写成“innercc init 基线版”“补齐 history snip 和 reactive compact 的 context 版”“纯 dcp 版”这类自然表述。

## 提炼规则

把原始改动整理成“工作项”，不要写成文件清单。

每个“本周工作”条目优先回答：

- 解决了什么问题或目标是什么。
- 设计或实现上做了哪些关键动作。
- 当前结果如何验证，是否已经接入主链路、完成 smoke、产出完整评测或进入看板。

默认写成可汇报版本：

- 先用一句话总结本周最重要的产出。
- 再展开 3 到 4 条关键工作项。
- 每条只保留高信号事实，不堆实现细节。

对这个仓库，优先把工作归并成以下类型，而不是按文件拆：

- 评测与运行链路：如 `run_evaluation.py`、direct/router 模式、后台运行、评测收口。
- 版本实验与效果对比：如 `innercc`、`claude`、`init/context/dcp` 版本对比。
- 看板与观测：如 dashboard 指标、显示修复、artifact 可见性、统计口径补齐。
- 稳定性治理：如 evaluator 依赖、clone fallback、session persistence、评测重试。

如果这周主要做了版本实验，优先写出：

- 跑了什么子集，例如 `project-coverage-7`
- 比较了哪些版本，例如 `pc7-innercc-init`、`pc7-innercc-context`
- 结果如何，例如 resolved、成本、token、cache hit 的主要结论

这里的“版本名写清楚”是指信息完整，不是要求保留代码样式；对外汇报时优先写成自然语言版本名，而不是反引号包裹的内部标识。

如果当前仍有运行中的实验，必须用具体日期说明“截至 YYYY-MM-DD”的状态，避免写成已完成。

默认不要写低价值细节，例如临时 tmux 会话名、纯本地调试开关、一次性的手工搬运步骤，除非它本身是本周核心交付。

## 下周计划生成

下周计划默认写 1 到 2 条；只有用户明确要求更细时，才扩成 3 条以上。要求具体、可执行、有产出物。

对这个仓库，优先给出：

- 一个近期可落地的验证项，例如补跑多轮 `project-coverage-7`、扩大 bad case、沉淀代表性失败样本。
- 一个系统化建设项，例如 router trace 接回、统计口径补齐、看板对比增强、自动化实验编排。

如果本周主题是上下文、压缩、记忆、检索或评测能力，优先考虑：

- 用当前版本验证 bad case，并沉淀可复现 case、触发条件和定位结论。
- 细化效果评测体系，包括 resolved、F2P、P2P、成本、token、cache hit、压缩后继续执行成功率等指标。
- 把实验配置、版本归档、trace 和结果展示进一步标准化，降低后续复现实验成本。

## 输出要求

默认输出精简中文，优先使用以下结构：

- `本周工作`
- `下周工作`

必要时参考 [references/report-template.md](references/report-template.md)。

除非用户明确要求，否则不要展开成长篇技术说明，也不要按文件逐个罗列改动。

如果用户给的是零散笔记，先归并重写，再输出可直接发送的周报版本。

默认结构如下：

```md
## 本周工作

一句话总结：……

- ……
- ……
- ……

## 下周工作

- ……
- ……
```
