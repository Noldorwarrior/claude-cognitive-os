---
version: 1.3
type: card
card_id: "09"
updated: 2026-04-20
---

# 09 — Рабочие механизмы

Проверенные процедуры, которые работают стабильно в 2+ проектах.

## Формат

```markdown
### wm-NNN — Название механизма

- domain: (область)
- from_pattern: [[pat-NNN]]
- applications: 3
- successful: 3
- success_rate: 1.00
- created: 2026-04-20
- domains_applied: [tooling, data]

**Когда применять:** условия запуска.

**Шаги:** 1, 2, 3...

**Выход:** что получается на выходе.

**Контроль качества:** как проверить, что получилось хорошо.

**Связи:** [[pat-NNN]], [[md-NNN]] (если продвинулось в принципы).
```

## Механизмы

_Пусто. Наполняется через [[patterns]] `promote_to_wm`._

## Кандидаты в принципы

_wm-NNN с applications ≥ 10 и domains ≥ 3 — кандидаты в md-NNN через
[[patterns]] `promote_to_principle`._

## Связанное

- [[02_patterns]] — источник wm-NNN.
- [[04_meta_decisions]] — куда продвигаются.
