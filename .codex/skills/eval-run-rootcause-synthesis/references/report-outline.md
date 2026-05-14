# 深度对比报告骨架

建议按下面结构写一份主文档：

## 1. 范围与数据源

- run 名称、run id、日期、CLI 二进制
- 使用了哪些本地文件
- 哪些证据缺失，例如 `router_trace_bundle.json` 为空

## 2. 统计口径

- 解释 `resolved`
- 解释 `f2p micro`
- 解释 `p2p micro`
- 如果看板值一样，拆成分子 / 分母

## 3. run 级结论

- 一张总表：`resolved`、`f2p micro`、`p2p micro`、`cost`、`turns`、`input tok`、`cache hit`
- 一段摘要：哪些变好了，哪些没变，哪些只是表面改善

## 4. case 级差异矩阵

- 每个 case 的 `resolved`、`f2p`、`p2p`
- 明确：
  - 谁决定了 `resolved`
  - 谁决定了 `f2p`
  - 谁决定了 `p2p`
  - 谁决定了成本

## 5. driver cases 深挖

每个 driver case 固定写：

- `当前状态`
- `概览`
- `判断`
- `证据`
- `为什么旧版错 / 新版对`
- `是否属于能力变化还是环境噪音`

## 6. 根因排序

建议至少分四类：

1. `localization / contract alignment`
2. `task understanding / self-report optimism`
3. `environment / install / dependency noise`
4. `validation gap`

## 7. 最终判断

- 这轮提升到底来自哪里
- 哪些结论可以归因给模型能力
- 哪些结论不能脱离环境因素去解释

## 8. 建议

- 下一轮应该固定哪些变量
- 哪些 case 值得当正例保留
- 哪些 case 需要单独隔离环境噪音再复验
