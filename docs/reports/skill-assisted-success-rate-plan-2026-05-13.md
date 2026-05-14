# 用 skill 提高 innerCC / Claude Code 成功率：写法与评测接入方案（2026-05-13）

## 1. 目标

这里讨论的不是“写一个通用大 prompt”，而是：

- 如何把已经从 bad case 里总结出的成功模式，固化成一个可重复使用的 skill
- 如何让这个 skill 同时能帮助 `innerCC` 和 `Claude Code`
- 如何把它接入你们当前的 `single-case / official48 / router` 评测流程

核心思路：

- **skill 负责约束 agent 的工作流**
- **runner 负责把这个 skill 稳定注入 benchmark 会话**

## 2. 我建议先做的 skill：`swebench-case-closer`

我已经先在仓库里落了一个草案：

- [config/skills/swebench-case-closer/SKILL.md](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/config/skills/swebench-case-closer/SKILL.md:1)

这个 skill 的定位非常明确：

- 用于 `SWE-bench / SWE-EVO` 这种有显式目标测试、release note、或窄行为契约的 bugfix 任务
- 目标是压制以下失败模式：
  - `wrong-target edits`
  - `over-exploration`
  - `hypothesis lock-in`
  - `validation gap`
  - `stopping after plausible reasoning instead of verified fixes`

### 2.1 为什么先做这个 skill

从你们前面大量 bad case 复盘来看，最常见的不是“模型根本不会写代码”，而是：

1. 没先把目标测试读透
2. 太早开始在相邻路径上修
3. 修完以后没有立刻回到目标验证对象
4. 一旦走偏，就在同一簇文件里长时间打转

这类问题非常适合 skill，因为它们更像：

- `workflow regularization`

而不是：

- `knowledge gap`

## 3. 这个 skill 应该怎么写

### 3.1 Skill 里的内容，不要写成“大而全知识库”

按照 skill 设计原则，这类 skill 最适合提供的是：

- 高价值工作流约束
- 低歧义 stop-loss 规则
- 明确的验证闭环

而不是长篇背景知识。

所以 `SKILL.md` 里应该保留：

1. 何时触发
2. 开场必须做什么
3. 编辑时不允许做什么
4. 每次编辑后的验证顺序
5. 什么时候必须 reset
6. 最终 finish gate

### 3.2 最重要的几条规则

`swebench-case-closer` 最关键的是下面这些：

1. **先读 target tests，再读代码**
2. **不允许跳过 exact F2P 验证**
3. **每次 edit 后先回到最小目标验证**
4. **连续 3 次无进展就 reset**
5. **8+ tool turns 没缩小失败路径就 reset**
6. **禁止 broad refactor 抢跑 narrow bugfix**

这些规则的价值在于，它们会直接减少：

- 无效 Read/Grep/Bash 往返
- 相邻函数反复试探
- 大量 tool_result 回流

从而既提升成功率，也改善缓存命中率。

## 4. skill 本身怎么让 `innerCC` 和 `Claude Code` 都能吃到

这里有 3 种接入模式。

### 模式 A：user skill（最快）

把 skill 放到用户级目录，比如：

- `~/.claude/skills/swebench-case-closer/SKILL.md`

优点：

- `Claude Code` 和 `innerCC` 都容易复用
- 不需要改 `innerCC` 主代码
- 最适合先验证 skill 是否真的有效

缺点：

- benchmark 自动跑时，不能保证模型自己一定会主动调用 skill
- 如果 runner 用了 `--bare`，虽然 slash skill 仍可用，但自动触发链路更弱

结论：

- 适合人工调试、交互试验
- 不适合直接作为 benchmark 自动化注入的唯一方式

### 模式 B：bundled skill（适合 innerCC 产品化）

把 skill 做进 `innerCC` 源码，例如：

- `src/skills/bundled/swebenchCaseCloser.ts`
- `src/skills/bundled/swebenchCaseCloserContent.ts`

参考现有实现：

- [src/skills/bundled/verify.ts](/home/wt/sss_repos/innerCC/src/skills/bundled/verify.ts:1)
- [src/skills/bundled/batch.ts](/home/wt/sss_repos/innerCC/src/skills/bundled/batch.ts:1)

优点：

- 内置、稳定、易控版本
- 可以配合 `whenToUse`、描述、工具池一起调

缺点：

- 只能直接改善 `innerCC`
- 不能天然迁移到 `Claude Code` benchmark 对照

结论：

- 适合当你们已经验证这个 skill 有效之后，再把它产品化进 `innerCC`

### 模式 C：runner 注入（最适合 benchmark）

这是我最推荐的评测接入方式。

不要依赖模型在 benchmark 里“自己想到要调用某个 skill”，而是：

- 在 runner 侧直接把 skill 内容注入到会话前缀

具体有两种做法：

1. **转成 append system prompt**
2. **转成一段固定的开场 user instruction**

为什么推荐 runner 注入：

- `Claude` 和 `innerCC` 可以共用同一份 skill 内容
- benchmark 比较更公平
- 不依赖 slash command / SkillTool / UI 交互

## 5. 结合你们现有 runner，应该怎么接

你们现在的单 case 与 official48 流程，最终都会走到：

- [custom_cli_case/run_custom_cli_case.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/custom_cli_case/run_custom_cli_case.py:215)
- [runtime/legacy/run_innercc_infer_official48.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/runtime/legacy/run_innercc_infer_official48.py:437)

当前调用 CLI 时，只传了：

- `prompt`
- `--model`
- `--settings`
- 以及 `innercc` 的 `--bare`

证据：

- `claude` 调用：[custom_cli_case/run_custom_cli_case.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/custom_cli_case/run_custom_cli_case.py:235)
- `innercc` 调用：[custom_cli_case/run_custom_cli_case.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/custom_cli_case/run_custom_cli_case.py:252)

这说明最自然的接入点是：

### 方案 1：追加系统提示词文件

利用 CLI 已支持的：

- `--append-system-prompt`
- `--append-system-prompt-file`

证据见：

- [src/main.tsx](/home/wt/sss_repos/innerCC/src/main.tsx:990)

做法：

1. 读取 `config/skills/swebench-case-closer/SKILL.md`
2. 提取 body
3. 生成一个临时 prompt 文件
4. runner 在调用 `claude` / `innercc` 时都追加 `--append-system-prompt-file`

优点：

- 最稳
- 最不依赖 skill auto-discovery
- 对 benchmark 最友好

### 方案 2：把 skill body 拼到 benchmark prompt 前面

直接改 `build_prompt(instance)`：

- [custom_cli_case/run_custom_cli_case.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/custom_cli_case/run_custom_cli_case.py:198)

把 skill 变成：

```text
[SKILL BODY]

[BENCHMARK TASK PROMPT]
```

优点：

- 改动最小

缺点：

- 不好区分“产品 prompt”和“实验 skill 注入”
- 后面做多 skill A/B 不方便

### 方案 3：在 runner 元数据里显式标记 skill

无论用哪种注入方式，都应该在：

- `metadata.json`
- `inference_summary.json`

记录：

- `skill_name`
- `skill_version`
- `skill_injection_mode`
- `skill_path`

这样你们后面做 run 对比时，才知道哪条 run 开了哪个 skill。

## 6. 我建议的评测接入方式

最推荐的是一个三段式实验设计：

### 实验 A：baseline

- 不注入 skill

### 实验 B：skill injected

- 给 `claude` 和 `innercc` 都注入同一份 `swebench-case-closer`

### 实验 C：mode sensitivity

- `innercc full + skill`
- `innercc bare + skill`

这样能回答三类问题：

1. skill 本身是否提高成功率
2. skill 对 `Claude` 和 `innerCC` 哪边更有效
3. `innercc --bare` 是否削弱了 skill 的收益

## 7. 为什么我不建议“完全依赖模型自己调用 SkillTool”

有两个现实原因。

### 7.1 bare 模式下，系统提示和工具池会收缩

你们当前 benchmark runner 对 `innercc` 强制加了 `--bare`：

- [custom_cli_case/run_custom_cli_case.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/custom_cli_case/run_custom_cli_case.py:252)

而 `--bare` 会进入 simple 模式：

- [src/main.tsx](/home/wt/sss_repos/innerCC/src/main.tsx:1023)
- [src/constants/prompts.ts](/home/wt/sss_repos/innerCC/src/constants/prompts.ts:450)

这时依赖“模型自己想到去调 skill”是不稳的。

### 7.2 benchmark 场景没有人类再提醒一次

交互里可以靠用户说：

- `/swebench-case-closer`

但 benchmark 里只有一次 prompt，所以更稳的办法一定是 runner 注入。

## 8. skill 内容应该如何继续迭代

第一版不要做太复杂。

建议先只针对最常见的 4 类失败模式：

1. target test 没读透
2. 错误定位偏到相邻路径
3. edit 后不回 target test
4. 无效探索时间太长

等第一版跑一批 case 以后，再看是否要加子策略：

- docs/example task
- mock/contract task
- aggregate vs per-partition task
- regression-prone task

不要一开始就把所有 bad case 模式都写进去，否则 skill 会变成一个大 prompt 包袱。

## 9. 推荐的最小落地顺序

### 第 1 步

保留现在这个 skill 草案：

- [config/skills/swebench-case-closer/SKILL.md](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/config/skills/swebench-case-closer/SKILL.md:1)

### 第 2 步

给 runner 加一个实验开关，比如：

- `--skill-file`
- `--skill-injection-mode append-system`

### 第 3 步

先只在 `single-case` 路径验证：

- `baseline`
- `skill injected`

### 第 4 步

如果单 case 有正收益，再扩到：

- `official48 subset`

### 第 5 步

只有当效果稳定后，再决定要不要把它做成 `innerCC bundled skill`

## 10. 一句话收束

如果你们想用一个 skill 真正提高 `innerCC` 和 `Claude Code` 的 benchmark 成功率，最好的方式不是指望模型在评测里自己发现并调用 skill，而是：

- **先把 bad-case 里最稳定的成功工作流固化成一个简短 skill**
- **再由 runner 把 skill 内容稳定注入 benchmark 会话**

这样你们得到的是：

- 可复现
- 可 A/B
- 可归因
- 同时兼容 `innerCC` 和 `Claude Code`
