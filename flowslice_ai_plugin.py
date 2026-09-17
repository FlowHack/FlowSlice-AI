# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy"]
#
# [tool.orcaslicer.plugin]
# name = "FlowSlice AI"
# description = "ИИ-ассистент инженера 3D-печати в OrcaSlicer: механика, Klipper и тонкая настройка материалов."
# author = "FlowSlice AI Team"
# version = "0.1.0"
# ///
"""FlowSlice AI — нативный Python-плагин OrcaSlicer с ИИ-ассистентом.

Монолитный плагин: вся логика, пользовательский интерфейс и стили хранятся
в одном файле. Этапы E1+E2 реализуют базовую архитектуру, слой конфигурации
и полноценную страницу настроек.
"""
# pylint: disable=too-many-lines
# HTML_PAGE — большая встроенная строка, из-за неё модуль превышает лимит строк.

import datetime
import importlib
import json
import logging
import pathlib
import random
import sys
import threading
import time
from typing import Any
import urllib.error
import urllib.request

import orca

try:
    import numpy as _np
    _HAS_NUMPY = _np is not None
except ImportError:
    _np = None
    _HAS_NUMPY = False


try:
    _PAGES_BASE = getattr(
        importlib.import_module("orca.pages"), "PagesPluginCapabilityBase", None
    )
except (ImportError, AttributeError):
    _PAGES_BASE = None

try:
    _SCRIPT_BASE = getattr(
        importlib.import_module("orca.script"), "ScriptPluginCapabilityBase", None
    )
except (ImportError, AttributeError):
    _SCRIPT_BASE = None


_LOGGER = logging.getLogger("flowslice_ai")
if not _LOGGER.handlers:
    _STREAM_HANDLER = logging.StreamHandler(sys.stderr)
    _STREAM_HANDLER.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    _LOGGER.addHandler(_STREAM_HANDLER)
    _LOGGER.setLevel(logging.INFO)


DEFAULT_PROVIDERS: dict[str, dict[str, Any]] = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "deepseek-chat": {
                "name": "DeepSeek V4 Flash",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "deepseek-reasoner": {
                "name": "DeepSeek V4 Pro",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "deepseek/deepseek-chat-v3-0324": {
                "name": "DeepSeek V3 (0324)",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "anthropic/claude-sonnet-4-5": {
                "name": "Claude Sonnet 4.5",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "openai/gpt-5.1": {
                "name": "GPT-5.1",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "google/gemini-2.5-flash": {
                "name": "Gemini 2.5 Flash",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "meta-llama/llama-3.3-70b-instruct:free": {
                "name": "Llama 3.3 70B (free)",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "google": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "gemini-2.5-flash": {
                "name": "Gemini 2.5 Flash",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "gemini-2.5-pro": {
                "name": "Gemini 2.5 Pro",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "gemini-2.5-flash-lite": {
                "name": "Gemini 2.5 Flash Lite",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "anthropic",
        "models": {
            "claude-opus-4-8": {
                "name": "Claude Opus 4.8",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "claude-sonnet-4-6": {
                "name": "Claude Sonnet 4.6",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "claude-haiku-4-5": {
                "name": "Claude Haiku 4.5",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "gpt-5.1": {
                "name": "GPT-5.1",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "gpt-5-mini": {
                "name": "GPT-5 Mini",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "gpt-4o": {
                "name": "GPT-4o",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "llama-3.3-70b-versatile": {
                "name": "Llama 3.3 70B Versatile",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "llama-3.1-8b-instant": {
                "name": "Llama 3.1 8B Instant",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "deepseek-r1-distill-llama-70b": {
                "name": "DeepSeek R1 Distill 70B",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "glm": {
        "name": "Zhipu GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "glm-4.6": {
                "name": "GLM-4.6",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "glm-4.5": {
                "name": "GLM-4.5",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "glm-4-flash": {
                "name": "GLM-4-Flash",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "cerebras": {
        "name": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "llama3.3-70b": {
                "name": "Llama 3.3 70B",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "llama-3.1-8b": {
                "name": "Llama 3.1 8B",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "mistral": {
        "name": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "mistral-large-latest": {
                "name": "Mistral Large",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "mistral-small-latest": {
                "name": "Mistral Small",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "xai": {
        "name": "xAI",
        "base_url": "https://api.x.ai/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "grok-3": {
                "name": "Grok 3",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "grok-3-mini": {
                "name": "Grok 3 Mini",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "custom": {
        "name": "Custom",
        "base_url": "",
        "api_key": "",
        "builtin": False,
        "scheme": "openai",
        "models": {},
    },
}

DEFAULT_CONFIG: dict[str, Any] = {
    "providers": json.loads(json.dumps(DEFAULT_PROVIDERS)),
    "active_provider": "deepseek",
    "active_model": "deepseek-chat",
    "default_model": "deepseek::deepseek-chat",
    "notes": "",
    "theme": "auto",
    "font_size": 14,
    "font_style": "system",
    "temperature": 0.7,
    "max_tokens": 4096,
    "reasoning": False,
    "usage": {},
}

# Ключи настроек, отправляемые в UI (без секретов).
SETTINGS_KEYS: tuple[str, ...] = (
    "active_provider",
    "active_model",
    "default_model",
    "notes",
    "temperature",
    "max_tokens",
    "reasoning",
    "theme",
    "font_size",
    "font_style",
)

# Служебные команды чата: единый источник для /help и state.
COMMANDS: list[tuple[str, str]] = [
    ("/context", "полный дамп контекста слайсера"),
    ("/clear", "очистить историю чата"),
    ("/model", "отчёт о модели на столе"),
    ("/printer", "сводка профилей печати"),
    ("/stats", "статистика использования"),
    ("/help", "список команд"),
    ("/reset", "сбросить настройки плагина"),
]

# Разделы пресетов: ключ результата → (атрибут коллекции, поля для full_config_value).
PRESET_SECTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "printer": (
        "printers",
        (
            "printer_model",
            "nozzle_diameter",
            "printable_height",
            "printable_width",
            "printable_depth",
            "printer_technology",
            "bed_shape",
            "bed_length",
            "bed_width",
            "max_print_height",
            "heated_bed",
            "heated_chamber",
            "chamber_temperature",
            "notes",
        ),
    ),
    "filament": (
        "filaments",
        (
            "filament_type",
            "filament_vendor",
            "filament_density",
            "filament_cost",
            "filament_flow_ratio",
            "filament_flow_ratio_initial_layer",
            "nozzle_temperature",
            "nozzle_temperature_initial_layer",
            "bed_temperature",
            "chamber_temperature",
            "notes",
        ),
    ),
    "print": (
        "prints",
        (
            "layer_height",
            "initial_layer_print_height",
            "line_width",
            "wall_loops",
            "sparse_infill_density",
            "sparse_infill_pattern",
            "enable_support",
            "support_type",
            "default_print_speed",
            "outer_wall_speed",
            "travel_speed",
            "brim_type",
            "brim_width",
            "ironing_type",
            "notes",
        ),
    ),
}

SYSTEM_PROMPT = (
    "You are FlowSlice AI, a strictly professional 3D-printing engineer embedded "
    "in OrcaSlicer. Provide highly technical, concrete advice. Focus expertise on "
    "mechanics, Klipper firmware configuration, and precise material tuning "
    "(e.g., PETG, TPU)."
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

STORAGE_DIR = pathlib.Path(__file__).resolve().parent
CHATS_FILE = STORAGE_DIR / "chats.json"
ICON_FILE = STORAGE_DIR / "tab_icon.svg"

# Собственный строгий геометрический знак: стилизованный поток/капля с крестом.
_TAB_ICON_SVG = """<svg version="1.0" xmlns="http://www.w3.org/2000/svg"
 width="20" height="20" viewBox="0 0 606 606"><g transform="translate(0.000000,606.000000) scale(0.100000,-0.100000)"
fill="#fff" stroke="none"><path d="M2847 5989 c-258 -25 -508 -114 -711 -253 -250 -170 -447 -433 -541
-721 -29 -91 -60 -259 -70 -387 l-7 -86 -63 -31 c-89 -44 -158 -110 -195 -184
-52 -107 -51 -157 16 -627 28 -197 43 -254 86 -322 57 -91 139 -152 288 -216
l45 -19 23 -119 c58 -297 108 -430 214 -569 l53 -70 0 -445 c0 -491 -1 -478
65 -553 126 -144 456 -257 841 -287 507 -41 1071 134 1169 362 23 53 23 54 15
385 -4 183 -4 379 0 437 7 104 7 105 54 169 60 82 116 188 147 279 23 69 84
351 84 390 0 13 12 24 38 34 195 79 290 163 340 300 34 92 107 640 99 739 -10
132 -91 244 -228 314 l-65 34 -12 126 c-36 383 -170 673 -426 918 -324 312
-758 450 -1259 402z m453 -143 c196 -30 375 -99 547 -212 96 -61 284 -244 317
-306 l19 -36 -36 -84 c-46 -108 -92 -272 -118 -418 -24 -139 -49 -395 -49
-499 l0 -76 -103 -1 c-176 -3 -387 -53 -497 -120 -137 -82 -222 -223 -239
-398 -9 -95 5 -471 19 -503 11 -26 46 -31 73 -11 16 12 16 30 6 239 -10 195
-9 236 4 301 44 215 160 315 427 366 224 44 316 38 440 -26 55 -28 82 -37 97
-31 24 9 34 29 27 57 -6 20 -117 92 -143 92 -31 0 5 447 54 678 27 124 93 332
105 332 11 0 64 -125 93 -220 50 -163 62 -258 61 -480 0 -211 -8 -301 -50
-622 -47 -361 -41 -348 -228 -522 -231 -214 -304 -288 -330 -335 -35 -66 -56
-161 -120 -551 -31 -184 -60 -351 -66 -371 -13 -48 -176 -186 -275 -233 -116
-56 -263 -76 -411 -57 -153 21 -266 78 -395 201 l-78 75 -51 310 c-65 400 -96
547 -128 614 -26 57 -75 107 -331 342 -169 156 -178 170 -202 310 -28 172 -67
494 -80 674 -23 315 15 567 116 790 20 43 38 75 41 73 3 -3 22 -57 44 -121 71
-213 107 -431 117 -712 l6 -170 -63 -30 c-70 -33 -101 -65 -93 -95 11 -42 39
-43 106 -6 86 48 181 69 276 61 150 -13 331 -54 406 -93 17 -8 53 -35 81 -58
28 -24 57 -44 64 -44 20 0 50 31 50 51 0 22 -56 80 -113 116 -108 68 -337 124
-509 125 l-108 1 0 99 c0 294 -70 669 -167 896 -42 99 -43 95 51 205 121 141
296 267 474 342 104 44 293 91 417 104 112 12 319 6 445 -13z m-1770 -1510 c0
-127 45 -493 108 -868 15 -93 24 -168 19 -168 -4 0 -29 11 -55 24 -86 44 -147
127 -170 231 -12 51 -51 329 -73 512 -13 115 -5 172 36 234 25 38 112 102 126
93 5 -3 9 -29 9 -58z m3100 7 c42 -35 80 -116 80 -170 0 -44 -53 -476 -70
-573 -17 -96 -40 -148 -87 -200 -41 -46 -138 -108 -149 -97 -3 3 11 101 30
218 46 276 106 767 106 861 0 17 2 17 29 4 16 -9 43 -28 61 -43z m-2530 -1283
c77 -76 94 -109 121 -232 25 -114 110 -620 106 -625 -6 -5 -176 182 -245 270
-147 186 -178 265 -247 632 -19 105 -38 203 -41 219 -6 26 9 15 117 -85 68
-63 153 -143 189 -179z m2125 35 c-26 -130 -55 -267 -67 -304 -31 -102 -90
-207 -181 -322 -103 -129 -247 -281 -242 -254 3 11 21 119 40 240 48 298 82
459 104 504 11 20 57 73 103 118 133 129 281 263 285 259 2 -2 -17 -111 -42
-241z m-1797 -1181 c122 -109 219 -172 315 -206 149 -53 373 -60 529 -17 158
44 292 142 531 388 l137 142 0 -118 c0 -65 3 -219 7 -343 5 -196 4 -229 -10
-256 -22 -43 -67 -78 -151 -121 -68 -35 -237 -95 -245 -88 -1 2 17 88 42 192
53 219 56 239 40 236 -7 -2 -35 -17 -62 -34 -40 -24 -53 -38 -60 -67 -6 -20
-28 -108 -50 -195 -21 -87 -41 -160 -44 -163 -13 -13 -242 -34 -377 -34 -131
0 -364 21 -376 33 -2 2 -26 91 -52 198 l-49 194 -59 38 c-58 38 -59 38 -62 15
-1 -13 18 -105 43 -206 25 -101 45 -189 45 -197 0 -31 -278 80 -349 140 -58
50 -59 55 -53 434 l5 344 106 -113 c58 -63 148 -151 199 -196z"/><path d="M2130 3895 c-160 -45 -177 -83 -82 -175 126 -123 308 -149 544 -79
101 29 102 58 6 144 -59 53 -145 97 -226 114 -69 14 -185 13 -242 -4z"/><path d="M3686 3898 c-83 -16 -170 -62 -235 -125 -34 -32 -61 -64 -61 -71 0
-60 261 -120 404 -93 115 21 231 95 272 173 18 35 11 50 -35 76 -83 47 -224
64 -345 40z"/><path d="M2782 2998 c-13 -13 -16 -47 -4 -65 4 -6 52 -33 107 -60 135 -65 164
-64 303 5 93 47 102 55 102 80 0 63 -33 66 -140 12 -54 -27 -93 -40 -120 -40
-27 0 -66 13 -120 40 -84 42 -108 48 -128 28z"/><path d="M2760 2564 c-52 -13 -103 -24 -112 -24 -27 0 -52 -44 -39 -68 16 -30
34 -33 134 -15 67 11 115 13 177 8 103 -9 110 -9 230 0 70 5 116 3 177 -9 89
-17 108 -14 124 16 19 35 -11 63 -83 77 -35 7 -85 19 -112 27 -63 18 -134 17
-166 -1 -33 -19 -69 -19 -113 0 -49 20 -105 18 -217 -11z"/><path d="M2807 2295 c-31 -31 -14 -68 40 -87 52 -18 315 -18 366 0 41 15 61
43 52 72 -9 28 -37 33 -120 19 -71 -11 -184 -9 -281 7 -31 5 -44 2 -57 -11z"/><path d="M994 2311 c-51 -13 -112 -53 -138 -90 -13 -20 -93 -191 -176 -381
-84 -190 -194 -439 -245 -555 -51 -115 -127 -286 -168 -380 -42 -93 -103 -231
-136 -305 l-61 -135 0 -106 c0 -71 5 -118 15 -141 18 -45 74 -94 122 -107 53
-15 5593 -15 5646 0 47 13 106 63 123 106 9 20 14 72 14 140 l0 107 -72 160
c-39 89 -97 220 -129 291 -31 72 -94 213 -139 315 -45 102 -115 259 -155 350
-236 536 -277 626 -300 656 -13 17 -46 42 -72 55 -47 23 -50 23 -478 23 l-430
1 -3 -67 -3 -68 182 -2 182 -3 48 -135 c27 -74 49 -141 49 -147 0 -10 -53 -13
-230 -13 l-230 0 0 -45 0 -45 238 0 c176 0 242 -3 254 -12 8 -7 32 -60 53
-118 21 -58 48 -133 61 -167 l23 -63 -273 0 -274 0 -38 158 -39 157 -5 -150
c-5 -138 -7 -154 -33 -203 -15 -30 -27 -56 -27 -58 0 -2 15 -4 33 -4 l32 0 43
-182 c23 -101 42 -186 42 -190 0 -5 -128 -8 -284 -8 -314 0 -296 -4 -296 65 0
43 -10 49 -61 34 l-41 -13 7 -43 6 -43 -601 0 -601 0 6 44 7 43 -46 16 -45 15
-6 -46 c-4 -26 -8 -53 -10 -60 -3 -9 -70 -12 -290 -12 -157 0 -285 2 -285 5 0
11 82 361 87 368 2 4 17 7 34 7 16 0 29 2 29 4 0 2 -12 28 -27 58 -25 48 -28
65 -33 198 l-5 145 -34 -140 c-18 -77 -37 -147 -42 -155 -6 -13 -47 -15 -273
-15 -172 0 -266 4 -266 10 0 13 105 307 119 334 11 20 18 21 256 21 l245 0 0
45 0 45 -230 0 c-126 0 -230 4 -230 9 0 7 74 221 95 274 6 15 25 17 187 17
l179 0 -3 68 -3 67 -410 2 c-225 0 -424 -2 -441 -6z m355 -243 c-23 -62 -47
-129 -53 -148 l-13 -35 -221 -3 -221 -2 39 89 c58 133 88 189 107 200 11 6 98
11 210 11 l192 0 -40 -112z m3738 90 c18 -20 38 -60 114 -236 l18 -42 -221 2
-221 3 -17 50 c-10 28 -34 94 -53 148 l-36 97 198 0 c192 0 198 -1 218 -22z
m-3844 -375 c4 -7 -19 -73 -109 -319 l-15 -42 -213 -1 c-118 -1 -225 1 -239 4
l-24 7 74 166 c41 92 77 173 80 180 4 9 58 12 223 12 121 0 221 -3 223 -7z
m4097 -176 c43 -97 75 -179 71 -181 -12 -6 -397 -4 -435 2 l-39 7 -62 172
c-34 95 -60 175 -57 178 3 3 104 4 225 3 l219 -3 78 -178z m-4282 -359 c-16
-46 -47 -130 -67 -188 l-38 -105 -261 -3 -261 -2 18 42 c42 97 143 324 148
331 2 4 114 7 248 7 l244 0 -31 -82z m682 70 c0 -7 -19 -93 -42 -190 l-42
-178 -298 0 c-180 0 -298 4 -298 9 0 8 100 289 125 354 7 16 29 17 281 17 212
0 274 -3 274 -12z m3165 -83 c18 -49 49 -134 69 -187 l35 -98 -302 0 -302 0
-43 183 c-23 100 -42 185 -42 190 0 4 124 6 276 5 l276 -3 33 -90z m565 86 c0
-5 36 -90 79 -188 l80 -178 -256 -3 c-141 -1 -258 0 -261 2 -6 7 -132 356
-132 367 0 5 109 9 245 9 144 0 245 -4 245 -9z m-4555 -478 c-10 -25 -115
-317 -115 -320 0 -2 -126 -3 -280 -3 l-280 0 15 38 c9 20 43 97 77 170 l61
132 265 0 c248 0 264 -1 257 -17z m715 0 c0 -10 -16 -87 -36 -170 l-36 -153
-324 0 c-192 0 -324 4 -324 9 0 14 91 272 106 304 l15 27 299 0 c279 0 300 -1
300 -17z m690 4 c0 -17 -28 -254 -35 -294 l-6 -33 -309 0 c-171 0 -310 2 -310
4 0 6 71 310 75 324 6 18 585 18 585 -1z m660 -157 l0 -170 -300 0 c-165 0
-300 1 -300 3 0 1 9 72 20 157 11 85 20 161 20 168 0 9 63 12 280 12 l280 0 0
-170z m664 138 c6 -34 36 -288 36 -301 0 -4 -135 -7 -300 -7 l-300 0 0 170 0
170 280 0 279 0 5 -32z m680 24 c5 -8 76 -310 76 -323 0 -5 -139 -9 -310 -9
-170 0 -310 1 -310 3 0 1 -9 74 -20 162 -11 88 -20 163 -20 167 0 10 577 10
584 0z m724 -19 c6 -16 31 -84 56 -153 24 -69 47 -133 51 -143 7 -16 -11 -17
-321 -15 l-328 3 -38 155 c-21 85 -38 161 -38 168 0 9 67 12 304 12 l304 0 10
-27z m698 -142 c41 -91 74 -166 74 -168 0 -2 -125 -3 -278 -3 l-278 0 -57 159
c-31 87 -57 164 -57 170 0 8 70 11 261 9 l261 -3 74 -164z m114 -359 c0 -34
-6 -66 -14 -78 -14 -19 -54 -19 -2811 -19 l-2797 0 -19 24 c-13 16 -19 39 -19
77 l0 54 2830 0 2830 0 0 -58z"/></g></svg>"""


class FlowSliceError(Exception):
    """Базовая ошибка плагина FlowSlice AI."""


class ConfigError(FlowSliceError):
    """Ошибка чтения, нормализации или сохранения конфигурации."""


class ApiError(FlowSliceError):
    """Ошибка ответа внешнего ИИ-провайдера."""


class NetworkError(FlowSliceError):
    """Ошибка сетевого взаимодействия."""


class StreamError(FlowSliceError):
    """Ошибка потоковой передачи ответа модели."""


class ContextError(FlowSliceError):
    """Ошибка сбора контекста слайсера."""


HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FlowSlice AI</title>
<style>
/* ===== Базовые переменные и темизация ===== */
* {
  box-sizing: border-box;
}
html,
body {
  margin: 0;
  padding: 0;
  height: 100%;
}
body {
  --orca-accent: #d9534f;
  --orca-accent-fg: #ffffff;
  background: var(--orca-bg);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 14px;
  overflow: hidden;
}
/* Принудительная чисто белая тема */
body.theme-light {
  color-scheme: light;
  --orca-bg: #ffffff;
  --orca-fg: #1a1a1a;
  --orca-muted: #6b6b6b;
  --orca-border: #d9d9d9;
  --orca-input: #f5f5f5;
  --orca-accent: #d9534f;
  --orca-accent-fg: #ffffff;
}
/* Принудительная чисто чёрная тема */
body.theme-dark {
  color-scheme: dark;
  --orca-bg: #000000;
  --orca-fg: #e6e6e6;
  --orca-muted: #8a8a8a;
  --orca-border: #2a2a2a;
  --orca-input: #141414;
  --orca-accent: #d9534f;
  --orca-accent-fg: #ffffff;
}
/* Нативные дропдауны: явные цвета, чтобы не было белого текста на белом фоне */
select {
  background: var(--orca-input);
  color: var(--orca-fg);
}
select option {
  background: var(--orca-input);
  color: var(--orca-fg);
}
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-thumb {
  background: var(--orca-border);
  border-radius: 4px;
}
::-webkit-scrollbar-track {
  background: transparent;
}

/* ===== Каркас приложения ===== */
.app {
  display: flex;
  height: 100vh;
}

/* ===== Sidebar чатов ===== */
.sidebar {
  width: 240px;
  min-width: 240px;
  border-right: 1px solid var(--orca-border);
  display: flex;
  flex-direction: column;
  background: var(--orca-bg);
}
.sidebar-header {
  padding: 12px;
  border-bottom: 1px solid var(--orca-border);
}
.sidebar-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--orca-muted);
  margin-bottom: 8px;
}
.sidebar-search {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  background: var(--orca-input);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 13px;
}
.sidebar-search:focus {
  outline: none;
  border-color: var(--orca-accent);
}
.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.chat-group {
  font-size: 11px;
  color: var(--orca-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 8px 6px 4px;
}
.chat-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  padding: 7px 8px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 2px;
}
.chat-item:hover {
  background: var(--orca-input);
}
.chat-item.active {
  background: var(--orca-input);
  box-shadow: inset 2px 0 0 var(--orca-accent);
}
.chat-title {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}
.chat-actions {
  display: none;
  gap: 2px;
}
.chat-item:hover .chat-actions {
  display: flex;
}
.chat-action {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  padding: 2px 3px;
  border-radius: 4px;
  color: var(--orca-muted);
}
.chat-action:hover {
  background: var(--orca-border);
  color: var(--orca-fg);
}
.sidebar-empty {
  padding: 12px 8px;
  font-size: 12px;
  color: var(--orca-muted);
  text-align: center;
}

/* ===== Основная область ===== */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--orca-border);
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
}
.brand-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #d9534f;
}
.brand-name {
  font-weight: 700;
  font-size: 15px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.model-status {
  font-size: 12px;
  color: var(--orca-muted);
  margin-right: 4px;
}
.icon-btn {
  border: 1px solid var(--orca-border);
  background: transparent;
  color: var(--orca-fg);
  border-radius: 6px;
  padding: 5px 9px;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}
.icon-btn:hover {
  border-color: var(--orca-accent);
  color: var(--orca-accent);
}

/* ===== Область сообщений ===== */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.msg-wrap {
  display: flex;
  flex-direction: column;
  max-width: 78%;
}
.msg-user {
  align-self: flex-end;
  align-items: flex-end;
}
.msg-assistant {
  align-self: flex-start;
}
.msg-system {
  align-self: center;
}
.msg-bubble {
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-user .msg-bubble {
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
  border-bottom-right-radius: 2px;
}
.msg-assistant .msg-bubble {
  background: var(--orca-input);
  border: 1px solid var(--orca-border);
  border-left: 3px solid var(--orca-accent);
  border-bottom-left-radius: 2px;
}
.msg-error .msg-bubble {
  border: 1px solid var(--orca-accent);
  background: var(--orca-input);
}
.msg-system .msg-bubble {
  background: var(--orca-input);
  border: 1px dashed var(--orca-border);
  color: var(--orca-muted);
  font-size: 12px;
  font-family: Consolas, monospace;
  padding: 6px 10px;
  max-width: 100%;
  text-align: left;
}
.msg-time {
  font-size: 10px;
  color: var(--orca-muted);
  margin-top: 3px;
}
.msg-image {
  max-width: 100%;
  max-height: 240px;
  border-radius: 8px;
  margin-bottom: 6px;
  display: block;
}
.msg-actions {
  display: none;
  gap: 4px;
  margin-top: 4px;
}
.msg-wrap:hover .msg-actions {
  display: flex;
}
.msg-action {
  border: 1px solid var(--orca-border);
  background: var(--orca-bg);
  color: var(--orca-muted);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
}
.msg-action:hover {
  border-color: var(--orca-accent);
  color: var(--orca-accent);
}
.msg-streaming .msg-bubble::after {
  content: "▌";
  color: var(--orca-accent);
  animation: blink 1s infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}

/* ===== Welcome-сообщение ===== */
.welcome {
  align-self: center;
  text-align: center;
  margin-top: 10vh;
  max-width: 480px;
}
.welcome-title {
  font-size: 22px;
  font-weight: 700;
}
.welcome-sub {
  color: var(--orca-muted);
  font-size: 13px;
  margin: 8px 0 16px;
}
.welcome-cmds {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
}
.welcome-cmd {
  border: 1px solid var(--orca-border);
  border-radius: 12px;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--orca-muted);
  font-family: Consolas, monospace;
}

/* ===== Индикатор «печатает…» ===== */
.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 16px 8px;
  color: var(--orca-muted);
  font-size: 12px;
}
.typing .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--orca-accent);
  animation: bounce 1.2s infinite;
}
.typing .dot:nth-child(2) {
  animation-delay: 0.15s;
}
.typing .dot:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}
.typing-text {
  margin-left: 6px;
}

/* ===== Панель контекста ===== */
.context-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 16px;
  border-top: 1px solid var(--orca-border);
  gap: 8px;
  flex-wrap: wrap;
}
.context-checks {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.ctx-check {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--orca-muted);
  cursor: pointer;
}
.ctx-check input {
  accent-color: var(--orca-accent);
}
.context-tokens {
  font-size: 12px;
  color: var(--orca-muted);
}

/* ===== Композер (input) ===== */
.composer {
  padding: 8px 16px 12px;
  border-top: 1px solid var(--orca-border);
  position: relative;
}
/* ===== Автодополнение команд по «/» ===== */
.cmd-suggest {
  position: absolute;
  bottom: 100%;
  left: 16px;
  right: 16px;
  margin-bottom: 6px;
  background: var(--orca-bg);
  border: 1px solid var(--orca-border);
  border-radius: 8px;
  max-height: 210px;
  overflow-y: auto;
  z-index: 60;
  box-shadow: 0 -4px 18px rgba(0, 0, 0, 0.25);
}
.cmd-suggest-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 7px 10px;
  cursor: pointer;
  font-size: 13px;
}
.cmd-suggest-item:hover {
  background: var(--orca-input);
}
.cmd-suggest-item.active {
  background: var(--orca-input);
  box-shadow: inset 2px 0 0 var(--orca-accent);
}
.cmd-suggest-cmd {
  font-family: Consolas, monospace;
  color: var(--orca-accent);
  white-space: nowrap;
}
.cmd-suggest-desc {
  color: var(--orca-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cmd-suggest-empty {
  padding: 8px 10px;
  font-size: 12px;
  color: var(--orca-muted);
}
.attach-preview {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.attach-card {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  background: var(--orca-input);
}
.attach-card img {
  width: 28px;
  height: 28px;
  object-fit: cover;
  border-radius: 4px;
}
.attach-name {
  max-width: 160px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.attach-remove {
  border: none;
  background: transparent;
  color: var(--orca-muted);
  cursor: pointer;
  font-size: 12px;
}
.attach-remove:hover {
  color: var(--orca-accent);
}
.input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.input-row textarea {
  flex: 1;
  resize: none;
  border: 1px solid var(--orca-border);
  border-radius: 8px;
  background: var(--orca-input);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 14px;
  padding: 9px 12px;
  max-height: 120px;
  line-height: 1.4;
}
.input-row textarea:focus {
  outline: none;
  border-color: var(--orca-accent);
}
.send-btn {
  border: none;
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
  border-radius: 8px;
  padding: 9px 14px;
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
}
.send-btn:hover {
  filter: brightness(1.1);
}
.stop-btn {
  border: 1px solid var(--orca-accent);
  background: transparent;
  color: var(--orca-accent);
  border-radius: 8px;
  padding: 9px 12px;
  cursor: pointer;
  font-size: 13px;
}
.stop-btn:hover {
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
}

/* ===== Модалка настроек ===== */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  width: 420px;
  max-width: 92vw;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: var(--orca-bg);
  border: 1px solid var(--orca-border);
  border-radius: 10px;
  padding: 16px;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.modal-header span {
  font-size: 15px;
  font-weight: 600;
}
.field {
  margin-bottom: 12px;
}
.field label {
  display: block;
  font-size: 12px;
  color: var(--orca-muted);
  margin-bottom: 5px;
}
.field select,
.field input[type="text"],
.field input[type="password"] {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  background: var(--orca-input);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 13px;
}
.field select:focus,
.field input:focus {
  outline: none;
  border-color: var(--orca-accent);
}
.field input[type="range"] {
  width: 100%;
  accent-color: var(--orca-accent);
}
.key-row {
  display: flex;
  gap: 6px;
}
.key-row input {
  flex: 1;
}
.eye-btn {
  border: 1px solid var(--orca-border);
  background: transparent;
  color: var(--orca-muted);
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  white-space: nowrap;
}
.eye-btn:hover {
  border-color: var(--orca-accent);
  color: var(--orca-accent);
}
.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.check-row input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--orca-accent);
  margin: 0;
}
.check-row label {
  margin: 0;
  cursor: pointer;
}
.range-value {
  color: var(--orca-accent);
  font-weight: 600;
}
.copy-modal-text {
  width: 100%;
  min-height: 160px;
  resize: vertical;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  background: var(--orca-input);
  color: var(--orca-fg);
  font-family: Consolas, monospace;
  font-size: 12px;
  padding: 8px;
  margin-bottom: 12px;
}
.copy-modal-text:focus {
  outline: none;
  border-color: var(--orca-accent);
}
.ghost-btn {
  border: 1px solid var(--orca-border);
  background: transparent;
  color: var(--orca-fg);
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
}
.ghost-btn:hover {
  border-color: var(--orca-accent);
  color: var(--orca-accent);
}
.usage-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.usage-row select {
  padding: 5px 8px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  background: var(--orca-input);
  color: var(--orca-fg);
  font-size: 12px;
}
.usage-row span {
  font-size: 12px;
  color: var(--orca-muted);
}
.modal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.danger-btn {
  border: 1px solid var(--orca-accent);
  background: transparent;
  color: var(--orca-accent);
  border-radius: 6px;
  padding: 7px 12px;
  cursor: pointer;
  font-size: 13px;
}
.danger-btn:hover {
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
}
.primary-btn {
  border: none;
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
  border-radius: 6px;
  padding: 7px 14px;
  cursor: pointer;
  font-size: 13px;
}
.primary-btn:hover {
  filter: brightness(1.1);
}

/* ===== Toast-уведомления ===== */
.toast {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--orca-fg);
  color: var(--orca-bg);
  border-radius: 8px;
  padding: 9px 16px;
  font-size: 13px;
  z-index: 200;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  transition: opacity 0.3s;
}
.toast-ok {
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
}
.toast-err {
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
}
.toast-hide {
  opacity: 0;
}

/* ===== Чип выбора модели под композером ===== */
.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 8px;
}
.model-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  border: 1px solid var(--orca-border);
  background: var(--orca-input);
  color: var(--orca-fg);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  font-family: var(--orca-font);
  cursor: pointer;
  transition: border-color 0.15s;
}
.model-chip:hover {
  border-color: var(--orca-accent);
}
.chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--orca-accent);
  flex-shrink: 0;
}
.chip-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chip-caret {
  color: var(--orca-muted);
  font-size: 10px;
  flex-shrink: 0;
}

/* ===== Модалка выбора модели ===== */
.mp-modal {
  width: 440px;
  max-width: 92vw;
  max-height: 72vh;
  display: flex;
  flex-direction: column;
  background: var(--orca-bg);
  border: 1px solid var(--orca-border);
  border-radius: 10px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
  overflow: hidden;
}
.mp-search {
  margin: 0 12px 8px;
  padding: 8px 12px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  background: var(--orca-input);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 13px;
}
.mp-search:focus {
  outline: none;
  border-color: var(--orca-accent);
}
.mp-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
  min-height: 120px;
}
.mp-group-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--orca-muted);
  padding: 10px 8px 4px;
}
.mp-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.mp-item:hover {
  background: var(--orca-input);
}
.mp-item.active {
  background: var(--orca-input);
  box-shadow: inset 2px 0 0 var(--orca-accent);
}
.mp-item-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mp-item-id {
  font-family: Consolas, monospace;
  font-size: 11px;
  color: var(--orca-muted);
  max-width: 40%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mp-check {
  color: var(--orca-accent);
  font-weight: 700;
  flex-shrink: 0;
}
.mp-star {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 15px;
  color: var(--orca-muted);
  padding: 0 2px;
  flex-shrink: 0;
}
.mp-star:hover {
  color: var(--orca-accent);
}
.mp-star.active {
  color: var(--orca-accent);
}
.mp-empty {
  padding: 14px 10px;
  font-size: 12px;
  color: var(--orca-muted);
  text-align: center;
}

/* ===== Кастомный дропдаун с поиском ===== */
.dd-wrap {
  position: relative;
}
.dd-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  width: 100%;
  border: 1px solid var(--orca-border);
  background: var(--orca-input);
  color: var(--orca-fg);
  border-radius: 6px;
  padding: 6px 10px;
  font-family: var(--orca-font);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
}
.dd-btn:hover {
  border-color: var(--orca-accent);
}
.dd-btn-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dd-caret {
  color: var(--orca-muted);
  font-size: 10px;
  flex-shrink: 0;
}
.dd-popup {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--orca-bg);
  border: 1px solid var(--orca-border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  z-index: 100;
  max-height: 260px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.dd-search {
  margin: 6px;
  padding: 6px 10px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  background: var(--orca-input);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 13px;
}
.dd-search:focus {
  outline: none;
  border-color: var(--orca-accent);
}
.dd-list {
  overflow-y: auto;
  padding: 4px;
}
.dd-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.dd-item:hover {
  background: var(--orca-input);
}
.dd-item.active {
  background: var(--orca-input);
  box-shadow: inset 2px 0 0 var(--orca-accent);
}
.dd-item-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dd-check {
  color: var(--orca-accent);
  font-weight: 700;
  flex-shrink: 0;
}
.dd-empty {
  padding: 10px;
  font-size: 12px;
  color: var(--orca-muted);
  text-align: center;
}
.dd-default-badge {
  font-size: 10px;
  color: var(--orca-muted);
  border: 1px dashed var(--orca-border);
  border-radius: 4px;
  padding: 1px 5px;
  white-space: nowrap;
  flex-shrink: 0;
}
.mini-btn {
  border: 1px solid var(--orca-border);
  background: transparent;
  color: var(--orca-muted);
  border-radius: 6px;
  padding: 3px 8px;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  flex-shrink: 0;
}
.mini-btn:hover {
  border-color: var(--orca-accent);
  color: var(--orca-accent);
}
.settings-scroll {
  overflow-y: auto;
  flex: 1;
  padding: 4px 2px;
}
.per-model-controls {
  display: flex;
  align-items: center;
  gap: 6px;
}
.per-model-controls input[type="range"],
.per-model-controls input[type="number"] {
  flex: 1;
  min-width: 0;
}
.provider-model-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  margin-bottom: 6px;
  cursor: pointer;
  font-size: 13px;
  background: var(--orca-input);
}
.provider-model-row:hover {
  border-color: var(--orca-accent);
}
.provider-model-row.active {
  box-shadow: inset 2px 0 0 var(--orca-accent);
}
.provider-model-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.provider-model-id {
  font-family: Consolas, monospace;
  font-size: 11px;
  color: var(--orca-muted);
  max-width: 40%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.provider-model-del {
  border: none;
  background: transparent;
  color: var(--orca-muted);
  cursor: pointer;
  font-size: 12px;
  flex-shrink: 0;
}
.provider-model-del:hover {
  color: var(--orca-accent);
}
#addModelForm input[type="text"],
#addModelForm input[type="password"],
#addModelForm input[type="number"] {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  background: var(--orca-input);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 13px;
  margin-bottom: 8px;
  box-sizing: border-box;
}
#addModelForm input:focus {
  outline: none;
  border-color: var(--orca-accent);
}
#addModelForm .dd-wrap {
  margin-bottom: 8px;
}
#addModelForm label {
  display: block;
  font-size: 12px;
  color: var(--orca-muted);
  margin-bottom: 5px;
}
#addModelForm .check-row {
  margin-bottom: 8px;
}
#addModelForm .modal-actions {
  margin-top: 4px;
}
details.field summary {
  cursor: pointer;
  font-size: 12px;
  color: var(--orca-muted);
  margin-bottom: 8px;
}
details.field summary:hover {
  color: var(--orca-accent);
}
</style>
</head>
<body>
<div class="app">
  <!-- Sidebar чатов -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-title">Чаты</div>
      <input type="text" id="searchInput" class="sidebar-search" placeholder="Поиск чатов…">
    </div>
    <div class="chat-list" id="chatList"></div>
  </aside>

  <!-- Основная область -->
  <section class="main">
    <header class="main-header">
      <div class="brand">
        <span class="brand-dot"></span>
        <span class="brand-name">FlowSlice AI</span>
      </div>
      <div class="header-right">
        <span class="model-status" id="modelStatus"></span>
        <button type="button" id="settingsBtn" class="icon-btn" title="Настройки">⚙</button>
        <button type="button" id="newChatBtn" class="icon-btn" title="Новый чат">+</button>
      </div>
    </header>

    <main class="messages" id="messages"></main>

    <div class="typing" id="typing" style="display:none">
      <span class="dot"></span>
      <span class="dot"></span>
      <span class="dot"></span>
      <span class="typing-text">печатает…</span>
    </div>

    <!-- Панель контекста -->
    <div class="context-panel">
      <div class="context-checks" id="contextChecks"></div>
      <div class="context-tokens" id="contextTokens">≈ 0 токенов</div>
    </div>

    <!-- Композер -->
    <div class="composer">
      <div class="cmd-suggest" id="cmdSuggest" style="display:none"></div>
      <div class="attach-preview" id="attachPreview"></div>
      <div class="input-row">
        <button type="button" id="attachBtn" class="icon-btn" title="Прикрепить файл">📎</button>
        <textarea id="input" rows="1" placeholder="Сообщение… (Enter — отправить, Shift+Enter — новая строка)"></textarea>
        <button type="button" id="stopBtn" class="stop-btn" title="Остановить генерацию" style="display:none">■</button>
        <button type="button" id="sendBtn" class="send-btn" title="Отправить">➤</button>
        <input type="file" id="fileInput" multiple accept="image/*,.txt,.md,.json,.gcode,.stl,.3mf" style="display:none">
      </div>
      <div class="composer-footer">
        <button type="button" id="modelChip" class="model-chip" title="Выбрать модель">
          <span class="chip-dot"></span>
          <span class="chip-label" id="modelChipLabel">—</span>
          <span class="chip-caret">▾</span>
        </button>
      </div>
    </div>
  </section>
</div>

<!-- Модалка настроек -->
<div class="modal-overlay" id="settingsModal" style="display:none">
  <div class="modal">
    <div class="modal-header">
      <span>Настройки</span>
      <button type="button" id="modalClose" class="icon-btn" title="Закрыть">✕</button>
    </div>
    <div class="settings-scroll">
      <div class="field">
        <label>Провайдер</label>
        <div class="dd-wrap" id="setProviderDD"></div>
      </div>
      <div class="field">
        <label for="setApiKey">API-ключ (провайдера)</label>
        <div class="key-row">
          <input type="password" id="setApiKey" autocomplete="off">
          <button type="button" id="setApiKeyEye" class="eye-btn" title="Показать ключ">👁</button>
          <button type="button" id="testKeyBtn" class="ghost-btn">Проверить ключ</button>
        </div>
      </div>
      <div class="field" id="customUrlWrap" style="display:none">
        <label for="setBaseUrl">Базовый URL API</label>
        <input type="text" id="setBaseUrl" autocomplete="off">
        <label for="setSchemeDD" style="margin-top:8px">Схема API</label>
        <div class="dd-wrap" id="setSchemeDD"></div>
      </div>
      <div class="field">
        <label>Модель</label>
        <div class="dd-wrap" id="setModelDD"></div>
      </div>
      <div class="field" id="modelSettingsBlock">
        <label>Настройки модели: <span id="modelSettingsLabel">—</span></label>
        <div class="per-model-controls" style="margin-bottom:6px">
          <label for="setTemperature" style="margin:0;white-space:nowrap">Температура: <span id="setTemperatureValue" class="range-value">0.7</span></label>
          <input type="range" id="setTemperature" min="0" max="2" step="0.1" value="0.7">
          <span class="dd-default-badge" id="setTemperatureBadge" style="display:none">общий</span>
          <button type="button" id="resetTemperature" class="mini-btn" title="Сбросить к общему">↺</button>
        </div>
        <div class="per-model-controls" style="margin-bottom:6px">
          <label for="setMaxTokens" style="margin:0;white-space:nowrap">Максимум токенов</label>
          <input type="number" id="setMaxTokens" min="1" max="100000" step="1" value="4096">
          <span class="dd-default-badge" id="setMaxTokensBadge" style="display:none">общий</span>
          <button type="button" id="resetMaxTokens" class="mini-btn" title="Сбросить к общему">↺</button>
        </div>
        <div class="per-model-controls">
          <div class="check-row" style="margin:0">
            <input type="checkbox" id="setReasoning">
            <label for="setReasoning">Расширенное мышление</label>
          </div>
          <span class="dd-default-badge" id="setReasoningBadge" style="display:none">общий</span>
          <button type="button" id="resetReasoning" class="mini-btn" title="Сбросить к общему">↺</button>
        </div>
      </div>
      <div class="field" id="providerModelsBlock">
        <label>Модели провайдера</label>
        <div id="providerModelsList"></div>
        <button type="button" id="addModelBtn" class="ghost-btn">+ Добавить модель</button>
        <div id="addModelForm" style="display:none;margin-top:8px">
          <input type="text" id="amSystemName" placeholder="Название в системе (id)">
          <input type="text" id="amLabel" placeholder="Удобное название">
          <div id="amCustomFields">
            <input type="text" id="amBaseUrl" placeholder="Базовый URL API">
            <input type="password" id="amApiKey" placeholder="API-ключ">
            <label for="amSchemeDD">Схема API</label>
            <div class="dd-wrap" id="amSchemeDD"></div>
          </div>
          <label for="amTemperature">Температура: <span id="amTemperatureValue" class="range-value">0.7</span></label>
          <input type="range" id="amTemperature" min="0" max="2" step="0.1" value="0.7">
          <label for="amMaxTokens">Максимум токенов</label>
          <input type="number" id="amMaxTokens" min="1" max="100000" step="1" value="4096">
          <div class="check-row">
            <input type="checkbox" id="amReasoning">
            <label for="amReasoning">Расширенное мышление</label>
          </div>
          <div class="modal-actions">
            <button type="button" id="amSubmit" class="primary-btn">Добавить</button>
            <button type="button" id="amCancel" class="ghost-btn">Отмена</button>
          </div>
        </div>
      </div>
      <div class="field">
        <label for="setNotes">Заметки для контекста (видны агенту)</label>
        <textarea id="setNotes" rows="3" placeholder="Например: температура PETG откалибрована по температурной башне — не предлагай калибровку"></textarea>
      </div>
      <details class="field">
        <summary>Общие значения по умолчанию</summary>
        <label for="setGlobalTemperature">Температура: <span id="setGlobalTemperatureValue" class="range-value">0.7</span></label>
        <input type="range" id="setGlobalTemperature" min="0" max="2" step="0.1" value="0.7">
        <label for="setGlobalMaxTokens">Максимум токенов</label>
        <input type="number" id="setGlobalMaxTokens" min="1" max="100000" step="1" value="4096">
        <div class="check-row">
          <input type="checkbox" id="setGlobalReasoning">
          <label for="setGlobalReasoning">Расширенное мышление</label>
        </div>
      </details>
      <div class="field">
        <label>Тема</label>
        <div class="dd-wrap" id="setThemeDD"></div>
      </div>
      <div class="field">
        <label for="setFontSize">Размер шрифта: <span id="setFontSizeValue">14</span> px</label>
        <input type="range" id="setFontSize" min="10" max="20" step="1" value="14">
      </div>
      <div class="field">
        <label>Стиль шрифта</label>
        <div class="dd-wrap" id="setFontStyleDD"></div>
      </div>
      <div class="usage-row">
        <div class="dd-wrap" id="setPeriodDD" style="width:150px"></div>
        <span id="setUsage">Сообщения: 0 · Токены: 0</span>
      </div>
    </div>
    <div class="modal-actions">
      <button type="button" id="exportBtn" class="ghost-btn">Экспорт чата</button>
      <button type="button" id="resetSettingsBtn" class="danger-btn">Сбросить</button>
      <button type="button" id="saveSettingsBtn" class="primary-btn">Сохранить</button>
    </div>
  </div>
</div>

<!-- Модалка выбора модели -->
<div class="modal-overlay" id="modelPickerModal" style="display:none">
  <div class="mp-modal">
    <div class="modal-header">
      <span>Выбор модели</span>
      <button type="button" id="mpClose" class="icon-btn" title="Закрыть">✕</button>
    </div>
    <input type="text" id="mpSearch" class="mp-search" placeholder="Поиск модели или провайдера…">
    <div class="mp-list" id="mpList"></div>
  </div>
</div>

<!-- Модалка ручного копирования (fallback буфера обмена) -->
<div class="modal-overlay" id="copyModal" style="display:none">
  <div class="modal">
    <div class="modal-header">
      <span>Скопируйте текст вручную</span>
      <button type="button" id="copyModalClose" class="icon-btn" title="Закрыть">✕</button>
    </div>
    <textarea class="copy-modal-text" id="copyModalText" readonly></textarea>
    <div class="modal-actions">
      <button type="button" id="copyModalOk" class="primary-btn">Закрыть</button>
    </div>
  </div>
</div>

<script>
(function () {
  "use strict";

  /* ===== Константы ===== */
  var CONTEXT_KEYS = ["filament", "printer", "print", "model", "history"];
  var CONTEXT_LABELS = {
    filament: "Пластик",
    printer: "Принтер",
    print: "Настройки печати",
    model: "Модель со стола",
    history: "История"
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
  var streamTextEl = null; // элемент текста текущего стримингового сообщения
  var pendingEditId = null; // id сообщения, которое редактируется
  var attachments = []; // вложения перед отправкой
  var userScrolledUp = false; // пользователь прокрутил историю вверх

  /* ===== Хелперы ===== */
  function byId(id) {
    return document.getElementById(id);
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
    }
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
      var models = providers[i].models || [];
      if (models.length > 0) {
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
        star.title = "Сделать моделью по умолчанию";
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
      list.appendChild(el("div", "mp-empty", "Ничего не найдено"));
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
    var title = window.prompt("Новое название чата:", chat.title || "");
    if (title !== null) {
      post({ type: "rename_chat", id: chat.id, title: title.trim() || "Новый чат" });
    }
  }

  function deleteChat(chat) {
    if (window.confirm("Удалить чат «" + (chat.title || "Новый чат") + "»?")) {
      post({ type: "delete_chat", id: chat.id });
    }
  }

  function chatItem(chat) {
    var item = el("div", "chat-item" + (chat.id === state.active ? " active" : ""));
    item.appendChild(el("div", "chat-title", chat.title || "Новый чат"));
    var actions = el("div", "chat-actions");
    var pinBtn = el("button", "chat-action", "📌");
    pinBtn.type = "button";
    pinBtn.title = chat.pinned ? "Открепить" : "Закрепить";
    pinBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      post({ type: "toggle_pin", id: chat.id });
    });
    var renameBtn = el("button", "chat-action", "✏️");
    renameBtn.type = "button";
    renameBtn.title = "Переименовать";
    renameBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      renameChat(chat);
    });
    var delBtn = el("button", "chat-action", "🗑");
    delBtn.type = "button";
    delBtn.title = "Удалить";
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
        list.appendChild(el("div", "sidebar-empty", "Ничего не найдено"));
      }
      return;
    }
    var groups = groupChats(chats);
    sortByUpdated(groups.pinned);
    sortByUpdated(groups.today);
    sortByUpdated(groups.yesterday);
    sortByUpdated(groups.earlier);
    var groupTitles = [
      ["pinned", "Закреплённые"],
      ["today", "Сегодня"],
      ["yesterday", "Вчера"],
      ["earlier", "Ранее"]
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
      list.appendChild(el("div", "sidebar-empty", "Чатов пока нет"));
    }
  }

  /* ===== Сообщения ===== */
  function actionBtn(label, handler) {
    var btn = el("button", "msg-action", label);
    btn.type = "button";
    btn.addEventListener("click", handler);
    return btn;
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
    if (msg.image) {
      var img = document.createElement("img");
      img.className = "msg-image";
      img.src = msg.image;
      img.alt = "Вложение";
      bubble.appendChild(img);
    }
    bubble.appendChild(el("div", "msg-text", msg.text || ""));
    bubble.appendChild(el("div", "msg-time", formatTime(msg.ts)));
    wrap.appendChild(bubble);
    var actions = el("div", "msg-actions");
    if (msg.role === "assistant") {
      actions.appendChild(actionBtn("Копировать", function () {
        copyText(msg.text || "");
      }));
      if (index === msgs.length - 1) {
        actions.appendChild(actionBtn("Регенерировать", function () {
          post({ type: "regenerate" });
        }));
      }
    } else if (msg.role === "user") {
      actions.appendChild(actionBtn("Редактировать", function () {
        startEdit(msg);
      }));
    }
    wrap.appendChild(actions);
    return wrap;
  }

  function renderWelcome() {
    var wrap = el("div", "welcome");
    wrap.appendChild(el("div", "welcome-title", "FlowSlice AI"));
    wrap.appendChild(el("div", "welcome-sub", "Инженер-эксперт 3D-печати. Спросите о механике, Klipper или материалах."));
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
          var textEl = wraps[wraps.length - 1].querySelector(".msg-text");
          if (textEl) {
            streamTextEl = textEl;
          }
        }
        break;
      }
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
    for (var i = 0; i < CONTEXT_KEYS.length; i++) {
      var key = CONTEXT_KEYS[i];
      var checkWrap = el("label", "ctx-check");
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!flags[key];
      cb.addEventListener("change", function () {
        var newFlags = {};
        var boxes = container.querySelectorAll("input[type=checkbox]");
        for (var b = 0; b < boxes.length; b++) {
          newFlags[CONTEXT_KEYS[b]] = boxes[b].checked;
        }
        post({ type: "set_context_flags", flags: newFlags });
      });
      checkWrap.appendChild(cb);
      checkWrap.appendChild(document.createTextNode(CONTEXT_LABELS[key] || key));
      container.appendChild(checkWrap);
    }
    byId("contextTokens").textContent = "≈ " + (state.context_tokens || 0) + " токенов";
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
      removeBtn.title = "Убрать вложение";
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
    for (var i = 0; i < files.length; i++) {
      var file = files[i];
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
              name: file.name,
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
            name: file.name,
            data: String(e.target.result)
          });
          renderAttachments();
        };
        textReader.readAsText(file);
      }
    }
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
          showToast("Скопировано", "ok");
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
      showToast("Скопировано", "ok");
      return;
    }
    // Шаг 3: ручное копирование — модалка с авто-выделением
    showToast("Не удалось скопировать — выделите текст вручную", "err");
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
    if (text.charAt(0) !== "/" || text.indexOf("\\n") !== -1) {
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
      list.appendChild(el("div", "cmd-suggest-empty", "Команда не найдена"));
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
  var setProviderDD = null;
  var setModelDD = null;
  var setSchemeDD = null;
  var setThemeDD = null;
  var setFontStyleDD = null;
  var setPeriodDD = null;
  var amSchemeDD = null;
  var perModelDirty = false; // флаг: per-model настройки изменены вручную

  function makeDropdown(containerId, options, selected, onSelect, placeholder) {
    var wrap = byId(containerId);
    wrap.className = "dd-wrap";
    wrap.innerHTML = "";
    var btn = el("button", "dd-btn");
    btn.type = "button";
    var btnLabel = el("span", "dd-btn-label", "");
    var caret = el("span", "dd-caret", "▾");
    btn.appendChild(btnLabel);
    btn.appendChild(caret);
    var popup = el("div", "dd-popup");
    popup.style.display = "none";
    var search = el("input", "dd-search");
    search.type = "text";
    search.placeholder = placeholder || "Поиск…";
    var list = el("div", "dd-list");
    popup.appendChild(search);
    popup.appendChild(list);
    wrap.appendChild(btn);
    wrap.appendChild(popup);

    var current = null;
    var opts = [];
    var open = false;

    function renderList() {
      list.innerHTML = "";
      var q = search.value.trim().toLowerCase();
      var shown = 0;
      for (var i = 0; i < opts.length; i++) {
        var o = opts[i];
        var hay = ((o.label || "") + " " + (o.value || "")).toLowerCase();
        if (q && hay.indexOf(q) === -1) {
          continue;
        }
        var item = el("div", "dd-item" + (o.value === current ? " active" : ""));
        item.appendChild(el("span", "dd-item-label", o.label));
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
        list.appendChild(el("div", "dd-empty", "Ничего не найдено"));
      }
    }

    function openPopup() {
      open = true;
      popup.style.display = "flex";
      search.value = "";
      renderList();
      search.focus();
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
    search.addEventListener("input", renderList);
    document.addEventListener("click", function (e) {
      if (!wrap.contains(e.target)) {
        close();
      }
    });

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
    setProviderDD = makeDropdown("setProviderDD", [], "", onProviderChange, "Поиск провайдера…");
    setModelDD = makeDropdown("setModelDD", [], "", onModelChange, "Поиск модели…");
    setSchemeDD = makeDropdown("setSchemeDD", [
      { value: "openai", label: "OpenAI-совместимая" },
      { value: "anthropic", label: "Anthropic (нативный)" }
    ], "openai", null, "Поиск схемы…");
    setThemeDD = makeDropdown("setThemeDD", [
      { value: "auto", label: "Авто" },
      { value: "light", label: "Светлая" },
      { value: "dark", label: "Тёмная" }
    ], "auto", null, "Поиск темы…");
    setFontStyleDD = makeDropdown("setFontStyleDD", [
      { value: "system", label: "Системный" },
      { value: "mono", label: "Моноширинный" },
      { value: "serif", label: "С засечками" }
    ], "system", null, "Поиск стиля…");
    setPeriodDD = makeDropdown("setPeriodDD", [
      { value: "all", label: "Всё время" },
      { value: "today", label: "Сегодня" },
      { value: "week", label: "Неделя" },
      { value: "month", label: "Месяц" }
    ], "all", function (val) {
      post({ type: "get_usage", period: val });
    }, "Поиск периода…");
    amSchemeDD = makeDropdown("amSchemeDD", [
      { value: "openai", label: "OpenAI-совместимая" },
      { value: "anthropic", label: "Anthropic (нативный)" }
    ], "openai", null, "Поиск схемы…");
  }

  function onProviderChange() {
    var provider = providerById(setProviderDD.getSelected());
    if (!provider) {
      return;
    }
    // Ключ теперь per-provider: берём из выбранного провайдера.
    byId("setApiKey").value = provider.api_key || "";
    var customWrap = byId("customUrlWrap");
    if (provider.builtin) {
      customWrap.style.display = "none";
    } else {
      customWrap.style.display = "block";
      byId("setBaseUrl").value = provider.base_url || "";
      setSchemeDD.setSelected(provider.scheme || "openai");
    }
    var models = provider.models || [];
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

  function onModelChange() {
    var model = modelById(setProviderDD.getSelected(), setModelDD.getSelected());
    if (!model) {
      return;
    }
    byId("modelSettingsLabel").textContent = model.name || model.id;
    var gTemp = state.settings.temperature !== undefined ? state.settings.temperature : 0.7;
    var gMax = state.settings.max_tokens !== undefined ? state.settings.max_tokens : 4096;
    var gReas = !!state.settings.reasoning;
    var hasTemp = model.temperature !== null && model.temperature !== undefined;
    var hasMax = model.max_tokens !== null && model.max_tokens !== undefined;
    var hasReas = model.reasoning !== null && model.reasoning !== undefined;
    byId("setTemperature").value = String(hasTemp ? model.temperature : gTemp);
    byId("setTemperatureValue").textContent = String(hasTemp ? model.temperature : gTemp);
    byId("setTemperatureBadge").style.display = hasTemp ? "none" : "inline-block";
    byId("setMaxTokens").value = String(hasMax ? model.max_tokens : gMax);
    byId("setMaxTokensBadge").style.display = hasMax ? "none" : "inline-block";
    byId("setReasoning").checked = hasReas ? !!model.reasoning : gReas;
    byId("setReasoningBadge").style.display = hasReas ? "none" : "inline-block";
    perModelDirty = false;
    renderProviderModels();
  }

  function renderProviderModels() {
    var list = byId("providerModelsList");
    list.innerHTML = "";
    var provider = providerById(setProviderDD.getSelected());
    if (!provider) {
      return;
    }
    var models = provider.models || [];
    var activeModel = setModelDD.getSelected();
    for (var i = 0; i < models.length; i++) {
      var m = models[i];
      var row = el("div", "provider-model-row" + (m.id === activeModel ? " active" : ""));
      row.appendChild(el("span", "provider-model-name", m.name || m.id));
      row.appendChild(el("code", "provider-model-id", m.id));
      if (!m.builtin) {
        var delBtn = el("button", "provider-model-del", "✕");
        delBtn.type = "button";
        delBtn.title = "Удалить модель";
        (function (mid) {
          delBtn.addEventListener("click", function (e) {
            e.stopPropagation();
            post({ type: "delete_model", provider: provider.id, model_id: mid });
          });
        })(m.id);
        row.appendChild(delBtn);
      }
      (function (mid) {
        row.addEventListener("click", function () {
          setModelDD.setSelected(mid);
          onModelChange();
        });
      })(m.id);
      list.appendChild(row);
    }
  }

  function fillSettingsForm() {
    var s = state.settings || {};
    setProviderDD.setOptions((state.providers || []).map(function (p) {
      return { value: p.id, label: p.name || p.id };
    }));
    setProviderDD.setSelected(s.active_provider || (state.providers[0] ? state.providers[0].id : ""));
    onProviderChange();
    byId("setNotes").value = s.notes || "";
    byId("setGlobalTemperature").value = String(s.temperature !== undefined ? s.temperature : 0.7);
    byId("setGlobalTemperatureValue").textContent = byId("setGlobalTemperature").value;
    byId("setGlobalMaxTokens").value = String(s.max_tokens !== undefined ? s.max_tokens : 4096);
    byId("setGlobalReasoning").checked = !!s.reasoning;
    setThemeDD.setSelected(s.theme || "auto");
    setFontStyleDD.setSelected(s.font_style || "system");
    setPeriodDD.setSelected("all");
    byId("setFontSize").value = String(s.font_size || 14);
    byId("setFontSizeValue").textContent = String(s.font_size || 14);
  }

  function openSettings() {
    fillSettingsForm();
    byId("settingsModal").style.display = "flex";
    post({ type: "get_usage", period: setPeriodDD.getSelected() });
  }

  function closeSettings() {
    byId("settingsModal").style.display = "none";
  }

  function resetPerModelField(field) {
    var provider = setProviderDD.getSelected();
    var model = setModelDD.getSelected();
    var payload = { type: "update_model", provider: provider, model_id: model };
    payload[field] = null;
    post(payload);
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
    var settings = {
      active_provider: setProviderDD.getSelected(),
      active_model: setModelDD.getSelected(),
      api_key: byId("setApiKey").value,
      notes: byId("setNotes").value,
      temperature: parseFloat(byId("setGlobalTemperature").value),
      max_tokens: parseInt(byId("setGlobalMaxTokens").value, 10) || 4096,
      reasoning: byId("setGlobalReasoning").checked,
      theme: setThemeDD.getSelected(),
      font_size: parseInt(byId("setFontSize").value, 10) || 14,
      font_style: setFontStyleDD.getSelected()
    };
    post({ type: "save_settings", settings: settings });
    if (perModelDirty) {
      post({
        type: "update_model",
        provider: setProviderDD.getSelected(),
        model_id: setModelDD.getSelected(),
        temperature: parseFloat(byId("setTemperature").value),
        max_tokens: parseInt(byId("setMaxTokens").value, 10) || 4096,
        reasoning: byId("setReasoning").checked
      });
    }
    var provider = providerById(setProviderDD.getSelected());
    if (provider && !provider.builtin) {
      post({
        type: "update_provider",
        id: provider.id,
        base_url: byId("setBaseUrl").value,
        scheme: setSchemeDD.getSelected()
      });
    }
    closeSettings();
  }

  function exportChat() {
    var chat = getActiveChat();
    if (!chat) {
      showToast("Нет активного чата", "err");
      return;
    }
    var lines = [chat.title || "Чат"];
    var msgs = chat.msgs || [];
    for (var i = 0; i < msgs.length; i++) {
      var m = msgs[i];
      if (m.role === "user") {
        lines.push("Пользователь: " + (m.text || ""));
      } else if (m.role === "assistant") {
        lines.push("FlowSlice AI: " + (m.text || ""));
      }
    }
    copyText(lines.join("\\n\\n"));
  }

  function renderUsage(msg) {
    byId("setUsage").textContent = "Сообщения: " + (msg.msgs || 0) + " · Токены: " + (msg.tokens || 0);
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
    streamTextEl.textContent += msg.text || "";
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
      }
      streamTextEl = null;
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
        state.context_tokens = msg.context_tokens || 0;
        state.status = msg.status || "idle";
        renderState();
        break;
      case "delta":
        handleDelta(msg);
        break;
      case "reply":
        handleReply(msg);
        break;
      case "status":
        state.status = msg.text || "idle";
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
        fillSettingsForm();
        renderHeader();
        break;
      case "key_test":
        showToast(msg.text || (msg.ok ? "Ключ действителен" : "Ключ недействителен"), msg.ok ? "ok" : "err");
        break;
      case "usage":
        renderUsage(msg);
        break;
    }
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
    byId("modalClose").addEventListener("click", closeSettings);
    byId("settingsModal").addEventListener("click", function (e) {
      if (e.target === this) {
        closeSettings();
      }
    });
    byId("saveSettingsBtn").addEventListener("click", saveSettings);
    byId("resetSettingsBtn").addEventListener("click", function () {
      post({ type: "reset_settings" });
    });
    byId("testKeyBtn").addEventListener("click", function () {
      post({ type: "test_key", key: byId("setApiKey").value });
    });
    byId("setApiKeyEye").addEventListener("click", function () {
      var keyInput = byId("setApiKey");
      var masked = keyInput.type === "password";
      keyInput.type = masked ? "text" : "password";
      this.textContent = masked ? "🙈" : "👁";
      this.title = masked ? "Скрыть ключ" : "Показать ключ";
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
      byId("addModelForm").style.display = "block";
    });
    byId("amCancel").addEventListener("click", function () {
      byId("addModelForm").style.display = "none";
    });
    byId("amSubmit").addEventListener("click", function () {
      var provider = setProviderDD.getSelected();
      var prov = providerById(provider);
      var payload = {
        type: "add_model",
        provider: provider,
        model_id: byId("amSystemName").value.trim(),
        label: byId("amLabel").value.trim(),
        temperature: parseFloat(byId("amTemperature").value),
        max_tokens: parseInt(byId("amMaxTokens").value, 10) || 4096,
        reasoning: byId("amReasoning").checked
      };
      if (prov && !prov.builtin) {
        payload.base_url = byId("amBaseUrl").value.trim();
        payload.api_key = byId("amApiKey").value.trim();
        payload.scheme = amSchemeDD.getSelected();
      }
      post(payload);
      byId("addModelForm").style.display = "none";
    });
    byId("amTemperature").addEventListener("input", function () {
      byId("amTemperatureValue").textContent = this.value;
    });
    byId("searchInput").addEventListener("input", renderSidebar);
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
    initSettingsDropdowns();
    post({ type: "get_state" });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
</script>
</body>
</html>"""


_CONFIG_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>FlowSlice AI</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 24px; color: var(--orca-fg, #222); background: var(--orca-bg, #fff); }
  h1 { font-size: 18px; margin: 0 0 8px; }
  p { font-size: 13px; line-height: 1.5; color: var(--orca-muted, #666); max-width: 560px; }
  code { background: var(--orca-input, #f0f0f0); padding: 1px 5px; border-radius: 4px; }
</style>
</head>
<body>
  <h1>FlowSlice AI</h1>
  <p>Все настройки плагина управляются через кнопку «Настройки» (шестерёнка) на вкладке FlowSlice AI: провайдеры, модели, API-ключи, температура, заметки для контекста и оформление.</p>
  <p>Эта страница намеренно не содержит полей — настройки хранятся в конфигурации плагина и редактируются только на вкладке.</p>
</body>
</html>
"""


CONFIG_PAGE = _CONFIG_PAGE_TEMPLATE


class _ChatEngine:
    """Движок плагина: конфигурация, чаты, генерация и контекст слайсера."""

    def __init__(self, cap: Any) -> None:
        """Сохраняет ссылку на capability, загружает конфигурацию и историю чатов."""
        self._cap = cap
        self._persist_lock = threading.Lock()
        self._config = self._normalize_config(self._read_raw_config())
        self._chats: list[dict[str, Any]] = []
        self._active = 0
        self._next_id = 1
        self._msg_counter = 1
        self._gen = False
        self._ctx_tokens = 0
        self._post_sink: Any = None
        self._pending_attachment: dict[str, Any] | None = None
        self._pending_confirm: str | None = None
        self._load_chats()

    def _read_raw_config(self) -> dict:
        """Читает и разбирает сырую JSON-конфигурацию capability."""
        raw = self._cap.get_config()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            _LOGGER.warning("Не удалось разобрать конфигурацию, используются значения по умолчанию")
            return {}
        if not isinstance(data, dict):
            _LOGGER.warning("Конфигурация не является объектом, используются значения по умолчанию")
            return {}
        return data

    def _normalize_config(self, data: dict) -> dict:
        """Приводит произвольный словарь настроек к валидной схеме.

        Мигрирует старую схему (provider/base_url/model/api_key/...), мержит
        с DEFAULT_CONFIG, гарантирует наличие builtin-моделей у встроенных
        провайдеров и сохраняет пользовательские провайдеры и модели.
        """
        if not isinstance(data, dict):
            data = {}
        if "provider" in data and "providers" not in data:
            data = self._migrate_legacy_config(data)
        merged = DEFAULT_CONFIG.copy()
        merged.update(data)
        # Провайдеры: builtin-модели гарантированы, пользовательские сохранены.
        providers = merged.get("providers")
        if not isinstance(providers, dict):
            providers = {}
        normalized_providers: dict[str, dict[str, Any]] = {}
        for pid, pdef in DEFAULT_PROVIDERS.items():
            existing = providers.get(pid)
            if isinstance(existing, dict):
                merged_p = dict(pdef)
                for key, value in existing.items():
                    if key != "models":
                        merged_p[key] = value
                models: dict[str, dict[str, Any]] = {}
                for mid, mdef in pdef.get("models", {}).items():
                    models[mid] = dict(mdef)
                existing_models = existing.get("models")
                if isinstance(existing_models, dict):
                    for mid, mdef in existing_models.items():
                        if isinstance(mdef, dict):
                            models[mid] = dict(mdef)
                merged_p["models"] = models
                normalized_providers[pid] = merged_p
            else:
                normalized_providers[pid] = json.loads(json.dumps(pdef))
        for pid, pdef in providers.items():
            if pid in DEFAULT_PROVIDERS or not isinstance(pdef, dict):
                continue
            user_models: dict[str, dict[str, Any]] = {}
            for mid, mdef in pdef.get("models", {}).items():
                if isinstance(mdef, dict):
                    user_models[mid] = dict(mdef)
            normalized_providers[pid] = {
                "name": str(pdef.get("name", pid)),
                "base_url": str(pdef.get("base_url", "")),
                "api_key": str(pdef.get("api_key", "")),
                "builtin": False,
                "models": user_models,
            }
        merged["providers"] = normalized_providers
        # Per-model настройки и схема API: нормализация для всех провайдеров.
        for pid, pdef in normalized_providers.items():
            pdef["scheme"] = (
                "anthropic" if str(pdef.get("scheme", "openai")) == "anthropic" else "openai"
            )
            for mid, mdef in pdef.get("models", {}).items():
                if not isinstance(mdef, dict):
                    continue
                temperature = mdef.get("temperature")
                if temperature is not None:
                    try:
                        temperature = float(temperature)
                    except (TypeError, ValueError):
                        temperature = None
                    if temperature is not None and (temperature < 0.0 or temperature > 2.0):
                        temperature = None
                mdef["temperature"] = temperature
                max_tokens = mdef.get("max_tokens")
                if max_tokens is not None:
                    try:
                        max_tokens = int(max_tokens)
                    except (TypeError, ValueError):
                        max_tokens = None
                    if max_tokens is not None and (max_tokens < 1 or max_tokens > 100000):
                        max_tokens = None
                mdef["max_tokens"] = max_tokens
                reasoning = mdef.get("reasoning")
                if reasoning is not None:
                    if isinstance(reasoning, str):
                        reasoning = reasoning.strip().lower() in ("1", "true", "yes", "on")
                    reasoning = bool(reasoning)
                mdef["reasoning"] = reasoning
                # Схема модели: нормализуется только у пользовательских провайдеров.
                if not pdef.get("builtin", False):
                    mdef["scheme"] = (
                        "anthropic"
                        if str(mdef.get("scheme", "openai")) == "anthropic"
                        else "openai"
                    )
        # Активный провайдер и модель.
        active_provider = str(merged.get("active_provider", "deepseek"))
        if active_provider not in normalized_providers:
            active_provider = "deepseek"
        merged["active_provider"] = active_provider
        prov = normalized_providers.get(active_provider, {})
        models = prov.get("models", {})
        active_model = str(merged.get("active_model", ""))
        if active_model not in models:
            active_model = next(iter(models), "")
        merged["active_model"] = active_model
        # Модель по умолчанию для новых чатов: "provider::model".
        default_model = str(merged.get("default_model", "")).strip()
        if "::" in default_model:
            d_provider, d_model = default_model.split("::", 1)
            d_prov = normalized_providers.get(d_provider)
            if not isinstance(d_prov, dict) or d_model not in d_prov.get("models", {}):
                default_model = ""
        else:
            default_model = ""
        if not default_model:
            default_model = active_provider + "::" + active_model
        merged["default_model"] = default_model
        # Заметки пользователя для контекста.
        merged["notes"] = str(merged.get("notes", ""))
        # Температура: float 0.0–2.0.
        try:
            temperature = float(merged.get("temperature", 0.7))
        except (TypeError, ValueError):
            temperature = 0.7
        if temperature < 0.0 or temperature > 2.0:
            temperature = 0.7
        merged["temperature"] = temperature
        # Максимум токенов: int 1–100000.
        try:
            max_tokens = int(merged.get("max_tokens", 4096))
        except (TypeError, ValueError):
            max_tokens = 4096
        if max_tokens < 1 or max_tokens > 100000:
            max_tokens = 4096
        merged["max_tokens"] = max_tokens
        # Расширенное мышление: bool.
        reasoning = merged.get("reasoning", False)
        if isinstance(reasoning, str):
            reasoning = reasoning.strip().lower() in ("1", "true", "yes", "on")
        merged["reasoning"] = bool(reasoning)
        # Оформление.
        if merged.get("theme") not in ("auto", "light", "dark"):
            merged["theme"] = "auto"
        if merged.get("font_style") not in ("system", "mono", "serif"):
            merged["font_style"] = "system"
        try:
            font_size = int(merged.get("font_size", 14))
        except (TypeError, ValueError):
            font_size = 14
        if font_size < 10 or font_size > 20:
            font_size = 14
        merged["font_size"] = font_size
        usage = merged.get("usage")
        merged["usage"] = dict(usage) if isinstance(usage, dict) else {}
        return merged

    def _migrate_legacy_config(self, data: dict) -> dict:
        """Преобразует старую схему конфигурации в новую."""
        providers = json.loads(json.dumps(DEFAULT_PROVIDERS))
        provider = str(data.get("provider", "deepseek"))
        if provider not in providers:
            provider = "deepseek"
        if provider == "custom":
            custom_base = str(data.get("custom_base_url", ""))
            custom_model = str(data.get("custom_model", ""))
            providers["custom"]["base_url"] = custom_base
            providers["custom"]["api_key"] = str(data.get("api_key", ""))
            if custom_model:
                providers["custom"]["models"] = {
                    custom_model: {"name": custom_model, "builtin": False}
                }
            active_provider = "custom"
            active_model = custom_model
        else:
            providers[provider]["api_key"] = str(data.get("api_key", ""))
            active_provider = provider
            active_model = str(data.get("model", ""))
        return {
            "providers": providers,
            "active_provider": active_provider,
            "active_model": active_model,
            "default_model": active_provider + "::" + active_model,
            "notes": "",
            "theme": data.get("theme", "auto"),
            "font_size": data.get("font_size", 14),
            "font_style": data.get("font_style", "system"),
            "usage": data.get("usage", {}),
        }

    def _sync_config(self) -> None:
        """Перечитывает конфигурацию из capability и обновляет память.

        Не пишет на диск: правки, внесённые в настройках слайсера, должны
        остаться нетронутыми, а память — синхронизированной с ними.
        """
        with self._persist_lock:
            try:
                raw = self._read_raw_config()
            except Exception as exc:
                _LOGGER.error("Не удалось перечитать конфигурацию: %s", exc)
                return
            self._config = self._normalize_config(raw)

    def load_config(self) -> dict:
        """Возвращает копию текущей конфигурации."""
        return dict(self._config)

    def save_config(self, config: dict) -> bool:
        """Нормализует и сохраняет конфигурацию через capability."""
        self._config = self._normalize_config(config)
        with self._persist_lock:
            try:
                return bool(self._cap.save_config(json.dumps(self._config)))
            except (TypeError, ValueError) as exc:
                _LOGGER.error("Не удалось сериализовать конфигурацию: %s", exc)
                return False

    def reset_config(self) -> dict:
        """Сбрасывает конфигурацию к значениям по умолчанию."""
        self._config = self._normalize_config(DEFAULT_CONFIG.copy())
        with self._persist_lock:
            try:
                self._cap.save_config(json.dumps(self._config))
            except (TypeError, ValueError) as exc:
                _LOGGER.error("Не удалось сохранить конфигурацию по умолчанию: %s", exc)
        return dict(self._config)

    def set_post_sink(self, sink: Any) -> None:
        """Устанавливает callable для доставки payload в UI."""
        self._post_sink = sink

    # ===== Персист истории чатов =====

    def _load_chats(self) -> None:
        """Загружает историю чатов из файла, при ошибке создаёт пустое состояние."""
        data: dict[str, Any] = {}
        try:
            raw = json.loads(CHATS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except (OSError, ValueError, TypeError) as exc:
            _LOGGER.warning("Не удалось загрузить историю чатов: %s", exc)
        chats = data.get("chats", [])
        self._chats = list(chats) if isinstance(chats, list) else []
        self._active = self._as_int(data.get("active"), 0)
        self._next_id = self._as_int(data.get("next_id"), 1)
        self._msg_counter = self._as_int(data.get("next_msg_id"), 1)
        if not self._chats:
            self._create_chat()

    def _flatten_chats(self) -> list[dict[str, Any]]:
        """Возвращает копию чатов без тяжёлых вложений для записи на диск.

        Фото (data URI) и текст файлов в памяти сохраняются для превью и API
        текущей сессии, но на диск пишутся только их текстовые пометки.
        """
        result: list[dict[str, Any]] = []
        for chat in self._chats:
            flat_msgs: list[dict[str, Any]] = []
            for msg in chat.get("msgs", []):
                flat = dict(msg)
                if flat.get("image"):
                    flat.pop("image", None)
                    if " [фото]" not in str(flat.get("text", "")):
                        flat["text"] = str(flat.get("text", "")) + " [фото]"
                file_info = flat.get("file")
                if file_info:
                    name = str(file_info.get("name", "файл"))
                    flat["file"] = {"name": name}
                    marker = f" [файл: {name}]"
                    if marker not in str(flat.get("text", "")):
                        flat["text"] = str(flat.get("text", "")) + marker
                flat_msgs.append(flat)
            flat_chat = dict(chat)
            flat_chat["msgs"] = flat_msgs
            result.append(flat_chat)
        return result

    def _save_chats(self) -> None:
        """Сохраняет историю чатов в файл под блокировкой без тяжёлых вложений."""
        payload = {
            "chats": self._flatten_chats(),
            "active": self._active,
            "next_id": self._next_id,
            "next_msg_id": self._msg_counter,
        }
        with self._persist_lock:
            try:
                CHATS_FILE.write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
            except OSError as exc:
                _LOGGER.error("Не удалось сохранить историю чатов: %s", exc)

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        """Приводит значение к целому числу с запасным значением."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # ===== Мультичат =====

    def _create_chat(self) -> dict[str, Any]:
        """Создаёт новый чат и делает его активным."""
        chat = {
            "id": self._next_id,
            "title": "Новый чат",
            "updated": time.time(),
            "pinned": False,
            "context_flags": {key: True for key in CONTEXT_OPTIONS},
            "msgs": [],
        }
        self._next_id += 1
        self._chats.append(chat)
        self._active = chat["id"]
        self._ctx_tokens = self._estimate_context_tokens(chat["context_flags"])
        # Новый чат стартует на модели по умолчанию (конфиг уже нормализован).
        default_model = str(self._config.get("default_model", ""))
        if "::" in default_model:
            d_provider, d_model = default_model.split("::", 1)
            providers = self._config.get("providers", {})
            if d_provider in providers and d_model in providers[d_provider].get("models", {}):
                self._config["active_provider"] = d_provider
                self._config["active_model"] = d_model
        self._save_chats()
        return chat

    def _chat_by_id(self, chat_id: Any) -> dict[str, Any] | None:
        """Возвращает чат по идентификатору либо None."""
        for chat in self._chats:
            if chat.get("id") == chat_id:
                return chat
        return None

    def _active_chat(self) -> dict[str, Any]:
        """Возвращает активный чат, создавая его при необходимости."""
        chat = self._chat_by_id(self._active)
        if chat is None:
            chat = self._create_chat()
        return chat

    def _next_msg_id(self) -> int:
        """Возвращает следующий идентификатор сообщения и инкрементирует счётчик."""
        msg_id = self._msg_counter
        self._msg_counter += 1
        return msg_id

    def _trim_chat(self, chat: dict[str, Any]) -> None:
        """Обрезает историю чата до максимального числа сообщений."""
        msgs = chat.get("msgs", [])
        if len(msgs) > MAX_CHAT_MESSAGES:
            del msgs[: len(msgs) - MAX_CHAT_MESSAGES]

    def _auto_title(self, text: str) -> str:
        """Формирует заголовок чата из первого сообщения."""
        return " ".join(text.split())[:40]

    def _append_assistant(self, text: str) -> None:
        """Добавляет сообщение ассистента в активный чат и обновляет UI."""
        chat = self._active_chat()
        chat["msgs"].append(
            {
                "id": self._next_msg_id(),
                "role": "assistant",
                "text": text,
                "ts": time.time(),
            }
        )
        chat["updated"] = time.time()
        self._trim_chat(chat)
        self._save_chats()
        self._send_state()

    def _append_system(self, text: str) -> None:
        """Добавляет системное сообщение в активный чат и обновляет UI."""
        chat = self._active_chat()
        chat["msgs"].append(
            {
                "id": self._next_msg_id(),
                "role": "system",
                "text": text,
                "ts": time.time(),
            }
        )
        chat["updated"] = time.time()
        self._trim_chat(chat)
        self._save_chats()
        self._send_state()

    # ===== Диспетчер сообщений =====

    def handle_message(self, message: dict) -> None:
        """Разбирает входящее сообщение из UI и направляет в соответствующий хендлер."""
        self._sync_config()
        msg_type = message.get("type", "")
        if msg_type == "get_state":
            self._handle_get_state()
        elif msg_type == "chat":
            self._handle_chat(message)
        elif msg_type == "new_chat":
            self._handle_new_chat()
        elif msg_type == "pick_chat":
            self._handle_pick_chat(message)
        elif msg_type == "delete_chat":
            self._handle_delete_chat(message)
        elif msg_type == "rename_chat":
            self._handle_rename_chat(message)
        elif msg_type == "toggle_pin":
            self._handle_toggle_pin(message)
        elif msg_type == "stop":
            self._handle_stop()
        elif msg_type == "set_context_flags":
            self._handle_context_flags(message)
        elif msg_type == "regenerate":
            self._handle_regenerate()
        elif msg_type == "save_settings":
            self._handle_save_settings(message)
        elif msg_type == "reset_settings":
            self._handle_reset_settings()
        elif msg_type == "test_key":
            self._handle_test_key(message)
        elif msg_type == "get_usage":
            self._handle_get_usage(message)
        elif msg_type == "attach_file":
            self._handle_attach_file(message)
        elif msg_type == "set_model":
            self._handle_set_model(message)
        elif msg_type == "set_default_model":
            self._handle_set_default_model(message)
        elif msg_type == "add_provider":
            self._handle_add_provider(message)
        elif msg_type == "update_provider":
            self._handle_update_provider(message)
        elif msg_type == "delete_provider":
            self._handle_delete_provider(message)
        elif msg_type == "add_model":
            self._handle_add_model(message)
        elif msg_type == "update_model":
            self._handle_update_model(message)
        elif msg_type == "delete_model":
            self._handle_delete_model(message)
        else:
            _LOGGER.warning("Неизвестный тип сообщения из UI: %s", msg_type)

    # ===== Хендлеры =====

    def _handle_get_state(self) -> None:
        """Отправляет полное состояние интерфейса."""
        self._send_state()

    def _settings_snapshot(self) -> dict[str, Any]:
        """Возвращает настройки для UI: общие ключи + ключ активного провайдера.

        Ключи остальных провайдеров в UI не отправляются — только активного,
        чтобы форма настроек могла предзаполнить поле API-ключа.
        """
        settings = {key: self._config[key] for key in SETTINGS_KEYS}
        provider_id = str(self._config.get("active_provider", "deepseek"))
        providers = self._config.get("providers", {})
        prov = providers.get(provider_id)
        settings["api_key"] = str(prov.get("api_key", "")) if isinstance(prov, dict) else ""
        return settings

    def _send_state(self) -> None:
        """Формирует и отправляет полный снимок состояния в UI."""
        chat = self._active_chat()
        self._post(
            {
                "type": "state",
                "chats": self._chats,
                "active": self._active,
                "settings": self._settings_snapshot(),
                "providers": self._providers_snapshot(),
                "commands": [{"cmd": cmd, "desc": desc} for cmd, desc in COMMANDS],
                "context_flags": chat["context_flags"],
                "context_tokens": self._ctx_tokens,
                "status": "печатает…" if self._gen else "",
            }
        )

    def _providers_snapshot(self) -> list[dict[str, Any]]:
        """Возвращает список провайдеров для UI.

        Ключи и URL отправляются в UI: это локальный webview, а не внешний
        канал, поэтому секреты доступны форме настроек для предзаполнения.
        """
        result: list[dict[str, Any]] = []
        providers = self._config.get("providers", {})
        for pid, pdef in providers.items():
            if not isinstance(pdef, dict):
                continue
            models: list[dict[str, Any]] = []
            for mid, mdef in pdef.get("models", {}).items():
                if isinstance(mdef, dict):
                    entry: dict[str, Any] = {
                        "id": mid,
                        "name": str(mdef.get("name", mid)),
                        "builtin": bool(mdef.get("builtin", False)),
                        "temperature": mdef.get("temperature"),
                        "max_tokens": mdef.get("max_tokens"),
                        "reasoning": mdef.get("reasoning"),
                        "scheme": str(mdef.get("scheme") or pdef.get("scheme") or "openai"),
                    }
                    if not mdef.get("builtin", False):
                        entry["base_url"] = str(mdef.get("base_url", ""))
                        entry["api_key"] = str(mdef.get("api_key", ""))
                    models.append(entry)
            prov_entry: dict[str, Any] = {
                "id": pid,
                "name": str(pdef.get("name", pid)),
                "builtin": bool(pdef.get("builtin", False)),
                "scheme": str(pdef.get("scheme", "openai")),
                "api_key": str(pdef.get("api_key", "")),
                "models": models,
            }
            if not pdef.get("builtin", False):
                prov_entry["base_url"] = str(pdef.get("base_url", ""))
            result.append(prov_entry)
        return result

    def _handle_chat(self, message: dict) -> None:
        """Обрабатывает отправку или редактирование сообщения пользователя."""
        text = str(message.get("text", "")).strip()
        if not text:
            return
        if text.startswith("/") and self._handle_command(text):
            self._pending_attachment = None
            return
        if self._gen:
            self._post(
                {
                    "type": "toast",
                    "text": "Генерация уже идёт. Дождитесь завершения или нажмите «Стоп».",
                    "kind": "err",
                }
            )
            return
        self._pending_confirm = None
        chat = self._active_chat()
        edit_id = message.get("edit_id")
        if edit_id is not None:
            self._apply_edit(chat, edit_id, text)
            return
        user_msg = {
            "id": self._next_msg_id(),
            "role": "user",
            "text": text,
            "ts": time.time(),
        }
        if self._pending_attachment is not None:
            user_msg.update(self._pending_attachment)
            self._pending_attachment = None
        chat["msgs"].append(user_msg)
        if chat["title"] == "Новый чат":
            chat["title"] = self._auto_title(text)
        chat["updated"] = time.time()
        self._trim_chat(chat)
        self._save_chats()
        self._start_generation(chat["id"], text, user_msg["id"])

    def _apply_edit(self, chat: dict[str, Any], edit_id: Any, text: str) -> None:
        """Заменяет текст отредактированного сообщения и перезапускает генерацию."""
        msgs = chat["msgs"]
        for index, msg in enumerate(msgs):
            if msg.get("id") == edit_id:
                msg["text"] = text
                del msgs[index + 1 :]
                chat["updated"] = time.time()
                self._save_chats()
                self._start_generation(chat["id"], text, edit_id)
                return
        _LOGGER.warning("Не найдено сообщение для редактирования: %s", edit_id)

    def _handle_new_chat(self) -> None:
        """Создаёт новый чат и обновляет интерфейс."""
        self._create_chat()
        self._send_state()

    def _handle_pick_chat(self, message: dict) -> None:
        """Переключает активный чат по идентификатору."""
        chat_id = message.get("id")
        if self._chat_by_id(chat_id) is not None:
            self._active = chat_id
            self._send_state()

    def _handle_delete_chat(self, message: dict) -> None:
        """Удаляет чат и корректирует активный идентификатор."""
        chat_id = message.get("id")
        self._chats = [chat for chat in self._chats if chat.get("id") != chat_id]
        if self._active == chat_id:
            self._active = self._chats[0]["id"] if self._chats else 0
        if not self._chats:
            self._create_chat()
        self._save_chats()
        self._send_state()

    def _handle_rename_chat(self, message: dict) -> None:
        """Переименовывает чат по идентификатору."""
        chat = self._chat_by_id(message.get("id"))
        if chat is None:
            return
        title = str(message.get("title", "")).strip()[:60]
        chat["title"] = title or "Новый чат"
        self._save_chats()
        self._send_state()

    def _handle_toggle_pin(self, message: dict) -> None:
        """Переключает закрепление чата."""
        chat = self._chat_by_id(message.get("id"))
        if chat is None:
            return
        chat["pinned"] = not chat.get("pinned", False)
        self._save_chats()
        self._send_state()

    def _handle_stop(self) -> None:
        """Останавливает текущую генерацию."""
        self._gen = False
        self._post({"type": "status", "text": ""})

    def _handle_context_flags(self, message: dict) -> None:
        """Обновляет флаги контекста активного чата."""
        flags = message.get("flags", {})
        if not isinstance(flags, dict):
            return
        chat = self._active_chat()
        chat["context_flags"] = {
            key: bool(flags.get(key, value))
            for key, value in chat["context_flags"].items()
        }
        self._ctx_tokens = self._estimate_context_tokens(chat["context_flags"])
        self._save_chats()
        self._send_state()

    def _handle_regenerate(self) -> None:
        """Перегенерирует последний ответ ассистента."""
        if self._gen:
            self._post(
                {
                    "type": "toast",
                    "text": "Генерация уже идёт. Дождитесь завершения или нажмите «Стоп».",
                    "kind": "err",
                }
            )
            return
        chat = self._active_chat()
        msgs = chat["msgs"]
        last_user = None
        for msg in reversed(msgs):
            if msg.get("role") == "user":
                last_user = msg
                break
        if last_user is None:
            return
        index = msgs.index(last_user)
        del msgs[index + 1 :]
        self._save_chats()
        self._start_generation(chat["id"], last_user["text"], last_user["id"])

    def _handle_save_settings(self, message: dict) -> None:
        """Сохраняет настройки, присланные из UI.

        Принимает новую схему (active_provider/active_model/api_key/...) и
        старую (provider/model/custom_*) для обратной совместимости с текущим JS.
        """
        settings = message.get("settings", {})
        if not isinstance(settings, dict):
            return
        for key in (
            "active_provider",
            "active_model",
            "default_model",
            "notes",
            "temperature",
            "max_tokens",
            "reasoning",
            "theme",
            "font_size",
            "font_style",
        ):
            if key in settings:
                self._config[key] = settings[key]
        # Обратная совместимость со старой схемой из текущего JS.
        if "provider" in settings:
            self._config["active_provider"] = settings["provider"]
        if "model" in settings:
            self._config["active_model"] = settings["model"]
        if settings.get("custom_model"):
            self._config["active_model"] = settings["custom_model"]
        if "custom_base_url" in settings:
            providers = self._config.setdefault("providers", {})
            providers.setdefault("custom", {})["base_url"] = settings["custom_base_url"]
        if "api_key" in settings:
            provider_id = str(self._config.get("active_provider", "deepseek"))
            providers = self._config.setdefault("providers", {})
            providers.setdefault(provider_id, {})["api_key"] = str(settings["api_key"])
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._post_settings()
        self._post({"type": "toast", "text": "Настройки сохранены.", "kind": "ok"})

    def _handle_reset_settings(self) -> None:
        """Сбрасывает настройки к заводским значениям."""
        self._config = self._normalize_config(DEFAULT_CONFIG.copy())
        self._cap.save_config(json.dumps(self._config))
        self._post_settings()
        self._post({"type": "toast", "text": "Настройки сброшены к заводским.", "kind": "ok"})

    def _post_settings(self) -> None:
        """Отправляет актуальные настройки в UI."""
        self._post(
            {
                "type": "settings",
                "settings": self._settings_snapshot(),
            }
        )

    def _handle_test_key(self, message: dict) -> None:
        """Запускает проверку API-ключа в фоновом потоке.

        Если в сообщении передан ключ (поле "key"), проверяется именно он,
        иначе — ключ активного провайдера.
        """
        key = message.get("key")
        if not isinstance(key, str) or not key.strip():
            key = None
        threading.Thread(target=self._test_key_worker, args=(key,), daemon=True).start()

    def _handle_get_usage(self, message: dict) -> None:
        """Отправляет статистику использования за выбранный период."""
        period = message.get("period", "all")
        snap = self._usage_snapshot(period)
        self._post({"type": "usage", **snap})

    def _handle_attach_file(self, message: dict) -> None:
        """Сохраняет вложение для следующего сообщения."""
        kind = message.get("kind")
        name = str(message.get("name", "файл"))
        data = message.get("data", "")
        if kind == "image":
            if len(data) > MAX_IMAGE_B64:
                self._post(
                    {
                        "type": "toast",
                        "text": "Изображение слишком большое (лимит 6 МБ).",
                        "kind": "err",
                    }
                )
                return
            self._pending_attachment = {"image": data}
        else:
            if len(data) > MAX_FILE_CHARS:
                self._post(
                    {
                        "type": "toast",
                        "text": "Файл слишком большой (лимит 1 МБ).",
                        "kind": "err",
                    }
                )
                return
            self._pending_attachment = {"file": {"name": name, "text": data}}
        self._post({"type": "toast", "text": "Вложение добавлено.", "kind": "ok"})

    # ===== Управление провайдерами и моделями =====

    def _handle_set_model(self, message: dict) -> None:
        """Устанавливает активного провайдера и модель."""
        provider = str(message.get("provider", ""))
        model = str(message.get("model", ""))
        providers = self._config.get("providers", {})
        if provider not in providers:
            self._post(
                {"type": "toast", "text": "Провайдер не найден: " + provider, "kind": "err"}
            )
            return
        if model not in providers[provider].get("models", {}):
            self._post(
                {"type": "toast", "text": "Модель не найдена: " + model, "kind": "err"}
            )
            return
        self._config["active_provider"] = provider
        self._config["active_model"] = model
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post({"type": "toast", "text": "Модель выбрана: " + model, "kind": "ok"})

    def _handle_set_default_model(self, message: dict) -> None:
        """Устанавливает модель по умолчанию для новых чатов."""
        provider = str(message.get("provider", ""))
        model = str(message.get("model", ""))
        providers = self._config.get("providers", {})
        if provider not in providers or model not in providers[provider].get("models", {}):
            self._post({"type": "toast", "text": "Модель не найдена.", "kind": "err"})
            return
        self._config["default_model"] = provider + "::" + model
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post({"type": "toast", "text": "Модель по умолчанию: " + model, "kind": "ok"})

    def _handle_add_provider(self, message: dict) -> None:
        """Создаёт пользовательского провайдера."""
        name = str(message.get("name", "")).strip()
        if not name:
            self._post(
                {"type": "toast", "text": "Укажите название провайдера.", "kind": "err"}
            )
            return
        base_url = str(message.get("base_url", "")).strip()
        api_key = str(message.get("api_key", "")).strip()
        pid = self._slugify(name) + "_" + self._random_suffix()
        providers = self._config.setdefault("providers", {})
        providers[pid] = {
            "name": name,
            "base_url": base_url,
            "api_key": api_key,
            "builtin": False,
            "scheme": "anthropic" if str(message.get("scheme", "openai")) == "anthropic" else "openai",
            "models": {},
        }
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post({"type": "toast", "text": "Провайдер добавлен: " + name, "kind": "ok"})

    def _handle_update_provider(self, message: dict) -> None:
        """Обновляет поля пользовательского провайдера."""
        pid = str(message.get("id", ""))
        providers = self._config.get("providers", {})
        prov = providers.get(pid)
        if not isinstance(prov, dict):
            self._post(
                {"type": "toast", "text": "Провайдер не найден.", "kind": "err"}
            )
            return
        if message.get("name") is not None:
            prov["name"] = str(message["name"]).strip() or prov.get("name", pid)
        if message.get("base_url") is not None:
            prov["base_url"] = str(message["base_url"]).strip()
        if message.get("api_key") is not None:
            prov["api_key"] = str(message["api_key"]).strip()
        if message.get("scheme") is not None:
            prov["scheme"] = (
                "anthropic" if str(message["scheme"]) == "anthropic" else "openai"
            )
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post({"type": "toast", "text": "Провайдер обновлён.", "kind": "ok"})

    def _handle_delete_provider(self, message: dict) -> None:
        """Удаляет пользовательского провайдера, встроенные — под защитой."""
        pid = str(message.get("id", ""))
        providers = self._config.get("providers", {})
        prov = providers.get(pid)
        if not isinstance(prov, dict):
            self._post(
                {"type": "toast", "text": "Провайдер не найден.", "kind": "err"}
            )
            return
        if prov.get("builtin"):
            self._post(
                {
                    "type": "toast",
                    "text": "Встроенный провайдер нельзя удалить.",
                    "kind": "err",
                }
            )
            return
        del providers[pid]
        if self._config.get("active_provider") == pid:
            self._config["active_provider"] = "deepseek"
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post({"type": "toast", "text": "Провайдер удалён.", "kind": "ok"})

    def _handle_add_model(self, message: dict) -> None:
        """Добавляет пользовательскую модель в провайдер."""
        provider = str(message.get("provider", ""))
        model_id = str(message.get("model_id", "")).strip()
        if not model_id:
            self._post(
                {"type": "toast", "text": "Укажите идентификатор модели.", "kind": "err"}
            )
            return
        name = str(message.get("name", "")).strip() or model_id
        providers = self._config.get("providers", {})
        prov = providers.get(provider)
        if not isinstance(prov, dict):
            self._post(
                {"type": "toast", "text": "Провайдер не найден.", "kind": "err"}
            )
            return
        models = prov.setdefault("models", {})
        if model_id in models:
            self._post(
                {
                    "type": "toast",
                    "text": "Модель уже существует: " + model_id,
                    "kind": "err",
                }
            )
            return
        entry: dict[str, Any] = {"name": name, "builtin": False}
        label = str(message.get("label", "")).strip()
        if label:
            entry["name"] = label
        # Per-model настройки: None → не записываем (наследуется глобальное).
        temperature = message.get("temperature")
        if temperature is not None:
            try:
                temperature = float(temperature)
            except (TypeError, ValueError):
                temperature = None
            if temperature is not None and (temperature < 0.0 or temperature > 2.0):
                temperature = None
            if temperature is not None:
                entry["temperature"] = temperature
        max_tokens = message.get("max_tokens")
        if max_tokens is not None:
            try:
                max_tokens = int(max_tokens)
            except (TypeError, ValueError):
                max_tokens = None
            if max_tokens is not None and (max_tokens < 1 or max_tokens > 100000):
                max_tokens = None
            if max_tokens is not None:
                entry["max_tokens"] = max_tokens
        reasoning = message.get("reasoning")
        if reasoning is not None:
            if isinstance(reasoning, str):
                reasoning = reasoning.strip().lower() in ("1", "true", "yes", "on")
            entry["reasoning"] = bool(reasoning)
        # URL/ключ/схема — только для пользовательских провайдеров.
        if not prov.get("builtin", False):
            if message.get("base_url") is not None:
                entry["base_url"] = str(message["base_url"]).strip()
            if message.get("api_key") is not None:
                entry["api_key"] = str(message["api_key"]).strip()
            if message.get("scheme") is not None:
                entry["scheme"] = (
                    "anthropic" if str(message["scheme"]) == "anthropic" else "openai"
                )
        models[model_id] = entry
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post({"type": "toast", "text": "Модель добавлена: " + model_id, "kind": "ok"})

    def _handle_update_model(self, message: dict) -> None:
        """Обновляет поля пользовательской модели.

        Принимает provider, model_id и опционально name, temperature,
        max_tokens, reasoning, base_url, api_key, scheme. URL/ключ/схему
        можно менять только у не-встроенных моделей.
        """
        provider = str(message.get("provider", ""))
        model_id = str(message.get("model_id", ""))
        providers = self._config.get("providers", {})
        prov = providers.get(provider)
        if not isinstance(prov, dict):
            self._post({"type": "toast", "text": "Провайдер не найден.", "kind": "err"})
            return
        models = prov.get("models", {})
        mdef = models.get(model_id)
        if not isinstance(mdef, dict):
            self._post({"type": "toast", "text": "Модель не найдена.", "kind": "err"})
            return
        if message.get("name") is not None:
            new_name = str(message["name"]).strip()
            if new_name:
                mdef["name"] = new_name
        temperature = message.get("temperature")
        if "temperature" in message:
            try:
                temperature = float(temperature) if temperature is not None else None
            except (TypeError, ValueError):
                temperature = None
            if temperature is not None and (temperature < 0.0 or temperature > 2.0):
                temperature = None
            mdef["temperature"] = temperature
        max_tokens = message.get("max_tokens")
        if "max_tokens" in message:
            try:
                max_tokens = int(max_tokens) if max_tokens is not None else None
            except (TypeError, ValueError):
                max_tokens = None
            if max_tokens is not None and (max_tokens < 1 or max_tokens > 100000):
                max_tokens = None
            mdef["max_tokens"] = max_tokens
        reasoning = message.get("reasoning")
        if "reasoning" in message:
            if reasoning is None:
                mdef["reasoning"] = None
            else:
                if isinstance(reasoning, str):
                    reasoning = reasoning.strip().lower() in ("1", "true", "yes", "on")
                mdef["reasoning"] = bool(reasoning)
        if mdef.get("builtin", False):
            if any(
                message.get(key) is not None
                for key in ("base_url", "api_key", "scheme")
            ):
                self._post(
                    {
                        "type": "toast",
                        "text": "У встроенной модели нельзя менять URL/ключ/схему.",
                        "kind": "err",
                    }
                )
                return
        else:
            if message.get("base_url") is not None:
                mdef["base_url"] = str(message["base_url"]).strip()
            if message.get("api_key") is not None:
                mdef["api_key"] = str(message["api_key"]).strip()
            if message.get("scheme") is not None:
                mdef["scheme"] = (
                    "anthropic" if str(message["scheme"]) == "anthropic" else "openai"
                )
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post({"type": "toast", "text": "Модель обновлена: " + model_id, "kind": "ok"})

    def _handle_delete_model(self, message: dict) -> None:
        """Удаляет пользовательскую модель, встроенные — под защитой."""
        provider = str(message.get("provider", ""))
        model_id = str(message.get("model_id", ""))
        providers = self._config.get("providers", {})
        prov = providers.get(provider)
        if not isinstance(prov, dict):
            self._post(
                {"type": "toast", "text": "Провайдер не найден.", "kind": "err"}
            )
            return
        models = prov.get("models", {})
        mdef = models.get(model_id)
        if not isinstance(mdef, dict):
            self._post(
                {"type": "toast", "text": "Модель не найдена.", "kind": "err"}
            )
            return
        if mdef.get("builtin"):
            self._post(
                {
                    "type": "toast",
                    "text": "Встроенную модель нельзя удалить.",
                    "kind": "err",
                }
            )
            return
        del models[model_id]
        if (
            self._config.get("active_provider") == provider
            and self._config.get("active_model") == model_id
        ):
            self._config["active_model"] = next(iter(models), "")
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post({"type": "toast", "text": "Модель удалена.", "kind": "ok"})

    @staticmethod
    def _slugify(text: str) -> str:
        """Преобразует название в идентификатор-слаг."""
        result: list[str] = []
        for ch in text.lower():
            if ch.isalnum() or ch in "-_":
                result.append(ch)
            elif ch.isspace():
                result.append("-")
        slug = "".join(result).strip("-")
        return slug or "provider"

    @staticmethod
    def _random_suffix() -> str:
        """Случайный короткий суффикс для идентификатора провайдера."""
        return "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=4))

    # ===== Отправка payload в UI =====

    def _post(self, payload: dict) -> None:
        """Отправляет payload в UI через установленный sink."""
        sink = self._post_sink
        if sink is None:
            return
        try:
            sink(payload)
        except Exception as exc:
            _LOGGER.error("Не удалось отправить payload в UI: %s", exc)

    # ===== Генерация ответа =====

    def _start_generation(self, chat_id: int, user_text: str, user_msg_id: int) -> None:
        """Запускает генерацию ответа в фоновом потоке."""
        if self._gen:
            self._post(
                {
                    "type": "toast",
                    "text": "Генерация уже идёт. Дождитесь завершения или нажмите «Стоп».",
                    "kind": "err",
                }
            )
            return
        self._gen = True
        threading.Thread(
            target=self._worker, args=(chat_id, user_text, user_msg_id), daemon=True
        ).start()

    def _worker(self, chat_id: int, user_text: str, user_msg_id: int) -> None:
        """Выполняет запрос к API в фоновом потоке и стримит ответ."""
        chat = self._chat_by_id(chat_id)
        if chat is None:
            self._gen = False
            return
        msg_id = self._next_msg_id()
        chat["msgs"].append(
            {"id": msg_id, "role": "assistant", "text": "", "ts": time.time()}
        )
        self._save_chats()
        self._post({"type": "status", "text": "печатает…"})
        try:
            messages = self._build_messages(chat, user_text)
            full_text = self._call_api(messages, chat_id)
            if not full_text.strip():
                full_text = "Модель вернула пустой ответ."
            msg = self._find_msg(chat, msg_id)
            if msg is not None:
                msg["text"] = full_text
            self._post({"type": "reply", "chat_id": chat_id, "text": full_text, "ok": True})
            self._record_usage(user_text, full_text)
        except FlowSliceError as exc:
            self._fail_generation(chat, chat_id, user_msg_id, msg_id, str(exc))
        except Exception as exc:
            _LOGGER.error("Необработанная ошибка генерации: %s", exc)
            self._fail_generation(
                chat, chat_id, user_msg_id, msg_id, "Внутренняя ошибка генерации."
            )
        finally:
            self._gen = False
            self._post({"type": "status", "text": ""})
            self._save_chats()

    def _fail_generation(
        self,
        chat: dict[str, Any],
        chat_id: int,
        user_msg_id: int,
        msg_id: int,
        text: str,
    ) -> None:
        """Помечает генерацию как ошибочную и уведомляет UI."""
        self._remove_msg(chat, user_msg_id)
        msg = self._find_msg(chat, msg_id)
        if msg is not None:
            msg["text"] = text
            msg["error"] = True
        self._post({"type": "reply", "chat_id": chat_id, "text": text, "ok": False})

    def _find_msg(self, chat: dict[str, Any], msg_id: int) -> dict[str, Any] | None:
        """Возвращает сообщение чата по идентификатору либо None."""
        for msg in chat.get("msgs", []):
            if msg.get("id") == msg_id:
                return msg
        return None

    def _remove_msg(self, chat: dict[str, Any], msg_id: int) -> None:
        """Удаляет сообщение из чата по идентификатору."""
        msgs = chat.get("msgs", [])
        for index, msg in enumerate(msgs):
            if msg.get("id") == msg_id:
                del msgs[index]
                return

    def _collect_context_images(self, chat: dict[str, Any]) -> list[str]:
        """Собирает data URI изображений из последних сообщений чата."""
        images: list[str] = []
        for msg in reversed(chat.get("msgs", [])):
            image = msg.get("image")
            if not isinstance(image, str) or not image.startswith("data:"):
                continue
            images.append(image)
            if len(images) >= MAX_IMAGES_IN_HISTORY:
                break
        return images

    def _build_messages(self, chat: dict[str, Any], user_text: str) -> list[dict[str, Any]]:
        """Собирает список сообщений для запроса к модели."""
        flags = chat.get("context_flags", {})
        ctx = self._collect_context(flags)
        system = self._build_system_prompt(ctx)
        if len(system) > MAX_CONTEXT_CHARS:
            system = system[:MAX_CONTEXT_CHARS]
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        if flags.get("history"):
            messages.extend(self._history_messages(chat, MAX_CONTEXT_CHARS))
        user_content = user_text
        last_user = self._last_user_msg(chat)
        if last_user is not None and last_user.get("file"):
            file_info = last_user["file"]
            user_content += (
                "\n\n[Файл: " + str(file_info.get("name", "файл")) + "]\n"
                + str(file_info.get("text", ""))
            )
        images = self._collect_context_images(chat)
        scheme = self._active_scheme()
        if images and scheme == "anthropic":
            # Нативный Messages API: изображения как base64-блоки.
            content: list[dict[str, Any]] = [{"type": "text", "text": user_content}]
            for img in images:
                b64 = img.split(",", 1)[1] if "," in img else img
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    }
                )
            messages.append({"role": "user", "content": content})
        elif images and scheme != "openai":
            content = [{"type": "text", "text": user_content}]
            content.extend(
                {"type": "image_url", "image_url": {"url": img}} for img in images
            )
            messages.append({"role": "user", "content": content})
        else:
            if images:
                user_content += (
                    "\n[Прикреплено изображений: "
                    + str(len(images))
                    + ". Модель DeepSeek не поддерживает изображения]"
                )
            messages.append({"role": "user", "content": user_content})
        return messages

    def _last_user_msg(self, chat: dict[str, Any]) -> dict[str, Any] | None:
        """Возвращает последнее сообщение пользователя в чате."""
        for msg in reversed(chat.get("msgs", [])):
            if msg.get("role") == "user":
                return msg
        return None

    def _history_messages(self, chat: dict[str, Any], max_chars: int) -> list[dict[str, Any]]:
        """Собирает историю сообщений для контекста, отбрасывая старые."""
        msgs = chat.get("msgs", [])
        last_user = self._last_user_msg(chat)
        history = msgs
        if last_user is not None:
            history = msgs[: msgs.index(last_user)]
        result: list[dict[str, Any]] = []
        total = 0
        for msg in reversed(history):
            if msg.get("role") not in ("user", "assistant"):
                continue
            text = str(msg.get("text", ""))
            if msg.get("image"):
                text += " [фото]"
            if msg.get("file"):
                text += " [файл: " + str(msg.get("file", {}).get("name", "файл")) + "]"
            if total + len(text) > max_chars:
                break
            result.append({"role": msg["role"], "content": text})
            total += len(text)
        result.reverse()
        return result

    def _active_api_credentials(self) -> tuple[str, str, str, str, str]:
        """Возвращает (provider_id, base_url, api_key, model, scheme).

        Учитывает переопределение base_url/api_key на уровне выбранной модели.
        Схема API: per-model, затем провайдер, затем "openai".
        """
        cfg = self._config
        provider_id = str(cfg.get("active_provider", "deepseek"))
        providers = cfg.get("providers", {})
        prov = providers.get(provider_id)
        if not isinstance(prov, dict):
            prov = {}
        base_url = str(prov.get("base_url", ""))
        api_key = str(prov.get("api_key", ""))
        model = str(cfg.get("active_model", ""))
        mdef = prov.get("models", {}).get(model)
        if isinstance(mdef, dict):
            if mdef.get("base_url"):
                base_url = str(mdef["base_url"])
            if mdef.get("api_key"):
                api_key = str(mdef["api_key"])
        scheme = str(mdef.get("scheme") or prov.get("scheme") or "openai")
        return provider_id, base_url, api_key, model, scheme

    def _active_scheme(self) -> str:
        """Возвращает схему API активной модели без повторной синхронизации."""
        cfg = self._config
        provider_id = str(cfg.get("active_provider", "deepseek"))
        prov = cfg.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            return "openai"
        mdef = prov.get("models", {}).get(str(cfg.get("active_model", "")))
        if isinstance(mdef, dict):
            return str(mdef.get("scheme") or prov.get("scheme") or "openai")
        return str(prov.get("scheme") or "openai")

    def _call_api(self, messages: list[dict[str, Any]], chat_id: int) -> str:
        """Выполняет запрос к API провайдера и возвращает полный текст ответа."""
        self._sync_config()
        provider_id, base_url, api_key, model, scheme = self._active_api_credentials()
        if not api_key:
            raise ApiError("Пожалуйста, укажите API-ключ в настройках.")
        cfg = self._config
        # Per-model настройки: None → наследуем глобальные значения.
        prov = cfg.get("providers", {}).get(provider_id)
        mdef = prov.get("models", {}).get(model) if isinstance(prov, dict) else {}
        temperature = mdef.get("temperature")
        if temperature is None:
            temperature = float(cfg.get("temperature", 0.7))
        max_tokens = mdef.get("max_tokens")
        if max_tokens is None:
            max_tokens = int(cfg.get("max_tokens", 4096))
        reasoning = mdef.get("reasoning")
        if reasoning is None:
            reasoning = bool(cfg.get("reasoning", False))
        if scheme == "anthropic":
            return self._call_anthropic(
                messages,
                chat_id,
                base_url,
                api_key,
                model,
                temperature,
                max_tokens,
                reasoning,
            )
        url = base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if reasoning:
            if provider_id == "openrouter":
                payload["reasoning"] = {"effort": "high"}
            elif provider_id == "openai":
                payload["reasoning_effort"] = "high"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**HTTP_HEADERS, "Authorization": "Bearer " + api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
                return self._read_sse(resp, chat_id)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise ApiError("Ошибка API " + str(exc.code) + ": " + body) from exc
        except urllib.error.URLError as exc:
            raise NetworkError("Сетевая ошибка: " + str(exc.reason)) from exc
        except TimeoutError as exc:
            raise NetworkError("Превышен таймаут запроса.") from exc
        except PermissionError as exc:
            raise NetworkError(
                "Сетевой доступ запрещён песочницей. Разрешите сеть для плагина."
            ) from exc
        except OSError as exc:
            raise NetworkError("Ошибка соединения: " + str(exc)) from exc

    def _call_anthropic(
        self,
        messages: list[dict[str, Any]],
        chat_id: int,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        reasoning: bool,
    ) -> str:
        """Выполняет запрос к нативному Messages API Anthropic."""
        system = ""
        body_messages = messages
        if messages and messages[0].get("role") == "system":
            system = str(messages[0].get("content", ""))
            body_messages = messages[1:]
        url = base_url.rstrip("/") + "/messages"
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": body_messages,
            "temperature": temperature,
            "stream": True,
        }
        if reasoning:
            budget = min(4096, max(1024, max_tokens // 2))
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OrcaSlicer/2.5.0",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
                return self._read_sse_anthropic(resp, chat_id)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise ApiError("Ошибка API " + str(exc.code) + ": " + body) from exc
        except urllib.error.URLError as exc:
            raise NetworkError("Сетевая ошибка: " + str(exc.reason)) from exc
        except TimeoutError as exc:
            raise NetworkError("Превышен таймаут запроса.") from exc
        except PermissionError as exc:
            raise NetworkError(
                "Сетевой доступ запрещён песочницей. Разрешите сеть для плагина."
            ) from exc
        except OSError as exc:
            raise NetworkError("Ошибка соединения: " + str(exc)) from exc

    def _read_sse(self, resp: Any, chat_id: int) -> str:
        """Читает SSE-поток ответа и отправляет инкрементальные куски в UI."""
        acc = ""
        sent = ""
        last_post = 0.0
        for raw in resp:
            if not self._gen:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"].get("content", "")
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            if not delta:
                continue
            acc += delta
            now = time.monotonic()
            if now - last_post >= STREAM_THROTTLE:
                self._post({"type": "delta", "chat_id": chat_id, "text": delta})
                last_post = now
                sent += delta
        if acc and sent != acc:
            self._post({"type": "delta", "chat_id": chat_id, "text": acc[len(sent) :]})
        return acc

    def _read_sse_anthropic(self, resp: Any, chat_id: int) -> str:
        """Читает SSE-поток Messages API Anthropic и стримит текст в UI."""
        acc = ""
        sent = ""
        last_post = 0.0
        for raw in resp:
            if not self._gen:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data:
                continue
            try:
                event = json.loads(data)
            except ValueError:
                continue
            if event.get("type") != "content_block_delta":
                continue
            delta = event.get("delta", {})
            text = delta.get("text", "")
            if not text:
                continue
            acc += text
            now = time.monotonic()
            if now - last_post >= STREAM_THROTTLE:
                self._post({"type": "delta", "chat_id": chat_id, "text": text})
                last_post = now
                sent += text
        if acc and sent != acc:
            self._post({"type": "delta", "chat_id": chat_id, "text": acc[len(sent) :]})
        return acc

    def _test_key_worker(self, key: str | None = None) -> None:
        """Проверяет API-ключ фоновым запросом к провайдеру.

        Если передан непустой ключ, он имеет приоритет над сохранённым.
        """
        self._sync_config()
        _, base_url, api_key, model, scheme = self._active_api_credentials()
        if key and key.strip():
            api_key = key.strip()
        if not api_key:
            self._post({"type": "key_test", "ok": False, "text": "API-ключ не указан."})
            return
        if scheme == "anthropic":
            url = base_url.rstrip("/") + "/messages"
            payload = {
                "model": model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
            }
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "OrcaSlicer/2.5.0",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
        else:
            url = base_url.rstrip("/") + "/chat/completions"
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "stream": False,
            }
            headers = {**HTTP_HEADERS, "Authorization": "Bearer " + api_key}
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                resp.read()
            self._post({"type": "key_test", "ok": True, "text": "Ключ действителен."})
        except urllib.error.HTTPError as exc:
            self._post(
                {"type": "key_test", "ok": False, "text": "Ошибка API " + str(exc.code) + "."}
            )
        except OSError as exc:
            self._post(
                {"type": "key_test", "ok": False, "text": "Сетевая ошибка: " + str(exc)}
            )

    # ===== Контекст слайсера =====

    def _collect_context(self, flags: dict[str, Any]) -> dict[str, Any]:
        """Собирает контекст слайсера по включённым флагам."""
        ctx: dict[str, Any] = {}
        if flags.get("model"):
            ctx["model"] = self._collect_model_data()
        if flags.get("filament") or flags.get("printer") or flags.get("print"):
            ctx["presets"] = self._collect_preset_data()
        return ctx

    def _collect_model_data(self) -> dict[str, Any]:
        """Собирает данные о модели на столе слайсера."""
        data: dict[str, Any] = {"objects": [], "coords": "world"}
        try:
            model = orca.host.model()
            for obj in model.objects():
                for vol in obj.volumes():
                    mesh = self._safe_get(vol, "mesh")
                    if mesh is None:
                        continue
                    bbox = self._safe_get(mesh, "bounding_box")
                    if bbox is not None:
                        size = getattr(bbox, "size", bbox)
                        if isinstance(size, (tuple, list)) and len(size) >= 3:
                            local_bbox = tuple(round(float(v), 1) for v in size[:3])
                        else:
                            local_bbox = ()
                    else:
                        local_bbox = ()
                    volume = self._safe_get(mesh, "volume")
                    entry: dict[str, Any] = {
                        "name": self._safe_get(vol, "name") or "",
                        "local_bbox_mm": local_bbox,
                        "volume_cm3": round(volume / 1000.0, 2) if volume else 0.0,
                        "manifold": bool(self._safe_get(mesh, "is_manifold")),
                        "triangles": self._safe_get(mesh, "triangle_count") or 0,
                    }
                    if _HAS_NUMPY:
                        entry.update(self._world_stats(obj, vol, mesh))
                    else:
                        entry["coords"] = "local"
                        entry.update(self._local_stats(obj))
                    data["objects"].append(entry)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Не удалось собрать данные модели: %s", exc)
            data["objects"] = []
        return data

    def _world_stats(self, obj: Any, vol: Any, mesh: Any) -> dict[str, Any]:
        """Считает мировые характеристики экземпляров через numpy."""
        assert _np is not None
        stats: dict[str, Any] = {"instances": []}
        try:
            verts = self._safe_get(mesh, "vertices")
            tris = self._safe_get(mesh, "triangles")
            vol_matrix = self._safe_get(vol, "matrix")
            if verts is None or tris is None or vol_matrix is None:
                return stats
            verts = _np.asarray(verts, dtype=_np.float64)
            tris = _np.asarray(tris)
            instances = self._safe_get(obj, "instances")
            if isinstance(instances, (list, tuple)):
                inst_list = instances
            else:
                inst_fn = getattr(obj, "instance", None)
                if not callable(inst_fn):
                    return stats
                inst_list = [inst_fn(i) for i in range(int(instances))]
            for index, inst in enumerate(inst_list):
                inst_matrix = self._safe_get(inst, "matrix")
                if inst_matrix is None:
                    continue
                world = (
                    _np.column_stack((verts, _np.ones(len(verts))))
                    @ (inst_matrix @ vol_matrix).T
                )[:, :3]
                bbox_min = world.min(axis=0)
                bbox_max = world.max(axis=0)
                tri_pts = world[tris]
                cross = _np.cross(
                    tri_pts[:, 1] - tri_pts[:, 0], tri_pts[:, 2] - tri_pts[:, 0]
                )
                area = float(_np.sum(_np.linalg.norm(cross, axis=1) / 2.0))
                stats["instances"].append(
                    {
                        "index": index,
                        "position_mm": tuple(
                            round(v, 1) for v in inst_matrix[:3, 3]
                        ),
                        "world_bbox_mm": tuple(
                            round(v, 1) for v in (bbox_max - bbox_min)
                        ),
                        "surface_area_cm2": round(area / 100.0, 2),
                        "mirrored": bool(self._safe_get(inst, "is_left_handed")),
                    }
                )
        except (ImportError, RuntimeError, ValueError, TypeError):
            stats = {}
        return stats

    def _local_stats(self, obj: Any) -> dict[str, Any]:
        """Собирает локальные характеристики экземпляров без numpy."""
        stats: dict[str, Any] = {"instances": []}
        try:
            instances = self._safe_get(obj, "instances")
            if isinstance(instances, (list, tuple)):
                inst_list = instances
            else:
                inst_fn = getattr(obj, "instance", None)
                if not callable(inst_fn):
                    return stats
                inst_list = [inst_fn(i) for i in range(int(instances))]
            for index, inst in enumerate(inst_list):
                stats["instances"].append(
                    {
                        "index": index,
                        "offset": tuple(
                            round(v, 1) for v in self._safe_get(inst, "offset")
                        ),
                        "rotation": tuple(
                            round(v, 1) for v in self._safe_get(inst, "rotation")
                        ),
                        "scaling_factor": tuple(
                            round(v, 2) for v in self._safe_get(inst, "scaling_factor")
                        ),
                        "mirrored": bool(self._safe_get(inst, "mirror")),
                    }
                )
        except (RuntimeError, ValueError, TypeError):
            stats = {}
        return stats

    @staticmethod
    def _safe_get(target: Any, name: str) -> Any:
        """Безопасно читает атрибут или метод объекта."""
        value = getattr(target, name, None)
        if callable(value):
            try:
                value = value()
            except (TypeError, RuntimeError):
                value = None
        return value

    @staticmethod
    def _json_safe(value: Any) -> Any:
        """Приводит значение к JSON-сериализуемому примитиву.

        None/bool/int/float/str возвращаются как есть; list/tuple и dict
        обрабатываются рекурсивно с ограничением размера; прочие объекты
        превращаются в строку (до 500 символов).
        """
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, (list, tuple)):
            return [_ChatEngine._json_safe(item) for item in list(value)[:50]]
        if isinstance(value, dict):
            return {
                str(key): _ChatEngine._json_safe(item)
                for key, item in list(value.items())[:50]
            }
        return str(value)[:500]

    def _collect_preset_data(self) -> dict[str, Any]:
        """Собирает данные активных пресетов печати через preset_bundle.

        Имя пресета берётся из коллекции (printers/prints/filaments),
        значения полей — через full_config_value с fallback на объединённый конфиг.
        """
        out: dict[str, Any] = {"printer": {}, "filament": {}, "print": {}}
        try:
            bundle = orca.host.preset_bundle()
        except RuntimeError:
            return out
        has_full_value = callable(getattr(bundle, "full_config_value", None))
        for key, (collection_attr, fields) in PRESET_SECTIONS.items():
            section: dict[str, Any] = {}
            try:
                collection = getattr(bundle, collection_attr, None)
                if collection is not None:
                    name = self._safe_get(collection, "get_selected_preset_name")
                    if name:
                        section["name"] = str(name)
            except (AttributeError, RuntimeError):
                pass
            for field in fields:
                value: Any = None
                if has_full_value:
                    try:
                        value = bundle.full_config_value(field)
                    except (RuntimeError, TypeError, ValueError):
                        value = None
                    value = getattr(value, "value", value)
                if value in (None, ""):
                    value = self._fallback_preset_value(bundle, field)
                if value not in (None, ""):
                    section[field] = self._json_safe(value)
            out[key] = section
        return out

    def _fallback_preset_value(self, bundle: Any, key: str) -> Any:
        """Ищет значение ключа через объединённый конфиг пресетов."""
        for attr in ("full_config", "full_fff_config"):
            config = self._safe_get(bundle, attr)
            if config is None:
                continue
            for accessor in ("opt_string", "get", "opt", "at", "option"):
                fn = getattr(config, accessor, None)
                if not callable(fn):
                    continue
                try:
                    value = fn(key)
                except (TypeError, RuntimeError, ValueError):
                    continue
                value = getattr(value, "value", value)
                if value not in (None, ""):
                    return value
        return None

    def _build_system_prompt(self, ctx: dict[str, Any]) -> str:
        """Собирает системный промпт с данными контекста слайсера."""
        parts = [SYSTEM_PROMPT]
        notes = str(self._config.get("notes", "")).strip()
        if notes:
            parts.append(
                "Заметки пользователя (важная информация, учитывай её при ответах):\n"
                + notes
            )
        if ctx.get("model"):
            parts.append(
                "Данные модели со стола:\n"
                + json.dumps(ctx["model"], ensure_ascii=False, indent=2)
            )
        if ctx.get("presets"):
            parts.append(
                "Профили печати:\n"
                + json.dumps(ctx["presets"], ensure_ascii=False, indent=2)
            )
        parts.append(
            "Окружение: Python "
            + sys.version.split()[0]
            + ", дата/время: "
            + time.strftime("%Y-%m-%d %H:%M")
        )
        return "\n\n".join(parts)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Грубо оценивает число токенов в тексте."""
        return len(text) // 4

    def _estimate_context_tokens(self, flags: dict[str, Any]) -> int:
        """Оценивает число токенов контекста по флагам."""
        try:
            ctx = self._collect_context(flags)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Не удалось собрать контекст слайсера: %s", exc)
            ctx = {}
        return self._estimate_tokens(json.dumps(ctx, ensure_ascii=False))

    # ===== Команды =====

    def _handle_command(self, text: str) -> bool:
        """Обрабатывает служебные команды, начинающиеся со слэша."""
        stripped = text.strip()
        if not stripped:
            return False
        cmd = stripped.split()[0].lower()
        if cmd == "/context":
            self._cmd_context()
        elif cmd == "/clear":
            self._cmd_clear()
        elif cmd == "/model":
            self._cmd_model()
        elif cmd == "/printer":
            self._cmd_printer()
        elif cmd == "/stats":
            self._cmd_stats()
        elif cmd == "/help":
            self._cmd_help()
        elif cmd == "/reset":
            self._cmd_reset()
        else:
            return False
        return True

    def _cmd_help(self) -> None:
        """Выводит список доступных команд."""
        lines = ["Доступные команды:"]
        for cmd, desc in COMMANDS:
            lines.append(cmd + " — " + desc)
        self._append_system("\n".join(lines))

    def _cmd_model(self) -> None:
        """Формирует отчёт о модели на столе."""
        data = self._collect_model_data()
        objects = data.get("objects", [])
        if not objects:
            self._append_system("Модель на столе отсутствует или недоступна.")
            return
        lines = ["Отчёт о модели на столе:"]
        for obj in objects:
            lines.append("• " + str(obj.get("name", "Без имени")))
            lines.append("  Локальный bbox, мм: " + str(obj.get("local_bbox_mm", "—")))
            lines.append("  Объём: " + str(obj.get("volume_cm3", "—")) + " см³")
            lines.append(
                "  Площадь поверхности: " + str(obj.get("surface_area_cm2", "—")) + " см²"
            )
            lines.append("  Треугольники: " + str(obj.get("triangles", "—")))
            lines.append("  Manifold: " + ("да" if obj.get("manifold") else "нет"))
            for inst in obj.get("instances", []):
                line = "  Экземпляр " + str(inst.get("index", "—"))
                if inst.get("mirrored"):
                    line += " — ЗЕРКАЛЬНЫЙ экземпляр"
                lines.append(line)
        self._append_system("\n".join(lines))

    def _cmd_printer(self) -> None:
        """Формирует сводку профилей печати."""
        data = self._collect_preset_data()
        lines = ["Сводка профилей печати:"]
        sections = (
            ("printer", "Принтер"),
            ("filament", "Пластик"),
            ("print", "Настройки печати"),
        )
        for key, label in sections:
            section = data.get(key, {})
            if not section:
                lines.append("• " + label + ": недоступно")
                continue
            lines.append("• " + label + ":")
            for field, value in section.items():
                lines.append("  " + str(field) + ": " + str(value))
        self._append_system("\n".join(lines))

    def _cmd_stats(self) -> None:
        """Выводит статистику использования ассистента."""
        snap = self._usage_snapshot("all")
        self._append_system(
            "Сообщений: " + str(snap["msgs"]) + ", Токенов: " + str(snap["tokens"])
        )

    def _cmd_context(self) -> None:
        """Выводит полный дамп контекста слайсера."""
        chat = self._active_chat()
        flags = chat.get("context_flags", {})
        ctx = self._collect_context(flags)
        lines = ["Контекст слайсера:"]
        lines.append("Системный промпт:")
        lines.append(self._build_system_prompt(ctx))
        lines.append("Чекбоксы контекста:")
        for key, value in flags.items():
            lines.append("  " + str(key) + ": " + ("вкл" if value else "выкл"))
        lines.append("Данные контекста:")
        lines.append(json.dumps(ctx, ensure_ascii=False, indent=2))
        lines.append("История сообщений:")
        history = self._history_messages(chat, MAX_CONTEXT_CHARS)
        if history:
            for item in history:
                lines.append("  [" + item["role"] + "] " + item["content"][:200])
        else:
            lines.append("  (пусто)")
        lines.append(
            "Оценка токенов контекста: " + str(self._estimate_context_tokens(flags))
        )
        self._append_system("\n".join(lines))

    def _confirm_command(self, cmd: str) -> bool:
        """Реализует двухшаговое подтверждение деструктивной команды."""
        if self._pending_confirm != cmd:
            self._pending_confirm = cmd
            self._append_system("Подтвердите: отправьте " + cmd + " ещё раз.")
            return False
        self._pending_confirm = None
        return True

    def _cmd_clear(self) -> None:
        """Очищает историю чата с двухшаговым подтверждением."""
        if not self._confirm_command("/clear"):
            return
        chat = self._active_chat()
        chat["msgs"] = []
        chat["title"] = "Новый чат"
        chat["updated"] = time.time()
        self._ctx_tokens = 0
        self._save_chats()
        self._append_system("История чата очищена.")

    def _cmd_reset(self) -> None:
        """Сбрасывает настройки с двухшаговым подтверждением."""
        if not self._confirm_command("/reset"):
            return
        self._config = self._normalize_config(DEFAULT_CONFIG.copy())
        self._cap.save_config(json.dumps(self._config))
        self._append_system("Настройки сброшены к заводским.")

    # ===== Статистика использования =====

    def _record_usage(self, user_text: str, answer_text: str) -> None:
        """Учитывает сообщение и токены в статистике использования."""
        today = time.strftime("%Y-%m-%d")
        usage = self._config.setdefault("usage", {})
        day = usage.setdefault(today, {"msgs": 0, "tokens": 0})
        day["msgs"] += 1
        day["tokens"] += (len(user_text) + len(answer_text)) // 4
        self._cap.save_config(json.dumps(self._config))

    def _usage_snapshot(self, period: str) -> dict[str, Any]:
        """Возвращает сводку использования за выбранный период."""
        usage = self._config.get("usage", {})
        today = time.strftime("%Y-%m-%d")
        if period == "day":
            keys = [today]
        elif period == "week":
            keys = [
                (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
                for i in range(7)
            ]
        elif period == "month":
            keys = [key for key in usage if key.startswith(today[:7])]
        else:
            keys = list(usage)
        msgs = sum(usage.get(key, {}).get("msgs", 0) for key in keys)
        tokens = sum(usage.get(key, {}).get("tokens", 0) for key in keys)
        return {"period": period, "msgs": msgs, "tokens": tokens}


class _ConfigMixin:
    """Общие методы конфигурации для вкладки и окна плагина."""

    def get_default_config(self) -> dict:
        """Возвращает дефолтную конфигурацию плагина."""
        return DEFAULT_CONFIG.copy()

    def get_config(self) -> str:
        """Возвращает конфигурацию базового capability либо пустой JSON."""
        getter: Any = getattr(super(), "get_config", None)
        if getter is not None:
            return str(getter())
        return "{}"

    def save_config(self, config: str) -> bool:
        """Сохраняет конфигурацию через базовый capability."""
        setter: Any = getattr(super(), "save_config", None)
        if setter is not None:
            return bool(setter(config))
        return False

    def has_config_ui(self) -> bool:
        """Сообщает хосту о наличии кастомной страницы настроек."""
        return True

    def get_config_ui(self) -> str:
        """Возвращает HTML-страницу настроек."""
        return CONFIG_PAGE

    def _ensure_engine(self) -> "_ChatEngine":
        """Лениво создаёт общий движок плагина и подключает sink."""
        engine = getattr(self, "_engine", None)
        if engine is None:
            engine = _ChatEngine(self)
            engine.set_post_sink(self._make_post_sink())
            self._engine = engine
        return engine

    def _make_post_sink(self) -> Any:
        """Возвращает callable для доставки payload в UI."""
        if _PAGES_BASE is not None and isinstance(self, _PAGES_BASE):
            return getattr(self, "post_message", self._window_post)
        return self._window_post

    def _window_post(self, payload: dict) -> None:
        """Отправляет payload в открытое окно ассистента."""
        win = getattr(self, "_win", None)
        if win is not None and win.is_open():
            win.post(payload)


if _PAGES_BASE is not None:

    class FlowSliceTab(_ConfigMixin, _PAGES_BASE):
        """Вкладка FlowSlice AI в главном окне OrcaSlicer."""

        def get_name(self) -> str:
            """Имя вкладки."""
            return "FlowSlice AI"

        def get_ui(self) -> str:
            """HTML-содержимое вкладки."""
            self._ensure_engine()
            return HTML_PAGE

        def get_icon(self) -> str:
            """Записывает иконку вкладки и возвращает путь к файлу."""
            try:
                ICON_FILE.write_text(_TAB_ICON_SVG, encoding="utf-8")
                return str(ICON_FILE)
            except OSError as exc:
                _LOGGER.error("Не удалось записать иконку вкладки: %s", exc)
                return ""

        def on_message(self, message: dict) -> None:
            """Обрабатывает сообщение из пользовательского интерфейса вкладки."""
            self._ensure_engine().handle_message(message)


if _SCRIPT_BASE is not None:

    class FlowSliceWindow(_ConfigMixin, _SCRIPT_BASE):
        """Оконная (script) capability FlowSlice AI."""

        _win: Any = None

        def get_name(self) -> str:
            """Имя capability."""
            return "FlowSlice AI"

        def execute(self) -> orca.ExecutionResult:
            """Открывает окно ассистента либо сообщает, что оно уже открыто."""
            self._ensure_engine()
            win = getattr(self, "_win", None)
            if win is not None and win.is_open():
                return orca.ExecutionResult.success("Окно FlowSlice AI уже открыто")
            self._win = orca.host.ui.create_window(
                html=HTML_PAGE,
                title="FlowSlice AI",
                on_message=self._on_message,
                on_close=self._on_close,
            )
            return orca.ExecutionResult.success("Окно FlowSlice AI открыто")

        def _on_message(self, message: dict) -> None:
            """Обрабатывает сообщение из окна ассистента."""
            self._ensure_engine().handle_message(message)

        def _on_close(self, *_args: Any) -> None:
            """Сбрасывает ссылку на закрытое окно."""
            self._win = None


@orca.plugin
class FlowSlicePlugin(orca.base):
    """Пакет плагина FlowSlice AI: регистрация capability."""

    def register_capabilities(self) -> None:
        """Регистрирует доступную capability в порядке приоритета."""
        if _PAGES_BASE is not None:
            orca.register_capability(FlowSliceTab)
        elif _SCRIPT_BASE is not None:
            orca.register_capability(FlowSliceWindow)
