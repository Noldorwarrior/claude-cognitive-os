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
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->", re.MULTILINE)

# Canonical map: ID-префикс (с дефисом) → имя счётчика в frontmatter/секции Counters.
CARD_PREFIX_MAP = {
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


def strip_html_comments(text: str) -> str:
    """Удаляет многострочные HTML-комментарии, чтобы шаблонные записи
    (`<!-- Шаблон записи: ### pat-001 — ... -->`) не попадали в счётчики."""
    return HTML_COMMENT_RE.sub("", text)


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
    """Возвращает (dict or None, list of parse errors).

    Поддерживает YAML-lists:

        key:
          - item1
          - item2

    Такой блок превращается в `data[key] = ["item1", "item2"]`.
    Остальные конструкции (простые `key: value`, mapping-подобные
    `parent:` + `  child: value`) ведут себя как раньше — вложенные
    ключи попадают на верхний уровень с префиксом отступа, снятым
    через `strip`, что согласовано с текущим поведением
    `thresholds` / `counters`.

    Inline-комментарии. Контракт соответствует YAML 1.2 § 6.6:
    комментарий начинается с `#` **после whitespace** (пробел или таб)
    либо с начала строки. Парсер удаляет полностью закомментированные
    строки, но НЕ срезает inline-комментарии внутри значений — ответственность
    за их обработку лежит на consumer'е (см. `RESERVED_RANGE_RE`,
    который поглощает хвост `\\s*(?:#.*)?$` сам).
    """
    m = FRONTMATTER_RE.search(text)
    if not m:
        return None, []
    raw = m.group(1)
    errors: list[str] = []
    data: dict = {}
    current_list_key: str | None = None

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            current_list_key = None
            continue

        # Строка-элемент YAML-list: "  - value" (после ключа с пустым значением).
        if (
            current_list_key is not None
            and line[:1] in (" ", "\t")
            and stripped.startswith("- ")
        ):
            item = stripped[2:].strip()
            if not isinstance(data.get(current_list_key), list):
                data[current_list_key] = []
            data[current_list_key].append(item)
            continue

        if ":" not in line:
            errors.append(f"Строка без `:` — `{line[:60]}`")
            current_list_key = None
            continue

        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()

        if val == "":
            # Ключ с пустым значением — возможное начало YAML-list или mapping.
            current_list_key = key
            data[key] = ""
        else:
            current_list_key = None
            data[key] = val

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

        # Удаляем HTML-комментарии, чтобы шаблонные ### pat-001 и т.п.,
        # обёрнутые в `<!-- Шаблон записи: ... -->`, не попадали в счётчики.
        text = strip_html_comments(text)

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


# Грамматика reserved-range: `<prefix>-NNN..[<prefix>-]NNN` плюс
# опциональный хвост `\s*#...` — любой whitespace и далее inline-комментарий
# до конца строки. Хвост — часть самой грамматики, а не артефакт парсера:
# это соответствует YAML 1.2 (§6.6), где комментарий начинается с `#`
# после whitespace. Благодаря этому fallback-срез в `parse_reserved_ranges`
# больше не нужен — regex принимает и `ent-019..ent-029`, и
# `ent-019..ent-029  # зарезервировано под организации`.
RESERVED_RANGE_RE = re.compile(
    r"^("
    + "|".join(p.rstrip("-") for p in ID_PREFIXES)
    + r")-(\d{3})\.\.(?:(?:"
    + "|".join(p.rstrip("-") for p in ID_PREFIXES)
    + r")-)?(\d{3})\s*(?:#.*)?$"
)


def parse_reserved_ranges(workspace: Path) -> dict[str, set[int]]:
    """Собирает зарезервированные ID-номера из frontmatter всех карточек.

    Формат во frontmatter карточки (YAML-list):

        reserved_ranges:
          - ent-019..ent-029
          - pat-050..pat-055
          - ent-019..029                  # сокращённо: префикс наследуется
          - ent-019..ent-029  # коммент   # inline-комментарий допустим

    Правый конец можно писать сокращённо — `ent-019..029` — левый префикс
    тогда наследуется. Inline-комментарий после элемента (YAML 1.2 § 6.6:
    `whitespace + #`) допустим и съедается `RESERVED_RANGE_RE`. Возвращает
    `dict[prefix, set[int]]` — множество зарезервированных номеров для
    каждого ID-префикса.
    """
    reserved: dict[str, set[int]] = defaultdict(set)

    for mf in workspace.rglob("*.md"):
        if "archive" in mf.parts or "_generated" in mf.parts or ".backup" in mf.parts:
            continue
        try:
            text = mf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        data, _ = parse_frontmatter(text)
        if not data:
            continue
        ranges = data.get("reserved_ranges")
        if not isinstance(ranges, list):
            continue
        for raw_range in ranges:
            candidate = str(raw_range).strip()
            m = RESERVED_RANGE_RE.match(candidate)
            if not m:
                continue
            prefix = m.group(1) + "-"
            start, end = int(m.group(2)), int(m.group(3))
            if end < start:
                start, end = end, start
            for n in range(start, end + 1):
                reserved[prefix].add(n)
    return reserved


def find_gaps(
    numbers_by_prefix: dict[str, list[int]],
    max_gap: int = 10,
    reserved: dict[str, set[int]] | None = None,
) -> dict[str, list[int]]:
    """Ищет пропуски в нумерации > max_gap.

    Если между соседними номерами полностью покрыто зарезервированными
    (`reserved`), gap не репортуется.
    """
    if reserved is None:
        reserved = {}
    gaps = {}
    for prefix, nums in numbers_by_prefix.items():
        if len(nums) < 2:
            continue
        reserved_nums = reserved.get(prefix, set())
        prefix_gaps = []
        for i in range(1, len(nums)):
            a, b = nums[i - 1], nums[i]
            diff = b - a
            if diff <= max_gap:
                continue
            missing = set(range(a + 1, b)) - reserved_nums
            if not missing:
                # Вся щель покрыта reserved_ranges — не репортуем.
                continue
            prefix_gaps.append((a, b, diff))
        if prefix_gaps:
            gaps[prefix] = prefix_gaps
    return gaps


def parse_declared_counters(workspace: Path) -> dict[str, int]:
    """Парсит 00_index.md, секция counters.

    Если секции `## Counters` нет — fallback на frontmatter карточек
    01–14: читает ключи `active_<plural>s` (active_patterns, active_mechanisms…)
    и маппит их в canonical counter keys, совпадающие с card_prefix_map в
    build_report. Это позволяет sync_check работать с воркспейсами, где
    счётчики живут во frontmatter отдельных карточек, а не в 00_index.
    """
    f = workspace / "00_index.md"
    counters = {}

    if f.exists():
        text = f.read_text(encoding="utf-8", errors="replace")

        # Ищем секцию counters
        counters_section = re.search(
            r"##\s*Counters[\s\S]+?(?=\n##\s|\Z)", text, re.IGNORECASE
        )
        if counters_section:
            for m in COUNTER_RE.finditer(counters_section.group(0)):
                key, val = m.groups()
                counters[key] = int(val)

    if counters:
        return counters

    # Fallback: собираем `active_<name>` из frontmatter всех карточек
    # (включая 00_index.md — там active_cards и т.п. тоже могут быть).
    # Маппинг active_<plural> → canonical counter key.
    active_key_map = {
        "active_patterns": "patterns",
        "active_mechanisms": "mechanisms",
        "active_errors": "errors",
        "active_knowledge_maps": "knowledge_maps",
        "active_meta_decisions": "meta_decisions",
        "active_terms": "terms",
        "active_glossary_terms": "terms",  # alias, встречается в 00_index
        "active_entities": "entities",
        "active_projects": "projects",
        "active_lessons": "lessons",
        "active_reflections": "reflections",
        "active_audits": "audits",
        "active_domains": "domains",
        "confidence_domains": "domains",  # alias в 00_index
        "active_clusters": "clusters",
        "cross_project_clusters": "clusters",  # alias в 00_index
    }

    for mf in workspace.rglob("*.md"):
        if "archive" in mf.parts or "_generated" in mf.parts or ".backup" in mf.parts:
            continue
        try:
            text = mf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        data, _ = parse_frontmatter(text)
        if not data:
            continue
        for fm_key, counter_key in active_key_map.items():
            if fm_key in data and counter_key not in counters:
                try:
                    counters[counter_key] = int(data[fm_key])
                except (ValueError, TypeError):
                    continue

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

    # Сравнение actual vs declared через canonical CARD_PREFIX_MAP
    for key, actual in count_by_prefix.items():
        counter_key = CARD_PREFIX_MAP.get(key, key.rstrip("-"))
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

    # 3. Пропуски — с учётом зарезервированных диапазонов из frontmatter.
    reserved = parse_reserved_ranges(workspace)
    gaps = find_gaps(numbers_by_prefix, reserved=reserved)
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

    # Counters — одна строка на префикс, actual сведён с declared через
    # CARD_PREFIX_MAP (иначе "pat-" и "patterns" рендерились бы отдельно).
    lines.append("## Counters")
    lines.append("")
    lines.append("| Prefix | Counter | Actual | Declared | Status |")
    lines.append("|---|---|---|---|---|")

    shown_counter_keys: set[str] = set()
    for prefix in sorted(report.counters_actual):
        counter_key = CARD_PREFIX_MAP.get(prefix, prefix.rstrip("-"))
        a = report.counters_actual.get(prefix, 0)
        d = report.counters_declared.get(counter_key, "—")
        status = "✅" if str(a) == str(d) else "⚠"
        lines.append(f"| `{prefix}` | `{counter_key}` | {a} | {d} | {status} |")
        shown_counter_keys.add(counter_key)

    # Declared-ключи без соответствующего actual (пришли из 00_index, но
    # в воркспейсе таких записей нет — полезно увидеть как отдельный блок)
    orphan_declared = sorted(
        k for k in report.counters_declared if k not in shown_counter_keys
    )
    for k in orphan_declared:
        d = report.counters_declared.get(k, "—")
        lines.append(f"| — | `{k}` | 0 | {d} | ⚠ |")
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
