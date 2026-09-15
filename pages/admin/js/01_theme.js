// ---------- Material You (Android 16 Monet) 动态主题色彩引擎 ----------
function hexToRgb(hex) {
  let c = String(hex || "").replace(/^#/, "").trim();
  if (c.length === 3) c = c.split("").map(x => x + x).join("");
  const num = parseInt(c, 16);
  if (isNaN(num)) return { r: 11, g: 87, b: 208 };
  return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
}

function rgbToHsl(r, g, b) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h, s, l = (max + min) / 2;
  if (max === min) {
    h = s = 0;
  } else {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }
  return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
}

let _CURRENT_MONET_COLOR = "#0B57D0";

function applyMonetTheme(hex) {
  if (!hex || !/^#[0-9a-fA-F]{3,6}$/i.test(hex)) hex = "#0B57D0";
  _CURRENT_MONET_COLOR = hex;
  try { localStorage.setItem("xbbot_monet_color", hex); } catch (e) {}

  const { r, g, b } = hexToRgb(hex);
  const { h, s, l } = rgbToHsl(r, g, b);
  const isDark = document.documentElement.dataset.theme === "dark";
  const root = document.documentElement;

  if (!isDark) {
    const isGoogleBlue = hex.toLowerCase() === "#0b57d0";
    const bgL = "#FFFFFF";
    const panelL = "#FFFFFF";
    const panelHoverL = "#F8FAFC";
    const panel2L = "#FFFFFF";
    const panel3L = "#FFFFFF";
    const lineL = "#D1D5DB";
    const lineSubtleL = "rgba(0, 0, 0, 0.06)";
    const priContL = isGoogleBlue ? "#D3E3FD" : `hsl(${h}, ${Math.max(40, Math.min(85, s * 0.75))}%, 90%)`;
    const onPriContL = "#041E49";

    root.style.setProperty("--md-sys-color-primary", hex);
    root.style.setProperty("--md-sys-color-on-primary", "#FFFFFF");
    root.style.setProperty("--md-sys-color-primary-container", priContL);
    root.style.setProperty("--md-sys-color-on-primary-container", onPriContL);
    root.style.setProperty("--md-sys-color-surface", bgL);
    root.style.setProperty("--md-sys-color-surface-container", panelL);
    root.style.setProperty("--md-sys-color-surface-container-high", panel2L);
    root.style.setProperty("--md-sys-color-surface-container-highest", panel3L);
    root.style.setProperty("--surface-container-high", panel2L);
    root.style.setProperty("--outline", "#74777F");

    root.style.setProperty("--bg", bgL);
    root.style.setProperty("--panel", panelL);
    root.style.setProperty("--panel-hover", panelHoverL);
    root.style.setProperty("--panel2", panel2L);
    root.style.setProperty("--panel3", panel3L);
    root.style.setProperty("--text", "#1F1F1F");
    root.style.setProperty("--text-secondary", "#444746");
    root.style.setProperty("--muted", "#444746");
    root.style.setProperty("--line", lineL);
    root.style.setProperty("--line-subtle", lineSubtleL);

    root.style.setProperty("--acc", hex);
    root.style.setProperty("--acc-hover", `hsl(${h}, ${s}%, ${Math.max(15, l * 0.85)}%)`);
    root.style.setProperty("--acc-active", `hsl(${h}, ${s}%, ${Math.max(10, l * 0.70)}%)`);
    root.style.setProperty("--accSoft", `rgba(${r}, ${g}, ${b}, 0.08)`);
    root.style.setProperty("--accSoft2", `rgba(${r}, ${g}, ${b}, 0.16)`);
    root.style.setProperty("--accBorder", `rgba(${r}, ${g}, ${b}, 0.30)`);
    root.style.setProperty("--primary-container", priContL);
    root.style.setProperty("--on-primary-container", onPriContL);
  } else {
    const isGoogleBlue = hex.toLowerCase() === "#0b57d0";
    const darkPrimary = isGoogleBlue ? "#A8C7FA" : `hsl(${h}, ${Math.max(45, Math.min(90, s * 0.85))}%, 78%)`;
    const bgD = "#111318";
    const panelD = "#191C20";
    const panelHoverD = "#21252C";
    const panel2D = "#22262B";
    const panel3D = "#2C3036";
    const lineD = "rgba(255, 255, 255, 0.12)";
    const lineSubtleD = "rgba(255, 255, 255, 0.06)";
    const priContD = isGoogleBlue ? "#0842A0" : `hsl(${h}, ${Math.max(35, s * 0.8)}%, 24%)`;
    const onPriContD = isGoogleBlue ? "#D3E3FD" : `hsl(${h}, ${Math.max(35, s * 0.75)}%, 94%)`;

    root.style.setProperty("--md-sys-color-primary", darkPrimary);
    root.style.setProperty("--md-sys-color-on-primary", "#041E49");
    root.style.setProperty("--md-sys-color-primary-container", priContD);
    root.style.setProperty("--md-sys-color-on-primary-container", onPriContD);
    root.style.setProperty("--md-sys-color-surface", bgD);
    root.style.setProperty("--md-sys-color-surface-container", panelD);
    root.style.setProperty("--md-sys-color-surface-container-high", panel2D);
    root.style.setProperty("--md-sys-color-surface-container-highest", panel3D);
    root.style.setProperty("--surface-container-high", panel2D);
    root.style.setProperty("--outline", "#8E918F");

    root.style.setProperty("--bg", bgD);
    root.style.setProperty("--panel", panelD);
    root.style.setProperty("--panel-hover", panelHoverD);
    root.style.setProperty("--panel2", panel2D);
    root.style.setProperty("--panel3", panel3D);
    root.style.setProperty("--text", "#E2E2E6");
    root.style.setProperty("--text-secondary", "#C4C7D0");
    root.style.setProperty("--muted", "#8E918F");
    root.style.setProperty("--line", lineD);
    root.style.setProperty("--line-subtle", lineSubtleD);

    root.style.setProperty("--acc", darkPrimary);
    root.style.setProperty("--acc-hover", `hsl(${h}, ${s}%, 86%)`);
    root.style.setProperty("--acc-active", `hsl(${h}, ${s}%, 70%)`);
    root.style.setProperty("--accSoft", `rgba(${r}, ${g}, ${b}, 0.16)`);
    root.style.setProperty("--accSoft2", `rgba(${r}, ${g}, ${b}, 0.26)`);
    root.style.setProperty("--accBorder", `rgba(${r}, ${g}, ${b}, 0.36)`);
    root.style.setProperty("--primary-container", priContD);
    root.style.setProperty("--on-primary-container", onPriContD);
  }

  const inputEl = document.getElementById("monetColorInput");
  const hexEl = document.getElementById("monetColorHex");
  if (inputEl) inputEl.value = hex;
  if (hexEl) hexEl.textContent = hex.toUpperCase();

  document.querySelectorAll(".monet-item").forEach((el) => {
    if (el.dataset.color && el.dataset.color.toLowerCase() === hex.toLowerCase()) {
      el.classList.add("on");
    } else {
      el.classList.remove("on");
    }
  });
}

function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  try { document.documentElement.style.colorScheme = t; } catch (e) {}
  try { localStorage.setItem("xbbot_theme", t); } catch (e) {}
  const b = document.getElementById("themeBtn");
  if (b) b.textContent = t === "dark" ? "☀" : "☾";
  applyMonetTheme(_CURRENT_MONET_COLOR);
}
function initTheme() {
  let savedColor = "#0B57D0";
  let savedTheme = "";
  try { savedColor = localStorage.getItem("xbbot_monet_color") || "#0B57D0"; } catch (e) {}
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
  _CURRENT_MONET_COLOR = savedColor;
  applyTheme(savedTheme);

  const b = document.getElementById("themeBtn");
  if (b) b.addEventListener("click", () => {
    const newTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(newTheme);
  });

  initMonetPalette();
}

function initMonetPalette() {
  const btn = document.getElementById("themePaletteBtn");
  const card = document.getElementById("monetPaletteCard");
  const closeBtn = document.getElementById("monetPaletteClose");
  const input = document.getElementById("monetColorInput");
  const resetBtn = document.getElementById("monetResetDefault");

  if (btn && card) {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isShow = card.style.display !== "none";
      card.style.display = isShow ? "none" : "block";
    });
  }

  if (closeBtn && card) {
    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      card.style.display = "none";
    });
  }

  document.addEventListener("click", (e) => {
    if (card && card.style.display !== "none" && !card.contains(e.target) && e.target !== btn) {
      card.style.display = "none";
    }
  });

  document.querySelectorAll(".monet-item").forEach((it) => {
    it.addEventListener("click", () => {
      const c = it.dataset.color;
      if (c) {
        applyMonetTheme(c);
        toast("已应用主题色：" + (it.querySelector("span")?.textContent || c), "ok");
      }
    });
  });

  if (input) {
    input.addEventListener("input", (e) => {
      applyMonetTheme(e.target.value);
    });
    input.addEventListener("change", (e) => {
      applyMonetTheme(e.target.value);
      toast("已应用自定义主色：" + e.target.value.toUpperCase(), "ok");
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      applyMonetTheme("#0B57D0");
      toast("已恢复默认谷歌蓝", "ok");
    });
  }
}

// ---------- toast ----------
let _toastT = null;
function toast(msg, type, duration = 2800) {
  let el = document.getElementById("toast");
  let txt = document.getElementById("toastTxt");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    txt = document.createElement("span");
    txt.id = "toastTxt";
    el.appendChild(txt);
    document.body.appendChild(el);
  }
  if (!txt) {
    txt = el.querySelector("span") || el;
  }
  txt.textContent = msg;
  el.className = "show " + (type === "ok" ? "okk" : type === "bad" ? "badk" : "");
  clearTimeout(_toastT);
  _toastT = setTimeout(() => { el.className = ""; }, duration || 2800);
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
        toast("已成功复制到剪贴板！", "ok");
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
      toast("已成功复制到剪贴板！", "ok");
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
      <div class="card" style="margin:4px 0 10px;padding:12px;border-radius:12px;border:1px solid var(--line);font-size:12.5px">
        <div style="font-weight:600;color:var(--text);margin-bottom:4px;word-break:break-all;font-size:13px">📄 ${esc(filename)} ${sizeKb ? `<span class="badge badge-primary" style="margin-left:6px">${sizeKb} KB</span>` : ""}</div>
        <div style="color:var(--muted);font-size:11.5px;line-height:1.5">文件已生成完成。若浏览器未自动弹出保存提示，请点击下方按钮手动保存：</div>
      </div>
      <div style="display:flex;gap:8px;margin:10px 0;flex-wrap:wrap">
        <a href="${blobUrl}" download="${esc(filename)}" id="btnModalSaveFileLink" class="btn" style="display:inline-flex;align-items:center;gap:5px;padding:8px 18px;background:var(--acc);color:#fff;border-radius:8px;font-weight:600;font-size:13px;text-decoration:none;cursor:pointer">⬇️ 保存文件到电脑</a>
        ${rawText ? `<button id="btnCopyExportData" class="ghost" style="padding:8px 14px;font-size:12.5px;cursor:pointer">📋 复制全部内容</button>` : ""}
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

