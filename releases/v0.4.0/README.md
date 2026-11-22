# DocLens V0.4.0 Windows 便携版

原貌比较版，2026-11-22。

解压完整 ZIP 后运行 `DocLens/DocLens.exe`，保留 `_internal` 与其他随附文件。

- DOCX 用本机 Microsoft Word 生成只读页面，保留原文档的字体、标题、表格、图片、页眉与分页显示；原件不保存修改。
- PDF 直接显示原页面，无需 Word。TXT 继续使用文字视图。
- 原貌页叠加红/绿/蓝差异标记，支持按差异跳转、两侧各自切换文字视图与缩放。
- `示例/原貌比对/` 包含两页 Word 文档，预期 4 组修改，包含表格内数字变化。

Word 原貌需要安装并激活 Microsoft Word，未安装或转换失败时回退文字显示。当前比较正文文字，不比较字体样式、图片、表格形状、页眉等变化。无法可靠映射、重复文字及纯空格变化会提示切换文字视图核对。原貌最多80页，另有图像与存储总量限制；扫描件 OCR 仍需在外部完成。

新增依赖为 pypdfium2 5.15.2 与 Pillow 12.3.0；随包在 `_internal` 的相应 dist-info 目录中保留完整许可证与 PDFium 依赖声明。

[原貌验证和截图](../../docs/validation/original-layout/验证报告.md) · [打包验证](../../docs/validation/v0.4.0/验证报告.md)
