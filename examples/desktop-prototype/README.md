# DocLens 关键词研究桌面原型 1.2

直接打开 [index.html](index.html) 查看 8 个平铺画板，或打开 [desktop.html](desktop.html) 连续操作。资源随工程提供，无需安装依赖。Windows 端验证使用 Edge。

双击 HTML 即可试用。浏览器对本地文件的存储规则不同时，可在本目录运行 `python -m http.server 8765 --bind 127.0.0.1`，访问 `http://127.0.0.1:8765/index.html`。在同一浏览器和访问地址中重开可读取已保存的演示数据。

1. 项目与文档打开文档库，查看四格式的示例解析状态，或选择 MD/TXT 临时预览。
2. 在关键词比较中点击 `ResNet`，选择文档范围、对照原文。输入新词可实际执行字面查找。
3. 点击「本地文本比较」，检查两篇示例的 `50` 和 `100` 差异。在下拉列表换一篇或换一个片段。
4. 点击「AI 分析用途」，打开「预览发送范围」，取消勾选对比表征研究的第二处，再确认。可查看预设结果、部分覆盖计数和对应原文。
5. 从多个片段点击「加入笔记」。打开研究笔记，编辑后保存并刷新，检查引用仍能分别回到原文。
6. 在导出与共享下载 Markdown，或分别下载带与不带示例原始文本的 ZIP。解压后打开 report.md。

打开[长文档案例](long.html)可从第 8 章直接比较训练 50 轮和 100 轮。两篇示例各 12 章、288 个正文段落，`ResNet` 合计命中 72 段。按文档展开命中时每次增加 8 段，点击段落可以跳到对应章节。AI 预览默认选中比较中的两段，最多可确认 20 段。长案例的笔记和词表单独保存。

可下载真实可打开的合成 Markdown 文件 [长文档 A](sample-documents/视觉编码实验记录A.md) 和 [长文档 B](sample-documents/视觉编码文献记录B.md)，在文档库临时预览，或在已有 DocLens 桌面版导入。关键词比较工程的长案例使用同一组正文。示例数值供界面演示。

原词查找、两段 Diff、多来源笔记和下载在浏览器中运行。所有研究材料均为合成示例。AI 使用预置判断，不发网络请求。PDF/DOCX 以预置文本展示，MD/TXT 临时预览不加入示例比较。ZIP 采用演示格式 `doclens-ui-demo/2`。正式 API、项目读写、旧版迁移和共享包重导由桌面应用实现。

每个页面通过 `data-page` 加载公共视图。`assets/compare.js` 提供原词匹配和片段 Diff，`assets/research-app.js` 提供界面与交互，`assets/research-data.js` 和 `assets/long-data.js` 提供合成样例，`assets/research.css` 定义桌面布局。Bootstrap 5.3.3（MIT）和 Lucide 0.468.0（ISC）许可随 `assets/vendor` 提供。

[新版需求规格](../../docs/design/keyword-research-mvp.md) · [原型设计说明](../../docs/design/desktop-prototype/关键词研究版设计说明.md) · [验证报告与截图](../../docs/validation/keyword-prototype/验证报告.md)
