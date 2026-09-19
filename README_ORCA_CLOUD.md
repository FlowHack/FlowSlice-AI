# FlowSlice AI

**An AI 3D-printing engineer right inside Orca Slicer.**
It sees your model, profiles and print history, and helps with mechanics, Klipper and material fine-tuning.

## 📖 Contents

- [What it is](#-what-it-is)
- [Features](#-features)
- [Screenshots](#-screenshots)
- [Installation](#-installation)
- [Quick start for beginners](#-quick-start-for-beginners)
- [Where to get an API key](#-where-to-get-an-api-key)
- [Settings](#-settings)
- [Model catalog sync](#-model-catalog-sync)
- [Slicer context](#-slicer-context)
- [Attachments and limits](#-attachments-and-limits)
- [Commands](#-commands)
- [Privacy & data](#-privacy--data)
- [FAQ](#-faq)
- [Links](#-links)

---

## 🤖 What it is

**FlowSlice AI** is an assistant plugin for [Orca Slicer](https://github.com/OrcaSlicer/OrcaSlicer).
It adds a dedicated chat tab where an AI 3D-printing engineer answers. The assistant works with your
slicer context, so its advice is specific to your model, your printer and your material — not generic
tips.

What the assistant can do:

- explain print defects and tell you which settings to change and where;
- help with calibration (flow, Pressure Advance, retraction, first layer);
- advise on mechanics, firmware (Klipper, Marlin) and printer maintenance;
- compare materials (PLA, PETG, ABS, TPU, etc.) for a specific task;
- analyze photos of defects when an image-capable model is selected.

> 💡 **Example.** "Why is there bulging on the corners? I use PETG on an Ender-3." — the assistant
> will see your profile, temperature, speed and flow and give concrete values to change.

---

## ✨ Features

### 💬 Chat

- Streaming responses (SSE) — text appears as it is generated
- Reasoning blocks for reasoning models: expandable, open while streaming and auto-collapsed when the answer is done (chevron, red live highlight). Supported for OpenRouter (`delta.reasoning`), DeepSeek and Anthropic
- Stop generation; an empty reply is marked as interrupted by the user, while already received text is kept as is
- Regenerate the last reply
- Edit and resend any of your messages (edit & resend)
- Answer variants with switching between them

### 🗂 Multi-chat

- Unlimited conversations
- Automatic titles from the first question
- Chat history search
- Pin important chats
- History saved between sessions
- Up to 200 messages per chat
- The selected model is remembered per chat and restored on restart, with a footnote showing the model that produced each answer

### 🧠 Slicer context

- Model on the plate: dimensions, volume, surface area, triangles, position, mesh integrity (manifold), instances
- Printer, filament and print profiles
- Full parameter dump or only changed vs. the base preset
- Human-readable, localized parameter names, e.g. "Brim type (brim_type)" — 823 OrcaSlicer settings with 753 Russian translations (English and Russian)
- Profile notes and start/end G-code
- Context checkboxes right in the chat panel, remembered per chat

### 🔌 Providers & models

- 11 built-in providers out of the box
- Your own OpenAI/Anthropic-compatible providers
- Favorite models: a pinned "Favorites" group and a ♥ button; the choice is kept across restarts
- Model catalog sync: "Refresh models" button and auto-refresh
- Model search independent of word order (finds full ids with `/` and `:` and versions like `3.7`)
- Per-model tuning: temperature, max tokens, reasoning mode, image support
- Default model (a star in the model list)
- Tokens come from provider usage when it is reported (OpenRouter together with the real `cost`, Anthropic with exact token counts), otherwise they are estimated; automatic fallback on HTTP 400. Cost is shown only when both input and output prices are known
- Usage statistics (📊)

Other:

- **Attachments:** photos (up to 4 MB on the client, compressed to 1024 px; 20 MB base64 total per request) and text files (up to 100,000 characters each, 400,000 in total).
- **Localization:** English / Russian / Serbian (English by default).
- **Themes:** auto (native Orca) / light / dark (pure white `#ffffff` and black `#000000`), signature red accent `#d9534f`.

---

## 📸 Screenshots

*Main screen:*

![Main screen](https://raw.githubusercontent.com/FlowHack/flowslice-ai/master/assets/screenshot_chat.png)

*Settings, Models tab: providers, API keys and per-model parameters (temperature, tokens, reasoning, vision):*

![Settings, Models tab: providers, API keys and per-model parameters](https://raw.githubusercontent.com/FlowHack/flowslice-ai/master/assets/screenshot_models.png)

*Settings, General tab: context notes, default model parameters, context compaction, provider auto-refresh and data reset:*

![Settings, General tab: context notes, default model parameters, compaction](https://raw.githubusercontent.com/FlowHack/flowslice-ai/master/assets/screenshot_general.png)

*Chat in action:*

![Chat in action](https://raw.githubusercontent.com/FlowHack/flowslice-ai/master/assets/screenshot_reasoning.png)

---

## 📦 Installation

FlowSlice AI is distributed through **OrcaCloud**:

1. Subscribe to **FlowSlice AI** on OrcaCloud.
2. After subscribing, the plugin appears in Orca Slicer under **File → Plugins** — install it.
3. Enable the **FlowSlice AI** toggle in the plugins list.
4. Open the **FlowSlice AI** tab in Orca Slicer.
5. Restart Orca Slicer if the tab does not appear right away.

> Installation is done entirely from the interface.

---

## 🚀 Quick start for beginners

Never used AI chats and APIs before? Follow the steps — it takes a couple of minutes.

### Step 1. Open the plugin tab

After installation, find the **FlowSlice AI** tab in Orca Slicer and open it.

### Step 2. Get an API key

Pick any provider from the [table below](#-where-to-get-an-api-key), sign up and create an API key.
It is free to start — almost all providers offer a trial quota.

### Step 3. Add the key to the plugin

1. Click the **Settings** button (gear) in the chat window.
2. Open the **Models** tab.
3. In the **Provider** dropdown, select the provider you got the key from.
4. Paste the key into the **API key** field. The eye button reveals hidden text.
5. Select a **Model** from the list.
6. Click **Save**.

> 🔰 **Beginner tip.** For your first run, **OpenRouter** is a convenient choice — one key gives
> access to many models from different vendors. The `Auto`, `Auto (beta)` and `Free` routers pick a
> suitable model for you.

### Step 4. Ask your first question

Type a message and press **Enter**. For example:

- "Check my PETG print settings and tell me what to improve."
- "Why does the first layer not stick well?"
- "What is Pressure Advance and how do I tune it on Klipper?"
- "Compare TPU and PETG for flexible parts."
- "Recommend nozzle and bed temperature for my filament."

### Step 5. Manage context

The chat panel has **Filament**, **Printer**, **Print settings**, **Model on the plate** and **Chat history** checkboxes.
Tick what the assistant should take into account. Each profile has a dropdown next to it:

- **changed** — send only the parameters you changed (saves tokens);
- **all** — send the full profile.

The model has its own modes: **brief**, **full** and **deep**.

Press **Enter** to send and **Shift+Enter** for a new line.

### Step 6. You're done!

Use the chat like a regular messenger. History is saved; you can create new chats, search them and pin
the important ones.

---

## 🔑 Where to get an API key

All keys are created in the providers' personal dashboards. The **API key** field is under
**Settings → Models**.

| Provider | Where to get the key | Note |
| --- | --- | --- |
| **DeepSeek** | https://platform.deepseek.com/api_keys | inexpensive, great for text |
| **OpenRouter** | https://openrouter.ai/keys | one key — many models, free options |
| **Google Gemini** | https://aistudio.google.com/app/apikey | free tier available |
| **Anthropic** | https://console.anthropic.com/settings/keys | Claude models |
| **OpenAI** | https://platform.openai.com/api-keys | GPT models |
| **Groq** | https://console.groq.com/keys | very high speed |
| **Zhipu GLM** | https://open.bigmodel.cn/ | GLM models |
| **Cerebras** | https://cloud.cerebras.ai/ | fast inference |
| **Mistral** | https://console.mistral.ai/api-keys | Mistral models |
| **xAI** | https://console.x.ai/ | Grok models |
| **NordRouter** | https://nordrouter.com/ | OpenAI-compatible aggregator, public price list |

> 🔒 The key is stored locally in the Orca Slicer plugin settings and is sent only to the server of
> the provider you selected. The plugin never forwards it to third parties.

---

## ⚙️ Settings

Settings open via the gear in the chat window and are split into four tabs.

| Tab | What you can configure |
| --- | --- |
| **Models** | Provider, API key, model, temperature, max tokens, reasoning mode, image support. The **Refresh models** and **Delete selected model** buttons sit next to it. |
| **Custom** | Your own OpenAI/Anthropic-compatible providers and models: base URL, API scheme, key, model ID and name, plus per-model temperature / max tokens / reasoning mode / vision / prices. |
| **General** | Context compaction (`compact_enabled`, threshold %, window size, number of photos kept from history); notes for the context, default temperature / max tokens / reasoning mode; provider auto-refresh (`auto_sync_providers`); reset models. |
| **Appearance** | Theme (auto / light / dark), font size 10–20 and style (system / mono / serif), interface language. |

- Model values can be tuned individually; if a field is left empty, the general defaults apply
  (`temperature = 0.3`, `max_tokens = 8192`, reasoning off by default). When reasoning is enabled, the
  inherited token limit is never lower than `16384` so the model has room to think; a per-model
  `max_tokens` you set yourself is not raised.
- Prices for input and output tokens apply to custom models and are used to show the cost of a reply;
  the cost appears only when both prices are known. Tokens and cost come from the provider when
  available and are estimated otherwise.
- The **Reset** button affects only the current tab.
- The **General** tab has **Reset models** and **Reset custom models**.
- Changes apply only after clicking **Save**.

---

## 🔄 Model catalog sync

- Every provider has a **Refresh models** button. It loads the provider's full model list into
  a session cache — the config does not grow. Names, prices and the image-support flag are refreshed.
- The **Auto-refresh providers** checkbox (`auto_sync_providers`) is on by default. Auto-sync starts
  lazily (when the provider list is built in the UI) and after an API key is saved; it walks providers
  that have a key plus OpenRouter and NordRouter, which are always checked. New models are not added —
  only existing ones are updated.
- Model search does not depend on word order: full ids with `/` and `:` and versions like `3.7` are
  found without separators.
- **Favorite models** are collected in a pinned **Favorites** group at the top of the model list and
  toggled with the ♥ button. The selection is stored in the config and survives restarts.
- **Prices** come from the specific provider: OpenRouter uses its own pricing catalog, NordRouter uses
  its public price list; for the other providers prices are set manually.
- **Image support** comes from the provider's own catalog first (Google, Anthropic, Mistral, xAI),
  with the OpenRouter catalog as a fallback.
- When a model is added or imported, its metadata is requested from the provider immediately.
- Manual values and `temperature` / `max_tokens` / `reasoning` are never overwritten by auto-sync.

---

## 🧠 Slicer context

The context panel in the chat decides what the assistant learns about your project:

| Checkbox | What it sends |
| --- | --- |
| **Model on the plate** | Dimensions, volume, surface area, triangle count, position on the plate, mesh integrity (manifold), number of instances. The model has **brief**, **full** and **deep** modes. |
| **Filament** | Filament profile: material, temperatures, flow, cooling and notes. |
| **Printer** | Printer profile: kinematics, nozzle, bed, limits and start/end G-code. |
| **Print settings** | Process profile: layers, perimeters, infill, speeds, supports. |
| **Chat history** | Previous messages of the current chat. |

For profiles, two export modes are available: **changed** (only the parameters changed relative to the
base preset) and **all** (the full profile). Selected checkboxes and modes are remembered per chat.

Parameter keys are enriched with interface labels before they are sent, so the model writes
"Brim type (brim_type)" instead of the internal key. The dictionary covers 823 OrcaSlicer settings;
753 of them have Russian translations. For Serbian, parameter labels are taken from the English table
as a fallback.

---

## 📎 Attachments and limits

- **Photos:** attach a photo of a print defect or a part. The image is compressed to 1024 px (JPEG)
  and sent only to models that support images. The client limit is 4 MB per image, the server limit is
  6 MB base64. If the selected model does not support images, the plugin tells you and does not send
  the file.
- **Text files:** the file contents (up to 100,000 characters per file, 400,000 in total) are added to
  the message as plain text, so they work with any model. When the history is saved, long text
  attachments are truncated.
- **Count:** up to 10 attachments per message, including up to 10 images per request (20 MB base64 in
  total).

> To analyze photos, choose an image-capable model, e.g. via OpenRouter (`Auto`, `Free` or a specific
> vision model).

### Limits and auto-compaction

| Parameter | Value |
| --- | --- |
| Attachments per message | up to 10 |
| Images per request | up to 10 |
| Total images per request | up to 20 MB base64 |
| Photos kept from history | up to 2 |
| Single image | 1024 px, JPEG; client 4 MB, server 6 MB base64 |
| Text attachment | 100,000 characters; 400,000 in total |
| Messages per chat | up to 200 |
| Context window | 128,000 tokens |
| Auto-compaction | at 80% of the window (can be disabled in settings) |

---

## ⌨️ Commands

Type a command in the chat input and press **Enter**.

| Command | Description |
| --- | --- |
| `/context` | Show the actual message list that will be sent to the model (full system prompt, history, images summarized) and an estimated token count of that request |
| `/compact` | Compress the chat history into a short summary (manually) |
| `/clear` | Clear the current chat |
| `/model` | Show the model-on-the-plate report |
| `/printer` | Show the print-profile summary with human-readable parameter labels |
| `/stats` | Show usage statistics |
| `/help` | List commands |
| `/reset` | Reset plugin settings (`/reset chats` — clear chats) |

**Hotkeys:** `Enter` — send, `Shift+Enter` — new line.

---

## 🔐 Privacy & data

The plugin follows a simple rule: only what is needed for an answer is sent. Below is exactly what
leaves your machine and what never does.

### What is sent to the AI provider

- The text of your messages and the history of the current chat, within the context you enabled.
- Slicer data enabled by the checkboxes in the chat panel:
  - profile parameters (only those changed from the base preset, or all of them, depending on your export mode);
  - profile notes and start/end G-code when those sections are enabled;
  - model statistics: dimensions, volume, surface area, triangle count, position, mesh integrity
    (manifold) and instance count; the `deep` analysis mode adds further geometric metrics.
- Photos you attach (compressed to 1024 px) and text files.
- The plugin system instruction and the selected request options.

### What is never sent

- **Your model file never leaves your machine.** Only computed numeric statistics are transmitted,
  never the geometry or the file itself.
- **Printer credentials** (`print_host`, `print_host_webui`, `printhost_apikey`, `printhost_user`,
  `printhost_password`, `printhost_cafile` and any key containing `password`, `apikey`, `secret` or
  `token`) are filtered out during context collection, including in the all-parameters export mode.
- **Provider API keys** are never sent to the model and never stored in chat history.
- There is no telemetry, analytics, sign-up or vendor server.

### Where data is stored

- **API keys** live in the Orca Slicer plugin configuration on your computer and are sent only to the
  server of the provider you selected, over HTTPS.
- **Chat history** is stored locally in `data_dir()/flowslice_ai/chats.json`; you can clear it with
  the `/clear` command or by deleting a chat.
- **Settings and usage statistics** are stored locally through the official Orca Slicer configuration API.

### Network requests

- API requests go directly from your computer to the selected provider, with no intermediate servers.
- To keep prices and image-support flags up to date, the plugin downloads the public OpenRouter model
  catalog (`https://openrouter.ai/api/v1/models`). That request carries no keys and no user data.

The donation details are static addresses hard-coded in the plugin; copying them sends nothing anywhere.

---

## ❓ FAQ

| Question | Answer |
| --- | --- |
| The plugin tab did not appear. | Make sure the plugin subscription is active on OrcaCloud and the plugin is enabled in the Orca Slicer plugin list. Restart Orca Slicer. Check that your Orca Slicer version supports Python plugins (2.x branch). |
| "API key missing" or "invalid key" error. | Open **Settings → Models**, check that the key was pasted without extra spaces, and click the key check button. Make sure the provider account has funds on balance. |
| The model does not accept photos. | The selected model does not support images. Choose a vision model (e.g. via OpenRouter) — the plugin will warn you automatically if a model cannot handle images. |
| Responses are cut off or arrive slowly. | Check your internet connection and the provider limits. Try increasing **Max tokens** in the model settings or choose a faster provider (e.g. Groq or Cerebras). For reasoning models the inherited limit is raised to at least `16384` automatically; a per-model **Max tokens** value you set yourself is not increased. |
| Where is the chat history stored? | In `data_dir()/flowslice_ai/chats.json` inside the Orca Slicer data directory. |
| Can I use my own server? | Yes. On the **Custom** tab, add your own provider: specify the base URL, API scheme (OpenAI- or Anthropic-compatible), key and model ID. |
| What if the model list is out of date? | Click **Refresh models** next to the provider, or enable **Auto-refresh providers** on the **General** tab — the catalog, prices and image-support flag will update automatically. |

---

## 🔗 Links

- Author: [@FlowHack](https://github.com/FlowHack)
- Source code: [FlowHack/flowslice-ai](https://github.com/FlowHack/flowslice-ai)
- Questions and bug reports: [Issues](https://github.com/FlowHack/flowslice-ai/issues)
