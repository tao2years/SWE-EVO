## 本周工作

一句话总结：本周围绕长任务稳定性和 SWE-EVO 快速评测，先梳理了长任务失控的主要问题并形成一版治理设计方案，再基于每个仓库各采样 1 个 case 的快速验证子集，对 innercc init、innercc context、dcp 等版本做了完整推理评测和数据对比。

- 分析了复杂长任务、多阶段任务和长时间 agent 执行卡住的典型案例，确认当前主要问题不在“不会做”，而在执行中后段容易失控：包括目标逐步跑偏、主线丢失、把局部验证当成整体验证、缺少明确 completion gate，以及把环境噪声误判成代码问题。
- 基于上述问题，明确了长任务治理的几个大致方向，包括目标与进度约束、关键决策和验证闭环、风险控制，以及必要的工具和执行机制补充；下周会继续做更具体的设计与实现，并结合批量对比实验验证效果。
- 梳理了 Claude Code 89-109 版本里和上下文相关的 feature，共看了 29 条，重点过了一遍上下文裁剪、压缩、记忆、恢复执行这些能力，也圈定了接下来优先要补的点。
- 过了一遍 NGA 到 CC 的需求迁移情况，共看了 46 条需求，标出了哪些已经有、哪些还缺、哪些不能直接照搬、需要重新适配。
- 在 SWE-EVO 上按“每个仓库采样 1 个代表 case”的方式整理出快速验证子集，围绕 innercc init、innercc context、innercc dcp、innercc dcp+context 以及 claude-2.1.116 跑通了完整的推理、评测、汇总和展示链路。其中，innercc init 是初始基线版本，未引入 history snip、reactive compact 和 dcp；innercc context 是在 init 基础上补齐 history snip 和 reactive compact；innercc dcp 是纯 dcp 版本，不带 context prompt 特性；innercc dcp+context 则同时引入了 dcp 和 context 相关能力。
- 从首轮数据看，innercc context 是当前效果最好的 innercc 版本：在 resolved 数与 init、dcp、dcp+context 持平的情况下，F2P 和 P2P 最优，且成本和 token 消耗最低，说明补齐 history snip 和 reactive compact 后对上下文控制和执行稳定性有明显收益；同时也观察到，相比 claude-2.1.116 的高缓存命中率，当前几版 innercc 的缓存命中率都明显偏低，说明后续还需要继续优化缓存利用和上下文复用策略。
- 针对 model: synthetic、Z.text.trim 问题尝试做修复验证，但自测发现引入了更多 API Error，已及时回退，没有继续扩散到主实验链路。

## 下周工作

- 围绕已经明确的几个方向继续做具体设计和实现，优先推进目标与进度约束、验证闭环、风险控制以及必要工具机制的接线。
- 基于当前快速验证子集开展更多轮批量对比实验，重点观察 innercc context、dcp 相关版本和后续改动在 resolved、F2P、P2P、token 消耗和缓存命中率上的变化。

## 实验数据

版本说明：

- pc7-innercc-init：初始基线版本，不含 history snip、reactive compact、dcp
- pc7-innercc-context：在 init 基础上补齐 history snip + reactive compact
- pc7-innercc-dcp：纯 dcp 版本，不带 context prompt 特性
- pc7-innercc-dcp+context：同时引入 dcp 和 context 相关能力
- pc7-claude-2.1.116：对照基线

| metric | pc7-innercc-dcp | pc7-innercc-context | pc7-innercc-init | pc7-innercc-dcp+context | pc7-claude-2.1.116 |
| --- | ---: | ---: | ---: | ---: | ---: |
| status | completed | completed | completed | completed | completed |
| active slots | 0 | 0 | 0 | 0 | 0 |
| failed | 0 | 0 | 0 | 0 | 0 |
| inference | 7/7 | 7/7 | 7/7 | 7/7 | 7/7 |
| eval reports | 7/7 | 7/7 | 7/7 | 7/7 | 7/7 |
| resolved | 3 | 3 | 3 | 3 | 2 |
| resolved rate | 42.9% | 42.9% | 42.9% | 42.9% | 28.6% |
| f2p micro | 45.5% | 59.1% | 45.5% | 50.0% | 40.9% |
| p2p micro | 54.3% | 99.8% | 54.3% | 54.3% | 54.3% |
| total cost | $59.12 | $16.80 | $19.88 | $46.22 | $29.65 |
| avg duration | 3.0 min | 3.1 min | 3.2 min | 6.0 min | 4.6 min |
| total turns | 254 turns | 296 turns | 294 turns | 515 turns | 349 turns |
| input tok | 18623k tok | 5110k tok | 6133k tok | 14577k tok | 8630k tok |
| output tok | 141k tok | 74.4k tok | 75.5k tok | 125k tok | 88.5k tok |
| total tok | 18764k tok | 5184k tok | 6209k tok | 14702k tok | 8719k tok |
| cache hit | 9.1% | 17.1% | 14.6% | 11.7% | 45.3% |
