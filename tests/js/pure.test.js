"use strict";

/*
 * Юнит-тесты чистых функций интерфейса без DOM.
 *
 * app.js — IIFE, которая при загрузке лишь регистрирует обработчик
 * DOMContentLoaded и экспортирует чистые функции через window.FlowSlicePure.
 * Этого достаточно, чтобы выполнить модуль в песочнице node с заглушками
 * document/window и проверить реальную логику экранирования, ссылок и цен.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const appPath = path.join(__dirname, "..", "..", "flowslice_ai", "ui", "app.js");
const source = fs.readFileSync(appPath, "utf8");

const noop = function () {};
const sandbox = {
  console: console,
  setTimeout: noop,
  clearTimeout: noop,
  navigator: {},
  document: {
    addEventListener: noop,
    documentElement: { lang: "en" },
  },
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(source, sandbox, { filename: "app.js" });

const pure = sandbox.FlowSlicePure;
if (!pure) {
  throw new Error("window.FlowSlicePure не экспортирован");
}

let failures = 0;
function check(name, actual, expected) {
  if (actual !== expected) {
    failures += 1;
    console.error(`FAIL ${name}: получено ${JSON.stringify(actual)}, ожидалось ${JSON.stringify(expected)}`);
  }
}

// Экранирование HTML: ответ модели не должен исполняться как разметка.
check("escapeHtml теги", pure.escapeHtml("<b>&\"'"), "&lt;b&gt;&amp;&quot;&#39;");
check("escapeHtml null", pure.escapeHtml(null), "");

// Ссылки: допускаются только http/https/mailto.
check("safeHref http", pure.safeHref("https://example.com"), "https://example.com");
check("safeHref javascript", pure.safeHref("javascript:alert(1)"), "");
check("safeHref data", pure.safeHref("data:text/html,x"), "");

// Форматирование токенов.
check("formatTokens миллион", pure.formatTokens(1500000), "1.5M");
check("formatTokens тысячи", pure.formatTokens(2500), "2.5K");
check("formatTokens малое", pure.formatTokens(42), "42");

// Форматирование стоимости.
check("formatCost копейки", pure.formatCost(0.0012), "$0.0012");
check("formatCost ноль", pure.formatCost(0), "$0");
check("formatCost округление", pure.formatCost(1.5), "$1.5");

// Форматирование цены за 1М токенов.
check("formatPrice мелкая", pure.formatPrice(0.005), "0.005");
check("formatPrice ноль", pure.formatPrice(0), "0");
check("formatPrice обычная", pure.formatPrice(1.5), "1.50");

// Кнопка копирования кода присутствует и код экранирован.
const codeHtml = pure.codeBlockHtml("&lt;b&gt;x&lt;/b&gt;");
check("codeBlockHtml кнопка", codeHtml.indexOf('class="md-copy"') !== -1, true);
check("codeBlockHtml код", codeHtml.indexOf("<code>&lt;b&gt;x&lt;/b&gt;</code>") !== -1, true);

// Markdown: разметка строится, но HTML из ответа модели не исполняется.
const heading = pure.renderMarkdown("# Заголовок");
check("renderMarkdown заголовок", heading, "<h1>Заголовок</h1>");
const fenced = pure.renderMarkdown("```\n<b>x</b>\n```");
check("renderMarkdown блок кода", fenced.indexOf('class="md-code-wrap"') !== -1, true);
check("renderMarkdown экранирование кода", fenced.indexOf("<code>&lt;b&gt;x&lt;/b&gt;</code>") !== -1, true);
const injected = pure.renderMarkdown("<script>alert(1)</script>");
check("renderMarkdown запрет script", injected.indexOf("<script>") === -1, true);
const list = pure.renderMarkdown("- один\n- два");
check("renderMarkdown список", list, "<ul><li>один</li><li>два</li></ul>");

// Поиск по моделям: порядок слов не важен, слово может быть префиксом.
check("поиск фраза", pure.matchesModelQuery("Free Models Router", "free models"), true);
check("поиск перестановка", pure.matchesModelQuery("Free Models Router", "router free"), true);
check("поиск префикс", pure.matchesModelQuery("Free Models Router", "free r"), true);
check("поиск кириллица перестановка", pure.matchesModelQuery("Модель Быстрая", "быстрая модель"), true);
check("поиск нет совпадений", pure.matchesModelQuery("Free Models Router", "gpt"), false);
check("поиск пустой запрос", pure.matchesModelQuery("Free Models Router", "  "), true);
check(
  "поиск по полному id",
  pure.matchesModelQuery("Qwen: Qwen3.8 27B (free)", "qwen/qwen3.8-27b:free"),
  true
);
check("поиск по id с автором", pure.matchesModelQuery("Qwen3.8 27B", "qwen/qwen3.8-27b"), true);
check(
  "поиск версии через пробел",
  pure.matchesModelQuery("Qwen: Qwen3.7 Flash", "qwen 3.7"),
  true
);
check(
  "поиск версии по полному id",
  pure.matchesModelQuery("Qwen: Qwen3.7 Flash", "qwen/qwen3.7-flash"),
  true
);

// Раскрытие блока размышлений: только у последнего assistant-сообщения во время стрима.
const streamMsgs = [
  { role: "user", text: "вопрос" },
  { role: "assistant", text: "", reasoning: "размышляю" },
];
check("reasoning последнее при стриме", pure.shouldOpenReasoning(streamMsgs[1], 1, streamMsgs, "streaming"), true);
check("reasoning не последнее", pure.shouldOpenReasoning(streamMsgs[0], 0, streamMsgs, "streaming"), false);
check("reasoning без стрима", pure.shouldOpenReasoning(streamMsgs[1], 1, streamMsgs, "idle"), false);
check("reasoning не assistant", pure.shouldOpenReasoning({ role: "user" }, 0, [{ role: "user" }], "streaming"), false);
check("reasoning пустой список", pure.shouldOpenReasoning({ role: "assistant" }, 0, [], "streaming"), false);
check("reasoning без msg", pure.shouldOpenReasoning(null, 0, streamMsgs, "streaming"), false);

// Метки времени: Python присылает секунды, JS — миллисекунды.
check("toMillis секунды", pure.toMillis(1789809720), 1789809720000);
check("toMillis миллисекунды", pure.toMillis(1789809720000), 1789809720000);
check("toMillis ноль", pure.toMillis(0), 0);
check("toMillis мусор", pure.toMillis("нет"), 0);

// Ссылки на модели для избранного: "provider::model".
check("favoriteRef", pure.favoriteRef("deepseek", "deepseek-chat"), "deepseek::deepseek-chat");
check("favoriteRef числа", pure.favoriteRef(1, 2), "1::2");

check(
  "parseModelRef обычная",
  JSON.stringify(pure.parseModelRef("deepseek::deepseek-chat")),
  JSON.stringify({ provider: "deepseek", model: "deepseek-chat" })
);
check(
  "parseModelRef первый разделитель",
  JSON.stringify(pure.parseModelRef("a::b::c")),
  JSON.stringify({ provider: "a", model: "b::c" })
);
check(
  "parseModelRef обрезка пробелов",
  JSON.stringify(pure.parseModelRef("  deepseek :: deepseek-chat  ")),
  JSON.stringify({ provider: "deepseek", model: "deepseek-chat" })
);
check("parseModelRef без разделителя", pure.parseModelRef("deepseek-chat"), null);
check("parseModelRef пустой провайдер", pure.parseModelRef("::model"), null);
check("parseModelRef пустая модель", pure.parseModelRef("provider::"), null);
check("parseModelRef не строка", pure.parseModelRef(null), null);
check("parseModelRef число", pure.parseModelRef(42), null);

// Заполнение истории до автосжатия: процент 0..100, устойчив к мусору.
check("contextFillPercent обычный", pure.contextFillPercent(50, 100), 50);
check("contextFillPercent ноль истории", pure.contextFillPercent(0, 100), 0);
check("contextFillPercent ноль порога", pure.contextFillPercent(50, 0), 0);
check("contextFillPercent превышение", pure.contextFillPercent(250, 100), 100);
check("contextFillPercent мусор", pure.contextFillPercent("нет", "нет"), 0);
check("contextFillPercent отрицательные", pure.contextFillPercent(-10, 100), 0);
check("contextFillPercent округление", pure.contextFillPercent(1, 3), 33);
check("contextFillPercent undefined", pure.contextFillPercent(undefined, undefined), 0);

if (failures > 0) {
  console.error(`Провалено проверок: ${failures}`);
  process.exit(1);
}
console.log("pure.test.js: все проверки пройдены");
