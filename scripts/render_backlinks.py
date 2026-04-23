#!/usr/bin/env python3
"""
render_backlinks.py — построение обратных ссылок для всех ID воркспейса.

Читает все `.md` в воркспейсе, собирает `[[target]]` и формирует
`_generated/backlinks.md`.

С версии v1.3.8 скрипт опирается на модуль ``link_classifier.py``:
каждая wikilink относится к одному из классов ``vault | plugin | agent |
carry_over | memory | dangling`` — см. ``docs/link-conventions.md``.
``backlinks.md`` формируется с отдельными секциями на каждый класс.

Запуск:
    python3 render_backlinks.py --workspace /path/to/cognitive_os
    python3 render_backlinks.py --workspace /path/to/cognitive_os --memory-dir ~/Library/.../memory
    python3 render_backlinks.py --workspace /path/to/cognitive_os --broken
    python3 render_backlinks.py --workspace /path/to/cognitive_os --orphans
    python3 render_backlinks.py --workspace /path/to/cognitive_os --id pat-007
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.error_handling import safe_main  # noqa: E402
from link_classifier import (  # noqa: E402
    CARD_NAMES,
    VAULT_ID_PREFIXES,
    WIKILINK_RE,
    build_carry_over_index,
    build_memory_index,
    classify_target,
    find_default_memory_dir,
    parse_target,
    strip_backticked,
)

# Паттерн для поиска уже существующих ID внутри vault (для ``collect_ids``).
# Дублируется здесь, потому что модуль-классификатор работает только с
# готовыми target-строками и не знает о том, как искать ID в тексте.
ID_RE = re.compile(
    r"\b(?:" + "|".join(VAULT_ID_PREFIXES) + r")-\d{3,}\b"
)


def collect_ids(workspace: Path) -> set[str]:
    """Сбор всех существующих vault-ID + имён системных карточек.

    Учитываются ID, встретившиеся в любом виде (заголовок, текст, frontmatter)
    во всех `.md` вне ``archive/``. Это множество — источник истины для
    классификатора при решении ``vault`` vs ``dangling``.
    """
    ids: set[str] = set()
    for mf in workspace.rglob("*.md"):
        if "archive" in mf.parts:
            continue
        try:
            text = mf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        ids.update(ID_RE.findall(text))
    # Системные карточки 00–14 — добавляем, если файл реально существует.
    for name in CARD_NAMES:
        if (workspace / f"{name}.md").exists():
            ids.add(name)
    return ids


def build_backlinks(
    workspace: Path,
    memory_dir: Path | None = None,
) -> tuple[dict[str, list[dict]], dict[str, str]]:
    """Собрать backlinks index + класс каждой цели.

    Возвращает:
      * ``backlinks`` — ``dict[target, list[{from, line, anchor?, via?}]]``.
      * ``classes``   — ``dict[target, class]`` (из link_classifier).

    Бэктик-обёрнутые плейсхолдеры отфильтровываются до парсинга wikilinks.
    """
    vault_ids = collect_ids(workspace)
    carry_over_index = build_carry_over_index(workspace)
    memory_index = build_memory_index(memory_dir)

    backlinks: dict[str, list[dict]] = defaultdict(list)
    classes: dict[str, str] = {}

    for mf in sorted(workspace.rglob("*.md")):
        if "archive" in mf.parts:
            continue
        if "_generated" in mf.parts:
            continue
        rel = mf.relative_to(workspace).as_posix()
        try:
            raw = mf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # КРИТИЧНО: сначала вырезаем `[[...]]`-плейсхолдеры в backticks.
        # Нарушение этого порядка возвращает висячие для всех шаблонных
        # примеров вида `[[pat-XXX]]`.
        text = strip_backticked(raw)
        for idx, line in enumerate(text.splitlines(), 1):
            for m in WIKILINK_RE.finditer(line):
                target, anchor = parse_target(m.group(1))
                cls = classify_target(
                    target, vault_ids, carry_over_index, memory_index,
                )
                # Для vault-таргетов с anchor-ом, который сам является
                # валидным ID — редиректим запись на него (исторический
                # хвост парсера: `[[02_patterns#pat-007]]` учитывается
                # как ссылка на `pat-007`, если он есть в vault).
                if cls == "dangling" and anchor:
                    anchor_cls = classify_target(
                        anchor, vault_ids, carry_over_index, memory_index,
                    )
                    if anchor_cls != "dangling":
                        backlinks[anchor].append({
                            "from": rel,
                            "anchor": anchor,
                            "line": idx,
                            "via": target,
                        })
                        classes[anchor] = anchor_cls
                        continue

                backlinks[target].append({
                    "from": rel,
                    "anchor": anchor,
                    "line": idx,
                })
                classes[target] = cls

    # Дедупликация записей в каждом списке.
    for k, arr in backlinks.items():
        seen = set()
        unique = []
        for e in arr:
            key = (e["from"], e.get("anchor"), e.get("via"), e["line"])
            if key not in seen:
                seen.add(key)
                unique.append(e)
        backlinks[k] = unique

    return backlinks, classes


# ---------------------------------------------------------------------------
# Рендер
# ---------------------------------------------------------------------------

# Порядок классов в отчёте и заголовки секций.
CLASS_SECTIONS: list[tuple[str, str]] = [
    ("vault", "## Обратные ссылки (vault → vault)"),
    ("plugin", "## Внешние ссылки на плагины"),
    ("agent", "## Системные агенты и команды"),
    ("carry_over", "## Carry-over документы"),
    ("memory", "## Memory-файлы"),
    ("dangling", "## Висячие ссылки (требуют внимания)"),
]

# Внутри vault — группировка по префиксу ID (как было в v1.3.7 и ранее).
VAULT_SUBGROUP_TITLES: dict[str, str] = {
    "pat-": "### Паттерны",
    "wm-": "### Механизмы",
    "ec-": "### Ошибки",
    "km-": "### Карты знаний",
    "md-": "### Мета-решения",
    "term-": "### Термины",
    "ent-": "### Сущности",
    "proj-": "### Проекты",
    "lesson-": "### Уроки",
    "sr-": "### Самоаудиты",
    "audit-": "### Аудиты",
    "domain-": "### Домены",
    "cluster-": "### Кластеры",
    "cards": "### Карточки",
}

VAULT_SUBGROUP_ORDER: list[str] = list(VAULT_SUBGROUP_TITLES.keys())


def _vault_subgroup(target: str) -> str:
    """Ключ подгруппы внутри секции ``vault``."""
    for pref in VAULT_SUBGROUP_ORDER:
        if pref == "cards":
            continue
        if target.startswith(pref):
            return pref
    if target in CARD_NAMES:
        return "cards"
    return "cards"


def _render_entry(entry: dict) -> str:
    """Одна строка списка ссылок."""
    via = f" (via `{entry['via']}`)" if entry.get("via") else ""
    anchor = f"#{entry['anchor']}" if entry.get("anchor") else ""
    # Anchor внутри via уже показан — не дублируем.
    if entry.get("via"):
        anchor = ""
    return f"- `{entry['from']}:{entry['line']}`{anchor}{via}"


def render(
    workspace: Path,
    backlinks: dict[str, list[dict]],
    classes: dict[str, str],
    mode: str = "full",
    id_filter: str | None = None,
) -> str:
    """Формирует backlinks.md как markdown-строку."""
    from datetime import date
    today = date.today().isoformat()
    lines = [f"# Обратные ссылки — {today}", ""]

    # --------------------- режим: только висячие ----------------------------
    if mode == "broken":
        lines.append("## Висячие ссылки")
        lines.append("")
        dangling_targets = sorted(
            [t for t, c in classes.items() if c == "dangling"]
        )
        if not dangling_targets:
            lines.append("_Висячих ссылок не обнаружено._")
        for t in dangling_targets:
            for e in backlinks[t]:
                anchor = f"#{e['anchor']}" if e.get("anchor") else ""
                lines.append(
                    f"- `{e['from']}:{e['line']}` → `[[{t}{anchor}]]` — **ВИСЯЧАЯ**"
                )
        return "\n".join(lines) + "\n"

    # --------------------- режим: изолированные -----------------------------
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

    # --------------------- режим: фильтр по одному ID -----------------------
    if id_filter:
        lines.append(f"## Обратные ссылки на `{id_filter}`")
        lines.append("")
        arr = backlinks.get(id_filter, [])
        if not arr:
            lines.append("_Нет входящих ссылок._")
        for e in arr:
            lines.append(_render_entry(e))
        return "\n".join(lines) + "\n"

    # --------------------- режим: полный отчёт (6 секций) -------------------
    # Сводка по классам — прямо под заголовком, чтобы видеть распределение.
    summary: dict[str, int] = defaultdict(int)
    for t, cls in classes.items():
        summary[cls] += len(backlinks[t])
    lines.append("## Сводка по классам")
    lines.append("")
    lines.append("| Класс | Целей | Ссылок |")
    lines.append("|---|---|---|")
    for cls, _title in CLASS_SECTIONS:
        n_targets = sum(1 for t in classes if classes[t] == cls)
        n_links = summary.get(cls, 0)
        lines.append(f"| {cls} | {n_targets} | {n_links} |")
    lines.append("")

    for cls, title in CLASS_SECTIONS:
        targets = sorted(t for t in classes if classes[t] == cls)
        lines.append(title)
        lines.append("")
        if not targets:
            lines.append("_Пусто._")
            lines.append("")
            continue

        # Секция vault — с подгруппами по префиксу ID.
        if cls == "vault":
            groups: dict[str, list[str]] = defaultdict(list)
            for t in targets:
                groups[_vault_subgroup(t)].append(t)
            for pref in VAULT_SUBGROUP_ORDER:
                ids_in_group = sorted(groups.get(pref, []))
                if not ids_in_group:
                    continue
                lines.append(VAULT_SUBGROUP_TITLES[pref])
                lines.append("")
                for t in ids_in_group:
                    lines.append(f"#### [[{t}]]")
                    for e in backlinks[t]:
                        lines.append(_render_entry(e))
                    lines.append("")
            continue

        # Секция dangling — чуть иной формат: показываем target прямо в строке.
        if cls == "dangling":
            for t in targets:
                for e in backlinks[t]:
                    anchor = f"#{e['anchor']}" if e.get("anchor") else ""
                    lines.append(
                        f"- `{e['from']}:{e['line']}` → `[[{t}{anchor}]]` — **ВИСЯЧАЯ**"
                    )
            lines.append("")
            continue

        # Остальные секции (plugin/agent/carry_over/memory) — плоский список.
        for t in targets:
            lines.append(f"### [[{t}]]")
            for e in backlinks[t]:
                lines.append(_render_entry(e))
            lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@safe_main
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Рендер backlinks когнитивного воркспейса.",
    )
    ap.add_argument("--workspace", required=True)
    ap.add_argument(
        "--memory-dir",
        help="Путь к auto-memory директории пользователя. "
             "Если не задан — скрипт пытается найти сам.",
    )
    ap.add_argument("--id", dest="id_filter", help="Только для одного ID")
    ap.add_argument("--broken", action="store_true", help="Только висячие")
    ap.add_argument("--orphans", action="store_true", help="Только изолированные")
    ap.add_argument(
        "--stdout", action="store_true",
        help="Не писать файл, вывод в stdout",
    )
    ap.add_argument(
        "--if-changed", action="store_true",
        help="Noop-флаг для hooks (скрипт идемпотентен).",
    )
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        print(f"Воркспейс не найден: {workspace}", file=sys.stderr)
        return 1

    if args.memory_dir:
        memory_dir: Path | None = Path(args.memory_dir).expanduser().resolve()
    else:
        memory_dir = find_default_memory_dir()

    backlinks, classes = build_backlinks(workspace, memory_dir=memory_dir)

    mode = "full"
    if args.broken:
        mode = "broken"
    elif args.orphans:
        mode = "orphans"

    content = render(
        workspace, backlinks, classes,
        mode=mode, id_filter=args.id_filter,
    )

    if args.stdout:
        print(content)
    else:
        out = workspace / "_generated" / "backlinks.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"Backlinks: {out}")

    dangling = sum(1 for c in classes.values() if c == "dangling")
    if dangling:
        print(
            f"ВНИМАНИЕ: найдено висячих ссылок (unique targets): {dangling}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    main()
