# Advanced confidence calibration

> **Статус:** 🚧 Заглушка. Будет развёрнута в v1.4.0.

## Назначение

Расширенные методы калибровки уверенности в `11_confidence_scoring.md`:
beta-распределения, Brier score, Platt scaling, изотоническая
регрессия, domain-specific baselines. Выходит за пределы базовой
калибровки через `calibrate_thresholds.py`.

## Планируемое содержание

- **Текущий baseline** (v1.3.3):
  - Простая формула `confidence = correct_predictions / total_predictions`
    по домену.
  - Минимум 10 наблюдений для активации калибровки в домене.
  - Фиксированные пороги low/medium/high = 0.33/0.67/0.85.
- **Beta-распределения**: использование `Beta(α, β)` для более точного
  учёта малых выборок (α = correct + 1, β = wrong + 1).
- **Brier score** как метрика качества калибровки — сравнение
  предсказанных вероятностей с фактическими исходами.
- **Platt scaling**: линейное преобразование выходов модели в
  откалиброванные вероятности через логистическую регрессию.
- **Изотоническая регрессия**: непараметрический метод для сохранения
  монотонности.
- **Domain-specific baselines**: у каждого из 8 доменов
  (`11_confidence_scoring.md`) свой baseline, зависящий от природы
  данных (цифры vs текст vs экспертные суждения).
- **Temporal decay**: уверенность по старым наблюдениям (>90 дней)
  весит меньше через экспоненциальное затухание.
- **Cross-domain transfer**: как использовать калибровку одного домена
  для bootstrap другого при недостатке данных.

## Текущее поведение (v1.3.3)

- `calibrate_thresholds.py` обновляет пороги `systemic_threshold`,
  `pattern`, `pattern_window_days`, `min_occurrences` по простым
  эвристикам из `12_cross_project_graph.md`.
- Callbacks в `11_confidence_scoring.md` вручную обновляются
  пользователем после каждой подтверждённой/опровергнутой гипотезы.
- Нет автоматического пересчёта confidence scores по beta/Brier.

## Связанные

- [[11_confidence_scoring]] — карточка с текущими baseline по 8 доменам.
- [[calibrate]] — action-скилл пересчёта порогов.
- `scripts/calibrate_thresholds.py` — текущая реализация.
- [[verification-core]] — механизм №14 «оценка уверенности»
  использует эти baselines.

## Roadmap

- v1.4.0 — переход на beta-распределения для доменов с <30 наблюдениями.
- v1.5.0 — интеграция Brier score в self-reflection отчёты.
- v2.0.0 — полный байесовский пайплайн с priors из
  [[07_global_entities]] и posteriors в [[11_confidence_scoring]].
