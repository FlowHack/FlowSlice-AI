**An AI 3D-printing engineer right inside Orca Slicer.**
It sees your model, profiles and print history, and helps with mechanics, Klipper and material fine-tuning.

---

## 🤖 What it is

**FlowSlice AI** is an assistant plugin for [Orca Slicer](https://github.com/OrcaSlicer/OrcaSlicer). It adds a chat tab where an AI 3D-printing engineer answers with your slicer context, so advice is specific to your model, printer and material.

- explains print defects and tells you which settings to change;
- helps with calibration (flow, Pressure Advance, retraction, first layer);
- advises on mechanics, firmware (Klipper, Marlin) and maintenance;
- compares materials (PLA, PETG, ABS, TPU) and analyzes defect photos.

> 💡 "Why is there bulging on the corners? I use PETG on an Ender-3." — the assistant sees your profile, temperature, speed and flow and gives concrete values.

---

## ✨ Features

### 💬 Chat

- Streaming responses (SSE); stop generation and regenerate the last reply.
- Reasoning blocks: expandable while streaming, auto-collapsed when done (OpenRouter, DeepSeek, Anthropic).
- Edit & resend any message; answer variants.

### 🗂 Multi-chat

- Unlimited conversations with automatic titles, search and pinning; up to 200 messages per chat.
- History persists between sessions; the model is remembered per chat.

### 🧠 Slicer context

- Model on the plate: dimensions, volume, surface area, triangles, position, manifold check, instances.
- Printer, filament and print profiles: full dump or only changed parameters.
- Localized parameter names ("Brim type (brim_type)"): 823 OrcaSlicer settings, 753 Russian translations.
- Profile notes, start/end G-code and per-chat context checkboxes.

### 🔌 Providers & models

- 11 built-in providers plus your own OpenAI/Anthropic-compatible ones; favorite models (♥) survive restarts.
- Catalog sync ("Refresh models" and auto-refresh) and word-order-independent search; per-model temperature, max tokens, reasoning mode and image support.
- Token and cost statistics (📊) from provider usage when reported, otherwise estimated; fallback on HTTP 400.

### 🎨 Interface and attachments

- **Attachments:** photos (4 MB client limit, compressed to 1024 px) and text files (100,000 characters each).
- **Localization:** English / Russian / Serbian.
- **Themes:** auto / light / dark (pure `#ffffff` and `#000000`) with the red accent `#d9534f`.

---

## 📸 Screenshots

*Main screen:*

![Main screen](https://raw.githubusercontent.com/FlowHack/flowslice-ai/master/assets/screenshot_chat.png)

*Settings, Models tab: providers, API keys and per-model parameters:*

![Settings, Models tab](https://raw.githubusercontent.com/FlowHack/flowslice-ai/master/assets/screenshot_models.png)

*Settings, General tab: context notes, default model parameters, compaction:*

![Settings, General tab](https://raw.githubusercontent.com/FlowHack/flowslice-ai/master/assets/screenshot_general.png)

*Chat in action:*

![Chat in action](https://raw.githubusercontent.com/FlowHack/flowslice-ai/master/assets/screenshot_reasoning.png)

---

## 📦 Installation

FlowSlice AI is distributed through **OrcaCloud**:

1. Subscribe to **FlowSlice AI** on [OrcaCloud Plugins](https://cloud.orcaslicer.com/app/plugins/plugin-hub).
2. In Orca Slicer open **File → Plugins**, install the plugin and enable the **FlowSlice AI** toggle.
3. Open the **FlowSlice AI** tab; restart Orca Slicer if it does not appear.

---

## 🚀 Quick start for beginners

Never used AI chats and APIs before? It takes a couple of minutes.

1. **Open the tab.** Find the **FlowSlice AI** tab in Orca Slicer and open it.
2. **Get an API key.** Pick any provider from the table below and create a key — it is free to start. For a first run **OpenRouter** is convenient: one key gives access to many models, and the `Auto` and `Free` routers pick a model for you.
3. **Add the key.** Open **Settings → Models**, select the provider, paste the key into **API key**, choose a **Model** and click **Save**.
4. **Ask a question.** Type a message and press **Enter**, for example "Check my PETG print settings and tell me what to improve.".
5. **Manage context.** Tick **Filament**, **Printer**, **Print settings**, **Model on the plate** or **Chat history**; per profile choose **changed** (only modified parameters, saves tokens) or **all**. The model has **brief**, **full** and **deep** modes; **Shift+Enter** adds a new line.
6. **You're done!** Use the chat like a messenger: create new chats, search and pin them.

---

## 🔑 Where to get an API key

Create keys in the providers' dashboards; paste them under **Settings → Models**.

| Provider | Key page |
| --- | --- |
| **DeepSeek** | https://platform.deepseek.com/api_keys |
| **OpenRouter** | https://openrouter.ai/keys |
| **Google Gemini** | https://aistudio.google.com/app/apikey |
| **Anthropic** | https://console.anthropic.com/settings/keys |
| **OpenAI** | https://platform.openai.com/api-keys |
| **Groq** | https://console.groq.com/keys |
| **Zhipu GLM** | https://open.bigmodel.cn/ |
| **Cerebras** | https://cloud.cerebras.ai/ |
| **Mistral** | https://console.mistral.ai/api-keys |
| **xAI** | https://console.x.ai/ |
| **NordRouter** | https://nordrouter.com/ |

> 🔒 The key is stored locally and sent only to the provider you selected.

---

## ⚙️ Settings

Settings open via the gear in the chat window and have four tabs.

| Tab | What you can configure |
| --- | --- |
| **Models** | Provider, API key, model, temperature, max tokens, reasoning mode, image support; **Refresh models**, **Delete selected model**. |
| **Custom** | Your own OpenAI/Anthropic-compatible providers: base URL, scheme, key, model ID, per-model parameters and prices. |
| **General** | Context compaction, context notes, default parameters, provider auto-refresh, reset models. |
| **Appearance** | Theme, font size and style, interface language. |

Empty per-model fields inherit the defaults (`temperature = 0.3`, `max_tokens = 8192`, reasoning off); with reasoning the limit is at least `16384`. Cost appears only when both prices are known; changes apply after **Save**.

---

## 🧠 Slicer context

| Checkbox | What it sends |
| --- | --- |
| **Model on the plate** | Dimensions, volume, surface area, triangles, position, manifold check, instances; **brief**, **full** and **deep** modes. |
| **Filament** | Material, temperatures, flow, cooling and notes. |
| **Printer** | Kinematics, nozzle, bed, limits and start/end G-code. |
| **Print settings** | Layers, perimeters, infill, speeds, supports. |
| **Chat history** | Previous messages of the current chat. |

Profiles export as **changed** (only parameters differing from the base preset) or **all**; checkboxes and modes are remembered per chat ("Brim type (brim_type)" labels: 823 settings, 753 Russian translations).

---

## 📎 Attachments and limits

- **Photos:** compressed to 1024 px JPEG and sent only to image-capable models; 4 MB per image, up to 10 images per request (20 MB base64).
- **Text files:** up to 100,000 characters per file, 400,000 total, readable by any model.
- Up to 10 attachments per message; 2 photos kept from history; 200 messages per chat; context window 128,000 tokens with auto-compaction at 80%.

---

## ⌨️ Commands

| Command | Description |
| --- | --- |
| `/context` | The exact request that will be sent, with a token estimate |
| `/compact` | Compress the chat history into a summary |
| `/clear` | Clear the current chat |
| `/model` | Model-on-the-plate report |
| `/printer` | Print-profile summary with readable labels |
| `/stats` | Usage statistics |
| `/reset` | Reset settings (`/reset chats` — clear chats) |

**Hotkeys:** `Enter` — send, `Shift+Enter` — new line.

---

## 🔐 Privacy & data

Only what is needed for an answer is sent.

**Sent:** the current chat's text and history; slicer data enabled by the context checkboxes (profile parameters, notes, start/end G-code, model statistics); attached photos and text files; the system instruction.

**Never sent:** your model file — only computed numeric statistics; printer credentials (`print_host`, `print_host_webui`, `printhost_apikey`, `printhost_user`, `printhost_password`, `printhost_cafile` and any key with `password`, `apikey`, `secret` or `token`) are filtered out even in the all-parameters mode; API keys never go to the model and are not stored in chat history; there is no telemetry or vendor server.

**Storage and network:** keys live in the plugin configuration and go only to the selected provider over HTTPS; chats are stored in `data_dir()/flowslice_ai/chats.json`; requests go straight to the provider, and the public OpenRouter catalog (`https://openrouter.ai/api/v1/models`) is fetched for prices and image support.

---

## 🔗 Links

- Author: [@FlowHack](https://github.com/FlowHack)
- Source code: [FlowHack/flowslice-ai](https://github.com/FlowHack/flowslice-ai)
- Issues: [FlowHack/flowslice-ai/issues](https://github.com/FlowHack/flowslice-ai/issues)
