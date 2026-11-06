import numpy as np
import pytest

import plotkit as pk
from plotkit.store.disk import ChunkedSeries
from plotkit.store.downsample import lttb, minmax_envelope
from plotkit.store.reclaim import Reclaimer


# ---------------- registry ----------------
def test_add_and_meta():
    store = pk.DataStore()
    meta = store.add(
        "v", [1, 2, 3], unit="V", role="series", tags=["out"], life="append"
    )
    assert meta.length == 3
    assert store.meta("v")["unit"] == "V"
    assert store.meta("v")["tags"] == ["out"]
    assert store.values("v").tolist() == [1, 2, 3]


def test_duplicate_add_needs_overwrite():
    store = pk.DataStore()
    store.add("v", [1])
    with pytest.raises(KeyError):
        store.add("v", [2])
    first = store.meta("v")["version"]
    store.add("v", [2], overwrite=True)
    assert store.values("v").tolist() == [2]
    assert store.meta("v")["version"] > first


def test_overwrite_invalidates_large_data_pyramid():
    store = pk.DataStore()
    store.add("x", np.arange(400001.0))
    store.add("y", np.zeros(400001))
    before = store.pyramid("x", "y")
    store.add("y", np.ones(400001), overwrite=True)
    after = store.pyramid("x", "y")
    assert after is not before
    assert float(after[-1][1].max()) == pytest.approx(1.0)


def test_bad_role_and_life_rejected():
    store = pk.DataStore()
    with pytest.raises(ValueError):
        store.add("v", [1], role="whatever")
    with pytest.raises(ValueError):
        store.add("v", [1], life="forever")


def test_push_append_keeps_history():
    store = pk.DataStore()
    store.add("v", [1, 2])
    store.push("v", [3])
    assert store.values("v").tolist() == [1, 2, 3]
    assert store.meta("v")["version"] == 2
    assert [h["length"] for h in store.history("v")] == [2, 3]


def test_push_replace_only_keeps_latest():
    store = pk.DataStore()
    store.add("v", [1, 2, 3], life="replace")
    store.push("v", [9])
    assert store.values("v").tolist() == [9]
    assert store.meta("v")["version"] == 2


def test_push_shape_mismatch_raises():
    store = pk.DataStore()
    store.add("v", [[1, 2], [3, 4]])
    with pytest.raises(ValueError):
        store.push("v", [[1, 2, 3]])


def test_catalog_groups_by_tags():
    store = pk.DataStore()
    store.add("t", [0, 1], role="coord", tags=["时间"])
    store.add("v", [1, 2], role="series", tags=["输出", "电压"])
    cat = store.catalog()
    assert set(cat["groups"]) == {"时间", "输出", "电压"}
    assert cat["groups"]["时间"] == ["t"]


def test_rename_updates_meta():
    store = pk.DataStore()
    store.add("v", [1])
    store.rename("v", "v2")
    assert "v2" in store and "v" not in store
    assert store.meta("v2")["name"] == "v2"


def test_remove_and_export(tmp_path):
    store = pk.DataStore()
    store.add("v", [1.5, 2.5], unit="V")
    target = store.export("v", tmp_path / "v.csv")
    text = target.read_text(encoding="utf-8")
    assert "name,unit,role" in text
    assert "1.5" in text
    store.remove("v")
    assert "v" not in store


def test_object_arrays_rejected():
    store = pk.DataStore()
    with pytest.raises(TypeError):
        store.add("v", np.array([object()], dtype=object))


# ---------------- reclaim ----------------
def test_release_moves_to_trash_and_restores():
    store = pk.DataStore()
    store.add("v", [1, 2, 3])
    rec = Reclaimer(store)
    rec.retain("v", "layer-1")
    rec.retain("v", "layer-2")
    assert rec.refcount("v") == 2
    assert rec.release("v", "layer-1") is False
    assert rec.release("v", "layer-2") is True
    assert "v" not in store
    assert [e["name"] for e in rec.list()] == ["v"]
    assert rec.restore("v") is True
    assert store.values("v").tolist() == [1, 2, 3]


def test_restore_never_overwrites_existing():
    store = pk.DataStore()
    store.add("v", [1])
    rec = Reclaimer(store)
    rec.retain("v", "o")
    rec.release("v", "o")
    store.add("v", [42])
    assert rec.restore("v") is True
    assert store.values("v").tolist() == [42]
    assert store.values("v~restored").tolist() == [1]


def test_quota_trim_purges_oldest():
    store = pk.DataStore()
    store.add("a", np.zeros(100, dtype=np.float64))
    store.add("b", np.zeros(100, dtype=np.float64))
    rec = Reclaimer(store, quota_bytes=1)
    rec.retain("a", "o")
    rec.release("a", "o")
    rec.retain("b", "o")
    rec.release("b", "o")
    assert rec.over_quota() is True
    purged = rec.trim(keep=["b"])
    assert purged == ["a"]
    assert rec.list() and rec.list()[0]["name"] == "b"
    assert rec.empty() == 1


# ---------------- downsample ----------------
def test_envelope_keeps_peaks():
    n = 100_000
    x = np.arange(n, dtype=float)
    y = np.sin(x / 500.0)
    y[54321] = 99.0  # 单点尖峰
    xs, ys = minmax_envelope(x, y, pixels=400, per_pixel=2.0)
    assert xs.size <= 400 * 2 + 4
    assert ys.max() == 99.0
    assert xs[0] == 0 and xs[-1] == n - 1


def test_envelope_short_series_passthrough():
    x = np.arange(10.0)
    y = np.arange(10.0)
    xs, ys = minmax_envelope(x, y, pixels=100)
    assert np.array_equal(xs, x) and np.array_equal(ys, y)


def test_envelope_handles_nan():
    x = np.arange(1000.0)
    y = np.sin(x)
    y[100:200] = np.nan
    xs, ys = minmax_envelope(x, y, pixels=50)
    assert np.isfinite(ys).any()


def test_envelope_length_mismatch():
    with pytest.raises(ValueError):
        minmax_envelope(np.arange(5.0), np.arange(4.0), pixels=2)


def test_lttb_keeps_endpoints_and_size():
    x = np.arange(10_000.0)
    y = np.cos(x / 100.0)
    xs, ys = lttb(x, y, 500)
    assert xs.size <= 500 + 2
    assert xs[0] == 0 and xs[-1] == 9999


# ---------------- disk ----------------
def test_chunked_series_roundtrip(tmp_path):
    series = ChunkedSeries.open(tmp_path, "v", chunk_size=100)
    series.append(np.arange(250, dtype=np.float32))
    assert len(series) == 250
    assert series.read(0, 5).tolist() == [0, 1, 2, 3, 4]
    assert series.read(95, 105).tolist() == list(range(95, 105))
    tail = series.read(240)
    assert tail.tolist() == list(range(240, 250))
    series.flush()
    assert len(list(series.chunk_files())) >= 2


def test_chunked_series_reopen_keeps_index(tmp_path):
    series = ChunkedSeries.open(tmp_path, "v", chunk_size=64)
    series.append(np.arange(200, dtype=np.float32))
    series.flush()
    reopened = ChunkedSeries.open(tmp_path, "v", chunk_size=64)
    assert len(reopened) == 200
    assert reopened.read(190, 200).tolist() == list(range(190, 200))
