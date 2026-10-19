# 导入与配置

1. 在 Dify Studio 新建 Advanced Chatflow，选择“导入 DSL”，导入 `local_knowledge_chatflow.yml`。
2. 在应用的环境变量中填写 `BRIDGE_API_KEY`。公开 DSL 中密钥为空；请只在 Dify 界面配置，不要提交真实密钥。
3. 本流程通过 HTTP 调用本地 bridge 检索，并没有 Dify 原生知识检索节点。检查“构建知识检索请求”和“构建图片检索请求”代码中的 `knowledge_id: local_all`，将它改成目标 bridge 支持的知识库标识；它不是在 Dify 下拉框里重新选择知识集。
4. DSL 中模型标识为 `deepseek-flash`，provider 为 `langgenius/deepseek/deepseek`。导入文件的 `dependencies` 为空，请先在目标 Dify 环境安装对应插件并重新绑定可用模型；视觉节点还需确认所选模型和插件支持图片输入。
5. 确认 Dify 容器能访问本地 bridge。`host.docker.internal:8004` 是原部署地址，换环境时请调整检索与图片接口地址。
6. 先测试无附件、文档附件和图片附件，再检查答案引用及资料链接。扫描型 PDF 没有可提取文字时可能无法读取。

## 附件处理

Markdown、TXT、PDF、PNG、JPG、JPEG、HEIC 附件只作为本轮回答上下文；该流程不会把它们送到 `/ingest` 或写入 Qdrant。Dify 平台仍可能按自身设置保留会话和上传文件，请检查实例的保留策略。

## 关于文件来源

DSL 的工作流图来自当前 Dify 发布版本的图快照；其余应用导入配置沿用本地 DSL 底稿。由于 DSL 不携带有效密钥，导入后仍需按本说明绑定环境变量、模型，并核对 bridge 地址与 knowledge_id。

## 学习与验证

建议先阅读 [分段学习指南](LEARNING.md)，再对照 [完整节点参考](NODE_REFERENCE.md) 查看提示词、代码和变量。文档与图示以仓库 DSL 为依据，不代表已在另一套 Dify 环境导入并运行通过。
