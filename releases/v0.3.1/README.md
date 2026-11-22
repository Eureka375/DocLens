# DocLens v0.3.1 Windows 构建说明

本版本在 v0.3.0 的离线文档比较、检索和 AI 原文证据功能上增加：

- 高置信度的“移动并修改”识别，以及对应的移动位置和字符级变化双重高亮。
- 改进相似段落匹配与复杂替换区间的移动恢复。
- AI 逐字摘录核对与部分单数值方向矛盾检查；旧协议仅引用 ID 时明确显示需人工核对。
- DOCX、PDF、长文本集成测试，11 组人工标注测试和固定基线的误报/漏报对比。
- 可重复执行的 GitHub Actions 回归、性能测试、Windows EXE 便携包和 Inno Setup 每用户安装包构建。

## 下载及验证

查看 PR #2 中最新的绿色 [GitHub Actions 工作流](https://github.com/Eureka375/DocLens/actions/workflows/ci.yml)；点击对应运行页面底部的 **Artifacts**，下载 `DocLens-0.3.1-windows-x64`，内含：

- `DocLens-Setup-0.3.1-x64.exe`：安装到当前用户目录，无需管理员权限。
- `DocLens-0.3.1-portable-x64.zip`：解压后运行 `DocLens/DocLens.exe`。
- `SHA256SUMS.txt`：两份可执行包的哈希校验值。

该构建由 CI 生成，并非签名的官方生产发行；Windows 可能提示未知发布者。请仅从仓库关联的 GitHub Actions 下载并核对 SHA256，不要从第三方镜像运行。

## 兼容性和局限

- 保留现有 TXT、DOCX、文本型 PDF 解析、原文跳转、文件夹检索及 AI 授权预览。
- 复杂重排、多段落同时移动并改写、扫描 PDF OCR 及语义真实性自动证明尚未解决；需人工确认重要结论。
- 同一标注测试集内的准确率提升不能推断为所有文档的实际表现。
- 便携版请保留整个解压目录，不能只复制 `DocLens.exe`。

[第二轮验证报告](../../docs/validation/phase2/README.md) · [上一版本说明](../v0.3.0/README.md)。
