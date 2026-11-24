from pathlib import Path

from PySide6.QtCore import QUrl

from test_desktop import app, wait_for, control, click, isolated_ai_settings
from doclens.app import create_window


def test_research_window_import_evidence_notes_and_reopen(app, tmp_path):
    source = tmp_path / 'sample.md'
    source.write_text('# Methods\n😀 We use BERT on CIFAR10.', encoding='utf-8')
    engine, window, controller = create_window(cache_root=tmp_path / 'cache', original_preview=False)
    try:
        click(window, 'openResearch')
        research = controller.research
        research.importFiles([QUrl.fromLocalFile(str(source))])
        wait_for(lambda: not research.busy)
        assert len(research.documents) == 1
        research.selectCell('BERT', research.documents[0]['id'])
        assert research.evidenceRows
        research.selectEvidence(research.evidenceRows[0]['id'])
        wait_for(lambda: control(window, 'researchText').property('selectedText') == 'BERT')
        research.saveNote('', '复核', True)
        assert research.notes[0]['evidence']
        assert control(window, 'researchDialog').property('noteId') == research.notes[0]['id']
        research.selectDocument(research.documents[0]['id'])
        research.jumpHeading(0)
        wait_for(lambda: control(window, 'researchText').property('selectedText') == '# Methods')
        project = tmp_path / 'study.json'
        research.saveProject(QUrl.fromLocalFile(str(project)))
        wait_for(lambda: not research.busy)
        assert project.is_file() and not research.dirty
        research.newProject('new')
        research.openProject(QUrl.fromLocalFile(str(project)))
        wait_for(lambda: not research.busy)
        assert research.notes[0]['text'] == '复核'
        assert not research.dirty
        broken = tmp_path / 'invalid.json'
        broken.write_text('{}', encoding='utf-8')
        research.openProject(QUrl.fromLocalFile(str(broken)))
        wait_for(lambda: not research.busy)
        assert research.notes[0]['text'] == '复核'
        assert '不支持' in research.status
    finally:
        controller.research._dirty = False
        window.close()
        engine.deleteLater()
