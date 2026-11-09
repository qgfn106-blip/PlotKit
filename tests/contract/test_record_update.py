# -*- coding: utf-8 -*-
"""README 更新记录机制（用户规则 2026-11-09）的行为回归。

只经 tools/record_update.py 的公开函数 check()/add() 驱动，全部落在 tmp_path，
不读仓库源码做字符串断言，也不触碰真实 README.md / docs/UPDATE_LOG.md。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[2] / "tools" / "record_update.py"


@pytest.fixture(scope="module")
def ru():
    spec = importlib.util.spec_from_file_location("record_update_under_test", _TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed(ru, directory: Path):
    readme = directory / "README.md"
    log = directory / "docs" / "UPDATE_LOG.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text(
        "# 标题\n\n<!-- UPDATE:LATEST:BEGIN -->\n"
        "- 日期：2026-11-09\n"
        "- 版本/ref：old-ref\n"
        "- 更新内容：旧内容\n"
        "- 证据：docs/old.md\n"
        + ru.RECORD_LINK
        + "\n<!-- UPDATE:LATEST:END -->\n\n正文须原样保留\n",
        encoding="utf-8",
    )
    log.write_text(
        "前言\n\n"
        + ru.HEADER
        + "\n| --- | --- | --- | --- | --- |\n"
        + "| 1 | 2026-11-09 | old-ref | 旧内容 | docs/old.md |\n"
        + "| 2 | 2026-11-08 | older | 更早 | docs/older.md |\n\n尾注\n",
        encoding="utf-8",
    )
    return readme, log


def test_check_accepts_five_line_block(ru, tmp_path):
    readme, log = _seed(ru, tmp_path)
    assert ru.check(readme, log) == 0


def test_check_rejects_missing_record_link(ru, tmp_path):
    readme, log = _seed(ru, tmp_path)
    text = readme.read_text(encoding="utf-8")
    readme.write_text(text.replace(ru.RECORD_LINK + "\n", ""), encoding="utf-8")
    assert ru.check(readme, log) == 1


def test_add_preserves_link_and_outside_content(ru, tmp_path):
    readme, log = _seed(ru, tmp_path)
    assert (
        ru.add(
            day="2026-11-10",
            ref="new-ref",
            summary="新内容",
            evidence="docs/new.md",
            readme_path=readme,
            log_path=log,
        )
        == 0
    )
    assert ru.check(readme, log) == 0
    text = readme.read_text(encoding="utf-8")
    assert ru.RECORD_LINK in text
    assert "# 标题" in text and "正文须原样保留" in text
    assert "- 版本/ref：new-ref" in text and "- 更新内容：新内容" in text
    log_text = log.read_text(encoding="utf-8")
    assert "| 1 | 2026-11-10 | new-ref | 新内容 | docs/new.md |" in log_text
    assert "尾注" in log_text


def test_add_rolls_to_max_rows(ru, tmp_path):
    readme, log = _seed(ru, tmp_path)
    for index in range(ru.MAX_ROWS + 2):
        day = f"2026-12-{index + 1:02d}"
        assert (
            ru.add(
                day=day,
                ref=f"ref-{index}",
                summary=f"内容-{index}",
                evidence=f"docs/e{index}.md",
                readme_path=readme,
                log_path=log,
            )
            == 0
        )
    assert ru.check(readme, log) == 0
    rows = [
        line
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("| ") and "---" not in line and "# |" not in line
    ]
    assert len(rows) == ru.MAX_ROWS
