#!/usr/bin/env python3
"""
render_mermaid.py — быстрый статический рендер mermaid-графа.

Обёртка над render_graph.py в режиме --mermaid-only. Используется для
случаев, когда нужен только текстовый граф (документация, README,
плейсхолдер в _generated/).

Запуск:
    python3 render_mermaid.py --workspace /path/to/cognitive_os
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Переиспользуем логику из render_graph.py
THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from render_graph import build_graph, render_mermaid  # type: ignore[import]
from lib.error_handling import safe_main  # noqa: E402


@safe_main
def main() -> int:
    ap = argparse.ArgumentParser(description="Рендер mermaid-графа.")
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--project", help="Ego-граф одного проекта")
    ap.add_argument("--conflict-only", action="store_true")
    ap.add_argument("--stdout", action="store_true", help="В stdout, не в файл")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        print(f"Воркспейс не найден: {workspace}", file=sys.stderr)
        return 1

    g = build_graph(
        workspace,
        {"project": args.project, "conflict_only": args.conflict_only},
    )

    if args.stdout:
        import io
        buf = io.StringIO()
        lines = ["```mermaid", "graph LR"]
        for n in g.nodes.values():
            safe_label = (n.label or n.id).replace('"', "'")
            lines.append(f'  {n.id.replace("-", "_")}["{n.id}: {safe_label}"]')
        for e in g.edges:
            a = e.from_.replace("-", "_")
            b = e.to.replace("-", "_")
            if e.kind == "conflict":
                lines.append(f"  {a} -.конфликт.-> {b}")
            else:
                lines.append(f"  {a} --> {b}")
        lines.append("  classDef conflict stroke:#f00,stroke-width:2px;")
        lines.append("```")
        print("\n".join(lines))
    else:
        out = workspace / "_generated" / "graph.mermaid"
        render_mermaid(g, out)
        print(f"Mermaid: {out}")

    print(f"Узлов: {len(g.nodes)} · Рёбер: {len(g.edges)}")
    return 0


if __name__ == "__main__":
    main()
