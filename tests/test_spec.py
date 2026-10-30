import json

import pytest

import plotkit as pk
from plotkit.spec import io as spec_io
from plotkit.spec.model import new_layer, new_spec
from plotkit.spec.validate import SpecError, validate_or_raise, validate_spec


def base_spec():
    spec = new_spec(title="t")
    store = pk.DataStore()
    store.add("t", [0, 1, 2], role="coord")
    store.add("v", [0.0, 1.0, 2.0], role="series")
    spec["layers"].append(new_layer("line", data={"x": "t", "y": "v"}))
    return spec, store


def test_new_spec_defaults():
    spec = new_spec()
    assert spec["spec_version"] == "0.1"
    assert spec["figure"]["ncols"] == 1
    assert spec["layers"] == []


def test_layer_has_stable_id_and_defaults():
    a = new_layer("line")
    b = new_layer("line")
    assert a["id"] != b["id"]
    assert a["style"]["mode"] == "lines"
    assert a["view"]["grid"] is True
    assert a["annotations"] == []


def test_layer_style_merge_keeps_marker_parts():
    layer = new_layer("line", style={"width": 3.0, "marker": {"size": 9}})
    assert layer["style"]["width"] == 3.0
    assert layer["style"]["marker"]["size"] == 9
    assert layer["style"]["marker"]["symbol"] == "circle"


def test_valid_spec_passes():
    spec, store = base_spec()
    report = validate_spec(spec, store=store)
    assert report.ok, report.as_dict()
    assert validate_or_raise(spec, store=store).ok


def test_missing_spec_version():
    spec, _ = base_spec()
    spec.pop("spec_version")
    report = validate_spec(spec)
    assert not report.ok
    assert report.errors[0].code == "spec.version"


def test_unknown_kind_rejected():
    spec, store = base_spec()
    spec["layers"][0]["kind"] = "surface3d"
    report = validate_spec(spec, store=store)
    assert not report.ok
    assert any(i.code == "layer.kind" for i in report.errors)


def test_duplicate_layer_ids_rejected():
    spec, store = base_spec()
    spec["layers"].append(dict(spec["layers"][0]))
    report = validate_spec(spec, store=store)
    assert any(i.code == "layer.id.duplicate" for i in report.errors)


def test_subplot_out_of_range():
    spec, store = base_spec()
    spec["layers"][0]["subplot"] = 5
    report = validate_spec(spec, store=store)
    assert any(i.code == "layer.subplot" for i in report.errors)


def test_unknown_dataset_rejected():
    spec, store = base_spec()
    spec["layers"][0]["data"]["y"] = "nope"
    report = validate_spec(spec, store=store)
    assert any(i.code == "layer.data.unknown" for i in report.errors)


def test_role_mismatch_rejected():
    store = pk.DataStore()
    store.add("img", [[1, 2], [3, 4]], role="image")
    spec = new_spec()
    spec["layers"].append(new_layer("line", data={"x": "img", "y": "img"}))
    report = validate_spec(spec, store=store)
    codes = {i.code for i in report.errors}
    assert "layer.data.role" in codes


def test_unknown_field_is_warning_and_preserved():
    spec, store = base_spec()
    spec["layers"][0]["style"]["shadow"] = True
    spec["future_flag"] = {"x": 1}
    report = validate_spec(spec, store=store)
    assert report.ok
    assert {i.code for i in report.warnings} >= {"layer.style.unknown", "spec.unknown"}
    # 保留：序列化后还在
    assert json.loads(spec_io.dumps(spec))["future_flag"] == {"x": 1}


def test_limits_must_be_two_numbers():
    spec, store = base_spec()
    spec["layers"][0]["view"]["xlim"] = [0]
    report = validate_spec(spec, store=store)
    assert any(i.code == "view.limits" for i in report.errors)


def test_bad_scale_rejected():
    spec, store = base_spec()
    spec["layers"][0]["view"]["xscale"] = "symlog"
    report = validate_spec(spec, store=store)
    assert any(i.code == "layer.view.scale" for i in report.errors)


def test_bad_annotation_rejected():
    spec, store = base_spec()
    spec["layers"][0]["annotations"] = [{"type": "arrow"}]
    report = validate_spec(spec, store=store)
    assert any(i.code == "layer.annotation.type" for i in report.errors)


def test_all_errors_collected_at_once():
    spec, store = base_spec()
    spec["layers"][0]["view"]["xlim"] = [0]
    spec["layers"][0]["style"]["mode"] = "dots"
    spec["layers"][0]["data"]["x"] = "ghost"
    report = validate_spec(spec, store=store)
    codes = {i.code for i in report.errors}
    assert {"view.limits", "layer.style.mode", "layer.data.unknown"} <= codes


def test_roundtrip_is_byte_stable(tmp_path):
    spec, store = base_spec()
    text = spec_io.dumps(spec)
    assert spec_io.dumps(spec_io.loads(text)) == text

    path = tmp_path / "spec.json"
    spec_io.save(spec, path)
    loaded = spec_io.load(path)
    assert loaded["layers"][0]["id"] == spec["layers"][0]["id"]


def test_load_rejects_future_version():
    with pytest.raises(SpecError):
        spec_io.loads('{"spec_version": "9.0", "figure": {}, "layers": []}')


def test_raise_if_bad_includes_paths():
    spec, store = base_spec()
    spec["layers"][0]["data"]["y"] = "ghost"
    with pytest.raises(SpecError) as exc:
        validate_or_raise(spec, store=store)
    assert "ghost" in str(exc.value)
