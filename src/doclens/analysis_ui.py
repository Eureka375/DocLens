from collections import OrderedDict

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .analysis import CATEGORIES, MAX_REPLY_BYTES, AnalysisError, prepare_analysis, parse_analysis

MAX_CACHE_ENTRIES = 16
REQUEST_TIMEOUT_MS = 30_000


class AnalysisController(QObject):
    changed = Signal()
    busyChanged = Signal()
    reportChanged = Signal()
    evidenceRequested = Signal(int, str, int, int)

    def __init__(self, parent: QObject, network: QNetworkAccessManager | None = None):
        super().__init__(parent)
        self._network = network if network is not None else QNetworkAccessManager(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self._abort("AI 分析请求超时。"))
        self._comparison = None
        self._draft = None
        self._submitted = None
        self._reply = None
        self._buffer = bytearray()
        self._abort_message = ""
        self._report = ()
        self._cache = OrderedDict()
        self._status = "先选择差异范围并预览待发送内容。"

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._reply is not None

    @Property(str, notify=changed)
    def status(self) -> str:
        return self._status

    @Property(str, notify=changed)
    def preview(self) -> str:
        return self._draft.preview if self._draft else ""

    @Property(str, notify=changed)
    def previewDestination(self) -> str:
        return f"{self._draft.endpoint}\n模型 {self._draft.model}" if self._draft else ""

    @Property(str, notify=changed)
    def scope(self) -> str:
        return self._draft.scope if self._draft else ""

    @Property("QVariantList", notify=reportChanged)
    def report(self) -> list[dict]:
        return [{"category": CATEGORIES[f.category], "summary": f.summary, "impact": f.impact,
                 "evidence": [f"第 {e.change_index + 1} 组 · {e.side} · {e.id}" for e in f.evidence]}
                for f in self._report]

    def set_comparison(self, left, right, comparison) -> None:
        self.invalidate()
        self._comparison = left, right, comparison

    def invalidate(self) -> None:
        self._comparison = None
        self._draft = None
        self._clear_report()
        self._status = "先选择差异范围并预览待发送内容。"
        if self.busy:
            self._abort("当前比对已更改，已取消 AI 分析。")
        self.changed.emit()

    def _clear_report(self) -> None:
        self._report = ()
        self.reportChanged.emit()

    @Slot(int, int, str, str, result=bool)
    @Slot(int, int, str, str, str, result=bool)
    def prepare(self, first: int, last: int, endpoint: str, model: str, provider: str = "auto") -> bool:
        if self.busy or self._comparison is None:
            return False
        self._draft = None
        try:
            self._draft = prepare_analysis(*self._comparison, first, last, endpoint, model, provider)
        except AnalysisError as exc:
            self._status = str(exc)
            self.changed.emit()
            return False
        self._status = "请核对预览后决定是否发送。"
        self.changed.emit()
        return True

    @Slot()
    def discardPreview(self) -> None:
        if self._draft is not None:
            self._draft = None
            self._status = "未发送。可以重新生成预览。"
            self.changed.emit()

    @Slot(str)
    def approveAndSend(self, api_key: str) -> None:
        if self.busy or self._draft is None:
            return
        draft, self._draft = self._draft, None
        self._clear_report()
        if draft.fingerprint in self._cache:
            self._cache.move_to_end(draft.fingerprint)
            self._report = self._cache[draft.fingerprint]
            self._status = "已使用本次会话缓存。 " + draft.scope.replace("发送", "覆盖", 1)
            self.reportChanged.emit()
            self.changed.emit()
            return
        api_key = api_key.strip()
        if not api_key or len(api_key) > 4096 or any(not 33 <= ord(c) <= 126 for c in api_key):
            self._status = "请输入有效的 API Key，然后重新预览。"
            self.changed.emit()
            return
        request = QNetworkRequest(QUrl(draft.endpoint, QUrl.ParsingMode.StrictMode))
        if not request.url().isValid():
            self._status = "服务地址格式有误。"
            self.changed.emit()
            return
        request.setRawHeader(b"Content-Type", b"application/json")
        request.setRawHeader(b"Authorization", b"Bearer " + api_key.encode("ascii"))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setAttribute(QNetworkRequest.Attribute.AuthenticationReuseAttribute,
                             QNetworkRequest.LoadControl.Manual)
        request.setAttribute(QNetworkRequest.Attribute.CookieLoadControlAttribute,
                             QNetworkRequest.LoadControl.Manual)
        request.setAttribute(QNetworkRequest.Attribute.CookieSaveControlAttribute,
                             QNetworkRequest.LoadControl.Manual)
        self._submitted = draft
        self._buffer.clear()
        self._abort_message = ""
        self._reply = self._network.post(request, draft.body)
        if isinstance(self._reply, QNetworkReply):
            self._reply.setReadBufferSize(MAX_REPLY_BYTES + 1)
        self._reply.readyRead.connect(self._read_reply)
        self._reply.finished.connect(self._finished)
        self._timer.start(REQUEST_TIMEOUT_MS)
        self._status = "服务正在分析已授权的差异…"
        self.busyChanged.emit()
        self.changed.emit()

    @Slot()
    def _read_reply(self) -> None:
        if not self.busy or self._abort_message:
            return
        self._buffer.extend(bytes(self._reply.read(MAX_REPLY_BYTES + 1 - len(self._buffer))))
        if len(self._buffer) > MAX_REPLY_BYTES:
            self._abort("服务响应超过上限，未显示结果。")

    def _abort(self, message: str) -> None:
        if self._reply is not None:
            self._abort_message = message
            self._reply.abort()

    @Slot()
    def cancel(self) -> None:
        self._abort("已取消等待结果。已发送的内容无法撤回。")

    @Slot()
    def _finished(self) -> None:
        reply, draft = self._reply, self._submitted
        if reply is None:
            return
        self._timer.stop()
        self._reply = self._submitted = None
        try:
            if self._abort_message:
                self._status = self._abort_message
                return
            code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if code in (401, 403):
                self._status = "模型服务拒绝身份验证。请检查 API Key 和模型权限。"
            elif code == 402:
                self._status = "模型服务返回 HTTP 402。请检查 API 账户余额。"
            elif code == 429:
                self._status = "服务限流或额度不足，请稍后手动重试。"
            elif isinstance(code, int) and 300 <= code < 400:
                self._status = "服务返回重定向，请填写最终 HTTPS 地址后重新确认。"
            elif code != 200 or reply.error() != QNetworkReply.NetworkError.NoError:
                self._status = f"模型服务请求失败（HTTP {code}）。" if code else "无法连接模型服务，请检查地址、网络和 TLS。"
            else:
                self._buffer.extend(bytes(reply.read(MAX_REPLY_BYTES + 1 - len(self._buffer))))
                self._report = parse_analysis(bytes(self._buffer), draft)
                self._cache[draft.fingerprint] = self._report
                if len(self._cache) > MAX_CACHE_ENTRIES:
                    self._cache.popitem(last=False)
                self._status = "分析完成。 " + draft.scope.replace("发送", "覆盖", 1)
                self.reportChanged.emit()
        except AnalysisError as exc:
            self._status = str(exc)
        finally:
            if not self._report:
                self._status += " 本地差异仍可使用，可关闭此窗口继续核对原文。"
            self._buffer.clear()
            reply.deleteLater()
            self.busyChanged.emit()
            self.changed.emit()

    @Slot(int, int)
    def openEvidence(self, finding_index: int, evidence_index: int) -> None:
        if not 0 <= finding_index < len(self._report):
            return
        evidence = self._report[finding_index].evidence
        if 0 <= evidence_index < len(evidence):
            item = evidence[evidence_index]
            self.evidenceRequested.emit(item.change_index, "left" if item.side == "原文" else "right",
                                        item.span.start, item.span.end)

    @Slot()
    def clearCache(self) -> None:
        if self.busy:
            return
        self._cache.clear()
        self._clear_report()
        self._status = "本次会话的 AI 分析缓存已清除。"
        self.changed.emit()
