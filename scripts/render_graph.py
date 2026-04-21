#!/usr/bin/env python3
"""
render_graph.py — отрисовка интерактивного графа связей воркспейса.

Читает карточки 00-14 в `<workspace>/`, собирает узлы и рёбра, рендерит
`_generated/graph.html` (vis-network, inline) и `_generated/graph.mermaid`
(fallback).

Используется скиллом `graph` и субагентом `cog-detector`.

Запуск:
    python3 render_graph.py --workspace /path/to/cognitive-os
    python3 render_graph.py --workspace /path/to/cognitive-os --project proj-001
    python3 render_graph.py --workspace /path/to/cognitive-os --mermaid-only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.error_handling import safe_main  # noqa: E402

# Регексы для ID
ID_PATTERNS = {
    "project": re.compile(r"\bproj-\d{3}\b"),
    "entity": re.compile(r"\bent-\d{3}\b"),
    "pattern": re.compile(r"\bpat-\d{3}\b"),
    "mechanism": re.compile(r"\bwm-\d{3}\b"),
    "error": re.compile(r"\bec-\d{3}\b"),
    "knowledge": re.compile(r"\bkm-\d{3}\b"),
    "lesson": re.compile(r"\blesson-\d{3}\b"),
    "meta": re.compile(r"\bmd-\d{3}\b"),
    "term": re.compile(r"\bterm-\d{3}\b"),
    "domain": re.compile(r"\bdomain-\d{3}\b"),
    "cluster": re.compile(r"\bcluster-\d{3}\b"),
    "reflection": re.compile(r"\bsr-\d{3}\b"),
    "audit": re.compile(r"\baudit-\d{3}\b"),
    "insight": re.compile(r"\binsight-\d{3}\b"),
    "insurance": re.compile(r"\binsurance-\d{3}\b"),
}

# Цвета узлов по типу (соответствуют SKILL.md графа)
NODE_COLORS = {
    "project": "#4A90E2",
    "entity": "#27AE60",
    "pattern": "#E67E22",
    "mechanism": "#F1C40F",
    "error": "#E74C3C",
    "knowledge": "#8E44AD",
    "lesson": "#95A5A6",
    "meta": "#34495E",
    "term": "#7F8C8D",
    "domain": "#1ABC9C",
    "cluster": "#9B59B6",
    "reflection": "#BDC3C7",
    "audit": "#C0392B",
    "insight": "#F39C12",
    "insurance": "#16A085",
}

WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#([^\]\|]+))?(?:\|[^\]]+)?\]\]")


@dataclass
class Node:
    id: str
    type: str
    label: str = ""
    title: str = ""  # tooltip
    color: str = "#888"
    group: str = ""  # для фильтров

    def to_vis(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label or self.id,
            "title": self.title or self.id,
            "color": self.color,
            "group": self.group or self.type,
        }


@dataclass
class Edge:
    from_: str
    to: str
    kind: str = "link"  # link | conflict | shared_domain | ...
    label: str = ""

    def to_vis(self) -> dict[str, Any]:
        style: dict[str, Any] = {"from": self.from_, "to": self.to}
        if self.kind == "conflict":
            style["color"] = {"color": "#E74C3C"}
            style["dashes"] = False
            style["width"] = 3
            style["label"] = self.label or "конфликт"
        elif self.kind == "shared_domain":
            style["dashes"] = True
        return style


@dataclass
class GraphData:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def add_node(self, node: Node) -> None:
        if node.id not in self.nodes:
            self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        # Дедупликация
        key = (edge.from_, edge.to, edge.kind)
        if not any((e.from_, e.to, e.kind) == key for e in self.edges):
            self.edges.append(edge)


def detect_type(node_id: str) -> str:
    for kind, rx in ID_PATTERNS.items():
        if rx.fullmatch(node_id):
            return kind
    return "other"


def extract_ids(text: str) -> set[str]:
    ids: set[str] = set()
    for rx in ID_PATTERNS.values():
        ids.update(rx.findall(text))
    return ids


def parse_wikilinks(text: str) -> list[tuple[str, str | None]]:
    """Возвращает список (target, anchor)."""
    return [(m.group(1).strip(), m.group(2)) for m in WIKILINK_RE.finditer(text)]


def extract_label(content: str, node_id: str) -> str:
    """Ищет строку '### node_id — Название' и возвращает название."""
    for line in content.splitlines():
        if node_id in line and "—" in line:
            parts = line.split("—", 1)
            if len(parts) == 2:
                return parts[1].strip()[:80]
    return node_id


def build_graph(workspace: Path, filters: dict[str, Any]) -> GraphData:
    """Читает все .md в воркспейсе, строит граф."""
    g = GraphData()
    md_files = sorted(workspace.glob("*.md"))

    # Добавляем проектные папки
    projects_dir = workspace / "projects"
    if projects_dir.exists():
        for pfile in sorted(projects_dir.rglob("*.md")):
            md_files.append(pfile)

    # 1. Сбор всех узлов по ID из всех файлов
    for mf in md_files:
        try:
            content = mf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for id_ in sorted(extract_ids(content)):
            if id_ in g.nodes:
                continue
            t = detect_type(id_)
            if t == "other":
                continue
            g.add_node(
                Node(
                    id=id_,
                    type=t,
                    label=extract_label(content, id_),
                    color=NODE_COLORS.get(t, "#888"),
                    group=t,
                )
            )

    # 2. Сбор рёбер из wikilinks
    for mf in md_files:
        try:
            content = mf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Из какого ID источника? Ищем ближайший ID выше каждого wikilink
        # Упрощение: берём все ID в файле и считаем их источниками
        # (адекватно для файлов-карточек).
        source_ids = extract_ids(content)
        if not source_ids:
            # файл-карточка без ID — пропуск (например, 00_index до наполнения)
            continue
        for target, _anchor in parse_wikilinks(content):
            t = target.strip()
            if t in g.nodes:
                for src in sorted(source_ids):
                    if src == t:
                        continue
                    g.add_edge(Edge(from_=src, to=t, kind="link"))

    # 3. Conflict-edges из 14_audit_log
    audit_file = workspace / "14_audit_log.md"
    if audit_file.exists():
        content = audit_file.read_text(encoding="utf-8", errors="replace")
        # Парсинг блоков audit-NNN: ищем «Источник A: [[X]]» и «Источник B: [[Y]]»
        blocks = re.split(r"\n###\s+audit-\d{3}", content)
        for b in blocks[1:]:
            a_match = re.search(r"Источник A:\s*\[\[([^\]\|#]+)", b)
            b_match = re.search(r"Источник B:\s*\[\[([^\]\|#]+)", b)
            if a_match and b_match:
                a, bn = a_match.group(1), b_match.group(1)
                if a in g.nodes and bn in g.nodes:
                    g.add_edge(Edge(from_=a, to=bn, kind="conflict", label="конфликт"))

    # 4. Фильтрация
    if filters.get("project"):
        p = filters["project"]
        if p in g.nodes:
            keep = {p}
            # соседи 2 хопа
            for _ in range(2):
                new = set(keep)
                for e in g.edges:
                    if e.from_ in keep:
                        new.add(e.to)
                    if e.to in keep:
                        new.add(e.from_)
                keep = new
            g.nodes = {k: v for k, v in g.nodes.items() if k in keep}
            g.edges = [e for e in g.edges if e.from_ in keep and e.to in keep]

    if filters.get("conflict_only"):
        conflict_nodes: set[str] = set()
        for e in g.edges:
            if e.kind == "conflict":
                conflict_nodes.add(e.from_)
                conflict_nodes.add(e.to)
        g.nodes = {k: v for k, v in g.nodes.items() if k in conflict_nodes}
        g.edges = [e for e in g.edges if e.kind == "conflict"]

    return g


def render_html(g: GraphData, out: Path, workspace_name: str) -> None:
    """Рендер интерактивного HTML на vis-network (inline)."""
    nodes_json = json.dumps([n.to_vis() for n in g.nodes.values()], ensure_ascii=False)
    edges_json = json.dumps([e.to_vis() for e in g.edges], ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Когнитивный граф — {workspace_name}</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #fafafa; }}
#header {{ padding: 0.75em 1em; background: #fff; border-bottom: 1px solid #ddd; display: flex; align-items: center; gap: 1em; flex-wrap: wrap; }}
#header h1 {{ margin: 0; font-size: 1.1em; }}
.legend {{ display: flex; gap: 0.5em; flex-wrap: wrap; }}
.legend span {{ padding: 0.2em 0.6em; border-radius: 4px; color: white; font-size: 0.85em; }}
#controls {{ display: flex; gap: 0.5em; margin-left: auto; }}
#controls input {{ padding: 0.3em 0.5em; border: 1px solid #ccc; border-radius: 4px; }}
#mynetwork {{ width: 100%; height: calc(100vh - 60px); border: 0; }}
#stats {{ position: fixed; bottom: 1em; right: 1em; background: white; padding: 0.5em 1em; border: 1px solid #ddd; border-radius: 6px; font-size: 0.85em; }}
</style>
</head>
<body>
<div id="header">
  <h1>Когнитивный граф — {workspace_name}</h1>
  <div class="legend">
    <span style="background:#4A90E2">проекты</span>
    <span style="background:#27AE60">сущности</span>
    <span style="background:#E67E22">паттерны</span>
    <span style="background:#F1C40F;color:#333">механизмы</span>
    <span style="background:#E74C3C">ошибки</span>
    <span style="background:#8E44AD">знания</span>
    <span style="background:#1ABC9C">домены</span>
    <span style="background:#9B59B6">кластеры</span>
  </div>
  <div id="controls">
    <input type="text" id="search" placeholder="Поиск по ID/названию..." />
  </div>
</div>
<div id="mynetwork"></div>
<div id="stats">Узлов: {len(g.nodes)} · Рёбер: {len(g.edges)}</div>
<script>
const nodes = new vis.DataSet({nodes_json});
const edges = new vis.DataSet({edges_json});
const container = document.getElementById('mynetwork');
const options = {{
  nodes: {{ shape: 'dot', size: 16, font: {{ size: 14, face: '-apple-system' }} }},
  edges: {{ smooth: {{ type: 'continuous' }}, arrows: {{ to: {{ enabled: false }} }} }},
  physics: {{ stabilization: {{ iterations: 150 }}, barnesHut: {{ gravitationalConstant: -4500, springLength: 120 }} }},
  interaction: {{ hover: true, tooltipDelay: 200, hideEdgesOnDrag: true }},
  groups: {{
    project: {{ color: '#4A90E2' }}, entity: {{ color: '#27AE60' }},
    pattern: {{ color: '#E67E22' }}, mechanism: {{ color: '#F1C40F' }},
    error: {{ color: '#E74C3C' }}, knowledge: {{ color: '#8E44AD' }},
    lesson: {{ color: '#95A5A6' }}, meta: {{ color: '#34495E' }},
    term: {{ color: '#7F8C8D' }}, domain: {{ color: '#1ABC9C' }},
    cluster: {{ color: '#9B59B6' }}, reflection: {{ color: '#BDC3C7' }},
    audit: {{ color: '#C0392B' }}, insight: {{ color: '#F39C12' }},
    insurance: {{ color: '#16A085' }}
  }}
}};
const network = new vis.Network(container, {{ nodes, edges }}, options);

document.getElementById('search').addEventListener('input', (e) => {{
  const q = e.target.value.trim().toLowerCase();
  if (!q) {{ nodes.forEach(n => nodes.update({{id: n.id, hidden: false}})); return; }}
  nodes.forEach(n => {{
    const hit = (n.id + ' ' + (n.label || '')).toLowerCase().includes(q);
    nodes.update({{id: n.id, hidden: !hit}});
  }});
}});
</script>
</body>
</html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def render_mermaid(g: GraphData, out: Path) -> None:
    """Рендер статического mermaid-графа (fallback)."""
    lines = ["```mermaid", "graph LR"]
    # Узлы
    for n in g.nodes.values():
        safe_label = (n.label or n.id).replace('"', "'")
        lines.append(f'  {n.id.replace("-", "_")}["{n.id}: {safe_label}"]')
    # Рёбра
    for e in g.edges:
        a = e.from_.replace("-", "_")
        b = e.to.replace("-", "_")
        if e.kind == "conflict":
            lines.append(f"  {a} -.конфликт.-> {b}")
        else:
            lines.append(f"  {a} --> {b}")
    # Классы
    lines.append("  classDef conflict stroke:#f00,stroke-width:2px;")
    lines.append("```")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


@safe_main
def main() -> int:
    ap = argparse.ArgumentParser(description="Рендер графа когнитивного воркспейса.")
    ap.add_argument("--workspace", required=True, help="Путь к воркспейсу (cognitive-os/)")
    ap.add_argument("--project", help="Ego-граф одного проекта (proj-NNN)")
    ap.add_argument("--conflict-only", action="store_true", help="Только conflict-edges")
    ap.add_argument("--mermaid-only", action="store_true", help="Не рендерить HTML")
    ap.add_argument("--html-only", action="store_true", help="Не рендерить mermaid")
    ap.add_argument("--if-changed", action="store_true",
                    help="Noop-флаг для hooks (скрипт идемпотентен).")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        print(f"Воркспейс не найден: {workspace}", file=sys.stderr)
        return 1

    filters = {
        "project": args.project,
        "conflict_only": args.conflict_only,
    }
    g = build_graph(workspace, filters)
    gen_dir = workspace / "_generated"

    if not args.mermaid_only:
        render_html(g, gen_dir / "graph.html", workspace.name)
        print(f"HTML: {gen_dir / 'graph.html'}")
    if not args.html_only:
        render_mermaid(g, gen_dir / "graph.mermaid")
        print(f"Mermaid: {gen_dir / 'graph.mermaid'}")

    print(f"Узлов: {len(g.nodes)} · Рёбер: {len(g.edges)}")
    return 0


if __name__ == "__main__":
    main()
