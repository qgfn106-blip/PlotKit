"""裁定 ⑨：probe()/compat_matrix 的四个命名空间互不混淆。

features 静态 P0 功能名；capabilities 静态后端能力名（8 行 capabilities_used
并集）；optional 动态 extra 安装状态；decisions 运行时按 optional 计算、只在
/api/capabilities 顶层暴露。全部走公开 API，不读源码做字符串断言。
"""

from __future__ import annotations

import plotkit.host_api as host_api
from plotkit.backends.selector import capability_rows
from plotkit.schema import load
from plotkit.server.app import create_app


def _matrix_union() -> list[str]:
    used: set[str] = set()
    for row in capability_rows():
        used.update(str(item) for item in (row.get("capabilities_used") or []))
    return sorted(used)


def test_probe_splits_four_namespaces():
    status = host_api.probe()
    features = status["features"]
    capabilities = status["capabilities"]
    optional = status["optional"]
    # features 是 compat_matrix 声明的静态 P0 功能名（单一来源）。
    compat = load("compat_matrix.json")
    assert features == compat["features"]
    # capabilities 是 8 行 capabilities_used 并集，与环境无关。
    assert capabilities == _matrix_union()
    # optional 是动态 extra 安装状态，键由 extra_requirements 声明。
    assert set(optional) == set(compat["extra_requirements"])
    assert all(isinstance(value, bool) for value in optional.values())
    # decisions 不属于 probe()，只在 HTTP 表面层。
    assert "decisions" not in status


def test_capabilities_never_contain_extra_names():
    capabilities = set(host_api.probe()["capabilities"])
    extras = set(load("compat_matrix.json")["extra_requirements"])
    assert capabilities.isdisjoint(extras)
    features = set(host_api.probe()["features"])
    assert features.isdisjoint(extras)


def test_capabilities_and_features_are_environment_independent(monkeypatch):
    baseline = host_api.probe()
    # 无论探测到全部可用或全部不可用，静态字段都不改变。
    monkeypatch.setattr(host_api, "_module_available", lambda name: False)
    monkeypatch.setattr(host_api, "_distribution_installed", lambda name: False)
    off = host_api.probe()
    monkeypatch.setattr(host_api, "_module_available", lambda name: True)
    monkeypatch.setattr(host_api, "_distribution_installed", lambda name: True)
    on = host_api.probe()
    assert off["features"] == baseline["features"] == on["features"]
    assert off["capabilities"] == baseline["capabilities"] == on["capabilities"]
    assert all(value is False for value in off["optional"].values())
    assert all(value is True for value in on["optional"].values())


def test_optional_uses_one_declared_probe_discipline(monkeypatch):
    # 统一口径：发行包声明 + 依赖闭包模块全部满足才算可用。
    seen: list[str] = []
    real_module = host_api._module_available

    def spy(name: str) -> bool:
        seen.append(name)
        return real_module(name)

    monkeypatch.setattr(host_api, "_module_available", spy)
    host_api._optional_features()
    declared = load("compat_matrix.json")["extra_requirements"]
    expected: list[str] = []
    for req in declared.values():
        expected.extend(str(item) for item in (req.get("modules") or []))
    # 每个声明的模块都经过同一 find_spec 探测（不再两套口径）。
    assert sorted(seen) == sorted(expected)


def test_capability_schema_is_strict_and_single_id():
    doc = load("capability.v1.json")
    # $id 是正式登记的 schema 文档 id；信封 const 是 matrix 的正式 id。
    assert doc["$id"] == "plotkit.capability/v1"
    schema_prop = doc["properties"]["schema"]
    assert schema_prop["const"] == "plotkit.capability_matrix/v1"
    assert "enum" not in schema_prop
    row = doc["$defs"]["row"]
    assert row["additionalProperties"] is False
    assert set(row["required"]) == {
        "id",
        "situation",
        "match",
        "backend",
        "placement",
        "capabilities_used",
        "fallback",
        "degraded_when",
        "acceptance",
    }
    assert doc["$defs"]["decision"]["additionalProperties"] is False
    # 两个 id 在 compat_matrix 正式登记，不靠 enum 两边讨好。
    ids = load("compat_matrix.json")["schema_ids"]
    assert ids["capability_schema_document"] == doc["$id"]
    assert ids["capability_matrix_envelope"] == schema_prop["const"]


def test_http_capabilities_exposes_four_namespaces(tmp_path):
    import plotkit as pk
    from fastapi.testclient import TestClient

    client = TestClient(create_app(pk.figure(), layout_path=tmp_path / "ui.json"))
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    payload = response.json()
    status = host_api.probe()
    assert payload["features"] == status["features"]
    assert payload["capabilities"] == status["capabilities"]
    assert payload["optional"] == status["optional"]
    assert len(payload["decisions"]) == 8


def test_http_capabilities_tolerates_minimal_probe(tmp_path, monkeypatch):
    import plotkit as pk
    from fastapi.testclient import TestClient

    import plotkit.server.app as app_module

    # test_ci_gate 风格的最小 probe dict：只含 optional，不应 KeyError。
    monkeypatch.setattr(
        app_module.host_api,
        "probe",
        lambda: {"optional": {"three": True, "ns": True}},
    )
    client = TestClient(create_app(pk.figure(), layout_path=tmp_path / "ui.json"))
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["features"] == []
    assert payload["capabilities"] == []
    assert payload["optional"] == {"three": True, "ns": True}
    assert len(payload["decisions"]) == 8
