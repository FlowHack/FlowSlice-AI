# FlowSlice AI

<p align="center">
  <img src="assets/preview.png" width="250" alt="FlowSlice AI">
</p>

<p align="center">
  <a href="https://github.com/OrcaSlicer/OrcaSlicer"><img src="https://img.shields.io/badge/OrcaSlicer-Plugin-181717?style=flat&logo=github&logoColor=white" alt="Orca Slicer"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white" alt="Python"></a>
  <a href="https://numpy.org/"><img src="https://img.shields.io/badge/numpy-1.26-4DABCF?logo=numpy&logoColor=white" alt="numpy"></a>
  <a href="https://github.com/FlowHack/flowslice-ai/actions/workflows/ci.yml"><img src="https://github.com/FlowHack/flowslice-ai/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

<p align="center">
  Нативный плагин для Orca Slicer: ИИ-ассистент-инженер 3D-печати.
</p>

## Возможности

- Чат с ИИ-ассистентом (персона: строгий инженер-эксперт 3D-печати)
- Контекст слайсера: модель со стола, профили принтера/пластика/настроек печати (полный дамп всех параметров, заметки профилей и start/end G-code)
- Мультичат с историей (персист в `data_dir()`), поиск, закрепление
- Команды: `/context`, `/clear`, `/model`, `/printer`, `/stats`, `/help`, `/reset`
- Стриминг ответов (SSE), остановка генерации, регенерация, edit & resend
- Вложения: фото (до 6 МБ) и текстовые файлы (до 1 МБ)
- Настройки на 3 вкладках: «Модели», «Общие значения», «Оформление»
  - Провайдеры: DeepSeek, OpenRouter, Custom (OpenAI-совместимый)
  - Черновик настроек модели сохраняется отдельно — применяется только по «Сохранить»
  - Заметки для контекста, общие значения по умолчанию
  - Отдельное окно статистики использования (📊)
- Локализация: English / Русский / Srpski (выбор языка в «Оформление», по умолчанию английский)
- Темизация: авто (нативная Orca) / чисто белая / чисто чёрная, акцент `#d9534f`

## Установка

Скачайте `flowslice_ai-<версия>-py3-none-any.whl` со страницы релизов и установите через
**Плагины → Установить локальный плагин** в Orca Slicer. Зависимость: `numpy` (ставится автоматически).

## Настройка

API-ключ указывается в настройках плагина (вкладка или окно чата → «Настройки» → «Модели»).
Поддерживаются провайдеры: DeepSeek, OpenRouter, Custom (OpenAI-совместимый).

## Команды

| Команда | Описание |
| --- | --- |
| `/context` | Показать контекст слайсера (модель, профили, чекбоксы, история) |
| `/clear` | Очистить текущий чат |
| `/model` | Показать текущую модель и её настройки |
| `/printer` | Показать информацию о принтере |
| `/stats` | Показать статистику использования |
| `/help` | Список команд |
| `/reset` | Сбросить настройки плагина |

## Разработка

- `flowslice_ai/` — модульный пакет плагина (движок-миксины, UI-ресурсы, конфигурация).
- `flowslice_ai/version.py` — единый файл версии (меняется только здесь).
- Сборка wheel: `python -m build --wheel` (в wheel попадают только модули пакета).
- `stubs/orca/` — стаб API Orca для локального QA (pylint/pyright вне слайсера).
- `tests/` — pytest (мок `tests/mocks/orca/` — тесты работают без слайсера).
- `assets/` — иконка вкладки и превью.
- `docs/` — официальная документация API Orca Slicer (обязательно сверяться при правках).
- `example/` — пример плагина (только для изучения синтаксиса `orca.host`).

QA: `PYTHONPATH=stubs pylint flowslice_ai --fail-under=9.0`,
`PYTHONPATH=stubs pyright flowslice_ai` (0 errors), `pytest tests/`.
