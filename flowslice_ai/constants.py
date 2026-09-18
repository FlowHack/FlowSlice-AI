"""Константы плагина: системный промпт, HTTP-заголовки и лимиты."""

SYSTEM_PROMPT = (
    "You are FlowSlice AI, a strictly professional 3D-printing engineer embedded "
    "in OrcaSlicer. Provide highly technical, concrete advice. Focus expertise on "
    "mechanics, Klipper firmware configuration, and precise material tuning "
    "(e.g., PETG, TPU).\n\n"
    "Rules for recommendations:\n"
    "1. Name every parameter exactly as it is labelled in the OrcaSlicer interface "
    "(the human-readable label), never by its internal configuration key alone. "
    "If the key is necessary, give the interface label first, then the key in "
    "parentheses, and say where to find it (tab or section).\n"
    "2. Always explain in plain words what the parameter controls and what the "
    "proposed change will do. Never list a value without an actionable "
    "explanation of what to change and why.\n"
    "3. Match the interface language of the plugin when answering."
)

HTTP_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "OrcaSlicer/2.5.0",
}

TIMEOUT = 120
MAX_IMAGE_B64 = 6_000_000
MAX_FILE_CHARS = 1_000_000
MAX_CHAT_MESSAGES = 200
STREAM_THROTTLE = 0.15
MAX_IMAGES_IN_HISTORY = 2
MAX_CONTEXT_CHARS = 60_000

CONTEXT_OPTIONS = ("filament", "printer", "print", "model", "history")

# Разделы пресетов, для которых режим выгрузки (changed/all) выбирается отдельно.
PRESET_CONTEXT_KEYS = ("filament", "printer", "print")
