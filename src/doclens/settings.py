"""Current-user Windows protection for the last AI connection configuration."""

import ctypes
from ctypes import wintypes
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import sys
import tempfile

from PySide6.QtCore import QStandardPaths

from .analysis import AnalysisError, _validate_endpoint
from .providers import ProviderConfig


class SettingsError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AISettings:
    endpoint: str
    model: str
    provider: str
    api_key: str = field(repr=False)


def valid_api_key(key: str) -> bool:
    return isinstance(key, str) and 1 <= len(key) <= 4096 and all(33 <= ord(c) <= 126 for c in key)


def _validate(config: AISettings) -> None:
    if not all(isinstance(value, str) for value in (config.endpoint, config.model, config.provider, config.api_key)):
        raise SettingsError("AI 设置格式无效，请重新填写。")
    try:
        _validate_endpoint(config.endpoint)
        ProviderConfig(config.provider).parameters(config.endpoint, 1400)
    except (AnalysisError, ValueError) as exc:
        raise SettingsError("服务地址或请求格式无效，请重新填写。") from exc
    if not config.model.strip() or len(config.model) > 160 or any(ord(c) < 32 for c in config.model):
        raise SettingsError("请输入有效的模型名称。")
    if not valid_api_key(config.api_key):
        raise SettingsError("请输入有效的 API Key。")


def _protect(data: bytes, *, decrypt: bool = False) -> bytes:
    if sys.platform != "win32":
        raise SettingsError("当前系统不支持 Windows 密钥保护，未保存密钥。")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    operation = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    operation.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    operation.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(data)
    entropy = ctypes.create_string_buffer(b"DocLens.AISettings.v1")
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    salt = Blob(len(entropy.raw), ctypes.cast(entropy, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    try:
        # UI_FORBIDDEN, current-user scope; never LOCAL_MACHINE.
        if not operation(ctypes.byref(source), None, ctypes.byref(salt), None, None, 1, ctypes.byref(output)):
            raise SettingsError("Windows 无法保护或读取 AI 设置，请重新保存。")
        return ctypes.string_at(output.data, output.size)
    finally:
        ctypes.memset(buffer, 0, len(buffer))
        if output.data:
            ctypes.memset(output.data, 0, output.size)
            kernel.LocalFree(output.data)


def default_settings_path() -> Path:
    root = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
    return Path(root) / "ai-settings.bin"


class AISettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else default_settings_path()

    def load(self) -> AISettings | None:
        try:
            if not self.path.exists():
                return None
            with self.path.open("rb") as handle:
                data = handle.read(64 * 1024 + 1)
            if len(data) > 64 * 1024:
                raise SettingsError("已保存的 AI 设置无效，请清除后重新填写。")
            config = AISettings(**json.loads(_protect(data, decrypt=True)))
            _validate(config)
            return config
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            raise SettingsError("无法读取已保存的 AI 设置，请重新填写或清除。") from exc

    def save(self, config: AISettings) -> None:
        _validate(config)
        temporary = None
        try:
            encrypted = _protect(json.dumps(asdict(config), ensure_ascii=False).encode("utf-8"))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix="ai-settings-", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except (OSError, ValueError) as exc:
            raise SettingsError("AI 设置未能安全保存；本次仍可使用输入的密钥。") from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    # Cleanup cannot mask a controlled save error. Any residue
                    # contains only DPAPI ciphertext, never plaintext settings.
                    pass

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise SettingsError("无法清除已保存的 AI 设置，请检查文件权限。") from exc
