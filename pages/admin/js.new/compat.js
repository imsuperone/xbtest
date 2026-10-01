// xbbot_beta xbimg-shell legacy compat: maps old js/00-10 expectations onto new shell.
// Loads AFTER old modules. Preserves xbimg palette, bridges tabs/toast/modal/lightbox.
(function () {
  "use strict";
  function $(s, r) { try { return (r || document).querySelector(s); } catch (e) { return null; } }
  function $id(id) { try { return document.getElementById(id); } catch (e) { return null; } }

  // 1. Monet -> xbimg accent guard: old applyMonetTheme would overwrite palette with #0B57D0 system.
  // Map it onto new applyAccentColor so colors stay in xbimg family.
  function patchMonet() {
    try {
      if (typeof window.applyMonetTheme === "function" && !window.applyMonetTheme.__patched) {
        var orig = window.applyMonetTheme;
        var fn = function (hex) {
          try {
            if (window.xbbotApp && typeof window.xbbotApp.setAccent === "function") {
              var saved = null;
              try { saved = localStorage.getItem("xbbot_accent"); } catch (e) {}
              if (saved && /^#[0-9a-fA-F]{6}$/.test(String(saved).trim())) {
                window.xbbotApp.setAccent(saved.trim());
                return;
              }
              if (String(hex || "").toLowerCase() === "#0b57d0") {
                window.xbbotApp.setAccent("");
                return;
              }
              window.xbbotApp.setAccent(hex || "#4A90D9");
              return;
            }
          } catch (e) {}
          try { return orig(hex); } catch (e) {}
        };
        fn.__patched = true;
        window.applyMonetTheme = fn;
      }
    } catch (e) {}
  }
  patchMonet();
  try { setTimeout(patchMonet, 0); setTimeout(patchMonet, 500); } catch (e) {}

  // 2. Old tab jumps use .tab/.on + #tab-xxx. Mirror them onto new .cat-tab/.active.
  function mirrorTabJump(tabId) {
    try {
      if (!tabId) return;
      if (window.xbbotApp && typeof window.xbbotApp.switchTab === "function") {
        window.xbbotApp.switchTab(tabId);
        return;
      }
      var btn = document.querySelector('.cat-tab[data-tab="' + tabId + '"]');
      if (btn) btn.click();
    } catch (e) {}
  }
  try {
    var obs = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var t = muts[i].target;
        try {
          if (t && t.classList && t.classList.contains("on") && t.hasAttribute && t.hasAttribute("data-tab")) {
            mirrorTabJump(t.getAttribute("data-tab"));
          }
        } catch (e) {}
      }
    });
    obs.observe(document.documentElement, { subtree: true, attributes: true, attributeFilter: ["class"] });
  } catch (e) {}
  // Legacy #tab-xxx nodes are hidden aliases; clicking old buttons still works via delegation.
  try {
    document.addEventListener("click", function (ev) {
      var el = ev.target && ev.target.closest ? ev.target.closest("[data-tab]") : null;
      if (!el) return;
      var id = el.getAttribute("data-tab");
      // Let app.js handle .cat-tab; only mirror legacy .tab/.on nodes.
      if (el.classList && el.classList.contains("tab")) mirrorTabJump(id);
    });
  } catch (e) {}

  // 3. Old toast uses #toast/#toastTxt. Mirror into new #toastContainer.
  try {
    var oldToast = $id("toast"), oldTxt = $id("toastTxt");
    if (oldToast && !oldToast.__mirrored) {
      oldToast.__mirrored = true;
      try { oldToast.style.display = "none"; } catch (e) {}
      var mo = new MutationObserver(function () {
        try {
          var msg = oldTxt ? oldTxt.textContent : oldToast.textContent;
          if (msg && window.xbbotApp && window.xbbotApp.toast) window.xbbotApp.toast(msg);
        } catch (e) {}
      });
      try { mo.observe(oldToast, { childList: true, subtree: true, characterData: true }); } catch (e) {}
    }
  } catch (e) {}

  // 4. refreshBtn: old code reloads active module; new app.js shows demo toast.
  // Rebind to reload active tab data if module exposes reload.
  try {
    var rb = $id("refreshBtn");
    if (rb && !rb.__wired) {
      rb.__wired = true;
      rb.addEventListener("click", function () {
        try {
          var active = document.querySelector("section.settings-section.active");
          var sec = active ? active.getAttribute("data-section") : "overview";
          if (window.xbbotApp && window.xbbotApp.refresh) window.xbbotApp.refresh(sec);
        } catch (e) {}
      });
    }
  } catch (e) {}
  // 6. Late bridge binding: app.js ran before old modules, so bind now.
  try {
    if (window.xbbotApp) {
      if (typeof window.getBridge === "function") window.xbbotApp.bridge = window.getBridge;
      if (typeof window.callApi === "function") window.xbbotApp.callApi = window.callApi;
      if (typeof window.postFile === "function") window.xbbotApp.postFile = window.postFile;
    }
  } catch (e) {}

  // 7. New .cat-tab clicks -> old TAB_LOADERS (old bindTabs targets .tabs buttons that no longer exist).
  function ensureTabLoaded(tab) {
    try {
      if (!tab) { return; }
      if (tab === "logs") {
        if (typeof loadLogs === "function") { try { loadLogs(false); } catch (e) {} }
        if (typeof startLogsAutoRefresh === "function") { try { startLogsAutoRefresh(); } catch (e) {} }
        return;
      }
      if (typeof stopLogsAutoRefresh === "function") { try { stopLogsAutoRefresh(); } catch (e) {} }
      if (tab === "overview") {
        if (typeof loadOverviewReq === "function") { try { Promise.resolve(loadOverviewReq()).catch(function () {}); } catch (e) {} }
        if (typeof loadStats === "function") { try { Promise.resolve(loadStats()).catch(function () {}); } catch (e) {} }
        return;
      }
      if (tab === "about") { return; }
      try {
        if (typeof TAB_DONE !== "undefined" && typeof TAB_LOADERS !== "undefined" && !TAB_DONE[tab] && TAB_LOADERS[tab]) {
          TAB_DONE[tab] = true;
          Promise.resolve(TAB_LOADERS[tab]()).then(function () {}, function () {
            try { TAB_DONE[tab] = false; } catch (e) {}
          });
        }
      } catch (e) {}
    } catch (e) {}
  }
  try {
    document.addEventListener("click", function (ev) {
      var el = ev.target && ev.target.closest ? ev.target.closest(".cat-tab") : null;
      if (!el) { return; }
      ensureTabLoaded(el.getAttribute("data-tab"));
    });
  } catch (e) {}
  try {
    var bootTab = function () {
      try {
        var active = document.querySelector(".cat-tab.active");
        ensureTabLoaded(active ? active.getAttribute("data-tab") : "overview");
      } catch (e) {}
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bootTab);
    else bootTab();
  } catch (e) {}
})();
