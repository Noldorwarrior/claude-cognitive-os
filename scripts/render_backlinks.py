#!/usr/bin/env python3
"""
render_backlinks.py — построение обратных ссылок для всех ID воркспейса.

Читает все `.md` в воркспейсе, собирает `[[target]]` и формирует
`_generated/backlinks.md`.

Используется скиллом `backlinks`. Также выявляет висячие ссылки
(target не существует) — они помечаются и, опционально, пишутся в
`14_audit_log.md` как regression.

Запуск:
    python3 render_backlinks.py --workspace /path/to/cognitive-os
    python3 render_backlinks.py --workspace /path/to/cognitive-os --broken
    python3 render_backlinks.py --workspace /path/to/cognitive-os --orphans
    python3 render_backlinks.py --workspace /path/to/cognitive-os --id pat-007
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.error_handling import safe_main  # noqa: E402

WIKILINK_RE = re.compile(r"\[\[([^\]\|]+)(?:\|[^\]]+)?\]\]")

ID_PREFIXES = [
    "pat-", "wm-", "ec-", "km-", "md-", "term-",
    "ent-", "proj-", "lesson-", "sr-", "audit-",
    "domain-", "cluster-",
]

ID_RE = re.compile(r"\b(" + "|".join(ID_PREFIXES) + r")\d{3}\b")

# Имена «системных» карточек (без NNN) — тоже допустимы как targets
CARD_NAMES = [
    "00_index", "01_user_profile", "02_patterns", "03_projects_registry",
    "04_meta_decisions", "05_global_glossary", "06_lessons_learned",
    "07_global_entities", "08_knowledge_maps", "09_working_mechanisms",
    "10_error_corrections", "11_confidence_scoring",
    "12_cross_project_graph", "13_self_reflection", "14_audit_log",
]


def collect_ids(workspace: Path) -> set[str]:
    """Сбор всех существующих ID в воркспейсе."""
    ids: set[str] = set()
    for mf in workspace.rglob("*.md"):
        # skip archive/
        if "archive" in mf.parts:
            continue
        try:
            text = mf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        ids.update(ID_RE.findall(text) and
                   [m.group(0) for m in ID_RE.finditer(text)])
    # второй заход для имён карточек (они есть, только если файл существует)
    for name in CARD_NAMES:
        if (workspace / f"{name}.md").exists():
            ids.add(name)
    return ids


def parse_target(raw: str) -> tuple[str, str | None]:
    """Разбирает '[[target#anchor]]' → (target, anchor)."""
    part = raw.split("|", 1)[0]
    if "#" in part:
        target, anchor = part.split("#", 1)
        return target.strip(), anchor.strip()
    return part.strip(), None


def build_backlinks(
    workspace: Path,
) -> tuple[dict[str, list[dict]], list[dict]]:
    """Собрать backlinks index и список висячих ссылок."""
    ids = collect_ids(workspace)
    backlinks: dict[str, list[dict]] = defaultdict(list)
    broken: list[dict] = []

    for mf in sorted(workspace.rglob("*.md")):
        if "archive" in mf.parts:
            continue
        if "_generated" in mf.parts:
            continue
        rel = mf.relative_to(workspace).as_posix()
        try:
            text = mf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            for m in WIKILINK_RE.finditer(line):
                target, anchor = parse_target(m.group(1))
                entry = {
                    "from": rel,
                    "anchor": anchor,
                    "line": idx,
                }
                if target in ids:
                    backlinks[target].append(entry)
                else:
                    # Возможно, это anchor от карточки (e.g. "02_patterns" → exists)
                    # если anchor есть и он — валидный ID, считаем target'ом именно его
                    if anchor and anchor in ids:
                        backlinks[anchor].append(
                            {**entry, "via": target}
                        )
                    else:
                        broken.append({**entry, "target": target, "anchor": anchor})

    # Дедупликация
    for k, arr in backlinks.items():
        seen = set()
        unique = []
        for e in arr:
            key = (e["from"], e.get("anchor"), e.get("via"))
            if key not in seen:
                seen.add(key)
                unique.append(e)
        backlinks[k] = unique

    return backlinks, broken


def render(
    workspace: Path,
    backlinks: dict[str, list[dict]],
    broken: list[dict],
    mode: str = "full",
    id_filter: str | None = None,
) -> str:
    """Формирует backlinks.md как markdown-строку."""
    from datetime import date
    today = date.today().isoformat()
    lines = [f"# Обратные ссылки — {today}", ""]

    # Группировка по типу
    groups: dict[str, list[str]] = defaultdict(list)
    for k in backlinks:
        prefix = next((p for p in ID_PREFIXES if k.startswith(p)), None)
        if prefix:
            groups[prefix].append(k)
        elif k in CARD_NAMES:
            groups["cards"].append(k)

    titles = {
        "pat-": "## Паттерны",
        "wm-": "## Механизмы",
        "ec-": "## Ошибки",
        "km-": "## Карты знаний",
        "md-": "## Мета-решения",
        "term-": "## Термины",
        "ent-": "## Сущности",
        "proj-": "## Проекты",
        "lesson-": "## Уроки",
        "sr-": "## Самоаудиты",
        "audit-": "## Аудиты",
        "domain-": "## Домены",
        "cluster-": "## Кластеры",
        "cards": "## Карточки",
    }

    if mode == "broken":
        lines.append("## Висячие ссылки")
        lines.append("")
        if not broken:
            lines.append("_Висячих ссылок не обнаружено._")
        for e in broken:
            lines.append(
                f"- `{e['from']}:{e['line']}` → `[[{e['target']}"
                + (f"#{e['anchor']}" if e.get("anchor") else "")
                + "]]` — **ВИСЯЧАЯ**"
            )
        return "\n".join(lines) + "\n"

    if mode == "orphans":
        all_ids = collect_ids(workspace)
        orphans = sorted(all_ids - set(backlinks.keys()))
        lines.append("## Изолированные узлы (нет входящих ссылок)")
        lines.append("")
        if not orphans:
            lines.append("_Нет._")
        for o in orphans:
            lines.append(f"- `{o}`")
        return "\n".join(lines) + "\n"

    if id_filter:
        lines.append(f"## Обратные ссылки на `{id_filter}`")
        lines.append("")
        arr = backlinks.get(id_filter, [])
        if not arr:
            lines.append("_Нет входящих ссылок._")
        for e in arr:
            anchor_part = f"#{e['anchor']}" if e.get("anchor") else ""
            lines.append(f"- `{e['from']}:{e['line']}`{' (via ' + e['via'] + ')' if e.get('via') else ''}")
        return "\n".join(lines) + "\n"

    # full mode
    order = list(titles.keys())
    for prefix in order:
        ids_in_group = sorted(groups.get(prefix, []))
        if not ids_in_group:
            continue
        lines.append(titles[prefix])
        lines.append("")
        for k in ids_in_group:
            lines.append(f"### [[{k}]]")
            for e in backlinks[k]:
                anchor_part = f"#{e['anchor']}" if e.get("anchor") else ""
                via_part = f" (via `{e['via']}`)" if e.get("via") else ""
                lines.append(f"- `{e['from']}:{e['line']}`{via_part}")
            lines.append("")

    if broken:
        lines.append("## Висячие ссылки")
        lines.append("")
        for e in broken:
            lines.append(
                f"- `{e['from']}:{e['line']}` → `[[{e['target']}"
                + (f"#{e['anchor']}" if e.get("anchor") else "")
                + "]]` — **ВИСЯЧАЯ**"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


@safe_main
def main() -> int:
    ap = argparse.ArgumentParser(description="Рендер backlinks когнитивного воркспейса.")
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--id", dest="id_filter", help="Только для одного ID")
    ap.add_argument("--broken", action="store_true", help="Только висячие")
    ap.add_argument("--orphans", action="store_true", help="Только изолированные")
    ap.add_argument("--stdout", action="store_true", help="Не писать файл, вывод в stdout")
    ap.add_argument("--if-changed", action="store_true",
                    help="Noop-флаг для hooks (скрипт идемпотентен).")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        print(f"Воркспейс не найден: {workspace}", file=sys.stderr)
        return 1

    backlinks, broken = build_backlinks(workspace)
    mode = "full"
    if args.broken:
        mode = "broken"
    elif args.orphans:
        mode = "orphans"

    content = render(workspace, backlinks, broken, mode=mode, id_filter=args.id_filter)

    if args.stdout:
        print(content)
    else:
        out = workspace / "_generated" / "backlinks.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"Backlinks: {out}")

    if broken:
        print(f"ВНИМАНИЕ: найдено висячих ссылок: {len(broken)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    main()
