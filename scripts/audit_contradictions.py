#!/usr/bin/env python3
"""
audit_contradictions.py — парный поиск противоречий в воркспейсе.

Реализует шаги 3, 4, 5 скилла [[audit]]:
- knowledge_conflict (пары km-NNN с противоречивыми утверждениями).
- pattern_conflict (пары pat-NNN с несовместимыми триггерами/предписаниями).
- project_conflict (пары proj-NNN с общим доменом и противоположными целями).

Использует эвристики:
- Семантическая близость (пересечение ключевых терминов).
- Бинарные несоответствия (числа / противоположные слова).
- Overlap триггеров.

Запуск:
    python3 audit_contradictions.py --workspace /path
    python3 audit_contradictions.py --workspace . --only knowledge
    python3 audit_contradictions.py --workspace . --similarity-threshold 0.5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.error_handling import safe_main  # noqa: E402

KM_HEADER_RE = re.compile(r"^###\s+(km-\d{3})\s*[—-]\s*(.+?)$", re.MULTILINE)
PAT_HEADER_RE = re.compile(r"^###\s+(pat-\d{3})\s*[—-]\s*(.+?)$", re.MULTILINE)
PROJ_HEADER_RE = re.compile(r"^##\s+(proj-\d{3})\s*[—-]\s*(.+?)$", re.MULTILINE)

RU_STOPWORDS = {
    "и", "в", "на", "с", "для", "по", "из", "что", "как", "это", "или",
    "а", "но", "же", "то", "не", "да", "так", "бы", "у", "к", "от", "до",
    "чтобы", "если", "при", "через", "о", "об", "про", "над", "под",
}

# Антонимы для бинарного детектирования
ANTONYMS = [
    ("централизованный", "децентрализованный"),
    ("верно", "неверно"),
    ("обязательный", "опциональный"),
    ("разрешено", "запрещено"),
    ("включён", "выключен"),
    ("активный", "неактивный"),
    ("прошёл", "не прошёл"),
]

NUMBER_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\b")


@dataclass
class Record:
    id: str
    title: str
    content: str
    keywords: set[str] = field(default_factory=set)
    numbers: list[str] = field(default_factory=list)


@dataclass
class Conflict:
    type: str
    a_id: str
    b_id: str
    similarity: float
    evidence: list[str]
    severity: str = "medium"


def extract_keywords(text: str, top_n: int = 20) -> set[str]:
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"\[\[[^\]]+\]\]", "", text)
    words = re.findall(r"\b[а-яА-Яa-zA-Z][\w\-]{3,}\b", text.lower())
    words = [w for w in words if w not in RU_STOPWORDS]
    cnt = Counter(words)
    return {w for w, _ in cnt.most_common(top_n)}


def extract_numbers(text: str) -> list[str]:
    return NUMBER_RE.findall(text)


def parse_section(workspace: Path, filename: str, header_re: re.Pattern) -> list[Record]:
    f = workspace / filename
    if not f.exists():
        return []
    text = f.read_text(encoding="utf-8", errors="replace")
    records = []
    matches = list(header_re.finditer(text))
    for i, m in enumerate(matches):
        rid = m.group(1)
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        records.append(
            Record(
                id=rid,
                title=title,
                content=content,
                keywords=extract_keywords(content),
                numbers=extract_numbers(content),
            )
        )
    return records


def similarity(a: Record, b: Record) -> float:
    if not a.keywords or not b.keywords:
        return 0.0
    inter = len(a.keywords & b.keywords)
    union = len(a.keywords | b.keywords)
    return inter / union if union > 0 else 0.0


def detect_binary_conflicts(a: Record, b: Record) -> list[str]:
    """Ищет антонимы в парах утверждений."""
    evidence = []
    a_text = a.content.lower()
    b_text = b.content.lower()
    for word_a, word_b in ANTONYMS:
        if word_a in a_text and word_b in b_text:
            evidence.append(f"Антонимы: «{word_a}» в {a.id} vs «{word_b}» в {b.id}")
        elif word_b in a_text and word_a in b_text:
            evidence.append(f"Антонимы: «{word_b}» в {a.id} vs «{word_a}» в {b.id}")
    return evidence


def detect_number_mismatches(a: Record, b: Record) -> list[str]:
    """Ищет расхождения в числах при похожей формулировке."""
    if not a.numbers or not b.numbers:
        return []
    common_keywords = a.keywords & b.keywords
    if len(common_keywords) < 3:
        return []

    # Если у обоих одно число в схожем контексте — проверяем совпадение
    evidence = []
    a_nums = set(a.numbers)
    b_nums = set(b.numbers)
    # Числа, которые встречаются только в одном
    only_a = a_nums - b_nums
    only_b = b_nums - a_nums
    if only_a and only_b and len(a_nums) <= 3 and len(b_nums) <= 3:
        # Малое число цифр — вероятнее, что они характеризуют одно и то же
        evidence.append(
            f"Числовое расхождение: {a.id}={sorted(a_nums)} vs "
            f"{b.id}={sorted(b_nums)} (общие термины: "
            f"{', '.join(list(common_keywords)[:5])})"
        )
    return evidence


def find_conflicts(
    records: list[Record],
    record_type: str,
    similarity_threshold: float = 0.6,
) -> list[Conflict]:
    conflicts = []
    for a, b in combinations(records, 2):
        sim = similarity(a, b)
        if sim < similarity_threshold:
            continue

        evidence = []
        evidence.extend(detect_binary_conflicts(a, b))
        evidence.extend(detect_number_mismatches(a, b))

        if not evidence:
            continue

        # Severity: больше evidence + выше similarity → выше severity
        if len(evidence) >= 2 and sim >= 0.75:
            severity = "high"
        elif len(evidence) >= 2:
            severity = "medium"
        else:
            severity = "low"

        conflicts.append(
            Conflict(
                type=record_type,
                a_id=a.id,
                b_id=b.id,
                similarity=round(sim, 3),
                evidence=evidence,
                severity=severity,
            )
        )
    return conflicts


def render_report(
    all_conflicts: dict[str, list[Conflict]],
    stats: dict[str, int],
) -> str:
    today = date.today().isoformat()
    lines = [f"# Противоречия — {today}", ""]
    lines.append(f"**Всего противоречий:** {sum(len(v) for v in all_conflicts.values())}")
    lines.append("")

    # Summary
    lines.append("| Тип | Records | Conflicts |")
    lines.append("|---|---|---|")
    for t, c in all_conflicts.items():
        total_recs = stats.get(t, 0)
        lines.append(f"| {t} | {total_recs} | {len(c)} |")
    lines.append("")

    # Detail
    for t, conflicts in all_conflicts.items():
        if not conflicts:
            continue
        lines.append(f"## {t.capitalize()} conflicts")
        lines.append("")
        for c in sorted(conflicts, key=lambda x: ("high", "medium", "low").index(x.severity)):
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}[c.severity]
            lines.append(f"### {emoji} `{c.a_id}` ↔ `{c.b_id}` (sim={c.similarity})")
            lines.append("")
            lines.append(f"**Severity:** {c.severity}")
            lines.append("")
            lines.append("**Evidence:**")
            for e in c.evidence:
                lines.append(f"- {e}")
            lines.append("")
            lines.append(f"**Предложение:** создать `audit-NNN` типа `{t}_conflict`.")
            lines.append("")

    if sum(len(v) for v in all_conflicts.values()) == 0:
        lines.append("_Противоречий не обнаружено._")

    return "\n".join(lines) + "\n"


@safe_main
def main() -> int:
    ap = argparse.ArgumentParser(description="Поиск противоречий в воркспейсе.")
    ap.add_argument("--workspace", required=True)
    ap.add_argument(
        "--only",
        choices=["knowledge", "pattern", "project", "all"],
        default="all",
    )
    ap.add_argument("--similarity-threshold", type=float, default=0.6)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        print(f"Воркспейс не найден: {workspace}", file=sys.stderr)
        return 1

    all_conflicts: dict[str, list[Conflict]] = {}
    stats: dict[str, int] = {}

    if args.only in ("knowledge", "all"):
        kms = parse_section(workspace, "08_knowledge_maps.md", KM_HEADER_RE)
        stats["knowledge"] = len(kms)
        all_conflicts["knowledge"] = find_conflicts(kms, "knowledge", args.similarity_threshold)

    if args.only in ("pattern", "all"):
        pats = parse_section(workspace, "02_patterns.md", PAT_HEADER_RE)
        stats["pattern"] = len(pats)
        all_conflicts["pattern"] = find_conflicts(pats, "pattern", args.similarity_threshold)

    if args.only in ("project", "all"):
        projs = parse_section(workspace, "03_projects_registry.md", PROJ_HEADER_RE)
        stats["project"] = len(projs)
        all_conflicts["project"] = find_conflicts(projs, "project", args.similarity_threshold)

    if args.json:
        out = {
            "workspace": str(workspace),
            "generated": date.today().isoformat(),
            "stats": stats,
            "conflicts": {
                t: [
                    {
                        "type": c.type,
                        "a_id": c.a_id,
                        "b_id": c.b_id,
                        "similarity": c.similarity,
                        "severity": c.severity,
                        "evidence": c.evidence,
                    }
                    for c in clist
                ]
                for t, clist in all_conflicts.items()
            },
        }
        content = json.dumps(out, ensure_ascii=False, indent=2)
    else:
        content = render_report(all_conflicts, stats)

    if args.stdout:
        print(content)
    else:
        out_path = workspace / "_generated" / (
            "contradictions.json" if args.json else "contradictions_report.md"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"Отчёт: {out_path}")

    total = sum(len(v) for v in all_conflicts.values())
    if total > 0:
        print(f"⚠ Найдено противоречий: {total}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    main()
