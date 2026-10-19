# 本地知识库问答：让资料真的派上用场

资料散在笔记、文档和截图里时，难的往往不是“问 AI”，而是弄清它凭什么这么回答。

这是一个在 Dify 中逐步打磨的本地知识库 Chatflow：先理解问题并检索资料，再让回答只引用能核对的证据。本轮上传的附件也能参与理解，但不会被这个流程送去入库。它适合作为搭建本地 RAG 的学习起点；bridge、向量库和模型仍需要你自己的环境。

## 先从流程总览开始

![六阶段流程导航](workflow/workflow-overview.png)

这张图和后面的分段图都由公开 DSL 重绘，便于阅读结构与实际分支；它们不是 Dify 画布截图。完整配置请继续往下读。

## 分段学习

[分段学习指南](workflow/LEARNING.md)按附件、检索计划、检索与故障、证据校验、关联原图、回答输出六段解释机制与失败分支，并嵌入六张可放大的中文流程图。

| 阶段 | 图 | 学习重点 |
| --- | --- | --- |
| 01 | [本轮附件](workflow/section-01.png) | 图片/文档分流与临时上下文 |
| 02 | [检索计划](workflow/section-02.png) | JSON 计划、校验与澄清分支 |
| 03 | [检索与故障](workflow/section-03.png) | bridge 请求与服务异常区分 |
| 04 | [证据筛选与校验](workflow/section-04.png) | 连续原文摘录和代码验证 |
| 05 | [关联原图解读](workflow/section-05.png) | 下载校验和视觉补充 |
| 06 | [答案与引用输出](workflow/section-06.png) | 已验证引用的最终把关 |

## 节点参考

[完整节点参考](workflow/NODE_REFERENCE.md)覆盖全部 40 个节点：真实变量选择器、输出、条件、模型配置、完整提示词、全部 Python 代码和其余 DSL 配置均可按节点 ID 对照。

## 导入与配置

[导入说明](workflow/IMPORT.md)说明模型插件、bridge 地址、密钥和本轮附件行为。公开 DSL 中不含有效密钥；请只在自己的 Dify 环境变量中填写 `BRIDGE_API_KEY`。

## DSL

[下载 Dify Chatflow DSL](workflow/local_knowledge_chatflow.yml)。该文件的工作流图来自当前发布图快照，其余应用导入配置沿用本地 DSL 底稿。它尚未在另一套 Dify 环境完成导入和运行验证，导入后请自行绑定模型、知识资源和 bridge 后测试。
