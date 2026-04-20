---
card: "00_index"
title: "Реестр карт cognitive-os"
type: index
version: "1.3.0-plugin"
created: "{{DATE}}"
updated: "{{DATE}}"
active_patterns: 0
active_mechanisms: 0
active_errors: 0
active_knowledge_maps: 0
active_lessons: 0
active_entities: 0
active_projects: 0
active_meta_decisions: 0
confidence_domains: 0
total_cards: 11
last_audit: null
last_calibration: null
last_archive: null
graph_last_build: null
schema_version: 1
---

# 00 — Реестр карт cognitive-os

Главное окно vault'а. Сводка по всем картам, перекрёстные ссылки,
сквозные метрики.

## Базовое ядро (8 карт)

| # | Карта | Записей | Статус |
|---|---|---|---|
| 01 | [[01_user_profile]] — профиль и стиль | — | active |
| 02 | [[02_patterns]] — сквозные паттерны | 0 / 50 | active |
| 03 | [[03_projects_registry]] — реестр проектов | 0 | active |
| 04 | [[04_meta_decisions]] — мета-решения | 0 | active |
| 05 | [[05_global_glossary]] — глоссарий | 0 | active |
| 06 | [[06_lessons_learned]] — уроки | 0 / 30 | active |
| 07 | [[07_global_entities]] — сущности | 0 | active |

## Расширение (3 карты, опционально)

| # | Карта | Записей | Статус |
|---|---|---|---|
| 08 | [[08_knowledge_maps]] — карты предметных знаний | 0 | active |
| 09 | [[09_working_mechanisms]] — рабочие механизмы | 0 | active |
| 10 | [[10_error_corrections]] — журнал ошибок | 0 | active |

## Служебные карты (создаются по триггерам)

| # | Карта | Триггер создания | Статус |
|---|---|---|---|
| 11 | [[11_confidence_scoring]] | 5+ задач в одном домене | dormant |
| 12 | [[12_cross_project_graph]] | 3+ проекта со связями | dormant |
| 13 | [[13_self_reflection]] | 1-й самоаудит | dormant |
| 14 | [[14_audit_log]] | 1-е противоречие между проектами | dormant |

## Архив

- `_archive/` — переносятся паттерны / сущности / сессии, не трогающиеся
  > `archive_entity_idle_months` (default 6).

## Сгенерированные артефакты

- `_generated/graph.html` — интерактивный граф связей (vis-network).
- `_generated/backlinks.md` — двусторонние обратные ссылки.
- `_generated/graph.mermaid` — fallback mermaid-граф.

## Последние события

| Дата | Событие | Карта | Детали |
|---|---|---|---|
| — | — | — | (заполняется автоматически при записях) |

## Счётчики порогов

| Параметр | Текущее | Порог | Остаток |
|---|---|---|---|
| Активных паттернов | 0 | 50 | 50 |
| Активных уроков | 0 | 30 | 30 |
| Доменов калибровки | 0 | — | — |
| Кластеров проектов (3+) | 0 | 3 | 3 |

## Интеграции

- [[productivity:memory-management]] — синхронизация с `TASKS.md`.
- [[consolidate-memory]] — ревизия (fallback: internal_minimal_revision).
- [[govdoc-analytics:self-reflection]] — самоаудит (fallback: internal_8axis_scoring).
- [[verification]] plugin — верификация (fallback: manual_checklist).

## Команды

| Команда | Что делает |
|---|---|
| `покажи состояние` | Читает frontmatter этого файла + граф |
| `покажи профиль` | Открывает [[01_user_profile]] |
| `покажи паттерны` | Открывает [[02_patterns]] |
| `покажи проекты` | Открывает [[03_projects_registry]] |
| `покажи граф` | Открывает `_generated/graph.html` |
| `пересмотри глобальный слой` | Запускает `calibrate` + `audit` |

---

**Принцип работы:** этот файл — единая точка входа в vault. Claude
всегда читает его на уровне 0–1 reading ladder. Frontmatter
обновляется автоматически при записи в любую из карт.
