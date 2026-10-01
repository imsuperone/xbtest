// ============================================================================
// xbbot_beta admin panel - PURE UI skeleton (no network, no business logic)
// Pairs with pages/admin/index.html (app-layout shell) + pages/admin/style.css
// ============================================================================
(function () {
  "use strict";

  var PLUGIN_ID = "astrbot_plugin_xbbot_beta";
  var DEFAULT_ACCENT = "#4A90D9";
  var TAB_KEY = "xbbot_active_tab";
  var THEME_KEY = "xbbot_theme";
  var ACCENT_KEY = "xbbot_accent";

  // ---- category tabs: toggles .cat-tab.active + section.settings-section.active ----
  function switchCategoryTab(tabId) {
    if (!tabId) { return; }
    try { console.log("[" + PLUGIN_ID + "] switchTab: " + tabId); } catch (e) {}
    var tabs = document.querySelectorAll(".cat-tab");
    for (var i = 0; i < tabs.length; i++) {
      var on = tabs[i].getAttribute("data-tab") === tabId;
      if (on) { tabs[i].classList.add("active"); }
      else { tabs[i].classList.remove("active"); }
    }
    var sections = document.querySelectorAll("section.settings-section");
    for (var j = 0; j < sections.length; j++) {
      var match = sections[j].id === ("section-" + tabId) ||
        sections[j].getAttribute("data-section") === tabId;
      if (match) { sections[j].classList.add("active"); }
      else { sections[j].classList.remove("active"); }
    }
    try { localStorage.setItem(TAB_KEY, tabId); } catch (e) {}
  }

  function restoreActiveTab() {
    var saved = null;
    try { saved = localStorage.getItem(TAB_KEY); } catch (e) {}
    if (saved && document.querySelector('.cat-tab[data-tab="' + saved + '"]')) {
      switchCategoryTab(saved);
      return;
    }
    var first = document.querySelector(".cat-tab");
    if (first) { switchCategoryTab(first.getAttribute("data-tab")); }
  }

  // ---- theme: data-theme + localStorage xbbot_theme ----
  function applyThemeMode(mode) {
    var m = (mode === "dark") ? "dark" : "light";
    try { document.documentElement.setAttribute("data-theme", m); } catch (e) {}
    try { localStorage.setItem(THEME_KEY, m); } catch (e) {}
    var btn = document.getElementById("themeToggleBtn");
    if (btn) { btn.setAttribute("aria-pressed", m === "dark" ? "true" : "false"); }
  }

  function toggleTheme() {
    var cur = "light";
    try {
      cur = document.documentElement.getAttribute("data-theme") || "light";
    } catch (e) {}
    applyThemeMode(cur === "dark" ? "light" : "dark");
    applyAccentColor(getSavedAccent());
    showToast(cur === "dark" ? "已切换浅色模式" : "已切换深色模式");
  }

  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem(THEME_KEY); } catch (e) {}
    if (saved !== "dark" && saved !== "light") { saved = "light"; }
    applyThemeMode(saved);
  }

  // ---- accent: xbimg tonal palette (primary + auto-tinted surfaces) ----
  var _ACCENT_VARS = ["--m3-sys-color-primary", "--m3-sys-color-primary-container", "--m3-sys-color-surface", "--m3-sys-color-surface-container", "--m3-sys-color-surface-container-high", "--m3-sys-color-surface-container-highest", "--m3-seg-ink"];

  function clamp01(n) {
    if (n < 0) { return 0; }
    if (n > 1) { return 1; }
    return n;
  }

  function mixHex(hexA, hexB, weight) {
    var w = clamp01(typeof weight === "number" ? weight : 0.5);
    function norm(h) {
      h = String(h || "").replace("#", "");
      if (h.length === 3) {
        h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
      }
      return h;
    }
    function toRgb(h) {
      h = norm(h);
      return [
        parseInt(h.slice(0, 2), 16) || 0,
        parseInt(h.slice(2, 4), 16) || 0,
        parseInt(h.slice(4, 6), 16) || 0
      ];
    }
    function toHex(n) {
      var s = Math.round(n).toString(16);
      return s.length === 1 ? "0" + s : s;
    }
    var a = toRgb(hexA);
    var b = toRgb(hexB);
    return "#" + toHex(a[0] * w + b[0] * (1 - w)) +
      toHex(a[1] * w + b[1] * (1 - w)) +
      toHex(a[2] * w + b[2] * (1 - w));
  }

  function _relLum(hex) {
    var c = [1, 3, 5].map(function (i) {
      var v = parseInt(hex.substr(i, 2), 16) / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }

  function _contrastOk(fg, bg) {
    var l1 = _relLum(fg), l2 = _relLum(bg);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05) >= 3.0;
  }

  function getSavedAccent() {
    try {
      var s = String(localStorage.getItem(ACCENT_KEY) || "").trim();
      return /^#[0-9a-fA-F]{6}$/.test(s) ? s : "";
    } catch (e) { return ""; }
  }

  function syncAccentPicker() {
    var picker = document.getElementById("accentPicker");
    if (!picker) { return; }
    var saved = getSavedAccent();
    if (saved) {
      try { picker.value = saved; } catch (e) {}
      return;
    }
    try {
      var def = getComputedStyle(document.documentElement).getPropertyValue("--m3-sys-color-primary").trim() || DEFAULT_ACCENT;
      picker.value = /^#[0-9a-fA-F]{6}$/.test(def) ? def : DEFAULT_ACCENT;
    } catch (e) {}
  }

  function applyAccentColor(hex) {
    var v = String(hex == null ? "" : hex).trim();
    var ok = /^#[0-9a-fA-F]{6}$/.test(v);
    var root = document.documentElement;
    if (ok) {
      var dark = (root.getAttribute("data-theme") || "light") === "dark";
      var tinted = dark ? {
        "--m3-sys-color-primary": v,
        "--m3-sys-color-primary-container": mixHex(v, "#1B2C42", 0.45),
        "--m3-sys-color-surface": mixHex(v, "#111418", 0.12),
        "--m3-sys-color-surface-container": mixHex(v, "#1A1F26", 0.16),
        "--m3-sys-color-surface-container-high": mixHex(v, "#232A33", 0.16),
        "--m3-sys-color-surface-container-highest": mixHex(v, "#2C343F", 0.16)
      } : {
        "--m3-sys-color-primary": v,
        "--m3-sys-color-primary-container": mixHex(v, "#E4EAF2", 0.25),
        "--m3-sys-color-surface": mixHex(v, "#F4F7FB", 0.08),
        "--m3-sys-color-surface-container": mixHex(v, "#E8EDF4", 0.12),
        "--m3-sys-color-surface-container-highest": mixHex(v, "#DFE6EF", 0.12)
      };
      for (var k in tinted) {
        try { root.style.setProperty(k, tinted[k]); } catch (e) {}
      }
      try {
        var segBg = dark ? tinted["--m3-sys-color-surface-container-high"] : "#FFFFFF";
        root.style.setProperty("--m3-seg-ink", _contrastOk(v, segBg) ? v : (dark ? "#EAE6DF" : "#1E1B16"));
      } catch (e) {}
      try { localStorage.setItem(ACCENT_KEY, v); } catch (e) {}
    } else {
      for (var i = 0; i < _ACCENT_VARS.length; i++) {
        try { root.style.removeProperty(_ACCENT_VARS[i]); } catch (e) {}
      }
      try { localStorage.removeItem(ACCENT_KEY); } catch (e) {}
    }
    syncAccentPicker();
  }

  function resetAccentColor() {
    applyAccentColor("");
  }

  function initAccentColor() {
    applyAccentColor(getSavedAccent());
    var picker = document.getElementById("accentPicker");
    if (!picker) { return; }
    picker.addEventListener("input", function (ev) {
      applyAccentColor(ev.target.value);
    });
    picker.addEventListener("change", function (ev) {
      applyAccentColor(ev.target.value);
      showToast("强调色已更新");
    });
    picker.addEventListener("dblclick", function () {
      resetAccentColor();
      showToast("强调色已重置");
    });
  }

  // ---- toast (dedupe identical messages) ----
  var _lastToastText = "";
  var _lastToastTime = 0;
  function showToast(msg, duration) {
    var text = String(msg == null ? "" : msg);
    if (!text) { return; }
    var now = Date.now();
    if (_lastToastText === text && now - _lastToastTime < 1200) { return; }
    _lastToastText = text;
    _lastToastTime = now;
    var container = document.getElementById("toastContainer");
    if (!container) { return; }
    var t = document.createElement("div");
    t.className = "m3-toast";
    t.textContent = text;
    container.appendChild(t);
    var ms = typeof duration === "number" ? duration : 2600;
    setTimeout(function () {
      t.style.opacity = "0";
      t.style.transform = "translateY(20px)";
      t.style.transition = "all 0.3s";
      setTimeout(function () { t.remove(); }, 320);
    }, ms);
  }

  // ---- in-page confirm / prompt via .xb-confirm-overlay (promise based) ----
  function _buildConfirmOverlay(message, opts) {
    opts = opts || {};
    var okText = opts.okText || "确定";
    var showInput = !!opts.showInput;
    var ov = document.createElement("div");
    ov.className = "xb-confirm-overlay";
    var card = document.createElement("div");
    card.className = "xb-confirm-card";
    var msg = document.createElement("div");
    msg.className = "xb-confirm-msg";
    msg.textContent = message;
    card.appendChild(msg);
    var input = null;
    if (showInput) {
      input = document.createElement("input");
      input.type = "text";
      input.className = "m3-input xb-confirm-input";
      input.placeholder = opts.inputPlaceholder || "";
      input.value = opts.inputValue || "";
      card.appendChild(input);
    }
    var actions = document.createElement("div");
    actions.className = "xb-confirm-actions";
    var cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "m3-btn secondary-btn";
    cancelBtn.textContent = "取消";
    var okBtn = document.createElement("button");
    okBtn.type = "button";
    okBtn.className = "m3-btn primary-btn";
    okBtn.textContent = okText;
    actions.appendChild(cancelBtn);
    actions.appendChild(okBtn);
    card.appendChild(actions);
    ov.appendChild(card);
    return { ov: ov, okBtn: okBtn, cancelBtn: cancelBtn, input: input };
  }

  function uiConfirm(message, okText) {
    return new Promise(function (resolve) {
      var parts = _buildConfirmOverlay(message, { okText: okText || "确定" });
      document.body.appendChild(parts.ov);
      var done = false;
      function finish(val) {
        if (done) { return; }
        done = true;
        document.removeEventListener("keydown", onKey, true);
        parts.ov.remove();
        resolve(val);
      }
      function onKey(ev) {
        if (ev.key === "Escape") { ev.stopPropagation(); finish(false); }
      }
      document.addEventListener("keydown", onKey, true);
      parts.cancelBtn.addEventListener("click", function () { finish(false); });
      parts.okBtn.addEventListener("click", function () { finish(true); });
      parts.ov.addEventListener("mousedown", function (ev) {
        if (ev.target === parts.ov) { finish(false); }
      });
      setTimeout(function () { parts.cancelBtn.focus(); }, 0);
    });
  }

  function uiPrompt(message, defaultValue, placeholder) {
    return new Promise(function (resolve) {
      var parts = _buildConfirmOverlay(message, {
        okText: "确定",
        showInput: true,
        inputPlaceholder: placeholder || "",
        inputValue: defaultValue || ""
      });
      document.body.appendChild(parts.ov);
      var done = false;
      function finish(val) {
        if (done) { return; }
        done = true;
        document.removeEventListener("keydown", onKey, true);
        parts.ov.remove();
        resolve(val);
      }
      function onKey(ev) {
        if (ev.key === "Escape") { ev.stopPropagation(); finish(null); }
        if (ev.key === "Enter" && parts.input) {
          ev.stopPropagation();
          var v = parts.input.value.trim();
          finish(v === "" ? null : v);
        }
      }
      document.addEventListener("keydown", onKey, true);
      parts.cancelBtn.addEventListener("click", function () { finish(null); });
      parts.okBtn.addEventListener("click", function () {
        var v = parts.input ? parts.input.value.trim() : "";
        finish(v === "" ? null : v);
      });
      parts.ov.addEventListener("mousedown", function (ev) {
        if (ev.target === parts.ov) { finish(null); }
      });
      setTimeout(function () { if (parts.input) { parts.input.focus(); } }, 0);
    });
  }

  // ---- global click delegation: visual feedback only, no network ----
  function bindGlobalDelegation() {
    document.addEventListener("click", function (ev) {
      var tab = ev.target.closest ? ev.target.closest(".cat-tab") : null;
      if (tab) {
        switchCategoryTab(tab.getAttribute("data-tab"));
        return;
      }
      var themeBtn = ev.target.closest ? ev.target.closest("#themeToggleBtn") : null;
      if (themeBtn) { toggleTheme(); return; }
      var accentReset = ev.target.closest ? ev.target.closest("#accentResetBtn") : null;
      if (accentReset) {
        resetAccentColor();
        showToast("强调色已重置");
        return;
      }
      var refreshBtn = ev.target.closest ? ev.target.closest("#refreshBtn") : null;
      if (refreshBtn) {
        showToast("已刷新（仅演示，无网络请求）");
        return;
      }
    });
  }

  // ---- placeholders: real wiring comes later (no logic here) ----
  // TODO wiring: table render (wallet/accounts/groups/rank) will hook here.
  // TODO wiring: config load/save will hook here.
  // TODO wiring: backups / snapshots list + restore will hook here.
  // TODO wiring: logs viewer + pagination will hook here.

  // ---- boot ----
  function startApp() {
    try { console.log("[" + PLUGIN_ID + "] admin skeleton ready (offline)"); } catch (e) {}
    initTheme();
    initAccentColor();
    restoreActiveTab();
    bindGlobalDelegation();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startApp);
  } else {
    startApp();
  }

  window.xbbotApp = {
    switchTab: switchCategoryTab,
    toggleTheme: toggleTheme,
    setAccent: function (hex) { applyAccentColor(hex); },
    toast: showToast,
    confirm: uiConfirm,
    prompt: uiPrompt
  };

  // ---- js.new core infra hooks (00_bridge/01_uiutil load separately; lazy delegation, no network here) ----
  try {
    if (typeof window.__xbbotBridge !== "undefined" && window.__xbbotBridge) {
      if (typeof window.__xbbotBridge.getBridge === "function") { window.xbbotApp.bridge = window.__xbbotBridge.getBridge; }
      if (typeof window.__xbbotBridge.callApi === "function") { window.xbbotApp.callApi = window.__xbbotBridge.callApi; }
      if (typeof window.__xbbotBridge.postFile === "function") { window.xbbotApp.postFile = window.__xbbotBridge.postFile; }
    }
    if (typeof window.xbbotApp.bridge !== "function" && typeof window.getBridge === "function") { window.xbbotApp.bridge = window.getBridge; }
    if (typeof window.xbbotApp.callApi !== "function" && typeof window.callApi === "function") { window.xbbotApp.callApi = window.callApi; }
    if (typeof window.xbbotApp.postFile !== "function" && typeof window.postFile === "function") { window.xbbotApp.postFile = window.postFile; }
    if (typeof window.xbbotApp.downloadJson !== "function" && typeof window.downloadJson === "function") { window.xbbotApp.downloadJson = window.downloadJson; }
    if (typeof window.xbbotApp.downloadBase64File !== "function" && typeof window.downloadBase64File === "function") { window.xbbotApp.downloadBase64File = window.downloadBase64File; }
    if (typeof window.xbbotApp.showExportModal !== "function" && typeof window.showExportModal === "function") { window.xbbotApp.showExportModal = window.showExportModal; }
    if (typeof window.xbbotApp.copyToClipboard !== "function" && typeof window.copyToClipboard === "function") { window.xbbotApp.copyToClipboard = window.copyToClipboard; }
  } catch (e) {}
})();
