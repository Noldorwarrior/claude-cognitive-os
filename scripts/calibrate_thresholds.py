#!/usr/bin/env python3
"""
calibrate_thresholds.py — анализ данных калибровки и выдача рекомендаций.

Читает `11_confidence_scoring.md`, извлекает записи вида
`task-NNN | domain | predicted_confidence | actual_outcome | delta`,
считает агрегаты по доменам и предлагает корректировки порогов.

Не меняет пороги сам — только выдаёт отчёт. Action-скилл [[calibrate]]
презентует пользователю и применяет по одобрению.

Запуск:
    python3 calibrate_thresholds.py --workspace /path/to/cognitive-os
    python3 calibrate_thresholds.py --workspace . --domain youth_policy
    python3 calibrate_thresholds.py --workspace . --window-days 90
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.error_handling import safe_main  # noqa: E402

# Паттерны записей калибровки
TASK_RE = re.compile(
    r"^\|\s*(task-\d+)\s*\|\s*([\w\-_]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([-+]?[\d.]+)\s*\|",
    re.MULTILINE,
)

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


@dataclass
class TaskRecord:
    task_id: str
    domain: str
    predicted: float
    actual: float
    delta: float
    date: date | None = None


@dataclass
class DomainStats:
    domain: str
    count: int = 0
    mean_predicted: float = 0.0
    mean_actual: float = 0.0
    mean_delta: float = 0.0
    overconfidence_rate: float = 0.0  # % tasks where predicted > actual
    underconfidence_rate: float = 0.0
    mae: float = 0.0  # mean absolute error
    records: list[TaskRecord] = field(default_factory=list)


def parse_confidence_scoring(workspace: Path, window_days: int | None = None) -> list[TaskRecord]:
    """Парсит 11_confidence_scoring.md, возвращает список записей."""
    f = workspace / "11_confidence_scoring.md"
    if not f.exists():
        return []

    text = f.read_text(encoding="utf-8", errors="replace")
    records = []
    cutoff: date | None = None
    if window_days:
        cutoff = date.today() - timedelta(days=window_days)

    # Парсим таблицы с данными
    for m in TASK_RE.finditer(text):
        task_id, domain, pred, actual, delta = m.groups()
        # Ищем дату в строке вблизи записи (простая эвристика)
        line_start = text.rfind("\n", 0, m.start())
        line_end = text.find("\n", m.end())
        surrounding = text[max(0, line_start - 200):line_end]
        date_match = DATE_RE.search(surrounding)
        rec_date = None
        if date_match:
            try:
                rec_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
            except ValueError:
                rec_date = None

        if cutoff and rec_date and rec_date < cutoff:
            continue

        try:
            records.append(
                TaskRecord(
                    task_id=task_id,
                    domain=domain,
                    predicted=float(pred),
                    actual=float(actual),
                    delta=float(delta),
                    date=rec_date,
                )
            )
        except ValueError:
            continue

    return records


def aggregate_by_domain(records: list[TaskRecord]) -> dict[str, DomainStats]:
    """Группировка и подсчёт статистик по доменам."""
    by_domain: dict[str, list[TaskRecord]] = defaultdict(list)
    for r in records:
        by_domain[r.domain].append(r)

    stats = {}
    for domain, recs in by_domain.items():
        n = len(recs)
        if n == 0:
            continue
        mean_pred = sum(r.predicted for r in recs) / n
        mean_act = sum(r.actual for r in recs) / n
        mean_delta = sum(r.delta for r in recs) / n
        over = sum(1 for r in recs if r.predicted > r.actual)
        under = sum(1 for r in recs if r.predicted < r.actual)
        mae = sum(abs(r.delta) for r in recs) / n

        stats[domain] = DomainStats(
            domain=domain,
            count=n,
            mean_predicted=round(mean_pred, 3),
            mean_actual=round(mean_act, 3),
            mean_delta=round(mean_delta, 3),
            overconfidence_rate=round(over / n, 3),
            underconfidence_rate=round(under / n, 3),
            mae=round(mae, 3),
            records=recs,
        )
    return stats


def generate_recommendations(
    stats: dict[str, DomainStats],
    confidence_min_tasks: int = 5,
) -> list[dict]:
    """Выработка рекомендаций по доменам."""
    recs = []
    for domain, s in stats.items():
        if s.count < confidence_min_tasks:
            recs.append(
                {
                    "domain": domain,
                    "type": "insufficient_data",
                    "severity": "info",
                    "message": f"Домен имеет только {s.count} записей (нужно ≥{confidence_min_tasks}). Калибровка отложена.",
                    "action": "none",
                }
            )
            continue

        # Критичная переоценка — более 25% или actual < 0.7
        if s.mean_actual < 0.7:
            recs.append(
                {
                    "domain": domain,
                    "type": "critical_underperformance",
                    "severity": "high",
                    "mean_predicted": s.mean_predicted,
                    "mean_actual": s.mean_actual,
                    "mae": s.mae,
                    "message": f"Домен '{domain}': средний actual {s.mean_actual:.2f} — ниже порога 0.7. Критичная переоценка.",
                    "action": "activate_P5_for_domain",
                    "recommended_threshold_adjustment": {
                        "default_confidence": round(s.mean_predicted - 0.15, 2),
                        "reason": "systemic_overconfidence",
                    },
                }
            )
        elif s.overconfidence_rate > 0.6:
            recs.append(
                {
                    "domain": domain,
                    "type": "overconfidence",
                    "severity": "medium",
                    "overconfidence_rate": s.overconfidence_rate,
                    "mean_delta": s.mean_delta,
                    "message": f"Домен '{domain}': переоценивание в {int(s.overconfidence_rate*100)}% случаев. MAE={s.mae:.2f}.",
                    "action": "lower_default_confidence",
                    "recommended_threshold_adjustment": {
                        "default_confidence_delta": round(-s.mean_delta, 2),
                        "reason": "persistent_overconfidence",
                    },
                }
            )
        elif s.underconfidence_rate > 0.6:
            recs.append(
                {
                    "domain": domain,
                    "type": "underconfidence",
                    "severity": "low",
                    "underconfidence_rate": s.underconfidence_rate,
                    "mean_delta": s.mean_delta,
                    "message": f"Домен '{domain}': недооценивание в {int(s.underconfidence_rate*100)}% случаев.",
                    "action": "raise_default_confidence",
                    "recommended_threshold_adjustment": {
                        "default_confidence_delta": round(-s.mean_delta, 2),
                        "reason": "persistent_underconfidence",
                    },
                }
            )
        else:
            recs.append(
                {
                    "domain": domain,
                    "type": "well_calibrated",
                    "severity": "info",
                    "mae": s.mae,
                    "message": f"Домен '{domain}' хорошо откалиброван. MAE={s.mae:.2f}.",
                    "action": "none",
                }
            )

    return recs


def render_report(
    stats: dict[str, DomainStats],
    recs: list[dict],
    window_days: int | None,
) -> str:
    """Markdown-отчёт."""
    today = date.today().isoformat()
    lines = [f"# Калибровка порогов — {today}", ""]
    if window_days:
        lines.append(f"**Окно:** последние {window_days} дней")
    lines.append(f"**Доменов проанализировано:** {len(stats)}")
    lines.append(f"**Всего записей:** {sum(s.count for s in stats.values())}")
    lines.append("")

    lines.append("## Статистика по доменам")
    lines.append("")
    lines.append("| Домен | N | mean(pred) | mean(actual) | MAE | overconf | underconf |")
    lines.append("|---|---|---|---|---|---|---|")
    for domain in sorted(stats.keys()):
        s = stats[domain]
        lines.append(
            f"| `{s.domain}` | {s.count} | {s.mean_predicted:.2f} | "
            f"{s.mean_actual:.2f} | {s.mae:.2f} | "
            f"{int(s.overconfidence_rate*100)}% | {int(s.underconfidence_rate*100)}% |"
        )
    lines.append("")

    lines.append("## Рекомендации")
    lines.append("")
    for r in recs:
        sev_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢", "info": "ℹ️"}.get(r["severity"], "•")
        lines.append(f"### {sev_emoji} {r['domain']} — {r['type']}")
        lines.append("")
        lines.append(r["message"])
        if "recommended_threshold_adjustment" in r:
            lines.append("")
            lines.append("**Предложенная корректировка:**")
            lines.append(f"```yaml")
            for k, v in r["recommended_threshold_adjustment"].items():
                lines.append(f"{k}: {v}")
            lines.append(f"```")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Не применяется автоматически. Для применения — запустить [[calibrate]] и одобрить предложения.")

    return "\n".join(lines) + "\n"


@safe_main
def main() -> int:
    ap = argparse.ArgumentParser(description="Калибровка порогов когнитивного воркспейса.")
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--domain", help="Только указанный домен")
    ap.add_argument("--window-days", type=int, help="Окно анализа в днях")
    ap.add_argument("--min-tasks", type=int, default=5, help="Минимум записей для рекомендации")
    ap.add_argument("--json", action="store_true", help="Вывод в JSON")
    ap.add_argument("--stdout", action="store_true", help="Не писать файл")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        print(f"Воркспейс не найден: {workspace}", file=sys.stderr)
        return 1

    records = parse_confidence_scoring(workspace, args.window_days)
    if args.domain:
        records = [r for r in records if r.domain == args.domain]

    if not records:
        print("Нет данных для калибровки. Проверьте 11_confidence_scoring.md.", file=sys.stderr)
        return 0

    stats = aggregate_by_domain(records)
    recs = generate_recommendations(stats, confidence_min_tasks=args.min_tasks)

    if args.json:
        out = {
            "workspace": str(workspace),
            "generated": date.today().isoformat(),
            "window_days": args.window_days,
            "stats": {d: s.__dict__ for d, s in stats.items()},
            "recommendations": recs,
        }
        for d in out["stats"].values():
            d.pop("records", None)
        content = json.dumps(out, ensure_ascii=False, indent=2, default=str)
    else:
        content = render_report(stats, recs, args.window_days)

    if args.stdout:
        print(content)
    else:
        out_path = workspace / "_generated" / (
            "calibration_report.json" if args.json else "calibration_report.md"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"Отчёт: {out_path}")

    critical = [r for r in recs if r["severity"] == "high"]
    if critical:
        print(f"⚠ Критичных доменов: {len(critical)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    main()
