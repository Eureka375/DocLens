# DocLens 桌面高保真设计原型

直接打开 [index.html](index.html) 查看 9 个 iframe 平铺界面，或打开 [desktop.html](desktop.html) 连续操作。全部资源已本地化，无需 npm、联网、API Key 或生产后端。

推荐在此目录运行 `python -m http.server 8765 --bind 127.0.0.1`，然后访问 `http://127.0.0.1:8765/index.html`。也可双击 HTML；file 协议的存储隔离因浏览器而异。不要同时打开多个编辑窗口修改同一篇演示笔记。

建议演示步骤：

1. 项目概览 → 文档库，查看四格式解析状态；可选本地 MD/TXT 临时预览，不进入预置研究矩阵。
2. 多文档比较，选 2–4 篇及数据集/方法，点击更新矩阵；选中第四篇可观察部分提取、证据不足。
3. 点击 CIFAR-10 / 轻量视觉编码，核对“仅提及”；点击其他单元格查看使用与否定状态。
4. 展开证据阅读，点击章节导航与“关联到笔记”；编辑正文，保存后刷新检查；导出 Markdown。
5. 版本比对查看三个预置差异，使用上一处/下一处。
6. 离线共享分别测试附带与不附带示例文本，下载 ZIP 后解压，打开 report.md。
7. P1 检索输入 ResNet 或不存在的关键词；设置可调整原文密度和恢复演示数据。

能力边界：这是设计原型。全部研究数据是合成示例；PDF/DOCX 为预置提取文本样式，未实现浏览器解析或原貌渲染；不实现通用研究分析、生产项目存储与安全包重导。笔记仅存此浏览器；共享 ZIP 为 doclens-ui-demo/1，不能承诺被生产应用读取。请勿在此存放个人文档或密钥。

工程结构：每个 HTML 指定 data-page；assets/app.js 提供公共导航、视图和交互；assets/data.js 提供合成数据；assets/app.css 定义主题与断点；assets/vendor 保存本地 Bootstrap 5.3.3（MIT）和 Lucide 0.468.0（ISC）资源及许可。自有界面 SVG 路径随此工程提供，不需外部字体。

需求与设计：[需求规格](../../docs/design/desktop-prototype/需求规格.md)、[设计说明](../../docs/design/desktop-prototype/设计说明.md)、[生成 Prompt](../../docs/design/desktop-prototype/中文原型生成Prompt.md)。检查与截图：[验证报告](../../docs/validation/desktop-prototype/验证报告.md)。在完整 ZIP 中保持相同相对目录，以上链接可用。
