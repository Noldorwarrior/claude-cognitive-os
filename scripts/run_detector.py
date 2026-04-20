#!/usr/bin/env python3
"""
run_detector.py — фоновый детектор сигналов воркспейса cognitive-os.

Ищет:
- pattern_candidate — 3+ похожих наблюдения в окне 30 дней.
- cluster_candidate — 3+ проектов одного домена с общим паттерном.
- systemic_error — 3+ ошибок одного типа.
- conflict_suspect — пересечение ключевых терминов ≥ 60%.
- threshold_near_trigger — счётчик достиг 80% порога.
- cold_candidate — запись не обновлялась > 4.8 месяцев.

Результат: <workspace>/_generated/detector_signals.md.

Запуск:
    python3 run_detector.py --workspace /path --full
    python3 run_detector.py --workspace /path --changed "02_patterns.md,03_projects_registry.md" --incremental

Вызывается из hooks.json. Не пишет в продовые карточки.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import combinations
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parent))
from lib.error_handling import safe_main  # noqa: E402
from pathlib import Path

# Паттерны заголовков
HEADERS = {
    "pat": re.compile(r"^###\s+(pat-\d{3})\s*[—-]\s*(.+?)$", re.MULTILINE),
    "proj": re.compile(r"^##\s+(proj-\d{3})\s*[—-]\s*(.+?)$", re.MULTILINE),
    "km": re.compile(r"^###\s+(km-\d{3})\s*[—-]\s*(.+?)$", re.MULTILINE),
    "ec": re.compile(r"^###\s+(ec-\d{3})\s*[—-]\s*(.+?)$", re.MULTILINE),
    "wm": re.compile(r"^###\s+(wm-\d{3})\s*[—-]\s*(.+?)$", re.MULTILINE),
}

DOMAIN_RE = re.compile(r"^-?\s*domain:\s*([\w\-_]+)", re.MULTILINE)
LAST_USED_RE = re.compile(r"^-?\s*last_used:\s*([\d\-]+)", re.MULTILINE)
CREATED_RE = re.compile(r"^-?\s*created:\s*([\d\-]+)", re.MULTILINE)
ERROR_TYPE_RE = re.compile(r"^-?\s*error_type:\s*([\w\-_]+)", re.MULTILINE)

RU_STOPWORDS = {
    "и", "в", "на", "с", "для", "по", "из", "что", "как", "это", "или",
    "а", "но", "же", "то", "не", "да", "так", "бы", "у", "к", "от", "до",
    "чтобы", "если", "при", "через", "о", "об", "про",
}

# Пороги по умолчанию. Фактические значения подгружаются
# динамически из references/thresholds.md или docs/thresholds_reference.md
# в момент запуска (функция load_thresholds). Хардкод — fallback,
# если файлы не найдены или ключи не перечислены.
THRESH_DEFAULTS: dict[str, float] = {
    "pattern_min": 3,
    "cluster_min_projects": 3,
    "systemic_error_min": 3,
    "similarity": 0.6,
    "near_trigger_pct": 0.80,
    "cold_idle_months": 4.8,
}

# Алиасы: как ключ может называться в thresholds.md → имя в THRESH.
# Позволяет пользователю вести справочник в «человеческом» стиле
# (`pattern`, `systemic_error`), не ломая скрипт.
THRESH_ALIASES: dict[str, str] = {
    "pattern": "pattern_min",
    "systemic_error": "systemic_error_min",
    "cluster_min_projects": "cluster_min_projects",
    "similarity": "similarity",
    "near_trigger_pct": "near_trigger_pct",
    "cold_idle_months": "cold_idle_months",
}

# Регекс строки markdown-таблицы с порогом: `| key | value |`.
# Совместим с форматом из sync_check.py (тот же паттерн).
THRESH_TABLE_RE = re.compile(r"^\|\s*`?(\w+)`?\s*\|\s*([^\s|]+)\s*\|", re.MULTILINE)


def _coerce(raw: str) -> float | int | None:
    """Безопасно приводит строковое значение к int/float."""
    raw = raw.strip().strip("`")
    if not raw:
        return None
    try:
        if "." in raw or "e" in raw.lower():
            return float(raw)
        return int(raw)
    except ValueError:
        return None


def load_thresholds(workspace: Path) -> dict[str, float]:
    """Подгружает пороги из thresholds.md, с фолбэком на THRESH_DEFAULTS.

    Порядок поиска:
    1. `<workspace>/references/thresholds.md`
    2. `<workspace>/docs/thresholds_reference.md`

    Неизвестные ключи (отсутствующие в THRESH_ALIASES) игнорируются —
    это защищает от шума из посторонних таблиц (например, reading_ladder).
    """
    thresh = dict(THRESH_DEFAULTS)
    candidates = [
        workspace / "references" / "thresholds.md",
        workspace / "docs" / "thresholds_reference.md",
    ]
    for f in candidates:
        if not f.exists():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in THRESH_TABLE_RE.finditer(text):
            raw_key, raw_val = m.groups()
            key = THRESH_ALIASES.get(raw_key)
            if key is None:
                continue
            val = _coerce(raw_val)
            if val is None:
                continue
            thresh[key] = val
    return thresh


@dataclass
class Signal:
    type: str
    subjects: list[str]
    evidence: str
    severity: str = "info"
    created: str = field(default_factory=lambda: date.today().isoformat())


def extract_keywords(text: str, top_n: int = 15) -> set[str]:
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"\[\[[^\]]+\]\]", "", text)
    words = re.findall(r"\b[а-яА-Яa-zA-Z][\w\-]{3,}\b", text.lower())
    words = [w for w in words if w not in RU_STOPWORDS]
    cnt = Counter(words)
    return {w for w, _ in cnt.most_common(top_n)}


def parse_records(workspace: Path, filename: str, kind: str) -> list[dict]:
    f = workspace / filename
    if not f.exists():
        return []
    text = f.read_text(encoding="utf-8", errors="replace")
    header_re = HEADERS.get(kind)
    if not header_re:
        return []

    matches = list(header_re.finditer(text))
    records = []
    for i, m in enumerate(matches):
        rid = m.group(1)
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end]

        domain_m = DOMAIN_RE.search(content)
        last_used_m = LAST_USED_RE.search(content)
        created_m = CREATED_RE.search(content)
        error_type_m = ERROR_TYPE_RE.search(content)

        records.append({
            "id": rid,
            "title": title,
            "content": content,
            "keywords": extract_keywords(content),
            "domain": domain_m.group(1).strip() if domain_m else "uncategorized",
            "last_used": last_used_m.group(1) if last_used_m else None,
            "created": created_m.group(1) if created_m else None,
            "error_type": error_type_m.group(1) if error_type_m else None,
        })
    return records


def find_pattern_candidates(records: list[dict], thresh: dict) -> list[Signal]:
    """3+ наблюдения с общими ключевыми словами."""
    signals = []
    groups: dict[frozenset, list[dict]] = defaultdict(list)
    for r in records:
        if len(r["keywords"]) < 3:
            continue
        # Используем топ-5 терминов как ключ группы
        key = frozenset(sorted(r["keywords"])[:5])
        groups[key].append(r)

    for key, group in groups.items():
        if len(group) >= thresh["pattern_min"]:
            ids = [r["id"] for r in group]
            signals.append(Signal(
                type="pattern_candidate",
                subjects=ids,
                evidence=f"Общие термины: {', '.join(list(key)[:3])}",
                severity="medium",
            ))
    return signals


def find_cluster_candidates(projects: list[dict], thresh: dict) -> list[Signal]:
    """3+ проектов одного домена."""
    signals = []
    by_domain: dict[str, list[str]] = defaultdict(list)
    for p in projects:
        by_domain[p["domain"]].append(p["id"])

    for domain, ids in by_domain.items():
        if domain == "uncategorized":
            continue
        if len(ids) >= thresh["cluster_min_projects"]:
            signals.append(Signal(
                type="cluster_candidate",
                subjects=ids,
                evidence=f"Домен «{domain}» объединяет {len(ids)} проектов",
                severity="medium",
            ))
    return signals


def find_systemic_errors(errors: list[dict], thresh: dict) -> list[Signal]:
    """3+ ошибок одного error_type."""
    signals = []
    by_type: dict[str, list[str]] = defaultdict(list)
    for e in errors:
        et = e["error_type"] or "untyped"
        by_type[et].append(e["id"])

    for et, ids in by_type.items():
        if et == "untyped":
            continue
        if len(ids) >= thresh["systemic_error_min"]:
            signals.append(Signal(
                type="systemic_error",
                subjects=ids,
                evidence=f"Тип «{et}»: {len(ids)} ошибок",
                severity="high",
            ))
    return signals


def find_conflict_suspects(records: list[dict], kind: str, thresh: dict) -> list[Signal]:
    """Высокое пересечение ключевых слов между парами."""
    signals = []
    for a, b in combinations(records, 2):
        if not a["keywords"] or not b["keywords"]:
            continue
        inter = len(a["keywords"] & b["keywords"])
        union = len(a["keywords"] | b["keywords"])
        sim = inter / union if union else 0
        if sim >= thresh["similarity"]:
            signals.append(Signal(
                type="conflict_suspect",
                subjects=[a["id"], b["id"]],
                evidence=f"{kind}: similarity={sim:.2f}, общих терминов={inter}",
                severity="low",
            ))
    return signals


def find_cold_candidates(records: list[dict], kind: str, thresh: dict) -> list[Signal]:
    """Записи, не обновлявшиеся дольше `cold_idle_months` месяцев."""
    signals = []
    today = date.today()
    threshold_days = thresh["cold_idle_months"] * 30
    for r in records:
        ref_date = r["last_used"] or r["created"]
        if not ref_date:
            continue
        try:
            d = datetime.strptime(ref_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        idle = (today - d).days
        if idle > threshold_days:
            signals.append(Signal(
                type="cold_candidate",
                subjects=[r["id"]],
                evidence=f"{kind} простой {idle} дней (с {ref_date})",
                severity="low",
            ))
    return signals


def render_report(signals: list[Signal], workspace: Path, mode: str) -> str:
    today = date.today().isoformat()
    lines = [
        "---",
        f"generated: {today}",
        f"mode: {mode}",
        f"type: detector_signals",
        "---",
        "",
        f"# Сигналы детектора — {today}",
        "",
        f"**Всего сигналов:** {len(signals)}",
        f"**Режим:** `{mode}`",
        "",
    ]

    if not signals:
        lines.append("_Сигналов не обнаружено._")
        return "\n".join(lines) + "\n"

    # Группируем по типу
    by_type: dict[str, list[Signal]] = defaultdict(list)
    for s in signals:
        by_type[s.type].append(s)

    lines.append("## Сводка")
    lines.append("")
    lines.append("| Тип | Количество |")
    lines.append("|---|---|")
    for t in sorted(by_type.keys()):
        lines.append(f"| {t} | {len(by_type[t])} |")
    lines.append("")

    # Детали
    severity_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    for t in sorted(by_type.keys()):
        lines.append(f"## {t}")
        lines.append("")
        for s in sorted(by_type[t], key=lambda x: severity_order.get(x.severity, 9)):
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢", "info": "ℹ"}[s.severity]
            subjects = ", ".join(f"`{sid}`" for sid in s.subjects)
            lines.append(f"- {emoji} **{s.severity}** — {subjects}")
            lines.append(f"  - Evidence: {s.evidence}")
        lines.append("")

    return "\n".join(lines) + "\n"


@safe_main
def main() -> int:
    ap = argparse.ArgumentParser(description="Детектор сигналов cognitive-os.")
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--incremental", action="store_true")
    ap.add_argument("--changed", default="", help="Список изменённых файлов через запятую.")
    ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--if-changed", action="store_true",
                    help="Noop-флаг для hooks (скрипт идемпотентен).")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        print(f"Воркспейс не найден: {workspace}", file=sys.stderr)
        return 1

    mode = "full" if args.full else "incremental" if args.incremental else "full"
    changed = [c.strip() for c in args.changed.split(",") if c.strip()]

    # Пороги: сначала пробуем подтянуть из references/thresholds.md,
    # при отсутствии файла остаются дефолты THRESH_DEFAULTS.
    thresh = load_thresholds(workspace)

    patterns = parse_records(workspace, "02_patterns.md", "pat")
    projects = parse_records(workspace, "03_projects_registry.md", "proj")
    errors = parse_records(workspace, "10_error_corrections.md", "ec")
    kmaps = parse_records(workspace, "08_knowledge_maps.md", "km")

    signals: list[Signal] = []

    # Pattern candidates — через сходство уже существующих наблюдений.
    if not changed or any("02_patterns" in c or "03_projects" in c for c in changed):
        signals.extend(find_pattern_candidates(patterns + kmaps, thresh))

    # Clusters
    if not changed or any("03_projects" in c for c in changed):
        signals.extend(find_cluster_candidates(projects, thresh))

    # Systemic errors
    if not changed or any("10_error" in c for c in changed):
        signals.extend(find_systemic_errors(errors, thresh))

    # Conflicts (только в full-режиме — дорого)
    if args.full:
        signals.extend(find_conflict_suspects(kmaps, "knowledge", thresh))
        signals.extend(find_conflict_suspects(patterns, "pattern", thresh))
        signals.extend(find_cold_candidates(patterns, "pattern", thresh))
        signals.extend(find_cold_candidates(projects, "project", thresh))

    report = render_report(signals, workspace, mode)

    if args.stdout:
        print(report)
    else:
        out_dir = workspace / "_generated"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "detector_signals.md"
        out_path.write_text(report, encoding="utf-8")
        print(f"Сигналы: {out_path} ({len(signals)} шт.)")

    return 0


if __name__ == "__main__":  # pragma: no cover
    main()
