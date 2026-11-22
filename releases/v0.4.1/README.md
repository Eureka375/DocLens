# DocLens V0.4.1 Windows 便携版

2026-11-22。解压完整 ZIP 后运行 `DocLens/DocLens.exe`，保留 `_internal` 和其他文件；也可直接运行项目中的 `dist/v0.4.1/DocLens/DocLens.exe`。

- 包含传统Diff和可选AI语义解释，优先论文/实验报告场景；新增学术变化分类、章节上下文和双侧引用完整校验。
- AI窗口可配置请求格式。填写一次API Key后点击“保存设置”，或确认发送时自动保存，重启后留空即可使用保存的密钥。
- 地址、模型、请求格式随密钥保存；Windows当前用户加密保护，不随便携目录迁移。支持替换或清除；换服务地址不会自动发送旧密钥。
- TXT/PDF识别常见学术章节；核心增加词级范围，界面继续使用字符高亮。附带“示例/学术比较/”案例，预期3组变化。
- 保留原貌预览、文件夹检索、证据跳转及TXT/DOCX/PDF混合比较。

AI仍需自行配置服务和凭据；网络或无效响应失败时可继续本地比较。真实服务输出需核对原文，不能保证语义正确性；被撤销或过期的密钥需更新。DOCX原貌需要本机Microsoft Word，PDF原貌不依赖Word。OCR、公式及图片内容比较尚不支持。

新增功能[验证记录](../../docs/validation/remember-ai-settings/验证报告.md) · [学术比较验证](../../docs/validation/academic-smart-comparison/验证报告.md) · [本版打包验证](../../docs/validation/v0.4.1/验证报告.md)
