---
name: cognitive-os-calibration
description: >-
  Reference-скилл для self-learning системы когнитивного воркспейса.
  Описывает использование скриптов `calibrate_thresholds.py`,
  `extract_principles.py`, `sync_check.py`. Содержит методологию
  калибровки, формулы MAE / overconfidence, правила промоушена
  wm→md, интерпретацию sync-отчётов. Загружается action-скиллами
  [[calibrate]], [[patterns]], [[audit]].
---

# cognitive-os-calibration — Reference self-learning

## Назначение

Объясняет, как работает автоматическое обучение воркспейса:
- Калибровка порогов уверенности.
- Извлечение принципов из механизмов.
- Проверка синхронизации данных.

Не action-скилл — подгружается при запуске [[calibrate]], [[patterns]],
[[audit]] для методологической базы.

## Скрипты в `scripts/`

| Скрипт | Что делает | Когда использовать |
|---|---|---|
| `calibrate_thresholds.py` | Анализ confidence vs actual | [[calibrate]], раз в 30 дней |
| `extract_principles.py` | Кандидаты wm→md | [[patterns]] в режиме promotion |
| `sync_check.py` | Проверка целостности | [[audit]], pre-release, hook |

## calibrate_thresholds.py

### Методология

1. **Сбор данных.** Парсим `11_confidence_scoring.md` — таблицы вида:
   ```
   | task_id | domain | predicted | actual | delta |
   ```
2. **Агрегирование.** По каждому домену считаем:
   - `mean_predicted` — средняя уверенность до выполнения.
   - `mean_actual` — средняя итоговая оценка.
   - `MAE` = mean(|delta|) — средняя абсолютная ошибка.
   - `overconfidence_rate` = fraction(predicted > actual).
   - `underconfidence_rate` = fraction(predicted < actual).

3. **Классификация домена.**
   - `critical_underperformance`: mean_actual < 0.7 → **П5 обязателен**.
   - `overconfidence`: overconfidence_rate > 0.6 → снизить default_confidence.
   - `underconfidence`: underconfidence_rate > 0.6 → поднять.
   - `well_calibrated`: иначе.

4. **Корректировка порогов.** Предложение = `-mean_delta`
   (если переоценка систематически +0.10, то сдвигаем default_confidence
   на -0.10).

### Параметры

| Флаг | Default | Описание |
|---|---|---|
| `--min-tasks` | 5 | Минимум записей для надёжной калибровки |
| `--window-days` | ∞ | Окно анализа, по умолчанию все данные |
| `--domain X` | — | Только один домен |

### Пример

```bash
python3 calibrate_thresholds.py --workspace . --window-days 90
```

Отчёт: `_generated/calibration_report.md`.

### Интерпретация

- `MAE < 0.10` — отличная калибровка, не трогать.
- `MAE 0.10-0.20` — приемлемо, мягкая корректировка.
- `MAE > 0.20` — систематическое смещение, жёсткая корректировка.
- `mean_actual < 0.7` — **критично**, активировать П5.

## extract_principles.py

### Методология промоушена

Цепочка: observation → pat-NNN → wm-NNN → md-NNN.

**pat-NNN → wm-NNN:** механизм становится `working_mechanism`, когда он
применяется в 3+ проектах с успехом (это делает [[patterns]]).

**wm-NNN → md-NNN:** принцип (meta-decision) выделяется, когда:
1. Применяемость `applied_count ≥ 3` (настраивается `--min-applied`).
2. Есть кластер из 2+ wm-NNN с общим семантическим ядром.
3. Пересечение ключевых терминов ≥ 3 (настраивается `--min-overlap`).

### Алгоритм

1. Парсинг `09_working_mechanisms.md` — все wm-NNN с их content.
2. Подсчёт `applied_count` — упоминания wm-ID в других карточках и
   проектах (исключая сам источник).
3. Извлечение keywords (top-10 частых слов, без stopwords).
4. Кластеризация по пересечению keywords.
5. Для каждого кластера — кандидат md-NNN с:
   - source_mechanisms
   - shared_keywords
   - confidence = min(1.0, total_applications / 20)

### Параметры

| Флаг | Default | Описание |
|---|---|---|
| `--min-applied` | 3 | Порог применимости |
| `--min-overlap` | 3 | Мин. общих ключевых слов |
| `--json` | — | Машиночитаемый вывод |

### Пример

```bash
python3 extract_principles.py --workspace . --min-applied 5
```

Отчёт: `_generated/principle_candidates.md`.

### Важно

- **Ничего не создаёт в продовых карточках.** Только кандидаты.
- **Финальный промоушен** — через [[patterns]] с ручным одобрением и
  П12 «Стратег» верификацией.

## sync_check.py

### Что проверяется

1. **Counters consistency:** `00_index.counters` vs фактический count
   записей по префиксам.
2. **Duplicate IDs:** один и тот же `pat-003` в двух разных файлах.
3. **ID gaps:** пропуски в нумерации > 10 (info-level).
4. **Frontmatter validity:** YAML парсится без ошибок.
5. **Thresholds sync:** пороги в references/thresholds.md vs 00_index.

### Severity

- **🔴 error:** duplicate IDs, невалидный frontmatter.
- **🟡 warning:** counter mismatch, missing counter.
- **ℹ️ info:** ID gaps, missing threshold declarations.

### Параметры

| Флаг | Default | Описание |
|---|---|---|
| `--report-only` | — | Отчёт без exit 1 |
| `--strict` | — | Exit 1 при любых issues |
| `--stdout` | — | Вывод в stdout |

### Пример

```bash
# В hook (на ошибках exit 1)
python3 sync_check.py --workspace $CLAUDE_WORKSPACE

# Для отчёта без остановки
python3 sync_check.py --workspace $CLAUDE_WORKSPACE --report-only
```

Отчёт: `_generated/sync_report.md`.

## Цикл self-learning

```
Недельный цикл:
  daily: cog-detector hook → detector_signals.md
  weekly: [[reflect]] → sr-NNN + update 11_confidence_scoring
  weekly: sync_check.py (hook or scheduled) → sync_report.md

Месячный цикл:
  [[calibrate]] → calibration_report.md → применение порогов
  extract_principles.py → кандидаты → [[patterns]] (promotion)

Квартальный цикл:
  [[audit]] full → резолюция противоречий
  [[archive]] cold records → archive/
```

## Интеграции

- [[calibrate]] — потребитель calibrate_thresholds.py.
- [[patterns]] — потребитель extract_principles.py в режиме promote.
- [[audit]] — потребитель sync_check.py.
- [[cog-verifier]] — проверяет результаты калибровки (П3 «Бухгалтер»).
- `hooks/hooks.json` — пост-write триггеры на sync_check.
- `_generated/*` — куда пишутся отчёты.

## Производительность

| Скрипт | < 100 записей | 100-500 | 500-2000 | > 2000 |
|---|---|---|---|---|
| `calibrate_thresholds` | < 1 сек | 1-2 сек | 2-5 сек | 5-15 сек |
| `extract_principles` | < 1 сек | 1-3 сек | 3-10 сек | 10-30 сек |
| `sync_check` | < 1 сек | 1-2 сек | 2-5 сек | 5-10 сек |

## Частые ошибки

1. **Мало данных для калибровки** (`count < min_tasks`). Решение: ждать
   накопления или снизить `--min-tasks`.
2. **Слишком много кластеров** в extract_principles. Решение: поднять
   `--min-overlap`.
3. **Counter mismatch ложноположительный** из-за подсчёта упоминаний
   вместо заголовков. Решение: sync_check считает только по `###
   prefix-NNN` заголовкам.

## Связанные

- [[calibrate]], [[patterns]], [[audit]] — action-скиллы.
- [[cog-verifier]] — субагент-валидатор.
- [[11_confidence_scoring]] — источник данных калибровки.
- [[09_working_mechanisms]] — источник для extract_principles.
- [[00_index]] — counters.
- `references/thresholds.md` — централизованные пороги.
