# DocLens 0.4.0

Windows 桌面文档比对工具，支持双栏比对、文件夹关键词检索和关联原文的 AI 差异解释。比对和检索可离线运行。

## 项目资料

- 技术方案和早期验证资料保存在项目的本地归档中。
- [PDF 与段落移动样例](examples/PDF比对/测试指南.md)、[跳转样例](examples/跳转测试/)和 [进阶案例指南](examples/进阶测试案例/测试指南.txt)位于 `examples/`。
- [Windows 发布包](releases/README.md)按版本保存。当前便携版位于 `dist/v0.4.0/DocLens/`，可运行该目录中的 `DocLens.exe`。
- V0.4.0 新增[原貌比较](docs/design/2026-11-22-original-layout.md)：PDF 直接显示原页面，DOCX 使用本机 Microsoft Word 将临时副本转换为只读页面；保留标题、字体、表格、图片、页眉与分页的显示。参见[示例](examples/原貌比对/测试指南.md)和[验证截图](docs/validation/original-layout/验证报告.md)。
- 后续成果按 [项目存放约定](AGENTS.md)归档。
- V0.3.1 包含结构化解析与分层比较：[开源核验及设计](docs/design/2026-11-22-open-source-review.md)、[源码验证记录](docs/validation/structured-comparison/验证报告.md)、[打包验证](docs/validation/v0.3.1/验证报告.md)、[结构化比对示例](examples/结构化比对/测试指南.md)。

## 启动

分别选择原文档与新版文档，点击「开始比对」。旧内容用红色高亮，新内容用绿色高亮，识别到的移动段落在双栏用蓝色高亮。打开「跳转到差异」列表可直接选择任意一组，双栏会滚动到对应原文。「上一处」和「下一处」可逐项浏览。PDF 差异标注页码与提取后的行号。

DOCX/PDF 默认显示原貌，两列可分别切换“原貌 / 文字”，并缩小、适宽或放大页面。DOCX 原貌需要本机安装并激活 Microsoft Word；PDF 原貌不依赖 Word。没有 Word、转换失败或预览超限时仍可用文字视图。页面上的标记对应正文差异；字体、表格形状、图片和页眉的变化尚不纳入比较。空白或重复文本等无法可靠映射时会提示切换文字核对。原貌预览最多 80 页，并有图像和临时存储总量限制。

在项目根目录用 PowerShell 执行。需要 Python 3.13 和 uv。首次安装依赖需要联网。

```powershell
uv sync --locked --python 3.13
uv run --locked python -m doclens
```

如果项目的 `.venv` 已配置好，可以直接运行 `./.venv/Scripts/python.exe -m doclens`，启动时无需访问网络。

也可以直接打开附带的示例：

```powershell
uv run --locked python -m doclens examples/原版.txt examples/新版.txt
```

## 测试任意跳转

```powershell
.\.venv\Scripts\python.exe -m doclens "examples/跳转测试/原版.txt" "examples/跳转测试/新版.txt"
```

预期显示 5 组差异（修改 3、删除 1、新增 1）。打开「跳转到差异」，直接选第 5 项，双栏应定位到文末的「45 天 → 90 天」；再选第 2 项，应返回文中的「20% → 35%」。第 3 项是删除纸质报送，第 4 项是新增状态变更通知。第 1 项位于文首，为「7 天 → 3 天」。

## 文件夹检索

1. 点击主窗口的「文件夹检索」，选择 `examples/跳转测试`。默认扫描当前目录，可以勾选「包含子文件夹」再扫描。
2. 在「已扫描文档」可打开任一文档的只读快照。输入两字词「留存」，预期两份文档各命中一个段落。点击任一搜索结果，右侧会滚动到原文并选中关键词。
3. 文件修改、新增或删除后点击「重新扫描」。损坏文件和省略结构见「扫描提示」。缓存保存在应用的本地数据目录 `workspaces` 下，窗口中的「清除缓存」只清除当前工作空间的索引。

检索支持区分大小写的字面查询，包括一两字中文和标点。结果按文件相关性和段落位置排序。一条结果定位该段落的首次命中。索引最多扫描 500 份文档，正文总量最多 500 万码点和 10 万文本块，结果最多显示 200 条。

## AI 差异分析

源码增量已优先支持论文与实验报告：新增[学术比较案例](examples/学术比较/测试指南.md)和[设计边界](docs/design/2026-11-22-academic-smart-comparison.md)。AI 分类包含研究问题、方法、数据、结果、结论和引用文献；保留通用分类。现有发布包尚未包含本次源码增量。

「请求格式」可选择自动识别、通用 Chat Completions、JSON 模式或 DeepSeek 格式。自动识别保持原有行为；JSON 模式需服务支持 `response_format`。其他鉴权方式和非 Chat Completions 协议尚不支持。每条 AI 解释必须完整引用所涉及差异组已提供的两侧证据（增删只有一侧）；无效响应会拒绝显示，仍可继续本地比对。章节路径也会随所选差异发送，在确认页可查看。

TXT/PDF 新增常见学术章节识别。编号标题仅推断内置的学术章节名称，首级限 1–20、最多六级且总长不超过80字符；自定义编号标题按普通段落比较，避免样本数和带单位小数被误认作标题。词级编辑范围已加入核心模型（英文词、小数、中文逐字），界面继续使用原有字符高亮。

1. 完成比对后点击「AI 分析」，输入服务的完整 HTTPS Chat Completions 地址、模型名称和 API Key。使用 DeepSeek 官方服务时，填 `https://api.deepseek.com/chat/completions` 和 `deepseek-flash`，密钥从 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 创建。DocLens 会为该地址使用 DeepSeek 的 `max_tokens` 和 JSON 输出。其他服务使用 `max_completion_tokens`，并须支持 Bearer 认证和非流式聊天响应。
2. 选择差异起止编号，点击「预览待发送内容」。查看实际片段、接收服务和模型后，再点击「确认发送」。片段来自选中的差异组，每次最多 20 组和 12,000 个请求数据字符。估算上限按字符计，模型供应商的 Token 限额单独生效。
3. 在测试文档选第 1 组时，模型应能从证据读出登记期限由 7 天缩短到 3 天。点击任一证据按钮，窗口会返回双栏并选中对应原文。模型说法应与原文核对。

API Key 和分析缓存仅保存在本次应用会话，可在应用内清缓存。更改服务地址会清空已输入的密钥。网络失败、取消或服务限流后可以手动重试。已发送的内容由所选模型服务处理。

## 支持范围

- TXT 默认 UTF-8，支持 BOM。旧版中文文本可在相应列中显式选择 GB18030 再比对。
- DOCX 提取正文段落、可见超链接文字和表格文字。含未处理修订的文档会提示另存副本。页眉页脚、批注、脚注、部分 Word 域、文本框、公式、图片和样式不在正文比对范围内。
- 支持文本型 PDF，可与 TXT、DOCX 混合比对，也可加入文件夹索引。纯扫描件需先做 OCR，混合文档的无文字页会在比对和检索中提示。PDF 以提取文本的阅读顺序为准，复杂分栏、表格、字体映射可能影响提取质量。
- 文件读取上限为 10 MiB，提取后的正文上限为 100,000 个 Unicode 码点。PDF 每份最多 300 页，遇到加密或内容超过解析上限时会提示。DOCX 也有压缩包大小和内部条目数限制。
- 差异按连续变化分组。长区间优先借助顺序一致的相同文本拆开远距离修改。两版各只出现一次、文字完全相同且能从新增与删除对应起来的文本块会显示为移动。重复文字、移动时同时改写的块及其他无法匹配的位置变化按普通差异显示。
- 源码比较先用唯一标题路径划分区域，再比较文本块和字符。DOCX 保留标题、列表及嵌套表格单元格元数据；TXT/PDF 保守识别 `#` 与“第…章/节”标题，PDF 保留页码。相邻且能逐段对应的修改会细分为独立差异；拆段、合段、不相关改写或预算不足时保留完整区域。纯样式、自动编号和表格形状变化不纳入比对。
- 取消在读取和计算的阶段边界生效。已开始的单次解析或匹配调用需要返回后才能确认取消。
- 模型协议与故障路径通过模拟服务验证，实际服务仍需用选定模型和凭据验收。

## 开发验证

```powershell
$env:QT_QUICK_BACKEND = 'software'
uv run --locked python -m pytest -q
```

`src/doclens/documents.py` 解析只读快照，`diff.py` 生成差异和原文位置，`workspace.py` 建立本地索引，`analysis.py` 构造请求并校验证据。`tests/` 包含核心与窗口集成用例。

在 Windows 上可用 PyInstaller 重新打包。验证脚本会添加示例、生成 ZIP，并从独立解压目录验证启动。保留整个 `dist/v0.4.0/DocLens` 目录再运行其中的 `DocLens.exe`。

```powershell
uv pip install --python .\.venv\Scripts\python.exe PyInstaller==6.22.3
.\scripts\package.ps1 -OutputDirectory dist/v0.4.0
.\.venv\Scripts\python.exe scripts/verify_windows_release.py 0.4.0 --with-word
```
