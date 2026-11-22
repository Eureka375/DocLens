from pathlib import Path
import argparse
import hashlib
import json
import re
import ctypes
from ctypes import wintypes
import os
import shutil
import subprocess
import time
import zipfile


parser = argparse.ArgumentParser(description="Verify and archive a built Windows bundle")
parser.add_argument("version", help="Three-part version, for example 0.3.1")
parser.add_argument("--with-word", action="store_true", help="Also smoke-test the local Word preview")
args = parser.parse_args()
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.version):
    parser.error("version must contain three numeric components")
version = args.version
smart_analysis = tuple(map(int, version.split("."))) >= (0, 4, 1)
extended_timeout = tuple(map(int, version.split("."))) >= (0, 4, 2)
review_workflow = tuple(map(int, version.split("."))) >= (0, 5, 0)
home_ai = tuple(map(int, version.split("."))) >= (0, 5, 1)
root = Path(__file__).resolve().parents[1]
dist = root / "dist" / f"v{version}"
bundle = dist / "DocLens"
release = root / "releases" / f"v{version}"
archive = release / f"DocLens-V{version}-Windows.zip"
if not (bundle / "DocLens.exe").is_file():
    raise SystemExit("Build the Windows bundle first using scripts/package.ps1")
release.mkdir(parents=True, exist_ok=True)
for name in ("PDF比对", "结构化比对"):
    shutil.copytree(root / "examples" / name, bundle / "示例" / name, dirs_exist_ok=True)
if smart_analysis:
    shutil.copytree(root / "examples" / "学术比较", bundle / "示例" / "学术比较", dirs_exist_ok=True)
if args.with_word:
    shutil.copytree(root / "examples" / "原貌比对", bundle / "示例" / "原貌比对", dirs_exist_ok=True)
(bundle / "使用说明.md").write_text(
    f"# DocLens V{version} Windows 便携版\n\n"
    "双击本目录 DocLens.exe。保留 _internal 和其余文件，不要单独移动 EXE。\n\n"
    "分别打开 [原版](示例/结构化比对/原版.txt) 和 [新版](示例/结构化比对/新版.txt)，预期 3 组修改。\n"
    "[结构化比对指南](示例/结构化比对/测试指南.md) · [PDF 比对指南](示例/PDF比对/测试指南.md)\n\n"
    "比对和检索可离线使用；AI 分析需要自行配置服务。扫描 PDF 需先 OCR。\n",
    encoding="utf-8",
)

# Confirm the new parser module actually reached the frozen archive.
from PyInstaller.archive.readers import CArchiveReader
embedded = CArchiveReader(str(bundle / "DocLens.exe")).open_embedded_archive("PYZ.pyz")
assert "doclens.structure" in embedded.toc, "Structured parser missing from frozen application"
if smart_analysis:
    for module in ("doclens.analysis", "doclens.analysis_ui", "doclens.providers", "doclens.settings"):
        assert module in embedded.toc, f"AI module missing: {module}"
    qml = (bundle / "_internal" / "doclens" / "ui" / "AnalysisDialog.qml").read_text(encoding="utf-8")
    for control in ("aiSaveSettings", "aiClearSettings", "aiProvider"):
        assert control in qml, f"AI control missing: {control}"
    assert not list(bundle.rglob("ai-settings.bin")), "User AI settings must not be bundled"
    if extended_timeout:
        frozen_analysis = embedded.extract("doclens.analysis_ui")
        assert 120_000 in frozen_analysis.co_consts, "Two-minute timeout missing from frozen application"
    with (bundle / "使用说明.md").open("a", encoding="utf-8") as guide:
        guide.write("\n[学术比较案例](示例/学术比较/测试指南.md)预期3组修改。\n"
                    "AI分析需填写服务地址、模型和API Key；保存设置或确认发送后会加密记住，重启可复用。\n"
                    "可在AI窗口替换密钥或清除保存的设置。切换服务地址不会带入旧密钥。\n"
                    "密钥由Windows当前用户保护，不随便携目录迁移。实际模型需自行配置并核对结果。\n")
        if extended_timeout:
            guide.write("AI分析最长等待120秒，可随时取消；超时后可手动重试。\n")
if review_workflow:
    assert "doclens.review" in embedded.toc, "Review report module missing"
    review_qml = bundle / "_internal" / "doclens" / "ui" / "ReviewPane.qml"
    assert review_qml.is_file(), "Review pane missing"
    assert "aiPrepareMissing" in qml and "aiCoverage" in qml
    with (bundle / "使用说明.md").open("a", encoding="utf-8") as guide:
        guide.write("\nV0.5.0：宽窗口左侧提供差异审阅列表，支持类型/核对状态/AI类别筛选、搜索、备注和已核对标记。\n"
                    "备注回车或离开输入框保存；换文件/重比会清空，请用导出HTML报告留档。\n"
                    "AI每批最多4组、每请求12,000字符，每次最多20组、总60,000字符；确认后顺序发送。\n"
                    "失败停止剩余批次并保留已有结果；补充未完成组仍须预览确认。\n"
                    "词级高亮只影响文字视图，原貌标记仍沿用精确文字位置。\n")
if home_ai:
    home_qml = review_qml.read_text(encoding="utf-8")
    assert all(control in home_qml for control in ("reviewAiSummary", "reviewAiStatus", "reviewAiEvidence"))
    assert "aiHome" in qml
    with (bundle / "使用说明.md").open("a", encoding="utf-8") as guide:
        guide.write("\nV0.5.1：AI结果同步显示在首页左侧各组，包含状态、解释、可能影响和原文/新版证据按钮。\n"
                    "长内容可展开，共同解释标出关联组；在AI窗口点击首页查看返回。\n")
if args.with_word:
    assert "doclens.preview" in embedded.toc, "Page preview module missing"
    assert (bundle / '_internal' / 'doclens' / 'word_preview.ps1').is_file()
    with (bundle / "使用说明.md").open('a', encoding='utf-8') as guide:
        guide.write('\nWord 原貌预览需要本机 Microsoft Word；PDF 原貌无需 Word。\n'
                    '[原貌比对样例](示例/原貌比对/测试指南.md)包含标题、表格、图片与分页。\n')

candidate = archive.with_suffix(".part")
with zipfile.ZipFile(candidate, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=5) as output:
    for path in sorted(bundle.rglob("*")):
        if path.is_file():
            output.write(path, path.relative_to(dist).as_posix())
verify_root = root / "build" / f"verify-v{version}-{time.time_ns()}"
with zipfile.ZipFile(candidate) as output:
    assert output.testzip() is None
    assert {"DocLens/DocLens.exe", "DocLens/示例/结构化比对/原版.txt",
            "DocLens/示例/PDF比对/新版.pdf"} <= set(output.namelist())
    if smart_analysis:
        assert "DocLens/示例/学术比较/测试指南.md" in output.namelist()
    output.extractall(verify_root)
verified_bundle = verify_root / "DocLens"

user32 = ctypes.WinDLL("user32", use_last_error=True)
enum_func = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = (enum_func, wintypes.LPARAM)
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

env = dict(os.environ)
windows = Path(env["SYSTEMROOT"])
env["PATH"] = f"{windows / 'System32'};{windows}"
env["QT_QUICK_BACKEND"] = "software"
for name in ("QT_QPA_PLATFORM", "PYTHONPATH", "PYTHONHOME"):
    env.pop(name, None)
checks = []
cases = [
    ("structured TXT", [str(verified_bundle / "示例" / "结构化比对" / name) for name in ("原版.txt", "新版.txt")]),
    ("PDF", [str(verified_bundle / "示例" / "PDF比对" / name) for name in ("原版.pdf", "新版.pdf")]),
]
if smart_analysis:
    cases.append(("academic TXT", [str(verified_bundle / "示例" / "学术比较" / name)
                                    for name in ("原稿.txt", "修订稿.txt")]))
if args.with_word:
    cases.append(('Word DOCX', [str(verified_bundle / '示例' / '原貌比对' / name) for name in ('原版.docx', '新版.docx')]))
for label, documents in cases:
    with subprocess.Popen([str(verified_bundle / "DocLens.exe"), *documents],
                              cwd=verified_bundle, env=env, creationflags=subprocess.CREATE_NO_WINDOW) as process:
        try:
            windows_found = []

            @enum_func
            def enumerate_window(hwnd, _):
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value != process.pid or not user32.IsWindowVisible(hwnd):
                    return True
                title = ctypes.create_unicode_buffer(255)
                user32.GetWindowTextW(hwnd, title, len(title))
                if title.value == "DocLens":
                    windows_found.append(hwnd)
                return True

            until = time.monotonic() + 20
            while process.poll() is None and not windows_found and time.monotonic() < until:
                user32.EnumWindows(enumerate_window, 0)
                time.sleep(0.2)
            assert windows_found, f"DocLens window missing (process exit {process.poll()})"
            time.sleep(18 if label == 'Word DOCX' else 1)
            assert process.poll() is None
            assert user32.PostMessageW(windows_found[0], 0x0010, 0, 0)
            assert process.wait(15) == 0
            print(f"Verified startup and normal close: {label}")
        finally:
            if process.poll() is None:
                process.terminate()
    checks.append({"case": label, "visible_window": True, "exit_code": 0})

candidate.replace(archive)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(archive.with_suffix(".zip.sha256")).write_text(f"{digest}  {archive.name}\n", encoding="ascii")
report_dir = root / "docs" / "validation" / f"v{version}"
report_dir.mkdir(parents=True, exist_ok=True)
report = {"version": version, "zip": archive.relative_to(root).as_posix(),
          "bytes": archive.stat().st_size, "sha256": digest, "zip_crc_verified": True,
          "structured_module_bundled": True, "environment": "Windows-only PATH; Python env vars removed",
          "checks": checks}
if smart_analysis:
    report.update(ai_modules_bundled=True, settings_controls_bundled=True, user_settings_excluded=True)
if extended_timeout:
    report["request_timeout_ms"] = 120_000
if review_workflow:
    report.update(review_module_bundled=True, review_and_coverage_controls_bundled=True)
if home_ai:
    report["home_ai_controls_bundled"] = True
(report_dir / "package-results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
