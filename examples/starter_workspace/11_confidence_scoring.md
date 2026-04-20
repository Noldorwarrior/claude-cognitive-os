---
version: 1.3
type: card
card_id: "11"
updated: 2026-04-20
---

# 11 — Калибровка уверенности

Фиксация предсказаний (predicted) и их результатов (actual) для
самообучения системы.

## Таблица задач

| task | domain | predicted | actual | delta | date | notes |
|---|---|---|---|---|---|---|
| task-001 | tooling | 0.8 | 0.9 | +0.1 | 2026-04-20 | первая настройка |

_Заполняйте построчно. `calibrate_thresholds.py` использует эту таблицу
для генерации рекомендаций._

## Глоссарий

- **task** — ID задачи (произвольный, рекомендуется task-NNN).
- **predicted** — уверенность 0.0–1.0 **до** выполнения.
- **actual** — оценка 0.0–1.0 **после** выполнения.
- **delta** = actual − predicted.

## История калибровок

_Запуски [[calibrate]] фиксируются здесь с датой и рекомендациями._

### pat-calibration-001 — Пример записи

- domain: tooling
- applied: 2026-04-20
- recommendation: well_calibrated
- MAE: 0.10
- tasks_analyzed: 5

## Правила

- Минимум 5 задач в домене для первой калибровки.
- При `overconfidence_rate > 0.60` — пресет П5.
- При `actual < 0.70` в среднем — critical underperformance.
- Записи старше 6 месяцев архивируются, если не влияют на recomendation.

## Связанное

- [[04_meta_decisions]] — куда попадают изменения порогов.
- [[13_self_reflection]] — источник данных для калибровки.
- `calibrate_thresholds.py` — исполнитель.
