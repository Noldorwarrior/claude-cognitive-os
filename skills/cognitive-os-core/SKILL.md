---
name: cognitive-os-core
description: >
  Этот скилл — когнитивное ядро плагина claude-cognitive-os. Загружается
  всегда в начале сессии и по триггерам: «покажи профиль», «покажи
  паттерны», «покажи проекты», «покажи механизмы», «покажи ошибки»,
  «пересмотри глобальный слой», «добавь знание про», «инициализируй
  cognitive-os», «мета-решение», «lessons learned», «сквозной паттерн».
  Управляет 15 картами знаний уровня vault (профиль, паттерны, реестр
  проектов, мета-решения, глоссарий, уроки, сущности, карты знаний,
  механизмы, ошибки, калибровка уверенности, граф, самоаудит,
  журнал). Детальные разделы вынесены в references/ и загружаются
  по необходимости.
metadata:
  version: "1.3.0"
  migrated_from: "cognitive-os skill v1.0.1"
  trigger_mode: pattern_detection_threshold
  verification: P5_maximum_32_mechanisms
  priority: critical
  required_for: ALL conversations across ALL projects
  thresholds:
    pattern: 3
    systemic_error: 3
    knowledge_map_access: 3
    pattern_window_days: 30
    max_active_patterns: 50
    max_active_lessons: 30
    archive_entity_idle_months: 6
    archive_pattern_idle_months: 6
    archive_lesson_idle_months: 12
    archive_reflection_idle_months: 24
    revision_interval_days: 30
    cluster_min_projects: 3
    confidence_min_tasks: 5
    extract_principle_min: 3
    extract_principle_min_overlap: 3
  fallbacks:
    consolidate_memory: internal_minimal_revision
    govdoc_self_reflection: internal_8axis_scoring
    verification_plugin: manual_checklist
  reading_ladder:
    "-1": overview_only
    "0": yaml_frontmatter_index
    "1": full_index_plus_profile
    "2": plus_patterns_and_meta
    "3": plus_knowledge_and_mechanisms
    "4": all_maps_by_relevance
---

# cognitive-os-core — когнитивное ядро плагина

## Назначение

`cognitive-os-core` — ядро четырёхслойной когнитивной архитектуры. Работает
поверх всех проектов пользователя, извлекает сквозные знания, аккумулирует
паттерны, фиксирует мета-решения и служит точкой роста памяти между
сессиями.

Скилл работает в тандеме с визуальным слоем (`cognitive-os-graph`),
self-learning слоем (`cognitive-os-calibration`) и десятью action-скиллами
плагина (`init`, `migrate`, `status`, `graph`, `backlinks`, `reflect`,
`calibrate`, `archive`, `patterns`, `audit`).

## Архитектура четырёх слоёв

| Слой | Где живёт | Что хранит | Скилл / инструмент |
|---|---|---|---|
| 1. Пользовательский | system prompt | 10 правил поведения | user_preferences |
| 2. Задачно-операционный | `TASKS.md` | Текущие задачи, дедлайны | `productivity:memory-management` |
| 3. Проектный | `Projects/<name>/` | Знания одного проекта | `project-knowledge-maps` (если установлен) |
| 4. **Глобальный когнитивный** | `cognitive_os/` или `Projects/<name>/` | Мета-знания, паттерны, профиль | **`cognitive-os-core` (этот скилл)** |

**Принцип не-дублирования:** если знание касается одного проекта — оно
живёт в `project-knowledge-maps`. Если знание сквозное (2+ проекта или все
диалоги) — оно живёт в глобальном слое.

Полная архитектура — в `references/architecture.md`.

## Состав 15 карт

Все карты создаются в `cognitive_os/` (один vault на пользователя) или
внутри `Projects/<name>/` (для одного проекта). Шаблоны — в
`templates/` плагина.

### Базовое ядро (8 карт) — создаются при инициализации

| # | Файл | Назначение |
|---|---|---|
| 00 | `00_index.md` | Реестр всех карт, главное окно |
| 01 | `01_user_profile.md` | Профиль: стиль работы, предпочтения |
| 02 | `02_patterns.md` | Сквозные паттерны (триггер: `thresholds.pattern` повторений) |
| 03 | `03_projects_registry.md` | Реестр проектов |
| 04 | `04_meta_decisions.md` | Мета-решения «как работать» |
| 05 | `05_global_glossary.md` | Сквозные термины |
| 06 | `06_lessons_learned.md` | Уроки из побед и провалов |
| 07 | `07_global_entities.md` | Сквозные люди / орг. / события |

### Расширение (3 карты) — по запросу пользователя

| # | Файл | Назначение |
|---|---|---|
| 08 | `08_knowledge_maps.md` | Карты предметных знаний |
| 09 | `09_working_mechanisms.md` | Карты рабочих механизмов |
| 10 | `10_error_corrections.md` | Журнал исправлений ошибок |

### Служебные (4 карты) — создаются по триггерам

| # | Файл | Когда создаётся | Назначение |
|---|---|---|---|
| 11 | `11_confidence_scoring.md` | После `thresholds.confidence_min_tasks` задач в одном домене | Калибровка уверенности |
| 12 | `12_cross_project_graph.md` | При `thresholds.cluster_min_projects` проектах со связями | Граф связей |
| 13 | `13_self_reflection.md` | После 1-го самоаудита | Журнал самоаудитов |
| 14 | `14_audit_log.md` | При 1-м противоречии между проектами | Расхождения |

**Итого:** 11 создаются при инициализации, 4 — по триггерам.

## Когда скилл активируется

**В начале каждого диалога** — чтение уровня 0-1 reading ladder: профиль,
релевантные паттерны, реестр проектов.

**По ходу работы** — запись нового паттерна / механизма / исправления
ошибки по триггерам (детали в `references/extraction_logic.md`).

**В конце задачи** — самоаудит через `govdoc-analytics:self-reflection` или
internal fallback, обновление `00_index.md` и `03_projects_registry.md`.

## Когда скилл НЕ отключается

Ядро — всегда в фоне, не деактивируется в рамках сессии. Глубина чтения
регулируется reading ladder уровнем (-1..4) от задачи — не самим фактом
активации. Для краткого ответа на простой вопрос уровень остаётся 0 или 1,
для мета-задачи поднимается до 4.

Полное «отключение» возможно только через удаление воркспейса
(`cognitive_os/` отсутствует) — в этом случае скилл предлагает запустить
[[init]].

## Reading ladder (уровни чтения)

| Уровень | Что читается | Когда останавливаться |
|---|---|---|
| -1 | Только `00_index.md` frontmatter + граф (v1.3) | Обзорный запрос о состоянии |
| 0 | YAML-frontmatter `00_index.md` (≈100 байт) | Простой вопрос без контекста |
| 1 | Полный `00_index.md` + `01_user_profile.md` (≈3 KB) | Вопрос о стиле / предпочтениях |
| 2 | + `02_patterns.md` + `04_meta_decisions.md` (≈10 KB) | Выбор подхода / методологии |
| 3 | + `08_knowledge_maps.md` + `09_working_mechanisms.md` (≈20 KB) | Содержательная задача в знакомом домене |
| 4 | + остальные карты (до ≈50 KB) | Глубокие аудиты / мета-задачи |

**Никогда не читать всё сразу.** Это противоречит экономии токенов.
Подробные примеры — в `references/reading_ladder.md`.

## Триггеры записи (кратко)

| Карта | Триггер | Частота |
|---|---|---|
| `02_patterns.md` | N+ повторений в окне `thresholds.pattern_window_days` (default 3 / 30 дней) | По триггеру |
| `09_working_mechanisms.md` | Обнаружен новый способ решения класса задач | Сразу |
| `10_error_corrections.md` | Claude исправил свою ошибку / пользователь указал | Сразу |
| `08_knowledge_maps.md` | Обращение к одному знанию `thresholds.knowledge_map_access` раз / явный запрос | По триггеру |

Полные правила, шаблоны записей, идентификаторы (`pat-NNN`, `wm-NNN`,
`ec-NNN`, `km-NNN`) — в `references/extraction_logic.md`.

## Команды пользователя

| Команда | Действие |
|---|---|
| `покажи профиль` | Показать `01_user_profile.md` |
| `покажи паттерны` | Показать `02_patterns.md` |
| `покажи проекты` | Показать `03_projects_registry.md` |
| `покажи знания по {домен}` | Поиск в `08_knowledge_maps.md` |
| `покажи механизмы` | Показать `09_working_mechanisms.md` |
| `покажи ошибки` | Показать `10_error_corrections.md` |
| `пересмотри глобальный слой` | Запустить ревизию (action-скилл `calibrate` + `audit`) |
| `сбрось паттерн X` | Удалить `pat-X` из `02_patterns.md` |
| `добавь знание про {домен}` | Создать запись в `08_knowledge_maps.md` |
| `покажи граф` | Открыть `_generated/graph.html` (если собран) |

## Интеграция с другими скиллами и плагинами

| Интеграция | Роль |
|---|---|
| `productivity:memory-management` | Читает `TASKS.md` для контекста, bidirectional exchange в v1.3 |
| `consolidate-memory` | Делегирование ревизии (fallback — internal minimal revision) |
| `govdoc-analytics:self-reflection` | Самоаудит в конце задачи (fallback — internal 8-axis scoring) |
| `verification` plugin (П1–П14) | Логирование в `13_self_reflection.md` и `10_error_corrections.md` (fallback — manual checklist) |
| `cognitive-os-graph` (из этого плагина) | Визуализация связей между картами и проектами |
| `cognitive-os-calibration` (из этого плагина) | Автокалибровка порогов, извлечение принципов |

Полная таблица с fallback-режимами — в
`references/integration_with_verification.md`.

## Принцип «не-инфляции»

1. Паттерны: не более `thresholds.max_active_patterns` (default 50).
   Старые — в `_archive/patterns_YYYY-MM.md`.
2. Уроки: не более `thresholds.max_active_lessons` (default 30). Старые
   сворачиваются в обобщённые принципы через `extract_principles.py`.
3. Сущности: в `07_global_entities.md` попадают только упомянутые в
   2+ проектах.
4. Решения: в `04_meta_decisions.md` — только архитектурные /
   стратегические.

## Чек-лист перед каждой записью

Перед фиксацией паттерна / механизма / ошибки Claude проверяет:

- [ ] Это действительно сквозное знание (2+ проекта или все диалоги)?
- [ ] Это уже не зафиксировано (поиск по grep)?
- [ ] Если паттерн — действительно `thresholds.pattern`+ повторений?
- [ ] Есть ли краткая формулировка (≤ 200 символов)?
- [ ] ID присвоен по формату (`pat-NNN`, `wm-NNN`, `ec-NNN`, `km-NNN`)?
- [ ] `00_index.md` обновлён?
- [ ] Пользователь уведомлён (если запись существенная)?

## References

- `references/architecture.md` — 4 слоя, не-дублирование, не-инфляция,
  связь с плагином v1.3, graph/backlinks/hooks
- `references/extraction_logic.md` — полные правила триггеров,
  идентификаторы, режимы работы (инициализация / работа / ревизия +
  fallback)
- `references/reading_ladder.md` — уровни -1..4 с примерами запросов
- `references/integration_with_verification.md` — интеграция со всеми
  скиллами, fallback-режимы, связь с verification plugin

## Версионирование

| Версия | Дата | Что изменилось |
|---|---|---|
| 1.0.0 | 2026-04 | Первая версия skill. 15 карт, триггер 3+, верификация П5 |
| 1.0.1 | 2026-04 | Патч: 4 минора П5, параметризация thresholds, fallback-режимы |
| 1.3.0-plugin | 2026-04 | Миграция в плагин. Добавлен reading ladder level -1, cognitive-os-graph, cognitive-os-calibration, 10 action-скиллов, 3 субагента, hooks |
