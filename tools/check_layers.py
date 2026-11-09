#!/usr/bin/env python3
"""P0 分层闸门：AST 扫描 src/plotkit 的 import，守住契约分层方向。

只启用在当前代码树上确实成立的规则（X8）：schema 不依赖 plotkit.*；document
不依赖 store/backends/server/api；store 不依赖 backends/server/api；backends
不依赖 server；server 不依赖 api.native；plotkit/__init__.py 不依赖 contrib；
契约加载器（schema/document）不依赖 Selector（裁定 ⑩，防止接缝粘连）。
默认写 reports/architecture.json；--check 只读核对已提交的报告。
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "plotkit"
REPORT = ROOT / "reports" / "architecture.json"

FORBIDDEN: dict[str, tuple[str, ...]] = {
    "document": ("plotkit.store", "plotkit.backends", "plotkit.server", "plotkit.api"),
    "store": ("plotkit.backends", "plotkit.server", "plotkit.api"),
    "backends": ("plotkit.server",),
    "server": ("plotkit.api.native",),
}

RULE_TEXT = {
    "schema": "schema 层不得依赖任何 plotkit.* 模块",
    "document": "document 层不得依赖 plotkit.store / backends / server / api",
    "store": "store 层不得依赖 plotkit.backends / server / api",
    "backends": "backends 层不得依赖 plotkit.server",
    "server": "server 层不得依赖 plotkit.api.native",
    "__init__": "plotkit/__init__.py 不得导入 contrib",
}

# 裁定 ⑩：接缝「契约加载器 + Selector.select()」是两处，防止粘连成一处。
CONTRACT_LOADERS = ("schema", "document")
SELECTOR_RULE = "契约加载器（schema/document）不得 import Selector"


def _is_selector_import(layer: str, module: str) -> bool:
    """检测契约加载器是否触碰了 Selector（绝对或相对导入）。"""
    if layer not in CONTRACT_LOADERS:
        return False
    if module == "plotkit.backends.selector":
        return True
    if module.startswith("plotkit.backends.selector."):
        return True
    # 相对导入 `.selector` 会被解析成 plotkit.<layer>.selector[.Name]。
    parts = module.split(".")
    return len(parts) >= 2 and parts[-1] == "selector"


def _layer(path: Path) -> str | None:
    """Return the first package directory under plotkit, or None for root modules."""
    parts = path.relative_to(PKG).parts
    if len(parts) == 1 and parts[0] == "__init__.py":
        return "__init__"
    if len(parts) >= 2:
        return parts[0]
    return None


def _package(path: Path) -> str:
    """Dotted name of the package containing this module (for relative imports)."""
    parts = list(path.relative_to(PKG).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    elif parts:
        parts.pop()
    return ".".join(["plotkit", *parts])


def _absolute_modules(node: ast.Import | ast.ImportFrom, package: str) -> list[str]:
    """Resolve imports to dotted absolute names, including ``from X import Y`` names."""
    modules: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name:
                modules.append(alias.name)
        return modules
    level = node.level or 0
    if level == 0:
        base = node.module.split(".") if node.module else []
    else:
        base = package.split(".") if package else []
        drop = level - 1
        if drop:
            base = base[:-drop] if drop <= len(base) else []
        if node.module:
            base = base + node.module.split(".")
    stem = ".".join(base)
    if stem:
        modules.append(stem)
    for alias in node.names:
        if alias.name == "*":
            continue
        modules.append(f"{stem}.{alias.name}" if stem else alias.name)
    return modules


def _is_forbidden(layer: str, module: str) -> bool:
    if layer == "schema":
        # Intra-package imports (plotkit.schema / plotkit.schema.*) are legitimate.
        if module == "plotkit.schema" or module.startswith("plotkit.schema."):
            return False
        return module == "plotkit" or module.startswith("plotkit.")
    if layer == "__init__":
        return "contrib" in module.split(".")
    return any(
        module == prefix or module.startswith(prefix + ".")
        for prefix in FORBIDDEN.get(layer, ())
    )


def evaluate() -> tuple[dict, list[str]]:
    files = sorted(PKG.rglob("*.py")) if PKG.is_dir() else []
    violations: list[str] = []
    for path in files:
        layer = _layer(path)
        if layer is None or layer not in RULE_TEXT:
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            violations.append(f"{rel}: 无法解析 AST：{type(exc).__name__}: {exc}")
            continue
        package = _package(path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for module in _absolute_modules(node, package):
                if _is_selector_import(layer, module):
                    violations.append(
                        f"{rel}:{node.lineno}: {SELECTOR_RULE}；发现 {module}"
                    )
                    continue
                if _is_forbidden(layer, module):
                    violations.append(
                        f"{rel}:{node.lineno}: {RULE_TEXT[layer]}；发现 {module}"
                    )
    violations = sorted(set(violations))
    payload = {"scanned": len(files), "violations": violations, "ok": not violations}
    return payload, violations


def _write_report(payload: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    REPORT.write_text(text, encoding="utf-8")


def run(*, write: bool = True, quiet: bool = False) -> int:
    payload, violations = evaluate()
    if write:
        _write_report(payload)
    elif REPORT.is_file():
        try:
            committed = json.loads(REPORT.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            violations.append(f"reports/architecture.json 无法读取：{exc}")
        else:
            if committed != payload:
                violations.append(
                    "reports/architecture.json 与当前扫描结果不一致；"
                    "请重新运行 python tools/check_layers.py"
                )
    else:
        violations.append(
            "缺少 reports/architecture.json；请先运行 python tools/check_layers.py"
        )
    for item in violations:
        print(item, file=sys.stderr)
    if not quiet:
        print(
            f"check_layers: scanned={payload['scanned']} "
            f"violations={len(violations)} ok={not violations}"
        )
    return 1 if violations else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PlotKit 分层依赖闸门")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write", action="store_true", help="生成 reports/architecture.json（默认）"
    )
    mode.add_argument(
        "--check", action="store_true", help="只读核对已提交报告，不写文件"
    )
    args = parser.parse_args(argv)
    return run(write=not args.check)


if __name__ == "__main__":
    sys.exit(main())
