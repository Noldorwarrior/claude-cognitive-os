# Миграция с cognitive-os v1.0.1 → v1.3.0-plugin

## Что изменилось

### Архитектура

- **v1.0.1** — один skill `cognitive-os` с встроенной логикой.
- **v1.3.0** — полноценный плагин: action-скиллы + reference-скиллы +
  субагенты + скрипты + hooks.

### Структура воркспейса

| v1.0.1 (18 карт) | v1.3 (15 карт) |
|---|---|
| `00_index.md` | `00_index.md` |
| `01_user_profile.md` | `01_user_profile.md` |
| `02_patterns.md` | `02_patterns.md` |
| `03_projects_registry.md` | `03_projects_registry.md` |
| `04_meta_decisions.md` | `04_meta_decisions.md` |
| `05_global_glossary.md` | `05_global_glossary.md` |
| `06_lessons_learned.md` | `06_lessons_learned.md` |
| `07_global_entities.md` | `07_global_entities.md` |
| `08_knowledge_maps.md` | `08_knowledge_maps.md` |
| `09_working_mechanisms.md` | `09_working_mechanisms.md` |
| `10_error_corrections.md` | `10_error_corrections.md` |
| `11_confidence_scoring.md` | `11_confidence_scoring.md` |
| `12_cross_project_graph.md` | `12_cross_project_graph.md` |
| `13_self_reflection.md` | `13_self_reflection.md` |
| `14_audit_log.md` | `14_audit_log.md` |
| `15_calibration.md` | **merged → `11_confidence_scoring`** |
| `16_templates.md` | **moved → `templates/` directory** |
| `17_integration.md` | **moved → `references/integration.md`** |

- 3 карты схлопнулись в ядро / вынесены в поддерживающие файлы.
- Все ID (`pat-NNN`, `wm-NNN` и т.д.) **сохраняются без изменений**.

### Wikilinks

- Старые: `[[15_calibration#pat-calibration-001]]` → новые:
  `[[11_confidence_scoring#pat-calibration-001]]`.
- Остальные ссылки не меняются.

### Frontmatter

v1.3 добавляет обязательные поля в карточки:

```yaml
---
version: 1.3
migrated_from: 1.0.1
migration_date: 2026-04-20
---
```

## Подготовка

### 1. Бэкап

Обязательный шаг. Миграция делает свой бэкап, но дублирующий ваш
собственный страхует от проблем.

```bash
cp -r /path/to/cognitive-os /path/to/cognitive-os-backup-pre-v1.3
```

### 2. Проверка v1.0.1 целостности

Убедитесь, что:
- Все 18 карт существуют.
- Wikilinks не битые.
- Есть активная frontmatter с version: 1.0.1 в 00_index.

### 3. Установка плагина v1.3

```bash
claude plugin install claude-cognitive-os
```

## Запуск миграции

### Вариант А: интерактивный

В Claude:

> мигрируй воркспейс из /path/to/cognitive-os v1.0.1 в v1.3

Скилл [[migrate]] пройдёт диалог:
1. Подтверждение пути и бэкапа.
2. Показ плана изменений (dry-run).
3. Запуск с П14 верификацией.

### Вариант B: неинтерактивный

```bash
# Dry-run для превью
python3 scripts/migrate_workspace.py \
  --from /old/path \
  --to /new/path \
  --dry-run

# Применение
python3 scripts/migrate_workspace.py \
  --from /old/path \
  --to /new/path
```

## Что делает миграция (шаг за шагом)

### Шаг 1: Валидация источника

- Все 18 карт присутствуют.
- Версия в frontmatter — 1.0.1.
- Счётчики в 00_index корректны (через sync_check.py).

### Шаг 2: Бэкап

Копия в `<new>/archive/.backup/pre-migration-{{DATE}}/`.

### Шаг 3: Копирование карт 00-14

Карты 00-14 копируются с:
- Обновлённым frontmatter (version: 1.3).
- Исправленными wikilinks (если где-то были `[[15_calibration]]`).

### Шаг 4: Merge 15_calibration → 11_confidence_scoring

Содержимое `15_calibration.md` переносится в `11_confidence_scoring.md`
под разделом **«История калибровок (из v1.0.1)»**.

IDs типа `calibration-001` переоформляются в `pat-calibration-001`
(сохраняется в том же файле).

### Шаг 5: Перенос 16_templates → templates/

Шаблоны извлекаются из `16_templates.md` и раскладываются в
`templates/<card>.template.md` по соответствию.

### Шаг 6: Перенос 17_integration → references/

Содержимое `17_integration.md` сохраняется как
`references/integration.md` (для использования внутри
`cognitive-os-core` скилла).

### Шаг 7: Валидация целостности

- Все wikilinks из старого воркспейса resolve в новом?
- Counters обновлены?
- Нет дубликатов IDs?

### Шаг 8: П14 верификация (обязательно)

Через [[cog-verifier]]:
- М25 (регрессия): ничего не потеряно.
- М26 (дрейф смысла): определения сохранены.
- М24 (diff): изменения соответствуют плану.
- М22 (согласованность): counters, cross-references.
- М32 (ссылочная целостность): все wikilinks работают.

### Шаг 9: Отчёт

`docs/migrations/migration_v1_0_1_to_v1_3_{{DATE}}.md` с:
- Что мигрировано.
- Что потеряно / слито.
- Рекомендации по проверке.

### Шаг 10: Post-migration

- Запуск [[graph]] — перестройка визуализации.
- Запуск [[backlinks]] — пересбор индекса.
- Запуск [[audit]] `--sync-only` — финальная проверка.

## Откат (rollback)

Если миграция не удалась или вам не нравится результат:

```bash
# Восстановление из автобэкапа
rm -rf /new/path
cp -r /old/path /new/path
# Или из вашего бэкапа:
cp -r /path/to/cognitive-os-backup-pre-v1.3 /path/to/cognitive-os
```

Migration создаёт `audit-NNN` типа `migration` — по нему можно
отследить что и когда было сделано.

## Частые проблемы

### 1. «Невалидный frontmatter в v1.0.1»

Добавьте в начало каждой карты:
```yaml
---
version: 1.0.1
type: card
---
```

### 2. «Ссылки на `[[15_calibration#X]]` не работают после миграции»

Миграция должна их автоматически переписать. Если нет — запустите:

```bash
python3 scripts/fix_wikilinks.py --workspace /new/path \
  --rename "15_calibration:11_confidence_scoring"
```

### 3. «Хуки не срабатывают»

После миграции обновите `~/.claude/cognitive-os-workspaces.json` — путь
мог измениться:

```json
{
  "active": "/new/path",
  "workspaces": [
    {"path": "/new/path", "name": "My Cognitive OS", "version": "1.3"}
  ]
}
```

### 4. «Слишком много висячих ссылок»

Вариант 1: запустите [[audit]] `--broken-links-only` — скилл поможет
разобрать каждую.

Вариант 2: если битые ссылки были и в v1.0.1 — они зафиксируются как
`audit-NNN` типа `regression_inherited`.

## Проверка после миграции

Чеклист:

- [ ] 15 карт существуют.
- [ ] `00_index.counters` совпадают с фактическим количеством.
- [ ] `sync_check.py` возвращает 0 errors.
- [ ] `render_backlinks.py` — висячих ссылок не больше, чем было в v1.0.1.
- [ ] `render_graph.py` — граф рисуется.
- [ ] Запрос [[status]] выдаёт адекватную картину.

## Связанное

- [[architecture]] — общая архитектура плагина.
- [[quick_start]] — работа после установки.
- [[migrate]] — action-скилл миграции.
- [[cog-verifier]] — субагент верификации (П14).
