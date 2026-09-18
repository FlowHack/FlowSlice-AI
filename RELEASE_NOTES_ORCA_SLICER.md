FlowSlice AI — version 0.1.0 (first public release)

An AI 3D-printing engineer right inside Orca Slicer. It sees your model, profiles and print history,
and helps with mechanics, Klipper and material fine-tuning.

What's new:
- AI 3D-printing engineer: expert in mechanics, Klipper and material fine-tuning, right in the Orca Slicer tab.
- Slicer context: model on the plate (dimensions, volume, manifold, instance stats), printer / filament / print-setting profiles (full parameter dump, notes, start/end G-code).
- Multi-chat with history: local persistence, search, pinning, auto titles, message limit.
- Streaming responses (SSE): stop generation, regenerate, edit and resend.
- Attachments: photos (up to 6 MB) and text files (up to 1 MB) in the context; a warning is shown for models without image support, and text files are sent as plain text.
- Providers: DeepSeek, OpenRouter (including auto / auto-beta / free routers), Google, Anthropic, OpenAI, Groq, GLM, Cerebras, Mistral, xAI; plus custom OpenAI/Anthropic-compatible providers on the Custom tab.
- Settings in 4 tabs: Models, Custom, General, Appearance; the draft applies only after Save, reset affects only the current tab.
- Context in chat: context checkboxes and preset export mode (changed only / all) for filament, printer and print settings, right in the chat panel and remembered per chat.
- Commands: /context, /clear, /model, /printer, /stats, /help, /reset.
- Localization: English / Русский / Srpski.
- Theming: auto (native Orca) / pure white / pure black, accent #d9534f.

Platforms: Windows x64, Linux x64, macOS x64, macOS arm64.

How to install:
1. Subscribe to FlowSlice AI on OrcaCloud.
2. After subscribing, the plugin appears among the available plugins in Orca Slicer — install and enable it.
3. Open the FlowSlice AI tab; restart Orca Slicer if the tab does not appear.

Note: the numpy dependency is installed automatically with the plugin.

Developer: @FlowHack
Build: v0.1.0
