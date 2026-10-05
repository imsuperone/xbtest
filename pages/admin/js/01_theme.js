// ---------- M3 Accent Color Engine (xbdoc/xbimg parity; keys: xbbot_accent/xbbot_theme) ----------
function hexToRgb(hex) {
  let c = String(hex || "").replace(/^#/, "").trim();
  if (c.length === 3) c = c.split("").map(x => x + x).join("");
  const num = parseInt(c, 16);
  if (isNaN(num)) return { r: 11, g: 87, b: 208 };
  return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
}

function mixHex(hexA, hexB, ratio) {
  const toRgb = (h) => [1, 3, 5].map((i) => parseInt(h.substr(i, 2), 16));
  const a = toRgb(hexA), b = toRgb(hexB);
  const mixed = a.map((v, i) => Math.round(v * ratio + b[i] * (1 - ratio)));
  return "#" + mixed.map((v) => Math.max(0, Math.min(255, v)).toString(16).padStart(2, "0")).join("");
}

const _ACCENT_VARS = ["--m3-sys-color-primary", "--m3-sys-color-on-primary", "--m3-sys-color-primary-container", "--m3-sys-color-surface", "--m3-sys-color-surface-container", "--m3-sys-color-surface-container-high", "--m3-sys-color-surface-container-highest", "--m3-seg-ink", "--acc", "--acc-hover", "--acc-active", "--accSoft", "--accSoft2", "--accBorder", "--primary-container", "--on-primary-container"];

function _relLum(hex) {
  const c = [1, 3, 5].map((i) => {
    const v = parseInt(hex.substr(i, 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

function _contrastOk(fg, bg) {
  const l1 = _relLum(fg), l2 = _relLum(bg);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05) >= 3.0;
}

let _CURRENT_ACCENT_COLOR = "#4A90D9";

function applyAccentColor(hex, save) {
  void save;
  const v = typeof hex === "string" ? hex.trim() : "";
  const ok = /^#[0-9a-fA-F]{6}$/.test(v);
  const root = document.documentElement;
  if (ok) {
    _CURRENT_ACCENT_COLOR = v;
    const dark = (root.getAttribute("data-theme") || root.dataset.theme || "light") === "dark";
    // 方案A：只染「强调系」（主色 + primary-container）。
    // 四个 surface 系（页面底 / 卡片 / 面板 / 最高层）不再随主题色变化，
    // 整页保持中性灰，只有按钮、徽章、选中态取色 —— 之前整页被染脏的主因。
    const tinted = dark ? {
      "--m3-sys-color-primary": v,
      "--m3-sys-color-primary-container": mixHex(v, "#1B2C42", 0.45),
    } : {
      "--m3-sys-color-primary": v,
      "--m3-sys-color-primary-container": mixHex(v, "#E4EAF2", 0.25),
    };
    for (const k in tinted) {
      try { root.style.setProperty(k, tinted[k]); } catch (e) {}
    }
    try {
      root.style.setProperty("--m3-sys-color-on-primary", _contrastOk("#FFFFFF", v) ? "#FFFFFF" : (dark ? "#06263F" : "#1E1B16"));
      // surface 已不参与染色，分段控件底色取 CSS 中性默认值做对比度判定
      let segBg = "";
      try { segBg = getComputedStyle(root).getPropertyValue("--m3-sys-color-surface-container-high").trim(); } catch (e) { segBg = ""; }
      if (!/^#[0-9a-fA-F]{6}$/.test(segBg)) segBg = dark ? "#232A33" : "#FFFFFF";
      root.style.setProperty("--m3-seg-ink", _contrastOk(v, segBg) ? v : (dark ? "#EAE6DF" : "#1E1B16"));
    } catch (e) {}
    try {
      const { r, g, b } = hexToRgb(v);
      const accMain = dark ? mixHex(v, "#FFFFFF", 0.35) : v;
      root.style.setProperty("--acc", accMain);
      root.style.setProperty("--acc-hover", dark ? mixHex(v, "#FFFFFF", 0.5) : mixHex(v, "#000000", 0.88));
      root.style.setProperty("--acc-active", dark ? mixHex(v, "#FFFFFF", 0.25) : mixHex(v, "#000000", 0.78));
      root.style.setProperty("--accSoft", `rgba(${r}, ${g}, ${b}, ${dark ? 0.16 : 0.10})`);
      root.style.setProperty("--accSoft2", `rgba(${r}, ${g}, ${b}, ${dark ? 0.26 : 0.18})`);
      root.style.setProperty("--accBorder", `rgba(${r}, ${g}, ${b}, ${dark ? 0.38 : 0.32})`);
      root.style.setProperty("--primary-container", tinted["--m3-sys-color-primary-container"]);
      root.style.setProperty("--on-primary-container", dark ? "#D6E8FA" : "#0F2B46");
    } catch (e) {}
    try { localStorage.setItem("xbbot_accent", v); } catch (e) {}
  } else {
    // 恢复默认：必须同时清空内存态 _CURRENT_ACCENT_COLOR。
    // 否则 applyTheme() 每次切换浅/深色都会用旧色重新写回 inline + 重新持久化，
    // 表现为「恢复默认后再切换，又变回第一次改的主题色 / 切换持久化卡住」。
    _CURRENT_ACCENT_COLOR = "";
    for (const k of _ACCENT_VARS) {
      try { root.style.removeProperty(k); } catch (e) {}
    }
    try { if (window.localStorage) window.localStorage.removeItem("xbbot_accent"); } catch (e) {}
    // 旧版遗留键：留着会在下次冷启动被 initAccentColor 当兜底复活
    try { if (window.localStorage) window.localStorage.removeItem("xbbot_monet_color"); } catch (e) {}
  }
  const picker = document.getElementById("accentPicker");
  if (picker) {
    if (ok) {
      picker.value = v;
      picker.dataset.custom = "1";
    } else {
      delete picker.dataset.custom;
      try {
        const def = getComputedStyle(document.documentElement).getPropertyValue("--m3-sys-color-primary").trim() || "#4A90D9";
        picker.value = /^#[0-9a-fA-F]{6}$/.test(def) ? def : "#4A90D9";
      } catch (e) {}
    }
  }
  const hexInput = document.getElementById("accentHex");
  if (hexInput && document.activeElement !== hexInput) {
    try {
      hexInput.value = ok ? v : (getComputedStyle(document.documentElement).getPropertyValue("--m3-sys-color-primary").trim() || "#4A90D9");
    } catch (e) {}
  }
  const cur = document.getElementById("accentCurrent");
  if (cur) {
    try {
      cur.style.background = ok ? v : (getComputedStyle(document.documentElement).getPropertyValue("--m3-sys-color-primary").trim() || "#4A90D9");
    } catch (e) {}
  }
}

const _MOON_SVG_PATH = "M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9c0-.46-.04-.92-.1-1.36-.98 1.37-2.58 2.26-4.4 2.26-2.98 0-5.4-2.42-5.4-5.4 0-1.81.89-3.42 2.26-4.4-.44-.06-.9-.1-1.36-.1z";
const _SUN_SVG_PATH = "M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1zm18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1zM11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1zm0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1zM5.99 4.58c-.39-.39-1.03-.39-1.41 0s-.39 1.03 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41L5.99 4.58zm12.37 12.37c-.39-.39-1.03-.39-1.41 0s-.39 1.03 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41l-1.06-1.06zm1.06-10.96c.39-.39.39-1.03 0-1.41s-1.03-.39-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06zM7.05 18.36c.39-.39.39-1.03 0-1.41s-1.03-.39-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06z";

function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  try { document.documentElement.style.colorScheme = t; } catch (e) {}
  try { localStorage.setItem("xbbot_theme", t); } catch (e) {}
  const icon = document.getElementById("themeIcon");
  if (icon) {
    icon.innerHTML = `<path d="${t === "dark" ? _SUN_SVG_PATH : _MOON_SVG_PATH}"/>`;
  }
  const legacyBtn = document.getElementById("themeBtn");
  if (legacyBtn) legacyBtn.textContent = t === "dark" ? "☀" : "☾";
  applyAccentColor(_CURRENT_ACCENT_COLOR || "", false);
}

function initAccentColor() {
  let v = "";
  try { v = localStorage.getItem("xbbot_accent") || ""; } catch (e) { v = ""; }
  if (!v) {
    try { v = localStorage.getItem("xbbot_monet_color") || ""; } catch (e) {}
  }
  // 不在此预写 _CURRENT_ACCENT_COLOR：由 applyAccentColor 统一维护（非法值/空值会被清成 ""）
  applyAccentColor(v, false);
}

function initTheme() {
  let savedTheme = "";
  try { savedTheme = localStorage.getItem("xbbot_theme") || ""; } catch (e) {}
  if (!savedTheme || (savedTheme !== "dark" && savedTheme !== "light")) {
    try {
      if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
        savedTheme = "dark";
      } else {
        savedTheme = "light";
      }
    } catch (e) {
      savedTheme = "light";
    }
  }
  initAccentColor();
  applyTheme(savedTheme);

  const toggleBtn = document.getElementById("themeToggleBtn");
  if (toggleBtn && !toggleBtn.dataset.bound) {
    toggleBtn.dataset.bound = "1";
    toggleBtn.addEventListener("click", () => {
      const cur = document.documentElement.dataset.theme || "light";
      const next = cur === "dark" ? "light" : "dark";
      applyTheme(next);
      toast(`当前界面已切换为${next === "dark" ? "深色" : "浅色"}模式。`, "ok");
    });
  }
  const legacyBtn = document.getElementById("themeBtn");
  if (legacyBtn && !legacyBtn.dataset.bound) {
    legacyBtn.dataset.bound = "1";
    legacyBtn.addEventListener("click", () => {
      const cur = document.documentElement.dataset.theme || "light";
      applyTheme(cur === "dark" ? "light" : "dark");
    });
  }

  initAccentPicker();
  initAccentPopover();
  initRefreshButton();
}

function initAccentPicker() {
  const picker = document.getElementById("accentPicker");
  if (picker && !picker.dataset.bound) {
    picker.dataset.bound = "1";
    picker.addEventListener("input", () => applyAccentColor(picker.value, false));
    picker.addEventListener("change", () => applyAccentColor(picker.value, false));
    picker.addEventListener("dblclick", () => applyAccentColor("", false));
  }
  const resetBtn = document.getElementById("accentResetBtn");
  if (resetBtn && !resetBtn.dataset.bound) {
    resetBtn.dataset.bound = "1";
    resetBtn.addEventListener("click", () => {
      applyAccentColor("", false);
      toast("已恢复默认主题颜色。", "ok");
    });
  }
}

function hexToHsv(hex) {
  const r = parseInt(hex.substr(1, 2), 16) / 255;
  const g = parseInt(hex.substr(3, 2), 16) / 255;
  const b = parseInt(hex.substr(5, 2), 16) / 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
  const d = mx - mn;
  let h = 0;
  if (d !== 0) {
    if (mx === r) h = 60 * (((g - b) / d) % 6);
    else if (mx === g) h = 60 * ((b - r) / d + 2);
    else h = 60 * ((r - g) / d + 4);
  }
  if (h < 0) h += 360;
  return { h: h, s: mx === 0 ? 0 : d / mx, v: mx };
}

function hsvToHex(h, s, v) {
  const c = v * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = v - c;
  let rp = 0, gp = 0, bp = 0;
  if (h < 60) { rp = c; gp = x; bp = 0; }
  else if (h < 120) { rp = x; gp = c; bp = 0; }
  else if (h < 180) { rp = 0; gp = c; bp = x; }
  else if (h < 240) { rp = 0; gp = x; bp = c; }
  else if (h < 300) { rp = x; gp = 0; bp = c; }
  else { rp = c; gp = 0; bp = x; }
  const to2 = (n) => Math.round((n + m) * 255).toString(16).padStart(2, "0");
  return "#" + to2(rp) + to2(gp) + to2(bp);
}

function initAccentPopover() {
  const btn = document.getElementById("accentPickerBtn");
  const picker = document.getElementById("accentPicker");
  const pop = document.getElementById("accentPopover");
  if (!btn || !picker || !pop) return;
  if (btn.dataset.popBound) return;
  btn.dataset.popBound = "1";
  const sv = document.getElementById("accentSv");
  const svDot = document.getElementById("accentSvDot");
  const hue = document.getElementById("accentHue");
  const hueDot = document.getElementById("accentHueDot");
  const hexInput = document.getElementById("accentHex");
  const current = document.getElementById("accentCurrent");
  const presets = document.getElementById("accentPresets");
  let st = { h: 210, s: 0.66, v: 0.85 };
  let open = false;

  function currentHex() {
    const v = (picker.value || "").trim();
    if (/^#[0-9a-fA-F]{6}$/.test(v)) return v;
    try {
      const def = getComputedStyle(document.documentElement).getPropertyValue("--m3-sys-color-primary").trim();
      if (/^#[0-9a-fA-F]{6}$/.test(def)) return def;
    } catch (e) {}
    return "#4A90D9";
  }

  function paint() {
    const hex = hsvToHex(st.h, st.s, st.v);
    if (sv) sv.style.background = "linear-gradient(to top,#000,transparent),linear-gradient(to right,#fff,transparent),hsl(" + Math.round(st.h) + ",100%,50%)";
    if (svDot) { svDot.style.left = (st.s * 100) + "%"; svDot.style.top = ((1 - st.v) * 100) + "%"; svDot.style.background = hex; }
    if (hueDot) { hueDot.style.left = (st.h / 360 * 100) + "%"; hueDot.style.background = "hsl(" + Math.round(st.h) + ",100%,50%)"; }
    if (hexInput && document.activeElement !== hexInput) hexInput.value = hex;
    if (current) current.style.background = hex;
  }

  function commit(fireChange) {
    const hex = hsvToHex(st.h, st.s, st.v);
    picker.value = hex;
    picker.dispatchEvent(new Event("input"));
    if (fireChange) picker.dispatchEvent(new Event("change"));
    if (hexInput) hexInput.value = hex;
    if (current) current.style.background = hex;
  }

  function place() {
    pop.hidden = false;
    const r = btn.getBoundingClientRect();
    const w = pop.offsetWidth || 240;
    const hgt = pop.offsetHeight || 260;
    const vw = window.innerWidth, vh = window.innerHeight;
    let left = r.left + 20 - w / 2;
    left = Math.max(8, Math.min(left, Math.max(8, vw - w - 8)));
    let top = r.bottom + 8;
    if (top + hgt > vh - 8) top = Math.max(8, r.top - hgt - 8);
    pop.style.left = left + "px";
    pop.style.top = top + "px";
  }

  function show() {
    st = hexToHsv(currentHex());
    paint();
    place();
    open = true;
  }

  function hide() {
    pop.hidden = true;
    open = false;
  }

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    if (open) hide();
    else show();
  });

  pop.addEventListener("click", (e) => e.stopPropagation());

  function svSet(e) {
    const r = sv.getBoundingClientRect();
    st.s = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    st.v = Math.max(0, Math.min(1, 1 - (e.clientY - r.top) / r.height));
    paint();
    commit(false);
  }

  if (sv) {
    sv.addEventListener("pointerdown", (e) => {
      try { sv.setPointerCapture(e.pointerId); } catch (err) {}
      svSet(e);
      const mv = (ev) => svSet(ev);
      const up = () => {
        sv.removeEventListener("pointermove", mv);
        picker.dispatchEvent(new Event("change"));
      };
      sv.addEventListener("pointermove", mv);
      sv.addEventListener("pointerup", up, { once: true });
    });
  }

  function hueSet(e) {
    const r = hue.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    st.h = ratio * 360;
    if (st.h >= 360) st.h = 359.9;
    paint();
    commit(false);
  }

  if (hue) {
    hue.addEventListener("pointerdown", (e) => {
      try { hue.setPointerCapture(e.pointerId); } catch (err) {}
      hueSet(e);
      const mv = (ev) => hueSet(ev);
      const up = () => {
        hue.removeEventListener("pointermove", mv);
        picker.dispatchEvent(new Event("change"));
      };
      hue.addEventListener("pointermove", mv);
      hue.addEventListener("pointerup", up, { once: true });
    });
  }

  function applyHexInput() {
    const v = (hexInput.value || "").trim();
    if (/^#[0-9a-fA-F]{6}$/.test(v)) {
      st = hexToHsv(v);
      paint();
      picker.value = v;
      picker.dispatchEvent(new Event("input"));
      picker.dispatchEvent(new Event("change"));
      if (current) current.style.background = v;
    } else {
      hexInput.value = currentHex();
    }
  }

  if (hexInput) {
    hexInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") applyHexInput();
      if (e.key === "Escape") hide();
    });
    hexInput.addEventListener("blur", applyHexInput);
    hexInput.addEventListener("click", (e) => e.stopPropagation());
  }

  if (presets) {
    presets.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-color]");
      if (!b) return;
      const v = b.getAttribute("data-color") || "";
      if (!/^#[0-9a-fA-F]{6}$/.test(v)) return;
      st = hexToHsv(v);
      paint();
      picker.value = v;
      picker.dispatchEvent(new Event("input"));
      picker.dispatchEvent(new Event("change"));
      if (current) current.style.background = v;
    });
  }

  document.addEventListener("click", (e) => {
    if (!open) return;
    if (!e.target.closest("#accentPopover") && !e.target.closest("#accentPickerBtn")) hide();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && open) hide();
  });

  window.addEventListener("resize", () => { if (open) place(); });
}

function initRefreshButton() {
  const btn = document.getElementById("refreshAllBtn");
  if (!btn || btn.dataset.bound) return;
  btn.dataset.bound = "1";
  btn.addEventListener("click", async () => {
    toast("正在刷新全部数据，请稍候……", "", 2000);
    try {
      const jobs = [];
      try { if (typeof loadOverviewReq === "function") jobs.push(loadOverviewReq().catch(() => {})); } catch (e) {}
      try { if (typeof loadAnalytics === "function") jobs.push(loadAnalytics().catch(() => {})); } catch (e) {}
      try {
        const on = document.querySelector("#mainTabs button.on") || document.querySelector(".tabs button.on");
        const tab = on && on.dataset ? on.dataset.tab : "";
        let loader = null;
        try { loader = (typeof TAB_LOADERS !== "undefined" && TAB_LOADERS) ? TAB_LOADERS[tab] : null; } catch (e) { loader = null; }
        if (tab && typeof loader === "function") jobs.push(loader().catch(() => {}));
      } catch (e) {}
      await Promise.all(jobs);
      toast("全部数据已刷新完毕。", "ok");
    } catch (err) {
      toast("部分数据刷新失败：" + ((err && err.message) || err), "bad");
    }
  });
}

// ---------- toast (xbimg式堆叠 m3-toast；旧 #toast/#snackbar 元素保留但不再驱动) ----------
let _lastToastText = "";
let _lastToastTime = 0;
function _ensureToastContainer() {
  let c = document.getElementById("toastContainer");
  if (!c) {
    c = document.createElement("div");
    c.id = "toastContainer";
    c.className = "toast-container";
    c.setAttribute("aria-live", "polite");
    document.body.appendChild(c);
  }
  return c;
}
function toast(msg, type, duration = 2800) {
  const text = String(msg ?? "");
  const now = Date.now();
  if (_lastToastText === text && now - _lastToastTime < 1200) return;
  _lastToastText = text;
  _lastToastTime = now;
  const container = _ensureToastContainer();
  if (container) {
    const t = document.createElement("div");
    t.className = "m3-toast" + (type === "ok" ? " okk" : type === "bad" ? " badk" : "");
    t.textContent = text;
    container.appendChild(t);
    setTimeout(() => {
      t.style.opacity = "0";
      t.style.transform = "translateY(20px)";
      t.style.transition = "all 0.3s";
      setTimeout(() => t.remove(), 300);
    }, duration || 2800);
  }
  // 只走堆叠通道：旧 #toast（右下同位）与 #snackbar（黑底反色，手机端同在底部）
  // 曾与堆叠层同时渲染，同一条消息出现三份、层间叠出怪底色与描边线，已停用驱动（元素保留兼容）。
}

// ---------- 页内确认框/输入框 (xbimg式，沙盒iframe内原生confirm/prompt会被拦截) ----------
function _buildConfirmOverlay(message, { okText = "确定", showInput = false, inputPlaceholder = "", inputValue = "" } = {}) {
  const ov = document.createElement("div");
  ov.className = "xb-confirm-overlay";
  const card = document.createElement("div");
  card.className = "xb-confirm-card";
  const msg = document.createElement("div");
  msg.className = "xb-confirm-msg";
  msg.textContent = message;
  card.appendChild(msg);
  let input = null;
  if (showInput) {
    input = document.createElement("input");
    input.type = "text";
    input.className = "m3-input xb-confirm-input";
    input.placeholder = inputPlaceholder;
    input.value = inputValue;
    card.appendChild(input);
  }
  const actions = document.createElement("div");
  actions.className = "xb-confirm-actions";
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "m3-btn secondary-btn ghost";
  cancelBtn.textContent = "取消";
  const okBtn = document.createElement("button");
  okBtn.type = "button";
  okBtn.className = "m3-btn";
  okBtn.style.cssText = "padding:8px 22px;font-size:14px;";
  okBtn.textContent = okText;
  actions.appendChild(cancelBtn);
  actions.appendChild(okBtn);
  card.appendChild(actions);
  ov.appendChild(card);
  return { ov, okBtn, cancelBtn, input };
}
function uiConfirm(message, okText = "确定删除") {
  return new Promise((resolve) => {
    const { ov, okBtn, cancelBtn } = _buildConfirmOverlay(message, { okText });
    document.body.appendChild(ov);
    let done = false;
    const finish = (val) => {
      if (done) return;
      done = true;
      document.removeEventListener("keydown", onKey, true);
      ov.remove();
      resolve(val);
    };
    const onKey = (ev) => { if (ev.key === "Escape") { ev.stopPropagation(); finish(false); } };
    document.addEventListener("keydown", onKey, true);
    cancelBtn.addEventListener("click", () => finish(false));
    okBtn.addEventListener("click", () => finish(true));
    ov.addEventListener("mousedown", (ev) => { if (ev.target === ov) finish(false); });
    setTimeout(() => cancelBtn.focus(), 0);
  });
}
function uiPrompt(message, defaultValue = "", placeholder = "") {
  return new Promise((resolve) => {
    const { ov, okBtn, cancelBtn, input } = _buildConfirmOverlay(
      message, { okText: "确定", showInput: true, inputPlaceholder: placeholder, inputValue: defaultValue });
    document.body.appendChild(ov);
    let done = false;
    const finish = (val) => {
      if (done) return;
      done = true;
      document.removeEventListener("keydown", onKey, true);
      ov.remove();
      resolve(val);
    };
    const onKey = (ev) => {
      if (ev.key === "Escape") { ev.stopPropagation(); finish(null); }
      else if (ev.key === "Enter" && document.activeElement === input) { finish((input.value || "").trim() ? input.value.trim() : null); }
    };
    document.addEventListener("keydown", onKey, true);
    cancelBtn.addEventListener("click", () => finish(null));
    okBtn.addEventListener("click", () => finish((input.value || "").trim() ? input.value.trim() : null));
    ov.addEventListener("mousedown", (ev) => { if (ev.target === ov) finish(null); });
    setTimeout(() => { input.focus(); input.select(); }, 0);
  });
}
// 原生 confirm/prompt 桥接：保留原生引用，仅在沙盒拦截时走页内框
if (typeof window !== "undefined" && !window._nativeConfirm) {
  try { window._nativeConfirm = window.confirm.bind(window); } catch (e) { window._nativeConfirm = null; }
  try { window._nativePrompt = window.prompt ? window.prompt.bind(window) : null; } catch (e) { window._nativePrompt = null; }
}
async function pageConfirm(message, okText = "确定") {
  try {
    if (window.parent && window.parent !== window) return await uiConfirm(message, okText);
  } catch (e) {}
  try { return await uiConfirm(message, okText); }
  catch (e) {
    if (window._nativeConfirm) return window._nativeConfirm(message);
    return false;
  }
}

// GET->POST 白名单：仅明确读接口允许在 GET 明确不可用时回退 POST。
// 写/删/恢复/修剪/清空类端点永远禁止回退（禁非原子 fallback 与 GET 副作用）。
const _GET_POST_FALLBACK_ALLOW = new Set([
  "stats", "rank", "config/get", "config/schema", "config/balance_state",
  "analytics/overview", "commands", "users",
  "user/export", "users/export",
  "images/list", "images/thumb", "images/export",
  "spirits", "gacha/weapons", "weapons/pool", "weapons/pool/img",
  "backups/list", "backups/config/snapshots", "backups/export",
  "version/check", "version/channel",
  "logs", "logs/export",
  "slave/users", "spirit/users", "groups/list",
  "images/text",
  "backup/webdav/test", "backups/webdav/test",
  "backup/webdav/files", "backups/webdav/files",
]);

function _shouldFallbackPost(cleanEp, res, err) {
  if (!_GET_POST_FALLBACK_ALLOW.has(cleanEp)) return false;
  if (err) {
    const msg = String((err && err.message) || err || "");
    // 仅网络异常/404/405 触发；超时/取消 AbortError 不重放
    if (/abort/i.test(msg)) return false;
    return true;
  }
  if (!res) return true;
  const msg = String((res && res.message) || "");
  const code = res && (res.code !== undefined ? res.code : res.status);
  if (/未找到|not found|404|405|method not allowed/i.test(msg)) return true;
  if (code === 404 || code === 405 || code === "404" || code === "405") return true;
  return false;
}

// 请求 API 封装（GET 参数拼 URL；仅白名单读接口在 404/405/网络异常时回退 POST）
async function callApi(endpoint, data = {}, method = "GET") {
  const _b = getBridge();
  const cleanEp = String(endpoint || "").replace(/^\/+/, "").split("?")[0];
  const cleanData = {};
  if (data && typeof data === "object") {
    Object.keys(data).forEach((k) => {
      if (data[k] !== undefined && data[k] !== null) {
        cleanData[k] = String(data[k]);
      }
    });
  }
  if (method === "GET") {
    let res = null;
    let err = null;
    try {
      res = await _b.apiGet(cleanEp, cleanData);
    } catch (e) {
      err = e;
    }
    // 空数组/空对象是合法结果，直接返回；仅白名单+明确不可用才回退 POST，避免双倍请求
    if (_shouldFallbackPost(cleanEp, res, err)) {
      res = await _b.apiPost(cleanEp, cleanData);
      return res;
    }
    if (err) throw err;
    return res;
  } else {
    return await _b.apiPost(cleanEp, cleanData);
  }
}

function copyToClipboard(text) {
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      navigator.clipboard.writeText(text).then(() => {
        toast("已复制到剪贴板", "ok");
      }).catch(() => {
        _execCommandCopy(text);
      });
      return;
    }
  } catch(e) {}
  _execCommandCopy(text);
}

function _execCommandCopy(text) {
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.top = "-9999px";
    ta.style.left = "-9999px";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const successful = document.execCommand("copy");
    ta.remove();
    if (successful) {
      toast("已复制到剪贴板", "ok");
    } else {
      toast("复制失败，请在下方文本框内手动全选复制", "bad");
    }
  } catch(err) {
    toast("复制失败，请在下方文本框内手动全选复制", "bad");
  }
}

function showExportModal({ filename, blob, blobUrl, rawText, base64Data }) {
  const modal = document.getElementById("appModal");
  if (!modal) return;
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");

  if (icon) icon.textContent = "📥";
  if (title) title.textContent = "导出文件就绪";
  if (inputWrap) inputWrap.style.display = "none";

  const sizeKb = blob ? (blob.size / 1024).toFixed(1) : (rawText ? (new Blob([rawText]).size / 1024).toFixed(1) : "");
  if (content) {
    content.innerHTML = `
      <div class="m3-card" style="margin:4px 0 10px;padding:14px 16px;font-size:12.5px">
        <div style="font-weight:600;color:var(--text);margin-bottom:4px;word-break:break-all;font-size:13px">📄 ${esc(filename)} ${sizeKb ? `<span class="badge badge-primary" style="margin-left:6px">${sizeKb} KB</span>` : ""}</div>
        <div style="color:var(--muted);font-size:11.5px;line-height:1.5">文件已生成完成。若浏览器未自动弹出保存提示，请点击下方按钮手动保存：</div>
      </div>
      <div style="display:flex;gap:8px;margin:10px 0;flex-wrap:wrap">
        <a href="${blobUrl}" download="${esc(filename)}" id="btnModalSaveFileLink" class="m3-btn" style="display:inline-flex;align-items:center;gap:5px;padding:8px 18px;font-size:13px;text-decoration:none;cursor:pointer;pointer-events:auto;z-index:2">⬇️ 保存文件到电脑</a>
        ${rawText ? `<button id="btnCopyExportData" class="m3-btn secondary-btn ghost" style="padding:8px 14px;font-size:12.5px;cursor:pointer;pointer-events:auto;z-index:2">📋 复制全部内容</button>` : ""}
      </div>
      ${rawText ? `<div style="margin-top:10px"><div style="font-size:11.5px;color:var(--muted);margin-bottom:4px">数据预览（点击文本框可自动全选）：</div><textarea readonly style="width:100%;height:100px;background:var(--panel);color:var(--text);font-family:monospace;font-size:11px;border:1px solid var(--line);border-radius:8px;padding:8px;outline:none;resize:vertical;line-height:1.4" onclick="this.select()">${esc(rawText.slice(0, 5000))}${rawText.length > 5000 ? "\n\n... (数据过长已截断预览，点击上方按钮复制全部数据)" : ""}</textarea></div>` : ""}
    `;
  }

  const saveBtn = document.getElementById("btnModalSaveFileLink");
  if (saveBtn) saveBtn.onclick = (e) => { e.preventDefault(); triggerDownload(blob, filename, rawText); };

  const copyBtn = document.getElementById("btnCopyExportData");
  if (copyBtn && rawText) {
    copyBtn.onclick = () => {
      copyToClipboard(rawText);
      copyBtn.textContent = "✅ 已复制到剪贴板";
      setTimeout(() => { copyBtn.textContent = "📋 复制全部内容"; }, 2000);
    };
  }

  if (cancelBtn) cancelBtn.style.display = "none";
  if (okBtn) {
    okBtn.textContent = "关闭";
    okBtn.onclick = () => {
      modal.className = "";
      if (cancelBtn) cancelBtn.style.display = "";
      okBtn.onclick = null;
    };
  }
  modal.className = "show";
}

function triggerExportResult({ filename, mime, blob, rawText, base64Data }) {
  if (!blob) {
    if (base64Data) {
      const bin = atob(String(base64Data || "").replace(/^data:.*?;base64,/, "").replace(/\s/g, "").trim());
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      blob = new Blob([bytes], { type: mime || "application/octet-stream" });
    } else if (rawText) {
      blob = new Blob([rawText], { type: mime || "application/json;charset=utf-8" });
    }
  }
  const blobUrl = blob ? URL.createObjectURL(blob) : "";
  let ok = false;
  if (blob) ok = triggerDownload(blob, filename, rawText);
  if (!ok) {
    showExportModal({ filename, blob, blobUrl, rawText, base64Data });
  } else if (blobUrl) {
    try { URL.revokeObjectURL(blobUrl); } catch (e) {}
  }
}

function triggerDownload(blob, filename, rawText = "") {
  let downloaded = false;
  filename = filename || "download.json";
  try {
    if (window.parent && window.parent !== window && window.parent.document && window.parent.document.body) {
      const url = URL.createObjectURL(blob);
      const a = window.parent.document.createElement("a");
      a.style.display = "none"; a.href = url; a.download = filename;
      window.parent.document.body.appendChild(a);
      a.click();
      setTimeout(() => { try { a.remove(); URL.revokeObjectURL(url); } catch (e) {} }, 1000);
      downloaded = true;
    }
  } catch (e) {}
  if (!downloaded) {
    try {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none"; a.href = url; a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { try { a.remove(); URL.revokeObjectURL(url); } catch (e) {} }, 1000);
      downloaded = true;
    } catch (e) {}
  }
  if (!downloaded && rawText) {
    try {
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = "data:application/json;charset=utf-8," + encodeURIComponent(rawText);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { try { a.remove(); } catch (e) {} }, 1000);
      downloaded = true;
    } catch (e) {}
  }
  toast("已触发下载: " + filename, "ok");
  return downloaded;
}

function downloadJson(data, filename) {
  try {
    const str = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    triggerDownload(new Blob([str], { type: "application/json;charset=utf-8" }), filename || "export.json", str);
  } catch (err) { toast("导出失败: " + err.message, "bad"); }
}

function downloadBase64File(base64Data, filename) {
  try {
    const bin = atob(String(base64Data || "").replace(/^data:.*?;base64,/, "").replace(/\s/g, "").trim());
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const mime = filename.endsWith(".zip") ? "application/zip" : (filename.endsWith(".json") ? "application/json;charset=utf-8" : "application/octet-stream");
    triggerDownload(new Blob([bytes], { type: mime }), filename || "download.bin");
  } catch (err) { toast("下载文件失败: " + err.message, "bad"); }
}

