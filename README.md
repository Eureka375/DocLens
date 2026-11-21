# DocLens 0.1.0

Windows 桌面文档比对工具。分别选择原文档与新版文档，点击「开始比对」。结果按组计数，红色高亮显示旧内容，绿色高亮显示新内容。「上一处」和「下一处」会定位到双方正文，并在窗口下方标出原文位置。整个流程可离线运行。

## 启动

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

## 支持范围

- TXT 默认 UTF-8，支持 BOM。旧版中文文本可在相应列中显式选择 GB18030 再比对。
- DOCX 提取正文段落、可见超链接文字和表格文字。含未处理修订的文档会提示另存副本。页眉页脚、批注、脚注、部分 Word 域、文本框、公式、图片和样式不在正文比对范围内。
- 文件读取上限为 10 MiB，提取后的正文上限为 100,000 个 Unicode 码点。DOCX 还有压缩包大小和内部条目数限制。
- 差异按连续变化分组。复杂长区间会降级为粗粒度显示，段落移动可能显示为删除和新增。双栏展示的是提取后的文字，行末统一为换行符。
- 取消在读取和计算的阶段边界生效。已开始的单次解析或匹配调用需要返回后才能确认取消。
- 文件夹检索、AI 解释和 PDF 属于后续开发。长文响应时间与无 Python 环境的打包运行仍需专项验收。

## 开发验证

```powershell
$env:QT_QUICK_BACKEND = 'software'
uv run --locked pytest -q
```

`src/doclens/documents.py` 解析只读快照，`diff.py` 生成差异和原文位置，`app.py` 负责后台任务与 Qt 的 UTF-16 位置映射。`tests/` 包含解析、差异和真实窗口的集成用例。
