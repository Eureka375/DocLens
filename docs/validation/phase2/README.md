# DocLens 第二轮（v0.3.1 候选）验证报告

验证日期：2026-11-22。对应分支 `feat/diff-evidence-regression`，PR [#2](https://github.com/Eureka375/DocLens/pull/2)。
发布版本仍为未经代码签名的候选，尚未合并到 `main`。

## 完成内容与代码位置

| 目标 | 代码与测试 |
| --- | --- |
| 复杂结构文档验证 | `tests/test_realistic_documents.py`：有标题、表格、32 个编号条款的 DOCX、跨页 PDF、长文本及重复相似段落 |
| 编辑后移动 | `src/doclens/edited_moves.py`、`diff.py`、`models.py`、`app.py`：`move_replace`，使用跨越稳定锚点、文本相似度、互为最佳且有分差的保守判断 |
| AI 证据验证 | `analysis.py`、`analysis_ui.py`、`AnalysisDialog.qml`：逐字摘录核对、单数值方向矛盾检查、核验状态显示；旧模型只返回证据 ID 时继续兼容但标为人工核对 |
| 新旧对照 | `scripts/compare_baseline.py` 固定读取主分支旧提交 `138c0e7ac3114249a845ec082c9c2870b01cd12b` |
| Windows 构建 | `.github/workflows/ci.yml`、`scripts/DocLens.iss`：便携 ZIP、每用户安装包 EXE、SHA256 和安装/启动冒烟测试 |

## 测试结果

运行环境为 GitHub Actions Python 3.13。Linux 核心测试 **62 passed**；Windows PySide6 桌面测试 **11 passed**。另有打包构建流程在 Windows runner 上通过（[成功构建运行 #44994914907](https://github.com/Eureka375/DocLens/actions/runs/44994914907)）。后续提交请以 [CI 工作流的最新结果](https://github.com/Eureka375/DocLens/actions/workflows/ci.yml) 为准。

11 个标注案例，共计 16 个预期差异，所有算法都使用相同输入、相同文本快照和同一 Python 进程的依赖；比较了固定旧版与当前版：

| 指标 | 原版 | 改进版 |
| --- | ---: | ---: |
| TP / FP / FN | 8 / 7 / 8 | 16 / 0 / 0 |
| Precision | 0.5333 | 1.0000 |
| Recall | 0.5000 | 1.0000 |
| F1 | 0.5161 | 1.0000 |

这些是专门针对已知边界场景设计的样例，不是随机抽取的生产文档集合，**不可概括为生产环境真实准确率**。DOCX 复杂样本由测试代码生成；PDF 使用仓库现有的跨页示例，不能称为第三方真实业务样本。

### 算法延迟对照

同一 Ubuntu CI 环境，单纯执行 Diff，不含文档解析、网络、AI、GUI；每组 10 次，记录中位耗时（毫秒）。

| 规模 | 旧版 | 改进版 |
| --- | ---: | ---: |
| 300 段 | 0.348 | 0.429 |
| 1000 段 | 0.998 | 1.256 |
| 3000 段 | 3.225 | 4.005 |

新算法在这些稀疏修改样本中略慢，这是保守配对检查的额外开销。测试脚本在没有可能发生位置移动的普通一对一替换时跳过全局锚点扫描，以控制成本。详尽 JSON 由 CI 保存为 Artifacts：`diff-metrics`。

## 校验边界

- `move_replace` 的判定限于**单段落、高文本相似度、唯一且跨越稳定锚点**的情况；复杂多段落改写不保证正确识别。重复或模糊匹配采用普通新增/删除/替换，宁可漏判也不强行宣称移动。
- 原文摘录经过严格字符串包含判断，并能定位到左右两侧文档，但摘录真实 **不意味着 AI 结论逻辑正确**。方向检查只覆盖时间/金额类且双方各只有一个数字的明确情形；不能自动证明法律含义或事实准确性。
- 新版 `move_replace` 扩展了 `Change.kind` 的取值；已有的四种变更类型仍然兼容，面向该枚举的第三方调用者需要适配新类型。
- Windows 安装版通过安装目录可执行文件的 `--help` 冒烟测试，不代表所有 Windows 系统/权限、杀毒软件或长期 GUI 使用都已验证。
- 尚未引入开放领域的大样本人工标注语料、复杂扫描 PDF OCR、端到端真实云端模型语义准确率测评及代码签名。

## 复现实验

```powershell
uv sync --locked --python 3.13
uv run --locked python -m pytest -q
uv run --locked python scripts/benchmark_diff.py --repeats 10 --output build/diff-metrics.json
uv run --locked python scripts/compare_baseline.py --repeats 10 --output build/baseline-comparison.json
```

旧版对照脚本需要 Git 完整历史。打包 Windows 版见 [v0.3.1 发布候选说明](../../../releases/v0.3.1/README.md)。对照结果以日志的 Git SHA 和运行环境为准，不能用于跨机器速度保证。
