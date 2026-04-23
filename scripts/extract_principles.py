#!/usr/bin/env python3
"""
extract_principles.py — извлечение кандидатов в принципы (md-NNN) из
часто применяемых механизмов (wm-NNN).

Логика:
1. Собрать все wm-NNN из 09_working_mechanisms.md.
2. Для каждого посчитать `applied_count` (число упоминаний в other
   карточках + в проектах).
3. Отсортировать, взять топ по `applied_count ≥ threshold`.
4. Кластеризовать по семантической близости (общие ключевые термины).
5. Для каждого кластера выдать кандидат в md-NNN.

Не создаёт md-NNN сам — только выдаёт кандидатов для [[patterns]] в
режиме promotion.

Запуск:
    python3 extract_principles.py --workspace /path/to/cognitive_os
    python3 extract_principles.py --workspace . --min-applied 5
    python3 extract_principles.py --workspace . --stdout
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parent))
from lib.error_handling import safe_main  # noqa: E402
from datetime import date
from pathlib import Path

WM_ID_RE = re.compile(r"\b(wm-\d{3})\b")
WM_HEADER_RE = re.compile(r"^###\s+(wm-\d{3})\s*[—-]\s*(.+?)$", re.MULTILINE)
TAGS_RE = re.compile(r"\btags?:\s*\[([^\]]+)\]", re.IGNORECASE)
DOMAIN_RE = re.compile(r"\bdomain:\s*([\w\-_]+)", re.IGNORECASE)

RU_STOPWORDS = {
    "и", "в", "на", "с", "для", "по", "из", "что", "как", "это", "или",
    "а", "но", "же", "то", "не", "да", "так", "бы", "у", "к", "от", "до",
    "чтобы", "если", "при", "через", "о", "об", "про",
}


@dataclass
class Mechanism:
    id: str
    title: str
    content: str
    applied_count: int = 0
    tags: list[str] = field(default_factory=list)
    domain: str | None = None
    keywords: set[str] = field(default_factory=set)


def extract_keywords(text: str, top_n: int = 10) -> set[str]:
    """Примитивное извлечение ключевых терминов по частоте."""
    # Убираем ссылки, код, frontmatter
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"\[\[[^\]]+\]\]", "", text)
    text = re.sub(r"---[\s\S]*?---", "", text, count=1)
    # Слова 4+ символа
    words = re.findall(r"\b[а-яА-Яa-zA-Z][\w\-]{3,}\b", text.lower())
    words = [w for w in words if w not in RU_STOPWORDS]
    cnt = Counter(words)
    return {w for w, _ in cnt.most_common(top_n)}


def parse_wm_card(workspace: Path) -> dict[str, Mechanism]:
    """Извлекает все wm-NNN из 09_working_mechanisms.md."""
    f = workspace / "09_working_mechanisms.md"
    if not f.exists():
        return {}

    text = f.read_text(encoding="utf-8", errors="replace")
    mechanisms = {}

    # Режем по заголовкам wm-NNN
    matches = list(WM_HEADER_RE.finditer(text))
    for i, m in enumerate(matches):
        mid = m.group(1)
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        tags: list[str] = []
        tm = TAGS_RE.search(content)
        if tm:
            tags = [t.strip().strip('"').strip("'") for t in tm.group(1).split(",")]

        domain = None
        dm = DOMAIN_RE.search(content)
        if dm:
            domain = dm.group(1).strip()

        mechanisms[mid] = Mechanism(
            id=mid,
            title=title,
            content=content,
            tags=tags,
            domain=domain,
            keywords=extract_keywords(content),
        )

    return mechanisms


def count_applications(workspace: Path, mechanisms: dict[str, Mechanism]) -> None:
    """Считает applied_count для каждого wm-NNN через упоминания."""
    for mf in workspace.rglob("*.md"):
        if "archive" in mf.parts or "_generated" in mf.parts:
            continue
        if mf.name == "09_working_mechanisms.md":
            continue  # не считаем упоминания внутри самого файла-источника
        try:
            text = mf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for mid in WM_ID_RE.findall(text):
            if mid in mechanisms:
                mechanisms[mid].applied_count += 1


def cluster_mechanisms(
    mechanisms: list[Mechanism],
    min_keyword_overlap: int = 3,
) -> list[list[Mechanism]]:
    """Простая кластеризация по пересечению ключевых слов."""
    clusters: list[list[Mechanism]] = []
    used: set[str] = set()

    for m in mechanisms:
        if m.id in used:
            continue
        cluster = [m]
        used.add(m.id)
        for other in mechanisms:
            if other.id in used:
                continue
            overlap = len(m.keywords & other.keywords)
            if overlap >= min_keyword_overlap:
                cluster.append(other)
                used.add(other.id)
        clusters.append(cluster)

    # Оставляем только кластеры из 2+ механизмов (потенциальные принципы)
    return [c for c in clusters if len(c) >= 2]


def generate_principle_candidates(clusters: list[list[Mechanism]]) -> list[dict]:
    """Для каждого кластера — кандидат в принцип."""
    candidates = []
    for i, cluster in enumerate(clusters, 1):
        total_applications = sum(m.applied_count for m in cluster)
        shared_keywords = set.intersection(*(m.keywords for m in cluster))
        shared_domains = {m.domain for m in cluster if m.domain}

        candidates.append(
            {
                "candidate_id": f"md-candidate-{i:03d}",
                "source_mechanisms": [m.id for m in cluster],
                "source_titles": [m.title for m in cluster],
                "total_applications": total_applications,
                "shared_keywords": sorted(shared_keywords),
                "shared_domains": sorted(shared_domains),
                "suggested_working_title": (
                    " / ".join(list(shared_keywords)[:3])
                    if shared_keywords
                    else "TBD"
                ),
                "confidence": min(1.0, total_applications / 20.0),  # эвристика
            }
        )

    return sorted(candidates, key=lambda c: -c["total_applications"])


def render_report(
    mechanisms: dict[str, Mechanism],
    candidates: list[dict],
    min_applied: int,
) -> str:
    """Markdown-отчёт."""
    today = date.today().isoformat()
    lines = [f"# Кандидаты в принципы (md-NNN) — {today}", ""]
    lines.append(f"**Всего механизмов:** {len(mechanisms)}")
    lines.append(f"**Порог применений:** {min_applied}")
    lines.append(f"**Кластеров-кандидатов:** {len(candidates)}")
    lines.append("")

    # Топ применяемых
    top = sorted(mechanisms.values(), key=lambda m: -m.applied_count)[:10]
    lines.append("## Топ-10 по применимости")
    lines.append("")
    lines.append("| ID | Title | applied_count |")
    lines.append("|---|---|---|")
    for m in top:
        lines.append(f"| `{m.id}` | {m.title} | {m.applied_count} |")
    lines.append("")

    # Кандидаты
    lines.append("## Кандидаты в md-NNN")
    lines.append("")
    if not candidates:
        lines.append("_Нет. Для принципа нужен кластер из 2+ механизмов с перекрытием ключевых терминов._")
        return "\n".join(lines) + "\n"

    for c in candidates:
        lines.append(f"### {c['candidate_id']}: {c['suggested_working_title']}")
        lines.append("")
        lines.append(f"- **Источники:** {', '.join('`' + s + '`' for s in c['source_mechanisms'])}")
        lines.append(f"- **Применений суммарно:** {c['total_applications']}")
        lines.append(f"- **Общие термины:** {', '.join(c['shared_keywords'][:8]) or '—'}")
        lines.append(f"- **Домены:** {', '.join(c['shared_domains']) or '—'}")
        lines.append(f"- **Confidence:** {c['confidence']:.2f}")
        lines.append("")
        lines.append("**Источник-заголовки:**")
        for title in c["source_titles"]:
            lines.append(f"  - {title}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Для промоушена кандидата в md-NNN — запустить [[patterns]] в режиме `promote_to_principle`.")
    return "\n".join(lines) + "\n"


@safe_main
def main() -> int:
    ap = argparse.ArgumentParser(description="Извлечение кандидатов в принципы.")
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--min-applied", type=int, default=3)
    ap.add_argument("--min-overlap", type=int, default=3,
                    help="Минимум общих ключевых слов для кластера")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        print(f"Воркспейс не найден: {workspace}", file=sys.stderr)
        return 1

    mechanisms = parse_wm_card(workspace)
    if not mechanisms:
        print("Нет механизмов (09_working_mechanisms.md пусто или отсутствует).", file=sys.stderr)
        return 0

    count_applications(workspace, mechanisms)

    # Фильтр по минимуму применений
    active = [m for m in mechanisms.values() if m.applied_count >= args.min_applied]
    clusters = cluster_mechanisms(active, min_keyword_overlap=args.min_overlap)
    candidates = generate_principle_candidates(clusters)

    if args.json:
        content = json.dumps(
            {
                "workspace": str(workspace),
                "generated": date.today().isoformat(),
                "min_applied": args.min_applied,
                "candidates": candidates,
            },
            ensure_ascii=False,
            indent=2,
        )
    else:
        content = render_report(mechanisms, candidates, args.min_applied)

    if args.stdout:
        print(content)
    else:
        out_path = workspace / "_generated" / (
            "principle_candidates.json" if args.json else "principle_candidates.md"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"Отчёт: {out_path}")

    print(f"Механизмов: {len(mechanisms)} · Активных: {len(active)} · Кандидатов: {len(candidates)}")
    return 0


if __name__ == "__main__":
    main()
