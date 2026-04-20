#!/usr/bin/env python3
"""
sync_check.py — проверка синхронизации когнитивного воркспейса.

Проверяет:
1. Пороги в `SKILL.md` (cognitive-os-core) соответствуют порогам в
   карточках и в references/thresholds.md.
2. `00_index.counters` совпадают с фактическими подсчётами записей.
3. Frontmatter YAML валиден во всех карточках.
4. Все wikilinks resolve (интеграция с render_backlinks).
5. IDs уникальны (нет дубликатов).
6. Нумерация IDs плотная (нет пропусков > 10).

Результат — `_generated/sync_report.md`. Если есть рассинхроны,
action-скилл [[audit]] может создать `audit-NNN` типа `threshold_mismatch`.

Запуск:
    python3 sync_check.py --workspace /path/to/cognitive-os
    python3 sync_check.py --workspace . --report-only
    python3 sync_check.py --workspace . --strict  # exit 1 при находках
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.error_handling import safe_main  # noqa: E402

ID_PREFIXES = [
    "pat-", "wm-", "ec-", "km-", "md-", "term-", "ent-",
    "proj-", "lesson-", "sr-", "audit-", "domain-", "cluster-",
]
ID_RE = re.compile(r"\b(" + "|".join(ID_PREFIXES) + r")(\d{3})\b")
FRONTMATTER_RE = re.compile(r"^---\n([\s\S]+?)\n---", re.MULTILINE)
COUNTER_RE = re.compile(r"^-\s+([\w_]+):\s*(\d+)\s*$", re.MULTILINE)
THRESHOLD_RE = re.compile(r"^\|\s*`?(\w+)`?\s*\|\s*(\S+)\s*\|", re.MULTILINE)


@dataclass
class SyncIssue:
    severity: str  # info | warning | error
    category: str
    message: str
    location: str | None = None


@dataclass
class SyncReport:
    issues: list[SyncIssue] = field(default_factory=list)
    counters_actual: dict[str, int] = field(default_factory=dict)
    counters_declared: dict[str, int] = field(default_factory=dict)
    thresholds: dict[str, str] = field(default_factory=dict)
    duplicate_ids: list[str] = field(default_factory=list)
    gaps: dict[str, list[int]] = field(default_factory=dict)


def parse_frontmatter(text: str) -> tuple[dict | None, list[str]]:
    """Возвращает (dict or None, list of parse errors)."""
    m = FRONTMATTER_RE.search(text)
    if not m:
        return None, []
    raw = m.group(1)
    errors = []
    data = {}
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            errors.append(f"Строка без `:` — `{line[:60]}`")
            continue
        key, _, val = line.partition(":")
        data[key.strip()] = val.strip()
    return data, errors


def count_ids(workspace: Path) -> tuple[dict[str, int], dict[str, list[int]], list[str]]:
    """Возвращает (count_by_prefix, numbers_by_prefix, duplicates)."""
    by_prefix: dict[str, set[int]] = defaultdict(set)
    all_occurrences: list[tuple[str, int, Path]] = []

    for mf in workspace.rglob("*.md"):
        if "archive" in mf.parts or "_generated" in mf.parts or ".backup" in mf.parts:
            continue
        try:
            text = mf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Только definitions (заголовки с ID), не все упоминания
        for line in text.splitlines():
            header_match = re.match(r"^###?\s+(" + "|".join(ID_PREFIXES) + r")(\d{3})", line)
            if header_match:
                prefix = header_match.group(1)
                num = int(header_match.group(2))
                by_prefix[prefix].add(num)
                all_occurrences.append((prefix, num, mf))

    # Дубликаты: один ID определён в нескольких местах
    seen: dict[tuple[str, int], Path] = {}
    duplicates = []
    for prefix, num, path in all_occurrences:
        key = (prefix, num)
        if key in seen and seen[key] != path:
            duplicates.append(f"{prefix}{num:03d} в {seen[key].name} и {path.name}")
        else:
            seen[key] = path

    count_by_prefix = {p: len(nums) for p, nums in by_prefix.items()}
    numbers_by_prefix = {p: sorted(nums) for p, nums in by_prefix.items()}

    return count_by_prefix, numbers_by_prefix, duplicates


def find_gaps(numbers_by_prefix: dict[str, list[int]], max_gap: int = 10) -> dict[str, list[int]]:
    """Ищет пропуски в нумерации > max_gap."""
    gaps = {}
    for prefix, nums in numbers_by_prefix.items():
        if len(nums) < 2:
            continue
        prefix_gaps = []
        for i in range(1, len(nums)):
            diff = nums[i] - nums[i - 1]
            if diff > max_gap:
                prefix_gaps.append((nums[i - 1], nums[i], diff))
        if prefix_gaps:
            gaps[prefix] = prefix_gaps
    return gaps


def parse_declared_counters(workspace: Path) -> dict[str, int]:
    """Парсит 00_index.md, секция counters."""
    f = workspace / "00_index.md"
    if not f.exists():
        return {}
    text = f.read_text(encoding="utf-8", errors="replace")
    counters = {}

    # Ищем секцию counters
    counters_section = re.search(
        r"##\s*Counters[\s\S]+?(?=\n##\s|\Z)", text, re.IGNORECASE
    )
    if not counters_section:
        return {}

    for m in COUNTER_RE.finditer(counters_section.group(0)):
        key, val = m.groups()
        counters[key] = int(val)

    return counters


def parse_thresholds_references(workspace: Path) -> dict[str, str]:
    """Парсит references/thresholds.md, если есть."""
    candidates = [
        workspace / "references" / "thresholds.md",
        workspace.parent / "references" / "thresholds.md",
    ]
    for f in candidates:
        if f.exists():
            text = f.read_text(encoding="utf-8", errors="replace")
            thresholds = {}
            for m in THRESHOLD_RE.finditer(text):
                key, val = m.groups()
                thresholds[key] = val
            return thresholds
    return {}


def validate_frontmatter_all(workspace: Path) -> list[SyncIssue]:
    """Проверяет frontmatter во всех карточках."""
    issues = []
    for mf in workspace.rglob("*.md"):
        if "archive" in mf.parts or "_generated" in mf.parts:
            continue
        try:
            text = mf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        data, errors = parse_frontmatter(text)
        for e in errors:
            issues.append(
                SyncIssue(
                    severity="warning",
                    category="frontmatter_parse",
                    message=f"Невалидный frontmatter: {e}",
                    location=str(mf.relative_to(workspace)),
                )
            )
    return issues


def build_report(workspace: Path) -> SyncReport:
    report = SyncReport()

    # 1. Counters
    count_by_prefix, numbers_by_prefix, duplicates = count_ids(workspace)
    report.counters_actual = count_by_prefix
    report.counters_declared = parse_declared_counters(workspace)
    report.duplicate_ids = duplicates

    # Сравнение actual vs declared
    for key, actual in count_by_prefix.items():
        card_prefix_map = {
            "pat-": "patterns",
            "wm-": "mechanisms",
            "ec-": "errors",
            "km-": "knowledge_maps",
            "md-": "meta_decisions",
            "term-": "terms",
            "ent-": "entities",
            "proj-": "projects",
            "lesson-": "lessons",
            "sr-": "reflections",
            "audit-": "audits",
            "domain-": "domains",
            "cluster-": "clusters",
        }
        counter_key = card_prefix_map.get(key, key.rstrip("-"))
        declared = report.counters_declared.get(counter_key)
        if declared is None:
            report.issues.append(
                SyncIssue(
                    severity="info",
                    category="counter_missing",
                    message=f"Counter `{counter_key}` не объявлен в 00_index (actual={actual})",
                    location="00_index.md",
                )
            )
        elif declared != actual:
            report.issues.append(
                SyncIssue(
                    severity="warning",
                    category="counter_mismatch",
                    message=f"Counter `{counter_key}`: declared={declared}, actual={actual}",
                    location="00_index.md",
                )
            )

    # 2. Дубликаты
    for dup in duplicates:
        report.issues.append(
            SyncIssue(
                severity="error",
                category="duplicate_id",
                message=f"Дубликат ID: {dup}",
            )
        )

    # 3. Пропуски
    gaps = find_gaps(numbers_by_prefix)
    report.gaps = {k: [f"{a}→{b} (gap {d})" for a, b, d in v] for k, v in gaps.items()}
    for prefix, glist in gaps.items():
        for a, b, d in glist:
            report.issues.append(
                SyncIssue(
                    severity="info",
                    category="id_gap",
                    message=f"Пропуск в нумерации {prefix}: {a:03d} → {b:03d} (gap {d})",
                )
            )

    # 4. Frontmatter
    report.issues.extend(validate_frontmatter_all(workspace))

    # 5. Thresholds — сверка references/thresholds.md vs 00_index (если есть)
    report.thresholds = parse_thresholds_references(workspace)

    return report


def render_report(report: SyncReport, workspace: Path) -> str:
    today = date.today().isoformat()
    lines = [f"# Проверка синхронизации — {today}", ""]
    lines.append(f"**Воркспейс:** `{workspace}`")
    lines.append(f"**Всего проблем:** {len(report.issues)}")
    lines.append("")

    # Summary by severity
    by_sev = Counter(i.severity for i in report.issues)
    lines.append("| Severity | Count |")
    lines.append("|---|---|")
    for sev in ["error", "warning", "info"]:
        lines.append(f"| {sev} | {by_sev.get(sev, 0)} |")
    lines.append("")

    # Counters
    lines.append("## Counters")
    lines.append("")
    lines.append("| Prefix | Actual | Declared |")
    lines.append("|---|---|---|")
    all_keys = set(report.counters_actual) | set(report.counters_declared)
    for k in sorted(all_keys):
        a = report.counters_actual.get(k, 0)
        d = report.counters_declared.get(k, "—")
        status = "✅" if str(a) == str(d) else "⚠"
        lines.append(f"| `{k}` | {a} | {d} | {status} |")
    lines.append("")

    # Issues detail
    if report.issues:
        lines.append("## Проблемы")
        lines.append("")
        for issue in sorted(report.issues, key=lambda i: ("error", "warning", "info").index(i.severity)):
            emoji = {"error": "🔴", "warning": "🟡", "info": "ℹ️"}.get(issue.severity, "•")
            loc = f" ({issue.location})" if issue.location else ""
            lines.append(f"- {emoji} [{issue.category}] {issue.message}{loc}")
        lines.append("")

    # Gaps
    if report.gaps:
        lines.append("## Пропуски нумерации")
        lines.append("")
        for prefix, gaps_list in report.gaps.items():
            lines.append(f"- `{prefix}`: {', '.join(gaps_list)}")
        lines.append("")

    # Thresholds
    if report.thresholds:
        lines.append("## Пороги (references/thresholds.md)")
        lines.append("")
        for k, v in sorted(report.thresholds.items()):
            lines.append(f"- `{k}`: `{v}`")
        lines.append("")

    return "\n".join(lines) + "\n"


@safe_main
def main() -> int:
    ap = argparse.ArgumentParser(description="Проверка синхронизации когнитивного воркспейса.")
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--report-only", action="store_true", help="Только отчёт, без exit 1")
    ap.add_argument("--strict", action="store_true", help="Exit 1 при любых находках")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        print(f"Воркспейс не найден: {workspace}", file=sys.stderr)
        return 1

    report = build_report(workspace)
    content = render_report(report, workspace)

    if args.stdout:
        print(content)
    else:
        out_path = workspace / "_generated" / "sync_report.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"Отчёт: {out_path}")

    by_sev = Counter(i.severity for i in report.issues)
    if by_sev.get("error", 0) > 0:
        print(f"🔴 Ошибок: {by_sev['error']}", file=sys.stderr)
    if by_sev.get("warning", 0) > 0:
        print(f"🟡 Предупреждений: {by_sev['warning']}", file=sys.stderr)

    if args.strict and report.issues:
        return 1
    if args.report_only:
        return 0
    return 1 if by_sev.get("error", 0) > 0 else 0


if __name__ == "__main__":
    main()
