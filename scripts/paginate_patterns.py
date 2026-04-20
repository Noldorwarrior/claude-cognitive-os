#!/usr/bin/env python3
"""
paginate_patterns.py — разбивает 02_patterns.md по группам, когда число
паттернов превышает порог (default 200).

Стратегии группировки:
- `by-domain` (default): группируем по полю `domain:` во frontmatter паттерна.
- `by-tag`: по первому тегу.
- `by-range`: по диапазонам ID (pat-001..050, pat-051..100...).

Запуск:
    python3 paginate_patterns.py --workspace /path --strategy by-domain
    python3 paginate_patterns.py --workspace /path --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.error_handling import safe_main  # noqa: E402

PAT_HEADER_RE = re.compile(r"^###\s+(pat-\d{3})\s*[—-]\s*(.+?)$", re.MULTILINE)
DOMAIN_RE = re.compile(r"^-?\s*domain:\s*([\w\-_]+)", re.MULTILINE)
TAGS_RE = re.compile(r"^-?\s*tags?:\s*\[([^\]]+)\]", re.MULTILINE)


def split_patterns(text: str) -> tuple[str, list[dict]]:
    """Возвращает (preamble, [{id, title, content, domain, tags}])."""
    matches = list(PAT_HEADER_RE.finditer(text))
    if not matches:
        return text, []

    preamble = text[: matches[0].start()]
    patterns = []
    for i, m in enumerate(matches):
        pid = m.group(1)
        title = m.group(2).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].rstrip() + "\n"

        domain_m = DOMAIN_RE.search(content)
        domain = domain_m.group(1).strip() if domain_m else "uncategorized"

        tags_m = TAGS_RE.search(content)
        tags = []
        if tags_m:
            tags = [t.strip().strip('"').strip("'") for t in tags_m.group(1).split(",")]

        patterns.append({
            "id": pid,
            "title": title,
            "content": content,
            "domain": domain,
            "tags": tags,
        })
    return preamble, patterns


def group_by_domain(patterns: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for p in patterns:
        groups[p["domain"]].append(p)
    return groups


def group_by_tag(patterns: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for p in patterns:
        key = p["tags"][0] if p["tags"] else "no_tag"
        groups[key].append(p)
    return groups


def group_by_range(patterns: list[dict], size: int = 50) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for p in patterns:
        num = int(p["id"].split("-")[1])
        bucket_start = ((num - 1) // size) * size + 1
        bucket_end = bucket_start + size - 1
        key = f"pat-{bucket_start:03d}-{bucket_end:03d}"
        groups[key].append(p)
    return groups


def render_group_page(
    group_name: str,
    patterns: list[dict],
    total_groups: int,
) -> str:
    today = date.today().isoformat()
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]+", "_", group_name).lower()
    lines = [
        "---",
        f"group: {group_name}",
        f"total_in_group: {len(patterns)}",
        f"generated: {today}",
        f"type: patterns_group",
        "---",
        "",
        f"# Паттерны — группа «{group_name}»",
        "",
        f"**Всего в группе:** {len(patterns)}",
        f"**Родительский индекс:** [[02_patterns]]",
        "",
    ]
    for p in patterns:
        lines.append(p["content"])
    return "\n".join(lines)


def render_index(
    preamble: str,
    groups: dict[str, list[dict]],
    strategy: str,
    total: int,
) -> str:
    today = date.today().isoformat()
    lines = [preamble.rstrip(), ""]
    lines.append(f"## Индекс паттернов ({strategy})")
    lines.append("")
    lines.append(f"**Всего паттернов:** {total}")
    lines.append(f"**Групп:** {len(groups)}")
    lines.append(f"**Стратегия:** `{strategy}`")
    lines.append(f"**Обновлено:** {today}")
    lines.append("")

    lines.append("### По группам")
    lines.append("")
    for group_name in sorted(groups.keys()):
        patterns = groups[group_name]
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]+", "_", group_name).lower()
        lines.append(
            f"- [[patterns_groups/patterns_{safe_name}|{group_name}]] "
            f"({len(patterns)} паттернов)"
        )
    lines.append("")

    lines.append("### Полный алфавитный список")
    lines.append("")
    all_pats = [p for pats in groups.values() for p in pats]
    for p in sorted(all_pats, key=lambda x: x["id"]):
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]+", "_", p["domain"]).lower()
        lines.append(
            f"- `{p['id']}` {p['title']} → "
            f"[[patterns_groups/patterns_{safe_name}#{p['id']}]]"
        )
    lines.append("")

    return "\n".join(lines) + "\n"


@safe_main
def main() -> int:
    ap = argparse.ArgumentParser(description="Пагинация 02_patterns.md.")
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--strategy", choices=["by-domain", "by-tag", "by-range"],
                    default="by-domain")
    ap.add_argument("--threshold", type=int, default=200)
    ap.add_argument("--range-size", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        print(f"Воркспейс не найден: {workspace}", file=sys.stderr)
        return 1

    f = workspace / "02_patterns.md"
    if not f.exists():
        print(f"Файл не найден: {f}", file=sys.stderr)
        return 1

    text = f.read_text(encoding="utf-8", errors="replace")
    preamble, patterns = split_patterns(text)

    if len(patterns) < args.threshold:
        print(
            f"Паттернов {len(patterns)} < порога {args.threshold}. Пагинация не нужна.",
            file=sys.stderr,
        )
        return 0

    if args.strategy == "by-domain":
        groups = group_by_domain(patterns)
    elif args.strategy == "by-tag":
        groups = group_by_tag(patterns)
    else:
        groups = group_by_range(patterns, size=args.range_size)

    if args.dry_run:
        print(f"[dry-run] Стратегия: {args.strategy}")
        print(f"[dry-run] Всего паттернов: {len(patterns)}")
        print(f"[dry-run] Групп: {len(groups)}")
        for g, pats in sorted(groups.items()):
            print(f"  - {g}: {len(pats)} паттернов")
        return 0

    # Бэкап
    backup_dir = workspace / "archive" / ".backup" / date.today().isoformat()
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "02_patterns.md").write_text(text, encoding="utf-8")
    print(f"Бэкап: {backup_dir}")

    # Пишем группы
    groups_dir = workspace / "patterns_groups"
    groups_dir.mkdir(exist_ok=True)
    for group_name, pats in groups.items():
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]+", "_", group_name).lower()
        page = render_group_page(group_name, pats, len(groups))
        (groups_dir / f"patterns_{safe_name}.md").write_text(page, encoding="utf-8")
        print(f"Группа {group_name}: {len(pats)}")

    # Перезаписываем 02_patterns.md как index
    new_index = render_index(preamble, groups, args.strategy, len(patterns))
    f.write_text(new_index, encoding="utf-8")
    print(f"Index: {f}")

    print(f"\nГотово. Паттернов: {len(patterns)}, групп: {len(groups)}.")
    return 0


if __name__ == "__main__":
    main()
