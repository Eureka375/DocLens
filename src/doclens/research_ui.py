"""Qt adapter: transactions run on copies so failed jobs preserve the open project."""
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl

from .research import ResearchProject, _atomic
from .workspace_ui import WorkspaceTask


class ResearchController(QObject):
    changed = Signal()
    busyChanged = Signal()
    previewChanged = Signal()
    jumpRequested = Signal(int, int)
    noteSaved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = ResearchProject()
        self._task = None
        self._dirty = False
        self._status = '新建或打开项目，批量导入论文。所有识别在本地完成。'
        self._issues = []
        self._document = ''
        self._evidence = ''
        self._rows = []
        self._matrix = []

    @Property(bool, notify=busyChanged)
    def busy(self):
        return self._task is not None

    @Property(bool, notify=changed)
    def dirty(self):
        return self._dirty

    @Property(str, notify=changed)
    def name(self):
        return self.project.name

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property('QStringList', notify=changed)
    def issues(self):
        return self._issues

    @Property('QVariantList', notify=changed)
    def documents(self):
        return [dict(id=d['id'], name=d['name'], warnings='；'.join(d['warnings'])) for d in self.project.documents]

    @Property('QVariantList', notify=changed)
    def matrix(self):
        return self._matrix

    @Property('QVariantList', notify=changed)
    def evidenceRows(self):
        return self._rows

    @Property('QVariantList', notify=changed)
    def notes(self):
        return self.project.notes

    @Property(str, notify=previewChanged)
    def previewText(self):
        return self.project.document(self._document)['text'] if self._document else ''

    @Property(str, notify=previewChanged)
    def previewName(self):
        return self.project.document(self._document)['name'] if self._document else '选择文档或矩阵证据'

    @Property(str, notify=previewChanged)
    def outline(self):
        if not self._document:
            return ''
        return '\n'.join(f"- [{b['text'].replace('[', '').replace(']', '')}](heading:{i})"
            for i, b in enumerate(self.project.document(self._document)['blocks']) if b['kind'] == 'heading')

    @Property(str, notify=changed)
    def selectedEvidence(self):
        return self._evidence

    def _refresh(self):
        self._matrix = self.project.matrix()
        self.changed.emit()

    def _start(self, action, finish):
        if self.busy:
            return
        task = WorkspaceTask(action, self)
        self._task = task
        def done():
            if task.error:
                self._status = task.error
            else:
                finish(task.result)
            self._task = None
            task.deleteLater()
            self.busyChanged.emit()
            self._refresh()
        task.finished.connect(done)
        self._status = '正在处理，请稍候…'
        self.busyChanged.emit()
        self.changed.emit()
        task.start()

    def _replace(self, project, dirty, status, issues=()):
        self.project = project
        self._document = self._evidence = ''
        self._rows = []
        self._dirty, self._status, self._issues = dirty, status, list(issues)
        self.previewChanged.emit()
        self._refresh()

    @Slot(str)
    def newProject(self, name):
        if not self.busy:
            self._replace(ResearchProject(name), False, '已新建项目。导入后请保存项目文件。')

    @Slot('QVariantList')
    def importFiles(self, urls):
        if self.busy:
            return
        project = deepcopy(self.project)
        paths = [Path(QUrl(u).toLocalFile()) for u in urls]
        def run(cancel, progress):
            issues = project.import_files(paths, cancel)
            project.matrix()
            return project, issues
        self._start(run, lambda result: self._replace(result[0], True,
            f'项目共 {len(result[0].documents)} 份文档；本批 {len(result[1])} 条提示。', result[1]))

    @Slot(QUrl)
    def openProject(self, url):
        self._start(lambda c, p: ResearchProject.load(Path(url.toLocalFile())),
            lambda project: self._replace(project, False, '已打开项目快照；使用线索需人工核对。'))

    @Slot(QUrl)
    def saveProject(self, url):
        self._start(lambda c, p: self.project.save(Path(url.toLocalFile())), self._saved)

    def _saved(self, result):
        self._dirty = False
        self._status = '项目已保存（含可用原文、提取正文和笔记）。'

    @Slot(QUrl)
    def exportMarkdown(self, url):
        self._start(lambda c, p: _atomic(Path(url.toLocalFile()), self.project.markdown().encode('utf-8')),
                    lambda r: self._exported())

    @Slot(QUrl, bool)
    def exportBundle(self, url, originals):
        self._start(lambda c, p: self.project.export_bundle(Path(url.toLocalFile()), originals),
                    lambda r: self._exported())

    def _exported(self):
        self._status = '导出完成。共享内容包含提取正文、证据和笔记。'

    @Slot(str)
    def selectDocument(self, identifier):
        if self.busy or identifier not in {d['id'] for d in self.project.documents}:
            return
        self._document = identifier
        self.previewChanged.emit()

    @Slot(str, str)
    def selectCell(self, term, document):
        if self.busy:
            return
        self._rows = [e for e in self.project.evidence() if e['term'] == term and e['document'] == document]
        self._evidence = ''
        self.selectDocument(document)
        self._status = f'{term}：{len(self._rows)} 条证据。未发现不等于不存在。'
        self.changed.emit()

    def _jump(self, start, end):
        text = self.previewText
        convert = lambda index: len(text[:index].encode('utf-16-le')) // 2
        self.jumpRequested.emit(convert(start), convert(end))

    @Slot(str)
    def selectEvidence(self, identifier):
        if self.busy:
            return
        e = next((e for e in self.project.evidence() if e['id'] == identifier), None)
        if e:
            self._evidence = identifier
            self.selectDocument(e['document'])
            self._jump(e['start'], e['end'])
            self.changed.emit()

    @Slot(int)
    def jumpHeading(self, index):
        if self.busy or not self._document:
            return
        blocks = self.project.document(self._document)['blocks']
        if 0 <= index < len(blocks):
            self._jump(blocks[index]['start'], blocks[index]['end'])

    @Slot(str, str, bool)
    def saveNote(self, identifier, text, link):
        if self.busy:
            return
        try:
            saved = self.project.save_note(identifier, text, self._evidence if link else '')
            self._dirty = True
            self._status = '笔记已更新，请保存项目。'
            self.noteSaved.emit(saved)
        except ValueError as exc:
            self._status = str(exc)
        self.changed.emit()

    @Slot(str)
    def deleteNote(self, identifier):
        if not self.busy:
            self.project.delete_note(identifier)
            self._dirty = True
            self.changed.emit()

    @Slot(str)
    def removeDocument(self, identifier):
        if not self.busy:
            self.project.remove_document(identifier)
            self._replace(self.project, True, '文档已移除，相关笔记正文保留，证据关联已清除。')
