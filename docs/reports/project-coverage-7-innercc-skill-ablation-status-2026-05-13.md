# project-coverage-7：innerCC skill ablation 当前状态（2026-05-13）

## 1. 为什么需要这份状态文档

当前我们想回答的不是：

- `skill-on` 和 baseline 谁更好

而是更精确的问题：

- `innercc_0509_context` 这次收益里，究竟有多少来自 **去掉 `--bare`**，有多少来自 **`swebench-case-closer` skill 本身**

为了拆开这两个因素，我们需要 3 条 run：

1. `baseline`
   - `innercc --bare`
   - no skill
2. `full + skill`
   - `innercc` 不再 bare
   - 注入 `swebench-case-closer`
3. `full + no-skill`
   - `innercc` 不再 bare
   - **不注入 skill**

前两条已经收完，第三条还没收完，但已经有 5 个 case 产出了完整 `cli_result.json + report.json`。

## 2. 当前 3 条 innerCC 相关 run

### A. baseline

- run: `20260511-194955-project-coverage-7-innercc-context-router-rerun`
- 含义：旧的 `innercc context` router baseline

### B. full + skill

- run: `20260513-153919-project-coverage-7-innercc-router`
- display name: `pc7-innercc-0509-context-skill-router`

### C. full + no-skill（干净控制组）

- run: `20260513-164631-project-coverage-7-innercc-router`
- display name: `pc7-innercc-0509-context-full-router-noskill-isolated`

这个控制组使用了：

- `CLAUDE_CONFIG_DIR=/tmp/codex-noskill-config`

这样可以确保：

- 用户级 `~/.claude/skills/swebench-case-closer` 不会被自动发现

并且已经从真实 router 首轮 request 验证：

- **请求里没有 `swebench-case-closer`**

## 3. 当前已经完成的结论

### 3.1 baseline vs full + skill

这部分已经是有效结论：

| metric | baseline | full + skill |
| --- | ---: | ---: |
| resolved | `3/7` | `3/7` |
| f2p micro | `40.9%` | `40.9%` |
| p2p micro | `54.3%` | `51.1%` |
| total cost | `$47.11` | `$51.10` |
| total turns | `445` | `445` |
| input tok | `14.95M` | `15.21M` |
| cache hit | `10.2%` | `35.4%` |

可以确认：

1. cache hit 提升非常大
2. 成功率没有提升
3. p2p 还略降

但这还**不能**直接说明 skill 没用，因为这里同时改了运行模式：

- baseline 更接近 `--bare`
- full + skill 明确去掉了 runner 强制 bare

### 3.2 full + no-skill 控制组已经是“干净的”

这个最关键。

当前控制组：

- `metadata.skill_name = ""`
- `disable_slash_commands = 0`
- 但因为 `CLAUDE_CONFIG_DIR` 指向空目录，所以首轮 request 里没有 `swebench-case-closer`

这说明：

- 它是真正可用的 `full + no-skill` 控制组
- 不是之前那个假 no-skill（只是没显式注入，但用户 skill 仍然被自动发现）

## 4. 当前真实进度

截至这次更新，第三条控制组的真实状态是：

- `total_instances = 7`
- 已完成并落出 `cli_result.json + report.json` 的 case：
  - `dask`
  - `iterative`
  - `modin`
  - `requests`
  - `pydantic`
- 已完成推理、但 evaluator 结果还没回来的 case：
  - `scikit`
- 仍在跑：
  - `conan`

因此当前能严肃计算的是：

- `5/7` 的质量矩阵
- `6/7` 的推理轨迹 / 成本矩阵

注意：

- `analysis/summary.json` 仍然是旧快照，只统计到了 `dask`
- 但 5 个 completed case 的原始产物已经足够做一版 **partial 5/7** 质量对照

## 5. partial 5/7：三方对照结果

这里先只比较已经完成的 5 个 case：

- `dask`
- `iterative`
- `modin`
- `requests`
- `pydantic`

### 5.1 5-case 聚合

| mode | resolved | f2p micro | p2p micro | turns | cost | input tok | cache hit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline` | `3/5` | `8/13 = 61.5%` | `4220/8401 = 50.23%` | `275` | `$17.35` | `5.29M` | `16.3%` |
| `full + skill` | `3/5` | `8/13 = 61.5%` | `4218/8401 = 50.21%` | `201` | `$9.87` | `2.63M` | `57.0%` |
| `full + no-skill` | `3/5` | `8/13 = 61.5%` | `4218/8401 = 50.21%` | `159` | `$10.83` | `2.57M` | `50.4%` |

当前 5 个 completed case 给出的信号是：

1. `full + skill` 和 `full + no-skill` 在质量上**完全一样**
   - `resolved`
   - `f2p micro`
   - `p2p micro`
   目前都没有差开
2. 相比 baseline，`full` 模式本身已经大幅改善：
   - turns
   - input tokens
   - cache hit
3. 在这 5 个 case 上，skill 的主要作用不是“提高成功率”，而是**重塑轨迹**

### 5.2 case 级差异

#### `dask`

- `full + skill` 和 `full + no-skill` 几乎完全一样
- 结论仍然不变：
  - 这里的主效应来自 **去掉 `--bare`**
  - 不是 skill 本身

#### `iterative`

- `baseline`: `52 turns`, `598k input`, `p2p_failure = 0`
- `full + skill`: `60 turns`, `1.21M input`, `p2p_failure = 2`
- `full + no-skill`: `77 turns`, `1.91M input`, `p2p_failure = 2`

这里 skill 的作用更像：

- 把一条已经会回归的 full-mode 轨迹收短
- 但没有把错误结果纠正回来

#### `modin`

- `baseline`: `38 turns`, `256k input`
- `full + skill`: `45 turns`, `532k input`
- `full + no-skill`: `9 turns`, `29k input`

`modin` 说明：

- `full` 模式并不总是比 baseline 更贵
- skill 甚至可能把一条本来很短的 full-mode 成功轨迹重新拉长

#### `requests`

- `full + skill` 和 `full + no-skill` 质量相同
- no-skill 稍贵，但差异不大

这里更像：

- skill 基本无害
- 但也没有明确额外收益

#### `pydantic`

- 三组都没有解出来
- `baseline`: `52 turns`, `661k input`, `p2p_failure = 4181`
- `full + skill`: `51 turns`, `512k input`, `p2p_failure = 4181`
- `full + no-skill`: `28 turns`, `226k input`, `p2p_failure = 4181`

这条很有价值：

- `full + no-skill` 在**不损失任何质量**的前提下，把轨迹和成本明显压低
- skill 没有带来额外质量收益，反而比 no-skill 更长更贵

## 6. 当前已经能下的结论

### 6.1 `--bare` 仍然是最强混杂因素

`dask` 已经给出强证据，5-case partial 聚合也在重复这个结论：

- 从 `baseline` 切到 `full` 模式，本身就会显著改善：
  - prompt/cache 结构
  - turns
  - input tokens
  - cache hit

所以：

- 不能把 `baseline -> full + skill` 的 cache hit 提升直接归因给 skill

### 6.2 在当前已完成的 5 个 case 上，skill 还没有证明净收益

更精确地说：

- `full + skill` 没有比 `full + no-skill` 多解决任何一个 case
- `f2p micro` 没有提升
- `p2p micro` 没有提升

它目前展示出的主要效果是：

- 改写探索轨迹
- 在部分 case 上减少搜索宽度

但这不等于：

- 提高最终成功率

### 6.3 skill 的作用明显是 case-dependent

当前已完成的证据已经说明：

- `dask`：skill 几乎没有额外作用
- `iterative`：skill 收短了轨迹，但没修好回归
- `modin`：skill 反而把一条本来更短的成功轨迹拉长
- `pydantic`：skill 让失败轨迹更长更贵

所以更合理的判断是：

- 这个 skill 不是全局增益开关
- 它是一个会改变搜索形态的干预项

## 7. 等这条控制组彻底收完后，应该怎么读

一旦 `20260513-164631-project-coverage-7-innercc-router` 收完，我们就看这三组：

### 组 1：baseline -> full + no-skill

回答：

- 去掉 `--bare` 本身带来了什么变化？

重点看：

- cache hit
- turns
- input tokens
- resolved / f2p

### 组 2：full + no-skill -> full + skill

回答：

- skill 在相同 full 模式下，是否带来额外收益？

重点看：

- resolved / f2p
- case-level turns
- tool error count
- cache hit 是否继续改善

### 组 3：case-family 维度

回答：

- skill 是全局有效，还是只对某些 case family 有效？

优先看：

- `dask`
- `requests`
- `conan`
- `scikit`
- `pydantic`

## 8. 当前最合理的中间判断

在 `conan / scikit` 收完之前，当前最合理的中间判断是：

1. `full` 模式本身已经解释了大部分 cache hit 改善
2. 在当前已完成的 5 个 case 上，skill 没有证明额外质量收益
3. skill 更像一个会改变轨迹长度和搜索宽度的干预项
4. 最值得继续盯的是：
   - `conan`
   - `scikit`
   这两个尾部 case 是否会把 `full + no-skill` 和 `full + skill` 真正拉开

## 9. 一句话收束

现在已经有了真正干净的 `innercc full, no-skill` 控制组，而且前 5 个 completed case 已经足够说明：  
`full` 模式的主效应远大于 skill，而 skill 目前更像是在重塑轨迹，而不是稳定提高成功率。  
下一步只要等 `conan / scikit` 收完，就能把：

- `去掉 --bare`
- 和 `skill 本身`

这两个因素真正拆开。  
