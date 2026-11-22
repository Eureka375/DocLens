# DocLens 0.3.1（待合并）

Windows 桌面文档比对工具，支持双栏比对、文件夹关键词检索和关联原文的 AI 差异解释。比对和检索可离线运行。

## 项目资料

- 技术方案和早期验证资料保存在项目的本地归档中。
- [PDF 与段落移动样例](examples/PDF比对/测试指南.md)、[跳转样例](examples/跳转测试/)和 [进阶案例指南](examples/进阶测试案例/测试指南.txt)位于 `examples/`。
- [Windows 发布包](releases/README.md)按版本保存。v0.3.1 安装版和便携版由 GitHub Actions 构建并作为 CI Artifacts 提供；既有 v0.3.0 便携版仍位于本机 `dist/v0.3.0/DocLens/`。
- 后续成果按 [项目存放约定](AGENTS.md)归档。

## 启动

分别选择原文档与新版文档，点击「开始比对」。旧内容用红色高亮，新内容用绿色高亮，识别到的原样移动段落在双栏用蓝色高亮。对于高置信度的移动并修改，未变部分用蓝色标记，修改字符用红色/绿色标记。打开「跳转到差异」列表可直接选择任意一组，双栏会滚动到对应原文。「上一处」和「下一处」可逐项浏览。PDF 差异标注页码与提取后的行号。

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

1. 完成比对后点击「AI 分析」，输入服务的完整 HTTPS Chat Completions 地址、模型名称和 API Key。使用 DeepSeek 官方服务时，填 `https://api.deepseek.com/chat/completions` 和 `deepseek-flash`，密钥从 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 创建。DocLens 会为该地址使用 DeepSeek 的 `max_tokens` 和 JSON 输出。其他服务使用 `max_completion_tokens`，并须支持 Bearer 认证和非流式聊天响应。
2. 选择差异起止编号，点击「预览待发送内容」。查看实际片段、接收服务和模型后，再点击「确认发送」。片段来自选中的差异组，每次最多 20 组和 12,000 个请求数据字符。估算上限按字符计，模型供应商的 Token 限额单独生效。
3. 在测试文档选第 1 组时，模型应能从证据读出登记期限由 7 天缩短到 3 天。点击任一证据按钮，窗口会返回双栏并选中对应原文。新版提示模型返回逐字引用摘录，并核验摘录是否真的出现在对应证据中；还会拒绝部分明显违反单一数值增减方向的说法。兼容旧模型的仅 ID 回答会明确标注为需人工核对。**引用校验不等于保证语义结论正确。**

API Key 和分析缓存仅保存在本次应用会话，可在应用内清缓存。更改服务地址会清空已输入的密钥。网络失败、取消或服务限流后可以手动重试。已发送的内容由所选模型服务处理。

## 支持范围

- TXT 默认 UTF-8，支持 BOM。旧版中文文本可在相应列中显式选择 GB18030 再比对。
- DOCX 提取正文段落、可见超链接文字和表格文字。含未处理修订的文档会提示另存副本。页眉页脚、批注、脚注、部分 Word 域、文本框、公式、图片和样式不在正文比对范围内。
- 支持文本型 PDF，可与 TXT、DOCX 混合比对，也可加入文件夹索引。纯扫描件需先做 OCR，混合文档的无文字页会在比对和检索中提示。PDF 以提取文本的阅读顺序为准，复杂分栏、表格、字体映射可能影响提取质量。
- 文件读取上限为 10 MiB，提取后的正文上限为 100,000 个 Unicode 码点。PDF 每份最多 300 页，遇到加密或内容超过解析上限时会提示。DOCX 也有压缩包大小和内部条目数限制。
- 差异按连续变化分组。长区间借助相似段落和顺序一致的锚点对齐。完全一致的唯一内容块可识别为移动。移动时改写且可由稳定锚点、较高文本相似度及唯一性条件共同确认的单段落，报告为“移动并修改”；不满足条件（含重复/复杂跨段落移动）的内容仍可能退化为普通新增、删除或替换。
- 取消在读取和计算的阶段边界生效。已开始的单次解析或匹配调用需要返回后才能确认取消。
- 模型协议与故障路径通过模拟服务验证，实际服务仍需用选定模型和凭据验收。

## 开发验证

```powershell
$env:QT_QUICK_BACKEND = 'software'
uv run --locked python -m pytest -q
```

`src/doclens/documents.py` 解析只读快照，`diff.py` 生成差异和原文位置，`workspace.py` 建立本地索引，`analysis.py` 构造请求并校验证据。`tests/` 包含核心与窗口集成用例。

在 Windows 上可用 PyInstaller 重新打包。保留整个 `dist/DocLens` 目录再运行其中的 `DocLens.exe`。

```powershell
uv pip install --python .\.venv\Scripts\python.exe PyInstaller==6.22.3
.\scripts\package.ps1
```

## 第一轮差异算法质量保障

本轮采用保守的段落相似匹配辅助对齐；仅在原文和新版中全局唯一、文字完全一致的内容块上确认移动。对于不能可靠配对的内容，继续使用现有的新增、删除、替换结果。拆分与合并保留为一个或多个 `replace` 差异组，未增加不兼容的新 `Change.kind`。

AI 分析每条结果必须引用已发送的证据 ID。引用某一差异组时，如发送了原文和新版两侧证据，两侧 ID 都必须出现，且点击仍可定位到原文。证据 ID 校验保证来源可定位，不等于自动验证模型的语义推理正确。

完整测试与可重复的性能统计命令：

```powershell
uv run --locked python -m pytest -q
uv run --locked python scripts/benchmark_diff.py --repeats 5 --output build/diff-metrics.json
```

标注样例在 `tests/fixtures/diff_cases.json`，包括新增、删除、替换、移动、拆分、合并、相邻变化、混合移动和重复文字反例。自动化流程在 `.github/workflows/ci.yml`，Ubuntu 执行核心回归和性能统计，Windows 执行原有桌面交互测试；本地性能受硬件、文档特征和重复次数影响，不能直接与 CI 的数字等同。首轮验证记录见 [docs/validation/phase1/README.md](docs/validation/phase1/README.md)。

## 0.3.1 算法验证与 Windows 构建

- `tests/fixtures/diff_cases.json` 含新增、删除、替换、移动、拆分、合并、移动并修改和模糊重复负例。
- `tests/test_realistic_documents.py` 覆盖带章节与表格的 DOCX、多页 PDF 和长文本。**这些是可复现的复杂测试样例，不代表外部真实文档的统计分布。**
- `scripts/compare_baseline.py` 在相同输入和进程中加载固定的旧版 Git 提交 `138c0e7`，输出原版和当前版的精确匹配率、F1 和耗时。运行时需保留完整 Git 历史。
- `.github/workflows/ci.yml` 执行 Ubuntu 核心测试、Windows GUI 测试及 Windows 打包验收。CI 产物包括便携 ZIP、每用户安装版 EXE 和 SHA256 校验文件，在对应 Actions 运行的 Artifacts 中下载；文件为**未签名的测试候选版本**。
- `scripts/DocLens.iss` 提供 Inno Setup 安装脚本。可在 Windows 使用 `scripts/package.ps1` 先生成 `dist/DocLens`，再由 Inno Setup 6 编译。
- 验证报告：[首轮](docs/validation/phase1/README.md) · [第二轮](docs/validation/phase2/README.md)。发布说明见 [v0.3.1](releases/v0.3.1/README.md)。
