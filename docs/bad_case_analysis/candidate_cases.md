# Divergent Case Backlog

本文档记录目前已经观察到的 `innercc` / `claude-code` 结果分歧 case，作为后续 bad case 深挖候选池。

## 1. innercc 成功，claude-code 失败

按分析价值排序：

1. `dask__dask_2024.3.1_2024.4.0`
   - 已分析
   - 特征：无回归，但修错层级

2. `dask__dask_2023.9.2_2023.9.3`
   - 特征：`innercc` F2P `1.0`，`claude-code` F2P `0.5`
   - 价值：适合分析“部分修到”的定位误差

3. `iterative__dvc_3.4.0_3.5.0`
   - 特征：`innercc` F2P `1.0`，`claude-code` F2P `0.0`
   - 价值：适合分析 DVC 类复杂工作流上的 search / validation 策略差异

4. `iterative__dvc_3.12.0_3.13.0`
   - 特征：`innercc` F2P `1.0`，`claude-code` F2P `0.0`

5. `iterative__dvc_2.19.0_2.20.0`
   - 特征：`claude-code` 并非完全失败，F2P `0.642857...`
   - 价值：适合看“修到一半”的错误收敛路径

6. `iterative__dvc_0.30.0_0.30.1`
   - 特征：`innercc` 最终 resolved=true，但 run 内带 timeout 异常
   - 价值：适合分析“有异常但最终修成”的鲁棒性

## 2. claude-code 成功，innercc 失败

按分析价值排序：

1. `psf__requests_v2.12.2_v2.12.3`
   - 已分析
   - 特征：`innercc` 写坏代码并被错误验证掩盖

2. `iterative__dvc_1.0.0b6_1.0.0`
   - 特征：`claude-code` F2P `1.0`，`innercc` F2P `0.0`
   - 价值：适合作为第二个 `innercc` 失败样本，看是否仍然是 validation gap，还是纯 localization 问题

## 3. 推荐迭代顺序

建议下一轮按下面顺序继续：

1. `iterative__dvc_1.0.0b6_1.0.0`
   - 先验证 `innercc` 的失败是否和 `requests` case 同型

2. `dask__dask_2023.9.2_2023.9.3`
   - 看 `claude-code` 的“部分修复”路径

3. `iterative__dvc_3.4.0_3.5.0`
   - 看复杂 repo 上的错误定位与验证问题
