(function () {
  "use strict";

  /* ===== Константы ===== */
  var CONTEXT_KEYS = ["filament", "printer", "print", "model", "history"];
  // Клиентские лимиты вложений (синхронизированы с лимитами бэкенда).
  var MAX_ATTACHMENTS = 10;
  var MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024;
  var MAX_TEXT_CHARS = 100000;
  var MAX_TOTAL_TEXT_CHARS = 400000;
  // Сколько последних запросов хранить для навигации стрелками в поле ввода.
  var HISTORY_LIMIT = 50;
  // Разделы пресетов с выбором режима выгрузки (изменённые/все) в панели чата.
  var CONTEXT_MODE_KEYS = ["filament", "printer", "print"];
  // Раздел «Модель со стола» имеет собственный режим: кратко/подробно.
  var CONTEXT_MODEL_KEY = "model";
  var CONTEXT_MODEL_MODES = ["brief", "full", "deep"];
  var CONTEXT_LABELS = {
    filament: "ctx.filament",
    printer: "ctx.printer",
    print: "ctx.print",
    model: "ctx.model",
    history: "ctx.history"
  };

  /* ===== Состояние ===== */
  var state = {
    chats: [],
    active: null,
    settings: {},
    providers: [],
    commands: [],
    context_flags: {},
    context_modes: {},
    context_tokens: 0,
    status: "idle",
    // Подгруженные через API списки моделей: { providerId: { models, error } }.
    apiModels: {}
  };

  // Провайдеры, для которых уже запрошен список моделей в текущей сессии.
  var apiModelsRequested = {};
  // Модели, для которых уже отправлен запрос на добавление из списка API.
  var apiModelsImporting = {};

  /* ===== Локализация (i18n) ===== */
  var I18N = {
    en: {
      "common.close": "Close",
      "common.search": "Search",
      "common.nothing": "No results",
      "common.copied": "Copied!",
      "common.copy_code": "Copy code",
      "js.error": "Interface error",
      "common.copy_failed": "Failed to copy — select the text manually",
      "common.save": "Save",
      "common.reset": "Reset",
      "common.cancel": "Cancel",
      "common.add": "Add",
      "common.delete": "Delete",
      "common.rename": "Rename",
      "common.pin": "Pin",
      "common.unpin": "Unpin",
      "common.copy": "Copy",
      "common.regenerate": "Regenerate",
      "common.edit": "Edit",
      "common.show_key": "Show key",
      "common.hide_key": "Hide key",
      "common.typing": "Typing...",
      "common.attachment": "Attachment",
      "common.reasoning": "Reasoning",
      "common.remove_attachment": "Remove attachment",
      "common.attach_file": "Attach file",
      "attach.default_name": "file",
      "attach.drop_hint": "Drop a file here to attach it",
      "attach.limit_count": "Attachment limit reached (max {n}).",
      "attach.limit_size": "File \"{name}\" is too large.",
      "attach.reading": "File is still being read, try again in a moment.",
      "attach.photo_name": "photo",
      "attach.binary_unsupported": "Binary files are not supported: {name}. Attach a text file or an image.",
      "attach.read_failed": "Failed to read file: {name}.",
      "attach.image_failed": "Failed to process image: {name}.",
      "attach.type_image": "Images",
      "attach.type_text": "Text files",
      "attach.file_too_big": "File \"{name}\" is too large (100 000 characters limit).",
      "attach.files_total_too_big": "Total size of text attachments is too large.",
      "common.stop": "Stop",
      "common.send": "Send",
      "common.choose_model": "Choose model",
      "common.new_chat": "New chat",
      "common.settings": "Settings",
      "common.stats": "Statistics",
      "common.no_active_chat": "No active chat",
      "chat.scroll_bottom": "Scroll to last message",
      "sidebar.chats": "Chats",
      "sidebar.search": "Search chats and messages...",
      "sidebar.pinned": "Pinned",
      "sidebar.today": "Today",
      "sidebar.yesterday": "Yesterday",
      "sidebar.earlier": "Earlier",
      "sidebar.empty": "No chats yet",
      "sidebar.rename_prompt": "Enter new chat name:",
      "sidebar.delete_confirm": "Delete chat \"{title}\"?",
      "sidebar.clear_all": "Clear chat history",
      "sidebar.clear_all_confirm": "Delete all chats? This cannot be undone.",
      "ctx.filament": "Filament",
      "ctx.printer": "Printer",
      "ctx.print": "Print settings",
      "ctx.model": "Model from the plate",
      "ctx.history": "Chat history",
      "ctx.filament_help": "Adds the active filament profile to the context: type, temperatures, flow rate and other parameters",
      "ctx.printer_help": "Adds the active printer profile to the context: bed size, print height, G-code and other parameters",
      "ctx.print_help": "Adds the active print profile to the context: layer height, speeds, infill and other parameters",
      "ctx.model_help": "Adds the loaded model data to the context. The dropdown sets the detail level: from a scene summary to a deep geometry analysis (dimensions, volume, triangles, base and overhang area).",
      "ctx.history_help": "Adds the current chat's message history to the context",
      "ctx.tokens": "Context tokens: {n}",
      "ctx.request_tokens": "Request tokens: {n}",
      "ctx.request_tokens_title": "Estimated tokens of the current message: text plus attachments.",
      "ctx.mode_changed": "changed",
      "ctx.mode_all": "all",
      "ctx.mode_title": "Preset export: only changed parameters or the full profile",
      "ctx.mode_help": "Dropdown on the right:\nchanged — only parameters changed from the base preset\nall — the full profile",
      "ctx.model_mode_brief": "brief",
      "ctx.model_mode_full": "full",
      "ctx.model_mode_deep": "deep analysis",
      "ctx.model_mode_title": "Model export: summary, detail or deep analysis",
      "ctx.model_mode_help": "Dropdown on the right:\nbrief — summary only: object count, overall size and volume\nfull — detailed data per object: bounding boxes, volume, triangles\ndeep analysis — full data plus base area, overhang area and bounding-box fill ratio",
      "composer.placeholder": "Message... (Enter — send, Shift+Enter — new line)",
      "welcome.sub": "3D printing engineer-expert. Ask about mechanics, Klipper or materials.",
      "settings.title": "Settings",
      "settings.tab.models": "Models",
      "settings.tab.custom": "Custom",
      "settings.tab.general": "General",
      "settings.tab.appearance": "Appearance",
      "settings.provider": "Provider",
      "settings.api_key": "API key",
      "settings.key_set": "Key is set — type a new one to replace",
      "settings.key_saved": "Key saved",
      "settings.test_key": "Test key",
      "settings.base_url": "Base URL",
      "settings.scheme": "API scheme",
      "settings.model": "Model",
      "settings.model_settings": "Model settings",
      "settings.model_name": "Display name",
      "settings.model_system_name": "Name in system (id)",
      "settings.temperature": "Temperature:",
      "settings.max_tokens": "Max tokens",
      "settings.reasoning": "Extended reasoning",
      "settings.compact_title": "Context compaction",
      "settings.compact_enabled": "Automatically compress history",
      "settings.help_compact_enabled": "Replace old messages with a short summary when the context approaches the limit",
      "settings.compact_threshold": "Compaction threshold, %",
      "settings.help_compact_threshold": "Share of the context window at which the history is compressed",
      "settings.context_window": "Context window, tokens",
      "settings.help_context_window": "Context window size of the active model; used to estimate the compaction threshold",
      "settings.global_badge": "global",
      "settings.reset_to_global": "Reset to global",
      "settings.add_model": "+ Add model",
      "settings.add_provider": "+ Add provider",
      "settings.add": "Add",
      "settings.cancel": "Cancel",
      "settings.delete_model": "Delete selected model",
      "settings.fine_tuning": "Fine tuning",
      "settings.delete_model_title": "Delete model",
      "settings.delete_provider_title": "Delete provider",
      "settings.name_required": "Enter a name",
      "settings.notes": "Notes for context (visible to agent)",
      "settings.notes_placeholder": "Profile-specific info can be written in the notes of the filament, printer or print profile and attached to the context. General additional info — in this field",
      "settings.default_model_title": "Default model settings",
      "settings.default_model_hint": "If a model has custom parameters, they are used instead of the defaults",
      "settings.data_title": "Reset data",
      "settings.reset_models": "Reset models",
      "settings.reset_custom_models": "Reset custom models",
      "settings.preset_context": "Preset context",
      "settings.preset_context_changed": "Only changed parameters",
      "settings.preset_context_all": "All parameters (changed ones are marked)",
      "settings.help_provider": "API provider used to send requests to models",
      "settings.help_model": "Active model for new messages",
      "settings.refresh_models": "Refresh model list from provider",
      "settings.help_url": "API server address of the provider",
      "settings.help_model_name": "Model name in the provider system (id)",
      "settings.help_model_alias": "Friendly model name shown in the UI",
      "settings.help_api_key": "Provider API access key",
      "settings.help_scheme": "API request format: OpenAI-compatible or native Anthropic",
      "settings.help_temperature": "Response randomness: lower is more precise, higher is more creative",
      "settings.help_max_tokens": "Maximum response length in tokens",
      "settings.help_reasoning": "Enable extended model reasoning before answering",
      "settings.vision": "Vision",
      "settings.help_vision": "Whether the model can analyze images.",
      "settings.vision_yes": "Yes",
      "settings.vision_no": "No",
      "settings.vision_unknown": "Unknown",
      "settings.vision_from_provider": "Confirmed by provider",
      "settings.vision_manual": "Set manually",
      "settings.price_in": "Input price, USD per 1M tokens",
      "settings.price_out": "Output price, USD per 1M tokens",
      "settings.price_from_provider": "Price from provider",
      "settings.price_manual": "Price set manually",
      "settings.price_hint": "Leave empty if unknown. Used to estimate the cost of replies.",
      "msg.usage_title": "Estimated tokens and cost of this reply, USD",
      "compact.indicator": "Earlier messages are compressed into a summary ({n})",
      "settings.help_notes": "Additional info the agent takes into account when answering",
      "settings.help_language": "Plugin UI language",
      "settings.help_preset_context": "What goes into the slicer context: only changed preset parameters or all of them",
      "settings.font_size": "Font size:",
      "settings.font_style": "Font style",
      "settings.language": "Language",
      "settings.theme": "Theme",
      "settings.saved": "Settings saved",
      "settings.reset_done": "Settings reset",
      "usage.title": "Usage Statistics",
      "usage.text": "Messages: {msgs} · Tokens: {tokens}",
      "usage.period.all": "All time",
      "usage.period.today": "Today",
      "usage.period.week": "This week",
      "usage.period.month": "This month",
      "mp.title": "Choose active model",
      "mp.search": "Search model or provider...",
      "mp.default": "Default",
      "mp.default_set": "Set as default model",
      "mp.vision_supported": "Supports image analysis",
      "mp.vision_none": "Does not accept images",
      "mp.refresh": "Refresh model list",
      "mp.price_title": "Price per 1M tokens (input/output), USD",
      "mp.free": "Free",
      "mp.need_key": "Set an API key for one of the providers or add your own model",
      "mp.no_model": "No model configured",
      "mp.open_settings": "Open settings",
      "mp.selected": "Selected",
      "copy.title": "Copy the text manually",
      "dd.provider_search": "Search providers...",
      "dd.model_search": "Search models...",
      "dd.scheme_search": "Search scheme...",
      "dd.theme_search": "Search theme...",
      "dd.period_search": "Search period...",
      "dd.language_search": "Search language...",
      "scheme.openai": "OpenAI-compatible",
      "scheme.anthropic": "Anthropic (native)",
      "theme.auto": "Auto",
      "theme.light": "Light",
      "theme.dark": "Dark",
      "font.system": "System",
      "font.mono": "Monospace",
      "font.serif": "Serif",
      "lang.en": "English",
      "lang.ru": "Русский",
      "lang.sr": "Srpski",
      "cmd.context": "/context — show slicer context",
      "cmd.clear": "/clear — clear chat",
      "cmd.model": "/model — show current model",
      "cmd.printer": "/printer — show printer info",
      "cmd.stats": "/stats — show usage stats",
      "cmd.help": "/help — show commands",
      "cmd.reset": "/reset — reset settings",
      "cmd.not_found": "Command not found",
      "key.valid": "API key is valid",
      "key.invalid": "API key is invalid",
      "export.user": "User",
      "export.title": "Chat",
      "export.chat": "Export chat",
      "export.system": "System",
      "export.failed": "Failed to prepare the export.",
      "export.fmt_md": "Markdown",
      "export.fmt_txt": "Plain text",
      "export.fmt_json": "JSON"
    },
    ru: {
      "common.close": "Закрыть",
      "common.search": "Поиск",
      "common.nothing": "Ничего не найдено",
      "common.copied": "Скопировано",
      "common.copy_code": "Копировать код",
      "js.error": "Ошибка интерфейса",
      "common.copy_failed": "Не удалось скопировать — выделите текст вручную",
      "common.save": "Сохранить",
      "common.reset": "Сбросить",
      "common.cancel": "Отмена",
      "common.add": "Добавить",
      "common.delete": "Удалить",
      "common.rename": "Переименовать",
      "common.pin": "Закрепить",
      "common.unpin": "Открепить",
      "common.copy": "Копировать",
      "common.regenerate": "Регенерировать",
      "common.edit": "Редактировать",
      "common.show_key": "Показать ключ",
      "common.hide_key": "Скрыть ключ",
      "common.typing": "печатает…",
      "common.attachment": "Вложение",
      "common.reasoning": "Размышления",
      "common.remove_attachment": "Убрать вложение",
      "common.attach_file": "Прикрепить файл",
      "attach.default_name": "файл",
      "attach.drop_hint": "Перетащите файл сюда, чтобы прикрепить",
      "attach.limit_count": "Достигнут предел вложений (не более {n}).",
      "attach.limit_size": "Файл «{name}» слишком большой.",
      "attach.reading": "Файл ещё читается, повторите через мгновение.",
      "attach.photo_name": "фото",
      "attach.binary_unsupported": "Бинарные файлы не поддерживаются: {name}. Прикрепите текстовый файл или изображение.",
      "attach.read_failed": "Не удалось прочитать файл: {name}.",
      "attach.image_failed": "Не удалось обработать изображение: {name}.",
      "attach.type_image": "Изображения",
      "attach.type_text": "Текстовые файлы",
      "attach.file_too_big": "Файл «{name}» слишком большой (лимит 100 000 символов).",
      "attach.files_total_too_big": "Суммарный объём текстовых вложений слишком большой.",
      "common.stop": "Остановить генерацию",
      "common.send": "Отправить",
      "common.choose_model": "Выбрать модель",
      "common.new_chat": "Новый чат",
      "common.settings": "Настройки",
      "common.stats": "Статистика",
      "common.no_active_chat": "Нет активного чата",
      "chat.scroll_bottom": "К последнему сообщению",
      "sidebar.chats": "Чаты",
      "sidebar.search": "Поиск по чатам и сообщениям…",
      "sidebar.pinned": "Закреплённые",
      "sidebar.today": "Сегодня",
      "sidebar.yesterday": "Вчера",
      "sidebar.earlier": "Ранее",
      "sidebar.empty": "Чатов пока нет",
      "sidebar.rename_prompt": "Новое название чата:",
      "sidebar.delete_confirm": "Удалить чат «{title}»?",
      "sidebar.clear_all": "Очистить историю чатов",
      "sidebar.clear_all_confirm": "Удалить все чаты? Это действие нельзя отменить.",
      "ctx.filament": "Пластик",
      "ctx.printer": "Принтер",
      "ctx.print": "Настройки печати",
      "ctx.model": "Модель со стола",
      "ctx.history": "История чата",
      "ctx.filament_help": "Добавляет в контекст активный профиль пластика: тип, температуры, скорость потока и другие параметры",
      "ctx.printer_help": "Добавляет в контекст активный профиль принтера: размеры стола, высоту печати, G-code и другие параметры",
      "ctx.print_help": "Добавляет в контекст активный профиль печати: высоту слоя, скорости, заполнение и другие параметры",
      "ctx.model_help": "Добавляет в контекст данные загруженной модели. Дропдаун справа задаёт глубину: от сводки по сцене до глубокого анализа геометрии (габариты, объём, треугольники, площадь основания и нависаний).",
      "ctx.history_help": "Добавляет в контекст историю сообщений текущего чата",
      "ctx.tokens": "Токенов контекста: {n}",
      "ctx.request_tokens": "Токенов запроса: {n}",
      "ctx.request_tokens_title": "Оценка токенов текущего сообщения: текст и вложения.",
      "ctx.mode_changed": "изм.",
      "ctx.mode_all": "все",
      "ctx.mode_title": "Выгрузка пресета: только изменённые параметры или полный профиль",
      "ctx.mode_help": "Дропдаун справа:\nизм. — только изменённые относительно базового пресета параметры\nвсе — полный профиль",
      "ctx.model_mode_brief": "кратко",
      "ctx.model_mode_full": "подробно",
      "ctx.model_mode_deep": "глубокий анализ",
      "ctx.model_mode_title": "Выгрузка модели: сводка, подробности или глубокий анализ",
      "ctx.model_mode_help": "Дропдаун справа:\nкратко — только сводка: число объектов, габариты и объём\nподробно — детальные данные по каждому объекту: габариты, объём, треугольники\nглубокий анализ — всё из «подробно» плюс площадь основания, площадь нависаний и заполнение габарита",
      "composer.placeholder": "Сообщение… (Enter — отправить, Shift+Enter — новая строка)",
      "welcome.sub": "Инженер-эксперт 3D-печати. Спросите о механике, Klipper или материалах.",
      "settings.title": "Настройки",
      "settings.tab.models": "Модели",
      "settings.tab.custom": "Персональные",
      "settings.tab.general": "Общие значения",
      "settings.tab.appearance": "Оформление",
      "settings.provider": "Провайдер",
      "settings.api_key": "API-ключ",
      "settings.key_set": "Ключ задан — введите новый, чтобы заменить",
      "settings.key_saved": "Ключ сохранён",
      "settings.test_key": "Проверить ключ",
      "settings.base_url": "Базовый URL API",
      "settings.scheme": "Схема API",
      "settings.model": "Модель",
      "settings.model_settings": "Настройки модели",
      "settings.model_name": "Удобное название",
      "settings.model_system_name": "Название в системе (id)",
      "settings.temperature": "Температура:",
      "settings.max_tokens": "Максимум токенов",
      "settings.reasoning": "Расширенное мышление",
      "settings.compact_title": "Сжатие контекста",
      "settings.compact_enabled": "Автоматически сжимать историю",
      "settings.help_compact_enabled": "Заменять старые сообщения короткой сводкой, когда контекст приближается к пределу",
      "settings.compact_threshold": "Порог сжатия, %",
      "settings.help_compact_threshold": "Доля окна контекста, при которой история сжимается",
      "settings.context_window": "Окно контекста, токенов",
      "settings.help_context_window": "Размер окна контекста активной модели; используется для оценки порога сжатия",
      "settings.global_badge": "общий",
      "settings.reset_to_global": "Сбросить к общему",
      "settings.add_model": "+ Добавить модель",
      "settings.add_provider": "+ Добавить провайдера",
      "settings.add": "Добавить",
      "settings.cancel": "Отмена",
      "settings.delete_model": "Удалить выбранную модель",
      "settings.fine_tuning": "Тонкие настройки",
      "settings.delete_model_title": "Удалить модель",
      "settings.delete_provider_title": "Удалить провайдера",
      "settings.name_required": "Укажите название",
      "settings.notes": "Заметки для контекста (видны агенту)",
      "settings.notes_placeholder": "Специфическую информацию к профилю можно прописывать в заметках профиля пластика, принтера или печати и подключать к контексту. Общую дополнительную информацию — в это поле",
      "settings.default_model_title": "Дефолтные настройки моделей",
      "settings.default_model_hint": "Если у модели изменены параметры, используются именно они, а не дефолтные",
      "settings.data_title": "Сброс данных",
      "settings.reset_models": "Сброс моделей",
      "settings.reset_custom_models": "Сброс персональных моделей",
      "settings.preset_context": "Контекст пресетов",
      "settings.preset_context_changed": "Только изменённые параметры",
      "settings.preset_context_all": "Все параметры (изменённые помечены)",
      "settings.help_provider": "Провайдер API, через который отправляются запросы к моделям",
      "settings.help_model": "Активная модель для новых сообщений",
      "settings.refresh_models": "Обновить список моделей у провайдера",
      "settings.help_url": "Адрес API-сервера провайдера",
      "settings.help_model_name": "Название модели в системе провайдера (id)",
      "settings.help_model_alias": "Удобное имя модели для отображения в интерфейсе",
      "settings.help_api_key": "Ключ доступа к API провайдера",
      "settings.help_scheme": "Формат запросов к API: OpenAI-совместимый или нативный Anthropic",
      "settings.help_temperature": "Случайность ответов: ниже — точнее, выше — креативнее",
      "settings.help_max_tokens": "Максимальная длина ответа в токенах",
      "settings.help_reasoning": "Включить расширенное мышление модели перед ответом",
      "settings.vision": "Зрение",
      "settings.help_vision": "Умеет ли модель распознавать изображения.",
      "settings.vision_yes": "Есть",
      "settings.vision_no": "Нет",
      "settings.vision_unknown": "Не знаю",
      "settings.vision_from_provider": "Подтверждено провайдером",
      "settings.vision_manual": "Задано вручную",
      "settings.price_in": "Цена входа, USD за 1 млн токенов",
      "settings.price_out": "Цена выхода, USD за 1 млн токенов",
      "settings.price_from_provider": "Цена от провайдера",
      "settings.price_manual": "Цена задана вручную",
      "settings.price_hint": "Оставьте пустым, если цена неизвестна. По ней оценивается стоимость ответов.",
      "msg.usage_title": "Оценка токенов и стоимости ответа, USD",
      "compact.indicator": "Ранние сообщения сжаты в сводку ({n})",
      "settings.help_notes": "Дополнительная информация, которую агент учитывает при ответах",
      "settings.help_language": "Язык интерфейса плагина",
      "settings.help_preset_context": "Что попадает в контекст слайсера: только изменённые параметры пресетов или все",
      "settings.font_size": "Размер шрифта:",
      "settings.font_style": "Стиль шрифта",
      "settings.language": "Язык",
      "settings.theme": "Тема",
      "settings.saved": "Настройки сохранены",
      "settings.reset_done": "Настройки сброшены",
      "usage.title": "Статистика использования",
      "usage.text": "Сообщения: {msgs} · Токены: {tokens}",
      "usage.period.all": "Всё время",
      "usage.period.today": "Сегодня",
      "usage.period.week": "Неделя",
      "usage.period.month": "Месяц",
      "mp.title": "Выбор активной модели",
      "mp.search": "Поиск модели или провайдера…",
      "mp.default": "По умолчанию",
      "mp.default_set": "Сделать моделью по умолчанию",
      "mp.vision_supported": "Поддерживает анализ изображений",
      "mp.vision_none": "Не принимает изображения",
      "mp.refresh": "Обновить список моделей",
      "mp.price_title": "Цена за 1 млн токенов (вход/выход), USD",
      "mp.free": "Бесплатно",
      "mp.need_key": "Укажите для одного из провайдеров токен или внесите свою модель",
      "mp.no_model": "Модель не настроена",
      "mp.open_settings": "Открыть настройки",
      "mp.selected": "Выбрано",
      "copy.title": "Скопируйте текст вручную",
      "dd.provider_search": "Поиск провайдера…",
      "dd.model_search": "Поиск модели…",
      "dd.scheme_search": "Поиск схемы…",
      "dd.theme_search": "Поиск темы…",
      "dd.period_search": "Поиск периода…",
      "dd.language_search": "Поиск языка…",
      "scheme.openai": "OpenAI-совместимая",
      "scheme.anthropic": "Anthropic (нативный)",
      "theme.auto": "Авто",
      "theme.light": "Светлая",
      "theme.dark": "Тёмная",
      "font.system": "Системный",
      "font.mono": "Моноширинный",
      "font.serif": "С засечками",
      "lang.en": "English",
      "lang.ru": "Русский",
      "lang.sr": "Srpski",
      "cmd.context": "/context — показать контекст слайсера",
      "cmd.clear": "/clear — очистить чат",
      "cmd.model": "/model — показать текущую модель",
      "cmd.printer": "/printer — показать информацию о принтере",
      "cmd.stats": "/stats — показать статистику использования",
      "cmd.help": "/help — показать команды",
      "cmd.reset": "/reset — сбросить настройки",
      "cmd.not_found": "Команда не найдена",
      "key.valid": "Ключ действителен",
      "key.invalid": "Ключ недействителен",
      "export.user": "Пользователь",
      "export.title": "Чат",
      "export.chat": "Экспорт чата",
      "export.system": "Система",
      "export.failed": "Не удалось подготовить экспорт.",
      "export.fmt_md": "Markdown",
      "export.fmt_txt": "Обычный текст",
      "export.fmt_json": "JSON"
    },
    sr: {
      "common.close": "Zatvori",
      "common.search": "Pretraga",
      "common.nothing": "Ništa nije pronađeno",
      "common.copied": "Kopirano!",
      "common.copy_code": "Kopiraj kod",
      "js.error": "Greška interfejsa",
      "common.copy_failed": "Kopiranje nije uspelo — označite tekst ručno",
      "common.save": "Sačuvaj",
      "common.reset": "Resetuj",
      "common.cancel": "Otkaži",
      "common.add": "Dodaj",
      "common.delete": "Obriši",
      "common.rename": "Preimenuj",
      "common.pin": "Zakači",
      "common.unpin": "Otkači",
      "common.copy": "Kopiraj",
      "common.regenerate": "Regeneriši",
      "common.edit": "Izmeni",
      "common.show_key": "Prikaži ključ",
      "common.hide_key": "Sakrij ključ",
      "common.typing": "kuca…",
      "common.attachment": "Prilog",
      "common.reasoning": "Razmišljanje",
      "common.remove_attachment": "Ukloni prilog",
      "common.attach_file": "Priloži datoteku",
      "attach.default_name": "datoteka",
      "attach.drop_hint": "Prevucite datoteku ovde da je priložite",
      "attach.limit_count": "Dostignut limit priloga (najviše {n}).",
      "attach.limit_size": "Datoteka \"{name}\" je prevelika.",
      "attach.reading": "Datoteka se još čita, pokušajte ponovo za trenutak.",
      "attach.photo_name": "foto",
      "attach.binary_unsupported": "Binarne datoteke nisu podržane: {name}. Priložite tekstualnu datoteku ili sliku.",
      "attach.read_failed": "Nije moguće pročitati datoteku: {name}.",
      "attach.image_failed": "Nije moguće obraditi sliku: {name}.",
      "attach.type_image": "Slike",
      "attach.type_text": "Tekstualne datoteke",
      "attach.file_too_big": "Datoteka \"{name}\" je prevelika (ograničenje 100 000 znakova).",
      "attach.files_total_too_big": "Ukupna veličina tekstualnih priloga je prevelika.",
      "common.stop": "Zaustavi",
      "common.send": "Pošalji",
      "common.choose_model": "Izaberi model",
      "common.new_chat": "Novi razgovor",
      "common.settings": "Podešavanja",
      "common.stats": "Statistika",
      "common.no_active_chat": "Nema aktivnog razgovora",
      "chat.scroll_bottom": "Na poslednju poruku",
      "sidebar.chats": "Razgovori",
      "sidebar.search": "Pretraga razgovora i poruka…",
      "sidebar.pinned": "Zakačeni",
      "sidebar.today": "Danas",
      "sidebar.yesterday": "Juče",
      "sidebar.earlier": "Ranije",
      "sidebar.empty": "Još nema razgovora",
      "sidebar.rename_prompt": "Unesite novo ime razgovora:",
      "sidebar.delete_confirm": "Obrisati razgovor \"{title}\"?",
      "sidebar.clear_all": "Obriši istoriju razgovora",
      "sidebar.clear_all_confirm": "Obrisati sve razgovore? Ova radnja se ne može poništiti.",
      "ctx.filament": "Filament",
      "ctx.printer": "Štampač",
      "ctx.print": "Podešavanja štampe",
      "ctx.model": "Model sa stola",
      "ctx.history": "Istorija razgovora",
      "ctx.filament_help": "Dodaje u kontekst aktivni profil filamenta: tip, temperature, protok i druge parametre",
      "ctx.printer_help": "Dodaje u kontekst aktivni profil štampača: dimenzije stola, visinu štampe, G-code i druge parametre",
      "ctx.print_help": "Dodaje u kontekst aktivni profil štampe: visinu sloja, brzine, ispunu i druge parametre",
      "ctx.model_help": "Dodaje u kontekst podatke učitanog modela. Padajuća lista desno bira nivo detalja: od sažetka scene do duboke analize geometrije (gabariti, zapremina, trouglovi, površina osnove i prevjesa).",
      "ctx.history_help": "Dodaje u kontekst istoriju poruka trenutnog razgovora",
      "ctx.tokens": "Tokeni konteksta: {n}",
      "ctx.request_tokens": "Tokeni zahteva: {n}",
      "ctx.request_tokens_title": "Procena tokena trenutne poruke: tekst i prilozi.",
      "ctx.mode_changed": "izm.",
      "ctx.mode_all": "sve",
      "ctx.mode_title": "Izvoz profila: samo izmenjeni parametri ili pun profil",
      "ctx.mode_help": "Padajuća lista desno:\nizm. — samo parametri izmenjeni u odnosu na bazni profil\nsve — pun profil",
      "ctx.model_mode_brief": "kratko",
      "ctx.model_mode_full": "detaljno",
      "ctx.model_mode_deep": "duboka analiza",
      "ctx.model_mode_title": "Izvoz modela: sažetak, detalji ili duboka analiza",
      "ctx.model_mode_help": "Padajuća lista desno:\nkratko — samo sažetak: broj objekata, gabariti i zapremina\ndetaljno — detaljni podaci po objektu: gabariti, zapremina, trouglovi\nduboka analiza — sve iz «detaljno» plus površina osnove, površina prevjesa i ispuna gabarita",
      "composer.placeholder": "Poruka… (Enter — pošalji, Shift+Enter — novi red)",
      "welcome.sub": "Inženjer-ekspert za 3D štampu. Pitajte o mehanici, Klipperu ili materijalima.",
      "settings.title": "Podešavanja",
      "settings.tab.models": "Modeli",
      "settings.tab.custom": "Lični",
      "settings.tab.general": "Opšte vrednosti",
      "settings.tab.appearance": "Izgled",
      "settings.provider": "Provajder",
      "settings.api_key": "API ključ",
      "settings.key_set": "Ključ je postavljen — unesite novi da zamenite",
      "settings.key_saved": "Ključ sačuvan",
      "settings.test_key": "Testiraj ključ",
      "settings.base_url": "Osnovni URL API",
      "settings.scheme": "API šema",
      "settings.model": "Model",
      "settings.model_settings": "Podešavanja modela",
      "settings.model_name": "Prikazano ime",
      "settings.model_system_name": "Ime u sistemu (id)",
      "settings.temperature": "Temperatura:",
      "settings.max_tokens": "Maksimum tokena",
      "settings.reasoning": "Produženo razmišljanje",
      "settings.compact_title": "Sažimanje konteksta",
      "settings.compact_enabled": "Automatski sažmi istoriju",
      "settings.help_compact_enabled": "Zameni stare poruke kratkim sažetkom kada se kontekst približi limitu",
      "settings.compact_threshold": "Prag sažimanja, %",
      "settings.help_compact_threshold": "Deo prozora konteksta pri kojem se istorija sažima",
      "settings.context_window": "Prozor konteksta, tokena",
      "settings.help_context_window": "Veličina prozora konteksta aktivnog modela; koristi se za procenu praga sažimanja",
      "settings.global_badge": "globalno",
      "settings.reset_to_global": "Resetuj na globalno",
      "settings.add_model": "+ Dodaj model",
      "settings.add_provider": "+ Dodaj provajdera",
      "settings.add": "Dodaj",
      "settings.cancel": "Otkaži",
      "settings.delete_model": "Obriši izabrani model",
      "settings.fine_tuning": "Fino podešavanje",
      "settings.delete_model_title": "Obriši model",
      "settings.delete_provider_title": "Obriši provajdera",
      "settings.name_required": "Unesite naziv",
      "settings.notes": "Beleške za kontekst (vidljive agentu)",
      "settings.notes_placeholder": "Informacije specifične za profil možete upisati u beleške profila filamenta, štampača ili štampe i priključiti ih kontekstu. Opšte dodatne informacije — u ovo polje",
      "settings.default_model_title": "Podrazumevana podešavanja modela",
      "settings.default_model_hint": "Ako model ima izmenjene parametre, koriste se oni, a ne podrazumevani",
      "settings.data_title": "Resetovanje podataka",
      "settings.reset_models": "Resetovanje modela",
      "settings.reset_custom_models": "Resetovanje ličnih modela",
      "settings.preset_context": "Kontekst preseta",
      "settings.preset_context_changed": "Samo izmenjeni parametri",
      "settings.preset_context_all": "Svi parametri (izmenjeni su označeni)",
      "settings.help_provider": "API provajder kroz koji se šalju zahtevi ka modelima",
      "settings.help_model": "Aktivni model za nove poruke",
      "settings.refresh_models": "Osveži listu modela od provajdera",
      "settings.help_url": "Adresa API servera provajdera",
      "settings.help_model_name": "Naziv modela u sistemu provajdera (id)",
      "settings.help_model_alias": "Prikazano ime modela u interfejsu",
      "settings.help_api_key": "Ključ za pristup API provajdera",
      "settings.help_scheme": "Format zahteva ka API: OpenAI-kompatibilan ili nativni Anthropic",
      "settings.help_temperature": "Nasumičnost odgovora: niže — preciznije, više — kreativnije",
      "settings.help_max_tokens": "Maksimalna dužina odgovora u tokenima",
      "settings.help_reasoning": "Uključi produženo razmišljanje modela pre odgovora",
      "settings.vision": "Vid",
      "settings.help_vision": "Da li model analizira slike.",
      "settings.vision_yes": "Ima",
      "settings.vision_no": "Nema",
      "settings.vision_unknown": "Ne znam",
      "settings.vision_from_provider": "Potvrđeno od provajdera",
      "settings.vision_manual": "Ručno podešeno",
      "settings.price_in": "Cena ulaza, USD za 1M tokena",
      "settings.price_out": "Cena izlaza, USD za 1M tokena",
      "settings.price_from_provider": "Cena od provajdera",
      "settings.price_manual": "Cena ručno podešena",
      "settings.price_hint": "Ostavite prazno ako cena nije poznata. Koristi se za procenu cene odgovora.",
      "msg.usage_title": "Procena tokena i cene odgovora, USD",
      "compact.indicator": "Ranije poruke su sažete u sažetak ({n})",
      "settings.help_notes": "Dodatne informacije koje agent uzima u obzir pri odgovaranju",
      "settings.help_language": "Jezik interfejsa dodatka",
      "settings.help_preset_context": "Šta ulazi u kontekst slajsera: samo izmenjeni parametri preseta ili svi",
      "settings.font_size": "Veličina fonta:",
      "settings.font_style": "Stil fonta",
      "settings.language": "Jezik",
      "settings.theme": "Tema",
      "settings.saved": "Podešavanja sačuvana",
      "settings.reset_done": "Podešavanja resetovana",
      "usage.title": "Statistika korišćenja",
      "usage.text": "Poruke: {msgs} · Tokeni: {tokens}",
      "usage.period.all": "Sve vreme",
      "usage.period.today": "Danas",
      "usage.period.week": "Ova nedelja",
      "usage.period.month": "Ovaj mesec",
      "mp.title": "Izbor aktivnog modela",
      "mp.search": "Pretraga modela ili provajdera…",
      "mp.default": "Podrazumevano",
      "mp.default_set": "Postavi kao podrazumevani model",
      "mp.vision_supported": "Podržava analizu slika",
      "mp.vision_none": "Ne prihvata slike",
      "mp.refresh": "Osveži listu modela",
      "mp.price_title": "Cena za 1M tokena (ulaz/izlaz), USD",
      "mp.free": "Besplatno",
      "mp.need_key": "Postavite token za jednog od provajdera ili dodajte sopstveni model",
      "mp.no_model": "Model nije podešen",
      "mp.open_settings": "Otvori podešavanja",
      "mp.selected": "Izabrano",
      "copy.title": "Kopirajte tekst ručno",
      "dd.provider_search": "Pretraga provajdera…",
      "dd.model_search": "Pretraga modela…",
      "dd.scheme_search": "Pretraga šeme…",
      "dd.theme_search": "Pretraga teme…",
      "dd.period_search": "Pretraga perioda…",
      "dd.language_search": "Pretraga jezika…",
      "scheme.openai": "OpenAI-kompatibilna",
      "scheme.anthropic": "Anthropic (nativni)",
      "theme.auto": "Auto",
      "theme.light": "Svetla",
      "theme.dark": "Tamna",
      "font.system": "Sistemski",
      "font.mono": "Monospace",
      "font.serif": "Serif",
      "lang.en": "English",
      "lang.ru": "Ruski",
      "lang.sr": "Srpski",
      "cmd.context": "/context — prikaži kontekst slajsera",
      "cmd.clear": "/clear — očisti razgovor",
      "cmd.model": "/model — prikaži trenutni model",
      "cmd.printer": "/printer — prikaži informacije o štampaču",
      "cmd.stats": "/stats — prikaži statistiku korišćenja",
      "cmd.help": "/help — prikaži komande",
      "cmd.reset": "/reset — resetuj podešavanja",
      "cmd.not_found": "Komanda nije pronađena",
      "key.valid": "API ključ je važeći",
      "key.invalid": "API ključ nije važeći",
      "export.user": "Korisnik",
      "export.title": "Ćaskanje",
      "export.chat": "Izvezi razgovor",
      "export.system": "Sistem",
      "export.failed": "Izrada izvoza nije uspela.",
      "export.fmt_md": "Markdown",
      "export.fmt_txt": "Običan tekst",
      "export.fmt_json": "JSON"
    }
  };

  function currentLang() {
    return (state && state.settings && state.settings.language) || "en";
  }

  function t(key, params) {
    var lang = currentLang();
    var s = (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key;
    if (params) {
      for (var k in params) {
        s = s.split("{" + k + "}").join(String(params[k]));
      }
    }
    return s;
  }

  function applyI18n(root) {
    document.documentElement.lang = currentLang();
    var scope = root || document;
    scope.querySelectorAll("[data-i18n]").forEach(function (el) {
      el.textContent = t(el.getAttribute("data-i18n"));
    });
    scope.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
      el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
    });
    scope.querySelectorAll("[data-i18n-title]").forEach(function (el) {
      el.setAttribute("title", t(el.getAttribute("data-i18n-title")));
    });
    scope.querySelectorAll("[data-i18n-aria-label]").forEach(function (el) {
      el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria-label")));
    });
    // Кнопки без явного aria-label получают его из title/текста.
    scope.querySelectorAll("button").forEach(function (btn) {
      if (btn.getAttribute("aria-label")) {
        return;
      }
      var titleKey = btn.getAttribute("data-i18n-title");
      var label = titleKey ? t(titleKey) : (btn.textContent || "").trim();
      if (label) {
        btn.setAttribute("aria-label", label);
      }
    });
    scope.querySelectorAll("[data-i18n-tooltip]").forEach(function (el) {
      el.setAttribute("data-tooltip", t(el.getAttribute("data-i18n-tooltip")));
      // Нативный title не нужен: подсказка показывается собственным элементом.
      el.removeAttribute("title");
    });
  }

  /* ===== Всплывающие подсказки «?» =====
     Рендерятся порталом в body с position:fixed, поэтому их не обрезают
     границы модалок (overflow) и они прижимаются к краям окна. */
  var helpTipEl = null;
  var helpTipHost = null;

  function hideHelpTip() {
    helpTipHost = null;
    if (helpTipEl) {
      helpTipEl.classList.remove("show");
    }
  }

  function showHelpTip(icon) {
    var text = icon.getAttribute("data-tooltip") || t(icon.getAttribute("data-i18n-tooltip"));
    if (!text) {
      return;
    }
    if (!helpTipEl) {
      helpTipEl = el("div", "help-tip");
      document.body.appendChild(helpTipEl);
    }
    helpTipEl.textContent = text;
    // Размеры считываем до показа: opacity на layout не влияет.
    var rect = icon.getBoundingClientRect();
    var tipWidth = helpTipEl.offsetWidth;
    var tipHeight = helpTipEl.offsetHeight;
    var gap = 8;
    var left = rect.left + rect.width / 2 - tipWidth / 2;
    left = Math.max(gap, Math.min(left, window.innerWidth - tipWidth - gap));
    var top = rect.top - tipHeight - gap;
    if (top < gap) {
      top = rect.bottom + gap;
    }
    helpTipEl.style.left = left + "px";
    helpTipEl.style.top = top + "px";
    helpTipEl.classList.add("show");
  }

  function initHelpTooltips() {
    // Делегирование: работает и для статичных «?», и для динамически
    // пересоздаваемых элементов (например, чекбоксы контекста в чате).
    document.addEventListener("mouseover", function (e) {
      var host = e.target && e.target.closest ? e.target.closest("[data-tooltip]") : null;
      if (!host || host === helpTipHost) {
        return;
      }
      showHelpTip(host);
    });
    document.addEventListener("mouseout", function (e) {
      var host = e.target && e.target.closest ? e.target.closest("[data-tooltip]") : null;
      if (!host) {
        return;
      }
      var to = e.relatedTarget;
      if (to && host.contains(to)) {
        return;
      }
      hideHelpTip();
    });
    window.addEventListener("scroll", hideHelpTip, true);
    window.addEventListener("resize", hideHelpTip);
  }

  var streamTextEl = null; // элемент текста текущего стримингового сообщения
  var streamText = ""; // накопленный текст текущего стрима (для перерисовок)
  var streamThoughtEl = null; // элемент текста размышлений текущего стрима
  var streamThought = ""; // накопленные размышления текущего стрима
  var pendingEditId = null; // id сообщения, которое редактируется
  var attachments = []; // вложения перед отправкой
  var inputHistory = []; // отправленные запросы (текст + вложения), новые в конце
  var historyIndex = -1; // позиция навигации по истории (-1 — черновик)
  var historyDraft = null; // черновик ввода, временно вытесненный историей
  var userScrolledUp = false; // пользователь прокрутил историю вверх
  var pendingForceScroll = false; // требуется прокрутка вниз после перерисовки

  /* ===== Хелперы ===== */
  function byId(id) {
    return document.getElementById(id);
  }

  // Ключ никогда не приходит из бэкенда: показываем только признак «задан».
  function setKeyField(inputId, hasKey) {
    var field = byId(inputId);
    if (!field) {
      return;
    }
    field.value = "";
    field.placeholder = hasKey ? t("settings.key_set") : t("settings.api_key");
    // Видимый статус: пустое поле не должно выглядеть как «ключ не задан».
    var wrap = field.closest(".field");
    if (!wrap) {
      return;
    }
    var status = wrap.querySelector(".key-status");
    if (!status) {
      status = el("span", "key-status");
      wrap.appendChild(status);
    }
    status.textContent = hasKey ? "✓ " + t("settings.key_saved") : "";
    status.classList.toggle("set", hasKey);
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) {
      node.className = cls;
    }
    if (text !== undefined && text !== null) {
      node.textContent = text;
    }
    return node;
  }

  function post(obj) {
    if (window.orca && typeof window.orca.postMessage === "function") {
      window.orca.postMessage(obj);
    }
  }

  function getActiveChat() {
    var chats = state.chats || [];
    for (var i = 0; i < chats.length; i++) {
      if (chats[i].id === state.active) {
        return chats[i];
      }
    }
    return null;
  }

  function formatTime(ts) {
    if (!ts) {
      return "";
    }
    var d = new Date(ts);
    var h = d.getHours();
    var m = d.getMinutes();
    return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m;
  }

  function formatTokens(value) {
    var n = Number(value) || 0;
    if (n >= 1000000) {
      return (n / 1000000).toFixed(1) + "M";
    }
    if (n >= 1000) {
      return (n / 1000).toFixed(1) + "K";
    }
    return String(n);
  }

  function formatCost(value) {
    var text = Number(value).toFixed(6);
    text = text.replace(/0+$/, "").replace(/\.$/, "");
    if (!text) {
      text = "0";
    }
    return "$" + text;
  }

  function usageMeta(msg) {
    if (!msg || msg.role !== "assistant") {
      return null;
    }
    var hasTokens = msg.tokens_in !== undefined || msg.tokens_out !== undefined;
    var hasCost = msg.cost !== undefined && msg.cost !== null;
    if (!hasTokens && !hasCost) {
      return null;
    }
    var parts = [];
    if (hasTokens) {
      parts.push(
        "≈ " + formatTokens(msg.tokens_in || 0) + " ↑ / " + formatTokens(msg.tokens_out || 0) + " ↓"
      );
    }
    if (hasCost) {
      parts.push(formatCost(msg.cost));
    }
    var span = el("span", "msg-meta", " · " + parts.join(" · "));
    span.title = t("msg.usage_title");
    return span;
  }

  /* ===== Тема и шрифт ===== */
  function applyTheme(settings) {
    var theme = (settings && settings.theme) || "auto";
    document.body.classList.remove("theme-light", "theme-dark");
    if (theme === "light") {
      document.body.classList.add("theme-light");
    } else if (theme === "dark") {
      document.body.classList.add("theme-dark");
    } else if (!orcaProvidesTheme()) {
      // Orca не отдала переменные темы (запуск вне слайсера) — берём системную.
      var dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
      document.body.classList.add(dark ? "theme-dark" : "theme-light");
    }
  }

  // Проверяет, определила ли Orca базовую переменную фона.
  function orcaProvidesTheme() {
    var probe = getComputedStyle(document.body).getPropertyValue("--orca-bg");
    return probe.trim().length > 0;
  }

  function applyFont(settings) {
    var size = (settings && settings.font_size) || 14;
    var style = (settings && settings.font_style) || "system";
    document.body.style.fontSize = size + "px";
    if (style === "mono") {
      document.body.style.fontFamily = "Consolas, monospace";
    } else if (style === "serif") {
      document.body.style.fontFamily = "Georgia, serif";
    } else {
      document.body.style.fontFamily = "var(--orca-font)";
    }
  }

  /* ===== Переключатель темы (горизонтальные кнопки) ===== */
  function updateThemeSwitch() {
    var theme = (state.settings && state.settings.theme) || "auto";
    var btns = document.querySelectorAll(".theme-switch button");
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle("active", btns[i].getAttribute("data-theme") === theme);
    }
  }

  /* ===== Header ===== */
  function providerById(pid) {
    var providers = state.providers || [];
    for (var i = 0; i < providers.length; i++) {
      if (providers[i].id === pid) {
        return providers[i];
      }
    }
    return null;
  }

  function modelById(providerId, modelId) {
    var provider = providerById(providerId);
    if (!provider) {
      return null;
    }
    var models = provider.models || [];
    for (var i = 0; i < models.length; i++) {
      if (models[i].id === modelId) {
        return models[i];
      }
    }
    return null;
  }

  /* ===== Подгрузка списков моделей провайдеров через API ===== */

  function apiModelsFor(providerId) {
    var cached = state.apiModels[providerId];
    return cached && cached.models ? cached.models : [];
  }

  function apiModelById(providerId, modelId) {
    var models = apiModelsFor(providerId);
    for (var i = 0; i < models.length; i++) {
      if (models[i].id === modelId) {
        return models[i];
      }
    }
    return null;
  }

  function requestApiModels(providerId, force) {
    if (!providerId) {
      return;
    }
    if (!force && apiModelsRequested[providerId]) {
      return;
    }
    apiModelsRequested[providerId] = true;
    if (!state.apiModels[providerId]) {
      state.apiModels[providerId] = { models: [], error: "" };
    }
    state.apiModels[providerId].loading = true;
    post({ type: "refresh_models", provider: providerId, force: !!force });
  }

  function requestModelsForProviders(force) {
    var providers = state.providers || [];
    for (var i = 0; i < providers.length; i++) {
      var provider = providers[i];
      // OpenRouter отдаёт список публично, остальным нужен ключ.
      if (!provider.has_key && provider.id !== "openrouter") {
        continue;
      }
      requestApiModels(provider.id, force);
    }
  }

  /* Слияние моделей конфига и подгруженного списка: конфиг первым. */
  function mergedModels(provider) {
    var result = [];
    var seen = {};
    var configModels = provider.models || [];
    for (var i = 0; i < configModels.length; i++) {
      var item = configModels[i];
      result.push({ id: item.id, name: item.name || item.id, model: item, api: false });
      seen[item.id] = true;
    }
    var apiModels = apiModelsFor(provider.id);
    for (var j = 0; j < apiModels.length; j++) {
      var entry = apiModels[j];
      if (seen[entry.id]) {
        continue;
      }
      result.push({ id: entry.id, name: entry.name || entry.id, model: entry, api: true });
    }
    return result;
  }

  /* Компактная подпись цены: только когда провайдер отдал числа. */
  function priceLabel(model) {
    if (!model || model.price_in === null || model.price_in === undefined) {
      return null;
    }
    var inPrice = Number(model.price_in);
    var outPrice = model.price_out === null || model.price_out === undefined
      ? inPrice : Number(model.price_out);
    if (!isFinite(inPrice) || !isFinite(outPrice)) {
      return null;
    }
    if (inPrice === 0 && outPrice === 0) {
      return el("span", "mp-price mp-free", t("mp.free"));
    }
    var span = el("span", "mp-price", "$" + formatPrice(inPrice) + " / $" + formatPrice(outPrice));
    span.title = t("mp.price_title");
    return span;
  }

  function formatPrice(value) {
    if (value === 0) {
      return "0";
    }
    if (value < 0.01) {
      return value.toFixed(3);
    }
    return value.toFixed(2);
  }

  /* Подпись модели для дропдауна настроек: имя плюс цена, если она известна. */
  function modelOptionLabel(model) {
    var label = model.name || model.id;
    if (!model || model.price_in === null || model.price_in === undefined) {
      return label;
    }
    var inPrice = Number(model.price_in);
    var outPrice = model.price_out === null || model.price_out === undefined
      ? inPrice : Number(model.price_out);
    if (!isFinite(inPrice) || !isFinite(outPrice)) {
      return label;
    }
    if (inPrice === 0 && outPrice === 0) {
      return label + "  · " + t("mp.free");
    }
    return label + "  · $" + formatPrice(inPrice) + "/$" + formatPrice(outPrice);
  }

  function settingsModelOptions(provider) {
    var merged = mergedModels(provider);
    var options = [];
    for (var i = 0; i < merged.length; i++) {
      options.push({ value: merged[i].id, label: modelOptionLabel(merged[i].model) });
    }
    return options;
  }

  function renderHeader() {
    var s = state.settings || {};
    var provider = providerById(s.active_provider);
    // Провайдер без ключа не может отвечать: показываем нейтральный текст.
    if (!provider || !provider.has_key) {
      byId("modelStatus").textContent = t("mp.no_model");
      return;
    }
    var providerName = provider ? provider.name : (s.active_provider || "—");
    var modelName = s.active_model || "—";
    var model = null;
    if (provider) {
      var models = provider.models || [];
      for (var i = 0; i < models.length; i++) {
        if (models[i].id === s.active_model) {
          model = models[i];
          break;
        }
      }
    }
    if (model && model.name) {
      modelName = model.name;
    }
    byId("modelStatus").textContent = providerName + " · " + modelName;
  }

  /* ===== Модель-пикер ===== */
  function renderModelChip() {
    var visionSlot = byId("modelChipVision");
    visionSlot.innerHTML = "";
    var s = state.settings || {};
    var provider = providerById(s.active_provider);
    // Нет ключа — конкретная модель неактуальна, показываем нейтральный текст.
    if (!provider || !provider.has_key) {
      byId("modelChipLabel").textContent = t("mp.no_model");
      return;
    }
    var providerName = provider ? provider.name : (s.active_provider || "—");
    var modelName = s.active_model || "—";
    var model = null;
    if (provider) {
      var models = provider.models || [];
      for (var i = 0; i < models.length; i++) {
        if (models[i].id === s.active_model) {
          model = models[i];
          modelName = models[i].name || models[i].id;
          break;
        }
      }
    }
    byId("modelChipLabel").textContent = providerName + " · " + modelName;
    // Значок зрения активной модели прямо на кнопке выбора модели.
    var eye = visionEye(model);
    if (eye) {
      visionSlot.appendChild(eye);
    }
  }

  // Значок зрения модели: 👁 — принимает изображения, перечёркнутый 👁 —
  // не принимает, null — поддержка неизвестна (ничего не рисуем).
  function visionEye(model) {
    if (!model || model.vision === null || model.vision === undefined) {
      return null;
    }
    if (model.vision) {
      var eye = el("span", "mp-vision", "👁");
      eye.title = t("mp.vision_supported");
      return eye;
    }
    var noEye = el("span", "mp-vision mp-vision-no", "👁");
    noEye.title = t("mp.vision_none");
    return noEye;
  }

  // Значение зрения для отправки на бэкенд: true/false/null (не знаю).
  function visionPayload(value) {
    if (value === "true") {
      return true;
    }
    if (value === "false") {
      return false;
    }
    return null;
  }

  // Текущий выбор зрения модели в виде строки для дропдауна.
  function modelVisionChoice(model) {
    if (!model || model.vision === null || model.vision === undefined) {
      return "unknown";
    }
    return model.vision ? "true" : "false";
  }

  function openModelPicker() {
    byId("mpSearch").value = "";
    requestModelsForProviders(false);
    renderModelPicker();
    byId("modelPickerModal").style.display = "flex";
    byId("mpSearch").focus();
  }

  function closeModelPicker() {
    byId("modelPickerModal").style.display = "none";
  }

  function refreshModelPicker() {
    requestModelsForProviders(true);
    renderModelPicker();
  }

  function renderModelPicker() {
    var list = byId("mpList");
    var prevScroll = list.scrollTop;
    list.innerHTML = "";
    var query = byId("mpSearch").value.trim().toLowerCase();
    var providers = state.providers || [];
    var withModels = [];
    for (var i = 0; i < providers.length; i++) {
      var prov = providers[i];
      // Показываем только провайдеров с непустым API-ключом и хотя бы одной моделью.
      var hasKey = !!prov.has_key;
      if (mergedModels(prov).length > 0 && hasKey) {
        withModels.push(prov);
      }
    }
    var s = state.settings || {};
    var activeProvider = s.active_provider;
    var activeModel = s.active_model;
    var single = withModels.length <= 1;
    var shown = 0;
    for (var p = 0; p < withModels.length; p++) {
      var provider = withModels[p];
      var provName = provider.name || provider.id;
      var cached = state.apiModels[provider.id];
      if (cached && cached.loading && apiModelsFor(provider.id).length === 0) {
        provName += " …";
      }
      var provMatch = query && provName.toLowerCase().indexOf(query) !== -1;
      var models = mergedModels(provider).slice().sort(function (a, b) {
        var na = (a.name || a.id).toLowerCase();
        var nb = (b.name || b.id).toLowerCase();
        return na < nb ? -1 : (na > nb ? 1 : 0);
      });
      var groupItems = [];
      for (var m = 0; m < models.length; m++) {
        var model = models[m];
        var modelName = model.name || model.id;
        if (query && !provMatch && modelName.toLowerCase().indexOf(query) === -1) {
          continue;
        }
        groupItems.push(model);
      }
      if (groupItems.length === 0) {
        continue;
      }
      if (!single) {
        list.appendChild(el("div", "mp-group-title", provName));
      }
      for (var k = 0; k < groupItems.length; k++) {
        var item = groupItems[k];
        var isActive = provider.id === activeProvider && item.id === activeModel;
        var isDefault = (provider.id + "::" + item.id) === (s.default_model || "");
        var row = el("div", "mp-item" + (isActive ? " active" : ""));
        row.setAttribute("data-provider", provider.id);
        row.setAttribute("data-model", item.id);
        row.appendChild(el("span", "mp-item-name", item.name || item.id));
        var eye = visionEye(item.model);
        if (eye) {
          row.appendChild(eye);
        }
        var price = priceLabel(item.model);
        if (price) {
          row.appendChild(price);
        }
        row.appendChild(el("code", "mp-item-id", item.id));
        var star = el("button", "mp-star" + (isDefault ? " active" : ""), isDefault ? "★" : "☆");
        star.type = "button";
        star.title = t("mp.default_set");
        (function (pid, mid) {
          star.addEventListener("click", function (e) {
            e.stopPropagation();
            post({ type: "set_default_model", provider: pid, model: mid });
          });
        })(provider.id, item.id);
        row.appendChild(star);
        (function (pid, mid, isApi) {
          row.addEventListener("click", function () {
            // Модель из подгруженного списка сначала добавляется в конфиг.
            post(
              isApi
                ? { type: "set_api_model", provider: pid, model_id: mid }
                : { type: "set_model", provider: pid, model: mid }
            );
            closeModelPicker();
          });
        })(provider.id, item.id, item.api);
        list.appendChild(row);
        shown++;
      }
    }
    if (shown === 0) {
      // Различаем «ключ не задан» и «ничего не нашлось по поиску».
      var hasAnyKey = false;
      for (var q = 0; q < providers.length; q++) {
        if (providers[q].has_key && mergedModels(providers[q]).length > 0) {
          hasAnyKey = true;
          break;
        }
      }
      if (hasAnyKey) {
        list.appendChild(el("div", "mp-empty", t("common.nothing")));
      } else {
        list.appendChild(el("div", "mp-empty", t("mp.need_key")));
        var settingsBtn = el("button", "ghost-btn mp-empty-action", t("mp.open_settings"));
        settingsBtn.type = "button";
        settingsBtn.addEventListener("click", function () {
          closeModelPicker();
          openSettings();
        });
        list.appendChild(settingsBtn);
      }
    }
    // Фоновое обновление (например, уточнение зрения) не должно сбрасывать
    // прокрутку у открытого списка.
    list.scrollTop = prevScroll;
  }

  /* ===== Sidebar ===== */
  function groupChats(chats) {
    var groups = { pinned: [], today: [], yesterday: [], earlier: [] };
    var now = new Date();
    var startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var startOfYesterday = new Date(startOfToday.getTime() - 86400000);
    for (var i = 0; i < chats.length; i++) {
      var chat = chats[i];
      if (chat.pinned) {
        groups.pinned.push(chat);
        continue;
      }
      var d = new Date(chat.updated || 0);
      if (d >= startOfToday) {
        groups.today.push(chat);
      } else if (d >= startOfYesterday) {
        groups.yesterday.push(chat);
      } else {
        groups.earlier.push(chat);
      }
    }
    return groups;
  }

  function sortByUpdated(list) {
    list.sort(function (a, b) {
      return (b.updated || 0) - (a.updated || 0);
    });
  }

  function renameChat(chat) {
    var title = window.prompt(t("sidebar.rename_prompt"), chat.title || "");
    if (title !== null) {
      post({ type: "rename_chat", id: chat.id, title: title.trim() || t("common.new_chat") });
    }
  }

  function deleteChat(chat) {
    if (window.confirm(t("sidebar.delete_confirm", { title: chat.title || t("common.new_chat") }))) {
      post({ type: "delete_chat", id: chat.id });
    }
  }

  function chatItem(chat) {
    var item = el("div", "chat-item" + (chat.id === state.active ? " active" : ""));
    item.tabIndex = 0;
    item.setAttribute("role", "button");
    item.setAttribute("aria-label", chat.title || t("common.new_chat"));
    item.appendChild(el("div", "chat-title", chat.title || t("common.new_chat")));
    var actions = el("div", "chat-actions");
    var pinBtn = el("button", "chat-action", "📌");
    pinBtn.type = "button";
    pinBtn.title = chat.pinned ? t("common.unpin") : t("common.pin");
    pinBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      post({ type: "toggle_pin", id: chat.id });
    });
    var renameBtn = el("button", "chat-action", "✏️");
    renameBtn.type = "button";
    renameBtn.title = t("common.rename");
    renameBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      renameChat(chat);
    });
    var delBtn = el("button", "chat-action", "🗑");
    delBtn.type = "button";
    delBtn.title = t("common.delete");
    delBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      deleteChat(chat);
    });
    actions.appendChild(pinBtn);
    actions.appendChild(renameBtn);
    actions.appendChild(delBtn);
    item.appendChild(actions);
    item.addEventListener("click", function () {
      post({ type: "pick_chat", id: chat.id });
    });
    item.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        post({ type: "pick_chat", id: chat.id });
      }
    });
    return item;
  }

  // Поиск по заголовку и по тексту сообщений чата.
  function chatMatches(chat, query) {
    if ((chat.title || "").toLowerCase().indexOf(query) !== -1) {
      return true;
    }
    var msgs = chat.msgs || [];
    for (var i = 0; i < msgs.length; i++) {
      var text = msgs[i] && typeof msgs[i].text === "string" ? msgs[i].text : "";
      if (text.toLowerCase().indexOf(query) !== -1) {
        return true;
      }
    }
    return false;
  }

  function renderSidebar() {
    var list = byId("chatList");
    list.innerHTML = "";
    var query = byId("searchInput").value.trim().toLowerCase();
    var chats = state.chats || [];
    if (query) {
      // Режим поиска: плоский список совпадений по названию и тексту сообщений
      var filtered = [];
      for (var i = 0; i < chats.length; i++) {
        if (chatMatches(chats[i], query)) {
          filtered.push(chats[i]);
        }
      }
      for (var j = 0; j < filtered.length; j++) {
        list.appendChild(chatItem(filtered[j]));
      }
      if (filtered.length === 0) {
        list.appendChild(el("div", "sidebar-empty", t("common.nothing")));
      }
      return;
    }
    var groups = groupChats(chats);
    sortByUpdated(groups.pinned);
    sortByUpdated(groups.today);
    sortByUpdated(groups.yesterday);
    sortByUpdated(groups.earlier);
    var groupTitles = [
      ["pinned", t("sidebar.pinned")],
      ["today", t("sidebar.today")],
      ["yesterday", t("sidebar.yesterday")],
      ["earlier", t("sidebar.earlier")]
    ];
    var any = false;
    for (var g = 0; g < groupTitles.length; g++) {
      var key = groupTitles[g][0];
      var label = groupTitles[g][1];
      var items = groups[key];
      if (items.length === 0) {
        continue;
      }
      any = true;
      list.appendChild(el("div", "chat-group", label));
      for (var k = 0; k < items.length; k++) {
        list.appendChild(chatItem(items[k]));
      }
    }
    if (!any) {
      list.appendChild(el("div", "sidebar-empty", t("sidebar.empty")));
    }
  }

  /* ===== Сообщения ===== */
  function actionBtn(label, handler) {
    var btn = el("button", "msg-action", label);
    btn.type = "button";
    btn.addEventListener("click", handler);
    return btn;
  }

  /* ===== Разметка Markdown =====
     Безопасный рендер без внешних библиотек: сначала экранируем HTML, затем
     разбираем блочные и встроенные конструкции. Ссылки допускаются только с
     http/https/mailto, поэтому вставка скриптов из ответа модели невозможна. */
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function safeHref(url) {
    var u = String(url || "").trim();
    return /^(https?:|mailto:)/i.test(u) ? u : "";
  }

  // Встроенные элементы: код, ссылки, жирный, курсив, зачёркнутый.
  function mdInline(text) {
    var parts = String(text).split("`");
    var placeholders = [];
    for (var i = 1; i < parts.length; i += 2) {
      placeholders.push(parts[i]);
      parts[i] = "\u0000" + (placeholders.length - 1) + "\u0000";
    }
    var out = parts.join("");
    out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (m, label, url) {
      var href = safeHref(url.replace(/&amp;/g, "&"));
      if (!href) {
        return label;
      }
      return (
        '<a href="' + escapeHtml(href) + '" target="_blank" rel="noopener noreferrer">' +
        label + "</a>"
      );
    });
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    out = out.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    out = out.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
    out = out.replace(/~~([^~]+)~~/g, "<del>$1</del>");
    out = out.replace(/\u0000(\d+)\u0000/g, function (m, n) {
      return "<code>" + placeholders[parseInt(n, 10)] + "</code>";
    });
    return out;
  }

  // Блок кода с кнопкой копирования. Код уже экранирован вызывающей стороной.
  function codeBlockHtml(code) {
    return (
      '<div class="md-code-wrap">' +
      '<button type="button" class="md-copy" title="' +
      escapeHtml(t("common.copy_code")) +
      '">' +
      escapeHtml(t("common.copy_code")) +
      "</button>" +
      '<pre class="md-code"><code>' +
      code +
      "</code></pre></div>"
    );
  }

  function renderMarkdown(raw) {
    var escaped = escapeHtml(raw);
    var lines = escaped.split("\n");
    var html = [];
    var i = 0;
    var inCode = false;
    var codeBuf = [];
    var listType = null;
    function closeList() {
      if (listType) {
        html.push("</" + listType + ">");
        listType = null;
      }
    }
    function isBlockStart(line) {
      return (
        /^```/.test(line) ||
        /^(#{1,6})\s+/.test(line) ||
        /^&gt;\s?/.test(line) ||
        /^\s*[-*+]\s+/.test(line) ||
        /^\s*\d+[.)]\s+/.test(line) ||
        /^(-{3,}|\*{3,}|_{3,})\s*$/.test(line)
      );
    }
    while (i < lines.length) {
      var line = lines[i];
      if (inCode) {
        if (/^```\s*$/.test(line)) {
          html.push(codeBlockHtml(codeBuf.join("\n")));
          inCode = false;
          codeBuf = [];
        } else {
          codeBuf.push(line);
        }
        i++;
        continue;
      }
      var fence = line.match(/^```\s*([\w+-]*)\s*$/);
      if (fence) {
        closeList();
        inCode = true;
        codeBuf = [];
        i++;
        continue;
      }
      var heading = line.match(/^(#{1,6})\s+(.*)$/);
      if (heading) {
        closeList();
        var level = heading[1].length;
        html.push("<h" + level + ">" + mdInline(heading[2]) + "</h" + level + ">");
        i++;
        continue;
      }
      var quote = line.match(/^&gt;\s?(.*)$/);
      if (quote) {
        closeList();
        html.push("<blockquote>" + mdInline(quote[1]) + "</blockquote>");
        i++;
        continue;
      }
      if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
        closeList();
        html.push("<hr>");
        i++;
        continue;
      }
      var ul = line.match(/^\s*[-*+]\s+(.*)$/);
      var ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
      if (ul || ol) {
        var want = ul ? "ul" : "ol";
        if (listType !== want) {
          closeList();
          listType = want;
          html.push("<" + want + ">");
        }
        html.push("<li>" + mdInline((ul || ol)[1]) + "</li>");
        i++;
        continue;
      }
      if (line.trim() === "") {
        closeList();
        i++;
        continue;
      }
      closeList();
      var para = [line];
      i++;
      while (i < lines.length && lines[i].trim() !== "" && !isBlockStart(lines[i])) {
        para.push(lines[i]);
        i++;
      }
      html.push("<p>" + mdInline(para.join("<br>")) + "</p>");
    }
    if (inCode) {
      html.push(codeBlockHtml(codeBuf.join("\n")));
    }
    closeList();
    return html.join("");
  }

  // Заполняет элемент текстом: Markdown для ответов ассистента, иначе — как есть.
  function setMessageText(node, text, markdown) {
    if (!node) {
      return;
    }
    if (markdown) {
      node.classList.add("md");
      node.innerHTML = renderMarkdown(text || "");
    } else {
      node.classList.remove("md");
      node.textContent = text || "";
    }
  }

  // Сворачиваемый блок размышлений reasoning-моделей.
  function buildReasoning(reasoning, open) {
    var det = document.createElement("details");
    det.className = "msg-reasoning";
    if (open) {
      det.open = true;
    }
    det.appendChild(el("summary", null, t("common.reasoning")));
    det.appendChild(el("div", "msg-reasoning-text", reasoning || ""));
    return det;
  }

  function renderMessage(msg, index, msgs) {
    var wrap = el("div", "msg-wrap msg-" + msg.role);
    if (msg.error) {
      wrap.classList.add("msg-error");
    }
    if (msg.role === "system") {
      wrap.appendChild(el("div", "msg-bubble", msg.text || ""));
      var sysActions = el("div", "msg-actions");
      sysActions.appendChild(actionBtn(t("common.copy"), function () {
        copyText(msg.text || "");
      }));
      wrap.appendChild(sysActions);
      return wrap;
    }
    var bubble = el("div", "msg-bubble");
    var images = [];
    if (msg.image) {
      images.push(msg.image);
    }
    if (msg.file && msg.file.name) {
      bubble.appendChild(el("span", "msg-file", "📄 " + msg.file.name));
    }
    if (msg.attachments && msg.attachments.length) {
      for (var ai = 0; ai < msg.attachments.length; ai++) {
        var att = msg.attachments[ai];
        if (att && att.image) {
          images.push(att.image);
        } else if (att && att.kind === "image") {
          bubble.appendChild(
            el("span", "msg-file", "🖼 " + (att.name || t("common.attachment")))
          );
        } else if (att && att.file && att.file.name) {
          bubble.appendChild(el("span", "msg-file", "📄 " + att.file.name));
        }
      }
    }
    for (var ii = 0; ii < images.length; ii++) {
      var img = document.createElement("img");
      img.className = "msg-image";
      img.src = images[ii];
      img.alt = t("common.attachment");
      bubble.appendChild(img);
    }
    if (msg.reasoning) {
      bubble.appendChild(buildReasoning(msg.reasoning, false));
    }
    var textNode = el("div", "msg-text");
    setMessageText(textNode, msg.text || "", msg.role === "assistant");
    bubble.appendChild(textNode);
    var timeRow = el("div", "msg-time", formatTime(msg.ts));
    var meta = usageMeta(msg);
    if (meta) {
      timeRow.appendChild(meta);
    }
    bubble.appendChild(timeRow);
    wrap.appendChild(bubble);
    var actions = el("div", "msg-actions");
    if (msg.role === "assistant") {
      actions.appendChild(actionBtn(t("common.copy"), function () {
        copyText(msg.text || "");
      }));
      if (index === msgs.length - 1) {
        actions.appendChild(actionBtn(t("common.regenerate"), function () {
          post({ type: "regenerate" });
        }));
      }
      var variants = msg.variants;
      if (!msg.error && Array.isArray(variants) && variants.length > 1) {
        var vi = typeof msg.variant_index === "number" ? msg.variant_index : variants.length - 1;
        if (vi < 0 || vi >= variants.length) {
          vi = variants.length - 1;
        }
        var nav = el("span", "variant-nav");
        if (vi > 0) {
          nav.appendChild(actionBtn("‹", function () {
            post({ type: "switch_variant", chat_id: state.active, index: vi - 1 });
          }));
        }
        nav.appendChild(el("span", "variant-pos", (vi + 1) + "/" + variants.length));
        if (vi < variants.length - 1) {
          nav.appendChild(actionBtn("›", function () {
            post({ type: "switch_variant", chat_id: state.active, index: vi + 1 });
          }));
        }
        actions.appendChild(nav);
      }
    } else if (msg.role === "user") {
      actions.appendChild(actionBtn(t("common.edit"), function () {
        startEdit(msg);
      }));
    }
    wrap.appendChild(actions);
    return wrap;
  }

  function renderWelcome() {
    var wrap = el("div", "welcome");
    wrap.appendChild(el("div", "welcome-title", "FlowSlice AI"));
    wrap.appendChild(el("div", "welcome-sub", t("welcome.sub")));
    var list = el("div", "welcome-cmds");
    var cmds = ["/context", "/clear", "/model", "/printer", "/stats", "/help", "/reset"];
    for (var i = 0; i < cmds.length; i++) {
      list.appendChild(el("span", "welcome-cmd", cmds[i]));
    }
    wrap.appendChild(list);
    return wrap;
  }

  function renderMessages() {
    var container = byId("messages");
    container.innerHTML = "";
    streamTextEl = null;
    streamThoughtEl = null;
    var chat = getActiveChat();
    if (!chat || !chat.msgs || chat.msgs.length === 0) {
      container.appendChild(renderWelcome());
      return;
    }
    var msgs = chat.msgs;
    if (chat.summary) {
      container.appendChild(el("div", "compact-note", t("compact.indicator", { n: String(chat.summary_count || 0) })));
    }
    for (var i = 0; i < msgs.length; i++) {
      container.appendChild(renderMessage(msgs[i], i, msgs));
    }
    // Ссылка на последнее сообщение assistant для стриминга
    for (var j = msgs.length - 1; j >= 0; j--) {
      if (msgs[j].role === "assistant") {
        var wraps = container.querySelectorAll(".msg-assistant");
        if (wraps.length > 0) {
          var lastWrap = wraps[wraps.length - 1];
          var textEl = lastWrap.querySelector(".msg-text");
          if (textEl) {
            streamTextEl = textEl;
          }
          var thoughtEl = lastWrap.querySelector(".msg-reasoning-text");
          if (thoughtEl) {
            streamThoughtEl = thoughtEl;
          }
        }
        break;
      }
    }
    // Перерисовка во время стрима не должна терять накопленный текст.
    if (state.status === "streaming" && streamTextEl) {
      setMessageText(streamTextEl, streamText, true);
    }
    if (state.status === "streaming" && streamThoughtEl) {
      streamThoughtEl.textContent = streamThought;
    }
    // Прокручиваем вниз только по явному запросу, чтобы не мешать чтению.
    scrollToBottom(pendingForceScroll);
    pendingForceScroll = false;
  }

  function scrollToBottom(force) {
    var container = byId("messages");
    if (force || !userScrolledUp) {
      container.scrollTop = container.scrollHeight;
      userScrolledUp = false;
    }
    updateScrollButton();
  }

  function onMessagesScroll() {
    var container = byId("messages");
    var nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    userScrolledUp = !nearBottom;
    updateScrollButton();
  }

  // Показывает кнопку возврата к последнему сообщению.
  function updateScrollButton() {
    var btn = byId("scrollBottom");
    if (!btn) {
      return;
    }
    btn.style.display = userScrolledUp ? "flex" : "none";
  }

  /* ===== Токены запроса (текст сообщения + вложения) ===== */
  function updateRequestTokens() {
    var el = byId("requestTokens");
    if (!el) {
      return;
    }
    var input = byId("input");
    var total = input ? Math.ceil(input.value.length / 4) : 0;
    for (var i = 0; i < attachments.length; i++) {
      var att = attachments[i];
      if (att.kind === "image") {
        // Оценка как в Anthropic: площадь / 750, минимум 85.
        total += att.tokens || 1100;
      } else {
        total += Math.ceil(String(att.data || "").length / 4);
      }
    }
    el.textContent = "≈ " + t("ctx.request_tokens", { n: total });
  }

  /* ===== Панель контекста ===== */
  function renderContext() {
    var container = byId("contextChecks");
    container.innerHTML = "";
    var flags = state.context_flags || {};
    var modes = state.context_modes || {};
    var modeDDs = {};
    // Собирает и отправляет текущие флаги и режимы пресетов.
    function collect() {
      var newFlags = {};
      var newModes = {};
      var items = container.querySelectorAll(".ctx-item");
      for (var n = 0; n < items.length; n++) {
        var itemKey = items[n].getAttribute("data-key");
        var box = items[n].querySelector("input[type=checkbox]");
        newFlags[itemKey] = box ? box.checked : false;
        if (modeDDs[itemKey]) {
          newModes[itemKey] = modeDDs[itemKey].getSelected();
        }
      }
      post({ type: "set_context_flags", flags: newFlags, modes: newModes });
    }
    for (var i = 0; i < CONTEXT_KEYS.length; i++) {
      var key = CONTEXT_KEYS[i];
      var item = el("span", "ctx-item");
      item.setAttribute("data-key", key);
      var checkWrap = el("label", "ctx-check");
      // Тултип: пояснение, что именно этот пункт добавляет в контекст,
      // а для пресетов и модели — ещё и смысл режимов выгрузки.
      var helpText = t("ctx." + key + "_help");
      var isPresetMode = CONTEXT_MODE_KEYS.indexOf(key) >= 0;
      var isModelMode = key === CONTEXT_MODEL_KEY;
      if (isPresetMode) {
        helpText += "\n\n" + t("ctx.mode_help");
      } else if (isModelMode) {
        helpText += "\n\n" + t("ctx.model_mode_help");
      }
      checkWrap.setAttribute("data-tooltip", helpText);
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!flags[key];
      cb.addEventListener("change", collect);
      checkWrap.appendChild(cb);
      checkWrap.appendChild(document.createTextNode(t(CONTEXT_LABELS[key] || key)));
      item.appendChild(checkWrap);
      container.appendChild(item);
      if (isPresetMode || isModelMode) {
        // Режим выгрузки: штатный дропдаун проекта (без поиска).
        var modeWrap = el("span", "ctx-mode-dd");
        var modeHost = el("span");
        modeHost.id = "ctxMode_" + key;
        modeWrap.appendChild(modeHost);
        item.appendChild(modeWrap);
        var modeOptions = isModelMode
          ? CONTEXT_MODEL_MODES.map(function (value) {
              return { value: value, label: t("ctx.model_mode_" + value) };
            })
          : [
              { value: "changed", label: t("ctx.mode_changed") },
              { value: "all", label: t("ctx.mode_all") }
            ];
        var modeDefault = isModelMode
          ? (CONTEXT_MODEL_MODES.indexOf(modes[key]) >= 0 ? modes[key] : "full")
          : (modes[key] === "all" ? "all" : "changed");
        modeDDs[key] = makeDropdown(
          modeHost.id,
          modeOptions,
          modeDefault,
          collect,
          null,
          false
        );
        // Подсказка на самой выпадайке: выбор режима выгрузки.
        var modeBtn = modeWrap.querySelector(".dd-btn");
        if (modeBtn) {
          modeBtn.setAttribute(
            "data-tooltip",
            t(isModelMode ? "ctx.model_mode_title" : "ctx.mode_title")
          );
        }
      }
    }
    byId("contextTokens").textContent = "≈ " + t("ctx.tokens", { n: state.context_tokens || 0 });
  }

  /* ===== Индикатор «печатает…» ===== */
  function updateTyping() {
    var streaming = state.status === "streaming";
    byId("typing").style.display = streaming ? "flex" : "none";
    byId("stopBtn").style.display = streaming ? "block" : "none";
  }

  /* ===== Полный ререндер по state ===== */
  function renderState() {
    renderHeader();
    renderModelChip();
    renderSidebar();
    renderContext();
    updateRequestTokens();
    renderMessages();
    applyTheme(state.settings);
    applyFont(state.settings);
    updateTyping();
    applyI18n();
  }

  /* ===== Вложения ===== */
  function renderAttachments() {
    var container = byId("attachPreview");
    container.innerHTML = "";
    for (var i = 0; i < attachments.length; i++) {
      var att = attachments[i];
      var card = el("div", "attach-card");
      if (att.kind === "image") {
        var thumb = document.createElement("img");
        thumb.src = att.data;
        thumb.alt = att.name;
        card.appendChild(thumb);
      } else {
        card.appendChild(el("span", "attach-icon", "📄"));
      }
      card.appendChild(el("span", "attach-name", att.name));
      var removeBtn = el("button", "attach-remove", "✕");
      removeBtn.type = "button";
      removeBtn.title = t("common.remove_attachment");
      removeBtn.addEventListener("click", (function (idx) {
        return function () {
          attachments.splice(idx, 1);
          renderAttachments();
        };
      })(i));
      card.appendChild(removeBtn);
      container.appendChild(card);
    }
    updateRequestTokens();
  }

  /* Нативный пикер (Chromium/WebView2) с жёстким фильтром без «Все файлы». */
  function filePickerTypes() {
    return [
      {
        description: t("attach.type_image"),
        accept: { "image/*": [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"] }
      },
      {
        description: t("attach.type_text"),
        accept: {
          "text/plain": [".txt", ".md", ".log", ".gcode", ".ini", ".cfg", ".yaml", ".yml"],
          "application/json": [".json"],
          "text/csv": [".csv"]
        }
      }
    ];
  }

  function pickFiles() {
    if (typeof window.showOpenFilePicker === "function") {
      window.showOpenFilePicker({
        multiple: true,
        excludeAcceptAllOption: true,
        types: filePickerTypes()
      })
        .then(function (handles) {
          return Promise.all(handles.map(function (handle) {
            return handle.getFile();
          }));
        })
        .then(function (files) {
          handleFiles(files);
        })
        .catch(function (err) {
          if (err && err.name === "AbortError") {
            return;
          }
          // Фильтр не поддержан — откатываемся на обычный input.
          byId("fileInput").click();
        });
      return;
    }
    byId("fileInput").click();
  }

  function handleFiles(fileList) {
    var files = Array.prototype.slice.call(fileList);
    files.forEach(function (file) {
      if (attachments.length >= MAX_ATTACHMENTS) {
        showToast(t("attach.limit_count", { n: MAX_ATTACHMENTS }), "err");
        return;
      }
      if (file.size && file.size > MAX_ATTACHMENT_BYTES) {
        showToast(t("attach.limit_size", { name: file.name || "" }), "err");
        return;
      }
      var name = file.name || t("attach.default_name");
      if (file.type && file.type.indexOf("image/") === 0) {
        // Фото: сжатие через canvas до 1024px по большей стороне
        var imgReader = new FileReader();
        imgReader.onerror = function () {
          showToast(t("attach.read_failed", { name: name }), "err");
        };
        imgReader.onload = function (e) {
          var img = new Image();
          img.onerror = function () {
            showToast(t("attach.image_failed", { name: name }), "err");
          };
          img.onload = function () {
            var maxSide = 1024;
            var scale = Math.min(1, maxSide / Math.max(img.width, img.height));
            var w = Math.round(img.width * scale);
            var h = Math.round(img.height * scale);
            var canvas = document.createElement("canvas");
            canvas.width = w;
            canvas.height = h;
            var ctx = canvas.getContext("2d");
            if (!ctx) {
              showToast(t("attach.image_failed", { name: name }), "err");
              return;
            }
            ctx.drawImage(img, 0, 0, w, h);
            var data = "";
            try {
              data = canvas.toDataURL("image/jpeg", 0.85);
            } catch (err) {
              console.error("Не удалось закодировать изображение:", err);
              showToast(t("attach.image_failed", { name: name }), "err");
              return;
            }
            attachments.push({
              kind: "image",
              name: name,
              tokens: Math.max(85, Math.ceil((w * h) / 750)),
              data: data
            });
            renderAttachments();
          };
          img.src = e.target.result;
        };
        imgReader.readAsDataURL(file);
      } else {
        // Текстовый файл
        var textReader = new FileReader();
        textReader.onload = function (e) {
          var text = String(e.target.result || "");
          // Бинарные файлы (STL, 3MF и др.) читать как текст нельзя —
          // они засоряют запрос нечитаемыми байтами.
          if (text.indexOf("\u0000") !== -1) {
            showToast(t("attach.binary_unsupported", { name: name }), "err");
            return;
          }
          if (text.length > MAX_TEXT_CHARS) {
            showToast(t("attach.file_too_big", { name: name }), "err");
            return;
          }
          attachments.push({
            kind: "text",
            name: name,
            tokens: Math.ceil(text.length / 4),
            data: text
          });
          renderAttachments();
        };
        textReader.onerror = function () {
          showToast(t("attach.read_failed", { name: name }), "err");
        };
        textReader.readAsText(file);
      }
    });
  }

  /* Вставка изображения из буфера обмена (Ctrl+V). Текстовую вставку не трогаем. */
  function handlePaste(e) {
    if (!e.clipboardData || !e.clipboardData.items) {
      return;
    }
    var files = [];
    for (var i = 0; i < e.clipboardData.items.length; i++) {
      var item = e.clipboardData.items[i];
      if (item.kind === "file") {
        var file = item.getAsFile();
        if (file) {
          files.push(file);
        }
      }
    }
    if (files.length > 0) {
      e.preventDefault();
      handleFiles(files);
    }
  }

  /* Перетаскивание файлов на область чата. */
  function dragHasFiles(e) {
    var types = (e.dataTransfer && e.dataTransfer.types) || [];
    for (var i = 0; i < types.length; i++) {
      if (types[i] === "Files") {
        return true;
      }
    }
    return false;
  }

  function setupDragDrop() {
    var main = document.querySelector(".main");
    if (!main) {
      return;
    }
    var depth = 0; // dragenter/dragleave приходят и для дочерних элементов
    main.addEventListener("dragenter", function (e) {
      if (!dragHasFiles(e)) {
        return;
      }
      e.preventDefault();
      depth += 1;
      main.classList.add("drag-over");
    });
    main.addEventListener("dragover", function (e) {
      if (!dragHasFiles(e)) {
        return;
      }
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    });
    main.addEventListener("dragleave", function () {
      depth = Math.max(0, depth - 1);
      if (depth === 0) {
        main.classList.remove("drag-over");
      }
    });
    main.addEventListener("drop", function (e) {
      if (!dragHasFiles(e)) {
        return;
      }
      e.preventDefault();
      depth = 0;
      main.classList.remove("drag-over");
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
        handleFiles(e.dataTransfer.files);
      }
    });
    // Сброс подсветки, если файл уронили вне области чата.
    window.addEventListener("drop", function () {
      depth = 0;
      main.classList.remove("drag-over");
    });
  }

  /* ===== Отправка сообщения ===== */
  /* ===== История ввода (стрелки вверх/вниз) ===== */
  // Копия вложений: объекты плоские (строки data/name), достаточно поэлементно.
  function cloneAttachments(list) {
    var copy = [];
    for (var i = 0; i < list.length; i++) {
      var att = list[i];
      copy.push({
        kind: att.kind,
        name: att.name,
        tokens: att.tokens,
        data: att.data
      });
    }
    return copy;
  }

  function pushInputHistory(text, list) {
    inputHistory.push({ text: text, attachments: cloneAttachments(list) });
    if (inputHistory.length > HISTORY_LIMIT) {
      inputHistory.shift();
    }
  }

  // Показываем запись истории (или черновик) в поле ввода.
  function applyHistoryEntry(entry) {
    byId("input").value = entry.text || "";
    attachments = cloneAttachments(entry.attachments || []);
    renderAttachments();
    autoResize();
    updateRequestTokens();
    var input = byId("input");
    input.focus();
    // Курсор в конец, чтобы следующая стрелка вверх продолжила навигацию.
    input.setSelectionRange(input.value.length, input.value.length);
  }

  // direction: -1 — вверх (к старым), 1 — вниз (к новым/черновику).
  function navigateHistory(direction) {
    if (inputHistory.length === 0) {
      return false;
    }
    if (direction < 0) {
      if (historyIndex === -1) {
        // Вход в историю: запоминаем текущий черновик.
        historyDraft = { text: byId("input").value, attachments: cloneAttachments(attachments) };
        historyIndex = inputHistory.length - 1;
      } else if (historyIndex > 0) {
        historyIndex -= 1;
      } else {
        return true; // уже на самом старом запросе
      }
      applyHistoryEntry(inputHistory[historyIndex]);
      return true;
    }
    if (historyIndex === -1) {
      return false; // уже в черновике
    }
    historyIndex += 1;
    if (historyIndex >= inputHistory.length) {
      historyIndex = -1;
      var draft = historyDraft || { text: "", attachments: [] };
      historyDraft = null;
      applyHistoryEntry(draft);
      return true;
    }
    applyHistoryEntry(inputHistory[historyIndex]);
    return true;
  }

  function sendMessage() {
    var input = byId("input");
    var text = input.value.trim();
    if (!text && attachments.length === 0) {
      return;
    }
    for (var i = 0; i < attachments.length; i++) {
      if (!attachments[i].ready) {
        showToast(t("attach.reading"), "err");
        return;
      }
    }
    var totalChars = 0;
    for (var j = 0; j < attachments.length; j++) {
      if (attachments[j].kind === "text") {
        totalChars += String(attachments[j].data || "").length;
      }
    }
    if (totalChars > MAX_TOTAL_TEXT_CHARS) {
      showToast(t("attach.files_total_too_big"), "err");
      return;
    }
    var editId = pendingEditId;
    pendingEditId = null;
    var payload = { type: "chat", text: text };
    // Вложения уходят тем же сообщением, что и текст: отдельные attach_file
    // могли теряться при быстрой отправке.
    if (attachments.length) {
      payload.attachments = attachments.slice();
    }
    if (editId) {
      payload.edit_id = editId;
    }
    post(payload);
    // После отправки всегда показываем последнее сообщение, даже если
    // пользователь был прокручен вверх.
    pendingForceScroll = true;
    // В историю навигации попадают только обычные отправки (не правки).
    if (!editId) {
      pushInputHistory(text, attachments);
    }
    historyIndex = -1;
    historyDraft = null;
    attachments = [];
    renderAttachments();
    byId("input").value = "";
    autoResize();
    updateRequestTokens();
    byId("input").focus();
  }

  function startEdit(msg) {
    pendingEditId = msg.id;
    byId("input").value = msg.text || "";
    autoResize();
    updateRequestTokens();
    byId("input").focus();
  }

  function copyText(text) {
    var value = text || "";
    // Шаг 1: современный async API буфера обмена
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      try {
        navigator.clipboard.writeText(value).then(function () {
          showToast(t("common.copied"), "ok");
        }, function () {
          copyTextFallback(value);
        });
        return;
      } catch (err) {
        copyTextFallback(value);
        return;
      }
    }
    copyTextFallback(value);
  }

  function copyTextFallback(value) {
    // Шаг 2: скрытый textarea + execCommand("copy")
    var ok = false;
    try {
      var ta = document.createElement("textarea");
      ta.value = value;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.top = "-1000px";
      ta.style.left = "-1000px";
      document.body.appendChild(ta);
      ta.select();
      ok = document.execCommand("copy");
      document.body.removeChild(ta);
    } catch (err) {
      ok = false;
    }
    if (ok) {
      showToast(t("common.copied"), "ok");
      return;
    }
    // Шаг 3: ручное копирование — модалка с авто-выделением
    showToast(t("common.copy_failed"), "err");
    var textEl = byId("copyModalText");
    textEl.value = value;
    byId("copyModal").style.display = "flex";
    textEl.focus();
    textEl.select();
  }

  function closeCopyModal() {
    byId("copyModal").style.display = "none";
  }

  function autoResize() {
    var input = byId("input");
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
  }

  /* ===== Автодополнение команд по «/» ===== */
  var cmdSuggestIndex = -1;
  var cmdSuggestMatches = [];

  function cmdSuggestOpen() {
    return byId("cmdSuggest").style.display !== "none";
  }

  function setCmdActive(idx) {
    var list = byId("cmdSuggest");
    var items = list.querySelectorAll(".cmd-suggest-item");
    for (var i = 0; i < items.length; i++) {
      items[i].classList.remove("active");
    }
    if (items[idx]) {
      items[idx].classList.add("active");
    }
    cmdSuggestIndex = idx;
  }

  function closeCmdSuggest() {
    byId("cmdSuggest").style.display = "none";
    byId("cmdSuggest").innerHTML = "";
    cmdSuggestIndex = -1;
    cmdSuggestMatches = [];
  }

  function chooseCmd(cmd) {
    byId("input").value = cmd;
    closeCmdSuggest();
    sendMessage();
  }

  function updateCmdSuggest() {
    var input = byId("input");
    var text = input.value;
    var list = byId("cmdSuggest");
    if (text.charAt(0) !== "/" || text.indexOf("\n") !== -1) {
      closeCmdSuggest();
      return;
    }
    var query = text.toLowerCase();
    var commands = state.commands || [];
    var matches = [];
    for (var i = 0; i < commands.length; i++) {
      var cmd = commands[i].cmd || "";
      if (cmd.toLowerCase().indexOf(query) === 0) {
        matches.push(commands[i]);
      }
    }
    list.innerHTML = "";
    if (matches.length === 0) {
      list.appendChild(el("div", "cmd-suggest-empty", t("cmd.not_found")));
      list.style.display = "block";
      cmdSuggestIndex = -1;
      cmdSuggestMatches = [];
      return;
    }
    for (var j = 0; j < matches.length; j++) {
      (function (cmdObj, idx) {
        var item = el("div", "cmd-suggest-item");
        item.appendChild(el("span", "cmd-suggest-cmd", cmdObj.cmd));
        item.appendChild(el("span", "cmd-suggest-desc", cmdObj.desc || ""));
        item.addEventListener("click", function () {
          chooseCmd(cmdObj.cmd);
        });
        item.addEventListener("mousemove", function () {
          setCmdActive(idx);
        });
        list.appendChild(item);
      })(matches[j], j);
    }
    cmdSuggestMatches = matches;
    cmdSuggestIndex = 0;
    setCmdActive(0);
    list.style.display = "block";
  }

  function onInputKey(e) {
    if (cmdSuggestOpen()) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (cmdSuggestMatches.length > 0) {
          setCmdActive((cmdSuggestIndex + 1) % cmdSuggestMatches.length);
        }
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        if (cmdSuggestMatches.length > 0) {
          setCmdActive(
            (cmdSuggestIndex - 1 + cmdSuggestMatches.length) % cmdSuggestMatches.length
          );
        }
        return;
      }
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        if (cmdSuggestMatches[cmdSuggestIndex]) {
          e.preventDefault();
          chooseCmd(cmdSuggestMatches[cmdSuggestIndex].cmd);
          return;
        }
      }
      if (e.key === "Escape") {
        e.preventDefault();
        closeCmdSuggest();
        return;
      }
    }
    // Навигация по истории ввода: стрелки работают только на границе строки.
    if (
      (e.key === "ArrowUp" || e.key === "ArrowDown") &&
      !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey
    ) {
      var input = byId("input");
      var noSelection = input.selectionStart === input.selectionEnd;
      if (noSelection && e.key === "ArrowUp") {
        var before = input.value.slice(0, input.selectionStart);
        if (before.indexOf("\n") === -1 && navigateHistory(-1)) {
          e.preventDefault();
          return;
        }
      }
      if (noSelection && e.key === "ArrowDown") {
        var after = input.value.slice(input.selectionEnd);
        if (after.indexOf("\n") === -1 && navigateHistory(1)) {
          e.preventDefault();
          return;
        }
      }
    }
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      sendMessage();
    }
  }

  /* ===== Модалка настроек ===== */
  var allDropdowns = []; // все созданные дропдауны для единого обработчика клика
  var ddDocListenerAdded = false; // флаг: document click listener уже добавлен
  var setProviderDD = null;
  var setModelDD = null;
  var setVisionDD = null;
  var setSchemeDD = null;
  var setFontStyleDD = null;
  var setLanguageDD = null;
  var setPeriodDD = null;
  var perModelDirty = false; // флаг: per-model настройки изменены вручную
  var currentModelKey = null; // ключ "provider::model" текущей редактируемой модели
  var perModelDrafts = {}; // черновики per-model настроек: ключ -> {temperature, max_tokens, reasoning}
  var customEmptyMode = false; // флаг: у пользовательского провайдера нет моделей
  var currentSettingsTab = "models"; // активная вкладка настроек (для области сброса)
  var ctModelDirty = false; // флаг: настройки персональной модели изменены вручную

  function makeDropdown(containerId, options, selected, onSelect, placeholder, showSearch, renderItem) {
    var wrap = byId(containerId);
    wrap.className = "dd-wrap";
    wrap.innerHTML = "";
    // Удаляем предыдущий дропдаун с тем же контейнером (пересоздание при смене языка).
    for (var d = allDropdowns.length - 1; d >= 0; d--) {
      if (allDropdowns[d].containerId === containerId) {
        allDropdowns.splice(d, 1);
      }
    }
    var btn = el("button", "dd-btn");
    btn.type = "button";
    var btnLabel = el("span", "dd-btn-label", "");
    var caret = el("span", "dd-caret", "▾");
    btn.appendChild(btnLabel);
    btn.appendChild(caret);
    var popup = el("div", "dd-popup");
    popup.style.display = "none";
    // Поле поиска создаётся только при showSearch !== false.
    var search = null;
    if (showSearch !== false) {
      search = el("input", "dd-search");
      search.type = "text";
      search.placeholder = placeholder || t("common.search");
      popup.appendChild(search);
    }
    var list = el("div", "dd-list");
    popup.appendChild(list);
    wrap.appendChild(btn);
    wrap.appendChild(popup);

    var current = null;
    var opts = [];
    var open = false;

    function renderList() {
      var prevScroll = list.scrollTop;
      list.innerHTML = "";
      var q = search ? search.value.trim().toLowerCase() : "";
      var shown = 0;
      for (var i = 0; i < opts.length; i++) {
        var o = opts[i];
        var hay = ((o.label || "") + " " + (o.value || "")).toLowerCase();
        if (q && hay.indexOf(q) === -1) {
          continue;
        }
        var item = el("div", "dd-item" + (o.value === current ? " active" : ""));
        if (renderItem) {
          // Кастомный рендер строки списка (например, с кнопкой удаления).
          renderItem(item, o);
        } else {
          item.appendChild(el("span", "dd-item-label", o.label));
        }
        (function (val) {
          item.addEventListener("click", function () {
            setSelected(val);
            close();
            if (onSelect) {
              onSelect(val);
            }
          });
        })(o.value);
        list.appendChild(item);
        shown++;
      }
      if (shown === 0) {
        list.appendChild(el("div", "dd-empty", t("common.nothing")));
      }
      // Сохраняем позицию прокрутки при фоновом обновлении списка.
      list.scrollTop = prevScroll;
    }

    function openPopup() {
      open = true;
      popup.style.display = "flex";
      if (search) {
        search.value = "";
        search.focus();
      }
      renderList();
    }

    function close() {
      open = false;
      popup.style.display = "none";
    }

    function setSelected(value) {
      current = value;
      var found = null;
      for (var i = 0; i < opts.length; i++) {
        if (opts[i].value === value) {
          found = opts[i];
          break;
        }
      }
      btnLabel.textContent = found ? found.label : (value || "—");
      renderList();
    }

    function setOptions(newOpts) {
      opts = newOpts || [];
      if (current !== null) {
        var still = false;
        for (var i = 0; i < opts.length; i++) {
          if (opts[i].value === current) {
            still = true;
            break;
          }
        }
        if (!still) {
          current = null;
        }
      }
      if (current === null && opts.length > 0) {
        current = opts[0].value;
      }
      setSelected(current);
    }

    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (open) {
        close();
      } else {
        openPopup();
      }
    });
    if (search) {
      search.addEventListener("input", renderList);
    }
    // Регистрируем дропдаун в общем списке для единого обработчика клика.
    allDropdowns.push({ containerId: containerId, wrap: wrap, close: close });
    // Единый document click listener: закрывает все дропдауны, кроме кликнутого.
    if (!ddDocListenerAdded) {
      ddDocListenerAdded = true;
      document.addEventListener("click", function (e) {
        for (var d = 0; d < allDropdowns.length; d++) {
          if (!allDropdowns[d].wrap.contains(e.target)) {
            allDropdowns[d].close();
          }
        }
      });
    }

    setOptions(options);
    if (selected !== undefined && selected !== null) {
      setSelected(selected);
    }

    return {
      setOptions: setOptions,
      setSelected: setSelected,
      getSelected: function () {
        return current;
      }
    };
  }

  function initSettingsDropdowns() {
    setProviderDD = makeDropdown("setProviderDD", [], "", onProviderChange, t("dd.provider_search"));
    setModelDD = makeDropdown("setModelDD", [], "", onModelChange, t("dd.model_search"), undefined, function (item, o) {
      // Кастомный рендер: имя модели + глазик зрения + кнопка удаления.
      item.appendChild(el("span", "dd-item-label", o.label));
      var provider = setProviderDD.getSelected();
      var prov = providerById(provider);
      var model = prov ? modelById(provider, o.value) : null;
      var eye = visionEye(model);
      if (eye) {
        item.appendChild(eye);
      }
      if (prov && !prov.builtin && model && !model.builtin) {
        var rm = el("button", "dd-remove", "✕");
        rm.type = "button";
        rm.title = t("settings.delete_model_title");
        (function (pid, mid) {
          rm.addEventListener("click", function (e) {
            e.stopPropagation();
            post({ type: "delete_model", provider: pid, model_id: mid });
          });
        })(provider, o.value);
        item.appendChild(rm);
      }
    });
    setSchemeDD = makeDropdown("setSchemeDD", [
      { value: "openai", label: t("scheme.openai") },
      { value: "anthropic", label: t("scheme.anthropic") }
    ], "openai", null, t("dd.scheme_search"));
    setVisionDD = makeDropdown("setVisionDD", [
      { value: "true", label: t("settings.vision_yes") },
      { value: "false", label: t("settings.vision_no") },
      { value: "unknown", label: t("settings.vision_unknown") }
    ], "unknown", onVisionSelect, null, false);
    setFontStyleDD = makeDropdown("setFontStyleDD", [
      { value: "system", label: t("font.system") },
      { value: "mono", label: t("font.mono") },
      { value: "serif", label: t("font.serif") }
    ], "system", null, null, false);
    setPeriodDD = makeDropdown("setPeriodDD", [
      { value: "all", label: t("usage.period.all") },
      { value: "today", label: t("usage.period.today") },
      { value: "week", label: t("usage.period.week") },
      { value: "month", label: t("usage.period.month") }
    ], "all", function (val) {
      post({ type: "get_usage", period: val });
    }, t("dd.period_search"));
    setLanguageDD = makeDropdown("setLanguageDD", [
      { value: "en", label: t("lang.en") },
      { value: "ru", label: t("lang.ru") },
      { value: "sr", label: t("lang.sr") }
    ], "en", null, t("dd.language_search"), false);
  }

  /* ===== Вкладка «Персональные модели» ===== */
  var ctProviderDD = null;
  var ctModelDD = null;
  var ctVisionDD = null;
  var ctSchemeDD = null;
  var ctNewSchemeDD = null;
  var ctEmptyMode = false; // флаг: у выбранного персонального провайдера нет моделей
  var ctCreatingProvider = false; // флаг: открыта форма создания нового провайдера

  function customProviders() {
    return (state.providers || []).filter(function (p) {
      return !p.builtin;
    });
  }

  function initCustomTab() {
    ctNewSchemeDD = makeDropdown("ctNewSchemeDD", [
      { value: "openai", label: t("scheme.openai") },
      { value: "anthropic", label: t("scheme.anthropic") }
    ], "openai", null, t("dd.scheme_search"));
    ctSchemeDD = makeDropdown("ctSchemeDD", [
      { value: "openai", label: t("scheme.openai") },
      { value: "anthropic", label: t("scheme.anthropic") }
    ], "openai", null, t("dd.scheme_search"));
    ctVisionDD = makeDropdown("ctVisionDD", [
      { value: "true", label: t("settings.vision_yes") },
      { value: "false", label: t("settings.vision_no") },
      { value: "unknown", label: t("settings.vision_unknown") }
    ], "unknown", null, null, false);
    ctProviderDD = makeDropdown("ctProviderDD", [], "", onCtProviderChange, t("dd.provider_search"), undefined, function (item, o) {
      // Кастомный рендер: имя персонального провайдера + корзина удаления.
      item.appendChild(el("span", "dd-item-label", o.label));
      var rm = el("button", "dd-remove", "✕");
      rm.type = "button";
      rm.title = t("settings.delete_provider_title");
      (function (pid) {
        rm.addEventListener("click", function (e) {
          e.stopPropagation();
          post({ type: "delete_provider", id: pid });
        });
      })(o.value);
      item.appendChild(rm);
    });
    ctModelDD = makeDropdown("ctModelDD", [], "", onCtModelChange, t("dd.model_search"), undefined, function (item, o) {
      item.appendChild(el("span", "dd-item-label", o.label));
      var ctEye = visionEye(modelById(ctProviderDD.getSelected(), o.value));
      if (ctEye) {
        item.appendChild(ctEye);
      }
      var rm = el("button", "dd-remove", "✕");
      rm.type = "button";
      rm.title = t("settings.delete_model_title");
      (function (mid) {
        rm.addEventListener("click", function (e) {
          e.stopPropagation();
          post({ type: "delete_model", provider: ctProviderDD.getSelected(), model_id: mid });
        });
      })(o.value);
      item.appendChild(rm);
    });
  }

  function fillCustomTab() {
    var provs = customProviders();
    var hasAny = provs.length > 0;
    var creating = !hasAny || ctCreatingProvider;
    byId("ctEmptyBlock").style.display = creating ? "block" : "none";
    byId("ctMainBlock").style.display = creating ? "none" : "block";
    // Кнопка «Добавить провайдера» видна только при наличии провайдеров и
    // когда форма создания уже не открыта.
    byId("ctProviderActions").style.display = (hasAny && !creating) ? "flex" : "none";
    // «Отмена» в форме создания имеет смысл только если провайдеры уже есть.
    byId("ctNewCancel").style.display = hasAny ? "inline-block" : "none";
    if (creating) {
      return;
    }
    ctProviderDD.setOptions(provs.map(function (p) {
      return { value: p.id, label: p.name || p.id };
    }));
    // Приоритет — активный провайдер, если он персональный.
    var s = state.settings || {};
    var ids = provs.map(function (p) { return p.id; });
    ctProviderDD.setSelected(ids.indexOf(s.active_provider) >= 0 ? s.active_provider : ids[0]);
    onCtProviderChange();
  }

  /* Открывает форму создания нового персонального провайдера. */
  function ctOpenNewProvider() {
    ctCreatingProvider = true;
    byId("ctNewName").value = "";
    byId("ctNewBaseUrl").value = "";
    byId("ctNewModelId").value = "";
    byId("ctNewModelLabel").value = "";
    byId("ctNewApiKey").value = "";
    ctNewSchemeDD.setSelected("openai");
    fillCustomTab();
  }

  /* Закрывает форму создания провайдера и возвращает управление списку. */
  function ctCancelNewProvider() {
    ctCreatingProvider = false;
    if (customProviders().length > 0) {
      fillCustomTab();
    }
  }

  function onCtProviderChange() {
    var prov = providerById(ctProviderDD.getSelected());
    if (!prov) {
      return;
    }
    byId("ctBaseUrl").value = prov.base_url || "";
    ctSchemeDD.setSelected(prov.scheme || "openai");
    setKeyField("ctApiKey", !!prov.has_key);
    var models = prov.models || [];
    updateCtModelMode(models, true);
    ctModelDD.setOptions(models.map(function (m) {
      return { value: m.id, label: m.name || m.id };
    }));
    var s = state.settings || {};
    var matched = false;
    for (var i = 0; i < models.length; i++) {
      if (models[i].id === s.active_model) {
        matched = true;
        break;
      }
    }
    ctModelDD.setSelected(matched ? s.active_model : (models.length > 0 ? models[0].id : ""));
    onCtModelChange();
  }

  /* Переключение режима персонального провайдера:
     - нет моделей: форма добавления видна сразу, кнопка «Добавить» — сабмит;
     - есть модели: дропдаун и настройки модели, кнопка «Добавить модель» раскрывает форму. */
  function updateCtModelMode(models, force) {
    var hasModels = (models || []).length > 0;
    var prevEmpty = ctEmptyMode;
    ctEmptyMode = !hasModels;
    byId("ctModelBlock").style.display = hasModels ? "block" : "none";
    byId("ctModelSettings").style.display = hasModels ? "block" : "none";
    byId("ctActionsBlock").style.display = "block";
    byId("ctDeleteModelBtn").style.display = hasModels ? "inline-block" : "none";
    byId("ctAddModelBtn").style.display = hasModels ? "inline-block" : "none";
    var form = byId("ctAddForm");
    if (hasModels) {
      if (force || prevEmpty) {
        form.style.display = "none";
      }
    } else {
      form.style.display = "block";
    }
  }

  function onCtModelChange() {
    var prov = providerById(ctProviderDD.getSelected());
    var model = prov ? modelById(prov.id, ctModelDD.getSelected()) : null;
    if (!model) {
      ctModelDirty = false;
      return;
    }
    var gTemp = state.settings.temperature !== undefined ? state.settings.temperature : 0.7;
    var gMax = state.settings.max_tokens !== undefined ? state.settings.max_tokens : 4096;
    var gReas = !!state.settings.reasoning;
    var hasTemp = model.temperature !== null && model.temperature !== undefined;
    var hasMax = model.max_tokens !== null && model.max_tokens !== undefined;
    var hasReas = model.reasoning !== null && model.reasoning !== undefined;
    byId("ctTemperature").value = String(hasTemp ? model.temperature : gTemp);
    byId("ctTemperatureValue").textContent = String(hasTemp ? model.temperature : gTemp);
    byId("ctTemperatureBadge").style.display = hasTemp ? "none" : "inline-block";
    byId("ctMaxTokens").value = String(hasMax ? model.max_tokens : gMax);
    byId("ctMaxTokensBadge").style.display = hasMax ? "none" : "inline-block";
    byId("ctReasoning").checked = hasReas ? !!model.reasoning : gReas;
    byId("ctReasoningBadge").style.display = hasReas ? "none" : "inline-block";
    ctVisionDD.setSelected(modelVisionChoice(model));
    var ctVisionSource = byId("ctVisionSource");
    if (model.vision_source === "provider") {
      ctVisionSource.textContent = t("settings.vision_from_provider");
      ctVisionSource.style.display = "inline-block";
    } else if (model.vision_source === "manual") {
      ctVisionSource.textContent = t("settings.vision_manual");
      ctVisionSource.style.display = "inline-block";
    } else {
      ctVisionSource.style.display = "none";
    }
    byId("ctPriceIn").value = (model.price_in === null || model.price_in === undefined) ? "" : String(model.price_in);
    byId("ctPriceOut").value = (model.price_out === null || model.price_out === undefined) ? "" : String(model.price_out);
    var ctPriceSource = byId("ctPriceSource");
    if (model.price_source === "provider") {
      ctPriceSource.textContent = t("settings.price_from_provider");
      ctPriceSource.style.display = "inline-block";
    } else if (model.price_source === "manual") {
      ctPriceSource.textContent = t("settings.price_manual");
      ctPriceSource.style.display = "inline-block";
    } else {
      ctPriceSource.style.display = "none";
    }
    byId("ctModelName").value = model.name || "";
    byId("ctModelSystemName").value = model.id || "";
    ctModelDirty = false;
  }

  function submitCtNewProvider() {
    var name = byId("ctNewName").value.trim();
    if (!name) {
      showToast(t("settings.name_required"), "err");
      return;
    }
    var payload = {
      type: "add_provider",
      name: name,
      base_url: byId("ctNewBaseUrl").value.trim(),
      api_key: byId("ctNewApiKey").value.trim(),
      scheme: ctNewSchemeDD.getSelected()
    };
    var mid = byId("ctNewModelId").value.trim();
    if (mid) {
      payload.model_id = mid;
      payload.label = byId("ctNewModelLabel").value.trim();
    }
    post(payload);
    ctCreatingProvider = false;
    byId("ctNewName").value = "";
    byId("ctNewBaseUrl").value = "";
    byId("ctNewModelId").value = "";
    byId("ctNewModelLabel").value = "";
    byId("ctNewApiKey").value = "";
  }

  function submitCtAddModel() {
    var pid = ctProviderDD.getSelected();
    var mid = byId("ctAddSystemName").value.trim();
    if (!pid || !mid) {
      showToast(t("settings.name_required"), "err");
      return;
    }
    post({ type: "add_model", provider: pid, model_id: mid, label: byId("ctAddLabel").value.trim() });
    byId("ctAddSystemName").value = "";
    byId("ctAddLabel").value = "";
    byId("ctAddForm").style.display = "none";
  }

  function resetCtModelField(field) {
    var pid = ctProviderDD.getSelected();
    var mid = ctModelDD.getSelected();
    if (!pid || !mid) {
      return;
    }
    var payload = { type: "update_model", provider: pid, model_id: mid };
    payload[field] = null;
    post(payload);
    if (field === "temperature") {
      var gTemp = state.settings.temperature !== undefined ? state.settings.temperature : 0.7;
      byId("ctTemperature").value = String(gTemp);
      byId("ctTemperatureValue").textContent = String(gTemp);
      byId("ctTemperatureBadge").style.display = "inline-block";
    } else if (field === "max_tokens") {
      var gMax = state.settings.max_tokens !== undefined ? state.settings.max_tokens : 4096;
      byId("ctMaxTokens").value = String(gMax);
      byId("ctMaxTokensBadge").style.display = "inline-block";
    } else if (field === "reasoning") {
      byId("ctReasoning").checked = !!state.settings.reasoning;
      byId("ctReasoningBadge").style.display = "inline-block";
    }
    ctModelDirty = false;
  }

  function saveCustomTab() {
    var pid = ctProviderDD ? ctProviderDD.getSelected() : "";
    if (!pid) {
      return;
    }
    var providerPayload = {
      type: "update_provider",
      id: pid,
      base_url: byId("ctBaseUrl").value,
      scheme: ctSchemeDD.getSelected()
    };
    // Пустое поле означает «оставить сохранённый ключ без изменений».
    var ctKey = byId("ctApiKey").value.trim();
    if (ctKey) {
      providerPayload.api_key = ctKey;
    }
    post(providerPayload);
    var mid = ctModelDD ? ctModelDD.getSelected() : "";
    if (!mid) {
      return;
    }
    var payload = {
      type: "update_model",
      provider: pid,
      model_id: mid,
      name: byId("ctModelName").value
    };
    if (ctModelDirty) {
      payload.temperature = parseFloat(byId("ctTemperature").value);
      payload.max_tokens = parseInt(byId("ctMaxTokens").value, 10) || 4096;
      payload.reasoning = byId("ctReasoning").checked;
    }
    if (ctVisionDD.getSelected() !== modelVisionChoice(modelById(pid, mid))) {
      payload.vision = visionPayload(ctVisionDD.getSelected());
    }
    var ctPriceIn = parsePriceField("ctPriceIn");
    var ctPriceOut = parsePriceField("ctPriceOut");
    var ctModel = modelById(pid, mid);
    if (ctModel && (ctPriceIn !== ctModel.price_in || ctPriceOut !== ctModel.price_out)) {
      payload.price_in = ctPriceIn;
      payload.price_out = ctPriceOut;
    }
    post(payload);
    ctModelDirty = false;
  }

  function onProviderChange() {
    var provider = providerById(setProviderDD.getSelected());
    if (!provider) {
      return;
    }
    // Ключ теперь per-provider: берём из выбранного провайдера.
    setKeyField("setApiKey", !!provider.has_key);
    var customWrap = byId("customUrlWrap");
    if (provider.builtin) {
      customWrap.style.display = "none";
    } else {
      customWrap.style.display = "block";
      byId("setBaseUrl").value = provider.base_url || "";
      setSchemeDD.setSelected(provider.scheme || "openai");
    }
    var models = provider.models || [];
    // Режим пользовательского провайдера (Custom): добавление/удаление моделей.
    // force=true: при смене провайдера принудительно закрываем форму добавления.
    updateCustomMode(provider, models, true);
    // Список моделей дополняем подгруженными по API (без дублей).
    setModelDD.setOptions(settingsModelOptions(provider));
    requestApiModels(provider.id, false);
    var s = state.settings || {};
    var matched = false;
    for (var i = 0; i < models.length; i++) {
      if (models[i].id === s.active_model) {
        matched = true;
        break;
      }
    }
    setModelDD.setSelected(matched ? s.active_model : (models.length > 0 ? models[0].id : ""));
    onModelChange();
  }

  /* Переключение режима добавления моделей на вкладке «Модели»:
     - есть модели: дропдаун + настройки, кнопка «Добавить модель» раскрывает форму;
     - нет моделей: форма добавления видна сразу.
     У встроенных провайдеров поля URL/ключа/схемы скрыты — модель добавляется только по id. */
  function updateCustomMode(provider, models, force) {
    var modelField = byId("setModelDD").closest(".field");
    var actionsBlock = byId("modelActionsBlock");
    var addForm = byId("addModelForm");
    var addBtn = byId("addModelBtn");
    var delBtn = byId("deleteModelBtn");
    var hr = byId("modelActionsHr");
    if (!provider) {
      customEmptyMode = false;
      modelField.style.display = "block";
      actionsBlock.style.display = "none";
      addForm.style.display = "none";
      return;
    }
    var hasModels = (models || []).length > 0;
    var prevEmpty = customEmptyMode;
    customEmptyMode = !hasModels;
    modelField.style.display = hasModels ? "block" : "none";
    actionsBlock.style.display = "block";
    delBtn.style.display = hasModels ? "inline-block" : "none";
    addBtn.style.display = "inline-block";
    addBtn.textContent = t("settings.add_model");
    if (hr) {
      hr.style.display = "block";
    }
    // URL, ключ и схема задаются только у провайдера — у модели их нет.
    byId("amSubmit").style.display = "inline-block";
    byId("amCancel").style.display = "inline-block";
    if (hasModels) {
      // Форма скрыта, раскрывается кнопкой «Добавить модель».
      if (force || prevEmpty) {
        addForm.style.display = "none";
      }
    } else {
      // Нет моделей: форма видна сразу.
      addForm.style.display = "block";
    }
  }

  /* Отправка формы добавления модели (общая для режимов «нет моделей» и «есть модели»). */
  function submitAddModel() {
    var payload = {
      type: "add_model",
      provider: setProviderDD.getSelected(),
      model_id: byId("amSystemName").value.trim(),
      label: byId("amLabel").value.trim()
    };
    post(payload);
    byId("addModelForm").style.display = "none";
    byId("amSystemName").value = "";
    byId("amLabel").value = "";
  }

  function onVisionSelect() {
    // Пользователь изменил зрение вручную — помечаем модель как изменённую.
    perModelDirty = true;
    var badge = byId("setVisionSource");
    badge.textContent = t("settings.vision_manual");
    badge.style.display = "inline-block";
  }

  function parsePriceField(id) {
    var raw = byId(id).value.trim();
    if (!raw) {
      return null;
    }
    var value = parseFloat(raw);
    if (isNaN(value) || value < 0) {
      return null;
    }
    return value;
  }

  function onPriceEdit() {
    // Цена правится вручную — помечаем модель как изменённую.
    perModelDirty = true;
    var badge = byId("setPriceSource");
    badge.textContent = t("settings.price_manual");
    badge.style.display = "inline-block";
  }

  function onCtPriceEdit() {
    ctModelDirty = true;
    var badge = byId("ctPriceSource");
    badge.textContent = t("settings.price_manual");
    badge.style.display = "inline-block";
  }

  function onModelChange() {
    // Сохраняем черновик предыдущей модели, если форма была изменена.
    if (currentModelKey && perModelDirty) {
      perModelDrafts[currentModelKey] = {
        temperature: parseFloat(byId("setTemperature").value),
        max_tokens: parseInt(byId("setMaxTokens").value, 10) || 4096,
        reasoning: byId("setReasoning").checked,
        vision: setVisionDD.getSelected(),
        price_in: parsePriceField("setPriceIn"),
        price_out: parsePriceField("setPriceOut")
      };
    }
    var provider = setProviderDD.getSelected();
    var model = modelById(provider, setModelDD.getSelected());
    if (!model) {
      // Возможно, выбрана модель из подгруженного списка: добавляем её в конфиг,
      // чтобы появились поля настройки (повторно не отправляем до обновления данных).
      var selectedId = setModelDD.getSelected();
      var importKey = provider + "::" + selectedId;
      if (apiModelById(provider, selectedId) && !apiModelsImporting[importKey]) {
        apiModelsImporting[importKey] = true;
        post({ type: "import_api_model", provider: provider, model_id: selectedId });
      }
      currentModelKey = null;
      byId("modelSettingsBlock").style.display = "none";
      return;
    }
    // Модель уже в конфиге — снимаем блокировку повторного импорта.
    delete apiModelsImporting[provider + "::" + model.id];
    byId("modelSettingsBlock").style.display = "block";
    var key = provider + "::" + model.id;
    currentModelKey = key;
    var draft = perModelDrafts[key];
    var gTemp = state.settings.temperature !== undefined ? state.settings.temperature : 0.7;
    var gMax = state.settings.max_tokens !== undefined ? state.settings.max_tokens : 4096;
    var gReas = !!state.settings.reasoning;
    var hasTemp = model.temperature !== null && model.temperature !== undefined;
    var hasMax = model.max_tokens !== null && model.max_tokens !== undefined;
    var hasReas = model.reasoning !== null && model.reasoning !== undefined;
    var temp = draft && draft.temperature !== null && draft.temperature !== undefined
      ? draft.temperature : (hasTemp ? model.temperature : gTemp);
    var maxT = draft && draft.max_tokens !== null && draft.max_tokens !== undefined
      ? draft.max_tokens : (hasMax ? model.max_tokens : gMax);
    var reas = draft && draft.reasoning !== null && draft.reasoning !== undefined
      ? draft.reasoning : (hasReas ? !!model.reasoning : gReas);
    byId("setTemperature").value = String(temp);
    byId("setTemperatureValue").textContent = String(temp);
    byId("setTemperatureBadge").style.display = (draft || hasTemp) ? "none" : "inline-block";
    byId("setMaxTokens").value = String(maxT);
    byId("setMaxTokensBadge").style.display = (draft || hasMax) ? "none" : "inline-block";
    byId("setReasoning").checked = !!reas;
    byId("setReasoningBadge").style.display = (draft || hasReas) ? "none" : "inline-block";
    // Зрение модели: true/false/неизвестно + источник значения.
    var visionValue = draft && draft.vision !== undefined
      ? draft.vision : modelVisionChoice(model);
    setVisionDD.setSelected(visionValue);
    var visionSource = byId("setVisionSource");
    if (model.vision_source === "provider") {
      visionSource.textContent = t("settings.vision_from_provider");
      visionSource.style.display = "inline-block";
    } else if (model.vision_source === "manual") {
      visionSource.textContent = t("settings.vision_manual");
      visionSource.style.display = "inline-block";
    } else {
      visionSource.style.display = "none";
    }
    // Цена модели за 1 млн токенов: из подгруженного списка или задана вручную.
    var priceIn = draft ? draft.price_in : model.price_in;
    var priceOut = draft ? draft.price_out : model.price_out;
    byId("setPriceIn").value = (priceIn === null || priceIn === undefined) ? "" : String(priceIn);
    byId("setPriceOut").value = (priceOut === null || priceOut === undefined) ? "" : String(priceOut);
    var priceSource = byId("setPriceSource");
    if (model.price_source === "provider") {
      priceSource.textContent = t("settings.price_from_provider");
      priceSource.style.display = "inline-block";
    } else if (model.price_source === "manual") {
      priceSource.textContent = t("settings.price_manual");
      priceSource.style.display = "inline-block";
    } else {
      priceSource.style.display = "none";
    }
    // Дополнительные поля пользовательской модели (URL/ключ/название/схема).
    var prov = providerById(provider);
    var customFields = byId("customModelFields");
    if (prov && !prov.builtin) {
      customFields.style.display = "block";
      byId("setModelName").value = model.name || "";
      byId("setModelSystemName").value = model.id || "";
    } else {
      customFields.style.display = "none";
    }
    perModelDirty = false;
  }

  function fillSettingsForm() {
    var s = state.settings || {};
    // На вкладке «Модели» — только встроенные провайдеры (персональные живут на своей вкладке).
    var builtin = (state.providers || []).filter(function (p) {
      return p.builtin;
    });
    setProviderDD.setOptions(builtin.map(function (p) {
      return { value: p.id, label: p.name || p.id };
    }));
    var hasActive = builtin.some(function (p) { return p.id === s.active_provider; });
    setProviderDD.setSelected(hasActive ? s.active_provider : (builtin[0] ? builtin[0].id : ""));
    onProviderChange();
    byId("setNotes").value = s.notes || "";
    byId("setGlobalTemperature").value = String(s.temperature !== undefined ? s.temperature : 0.7);
    byId("setGlobalTemperatureValue").textContent = byId("setGlobalTemperature").value;
    byId("setGlobalMaxTokens").value = String(s.max_tokens !== undefined ? s.max_tokens : 4096);
    byId("setGlobalReasoning").checked = !!s.reasoning;
    byId("setCompactEnabled").checked = s.compact_enabled !== false;
    byId("setCompactThreshold").value = String(s.compact_threshold !== undefined ? s.compact_threshold : 80);
    byId("setContextWindow").value = String(s.context_window !== undefined ? s.context_window : 128000);
    updateThemeSwitch();
    setFontStyleDD.setSelected(s.font_style || "system");
    setLanguageDD.setSelected(s.language || "en");
    byId("setFontSize").value = String(s.font_size || 14);
    byId("setFontSizeValue").textContent = String(s.font_size || 14);
    fillCustomTab();
  }

  function openSettings() {
    perModelDrafts = {};
    perModelDirty = false;
    currentModelKey = null;
    ctModelDirty = false;
    // Пересоздаём дропдауны: лейблы и плейсхолдеры должны быть на текущем языке.
    initSettingsDropdowns();
    initCustomTab();
    fillSettingsForm();
    switchSettingsTab(currentSettingsTab);
    byId("settingsModal").style.display = "flex";
    focusModal(byId("settingsModal"));
  }

  function closeSettings() {
    hideHelpTip();
    byId("settingsModal").style.display = "none";
  }

  function switchSettingsTab(tab) {
    currentSettingsTab = tab;
    var tabs = ["models", "custom", "general", "appearance"];
    for (var i = 0; i < tabs.length; i++) {
      var pane = byId("tab" + tabs[i].charAt(0).toUpperCase() + tabs[i].slice(1));
      if (pane) {
        pane.style.display = (tabs[i] === tab) ? "block" : "none";
      }
    }
    var btns = document.querySelectorAll(".settings-tab");
    for (var j = 0; j < btns.length; j++) {
      btns[j].classList.toggle("active", btns[j].getAttribute("data-tab") === tab);
    }
    // У вкладок «Модели» и «Персональные» нет общей кнопки сброса.
    var resetBtn = byId("resetSettingsBtn");
    if (resetBtn) {
      resetBtn.style.display = (tab === "models" || tab === "custom") ? "none" : "inline-block";
    }
  }

  function openUsage() {
    setPeriodDD.setSelected("all");
    byId("usageModal").style.display = "flex";
    focusModal(byId("usageModal"));
    post({ type: "get_usage", period: "all" });
  }

  function closeUsage() {
    byId("usageModal").style.display = "none";
  }

  // Порядок модалок от самой верхней к нижней: нужен для Esc и ловушки фокуса.
  var MODAL_IDS = ["modelPickerModal", "copyModal", "usageModal", "settingsModal"];

  function visibleModal() {
    for (var i = 0; i < MODAL_IDS.length; i++) {
      var modal = byId(MODAL_IDS[i]);
      if (modal && modal.style.display !== "none") {
        return modal;
      }
    }
    return null;
  }

  // Удерживает Tab внутри открытой модалки: фокус не уходит на фон.
  function trapModalFocus(e) {
    var modal = visibleModal();
    if (!modal) {
      return;
    }
    var nodes = modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    var list = [];
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      if (node.disabled) {
        continue;
      }
      if (node.offsetWidth === 0 && node.offsetHeight === 0 && node !== document.activeElement) {
        continue;
      }
      list.push(node);
    }
    if (!list.length) {
      return;
    }
    var first = list[0];
    var last = list[list.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  // Переводит фокус на первый элемент управления модалки при открытии.
  function focusModal(modal) {
    if (!modal) {
      return;
    }
    var node = modal.querySelector(
      'input, select, textarea, button, [tabindex]:not([tabindex="-1"])'
    );
    if (node) {
      node.focus();
    }
  }

  function resetPerModelField(field) {
    var provider = setProviderDD.getSelected();
    var model = setModelDD.getSelected();
    var payload = { type: "update_model", provider: provider, model_id: model };
    payload[field] = null;
    post(payload);
    // Черновик: поле сбрасывается к глобальному значению.
    if (currentModelKey) {
      if (!perModelDrafts[currentModelKey]) {
        perModelDrafts[currentModelKey] = {};
      }
      perModelDrafts[currentModelKey][field] = null;
    }
    // Показываем глобальное значение и бейдж «общий».
    if (field === "temperature") {
      var gTemp = state.settings.temperature !== undefined ? state.settings.temperature : 0.7;
      byId("setTemperature").value = String(gTemp);
      byId("setTemperatureValue").textContent = String(gTemp);
      byId("setTemperatureBadge").style.display = "inline-block";
    } else if (field === "max_tokens") {
      var gMax = state.settings.max_tokens !== undefined ? state.settings.max_tokens : 4096;
      byId("setMaxTokens").value = String(gMax);
      byId("setMaxTokensBadge").style.display = "inline-block";
    } else if (field === "reasoning") {
      byId("setReasoning").checked = !!state.settings.reasoning;
      byId("setReasoningBadge").style.display = "inline-block";
    }
    perModelDirty = false;
  }

  function saveSettings() {
    var themeBtn = document.querySelector(".theme-switch button.active");
    // Активного провайдера/модель берём с той вкладки, где сейчас пользователь.
    var activeProvider = setProviderDD.getSelected();
    var activeModel = setModelDD.getSelected();
    if (currentSettingsTab === "custom" && ctProviderDD && ctProviderDD.getSelected()) {
      activeProvider = ctProviderDD.getSelected();
      activeModel = ctModelDD.getSelected();
    }
    var settings = {
      active_provider: activeProvider,
      active_model: activeModel,
      notes: byId("setNotes").value,
      temperature: parseFloat(byId("setGlobalTemperature").value),
      max_tokens: parseInt(byId("setGlobalMaxTokens").value, 10) || 4096,
      reasoning: byId("setGlobalReasoning").checked,
      compact_enabled: byId("setCompactEnabled").checked,
      compact_threshold: parseInt(byId("setCompactThreshold").value, 10) || 80,
      context_window: parseInt(byId("setContextWindow").value, 10) || 128000,
      theme: themeBtn ? themeBtn.getAttribute("data-theme") : "auto",
      font_size: parseInt(byId("setFontSize").value, 10) || 14,
      font_style: setFontStyleDD.getSelected(),
      language: setLanguageDD.getSelected()
    };
    // Пустое поле означает «оставить сохранённый ключ без изменений».
    var newKey = byId("setApiKey").value.trim();
    if (newKey) {
      settings.api_key = newKey;
    }
    post({ type: "save_settings", settings: settings });
    // Сохраняем черновики всех изменённых моделей.
    var keys = Object.keys(perModelDrafts);
    for (var i = 0; i < keys.length; i++) {
      var key = keys[i];
      var sep = key.indexOf("::");
      if (sep <= 0) {
        continue;
      }
      var pid = key.substring(0, sep);
      var mid = key.substring(sep + 2);
      var draft = perModelDrafts[key];
      var modelPayload = {
        type: "update_model",
        provider: pid,
        model_id: mid,
        temperature: draft.temperature !== undefined ? draft.temperature : null,
        max_tokens: draft.max_tokens !== undefined ? draft.max_tokens : null,
        reasoning: draft.reasoning !== undefined ? draft.reasoning : null
      };
      var drafted = modelById(pid, mid);
      if (draft.vision !== undefined && draft.vision !== modelVisionChoice(drafted)) {
        modelPayload.vision = visionPayload(draft.vision);
      }
      if (drafted && (draft.price_in !== drafted.price_in || draft.price_out !== drafted.price_out)) {
        modelPayload.price_in = draft.price_in;
        modelPayload.price_out = draft.price_out;
      }
      post(modelPayload);
    }
    // Текущая модель, если изменена вручную.
    var provider = setProviderDD.getSelected();
    if (perModelDirty && provider) {
      var currentModel = modelById(provider, setModelDD.getSelected());
      var currentPayload = {
        type: "update_model",
        provider: provider,
        model_id: setModelDD.getSelected(),
        temperature: parseFloat(byId("setTemperature").value),
        max_tokens: parseInt(byId("setMaxTokens").value, 10) || 4096,
        reasoning: byId("setReasoning").checked
      };
      if (setVisionDD.getSelected() !== modelVisionChoice(currentModel)) {
        currentPayload.vision = visionPayload(setVisionDD.getSelected());
      }
      if (currentModel) {
        var curPriceIn = parsePriceField("setPriceIn");
        var curPriceOut = parsePriceField("setPriceOut");
        if (curPriceIn !== currentModel.price_in || curPriceOut !== currentModel.price_out) {
          currentPayload.price_in = curPriceIn;
          currentPayload.price_out = curPriceOut;
        }
      }
      post(currentPayload);
    }
    var prov = providerById(provider);
    if (prov && !prov.builtin) {
      post({
        type: "update_provider",
        id: prov.id,
        base_url: byId("setBaseUrl").value,
        scheme: setSchemeDD.getSelected()
      });
      // Дополнительные поля пользовательской модели.
      var modelId = setModelDD.getSelected();
      if (modelId) {
        post({
          type: "update_model",
          provider: prov.id,
          model_id: modelId,
          name: byId("setModelName").value
        });
      }
    }
    saveCustomTab();
    perModelDrafts = {};
    perModelDirty = false;
    currentModelKey = null;
    closeSettings();
  }

  /* ===== Экспорт чата ===== */
  // Имена вложений сообщения без тяжёлых данных (data URI не экспортируем).
  function exportAttachments(msg) {
    var result = [];
    if (msg.image) {
      result.push({ kind: "image", name: t("attach.photo_name") });
    }
    if (msg.file && msg.file.name) {
      result.push({ kind: "text", name: msg.file.name });
    }
    var list = msg.attachments || [];
    for (var i = 0; i < list.length; i++) {
      var att = list[i];
      if (!att || typeof att !== "object") {
        continue;
      }
      if (att.image || att.kind === "image") {
        result.push({ kind: "image", name: att.name || t("attach.photo_name") });
      } else if (att.file && att.file.name) {
        result.push({ kind: "text", name: att.file.name });
      } else if (att.kind === "text") {
        result.push({ kind: "text", name: att.name || "" });
      }
    }
    return result;
  }

  function exportRoleLabel(role) {
    if (role === "user") {
      return t("export.user");
    }
    if (role === "assistant") {
      return "FlowSlice AI";
    }
    return t("export.system");
  }

  function buildExport(chat, fmt) {
    var msgs = chat.msgs || [];
    var title = chat.title || t("common.new_chat");
    if (fmt === "json") {
      var payload = {
        app: "FlowSlice AI",
        title: title,
        exported_at: new Date().toISOString(),
        messages: []
      };
      for (var j = 0; j < msgs.length; j++) {
        var jm = msgs[j];
        var item = {
          role: jm.role,
          text: jm.text || "",
          ts: jm.ts || null,
          attachments: exportAttachments(jm)
        };
        if (jm.reasoning) {
          item.reasoning = jm.reasoning;
        }
        payload.messages.push(item);
      }
      return JSON.stringify(payload, null, 2);
    }
    var lines = [];
    if (fmt === "md") {
      lines.push("# " + title);
      lines.push("");
      for (var k = 0; k < msgs.length; k++) {
        var km = msgs[k];
        lines.push("## " + exportRoleLabel(km.role));
        lines.push("");
        var atts = exportAttachments(km);
        if (atts.length) {
          lines.push("_" + atts.map(function (a) { return a.name; }).join(", ") + "_");
          lines.push("");
        }
        lines.push(km.text || "");
        lines.push("");
      }
      return lines.join("\n");
    }
    // Обычный текст
    lines.push(t("export.title") + ": " + title);
    for (var n = 0; n < msgs.length; n++) {
      lines.push(exportRoleLabel(msgs[n].role) + ": " + (msgs[n].text || ""));
    }
    return lines.join("\n\n");
  }

  function exportChat(fmt) {
    var chat = getActiveChat();
    if (!chat) {
      showToast(t("common.no_active_chat"), "err");
      return;
    }
    var text;
    try {
      text = buildExport(chat, fmt || "md");
    } catch (err) {
      // Экспорт не должен падать молча: сообщаем и пишем в лог.
      console.error("Ошибка экспорта чата:", err);
      showToast(t("export.failed"), "err");
      return;
    }
    copyText(text);
  }

  function closeExportMenu() {
    var menu = byId("exportMenu");
    if (menu) {
      menu.style.display = "none";
    }
  }

  function toggleExportMenu() {
    var menu = byId("exportMenu");
    if (!menu) {
      return;
    }
    menu.style.display = menu.style.display === "none" ? "flex" : "none";
  }

  function renderUsage(msg) {
    byId("setUsage").textContent = t("usage.text", { msgs: msg.msgs || 0, tokens: msg.tokens || 0 });
  }

  /* ===== Toast ===== */
  function showToast(text, kind) {
    var toast = el("div", "toast" + (kind ? " toast-" + kind : ""), text);
    document.body.appendChild(toast);
    setTimeout(function () {
      toast.classList.add("toast-hide");
    }, 2500);
    setTimeout(function () {
      toast.remove();
    }, 2800);
  }

  /* ===== Обработка входящих сообщений Py→JS ===== */
  function handleDelta(msg) {
    if (msg.chat_id && msg.chat_id !== state.active) {
      return;
    }
    if (!streamTextEl) {
      // Стриминг начался без полного state — создаём сообщение на лету
      var chat = getActiveChat();
      if (!chat) {
        return;
      }
      chat.msgs = chat.msgs || [];
      chat.msgs.push({ id: "stream", role: "assistant", text: "", ts: Date.now() });
      var node = renderMessage(chat.msgs[chat.msgs.length - 1], chat.msgs.length - 1, chat.msgs);
      node.classList.add("msg-streaming");
      byId("messages").appendChild(node);
      streamTextEl = node.querySelector(".msg-text");
    }
    streamText += msg.text || "";
    setMessageText(streamTextEl, streamText, true);
    scrollToBottom(false);
  }

  // Стриминг размышлений reasoning-моделей.
  function handleThoughtDelta(msg) {
    if (msg.chat_id && msg.chat_id !== state.active) {
      return;
    }
    streamThought += msg.text || "";
    if (!streamThoughtEl) {
      var wrap = streamTextEl ? streamTextEl.closest(".msg-wrap") : null;
      if (!wrap) {
        return;
      }
      var bubble = wrap.querySelector(".msg-bubble");
      var textNode = wrap.querySelector(".msg-text");
      if (!bubble || !textNode) {
        return;
      }
      var det = buildReasoning("", true);
      bubble.insertBefore(det, textNode);
      streamThoughtEl = det.querySelector(".msg-reasoning-text");
    }
    streamThoughtEl.textContent = streamThought;
    scrollToBottom(false);
  }

  function handleReply(msg) {
    if (msg.chat_id && msg.chat_id !== state.active) {
      return;
    }
    if (streamTextEl) {
      setMessageText(streamTextEl, msg.text || "", true);
      var node = streamTextEl.closest(".msg-wrap");
      if (node) {
        node.classList.remove("msg-streaming");
        if (!msg.ok) {
          node.classList.add("msg-error");
        }
        if (msg.reasoning) {
          if (!streamThoughtEl) {
            var bubble = node.querySelector(".msg-bubble");
            var textNode = node.querySelector(".msg-text");
            if (bubble && textNode) {
              var det = buildReasoning("", false);
              bubble.insertBefore(det, textNode);
              streamThoughtEl = det.querySelector(".msg-reasoning-text");
            }
          }
          if (streamThoughtEl) {
            streamThoughtEl.textContent = msg.reasoning;
          }
        }
      }
      streamTextEl = null;
      streamText = "";
      streamThoughtEl = null;
      streamThought = "";
    } else {
      // Ответ без стриминга — добавляем сообщение целиком
      var chat = getActiveChat();
      if (!chat) {
        return;
      }
      chat.msgs = chat.msgs || [];
      chat.msgs.push({
        id: "r" + Date.now(),
        role: "assistant",
        text: msg.text || "",
        reasoning: msg.reasoning || "",
        ts: Date.now(),
        error: !msg.ok
      });
      renderMessages();
    }
    state.status = "idle";
    updateTyping();
    scrollToBottom(false);
  }

  // Кэш медиа сообщений. Сервер в общем снимке состояния не передаёт
  // тяжёлые data URI изображений, поэтому UI запоминает их из полных снимков
  // (загрузка, переключение чата, старт генерации) и восстанавливает по id.
  var messageMediaCache = {};

  function rememberMessageMedia(chats) {
    (chats || []).forEach(function (chat) {
      if (!chat || !Array.isArray(chat.msgs)) {
        return;
      }
      chat.msgs.forEach(function (msg) {
        if (!msg || !msg.id) {
          return;
        }
        var hasImage = !!msg.image;
        if (!hasImage && Array.isArray(msg.attachments)) {
          hasImage = msg.attachments.some(function (att) {
            return att && att.image;
          });
        }
        if (hasImage) {
          messageMediaCache[msg.id] = {
            image: msg.image || null,
            attachments: Array.isArray(msg.attachments) ? msg.attachments : null
          };
        }
      });
    });
  }

  function pruneMessageMedia(chats) {
    var alive = {};
    (chats || []).forEach(function (chat) {
      if (!chat || !Array.isArray(chat.msgs)) {
        return;
      }
      chat.msgs.forEach(function (msg) {
        if (msg && msg.id) {
          alive[msg.id] = true;
        }
      });
    });
    Object.keys(messageMediaCache).forEach(function (id) {
      if (!alive[id]) {
        delete messageMediaCache[id];
      }
    });
  }

  function restoreMessageMedia(chats) {
    (chats || []).forEach(function (chat) {
      if (!chat || !Array.isArray(chat.msgs)) {
        return;
      }
      chat.msgs.forEach(function (msg) {
        if (!msg || !msg.id) {
          return;
        }
        var cached = messageMediaCache[msg.id];
        if (!cached) {
          return;
        }
        if (!msg.image && cached.image) {
          msg.image = cached.image;
        }
        if ((!Array.isArray(msg.attachments) || !msg.attachments.length) && cached.attachments) {
          msg.attachments = cached.attachments;
        }
      });
    });
    pruneMessageMedia(chats);
  }

  function onMessage(msg) {
    if (!msg || typeof msg !== "object") {
      return;
    }
    switch (msg.type) {
      case "state":
        rememberMessageMedia(state.chats);
        var prevActiveState = state.active;
        state.chats = msg.chats || [];
        restoreMessageMedia(state.chats);
        state.active = msg.active || null;
        // При переключении чата показываем его конец.
        if (state.active !== prevActiveState) {
          userScrolledUp = false;
          pendingForceScroll = true;
        }
        state.settings = msg.settings || {};
        state.providers = msg.providers || [];
        state.commands = msg.commands || [];
        state.context_flags = msg.context_flags || {};
        state.context_modes = msg.context_modes || {};
        state.context_tokens = msg.context_tokens || 0;
        state.status = msg.status || "idle";
        if (state.status !== "streaming") {
          streamText = "";
          streamThought = "";
          streamThoughtEl = null;
        }
        renderState();
        // Обновляем открытые модалки без сброса несохранённых правок.
        if (byId("settingsModal").style.display !== "none") {
          refreshSettingsModels();
        }
        if (byId("modelPickerModal").style.display !== "none") {
          renderModelPicker();
        }
        break;
      case "delta":
        handleDelta(msg);
        break;
      case "thought_delta":
        handleThoughtDelta(msg);
        break;
      case "reply":
        handleReply(msg);
        break;
      case "status":
        state.status = msg.text || "idle";
        if (state.status !== "streaming") {
          streamText = "";
          streamTextEl = null;
          streamThought = "";
          streamThoughtEl = null;
        }
        updateTyping();
        break;
      case "toast":
        showToast(msg.text || "", msg.kind || "");
        break;
      case "chats":
        state.chats = msg.chats || [];
        state.active = msg.active || null;
        renderSidebar();
        break;
      case "settings":
        state.settings = msg.settings || {};
        applyTheme(state.settings);
        applyFont(state.settings);
        // Пересоздаём дропдауны и форму: язык мог измениться в настройках.
        initSettingsDropdowns();
        initCustomTab();
        fillSettingsForm();
        applyI18n();
        renderHeader();
        // Перерисовываем динамический контент чата на новом языке.
        renderSidebar();
        renderContext();
        renderMessages();
        break;
      case "key_test":
        showToast(msg.text || (msg.ok ? t("key.valid") : t("key.invalid")), msg.ok ? "ok" : "err");
        break;
      case "models_loading":
        if (!state.apiModels[msg.provider]) {
          state.apiModels[msg.provider] = { models: [], error: "" };
        }
        state.apiModels[msg.provider].loading = true;
        if (byId("modelPickerModal").style.display !== "none") {
          renderModelPicker();
        }
        break;
      case "api_models":
        state.apiModels[msg.provider] = {
          models: msg.models || [],
          error: msg.error || "",
          loading: false
        };
        // Ошибку показываем только когда показать нечего: иначе работает кэш.
        if (msg.error && (msg.models || []).length === 0) {
          showToast(msg.error, "err");
        }
        if (byId("modelPickerModal").style.display !== "none") {
          renderModelPicker();
        }
        if (byId("settingsModal").style.display !== "none") {
          refreshSettingsModels();
        }
        break;
      case "usage":
        renderUsage(msg);
        break;
    }
  }

  function refreshSettingsModels() {
    var provider = providerById(setProviderDD.getSelected());
    if (!provider) {
      return;
    }
    var models = provider.models || [];
    var current = setModelDD.getSelected();
    setModelDD.setOptions(settingsModelOptions(provider));
    var still = false;
    var merged = mergedModels(provider);
    for (var i = 0; i < merged.length; i++) {
      if (merged[i].id === current) {
        still = true;
        break;
      }
    }
    setModelDD.setSelected(still ? current : (models.length > 0 ? models[0].id : ""));
    // Признак «ключ задан» мог измениться (например, после сброса моделей).
    setKeyField("setApiKey", !!provider.has_key);
    onModelChange();
    // Обновляем режим добавления моделей (переход «нет моделей» ↔ «есть модели»).
    updateCustomMode(provider, models, false);
    // Обновляем вкладку персональных провайдеров.
    fillCustomTab();
  }

  /* ===== Инициализация ===== */
  function init() {
    byId("sendBtn").addEventListener("click", sendMessage);
    byId("stopBtn").addEventListener("click", function () {
      post({ type: "stop" });
    });
    byId("attachBtn").addEventListener("click", function () {
      pickFiles();
    });
    byId("fileInput").addEventListener("change", function () {
      handleFiles(this.files);
      this.value = "";
    });
    // Вставка изображения из буфера и перетаскивание файлов в чат.
    document.addEventListener("paste", handlePaste);
    setupDragDrop();
    byId("input").addEventListener("keydown", onInputKey);
    byId("input").addEventListener("input", function () {
      // Ручной ввод завершает навигацию по истории.
      historyIndex = -1;
      historyDraft = null;
      autoResize();
      updateCmdSuggest();
      updateRequestTokens();
    });
    byId("input").addEventListener("blur", function () {
      // Небольшая задержка, чтобы клик по элементу списка успел сработать
      setTimeout(closeCmdSuggest, 150);
    });
    byId("newChatBtn").addEventListener("click", function () {
      post({ type: "new_chat" });
    });
    byId("settingsBtn").addEventListener("click", openSettings);
    byId("usageBtn").addEventListener("click", openUsage);
    byId("usageModalClose").addEventListener("click", closeUsage);
    byId("usageModalOk").addEventListener("click", closeUsage);
    byId("usageModal").addEventListener("click", function (e) {
      if (e.target === this) {
        closeUsage();
      }
    });
    var tabBtns = document.querySelectorAll(".settings-tab");
    for (var tb = 0; tb < tabBtns.length; tb++) {
      (function (btn) {
        btn.addEventListener("click", function () {
          switchSettingsTab(btn.getAttribute("data-tab"));
        });
      })(tabBtns[tb]);
    }
    // Горизонтальный переключатель темы.
    var themeBtns = document.querySelectorAll(".theme-switch button");
    for (var tb2 = 0; tb2 < themeBtns.length; tb2++) {
      (function (btn) {
        btn.addEventListener("click", function () {
          state.settings.theme = btn.getAttribute("data-theme");
          applyTheme(state.settings);
          updateThemeSwitch();
        });
      })(themeBtns[tb2]);
    }
    byId("modalClose").addEventListener("click", closeSettings);
    byId("settingsModal").addEventListener("click", function (e) {
      if (e.target === this) {
        closeSettings();
      }
    });
    byId("saveSettingsBtn").addEventListener("click", saveSettings);
    byId("resetSettingsBtn").addEventListener("click", function () {
      post({ type: "reset_settings", scope: currentSettingsTab });
    });
    byId("resetModelsBtn").addEventListener("click", function () {
      post({ type: "reset_models" });
    });
    byId("resetCustomModelsBtn").addEventListener("click", function () {
      post({ type: "reset_custom_models" });
    });
    byId("testKeyBtn").addEventListener("click", function () {
      post({ type: "test_key", key: byId("setApiKey").value, provider: setProviderDD.getSelected() });
    });
    byId("setApiKeyEye").addEventListener("click", function () {
      var keyInput = byId("setApiKey");
      var masked = keyInput.type === "password";
      keyInput.type = masked ? "text" : "password";
      this.textContent = masked ? "🙈" : "👁";
      this.title = masked ? t("common.hide_key") : t("common.show_key");
    });
    byId("setTemperature").addEventListener("input", function () {
      byId("setTemperatureValue").textContent = this.value;
      perModelDirty = true;
      byId("setTemperatureBadge").style.display = "none";
    });
    byId("setMaxTokens").addEventListener("input", function () {
      perModelDirty = true;
      byId("setMaxTokensBadge").style.display = "none";
    });
    byId("setReasoning").addEventListener("change", function () {
      perModelDirty = true;
      byId("setReasoningBadge").style.display = "none";
    });
    byId("setPriceIn").addEventListener("input", onPriceEdit);
    byId("setPriceOut").addEventListener("input", onPriceEdit);
    byId("resetTemperature").addEventListener("click", function () {
      resetPerModelField("temperature");
    });
    byId("resetMaxTokens").addEventListener("click", function () {
      resetPerModelField("max_tokens");
    });
    byId("resetReasoning").addEventListener("click", function () {
      resetPerModelField("reasoning");
    });
    byId("setGlobalTemperature").addEventListener("input", function () {
      byId("setGlobalTemperatureValue").textContent = this.value;
    });
    byId("setFontSize").addEventListener("input", function () {
      byId("setFontSizeValue").textContent = this.value;
    });
    byId("exportBtn").addEventListener("click", function (e) {
      e.stopPropagation();
      toggleExportMenu();
    });
    var exportOptions = document.querySelectorAll(".export-opt");
    for (var eo = 0; eo < exportOptions.length; eo++) {
      exportOptions[eo].addEventListener("click", function () {
        closeExportMenu();
        exportChat(this.getAttribute("data-fmt"));
      });
    }
    document.addEventListener("click", function (e) {
      var wrap = document.querySelector(".composer-export");
      if (wrap && !wrap.contains(e.target)) {
        closeExportMenu();
      }
    });
    byId("addModelBtn").addEventListener("click", function () {
      byId("amSubmit").style.display = "inline-block";
      byId("amCancel").style.display = "inline-block";
      byId("addModelForm").style.display = "block";
    });
    byId("amCancel").addEventListener("click", function () {
      byId("addModelForm").style.display = "none";
    });
    byId("amSubmit").addEventListener("click", submitAddModel);
    byId("deleteModelBtn").addEventListener("click", function () {
      var provider = setProviderDD.getSelected();
      var model = setModelDD.getSelected();
      if (!provider || !model) {
        return;
      }
      post({ type: "delete_model", provider: provider, model_id: model });
    });
    /* ===== Слушатели вкладки «Персональные модели» ===== */
    byId("ctNewApiKeyEye").addEventListener("click", function () {
      var keyInput = byId("ctNewApiKey");
      var masked = keyInput.type === "password";
      keyInput.type = masked ? "text" : "password";
      this.textContent = masked ? "🙈" : "👁";
      this.title = masked ? t("common.hide_key") : t("common.show_key");
    });
    byId("ctApiKeyEye").addEventListener("click", function () {
      var keyInput = byId("ctApiKey");
      var masked = keyInput.type === "password";
      keyInput.type = masked ? "text" : "password";
      this.textContent = masked ? "🙈" : "👁";
      this.title = masked ? t("common.hide_key") : t("common.show_key");
    });
    byId("ctNewSubmit").addEventListener("click", submitCtNewProvider);
    byId("ctNewCancel").addEventListener("click", ctCancelNewProvider);
    byId("ctAddProviderBtn").addEventListener("click", ctOpenNewProvider);
    byId("ctAddModelBtn").addEventListener("click", function () {
      // Кнопка работает как переключатель: раскрывает или скрывает форму.
      var form = byId("ctAddForm");
      form.style.display = form.style.display === "block" ? "none" : "block";
    });
    byId("ctAddSubmit").addEventListener("click", submitCtAddModel);
    byId("ctDeleteModelBtn").addEventListener("click", function () {
      var pid = ctProviderDD.getSelected();
      var mid = ctModelDD.getSelected();
      if (!pid || !mid) {
        return;
      }
      post({ type: "delete_model", provider: pid, model_id: mid });
    });
    byId("ctTemperature").addEventListener("input", function () {
      byId("ctTemperatureValue").textContent = this.value;
      ctModelDirty = true;
      byId("ctTemperatureBadge").style.display = "none";
    });
    byId("ctMaxTokens").addEventListener("input", function () {
      ctModelDirty = true;
      byId("ctMaxTokensBadge").style.display = "none";
    });
    byId("ctReasoning").addEventListener("change", function () {
      ctModelDirty = true;
      byId("ctReasoningBadge").style.display = "none";
    });
    byId("ctPriceIn").addEventListener("input", onCtPriceEdit);
    byId("ctPriceOut").addEventListener("input", onCtPriceEdit);
    byId("ctTemperatureReset").addEventListener("click", function () {
      resetCtModelField("temperature");
    });
    byId("ctMaxTokensReset").addEventListener("click", function () {
      resetCtModelField("max_tokens");
    });
    byId("ctReasoningReset").addEventListener("click", function () {
      resetCtModelField("reasoning");
    });
    byId("searchInput").addEventListener("input", renderSidebar);
    byId("clearChatsBtn").addEventListener("click", function () {
      if (window.confirm(t("sidebar.clear_all_confirm"))) {
        post({ type: "clear_chats" });
      }
    });
    byId("messages").addEventListener("scroll", onMessagesScroll);
    byId("scrollBottom").addEventListener("click", function () {
      scrollToBottom(true);
    });
    byId("messages").addEventListener("click", function (e) {
      var btn = e.target && e.target.closest ? e.target.closest(".md-copy") : null;
      if (!btn || !btn.parentNode) {
        return;
      }
      var code = btn.parentNode.querySelector("code");
      if (code) {
        copyText(code.textContent);
      }
    });
    byId("copyModalClose").addEventListener("click", closeCopyModal);
    byId("copyModalOk").addEventListener("click", closeCopyModal);
    byId("copyModal").addEventListener("click", function (e) {
      if (e.target === this) {
        closeCopyModal();
      }
    });
    byId("modelChip").addEventListener("click", openModelPicker);
    byId("mpClose").addEventListener("click", closeModelPicker);
    byId("mpRefresh").addEventListener("click", refreshModelPicker);
    byId("setModelsRefresh").addEventListener("click", function () {
      var pid = setProviderDD.getSelected();
      if (pid) {
        requestApiModels(pid, true);
      }
    });
    byId("modelPickerModal").addEventListener("click", function (e) {
      if (e.target === this) {
        closeModelPicker();
      }
    });
    byId("mpSearch").addEventListener("input", renderModelPicker);
    /* ===== Горячие клавиши ===== */
    document.addEventListener("keydown", function (e) {
      var ctrl = e.ctrlKey || e.metaKey;
      if (e.key === "Escape") {
        if (byId("modelPickerModal").style.display !== "none") {
          closeModelPicker();
          return;
        }
        if (byId("copyModal").style.display === "flex") {
          closeCopyModal();
          return;
        }
        if (byId("usageModal").style.display === "flex") {
          closeUsage();
          return;
        }
        if (byId("settingsModal").style.display === "flex") {
          closeSettings();
          return;
        }
        if (byId("exportMenu").style.display === "flex") {
          closeExportMenu();
          return;
        }
        if (cmdSuggestOpen()) {
          closeCmdSuggest();
        }
        return;
      }
      if (e.key === "Tab") {
        trapModalFocus(e);
        return;
      }
      if (ctrl && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        var search = byId("searchInput");
        search.focus();
        search.select();
        return;
      }
      if (ctrl && e.key === "Enter") {
        e.preventDefault();
        sendMessage();
        return;
      }
      if (ctrl && e.shiftKey && (e.key === "n" || e.key === "N")) {
        e.preventDefault();
        post({ type: "new_chat" });
      }
    });

    /* ===== Глобальный перехват JS-ошибок ===== */
    window.addEventListener("error", function (event) {
      var detail = event && event.message ? event.message : String(event);
      console.error("JS error:", event && event.error ? event.error : detail);
      showToast(t("js.error") + ": " + detail, "err");
    });
    window.addEventListener("unhandledrejection", function (event) {
      var reason = event ? event.reason : null;
      var detail = reason && reason.message ? reason.message : String(reason);
      console.error("Unhandled rejection:", reason);
      showToast(t("js.error") + ": " + detail, "err");
    });

    if (window.orca && typeof window.orca.onMessage === "function") {
      window.orca.onMessage(onMessage);
    }
    initHelpTooltips();
    initSettingsDropdowns();
    post({ type: "get_state" });
  }

  // Чистые функции, доступные юнит-тестам node (tests/js/pure.test.js).
  window.FlowSlicePure = {
    escapeHtml: escapeHtml,
    safeHref: safeHref,
    formatTokens: formatTokens,
    formatCost: formatCost,
    formatPrice: formatPrice,
    codeBlockHtml: codeBlockHtml,
    renderMarkdown: renderMarkdown,
  };

  document.addEventListener("DOMContentLoaded", init);
})();
