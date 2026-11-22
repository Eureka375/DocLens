import sys

import pytest

from doclens import settings

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI integration")


def configuration(key="fictional-key-for-storage-test"):
    return settings.AISettings("https://models.example/chat/completions", "test-model", "json", key)


def test_dpapi_settings_survive_new_store_without_plaintext(tmp_path):
    path = tmp_path / "ai-settings.bin"
    store = settings.AISettingsStore(path)
    config = configuration()
    store.save(config)
    data = path.read_bytes()
    assert config.api_key.encode() not in data
    assert config.endpoint.encode() not in data
    assert config.api_key not in repr(config)
    assert settings.AISettingsStore(path).load() == config
    store.clear()
    assert not path.exists()
    assert store.load() is None


def test_corrupt_settings_fail_closed(tmp_path):
    path = tmp_path / "ai-settings.bin"
    path.write_bytes(b"not a DPAPI blob")
    with pytest.raises(settings.SettingsError):
        settings.AISettingsStore(path).load()


def test_failed_atomic_replace_keeps_old_encrypted_settings(tmp_path, monkeypatch):
    path = tmp_path / "ai-settings.bin"
    store = settings.AISettingsStore(path)
    store.save(configuration())
    def fail(*args):
        raise OSError("test write failure")
    monkeypatch.setattr(settings.os, "replace", fail)
    with pytest.raises(settings.SettingsError):
        store.save(configuration("replacement-fictional-key"))
    assert store.load() == configuration()
    assert list(tmp_path.iterdir()) == [path]


def test_failed_temp_cleanup_still_reports_controlled_settings_error(tmp_path, monkeypatch):
    store = settings.AISettingsStore(tmp_path / "ai-settings.bin")
    def fail(*args, **kwargs):
        raise OSError("test permission failure")
    monkeypatch.setattr(settings.os, "replace", fail)
    monkeypatch.setattr(settings.Path, "unlink", fail)
    with pytest.raises(settings.SettingsError):
        store.save(configuration())
    assert all(configuration().api_key.encode() not in path.read_bytes() for path in tmp_path.iterdir())


@pytest.mark.parametrize("field,value", [("endpoint", "http://bad.example/chat/completions"),
                                        ("provider", "unknown"), ("api_key", "invalid key"),
                                        ("model", "")])
def test_invalid_settings_never_written(tmp_path, field, value):
    from dataclasses import replace
    path = tmp_path / "ai-settings.bin"
    with pytest.raises(settings.SettingsError):
        settings.AISettingsStore(path).save(replace(configuration(), **{field: value}))
    assert not path.exists()
