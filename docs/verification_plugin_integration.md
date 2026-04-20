# Verification plugin integration

> **Статус:** 🚧 Заглушка. Будет развёрнута в v1.4.0.

## Назначение

Детальное описание интеграции `claude-cognitive-os` с внешним плагином
`verification` (32 механизма, 19 пресетов, П1–П14). Охватывает
delegation-паттерн, fallback при отсутствии плагина, контракты обмена
данными между `cog-verifier` субагентом и `verification:verify`.

## Планируемое содержание

- **Delegation pattern**: как `cog-verifier` делегирует в
  `verification:verify` через Skill tool.
- **Fallback-логика**: если плагин verification не установлен —
  внутренний чек-лист (8 осей + 32 механизма по упрощённой схеме).
- **Контракты данных**: формат входа (путь к документу, пресет,
  механизмы), формат выхода (JSON с результатами верификации).
- **Маппинг пресетов**: как пресеты `verification` соотносятся с
  действиями `claude-cognitive-os` (archive → П13, reflect → П14,
  patterns → П12, audit → П5+П13).
- **Совместимость версий**: какие версии `verification` совместимы с
  какими версиями `claude-cognitive-os`.
- **Отчёты**: где сохраняются результаты (`docs/verification/YYYY-MM-DD_<preset>.md`).

## Текущее поведение (v1.3.3)

- `cog-verifier` пытается вызвать `verification:verify` как Skill tool.
- Если Skill tool возвращает «skill not found» — субагент переключается
  на встроенный fallback (минимальный набор 8 осей).
- Результаты не сохраняются автоматически в `docs/verification/` —
  пользователь сам решает, нужен ли отчёт.
- `cog-verifier` работает на Claude Opus 4.6 (апгрейд с Sonnet 4.6 в
  v1.3.3 для П5 «Максимум» и критичных документов).

## Связанные

- [[audit]], [[calibrate]], [[reflect]], [[archive]], [[migrate]],
  [[patterns]] — action-скиллы, запускающие `cog-verifier`.
- `agents/cog-verifier.md` — субагент-исполнитель верификации.
- `skills/cognitive-os-core/references/integration_with_verification.md` —
  текущее (краткое) описание интеграции.

## Roadmap

- v1.4.0 — формализация fallback-чек-листа в отдельном файле
  `references/fallback_checklist.md`.
- v1.5.0 — автосохранение отчётов в `docs/verification/` для пресетов
  П5, П12, П13, П14.
- v2.0.0 — bidirectional sync: результаты верификации автоматически
  триггерят записи в [[13_self_reflection]] и [[10_error_corrections]].
