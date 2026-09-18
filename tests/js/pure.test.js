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

if (failures > 0) {
  console.error(`Провалено проверок: ${failures}`);
  process.exit(1);
}
console.log("pure.test.js: все проверки пройдены");
