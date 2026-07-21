import json

from fronda.settings import SettingsStore


def test_settings_ignores_unknown_future_fields(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"template_path": "template.psd", "future_option": True}), encoding="utf-8")
    settings = SettingsStore(path).load()
    assert settings.template_path == "template.psd"
    assert settings.release_type == "Episode"

