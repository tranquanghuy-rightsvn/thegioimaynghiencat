#!/usr/bin/env node
/**
 * Chạy thử phần client của CMS (gas/js.html) trong Node với DOM giả, để bắt lỗi khi tải trang
 * TRƯỚC khi deploy lên Apps Script. Lỗi kinh điển hay tái phát:
 *   "ReferenceError: Cannot access 'X' before initialization"
 * = code chạy ngay lúc tải (vd bootApp() vẽ từ cache) gọi tới hàm dùng const/let khai báo PHÍA
 * DƯỚI trong file. Script này chạy mọi đường tải trang có thể xảy ra (chưa đăng nhập; đã đăng
 * nhập + có cache, với từng quyền; mở từng tab) - lỗi nào ném ra là fail.
 *
 * Dùng: node scripts/check_gas_client.mjs   (exit 0 = ổn, exit 1 = có lỗi, in chi tiết)
 * Được gọi tự động bởi hook trong .claude/settings.json mỗi khi sửa file trong gas/.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const jsHtml = readFileSync(process.argv[2] || join(root, "gas/js.html"), "utf8");
const appHtml = readFileSync(join(dirname(process.argv[2] || join(root, "gas/js.html")), "app.html"), "utf8");

// Chỉ lấy các <script> inline (bỏ <script src=...> như TinyMCE).
const inlineScripts = [...jsHtml.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
if (!inlineScripts.length) {
  console.error("check_gas_client: không tìm thấy <script> inline nào trong js.html");
  process.exit(1);
}
const code = inlineScripts.join("\n;\n");

const CLIENT_BUILD = "check";
// Lấy đúng tiền tố localStorage của dự án từ chính js.html (dùng chung được cho mọi dự án cùng mô hình).
const LS_PREFIX = (code.match(/const\s+LS_PREFIX\s*=\s*["']([^"']+)["']/) || [])[1] || "cms_";

/** Phần tử DOM giả: thuộc tính nào cũng đọc/ghi được, method nào cũng gọi được. */
function fakeElement(id) {
  const store = {
    id: id || "",
    value: "",
    textContent: "",
    innerHTML: "",
    className: "",
    disabled: false,
    style: {},
    dataset: {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    children: [],
    getAttribute: () => null,
    setAttribute() {},
    addEventListener() {},
    removeEventListener() {},
    appendChild: (c) => c,
    querySelector: () => fakeElement(),
    querySelectorAll: () => [],
    closest: () => null,
    focus() {},
    click() {},
    remove() {},
  };
  return new Proxy(store, {
    get(target, prop) {
      if (prop in target) return target[prop];
      if (typeof prop === "symbol") return undefined;
      return () => fakeElement();
    },
    set(target, prop, value) {
      target[prop] = value;
      return true;
    },
  });
}

function makeContext(lsSeed) {
  const elements = new Map();
  const errors = [];
  const ls = new Map(Object.entries(lsSeed));
  const localStorage = {
    getItem: (k) => (ls.has(k) ? ls.get(k) : null),
    setItem: (k, v) => ls.set(k, String(v)),
    removeItem: (k) => ls.delete(k),
    key: (i) => [...ls.keys()][i] ?? null,
    get length() { return ls.size; },
  };
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, fakeElement(id));
      return elements.get(id);
    },
    querySelector: () => fakeElement(),
    querySelectorAll: () => [],
    createElement: () => fakeElement(),
    addEventListener() {},
    body: fakeElement("body"),
  };
  // google.script.run.withSuccessHandler(..).withFailureHandler(..)[name](...) - không bao giờ
  // trả kết quả (chỉ kiểm tra đường tải trang đồng bộ + từ cache).
  const run = new Proxy({}, {
    get(_, prop) {
      if (prop === "withSuccessHandler" || prop === "withFailureHandler" || prop === "withUserObject") return () => run;
      return () => undefined;
    },
  });
  const listeners = {};
  const window = {
    CLIENT_BUILD,
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
    removeEventListener() {},
  };
  const ctx = {
    window,
    document,
    localStorage,
    google: { script: { run } },
    tinymce: { init: () => Promise.resolve([]), get: () => null, remove() {} },
    location: { reload() {}, href: "" },
    console: { log() {}, warn() {}, info() {}, error: (...a) => errors.push(a.map(String).join(" ")) },
    setTimeout: () => 0,
    clearTimeout() {},
    requestAnimationFrame: () => 0,
    Image: function () {},
    URL: { createObjectURL: () => "" },
    Promise, JSON, Math, Date, Object, Array, String, Number, Boolean, RegExp, Error, Map, Set,
  };
  window.document = document;
  window.localStorage = localStorage;
  ctx.globalThis = ctx;
  return { ctx: vm.createContext(ctx), errors, listeners };
}

function lsSeedLoggedIn(role) {
  return {
    [LS_PREFIX + "token"]: "fake-token",
    [LS_PREFIX + "boot_cache_" + CLIENT_BUILD]: JSON.stringify({
      me: { email: "me@example.com", role },
      appHtml: appHtml,
      posts: [{ slug: "bai-a", title: "Bài A", section: "cat-a", description: "", date: "2026-01-01T00:00:00+00:00", thumb: "assets/img/a.webp", tags: ["t-a"] }],
      menu: {
        groups: [{ key: "g", label: "Nhóm G", landing: "/g/", nav: "g", base: "/g/", order: 1, builtin: true, intro: "", links: [{ name: "L", path: "/l/" }] }],
        categories: [{ key: "cat-a", parent: "g", name: "Danh mục A", path: "/g/cat-a/", intro: "", order: 1, products: ["Máy A"], capacity: true, flow: [["a", "b"]], project_kw: ["x"] }],
      },
      tags: { "t-a": "Tag A" },
      catalog: ["Máy A", "Máy B"],
      github: { owner: "o", repo: "r", branch: "master" },
    }),
    [LS_PREFIX + "users_" + CLIENT_BUILD]: JSON.stringify([
      { email: "me@example.com", role, hasPassword: true },
      { email: "editor@example.com", role: "editor", hasPassword: false },
      { email: "admin@example.com", role: "admin", hasPassword: true },
    ]),
  };
}

// Mọi tab có trong app.html (data-tab="...") - mở thử từng tab sau khi tải xong.
const tabs = [...new Set([...appHtml.matchAll(/data-tab="([^"]+)"/g)].map((m) => m[1]))];

const scenarios = [
  { name: "chưa đăng nhập", seed: {} },
  ...["editor", "admin", "root"].map((role) => ({ name: "đã đăng nhập + có cache (" + role + ")", seed: lsSeedLoggedIn(role), tabs: true })),
];

const failures = [];
for (const sc of scenarios) {
  const { ctx, errors } = makeContext(sc.seed);
  const step = (label, fn) => {
    try {
      fn();
    } catch (e) {
      const where = e && e.stack ? (e.stack.match(/gas\/js\.html\(inline\):\d+/) || [""])[0] : "";
      failures.push("[" + sc.name + "] " + label + ": " + (e && e.name) + ": " + (e && e.message) + (where ? "  @ " + where : ""));
    }
  };
  step("tải trang", () => vm.runInContext(code, ctx, { filename: "gas/js.html(inline)" }));
  if (sc.tabs) {
    for (const tab of tabs) step("switchTab('" + tab + "')", () => vm.runInContext("switchTab(" + JSON.stringify(tab) + ")", ctx));
    // Mở thử mọi form soạn/sửa (tạo mới + sửa bản ghi có sẵn).
    for (const call of ["openPostEditor(null)", "openGroupEditor(null)", "openGroupEditor('g')",
      "openCategoryEditor(null)", "openCategoryEditor('cat-a')", "renderPostsTable()", "backToPostsList()"]) {
      step(call, () => vm.runInContext(call, ctx));
    }
  }
  errors.forEach((msg) => failures.push("[" + sc.name + "] console.error: " + msg));
}

if (failures.length) {
  console.error("check_gas_client: LỖI khi chạy thử client CMS (gas/js.html):\n");
  failures.forEach((f) => console.error("  - " + f + "\n"));
  console.error(
    "Gợi ý: 'Cannot access X before initialization' = code chạy lúc tải trang dùng const/let khai báo\n" +
    "phía dưới. Khai báo hằng số ở ĐẦU file; lời gọi khởi động (bootApp) luôn nằm CUỐI file."
  );
  process.exit(1);
}
console.log("check_gas_client: OK (" + scenarios.length + " kịch bản tải trang, " + tabs.length + " tab)");
