# FlowSlice AI

Нативный плагин для Orca Slicer: ИИ-ассистент-инженер 3D-печати.

![FlowSlice AI](assets/preview.png)

## Возможности

- Чат с ИИ-ассистентом (персона: строгий инженер-эксперт 3D-печати)
- Контекст слайсера: модель со стола, профили принтера/пластика/настроек печати
- Мультичат с историей (персист в `data_dir()`), поиск, закрепление
- Команды: `/context`, `/clear`, `/model`, `/printer`, `/stats`, `/help`, `/reset`
- Стриминг ответов (SSE), остановка генерации, регенерация, edit & resend
- Вложения: фото (до 6 МБ) и текстовые файлы (до 1 МБ)
- Темизация: авто (нативная Orca) / чисто белая / чисто чёрная, акцент `#d9534f`

## Установка

Скопируйте `flowslice_ai_plugin.py` в каталог плагинов Orca Slicer
(`data_dir()/orca_plugins/FlowSlice AI/`) и установите через менеджер плагинов.
Зависимость: `numpy` (ставится автоматически).

## Настройка

API-ключ указывается в настройках плагина (вкладка или окно чата → «Настройки»).
Поддерживаются провайдеры: DeepSeek, OpenRouter, Custom (OpenAI-совместимый).

## Разработка

- `flowslice_ai_plugin.py` — единственный файл плагина (PEP 723, HTML/CSS/JS внутри).
- `stubs/orca/` — стаб API Orca для локального QA (pylint/pyright вне слайсера).
- `assets/` — иконка вкладки и превью.

QA: `PYTHONPATH=stubs pylint flowslice_ai_plugin.py --disable=...` (цель 10.00/10),
`PYTHONPATH=stubs pyright flowslice_ai_plugin.py` (0 errors).