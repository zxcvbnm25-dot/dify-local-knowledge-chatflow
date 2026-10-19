# 导入与配置

1. 在 Dify Studio 新建 Advanced Chatflow，选择“导入 DSL”，导入 `local_knowledge_chatflow.yml`。
2. 在应用的环境变量中填写 `BRIDGE_API_KEY`。公开 DSL 中密钥为空；请只在 Dify 界面配置，不要提交真实密钥。
3. 将外部知识集绑定到你自己的 Dify 工作区。导入文件中的知识集 ID 属于原工作区，迁移后需在“检索本地知识库”节点重新选择。
4. 当前发布图使用 DeepSeek V4.1 Flash。导入后确认 Dify 中安装了对应模型插件并重新绑定可用模型。
5. 确认 Dify 容器能访问本地 bridge。`host.docker.internal:8004` 是原部署地址，换环境时请调整检索与图片接口地址。
6. 先测试无附件、文档附件和图片附件，再检查答案引用及资料链接。扫描型 PDF 没有可提取文字时可能无法读取。

## 附件处理

Markdown、TXT、PDF、PNG、JPG、JPEG、HEIC 附件只作为本轮回答上下文；该流程不会把它们送到 `/ingest` 或写入 Qdrant。Dify 平台仍可能按自身设置保留会话和上传文件，请检查实例的保留策略。

## 关于文件来源

DSL 的工作流图来自当前 Dify 发布版本的图快照；其余应用导入配置沿用本地 DSL 底稿。由于 DSL 不携带有效密钥，导入后仍需按本说明绑定环境变量、模型和知识集。
