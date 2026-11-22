# DocLens 首轮改进验证报告（2026-11-22）

## 对象和范围

- 仓库：`Eureka375/DocLens`
- 基线：`main`，提交 `138c0e7ac3114249a845ec082c9c2870b01cd12b`
- 开发分支：`feat/diff-evidence-regression`
- PR：[DocLens #2](https://github.com/Eureka375/DocLens/pull/2)
- 验证运行：[GitHub Actions #44994173527](https://github.com/Eureka375/DocLens/actions/runs/44994173527)，执行的代码提交 `916593f990a93cad7ff5c52bb36e9b966537cab3`

## 功能改动

1. `src/doclens/alignment.py`：新增有界动态规划对齐相似段落、将部分隐藏在替换区间中的唯一精确移动显式拆出，保留原有比较 API。
2. `src/doclens/diff.py`：接入段落精细对齐和移动恢复；字符级差异计算和位置结构不变。
3. `src/doclens/analysis.py`：模型的每条结果按已引用差异组验证完整证据 ID，若一组有原文和新版证据，则必须同时引用。
4. `tests/fixtures/diff_cases.json`、`tests/test_diff_gold.py`：建立标注语料和回归断言，校验类型、左右原文片段、边界和细粒度编辑。
5. `tests/test_analysis_evidence.py`：覆盖缺失一侧证据、缺失跨组证据及伪造 ID。
6. `scripts/benchmark_diff.py`：统计标准语料的 TP/FP/FN、Precision/Recall/F1、比较延迟中位数与 P95 和 Python 追踪峰值分配。
7. `.github/workflows/ci.yml`：Ubuntu 运行核心回归和性能统计，Windows 运行 PySide6 桌面集成测试。

## 已运行的验证

| 项目 | 结果 |
| --- | --- |
| Ubuntu 非 GUI 自动化测试 | 53 passed，1.76 s |
| Windows 桌面集成测试 | 10 passed，8.59 s |
| 标注差异测试集 | 9 / 9 案例，13 / 13 预期差异 |
| 标注集 TP / FP / FN | 13 / 0 / 0 |
| 标注集 Precision / Recall / F1 | 1.0000 / 1.0000 / 1.0000 |

以上仅反映固定的小型标注样例和现有回归集；不能据此推断任意真实文档的准确率。Linux 上直接运行桌面集成测试曾在初始化 Qt 窗口时崩溃；随后拆分为 Ubuntu 核心任务和 Windows 桌面任务，第二次工作流两组测试均通过。

### GitHub Ubuntu Runner 的初步性能指标

用 `python scripts/benchmark_diff.py --repeats 3` 测得。每个规模仅修改三个文本块，不包括解析、GUI 或网络；测试需重复更多次数并扩展输入分布。

| 文本块 | 字符量 | 中位延迟 ms | P95 延迟 ms | Python 峰值分配 MiB |
| ---: | ---: | ---: | ---: | ---: |
| 300 | 7,799 | 0.360 | 0.368 | 0.040 |
| 1,000 | 25,999 | 1.031 | 1.074 | 0.216 |
| 3,000 | 77,999 | 3.611 | 4.633 | 0.812 |

`tracemalloc` 不记录所有原生库分配和进程总 RSS。由于每个规模只有三次耗时样本，P95 不具有稳定的统计意义；后续性能验收建议增大重复数及复杂度分层。

## 兼容性与限制

- 未修改 `Change`、`Comparison` 或 QML 使用的公开字段；拆分和合并仍以 `replace` 返回。
- 移动采用全局唯一且完全相同的块，改写移动、重复段落的移动仍可能退化为普通 Diff。
- AI 返回结果可以通过 ID 关联到局部原文，**但模型的解释是否真正由原文支持仍需要人工审查**，不能单凭引用 ID 判断事实性。
- 相似度对齐采用阈值与计算预算，超限或无法可靠配对时回退原有算法；后续应增加真实 DOCX/PDF、重复文本、跨章节大幅调整与恶意输入语料。
- 尚未对照基线版本测量真实语料的误报、漏报变化，也没有执行真实云端模型服务验收。
- 此分支尚未合并 `main`，Windows 本地发行包也未重新构建。

## 复现命令

```powershell
uv sync --locked --python 3.13
uv run --locked python -m pytest -q
uv run --locked python scripts/benchmark_diff.py --repeats 5 --output build/diff-metrics.json
```
