"""NS 自相似场：标度律、不可压性、轴上正则性。"""

from __future__ import annotations

import numpy as np
import pytest

from plotkit.contrib.ns import (
    SimilarityField,
    SimilarityParams,
    analyze,
    grid_stats,
    inverse_map,
    profile_table,
    velocity_at,
)


@pytest.fixture(scope="module")
def p():
    return SimilarityParams()


@pytest.fixture(scope="module")
def table(p):
    return profile_table(p)


def test_paper_h_bound_is_reported(p):
    assert p.paper_compliant
    assert SimilarityParams(h=0.05).paper_compliant is False


def test_invalid_h_rejected():
    with pytest.raises(ValueError):
        SimilarityParams(h=0.0)
    with pytest.raises(ValueError):
        SimilarityParams(h=0.6)


def test_inverse_map_roundtrip(p):
    """(r,z) → (X,η) → (r,z) 必须回到原点。"""
    r = np.array([0.01, 0.05, 0.2])
    z = np.array([0.02, 0.1, -0.4])
    t = 0.5
    X, eta, q = inverse_map(z, r, t, p)
    tau = p.t_blow - t
    # 反解：q = τ/(1-η²)，z = q^D η，r = √(2qX)
    q_back = tau / (1.0 - eta**2)
    np.testing.assert_allclose(q_back, q, rtol=1e-6)
    np.testing.assert_allclose(np.power(q, p.D) * eta, z, rtol=1e-6, atol=1e-9)
    np.testing.assert_allclose(np.sqrt(2.0 * q * X), r, rtol=1e-6)


def test_axis_is_regular(p, table):
    """u_θ/r 在 r→0 有有限极限（涡核是刚体旋转，不是奇点）。"""
    t = 0.5
    omegas = []
    for r in (1e-5, 1e-4, 1e-3):
        _, ut, _ = velocity_at(np.array([r]), np.array([0.05]), t, p, table)
        omegas.append(float(ut[0] / r))
    assert np.all(np.isfinite(omegas))
    assert max(omegas) - min(omegas) < 1e-3 * abs(omegas[0])


def test_velocity_matches_field_protocol(p):
    """NSField.velocity 与 velocity_at 在同一批点上一致。"""
    field = SimilarityField(p)
    rng = np.random.default_rng(0)
    pts = rng.uniform(-0.2, 0.2, size=(64, 3))
    v = field.velocity(pts, 0.5)
    r = np.hypot(pts[:, 0], pts[:, 1])
    ur, ut, uz = velocity_at(r, pts[:, 2], 0.5, p, field.table)
    th = np.arctan2(pts[:, 1], pts[:, 0])
    np.testing.assert_allclose(v[:, 0], ur * np.cos(th) - ut * np.sin(th), rtol=1e-9)
    np.testing.assert_allclose(v[:, 2], uz, rtol=1e-9)


def test_incompressibility_residual(p, table):
    """‖∇·u‖ 相对误差应远小于 10%（前导阶自相似解的离散残差）。"""
    n = 128
    r = np.linspace(0.003, 0.35, n)
    z = np.linspace(-1.0, 1.0, n)
    R, Z = np.meshgrid(r, z, indexing="ij")
    ur, ut, uz = velocity_at(R, Z, 0.5, p, table)
    div = (
        np.gradient(ur, r[1] - r[0], axis=0)
        + ur / R
        + np.gradient(uz, z[1] - z[0], axis=1)
    )
    rel = np.sqrt(np.mean(div**2)) / np.sqrt(np.mean(ur**2 + ut**2 + uz**2))
    assert rel < 0.05, f"不可压残差 {rel:.3f} 偏大"


def test_axial_velocity_flips_sign(p, table):
    """论文 §2：分层两侧上下流出 → u_z 在 z 变号。"""
    r = np.array([0.05, 0.05])
    z = np.array([0.3, -0.3])
    _, _, uz = velocity_at(r, z, 0.5, p, table)
    assert uz[0] * uz[1] < 0


def test_radial_velocity_points_inward(p, table):
    """r·u_r = V₀ < 0：粒子向内旋（参考图里螺旋收缩的来源）。"""
    _, _, _ = velocity_at(np.array([0.1]), np.array([0.1]), 0.5, p, table)
    ur, _, _ = velocity_at(np.array([0.1]), np.array([0.1]), 0.5, p, table)
    assert ur[0] < 0


@pytest.mark.parametrize("tau", [0.2, 0.05, 0.01])
def test_growth_scaling(p, table, tau):
    """峰值速度与涡量按 τ^(−1/2−h) 增长（论文标度）。"""
    t = p.t_blow - tau
    stats = analyze(p, t, table=table, n_r=160, n_z=160)
    ref_tau = 0.2
    ref = analyze(p, p.t_blow - ref_tau, table=table, n_r=160, n_z=160)
    # 论文：‖u‖ ≍ τ^(−1/2−h)，而 ‖ω‖ ≍ τ^(−1)（涡量才是真正发散的量）
    assert stats.u_max / ref.u_max == pytest.approx(
        (tau / ref_tau) ** (-(0.5 + p.h)), rel=0.25
    )
    assert stats.omega_max / ref.omega_max == pytest.approx(
        (tau / ref_tau) ** -1.0, rel=0.35
    )


def test_elongation_grows_as_tau_power():
    """ℓ_z/ℓ_r ≍ τ^(−h)。h=0.2（非论文区间）放大效应才量得出来。"""
    q = SimilarityParams(h=0.2)
    tq = profile_table(q)
    a = analyze(q, q.t_blow - 0.20, table=tq, n_r=240, n_z=240, r_max=1.5, z_max=2.0)
    b = analyze(q, q.t_blow - 0.02, table=tq, n_r=240, n_z=240, r_max=1.5, z_max=2.0)
    assert b.elongation > a.elongation * 1.1


def test_grid_column_undershoots_analytic(p, table):
    """网格列的峰值不应超过解析列（分辨率不足只会低估，不会凭空放大）。"""
    t = 0.5
    ana = analyze(p, t, table=table, n_r=200, n_z=200)
    for n in (32, 64):
        g = grid_stats(p, t, table=table, n=n, extent=0.35, z_extent=0.8)
        assert g.omega_max <= ana.omega_max * 1.05


def test_diagnostics_fields_are_finite(p, table):
    s = analyze(p, 0.5, table=table, n_r=120, n_z=120)
    d = s.as_dict()
    for key in (
        "u_max",
        "omega_max",
        "enstrophy",
        "kinetic",
        "core_radius",
        "axial_extent",
        "elongation",
        "divergence_rel",
        "re_theta",
    ):
        assert np.isfinite(d[key]), key
        assert d[key] >= 0 or key == "elongation"
