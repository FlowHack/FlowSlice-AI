(function () {
  "use strict";

  /* ===== Константы ===== */
  var CONTEXT_KEYS = ["filament", "printer", "print", "model", "history"];
  // Клиентские лимиты вложений (синхронизированы с лимитами бэкенда).
  var MAX_ATTACHMENTS = 4;
  var MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024;
  // Разделы пресетов с выбором режима выгрузки (изменённые/все) в панели чата.
  var CONTEXT_MODE_KEYS = ["filament", "printer", "print"];
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
    context_tokens: 0,
    status: "idle"
  };

  /* ===== Локализация (i18n) ===== */
  var I18N = {
    en: {
      "common.close": "Close",
      "common.search": "Search",
      "common.nothing": "No results",
      "common.copied": "Copied!",
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
      "attach.limit_count": "Attachment limit reached (max {n}).",
      "attach.limit_size": "File \"{name}\" is too large.",
      "common.stop": "Stop",
      "common.send": "Send",
      "common.choose_model": "Choose model",
      "common.new_chat": "New chat",
      "common.settings": "Settings",
      "common.stats": "Statistics",
      "common.no_active_chat": "No active chat",
      "sidebar.chats": "Chats",
      "sidebar.search": "Search chats...",
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
      "ctx.model_help": "Adds the loaded model data to the context: dimensions, volume, triangle count",
      "ctx.history_help": "Adds the current chat's message history to the context",
      "ctx.tokens": "Context tokens: {n}",
      "ctx.mode_changed": "changed",
      "ctx.mode_all": "all",
      "ctx.mode_title": "Preset export: only changed parameters or the full profile",
      "ctx.mode_help": "Dropdown on the right:\nchanged — only parameters changed from the base preset\nall — the full profile",
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
      "settings.help_url": "API server address of the provider",
      "settings.help_model_name": "Model name in the provider system (id)",
      "settings.help_model_alias": "Friendly model name shown in the UI",
      "settings.help_api_key": "Provider API access key",
      "settings.help_scheme": "API request format: OpenAI-compatible or native Anthropic",
      "settings.help_temperature": "Response randomness: lower is more precise, higher is more creative",
      "settings.help_max_tokens": "Maximum response length in tokens",
      "settings.help_reasoning": "Enable extended model reasoning before answering",
      "settings.help_notes": "Additional info the agent takes into account when answering",
      "settings.help_language": "Plugin UI language",
      "settings.help_preset_context": "What goes into the slicer context: only changed preset parameters or all of them",
      "settings.font_size": "Font size:",
      "settings.font_style": "Font style",
      "settings.language": "Language",
      "settings.theme": "Theme",
      "settings.export": "Export chat",
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
      "export.chat": "Export chat"
    },
    ru: {
      "common.close": "Закрыть",
      "common.search": "Поиск",
      "common.nothing": "Ничего не найдено",
      "common.copied": "Скопировано",
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
      "attach.limit_count": "Достигнут предел вложений (не более {n}).",
      "attach.limit_size": "Файл «{name}» слишком большой.",
      "common.stop": "Остановить генерацию",
      "common.send": "Отправить",
      "common.choose_model": "Выбрать модель",
      "common.new_chat": "Новый чат",
      "common.settings": "Настройки",
      "common.stats": "Статистика",
      "common.no_active_chat": "Нет активного чата",
      "sidebar.chats": "Чаты",
      "sidebar.search": "Поиск чатов…",
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
      "ctx.model_help": "Добавляет в контекст данные загруженной модели: размеры, объём, количество треугольников",
      "ctx.history_help": "Добавляет в контекст историю сообщений текущего чата",
      "ctx.tokens": "Токенов контекста: {n}",
      "ctx.mode_changed": "изм.",
      "ctx.mode_all": "все",
      "ctx.mode_title": "Выгрузка пресета: только изменённые параметры или полный профиль",
      "ctx.mode_help": "Дропдаун справа:\nизм. — только изменённые относительно базового пресета параметры\nвсе — полный профиль",
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
      "settings.help_url": "Адрес API-сервера провайдера",
      "settings.help_model_name": "Название модели в системе провайдера (id)",
      "settings.help_model_alias": "Удобное имя модели для отображения в интерфейсе",
      "settings.help_api_key": "Ключ доступа к API провайдера",
      "settings.help_scheme": "Формат запросов к API: OpenAI-совместимый или нативный Anthropic",
      "settings.help_temperature": "Случайность ответов: ниже — точнее, выше — креативнее",
      "settings.help_max_tokens": "Максимальная длина ответа в токенах",
      "settings.help_reasoning": "Включить расширенное мышление модели перед ответом",
      "settings.help_notes": "Дополнительная информация, которую агент учитывает при ответах",
      "settings.help_language": "Язык интерфейса плагина",
      "settings.help_preset_context": "Что попадает в контекст слайсера: только изменённые параметры пресетов или все",
      "settings.font_size": "Размер шрифта:",
      "settings.font_style": "Стиль шрифта",
      "settings.language": "Язык",
      "settings.theme": "Тема",
      "settings.export": "Экспорт чата",
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
      "export.chat": "Экспорт чата"
    },
    sr: {
      "common.close": "Zatvori",
      "common.search": "Pretraga",
      "common.nothing": "Ništa nije pronađeno",
      "common.copied": "Kopirano!",
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
      "attach.limit_count": "Dostignut limit priloga (najviše {n}).",
      "attach.limit_size": "Datoteka \"{name}\" je prevelika.",
      "common.stop": "Zaustavi",
      "common.send": "Pošalji",
      "common.choose_model": "Izaberi model",
      "common.new_chat": "Novi razgovor",
      "common.settings": "Podešavanja",
      "common.stats": "Statistika",
      "common.no_active_chat": "Nema aktivnog razgovora",
      "sidebar.chats": "Razgovori",
      "sidebar.search": "Pretraga razgovora…",
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
      "ctx.model_help": "Dodaje u kontekst podatke učitanog modela: dimenzije, zapreminu, broj trouglova",
      "ctx.history_help": "Dodaje u kontekst istoriju poruka trenutnog razgovora",
      "ctx.tokens": "Tokeni konteksta: {n}",
      "ctx.mode_changed": "izm.",
      "ctx.mode_all": "sve",
      "ctx.mode_title": "Izvoz profila: samo izmenjeni parametri ili pun profil",
      "ctx.mode_help": "Padajuća lista desno:\nizm. — samo parametri izmenjeni u odnosu na bazni profil\nsve — pun profil",
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
      "settings.help_url": "Adresa API servera provajdera",
      "settings.help_model_name": "Naziv modela u sistemu provajdera (id)",
      "settings.help_model_alias": "Prikazano ime modela u interfejsu",
      "settings.help_api_key": "Ključ za pristup API provajdera",
      "settings.help_scheme": "Format zahteva ka API: OpenAI-kompatibilan ili nativni Anthropic",
      "settings.help_temperature": "Nasumičnost odgovora: niže — preciznije, više — kreativnije",
      "settings.help_max_tokens": "Maksimalna dužina odgovora u tokenima",
      "settings.help_reasoning": "Uključi produženo razmišljanje modela pre odgovora",
      "settings.help_notes": "Dodatne informacije koje agent uzima u obzir pri odgovaranju",
      "settings.help_language": "Jezik interfejsa dodatka",
      "settings.help_preset_context": "Šta ulazi u kontekst slajsera: samo izmenjeni parametri preseta ili svi",
      "settings.font_size": "Veličina fonta:",
      "settings.font_style": "Stil fonta",
      "settings.language": "Jezik",
      "settings.theme": "Tema",
      "settings.export": "Izvezi razgovor",
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
      "export.chat": "Izvezi razgovor"
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
  var userScrolledUp = false; // пользователь прокрутил историю вверх

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
    var s = state.settings || {};
    var provider = providerById(s.active_provider);
    // Нет ключа — конкретная модель неактуальна, показываем нейтральный текст.
    if (!provider || !provider.has_key) {
      byId("modelChipLabel").textContent = t("mp.no_model");
      return;
    }
    var providerName = provider ? provider.name : (s.active_provider || "—");
    var modelName = s.active_model || "—";
    if (provider) {
      var models = provider.models || [];
      for (var i = 0; i < models.length; i++) {
        if (models[i].id === s.active_model) {
          modelName = models[i].name || models[i].id;
          break;
        }
      }
    }
    byId("modelChipLabel").textContent = providerName + " · " + modelName;
  }

  function openModelPicker() {
    byId("mpSearch").value = "";
    renderModelPicker();
    byId("modelPickerModal").style.display = "flex";
    byId("mpSearch").focus();
  }

  function closeModelPicker() {
    byId("modelPickerModal").style.display = "none";
  }

  function renderModelPicker() {
    var list = byId("mpList");
    list.innerHTML = "";
    var query = byId("mpSearch").value.trim().toLowerCase();
    var providers = state.providers || [];
    var withModels = [];
    for (var i = 0; i < providers.length; i++) {
      var provModels = providers[i].models || [];
      // Показываем только провайдеров с непустым API-ключом и хотя бы одной моделью.
      var hasKey = !!providers[i].has_key;
      if (provModels.length > 0 && hasKey) {
        withModels.push(providers[i]);
      }
    }
    var s = state.settings || {};
    var activeProvider = s.active_provider;
    var activeModel = s.active_model;
    var single = withModels.length <= 1;
    var shown = 0;
    for (var p = 0; p < withModels.length; p++) {
      var prov = withModels[p];
      var provName = prov.name || prov.id;
      var provMatch = query && provName.toLowerCase().indexOf(query) !== -1;
      var models = (prov.models || []).slice().sort(function (a, b) {
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
        var isActive = prov.id === activeProvider && item.id === activeModel;
        var isDefault = (prov.id + "::" + item.id) === (s.default_model || "");
        var row = el("div", "mp-item" + (isActive ? " active" : ""));
        row.setAttribute("data-provider", prov.id);
        row.setAttribute("data-model", item.id);
        row.appendChild(el("span", "mp-item-name", item.name || item.id));
        row.appendChild(el("code", "mp-item-id", item.id));
        var star = el("button", "mp-star" + (isDefault ? " active" : ""), isDefault ? "★" : "☆");
        star.type = "button";
        star.title = t("mp.default_set");
        (function (pid, mid) {
          star.addEventListener("click", function (e) {
            e.stopPropagation();
            post({ type: "set_default_model", provider: pid, model: mid });
          });
        })(prov.id, item.id);
        row.appendChild(star);
        if (isActive) {
          row.appendChild(el("span", "mp-check", "✓"));
        }
        (function (pid, mid) {
          row.addEventListener("click", function () {
            post({ type: "set_model", provider: pid, model: mid });
            closeModelPicker();
          });
        })(prov.id, item.id);
        list.appendChild(row);
        shown++;
      }
    }
    if (shown === 0) {
      // Различаем «ключ не задан» и «ничего не нашлось по поиску».
      var hasAnyKey = false;
      for (var q = 0; q < providers.length; q++) {
        if (providers[q].has_key && (providers[q].models || []).length > 0) {
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
    return item;
  }

  function renderSidebar() {
    var list = byId("chatList");
    list.innerHTML = "";
    var query = byId("searchInput").value.trim().toLowerCase();
    var chats = state.chats || [];
    if (query) {
      // Режим поиска: плоский список совпадений
      var filtered = [];
      for (var i = 0; i < chats.length; i++) {
        if ((chats[i].title || "").toLowerCase().indexOf(query) !== -1) {
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
    bubble.appendChild(el("div", "msg-text", msg.text || ""));
    bubble.appendChild(el("div", "msg-time", formatTime(msg.ts)));
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
      streamTextEl.textContent = streamText;
    }
    if (state.status === "streaming" && streamThoughtEl) {
      streamThoughtEl.textContent = streamThought;
    }
    scrollToBottom(true);
  }

  function scrollToBottom(force) {
    var container = byId("messages");
    if (force || !userScrolledUp) {
      container.scrollTop = container.scrollHeight;
    }
  }

  function onMessagesScroll() {
    var container = byId("messages");
    var nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    userScrolledUp = !nearBottom;
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
      // а для пресетов — ещё и смысл режимов «изм.»/«все».
      var helpText = t("ctx." + key + "_help");
      if (CONTEXT_MODE_KEYS.indexOf(key) >= 0) {
        helpText += "\n\n" + t("ctx.mode_help");
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
      if (CONTEXT_MODE_KEYS.indexOf(key) >= 0) {
        // Режим пресета: штатный дропдаун проекта (без поиска).
        var modeWrap = el("span", "ctx-mode-dd");
        var modeHost = el("span");
        modeHost.id = "ctxMode_" + key;
        modeWrap.appendChild(modeHost);
        item.appendChild(modeWrap);
        modeDDs[key] = makeDropdown(
          modeHost.id,
          [
            { value: "changed", label: t("ctx.mode_changed") },
            { value: "all", label: t("ctx.mode_all") }
          ],
          modes[key] === "all" ? "all" : "changed",
          collect,
          null,
          false
        );
        // Подсказка на самой выпадайке: выбор «изм.»/«все».
        var modeBtn = modeWrap.querySelector(".dd-btn");
        if (modeBtn) {
          modeBtn.setAttribute("data-tooltip", t("ctx.mode_title"));
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
        imgReader.onload = function (e) {
          var img = new Image();
          img.onload = function () {
            var maxSide = 1024;
            var scale = Math.min(1, maxSide / Math.max(img.width, img.height));
            var w = Math.round(img.width * scale);
            var h = Math.round(img.height * scale);
            var canvas = document.createElement("canvas");
            canvas.width = w;
            canvas.height = h;
            var ctx = canvas.getContext("2d");
            ctx.drawImage(img, 0, 0, w, h);
            attachments.push({
              kind: "image",
              name: name,
              data: canvas.toDataURL("image/jpeg", 0.85)
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
          attachments.push({
            kind: "text",
            name: name,
            data: String(e.target.result)
          });
          renderAttachments();
        };
        textReader.readAsText(file);
      }
    });
  }

  /* ===== Отправка сообщения ===== */
  function sendMessage() {
    var input = byId("input");
    var text = input.value.trim();
    if (!text && attachments.length === 0) {
      return;
    }
    for (var i = 0; i < attachments.length; i++) {
      post({
        type: "attach_file",
        kind: attachments[i].kind,
        name: attachments[i].name,
        data: attachments[i].data
      });
    }
    attachments = [];
    renderAttachments();
    var editId = pendingEditId;
    pendingEditId = null;
    var payload = { type: "chat", text: text };
    if (editId) {
      payload.edit_id = editId;
    }
    post(payload);
    input.value = "";
    autoResize();
    input.focus();
  }

  function startEdit(msg) {
    pendingEditId = msg.id;
    byId("input").value = msg.text || "";
    autoResize();
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
  var setSchemeDD = null;
  var setFontStyleDD = null;
  var setLanguageDD = null;
  var setPeriodDD = null;
  var amSchemeDD = null;
  var setModelSchemeDD = null;
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
        if (o.value === current) {
          item.appendChild(el("span", "dd-check", "✓"));
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
      // Кастомный рендер: имя модели + кнопка удаления для пользовательских моделей.
      item.appendChild(el("span", "dd-item-label", o.label));
      var provider = setProviderDD.getSelected();
      var prov = providerById(provider);
      var model = prov ? modelById(provider, o.value) : null;
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
    amSchemeDD = makeDropdown("amSchemeDD", [
      { value: "openai", label: t("scheme.openai") },
      { value: "anthropic", label: t("scheme.anthropic") }
    ], "openai", null, t("dd.scheme_search"));
    setModelSchemeDD = makeDropdown("setModelSchemeDD", [
      { value: "openai", label: t("scheme.openai") },
      { value: "anthropic", label: t("scheme.anthropic") }
    ], "openai", null, t("dd.scheme_search"));
    setLanguageDD = makeDropdown("setLanguageDD", [
      { value: "en", label: t("lang.en") },
      { value: "ru", label: t("lang.ru") },
      { value: "sr", label: t("lang.sr") }
    ], "en", null, t("dd.language_search"), false);
  }

  /* ===== Вкладка «Персональные модели» ===== */
  var ctProviderDD = null;
  var ctModelDD = null;
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
    setModelDD.setOptions(models.map(function (m) {
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
    // Поля URL/ключа/схемы доступны только персональным провайдерам.
    byId("amCustomFields").style.display = provider.builtin ? "none" : "block";
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
    var provider = setProviderDD.getSelected();
    var prov = providerById(provider);
    var payload = {
      type: "add_model",
      provider: provider,
      model_id: byId("amSystemName").value.trim(),
      label: byId("amLabel").value.trim()
    };
    if (prov && !prov.builtin) {
      payload.base_url = byId("amBaseUrl").value.trim();
      payload.api_key = byId("amApiKey").value.trim();
      payload.scheme = amSchemeDD.getSelected();
    }
    post(payload);
    byId("addModelForm").style.display = "none";
    byId("amSystemName").value = "";
    byId("amLabel").value = "";
    byId("amBaseUrl").value = "";
    byId("amApiKey").value = "";
  }

  function onModelChange() {
    // Сохраняем черновик предыдущей модели, если форма была изменена.
    if (currentModelKey && perModelDirty) {
      perModelDrafts[currentModelKey] = {
        temperature: parseFloat(byId("setTemperature").value),
        max_tokens: parseInt(byId("setMaxTokens").value, 10) || 4096,
        reasoning: byId("setReasoning").checked
      };
    }
    var provider = setProviderDD.getSelected();
    var model = modelById(provider, setModelDD.getSelected());
    if (!model) {
      currentModelKey = null;
      byId("modelSettingsBlock").style.display = "none";
      return;
    }
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
    // Дополнительные поля пользовательской модели (URL/ключ/название/схема).
    var prov = providerById(provider);
    var customFields = byId("customModelFields");
    if (prov && !prov.builtin) {
      customFields.style.display = "block";
      byId("setModelName").value = model.name || "";
      byId("setModelSystemName").value = model.id || "";
      byId("setModelBaseUrl").value = model.base_url || "";
      setKeyField("setModelApiKey", !!model.has_key);
      setModelSchemeDD.setSelected(model.scheme || prov.scheme || "openai");
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
    post({ type: "get_usage", period: "all" });
  }

  function closeUsage() {
    byId("usageModal").style.display = "none";
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
      post({
        type: "update_model",
        provider: pid,
        model_id: mid,
        temperature: draft.temperature !== undefined ? draft.temperature : null,
        max_tokens: draft.max_tokens !== undefined ? draft.max_tokens : null,
        reasoning: draft.reasoning !== undefined ? draft.reasoning : null
      });
    }
    // Текущая модель, если изменена вручную.
    var provider = setProviderDD.getSelected();
    if (perModelDirty && provider) {
      post({
        type: "update_model",
        provider: provider,
        model_id: setModelDD.getSelected(),
        temperature: parseFloat(byId("setTemperature").value),
        max_tokens: parseInt(byId("setMaxTokens").value, 10) || 4096,
        reasoning: byId("setReasoning").checked
      });
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
        var modelPayload = {
          type: "update_model",
          provider: prov.id,
          model_id: modelId,
          name: byId("setModelName").value,
          base_url: byId("setModelBaseUrl").value,
          scheme: setModelSchemeDD.getSelected()
        };
        var modelKey = byId("setModelApiKey").value.trim();
        if (modelKey) {
          modelPayload.api_key = modelKey;
        }
        post(modelPayload);
      }
    }
    saveCustomTab();
    perModelDrafts = {};
    perModelDirty = false;
    currentModelKey = null;
    closeSettings();
  }

  function exportChat() {
    var chat = getActiveChat();
    if (!chat) {
      showToast(t("common.no_active_chat"), "err");
      return;
    }
    var lines = [chat.title || t("common.new_chat")];
    var msgs = chat.msgs || [];
    for (var i = 0; i < msgs.length; i++) {
      var m = msgs[i];
      if (m.role === "user") {
        lines.push(t("export.user") + ": " + (m.text || ""));
      } else if (m.role === "assistant") {
        lines.push("FlowSlice AI: " + (m.text || ""));
      }
    }
    copyText(lines.join("\n\n"));
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
    streamTextEl.textContent = streamText;
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
      streamTextEl.textContent = msg.text || "";
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

  function onMessage(msg) {
    if (!msg || typeof msg !== "object") {
      return;
    }
    switch (msg.type) {
      case "state":
        state.chats = msg.chats || [];
        state.active = msg.active || null;
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
    setModelDD.setOptions(models.map(function (m) {
      return { value: m.id, label: m.name || m.id };
    }));
    var still = false;
    for (var i = 0; i < models.length; i++) {
      if (models[i].id === current) {
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
      byId("fileInput").click();
    });
    byId("fileInput").addEventListener("change", function () {
      handleFiles(this.files);
      this.value = "";
    });
    byId("input").addEventListener("keydown", onInputKey);
    byId("input").addEventListener("input", function () {
      autoResize();
      updateCmdSuggest();
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
      post({ type: "test_key", key: byId("setApiKey").value });
    });
    byId("setApiKeyEye").addEventListener("click", function () {
      var keyInput = byId("setApiKey");
      var masked = keyInput.type === "password";
      keyInput.type = masked ? "text" : "password";
      this.textContent = masked ? "🙈" : "👁";
      this.title = masked ? t("common.hide_key") : t("common.show_key");
    });
    byId("setModelApiKeyEye").addEventListener("click", function () {
      var keyInput = byId("setModelApiKey");
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
    byId("exportBtn").addEventListener("click", exportChat);
    byId("addModelBtn").addEventListener("click", function () {
      var provider = providerById(setProviderDD.getSelected());
      byId("amCustomFields").style.display = (provider && !provider.builtin) ? "block" : "none";
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
    byId("copyModalClose").addEventListener("click", closeCopyModal);
    byId("copyModalOk").addEventListener("click", closeCopyModal);
    byId("copyModal").addEventListener("click", function (e) {
      if (e.target === this) {
        closeCopyModal();
      }
    });
    byId("modelChip").addEventListener("click", openModelPicker);
    byId("mpClose").addEventListener("click", closeModelPicker);
    byId("modelPickerModal").addEventListener("click", function (e) {
      if (e.target === this) {
        closeModelPicker();
      }
    });
    byId("mpSearch").addEventListener("input", renderModelPicker);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && byId("modelPickerModal").style.display !== "none") {
        closeModelPicker();
      }
    });

    if (window.orca && typeof window.orca.onMessage === "function") {
      window.orca.onMessage(onMessage);
    }
    initHelpTooltips();
    initSettingsDropdowns();
    post({ type: "get_state" });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
