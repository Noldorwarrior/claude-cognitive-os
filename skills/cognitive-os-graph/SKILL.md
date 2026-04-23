---
name: cognitive-os-graph
description: >-
  Reference-скилл для визуализации когнитивного воркспейса. Описывает, как
  правильно использовать скрипты `render_graph.py`, `render_backlinks.py`,
  `render_mermaid.py` из `scripts/`. Загружается автоматически, когда
  action-скиллы [[graph]] или [[backlinks]] запускают рендер. Содержит
  справочник цветовой палитры, стилей рёбер, параметров фильтрации,
  рекомендации по производительности и примеры интерпретации графа.
---

# cognitive-os-graph — Reference визуализации

## Назначение

Reference-скилл (не action). Объясняет:
- Какие скрипты запускать для каких задач.
- Какую цветовую палитру применяем (согласованность с [[graph]] SKILL).
- Как читать граф (типы узлов, стили рёбер).
- Как ускорить рендер на больших воркспейсах.

Не запускается напрямую пользователем — подгружается action-скиллами
[[graph]] и [[backlinks]].

## Скрипты в `scripts/`

| Скрипт | Что делает | Когда использовать |
|---|---|---|
| `render_graph.py` | Полный рендер HTML + mermaid | Post-write hook на карточки, команда `graph` |
| `render_backlinks.py` | Сбор обратных ссылок | Команда `backlinks`, детект висячих |
| `render_mermaid.py` | Только mermaid | Быстрая перерисовка, документация |

## Унифицированные параметры

Все скрипты принимают `--workspace <path>` — путь к папке воркспейса
(cognitive_os/).

## render_graph.py

### Режимы

```bash
# Полный граф
python3 render_graph.py --workspace /path/to/cognitive_os

# Ego-граф одного проекта (соседи на расстоянии 2)
python3 render_graph.py --workspace /path/to/cognitive_os --project proj-001

# Только conflict-edges и их концы
python3 render_graph.py --workspace /path/to/cognitive_os --conflict-only

# Только mermaid (без HTML)
python3 render_graph.py --workspace /path/to/cognitive_os --mermaid-only

# Только HTML
python3 render_graph.py --workspace /path/to/cognitive_os --html-only
```

### Выход

- `<workspace>/_generated/graph.html` — интерактивный граф на vis-network.
- `<workspace>/_generated/graph.mermaid` — статический mermaid.

### Цветовая палитра

| Тип узла | Префикс ID | Цвет |
|---|---|---|
| project | `proj-` | `#4A90E2` (синий) |
| entity | `ent-` | `#27AE60` (зелёный) |
| pattern | `pat-` | `#E67E22` (оранжевый) |
| mechanism | `wm-` | `#F1C40F` (жёлтый) |
| error | `ec-` | `#E74C3C` (красный) |
| knowledge | `km-` | `#8E44AD` (фиолетовый) |
| lesson | `lesson-` | `#95A5A6` (серый) |
| meta | `md-` | `#34495E` (тёмно-серый) |
| term | `term-` | `#7F8C8D` (средне-серый) |
| domain | `domain-` | `#1ABC9C` (бирюзовый) |
| cluster | `cluster-` | `#9B59B6` (пурпурный) |
| reflection | `sr-` | `#BDC3C7` (светло-серый) |
| audit | `audit-` | `#C0392B` (тёмно-красный) |

### Стили рёбер

| Тип ребра | Стиль |
|---|---|
| `link` (обычная wikilink) | сплошная, серая |
| `conflict` (из audit_log) | красная толстая с подписью «конфликт» |
| `shared_domain` | пунктир |

## render_backlinks.py

### Режимы

```bash
# Полный rebuild
python3 render_backlinks.py --workspace /path/to/cognitive_os

# Только для одного ID
python3 render_backlinks.py --workspace /path/to/cognitive_os --id pat-007

# Только висячие ссылки
python3 render_backlinks.py --workspace /path/to/cognitive_os --broken

# Только изолированные узлы (без входящих)
python3 render_backlinks.py --workspace /path/to/cognitive_os --orphans

# В stdout без записи файла
python3 render_backlinks.py --workspace /path/to/cognitive_os --stdout
```

### Выход

- `<workspace>/_generated/backlinks.md` — текстовый индекс.

### Как читать

- Секция по каждому типу ID.
- Внутри каждой записи — список мест, откуда ссылаются.
- Формат: `from_file:line_number` + опц. `(via alternate_target)`.
- Секция **«Висячие ссылки»** в конце — то, что требует внимания
  (может быть в `14_audit_log`).

## render_mermaid.py

Обёртка над render_graph.py в режиме `--mermaid-only`. Быстрый способ
получить текстовый граф.

```bash
python3 render_mermaid.py --workspace /path/to/cognitive_os
python3 render_mermaid.py --workspace /path/to/cognitive_os --stdout
```

## Производительность

| Размер воркспейса | Рендер graph.html | Рендер backlinks.md |
|---|---|---|
| < 100 узлов | < 1 сек | < 1 сек |
| 100-500 | 1-3 сек | 1-2 сек |
| 500-2000 | 3-10 сек | 2-5 сек |
| > 2000 | **используй пагинацию** | ок |

Для воркспейсов > 2000 узлов:
- Рендер по доменам: `--domain=<domain>` (планируемая опция v1.4+).
- Или разбить воркспейс на несколько (отдельные организационные контексты).

## Интеграция с hooks

`hooks/hooks.json` содержит post-write триггеры:

```json
{
  "hooks": [
    {
      "event": "post-write",
      "match": ["**/0[0-9]_*.md", "**/1[0-4]_*.md", "projects/**/*.md"],
      "debounce_seconds": 3,
      "command": "python3 scripts/render_graph.py --workspace ${CLAUDE_WORKSPACE}",
      "also": "python3 scripts/render_backlinks.py --workspace ${CLAUDE_WORKSPACE}"
    }
  ]
}
```

Debounce 3 сек защищает от лавины перерисовок при массовых правках.

Дополнительная mtime-проверка внутри скриптов: если ни один входной
файл не менялся с момента последнего запуска — skip.

## Интеграции

- [[graph]] — action-скилл, зовёт render_graph.py.
- [[backlinks]] — action-скилл, зовёт render_backlinks.py.
- [[cog-detector]] — субагент, триггерящий перерисовку.
- [[audit]] — потребитель висячих ссылок.
- [[cognitive-os-core]] — общие правила.

## Частые ошибки

1. **Workspace путь неверный** → скрипт выходит с код 1. Проверка в
   начале main().
2. **Vis-network не загрузился** (CDN недоступен) → граф не интерактивный.
   Fallback: mermaid в `graph.mermaid`.
3. **Очень большой граф** → браузер тормозит. Решение: ego-графы
   (`--project`) или фильтр conflict-only.

## Связанные

- [[graph]], [[backlinks]] — action-скиллы.
- [[cog-detector]] — subagent-триггер.
- [[cognitive-os-core]] — корневые правила.
- `hooks/hooks.json` — где прописаны триггеры.
