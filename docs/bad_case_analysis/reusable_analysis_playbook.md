# Reusable Analysis Playbook

这份文档是面向“继续写新 bad case 文档的人”的操作手册。它和 `bad_case_analysis_design.md` 的区别是：

- `bad_case_analysis_design.md` 解释“为什么这样设计、文档应该长什么样”
- 本文解释“下一篇具体怎么做、按什么顺序、每一步输出什么”

## 1. 适用场景

适用于所有 official48 case，尤其是：

1. `release note` 很长、`FAIL_TO_PASS` 很多的 bundle case
2. `FAIL_TO_PASS` 很少，但 patch 影响公共函数的单点 case
3. 两个 CLI 结果分歧明显的对照 case

## 2. 标准工作流

每个新 case 必须按下面顺序推进，不能跳步。

### Step 1. 先定任务边界

从 `official48_source/output_final/<instance_id>.json` 读取：

- `problem_statement`
- `FAIL_TO_PASS`
- `PASS_TO_PASS`
- `patch`
- `test_patch`

必须先判断 case 类型：

1. `single_point`
   - F2P 少
   - release note 聚焦
   - 目标通常是单函数或单 API 行为

2. `multi_task`
   - release note 至少有两条明显独立修复点
   - F2P 分布在不同模块

3. `bundle_case`
   - F2P 很大
   - 官方 patch 很大
   - 涉及多个子系统

### Step 2. 还原 CLI 真正收到的 query

用 `custom_cli_case/run_custom_cli_case.py` 里的 `build_prompt()` 模板还原完整 prompt。

这一步必须写进文档，因为后续所有“任务理解是否偏航”的判断都基于这条 query，而不是基于你脑补的 issue 描述。

### Step 3. 先看 evaluator，再看 trace

顺序不能反：

1. 先看 `report.json`
   - 判断是“没修到”还是“修坏了”
2. 再看 `test_output.txt`
   - 找决定性失败证据
3. 再看 `run_instance.log`
   - 看 patch 是否成功应用、是否有 evaluator 包装层异常
4. 最后才看 `router_trace_bundle.json`

原因：

- evaluator 告诉你真实世界发生了什么
- trace 只告诉你 agent 当时以为发生了什么

## 3. 如何重建推理过程

### 3.1 先按 phase，不先按工具

不要一上来做“工具次数统计 -> 下结论”。先按 phase 切分：

- `bootstrap`
- `repo_exploration`
- `task_planning`
- `fault_localization`
- `hypothesis_testing`
- `code_editing`
- `validation`
- `termination`

### 3.2 phase 的判断标准

#### `bootstrap`

- 看版本
- 看仓库结构
- 看目录 / 基本文件

#### `repo_exploration`

- grep test 名
- read 相关函数
- 搜配置、常量、入口

#### `task_planning`

- assistant 明确说“需要修 2 个问题”“先做 A 再做 B”

#### `fault_localization`

- assistant 明确说“问题在某个函数/某层级”

#### `hypothesis_testing`

- 手写 Python probe
- 跑局部 pytest
- 用最小复现测试自己假设

#### `code_editing`

- 出现 `Edit` / `Write`

#### `validation`

- 修改后看 diff
- 跑 pytest / import / py_compile / scripts

#### `termination`

- assistant 输出 `fix is complete`
- 或输出最终总结、停止继续迭代

## 4. 如何判断根因

### 4.1 先分成 3 层

每篇文档必须分开写：

1. `direct_root_cause`
2. `contributing_factors`
3. `misleading_signals`

### 4.2 根因标签使用规范

#### `task_understanding_error`

用在：

- release note 里有多条修复，但 agent 只抓一条
- F2P 很多，但 agent 按单点 bug 在修
- prompt 明确给了 failing tests，agent 仍然被 release note 文本带偏

#### `localization_error`

用在：

- patch 落点和 evaluator traceback 最深项目帧不一致
- patch 改的是相邻对象、相邻 cache、相邻层级

#### `hypothesis_lock_in`

用在：

- agent 很早锁定一个解释
- 后面几十步都只在替这个解释找证据
- 即使失败断言已经出现反证，也不回头

#### `validation_gap`

用在：

- 没跑 exact failing tests
- 只跑了局部 Python probe
- 用了 `pytest ... | head`
- F2P 全过后没看 P2P

#### `termination_error`

用在：

- 明显只修了局部，却直接结束
- case 是 bundle，但 patch 覆盖率极低就收工

#### `overfitted_to_f2p`

用在：

- F2P 全过
- 但相邻模块 P2P 明显回归

#### `edit_safety_error`

用在：

- 非 ASCII 标点进入代码
- 语法错误
- import 级炸掉

## 5. 写文档时必须回答的 8 个问题

每篇单 case 文档都要能直接回答：

1. benchmark 真正要修什么？
2. CLI 真正收到了什么 query？
3. 官方 golden patch 核心在修哪里？
4. 两个 CLI 分别在第几步开始形成关键假设？
5. 哪一步开始偏航？
6. patch 落点与 evaluator 失败证据是否一致？
7. 为什么 evaluator 最终判它失败/成功？
8. 这个 case 能沉淀出什么 CLI 规则？

如果答不出来，就说明文档还不够细。

## 6. 什么时候应该把 case 归成哪类

### `reference_success`

条件：

- F2P 全过
- P2P 无回归
- patch 窄且和任务高度对齐

用途：

- 用来做正例模板

### `partial_success`

条件：

- F2P 过了一部分
- 或 F2P 全过但 P2P 回归导致未 resolve

用途：

- 分析“修到一半”或“过拟合 F2P”

### `wrong_target`

条件：

- patch 在修 release note 某一条真实内容
- 但不是 benchmark 实际 target

用途：

- 说明 agent 过度相信 release note，而没让 failing tests 主导任务

### `bundle_collapse`

条件：

- bundle case 被缩成单点兼容修复

用途：

- 说明 agent 缺乏任务规模判断

## 7. 当前最值得复用的经验

基于已完成 case，最稳的复用结论是：

1. 单点、单函数、单 failing-test case 最容易成功。
2. 多子任务 release case 必须先做 failing-test 聚类，否则大概率偏航。
3. evaluator 的失败证据必须比 trace 假设优先级更高。
4. exact failing test 与相邻 P2P 的联合验证，是目前最值得固化成规则的闭环。
