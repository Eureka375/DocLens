"""Capture the actual QML research window with the maintained example project."""
from pathlib import Path
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')

from PySide6.QtCore import QObject, QEventLoop, QTimer, QMetaObject, Qt, QPointF
from PySide6.QtGui import QGuiApplication
import pypdfium2

from doclens.app import create_window
from doclens.research import ResearchProject


root = Path(__file__).resolve().parents[1]
output = root / 'docs/validation/multi-document-mvp'
output.mkdir(parents=True, exist_ok=True)
app = QGuiApplication([])
engine, window, controller = create_window(original_preview=False)
p = ResearchProject.load(root / 'examples/多文档研究/demo-project.json')
controller.research._replace(p, False, '四格式演示项目 · 点击矩阵单元格核对证据')
dialog = window.findChild(QObject, 'researchDialog')
QMetaObject.invokeMethod(dialog, 'open', Qt.DirectConnection)
doc = p.documents[0]
controller.research.selectCell('BERT', doc['id'])
loop = QEventLoop()
QTimer.singleShot(600, loop.quit)
loop.exec()
controller.research.selectEvidence(controller.research.evidenceRows[0]['id'])
QTimer.singleShot(200, loop.quit)
loop.exec()
assert window.grabWindow().save(str(output / 'research-window.png'))
button = window.findChild(QObject, 'openResearch')
point = button.mapToScene(QPointF(button.width()/2, button.height()/2))
(output / 'research-button-position.json').write_text(json.dumps(dict(x=point.x(), y=point.y())), encoding='utf-8')
pdf = pypdfium2.PdfDocument(root / 'examples/多文档研究/04-retrieval.pdf')
pdf[0].render(scale=1.2).to_pil().save(output / 'example-pdf.png')
window.close()
