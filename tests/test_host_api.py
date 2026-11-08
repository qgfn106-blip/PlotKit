"""host_api.probe() 三态契约（严格审计 §6：available / missing / incompatible）。"""

from __future__ import annotations

import builtins

import pytest

from plotkit import host_api


def test_probe_available() -> None:
    result = host_api.probe()
    assert result["state"] == "available"
    assert result["version"]
    assert result["api_version"] == host_api.API_VERSION


def test_probe_missing_when_backend_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name == "matplotlib" or name.startswith("matplotlib."):
            raise ImportError("matplotlib not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = host_api.probe()
    assert result["state"] == "missing"
    assert "matplotlib" in result["detail"]


def test_probe_incompatible_version(monkeypatch: pytest.MonkeyPatch) -> None:
    import plotkit

    monkeypatch.setattr(plotkit, "__version__", "0.1.9")
    result = host_api.probe()
    assert result["state"] == "incompatible"
    assert result["version"] == "0.1.9"
