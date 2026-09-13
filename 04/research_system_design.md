# 六维 Hodge 类多 Agent 研究系统

## 目标

使三种互补的数学研究路线各自独立推进六维阿贝尔簇的 21 个子问题，在强制组会中交换证据、反例和新引理，然后继续长期研究，最后形成可审稿的论文草稿。

## 三条研究路线

- **A1 / Shimura-family**：跟踪参数族、Hodge locus、特殊化与退化关系，用族的视角连接各个子类。
- **A2 / Simple-Albert**：对 simple 六维情形按 Albert I–IV 型、End⁰和 Hodge 群计算 Hodge/除子/Weil 类。
- **A3 / Splitting-exception**：处理非 simple 分解、混合不变量和 exceptional Hodge classes，并搜索反例。

## 运行契约

1. 每条路线都必须覆盖全部 21 个 task，不是只做自己擅长的分支。
2. 任一路线证明一个问题就可向中心提交；中心立即启动该问题的 reviewer，只检查证明是否有严重数学错误，允许小的记号或表述错误。
3. reviewer 返回 APPROVE 后，Writer 立即将答案写入预先结构化的 21 个 LaTeX 章节；REVISE 则把具体问题退回原 agent。
4. 组会在第 10 分钟强制启动，A1、A2、A3 依次发言，再由会议主持人生成共享 digest，三个 agent 都必须将其写入后续 context。
5. 长效推理以各任务的 LangGraph 状态和运行文件表示；整个实验在第 20 分钟强制停止，并保存当前不完整的论文。
6. 每个结论必须区分 theorem / conjecture / heuristic / obstruction，不允许把猜想写成定理。

## 状态图

```text
A1/A2/A3 workers -> submit proof -> committee -> reviewer
                                      ├─ REVISE → original worker
                                      └─ APPROVE → Writer fills LaTeX slot

10 min: A1 → A2 → A3 → shared digest → all contexts
20 min: hard stop → preserve current 21-section LaTeX
```

每一轮都保存 agent 产物、消息、组会摘要和下一轮目标；论文汇总只读取已保存的证据，不覆盖原始研究记录。
