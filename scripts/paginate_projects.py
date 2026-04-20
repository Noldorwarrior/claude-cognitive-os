#!/usr/bin/env python3
"""
paginate_projects.py — разбивает 03_projects_registry.md на страницы,
когда число проектов превышает порог (default 100).

Стратегия:
- Оставляет `03_projects_registry.md` как index со списком ссылок.
- Проекты переносит в `projects_pages/projects_001.md`, `projects_002.md`
  и т.д. по 50 проектов на страницу (default).
- Сохраняет все wikilinks рабочими через stub-ссылки.

Запуск:
    python3 paginate_projects.py --workspace /path --projects-per-page 50
    python3 paginate_projects.py --workspace /path --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.error_handling import safe_main  # noqa: E402

PROJ_HEADER_RE = re.compile(r"^##\s+(proj-\d{3})\s*[—-]\s*(.+?)$", re.MULTILINE)
# level-2 заголовок — проект; level-3 — детали внутри.


def split_projects(text: str) -> tuple[str, list[tuple[str, str, str]]]:
    """
    Возвращает (preamble, [(proj_id, title, content)]).
    `preamble` — всё до первого ## proj-NNN.
    """
    matches = list(PROJ_HEADER_RE.finditer(text))
    if not matches:
        return text, []

    preamble = text[: matches[0].start()]
    projects = []
    for i, m in enumerate(matches):
        proj_id = m.group(1)
        title = m.group(2).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].rstrip() + "\n"
        projects.append((proj_id, title, content))
    return preamble, projects


def render_page(
    page_num: int,
    total_pages: int,
    projects: list[tuple[str, str, str]],
    workspace_name: str,
) -> str:
    today = date.today().isoformat()
    lines = [
        "---",
        f"page: {page_num}",
        f"total_pages: {total_pages}",
        f"generated: {today}",
        f"type: projects_page",
        "---",
        "",
        f"# Проекты — страница {page_num} из {total_pages}",
        "",
        f"Навигация: [[03_projects_registry]] ← ",
    ]
    if page_num > 1:
        lines[-1] += f"[[projects_pages/projects_{page_num-1:03d}]] | "
    if page_num < total_pages:
        lines[-1] += f"[[projects_pages/projects_{page_num+1:03d}]] →"
    lines.append("")
    for proj_id, title, content in projects:
        lines.append(content)
    return "\n".join(lines)


def render_index(
    preamble: str,
    all_projects: list[tuple[str, str, str]],
    pages: list[list[tuple[str, str, str]]],
) -> str:
    today = date.today().isoformat()
    lines = [preamble.rstrip(), "", "## Индекс проектов", ""]
    lines.append(f"**Всего проектов:** {len(all_projects)}")
    lines.append(f"**Страниц:** {len(pages)}")
    lines.append(f"**Обновлено:** {today}")
    lines.append("")

    lines.append("### По страницам")
    lines.append("")
    for i, page_projects in enumerate(pages, 1):
        first_id = page_projects[0][0]
        last_id = page_projects[-1][0]
        lines.append(
            f"- [[projects_pages/projects_{i:03d}|Страница {i}]] — "
            f"{first_id}...{last_id} ({len(page_projects)} проектов)"
        )
    lines.append("")

    lines.append("### Алфавитный список")
    lines.append("")
    for proj_id, title, _ in sorted(all_projects, key=lambda p: p[0]):
        # Находим, в какую страницу попал
        page_num = next(
            i
            for i, pg in enumerate(pages, 1)
            if any(p[0] == proj_id for p in pg)
        )
        lines.append(f"- `{proj_id}` {title} → [[projects_pages/projects_{page_num:03d}#{proj_id}]]")
    lines.append("")

    return "\n".join(lines) + "\n"


@safe_main
def main() -> int:
    ap = argparse.ArgumentParser(description="Пагинация 03_projects_registry.md.")
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--projects-per-page", type=int, default=50)
    ap.add_argument("--threshold", type=int, default=100,
                    help="Минимум проектов для запуска пагинации")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        print(f"Воркспейс не найден: {workspace}", file=sys.stderr)
        return 1

    registry = workspace / "03_projects_registry.md"
    if not registry.exists():
        print(f"Файл не найден: {registry}", file=sys.stderr)
        return 1

    text = registry.read_text(encoding="utf-8", errors="replace")
    preamble, projects = split_projects(text)

    if len(projects) < args.threshold:
        print(
            f"Проектов {len(projects)} < порога {args.threshold}. Пагинация не нужна.",
            file=sys.stderr,
        )
        return 0

    # Разбиваем на страницы
    per_page = args.projects_per_page
    pages = [projects[i : i + per_page] for i in range(0, len(projects), per_page)]

    if args.dry_run:
        print(f"[dry-run] Всего проектов: {len(projects)}")
        print(f"[dry-run] Будет создано страниц: {len(pages)}")
        for i, pg in enumerate(pages, 1):
            print(f"  - Страница {i}: {pg[0][0]}...{pg[-1][0]} ({len(pg)} проектов)")
        return 0

    # Бэкап
    backup_dir = workspace / "archive" / ".backup" / date.today().isoformat()
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "03_projects_registry.md").write_text(text, encoding="utf-8")
    print(f"Бэкап: {backup_dir}")

    # Пишем страницы
    pages_dir = workspace / "projects_pages"
    pages_dir.mkdir(exist_ok=True)
    for i, page_projects in enumerate(pages, 1):
        page_content = render_page(i, len(pages), page_projects, workspace.name)
        (pages_dir / f"projects_{i:03d}.md").write_text(page_content, encoding="utf-8")
        print(f"Страница {i}: {len(page_projects)} проектов")

    # Перезаписываем реестр как index
    new_registry = render_index(preamble, projects, pages)
    registry.write_text(new_registry, encoding="utf-8")
    print(f"Index: {registry}")

    print(f"\nГотово. Проектов: {len(projects)}, страниц: {len(pages)}.")
    print("Запустите sync_check.py и render_backlinks.py для валидации ссылок.")
    return 0


if __name__ == "__main__":
    main()
