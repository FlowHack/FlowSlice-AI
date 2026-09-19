# FlowSlice AI

<p align="center">
  <img src="https://raw.githubusercontent.com/FlowHack/flowslice-ai/master/assets/preview.png" width="280" alt="FlowSlice AI">
</p>

<p align="center">
  <b>An AI 3D-printing engineer right inside Orca Slicer.</b><br>
  It sees your model, profiles and print history, and helps with mechanics, Klipper and material fine-tuning.
</p>

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

<table>
<tr>
<td width="50%" valign="top">

### 💬 Chat
- Streaming responses (SSE) — text appears as it is generated
- Stop generation, regenerate
- Edit & resend
- Regenerate any answer

### 🗂 Multi-chat
- Unlimited conversations
- Automatic titles from the first question
- Chat history search
- Pin important chats
- History saved between sessions
- Up to 200 messages per chat

</td>
<td width="50%" valign="top">

### 🧠 Slicer context
- Model on the plate: dimensions, volume, surface area, triangles, position, mesh integrity (manifold), instances
- Printer, filament and print profiles
- Full parameter dump or only changed vs. the base preset
- Profile notes and start/end G-code
- Context checkboxes right in the chat panel, remembered per chat

### 🔌 Providers & models
- 11 built-in providers out of the box
- Your own OpenAI/Anthropic-compatible providers
- Model catalog sync: "Refresh from provider" button and auto-refresh
- Per-model tuning: temperature, max tokens, reasoning mode
- Default model and per-model notes
- Usage statistics (📊)

</td>
</tr>
</table>

- **Attachments:** photos (up to 4 MB on the client, compressed to 1024 px) and text files (up to 100,000 characters each, 400,000 in total).
- **Localization:** English / Russian / Serbian (English by default).
- **Themes:** auto (native Orca) / pure white / pure black, signature red accent `#d9534f`.

---

## 🧩 Requirements

| Component | Version |
| --- | --- |
| Orca Slicer | with Python plugin support (2.x branch) |
| OS | Windows / Linux / macOS (x64, macOS arm64) |
| Python | 3.12+ (bundled with Orca Slicer) |
| numpy | optional (extra `deep`) — enables deep model geometry analysis; the plugin works without it |
| Internet | required to reach the selected provider's API |

### 📦 Installation

FlowSlice AI is distributed through **OrcaCloud**:

1. Subscribe to **FlowSlice AI** on OrcaCloud.
2. After subscribing, the plugin appears among the available plugins in Orca Slicer — install and enable it.
3. Open the **FlowSlice AI** tab in Orca Slicer.
4. Restart Orca Slicer if the tab does not appear right away.

> No separate `.whl` installation is required — everything is done from the interface.

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
The chat panel has **Model**, **Filament**, **Printer**, **Print settings** and **History** checkboxes.
Tick what the assistant should take into account. Each profile has a dropdown next to it:

- **changed** — send only the parameters you changed (saves tokens);
- **all** — send the full profile.

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
| **Models** | Provider, API key, model, temperature, max tokens, reasoning mode. The **Refresh from provider** button and the trash icon sit next to it. |
| **Custom** | Your own OpenAI/Anthropic-compatible providers and models: base URL, API scheme, key, model ID and name. |
| **General** | Notes for the context, default temperature / max tokens / reasoning mode; provider auto-refresh (`auto_sync_providers`); reset models. |
| **Appearance** | Theme (auto / white / black), font size and style, interface language. |

- Model values can be tuned individually; if a field is left empty, the general defaults apply
  (`temperature = 0.7`, `max_tokens = 4096`, reasoning off by default).
- The **Reset** button affects only the current tab.
- The **General** tab has **Reset models** and **Reset custom models**.
- Changes apply only after clicking **Save**.

---

## 🔄 Model catalog sync

- Every provider has a **Refresh from provider** button. It loads the provider's full model list into
  a session cache — the config does not grow. Names, prices and the image-support flag are refreshed.
- The **Auto-refresh providers** checkbox (`auto_sync_providers`) is on by default and runs on plugin
  start and after an API key is saved.
- **Prices** come from the specific provider: OpenRouter uses its own pricing catalog, NordRouter uses
  its public price list.
- **Image support** is derived from the OpenRouter catalog with the provider prefix (for every
  provider except OpenRouter itself).
- When a model is added or imported, its metadata is requested from the provider immediately.
- Manual values and `temperature` / `max_tokens` / `reasoning` are never overwritten by auto-sync.

---

## 🧠 Slicer context

The context panel in the chat decides what the assistant learns about your project:

| Checkbox | What it sends |
| --- | --- |
| **Model** | Dimensions, volume, surface area, triangle count, position on the plate, mesh integrity (manifold), number of instances. |
| **Filament** | Filament profile: material, temperatures, flow, cooling and notes. |
| **Printer** | Printer profile: kinematics, nozzle, bed, limits and start/end G-code. |
| **Print settings** | Process profile: layers, perimeters, infill, speeds, supports. |
| **History** | Previous messages of the current chat. |

For profiles, two export modes are available: **changed** (only the parameters changed relative to the
base preset) and **all** (the full profile). Selected checkboxes and modes are remembered per chat.

---

## 📎 Attachments and limits

- **Photos:** attach a photo of a print defect or a part. The image is compressed to 1024 px (JPEG)
  and sent only to models that support images. The client limit is 4 MB per image, the server limit is
  6 MB base64. If the selected model does not support images, the plugin tells you and does not send
  the file.
- **Text files:** the file contents (up to 100,000 characters per file, 400,000 in total) are added to
  the message as plain text, so they work with any model.
- **Count:** up to 10 attachments per message, including up to 10 images per request.

> To analyze photos, choose an image-capable model, e.g. via OpenRouter (`Auto`, `Free` or a specific
> vision model).

### Limits and auto-compaction

| Parameter | Value |
| --- | --- |
| Attachments per message | up to 10 |
| Images per request | up to 10 |
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
| `/context` | Show slicer context (model, profiles, checkboxes, history) |
| `/compact` | Compress the chat history into a short summary (manually) |
| `/clear` | Clear the current chat |
| `/model` | Show the model-on-the-plate report |
| `/printer` | Show the print-profile summary |
| `/stats` | Show usage statistics |
| `/help` | List commands |
| `/reset` | Reset plugin settings (`/reset chats` — clear chats) |

**Hotkeys:** `Enter` — send, `Shift+Enter` — new line.

---

## 🔐 Privacy & data

- **API keys** are stored in the Orca Slicer plugin configuration and are sent only to the server of
  the provider you selected.
- **Chat history** is stored locally: `data_dir()/flowslice_ai/chats.json`.
- **The plugin has no telemetry** and sends no data anywhere except the API request to the selected
  model.
- Requests go directly from your computer to the provider (no intermediate servers).

---

## ❓ FAQ

<details>
<summary><b>The plugin tab did not appear.</b></summary>

Make sure the plugin subscription is active on OrcaCloud and the plugin is enabled in the Orca Slicer
plugin list. Restart Orca Slicer. Check that your Orca Slicer version supports Python plugins (2.x
branch).
</details>

<details>
<summary><b>"API key missing" or "invalid key" error.</b></summary>

Open **Settings → Models**, check that the key was pasted without extra spaces, and click the key
check button. Make sure the provider account has funds on balance.
</details>

<details>
<summary><b>The model does not accept photos.</b></summary>

The selected model does not support images. Choose a vision model (e.g. via OpenRouter) — the plugin
will warn you automatically if a model cannot handle images.
</details>

<details>
<summary><b>Responses are cut off or arrive slowly.</b></summary>

Check your internet connection and the provider limits. Try increasing **Max tokens** in the model
settings or choose a faster provider (e.g. Groq or Cerebras).
</details>

<details>
<summary><b>Where is the chat history stored?</b></summary>

In `data_dir()/flowslice_ai/chats.json` inside the Orca Slicer data directory.
</details>

<details>
<summary><b>Can I use my own server?</b></summary>

Yes. On the **Custom** tab, add your own provider: specify the base URL, API scheme (OpenAI- or
Anthropic-compatible), key and model ID.
</details>

<details>
<summary><b>What if the model list is out of date?</b></summary>

Click **Refresh from provider** next to the provider, or enable **Auto-refresh providers** on the
**General** tab — the catalog, prices and image-support flag will update automatically.
</details>
