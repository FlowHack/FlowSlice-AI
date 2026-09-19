What's new in 0.1.0 — first public release.

AI 3D-printing engineer right inside Orca Slicer, aware of your slicer context.
Slicer context: model on the plate (dimensions, volume, surface, triangles, manifold) and printer / filament / print-setting profiles, with changed-only or full export per profile. Parameter keys are sent with human-readable interface labels such as "Brim type (brim_type)" — 823 OrcaSlicer settings with 753 Russian translations.
Reasoning models: expandable reasoning blocks that open while streaming and collapse when the answer is done, with a chevron and a red live highlight. Supported for OpenRouter, DeepSeek and Anthropic.
Exact usage and cost: real prompt and completion tokens and cost from OpenRouter, exact token counts from Anthropic, and an estimate otherwise. The cost is shown only when both input and output prices are known.
Context checkboxes and preset export mode are remembered per chat.
Multi-chat with local history, search, pinning and up to 200 messages per chat. The selected model is remembered per chat and restored on restart, with a footnote showing the model that produced each answer.
Streaming responses with stop, regenerate, edit and resend, and answer variants. A stopped reply is marked as interrupted by the user instead of staying empty.
Attachments: photos up to 4 MB (compressed to 1024 px) and text files up to 100,000 characters, up to 10 per message.
11 built-in providers including NordRouter, plus custom OpenAI/Anthropic-compatible providers.
Favorite models: a pinned Favorites group and a heart toggle, kept across restarts.
Model catalog sync: refresh from provider button and auto-refresh, with prices and image-support flags; manual tuning is preserved. Model search does not depend on word order.
Settings in 4 tabs with per-model temperature, max tokens and reasoning mode. Defaults: temperature 0.3, max tokens 8192, and at least 16384 when reasoning is enabled.
Automatic history compaction at 80 percent of the 128,000-token context window.
The context command shows the actual message list sent to the model and the real token count of the request.
An optional Support the project widget with the current donation details.
Commands, localization (English / Russian / Serbian) and themes (auto / white / black).
