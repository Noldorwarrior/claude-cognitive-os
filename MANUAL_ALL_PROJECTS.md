---
title: Ручной обход всех проектов через claude-cognitive-os
version: 1.1 (для плагина v1.3.8)
created: 2026-04-21
updated: 2026-04-23
scope: Пошаговая инструкция как вручную прогнать полный цикл плагина по всем проектам из реестра за одну сессию
---

# Ручной обход всех проектов через claude-cognitive-os

**Что значит «применить плагин для всех проектов сразу»:**
Прогнать один полный цикл — статус → health → инвентаризация proj-NNN → обновление статусов → рефлексия → паттерны → калибровка → архивация → граф/backlinks → финальная верификация — для всех проектов, зарегистрированных в `cognitive_os/03_projects_registry.md`.

**Когда делать:**
- Раз в 30 дней (плановая регенерация всей карты).
- После серии закрытых крупных задач в разных проектах.
- Перед релизом / аудитом / сверкой.
- После миграции версии плагина.

**Когда НЕ делать:**
- В сессии с единичной узкой задачей по одному проекту — хватит `claude-cognitive-os:status` + точечного `reflect` по нужному proj.
- Сразу после предыдущего полного обхода (<7 дней) — избыточно, только калибровка/архивация по расписанию.

---

## 0. Pre-flight (один раз в начале сессии)

### 0.1. Открой воркспейс в новом окне

```
прочти /Users/noldorwarrior/Documents/Claude/cognitive_os/00_index.md и /Users/noldorwarrior/Documents/Claude/cognitive_os/03_projects_registry.md,
затем запусти ручной обход всех проектов по /Users/noldorwarrior/Documents/Claude/dev/claude-cognitive-os/MANUAL_ALL_PROJECTS.md
```

### 0.2. Проверь, что версия плагина совпадает с ожидаемой

```bash
cat /Users/noldorwarrior/Documents/Claude/dev/claude-cognitive-os/.claude-plugin/plugin.json | grep version
```

Если плагин в Cowork ниже манифеста — сначала апгрейд (drag & drop `.plugin` файла), иначе часть скиллов может работать по старому контракту.

### 0.3. Сохрани baseline состояния ДО обхода

```bash
cd /Users/noldorwarrior/Documents/Claude/cognitive_os
PYTHONHASHSEED=42 python3 scripts/check.py all | tee /tmp/cog_before.txt
```

Это нужно чтобы в конце показать diff (что изменилось за сессию).

---

## Шаг 1. Статус воркспейса

**Цель:** одна сводка — какие карточки есть, счётчики, последние события, open-ошибки, open-audits.

**Как:**
Вызов скилла в чате:

```
claude-cognitive-os:status
```

Либо прямое чтение `cognitive_os/00_index.md`. Скилл легковесный, только читает.

**Что зафиксировать на этом шаге:**
- Число active патт/механизмов/ошибок/уроков.
- Даты последней калибровки, архивации, аудита.
- Если хоть одна из них > 30 дней — пометь в TODO сессии (будут шаги 7, 8, 10).

---

## Шаг 2. Полная health-check всей карты

**Цель:** sync + audit + graph за один проход; выявить DANGLING/orphans/duplicates/status_drift ДО того как менять проекты.

**Как:**
```bash
cd /Users/noldorwarrior/Documents/Claude/cognitive_os
PYTHONHASHSEED=42 python3 scripts/check.py all
```

**Критерии зелёного старта:**
- sync: PASS, все счётчики ✅.
- audit: total=0 findings.
- graph: 0 dangling / 0 warnings.

**Если что-то красное:**
1. DANGLING link → найти в карточке, привести к каноническому формату `[[NN_card#id]]` или удалить ссылку.
2. status_drift → сверить статус в самой записи (field `status:`) и в счётчике `00_index`.
3. duplicates → слить две записи, оставить меньший ID, обновить ссылки.
4. orphans → либо заархивировать запись, либо добавить ссылку хотя бы из одной карточки.

**Не переходи к Шагу 3, пока check.py all не зелёный.**

---

## Шаг 3. Инвентаризация проектов

**Цель:** составить рабочий список — все `proj-NNN`, их статус сейчас, что изменилось со времени последнего касания.

**Как:**
Прочитать `03_projects_registry.md` целиком. Для каждого проекта заполнить табличку (в чате или в temp-файле):

| ID | Название | Status | Last touched | Новых событий с тех пор | CLAUDE.md есть? | Действие |
|----|----------|--------|--------------|-------------------------|-----------------|----------|

**Где взять "Last touched":**
- Поле `last_event` в записи `proj-NNN`.
- Или git-лог файлов в `projects/<name>/` если проект имеет рабочую папку.

**Возможные значения "Действие":**
- `refresh` — статус в порядке, нужен только reflect и обновление last_event.
- `status_change` — статус устарел (planned → active, active → completed/paused).
- `content_init` — заглушка получила первый контент, нужна перерегистрация + инициализация wiki/index.
- `archive` — проект закрыт > 90 дней назад, переносить в `archive/projects/`.
- `skip` — никаких изменений с прошлого обхода, ничего не делаем.

**Пример для текущего воркспейса (2026-04-21):**
- `proj-012 Supermemory` → status_change пока нет, остаётся `active (инфраструктурный)`; при наличии контента в `Projects/Supermemory/` — `content_init`.
- `proj-013 Jarvis` → planned остаётся; при появлении файлов в `raw/` — `content_init` с инициализацией `wiki/index.md` и `wiki/log.md`.
- Остальные (proj-001..011) — по факту последнего касания.

---

## Шаг 4. Обновление статусов и карточек проектов

**Цель:** привести `03_projects_registry.md` и `CLAUDE.md` каждого проекта к текущей реальности.

**Для каждого `proj-NNN` с действием ≠ `skip`:**

### 4.1. Если `refresh`:
В записи `proj-NNN` обновить:
- `last_event: 2026-04-21 [суть события]`
- Если есть новые задачи/артефакты — добавить в соответствующее поле.
- Счётчик `00_index` трогать не нужно (число active не меняется).

### 4.2. Если `status_change`:
- Изменить поле `status:` в записи.
- В `00_index.md` → таблица «Счётчики порогов» → обновить число active projects по категориям (если разбивка есть).
- В «Последние события» 00_index → добавить строку:
  `2026-04-21 | proj-NNN смена статуса X → Y | Причина`

### 4.3. Если `content_init` (заглушка → рабочая):
- В `proj-NNN`: `status: planned/active инфраструктурный` → `active`.
- Инициализировать `Projects/<name>/wiki/index.md` карту вольта (если это second-brain-подобный проект, например Jarvis).
- Инициализировать `Projects/<name>/wiki/log.md` как журнал событий с первой записью от сегодняшней даты.
- Обновить `CLAUDE.md` в корне проекта: снять пометку «заглушка», описать реальный контент.
- В 00_index «Последние события»: `proj-NNN наполнение — инициализация wiki/`.

### 4.4. Если `archive`:
- В `proj-NNN`: `status: archived`, добавить `archived_at: 2026-04-21` и причину.
- Переместить карточку целиком в раздел «Архивные проекты» в том же `03_projects_registry.md` (или отдельным скиллом — см. Шаг 8).

**Важно:** одна правка = один осознанный commit мысли. Если проектов много (>5 требуют действия) — после каждой правки 03_projects_registry запускай sync_check и подтверждай PASS. Иначе счётчики разъедутся.

---

## Шаг 5. Рефлексия по сессии

**Цель:** зафиксировать sr-NNN за текущую сессию — 8 осей + извлечение уроков + калибровка уверенности.

**Как:**
Вызов скилла:

```
claude-cognitive-os:reflect
```

Скилл сам:
1. Создаст запись `sr-NNN` в `13_self_reflection.md` с оценкой по 8 осям (цель, план, исполнение, коммуникация, качество, эффективность, этика, калибровка).
2. Предложит 2-5 уроков → допишет в `06_lessons_learned.md`.
3. Если есть ошибки — создаст `ec-NNN` в `10_error_corrections.md`.
4. Обновит калибровку в `11_confidence_scoring.md`.

**Что важно ПЕРЕД вызовом:**
- В диалоге явно перечислить «что было сделано в сессии» — скилл это использует как вход.
- Если обход коснулся >3 проектов — попросить скилл явно разделить уроки по доменам (tool_usage / behavior / calibration), чтобы потом они кластеризовались для Шага 6.

---

## Шаг 6. Извлечение паттернов и принципов

**Цель:** проверить, не накопилось ли 3+ уроков на одну тему → promotion до `pat-NNN` + возможный `md-NNN` + `wm-NNN` (механизм защиты).

**Как:**
Вызов скилла:

```
claude-cognitive-os:patterns
```

Скилл:
1. Пройдёт по `06_lessons_learned.md` и `09_protective_mechanisms.md`.
2. Найдёт кластеры ≥ `thresholds.pattern` (по умолчанию 3 уроков в окне `thresholds.pattern_window_days`).
3. Предложит создать `pat-NNN` с указанием confidence (provisional, если все кейсы в одной сессии).
4. Если кластеров ≥ `extract_principle_min` на одну тему → предложит `md-NNN` как meta-decision.
5. Если уязвимость повторная → предложит `wm-NNN` с 4-6 шаговой процедурой защиты.

**Правило для новых pat-NNN:**
- Если 3+ кейса в **одной** сессии → `confidence: 0.X provisional`. Снимается при 4-м кейсе в другой сессии.
- Если кейсы из разных сессий → `confidence` обычный, не provisional.

**После создания:**
- Счётчики `00_index.patterns/mechanisms/meta_decisions` обновить вручную (скилл покажет какие).
- Уроки, вошедшие в кластер, перевести `active → promoted_to_pattern`.

---

## Шаг 7. Калибровка

**Цель:** сверить заявленную и фактическую уверенность по доменам; при overconfidence — понизить планку или включить обязательную П5.

**Как:**
Вызов скилла:

```
claude-cognitive-os:calibrate
```

Или напрямую:

```bash
cd /Users/noldorwarrior/Documents/Claude/cognitive_os
PYTHONHASHSEED=42 python3 scripts/calibrate_thresholds.py
```

**Что смотреть:**
- Колонка MAE по доменам. Если MAE > 0.15 → домен миска-калиброван.
- Overconfidence > 0.1 → заявленная уверенность выше фактической → автоматически включить П5 для этого домена в следующей сессии.
- Underconfidence > 0.1 → наоборот, можно ослабить верификацию.

**Результат:**
- Запись обновляется в `11_confidence_scoring.md`.
- При смене порога обновляется `00_index.thresholds.*`.
- В «Последние события» 00_index: `2026-04-21 калибровка: domain-NNN MAE 0.12 → 0.08, overconfidence снят`.

**Пропустить, если:** последняя калибровка была < 14 дней назад И ни один домен не показал новые overconfidence-случаи.

---

## Шаг 8. Архивация устаревшего

**Цель:** очистить active-слой от записей со статусом `archived` — перенести их в `archive/` с сохранением ID и backlinks.

**Как:**
Вызов скилла:

```
claude-cognitive-os:archive
```

Скилл:
1. Пройдёт по всем карточкам 00-14.
2. Соберёт записи `status: archived`.
3. Покажет кандидатов таблицей (ID, тип, причина, дата архивации, сколько backlinks).
4. Попросит подтверждения — что переносить сейчас, что оставить.
5. Переместит в `archive/<card_name>/<id>.md` с сохранением frontmatter.
6. Обновит счётчики в 00_index.

**Ручной контроль:** если у кандидата >5 входящих backlinks из active-слоя — проверь, не сломает ли архивация логику. Иногда лучше оставить со статусом `inactive` вместо `archived`.

---

## Шаг 9. Регенерация графа и backlinks

**Цель:** получить свежую картинку связей + список входящих ссылок для каждого ID.

**Как:**

```bash
# Backlinks — полный индекс «кто ссылается на NNN»
cd /Users/noldorwarrior/Documents/Claude/cognitive_os
PYTHONHASHSEED=42 python3 /Users/noldorwarrior/Documents/Claude/dev/claude-cognitive-os/scripts/render_backlinks.py \
  --workspace /Users/noldorwarrior/Documents/Claude/cognitive_os

# Граф — vis-network HTML + mermaid
PYTHONHASHSEED=42 python3 scripts/render_graph.py \
  --workspace /Users/noldorwarrior/Documents/Claude/cognitive_os
PYTHONHASHSEED=42 python3 scripts/render_mermaid.py \
  --workspace /Users/noldorwarrior/Documents/Claude/cognitive_os
```

Либо одним вызовом:

```
claude-cognitive-os:graph
claude-cognitive-os:backlinks
```

**Что проверить на графе:**
- Узлы-сироты (0 connections) → либо удалить, либо добавить хотя бы 1 ссылку.
- Висячие рёбра красным (conflict-edges) — это нерешённые противоречия из `14_audit_log`.
- Кластеры, появившиеся в этой сессии (pat-009/010, md-009, wm-109 в текущем воркспейсе) должны быть связаны минимум с одним proj-NNN и одним lesson/ec.

**Важное различие (уже встретилось ранее):**
- `render_backlinks.py` использует более либеральный набор ID-паттернов, показывает больше «висячих» (116 в текущем воркспейсе).
- `audit_contradictions.py` — строгий, выдаёт 0 dangling.
- Расхождение — не противоречие, а разные масштабы. В инструкции ориентируемся на audit=0 как критерий зелёного.

---

## Шаг 10. Финальная верификация

**Цель:** подтвердить что обход не сломал инварианты.

### 10.1. Повторный check.py all

```bash
cd /Users/noldorwarrior/Documents/Claude/cognitive_os
PYTHONHASHSEED=42 python3 scripts/check.py all | tee /tmp/cog_after.txt
diff /tmp/cog_before.txt /tmp/cog_after.txt
```

**Критерии:**
- sync: PASS.
- audit: total=0 (или только новые info-findings о новых promotion'ах, но без low/medium/high).
- graph: 0 dangling.

### 10.2. Верификационный пресет для всей сессии

Если обход был существенным (изменено >3 проектов, созданы pat/md/wm, вызвана калибровка) — запусти полную верификацию:

```
claude-cognitive-os:audit
```

Скилл вызовет `cog-verifier` по пресету П13 «Аудитор». Пройдёт:
- Цепочка происхождения изменений.
- Декомпозиция фактов.
- Триангуляция (сверка 00_index ↔ карточка ↔ 12_graph).
- Эпистемический статус каждой новой записи.
- Поиск парадоксов и скрытых допущений.
- Метаморфическое тестирование (если счётчик patterns 8→10, то audit_contradictions тоже должен видеть +2 pat).
- Границы (что НЕ покрыто этой сессией).

### 10.3. Финальный отчёт в чате

В конце сессии запиши краткий summary:
- Сколько проектов обработано / refresh / status_change / content_init / archive / skip.
- Какие новые pat/md/wm созданы.
- Какой sr-NNN создан.
- Калибровка: MAE до/после по ключевым доменам.
- Архивировано: сколько записей, по каким карточкам.
- Финальный sync sha (не как baseline, а как отметка времени).

---

## Чек-лист: порядок за один проход

```
☐ 0.1  Открыл воркспейс и прочитал 00_index + 03_projects_registry
☐ 0.2  Версия плагина совпадает с манифестом
☐ 0.3  Сохранил baseline (check.py all → /tmp/cog_before.txt)

☐ 1    status: сводка карточек, счётчики, последние события
☐ 2    health: check.py all → всё зелёное
☐ 3    Инвентаризация: таблица по всем proj-NNN (ID, status, last_touched, действие)
☐ 4    Обновление карточек проектов (refresh / status_change / content_init / archive)
        ☐ 4.x После каждой правки 03_projects_registry — sync_check PASS
☐ 5    reflect: новый sr-NNN за сессию
☐ 6    patterns: кластеризация уроков → pat/md/wm
☐ 7    calibrate: пересмотр порогов и overconfidence (если > 14 дней или новые сигналы)
☐ 8    archive: перенос записей со статусом archived в archive/
☐ 9    graph + backlinks: регенерация _generated/
☐ 10.1 Повторный check.py all → зелёное
☐ 10.2 audit (П13 «Аудитор») — если сессия существенная
☐ 10.3 Финальный summary в чате
```

---

## Оценка времени

- Воркспейс с ≤5 проектами и без крупных изменений → 20-30 минут.
- Воркспейс с 10+ проектами, 3+ status_change, калибровка, извлечение паттернов → 60-90 минут.
- Плюс к этому — сколько диалога нужно чтобы сверить действия по каждому proj-NNN с пользователем (минимум по 2-3 реплики на неочевидный case).

---

## Частые ошибки и как их не сделать

1. **Пропустить Шаг 2 (health) и сразу править проекты.**
   Итог: DANGLING link, который был ДО сессии, будет списан на правки текущей сессии. Всегда фиксируй зелёный baseline перед обходом.

2. **Менять счётчики в 00_index «по памяти».**
   Источник истины — `md-008 «00_index — центральный регистр, все active-счётчики = реальности»`. После любой правки active-записи → обязательный sync_check.

3. **Обновлять `last_event` без обновления `last_touched`.**
   Это разные поля: `last_event` = суть, `last_touched` = дата для сортировки в инвентаризации.

4. **Создавать pat-NNN с confidence > 0.8, когда все кейсы из одной сессии.**
   Такие паттерны должны быть provisional. Снятие флага только при 4-м независимом кейсе.

5. **Запускать calibrate чаще, чем раз в 14 дней без новых сигналов.**
   Шум оценок превысит сигнал. Калибровка — тяжёлый инструмент.

6. **Архивировать proj-NNN с входящими backlinks из active-слоя без правки этих ссылок.**
   Правило: сначала убрать все active→archived ссылки (заменить на `archive/proj-NNN` путь), только потом перенос.

---

## Быстрый один-лайнер для «всё сразу» (только если уверен)

```bash
cd /Users/noldorwarrior/Documents/Claude/cognitive_os && \
PYTHONHASHSEED=42 python3 scripts/check.py all && \
PYTHONHASHSEED=42 python3 scripts/calibrate_thresholds.py && \
PYTHONHASHSEED=42 python3 /Users/noldorwarrior/Documents/Claude/dev/claude-cognitive-os/scripts/render_backlinks.py --workspace . && \
PYTHONHASHSEED=42 python3 scripts/render_graph.py --workspace . && \
PYTHONHASHSEED=42 python3 scripts/render_mermaid.py --workspace . && \
PYTHONHASHSEED=42 python3 scripts/check.py all
```

**НЕ подменяет ручные шаги 3-6**, потому что они требуют суждения (инвентаризация, обновление карточек, рефлексия, кластеризация). Этот one-liner — только автоматизированная часть.

---

**Конец инструкции. При существенных изменениях плагина версия документа обновляется (сейчас 1.1 для v1.3.8).**
