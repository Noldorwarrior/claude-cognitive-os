---
version: 1.3
type: card
card_id: "14"
updated: 2026-04-20
---

# 14 — Лог аудита

Все системные события: миграции, архивации, калибровки, изменения
порогов, обнаруженные противоречия.

## Формат

```markdown
### audit-NNN — Тип события

- date: 2026-04-20
- type: (migration / archive / calibration / threshold_change /
         knowledge_conflict / pattern_conflict / project_conflict /
         regression_inherited / systemic_error / ...)
- severity: (low / medium / high)
- trigger: (скилл / детектор / пользователь)

**Описание:** что произошло.

**Связи:** [[md-NNN]], [[pat-NNN]], [[ec-NNN]] ...

**Действие:** что сделано в ответ.
```

## События

_Пусто. Заполняется автоматически скиллами и детектором._

## Правила

- Каждое изменение порогов — `audit-NNN` типа `threshold_change`.
- Каждая миграция — `audit-NNN` типа `migration`.
- Каждый обнаруженный конфликт — `audit-NNN` соответствующего типа.
- Каждая архивация — `audit-NNN` типа `archive`.

## Связанное

- [[04_meta_decisions]] — причины изменений.
- `audit_contradictions.py` — источник конфликтов.
- [[audit]] — пользовательский скилл полного аудита.
