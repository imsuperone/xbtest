const PLUGIN_ID = "astrbot_plugin_xbbot_beta";
// 构建时由 build_frontend.py 注入当前 metadata 版本（与后端对账用；源里永远是占位）
const FRONTEND_VER = "2026w0911h";

let _WORKING_API_PREFIX = null;

function cleanEndpointAndParams(endpoint, params) {
  let ep = String(endpoint || "").replace(/^\/+/, "");
  let mergedParams = (params && typeof params === "object") ? Object.assign({}, params) : {};
  if (ep.includes("?")) {
    const qIdx = ep.indexOf("?");
    const qStr = ep.slice(qIdx + 1);
    ep = ep.slice(0, qIdx);
    if (qStr) {
      try {
        const urlParams = new URLSearchParams(qStr);
        for (const [k, v] of urlParams.entries()) {
          if (!(k in mergedParams)) {
            mergedParams[k] = v;
          }
        }
      } catch (e) {}
    }
  }
  return { ep, params: mergedParams };
}

// 传文件类读接口不加超时（备份/镜像导出按体积走，服务端自有熔断；加了会误杀大文件下载）
const _NO_TIMEOUT_GET = /^(backups\/export|images\/export|user\/export|users\/export)/;

function getBridge() {
  let rawBridge = null;
  try {
    if (window.bridge && typeof window.bridge.apiGet === "function") rawBridge = window.bridge;
    else if (window.AstrBotPluginPage && typeof window.AstrBotPluginPage.apiGet === "function") rawBridge = window.AstrBotPluginPage;
    else {
      try {
        if (window.parent && window.parent.AstrBotPluginPage && typeof window.parent.AstrBotPluginPage.apiGet === "function") {
          rawBridge = window.parent.AstrBotPluginPage;
        } else if (window.parent && window.parent.bridge && typeof window.parent.bridge.apiGet === "function") {
          rawBridge = window.parent.bridge;
        }
      } catch (e) {}
    }
  } catch (e) {}

  if (rawBridge) {
    return {
      apiGet(endpoint, params) {
        const { ep, params: cleanParams } = cleanEndpointAndParams(endpoint, params);
        const _p = (cleanParams && Object.keys(cleanParams).length > 0)
          ? rawBridge.apiGet(ep, cleanParams)
          : rawBridge.apiGet(ep);
        // 读超时 30s（传文件类排除）；写操作另有服务端熔断，此处只治读 hung
        return _NO_TIMEOUT_GET.test(ep) ? _p : apiTimeout(_p, 30000, ep);
      },
      apiPost(endpoint, data) {
        const { ep } = cleanEndpointAndParams(endpoint);
        return rawBridge.apiPost(ep, data || {});
      },
      download(endpoint, params, filename) {
        const { ep, params: cleanParams } = cleanEndpointAndParams(endpoint, params);
        if (typeof rawBridge.download === "function") {
          return rawBridge.download(ep, cleanParams, filename);
        }
      }
      // 注：rawBridge.upload 已移除，上传一律走 postFile base64-JSON，禁裸 FormData 走桥
    };
  }

  return {
    apiGet(endpoint, params) {
      const { ep, params: cleanParams } = cleanEndpointAndParams(endpoint, params);
      // 整条前缀链 30s 总预算（传文件类排除）：黑洞前缀不再 eternal hang
      const _run = async () => {
      let fullEp = ep;
      if (cleanParams && Object.keys(cleanParams).length > 0) {
        fullEp += "?" + new URLSearchParams(cleanParams).toString();
      }
      if (_WORKING_API_PREFIX !== null) {
        try {
          const r = await fetch(_WORKING_API_PREFIX + fullEp);
          if (r.ok) return await r.json();
        } catch (err) {}
      }
      const prefixes = [`/api/plugins/${PLUGIN_ID}/`, `/${PLUGIN_ID}/`, `api/`, `./api/`, ``];
      for (const p of prefixes) {
        try {
          const r = await fetch(p + fullEp);
          if (r.ok) {
            _WORKING_API_PREFIX = p;
            return await r.json();
          }
        } catch (err) {}
      }
      const r = await fetch(fullEp);
      return await r.json();
      };
      const _p = _run();
      return _NO_TIMEOUT_GET.test(ep) ? _p : apiTimeout(_p, 30000, ep);
    },
    async apiPost(endpoint, data) {
      const { ep } = cleanEndpointAndParams(endpoint);
      if (_WORKING_API_PREFIX !== null) {
        try {
          const r = await fetch(_WORKING_API_PREFIX + ep, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data || {})
          });
          if (r.ok) return await r.json();
        } catch (err) {}
      }
      const prefixes = [`/api/plugins/${PLUGIN_ID}/`, `/${PLUGIN_ID}/`, `api/`, `./api/`, ``];
      for (const p of prefixes) {
        try {
          const r = await fetch(p + ep, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data || {})
          });
          if (r.ok) {
            _WORKING_API_PREFIX = p;
            return await r.json();
          }
        } catch (err) {}
      }
      const r = await fetch(ep, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data || {})
      });
      return await r.json();
    },
    async upload(endpoint, file) {
      // 已收口：禁用裸 FormData，一律走 postFile base64-JSON（法则12）
      return postFile(endpoint, {}, file);
    }
  };
}
let CFG = {};

// 请求超时竞速（桥 sequential fallback 无超时，环境黑洞会 eternal hang：
// Tab 首次加载卡死即此因。超时转拒绝，调用方显示可重试错误，不再永久占位）。
function apiTimeout(promise, ms, label) {
  const t = (typeof ms === "number" && ms > 0) ? ms : 20000;
  let timer = null;
  try {
    return Promise.race([
      Promise.resolve(promise),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("请求超时(" + Math.round(t / 1000) + "s)" + (label ? ":" + label : "") + "，点重试")), t);
        try { if (timer && typeof timer.unref === "function") timer.unref(); } catch (e) {}
      })
    ]).finally(() => { try { if (timer) clearTimeout(timer); } catch (e) {} });
  } catch (e) {
    return Promise.resolve(promise);
  }
}

// 各配置节归属系统（用于分类）+ 必要/玩法分层
const NECESSARY_SECTIONS = ["总开关配置", "群组开关配置", "网络", "维护配置"];
// 备份配置（含 WebDAV）已迁移至「备份管理」Tab 专属卡片，不在配置页重复渲染
const GAMEPLAY_SECTIONS = ["签到配置","抽奖配置","新手配置","点赞配置","银行配置","娱乐配置","精灵配置","坐骑配置","帮派配置","冒险配置","祈福配置","概率配置","唤醒词配置"];
const SYSTEM_MAP = {
  "设置": "奴隶系统", "费用配置": "奴隶系统", "间隔配置": "奴隶系统",
  "概率配置": "奴隶系统", "祈福配置": "奴隶系统",
  "签到配置": "签到系统", "抽奖配置": "签到系统",
  "新手配置": "签到系统", "点赞配置": "签到系统",
  "银行配置": "银行系统", "娱乐配置": "娱乐系统",
  "精灵配置": "精灵系统",
  "坐骑配置": "坐骑系统", "帮派配置": "帮派系统",
  "超管配置": "超管系统", "冒险配置": "冒险系统",
  "商城图鉴": "商城图鉴", "精灵图鉴": "精灵图鉴",
  "备份配置": "备份", "网络": "网络", "唤醒词配置": "唤醒词",
};
let CUR_SYSTEM = "全部";

// ---------- 主题(沙箱 iframe 禁止 localStorage, 仅内存切换) ----------
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  const b = document.getElementById("themeBtn");
  if (b) b.textContent = t === "dark" ? "☀" : "☾";
}
function initTheme() {
  applyTheme("light");
  const b = document.getElementById("themeBtn");
  if (b) b.addEventListener("click", () => {
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  });
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

// 请求 API 封装（支持 GET 自动转参数拼在 URL 与 fallback POST 双向兼容）
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
    try {
      let res = await _b.apiGet(cleanEp, cleanData);
      // 空数组/空对象是合法结果，直接返回；仅无响应或明确“未找到”才回退 POST，避免双倍请求
      if (!res || (res && res.status === "error" && res.message && res.message.includes("未找到"))) {
        res = await _b.apiPost(cleanEp, cleanData);
      }
      return res;
    } catch (e) {
      return await _b.apiPost(cleanEp, cleanData);
    }
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
  
    let actionsHtml = `
  <div style="margin:4px 0 10px;padding:12px;background:var(--panel2);border-radius:12px;border:1px solid var(--line);font-size:12.5px">
    <div style="font-weight:600;color:var(--text);margin-bottom:4px;word-break:break-all;font-size:13px">📄 ${esc(filename)} ${sizeKb ? `<span class="badge badge-primary" style="margin-left:6px">${sizeKb} KB</span>` : ""}</div>
    <div style="color:var(--muted);font-size:11.5px;line-height:1.5">文件已生成完成。若浏览器未自动弹出保存提示，请点击下方按钮手动保存：</div>
  </div>
  <div style="display:flex;gap:8px;margin:10px 0;flex-wrap:wrap">
    <a href="${blobUrl}" download="${esc(filename)}" id="btnModalSaveFileLink" class="btn" style="display:inline-flex;align-items:center;gap:5px;padding:8px 18px;background:var(--acc);color:#fff;border-radius:8px;font-weight:600;font-size:13px;text-decoration:none;cursor:pointer">⬇️ 保存文件到电脑</a>
    ${rawText ? `<button id="btnCopyExportData" class="ghost" style="padding:8px 14px;font-size:12.5px;cursor:pointer">📋 复制全部内容</button>` : ""}
  </div>
  ${rawText ? `<div style="margin-top:10px"><div style="font-size:11.5px;color:var(--muted);margin-bottom:4px">数据预览（点击文本框可自动全选）：</div><textarea readonly style="width:100%;height:100px;background:var(--panel);color:var(--text);font-family:monospace;font-size:11px;border:1px solid var(--line);border-radius:8px;padding:8px;outline:none;resize:vertical;line-height:1.4" onclick="this.select()">${esc(rawText.slice(0, 5000))}${rawText.length > 5000 ? "\n\n... (数据过长已截断预览，点击上方按钮复制全部数据)" : ""}</textarea></div>` : ""}
  `;

  if (content) content.innerHTML = actionsHtml;

  const saveBtn = document.getElementById("btnModalSaveFileLink");
  if (saveBtn) {
    saveBtn.onclick = (e) => {
      e.preventDefault();
      triggerDownload(blob, filename, rawText);
    };
  }

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
      const rawData = String(base64Data || "").replace(/^data:.*?;base64,/, "").replace(/\s/g, "").trim();
      const bin = atob(rawData);
      const len = bin.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
      blob = new Blob([bytes], { type: mime || "application/octet-stream" });
    } else if (rawText) {
      blob = new Blob([rawText], { type: mime || "application/json;charset=utf-8" });
    }
  }

  const blobUrl = blob ? URL.createObjectURL(blob) : "";
  let ok = false;
  if (blob) {
    ok = triggerDownload(blob, filename, rawText);
  }
  // 自动下载成功不再弹手动窗；失败才弹兜底（顺手释放预览URL防大zip常驻内存）
  if (!ok) {
    showExportModal({ filename, blob, blobUrl, rawText, base64Data });
  } else if (blobUrl) {
    try { URL.revokeObjectURL(blobUrl); } catch (e) {}
  }
}

function triggerDownload(blob, filename, rawText = "") {
  let downloaded = false;
  filename = filename || "download.json";

  // 1. 尝试通过 window.parent.document 触发（突破 iframe sandbox 拦截）
  try {
    if (window.parent && window.parent !== window && window.parent.document && window.parent.document.body) {
      const url = URL.createObjectURL(blob);
      const a = window.parent.document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = filename;
      window.parent.document.body.appendChild(a);
      a.click();
      setTimeout(() => { try { a.remove(); URL.revokeObjectURL(url); } catch(e) {} }, 1000);
      downloaded = true;
    }
  } catch (e) {}

  // 2. 尝试在本窗口 document 触发
  if (!downloaded) {
    try {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { try { a.remove(); URL.revokeObjectURL(url); } catch(e) {} }, 1000);
      downloaded = true;
    } catch (e) {}
  }

  // 3. 尝试 data URI (针对文本/JSON)
  if (!downloaded && rawText) {
    try {
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = "data:application/json;charset=utf-8," + encodeURIComponent(rawText);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { try { a.remove(); } catch(e) {} }, 1000);
      downloaded = true;
    } catch (e) {}
  }

  toast("已触发下载: " + filename, "ok");
  return downloaded;
}

function downloadJson(data, filename) {
  try {
    const str = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    const blob = new Blob([str], { type: "application/json;charset=utf-8" });
    triggerDownload(blob, filename || "export.json", str);
  } catch (err) {
    toast("导出失败: " + err.message, "bad");
  }
}

function downloadBase64File(base64Data, filename) {
  try {
    const rawData = String(base64Data || "").replace(/^data:.*?;base64,/, "").replace(/\s/g, "").trim();
    if (!rawData) throw new Error("数据为空");
    const bin = atob(rawData);
    const len = bin.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
    const mime = filename.endsWith(".zip") ? "application/zip" : (filename.endsWith(".json") ? "application/json;charset=utf-8" : "application/octet-stream");
    const blob = new Blob([bytes], { type: mime });
    triggerDownload(blob, filename || "download.bin");
  } catch (err) {
    toast("下载文件失败: " + err.message, "bad");
  }
}

function _formatModalText(msg) {
  if (!msg) return "";
  if (msg.includes("<div") || msg.includes("<strong") || msg.includes("<span") || msg.includes("<br")) {
    return msg;
  }
  return esc(String(msg))
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/^· (.*?)$/gm, "• $1")
    .split("\n").join("<br>");
}

function _safeImgSrc(u) {
  const s = String(u || "");
  return /^(data:image\/|https?:\/\/|\/|\.\/)/.test(s) ? s : "";
}

function _normalizeModalTitleAndIcon(rawTitle, rawIcon) {
  let title = String(rawTitle || "提示").trim();
  let icon = rawIcon ? String(rawIcon).trim() : "";

  // 匹配前导 Emoji（支持各种复杂组合 Emoji、变体选择符及跟随的空格）
  const emojiPrefixRegex = /^([\p{Extended_Pictographic}\uFE0E\uFE0F\u200D\u20E3\u2600-\u27BF]|\s)+/u;
  const match = title.match(emojiPrefixRegex);

  if (match) {
    const extractedEmoji = match[0].trim();
    const cleanTitle = title.replace(emojiPrefixRegex, "").trim();
    if (cleanTitle) {
      title = cleanTitle;
    }
    // 若未显式指定 icon 或指定的是默认占位符 ℹ️，则将 title 前导 emoji 作为 icon
    if (!icon || icon === "ℹ️") {
      icon = extractedEmoji;
    }
  }

  if (!icon) icon = "ℹ️";
  if (!title) title = "提示";

  return { title, icon };
}

function uiAlert(msg, rawTitle = "提示", rawIcon = "ℹ️") {
  const norm = _normalizeModalTitleAndIcon(rawTitle, rawIcon);
  const title = norm.title;
  const icon = norm.icon;

  return new Promise((resolve) => {
    const modal = document.getElementById("appModal");
    if (!modal) {
      if (window.alert) window.alert(title + "\n\n" + msg.replace(/<[^>]+>/g, ""));
      resolve(true);
      return;
    }
    const closeBtn = document.getElementById("appModalClose");
    const iconEl = document.getElementById("appModalIcon");
    if (iconEl) {
      iconEl.textContent = icon;
      iconEl.style.color = (icon === "⚠️" || icon === "❌" || icon === "🗑️") ? "var(--bad)" : ((icon === "✅" || icon === "🟢") ? "var(--ok)" : "var(--acc)");
    }
    const titleEl = document.getElementById("appModalTitle");
    if (titleEl) titleEl.textContent = title;
    const contentEl = document.getElementById("appModalContent");
    if (contentEl) contentEl.innerHTML = _formatModalText(msg);
    const inpWrap = document.getElementById("appModalInputWrap");
    if (inpWrap) inpWrap.style.display = "none";
    
    const okBtn = document.getElementById("appModalOk");
    const cancelBtn = document.getElementById("appModalCancel");
    if (cancelBtn) cancelBtn.style.display = "none";
    if (okBtn) {
      okBtn.textContent = "确定";
      okBtn.style.display = "";
      okBtn.style.background = "var(--acc)";
      okBtn.style.borderColor = "transparent";
    }

    modal.classList.add("show");

    const clean = () => {
      modal.classList.remove("show");
      if (okBtn) okBtn.onclick = null;
      if (closeBtn) closeBtn.onclick = null;
      modal.onclick = null;
      if (cancelBtn) cancelBtn.style.display = "";
    };

    if (okBtn) okBtn.onclick = () => { clean(); resolve(true); };
    if (closeBtn) closeBtn.onclick = () => { clean(); resolve(true); };
    modal.onclick = (e) => { if (e.target === modal) { clean(); resolve(true); } };
  });
}

function uiConfirm(msg, rawTitle = "确认操作") {
  const isDanger = /危险|清空|删除|覆盖|终极/.test(rawTitle + msg);
  const norm = _normalizeModalTitleAndIcon(rawTitle, isDanger ? "⚠️" : "ℹ️");
  const title = norm.title;
  const icon = norm.icon;

  return new Promise((resolve) => {
    const modal = document.getElementById("appModal");
    if (!modal) {
      try { toast("弹窗不可用，已取消操作", "bad"); } catch (e) {}
      resolve(false);
      return;
    }
    const closeBtn = document.getElementById("appModalClose");
    const iconEl = document.getElementById("appModalIcon");
    if (iconEl) {
      iconEl.textContent = icon;
      iconEl.style.color = (icon === "⚠️" || icon === "❌" || icon === "🗑️" || isDanger) ? "var(--bad)" : "var(--acc)";
    }
    const titleEl = document.getElementById("appModalTitle");
    if (titleEl) titleEl.textContent = title;
    const contentEl = document.getElementById("appModalContent");
    if (contentEl) contentEl.innerHTML = _formatModalText(msg);
    const inpWrap = document.getElementById("appModalInputWrap");
    if (inpWrap) inpWrap.style.display = "none";

    const okBtn = document.getElementById("appModalOk");
    const cancelBtn = document.getElementById("appModalCancel");
    if (cancelBtn) {
      cancelBtn.style.display = "";
      cancelBtn.textContent = "取消";
    }
    if (okBtn) {
      okBtn.textContent = isDanger ? "确认" : "确定";
      if (isDanger) {
        okBtn.style.background = "var(--bad)";
        okBtn.style.borderColor = "var(--bad)";
      } else {
        okBtn.style.background = "var(--acc)";
        okBtn.style.borderColor = "transparent";
      }
    }

    modal.classList.add("show");

    const clean = () => {
      modal.classList.remove("show");
      if (okBtn) okBtn.onclick = null;
      if (cancelBtn) cancelBtn.onclick = null;
      if (closeBtn) closeBtn.onclick = null;
      modal.onclick = null;
    };
    if (okBtn) okBtn.onclick = () => { clean(); resolve(true); };
    if (cancelBtn) cancelBtn.onclick = () => { clean(); resolve(false); };
    if (closeBtn) closeBtn.onclick = () => { clean(); resolve(false); };
    modal.onclick = (e) => { if (e.target === modal) { clean(); resolve(false); } };
  });
}

function uiPrompt(msg, dflt = "", rawTitle = "请输入") {
  const norm = _normalizeModalTitleAndIcon(rawTitle, "✏️");
  const title = norm.title;
  const icon = norm.icon;

  return new Promise((resolve) => {
    const modal = document.getElementById("appModal");
    if (!modal) {
      try { toast("弹窗不可用，已取消操作", "bad"); } catch (e) {}
      resolve(null);
      return;
    }
    const closeBtn = document.getElementById("appModalClose");
    const iconEl = document.getElementById("appModalIcon");
    if (iconEl) { iconEl.textContent = icon; iconEl.style.color = "var(--acc)"; }
    document.getElementById("appModalTitle").textContent = title;
    document.getElementById("appModalContent").textContent = msg;
    const inpWrap = document.getElementById("appModalInputWrap");
    const inp = document.getElementById("appModalInput");
    inpWrap.style.display = "block";
    inp.value = dflt || "";
    modal.classList.add("show");
    setTimeout(() => { inp.focus(); inp.select(); }, 50);

    const okBtn = document.getElementById("appModalOk");
    const cancelBtn = document.getElementById("appModalCancel");
    okBtn.style.background = "var(--acc)";
    okBtn.style.borderColor = "transparent";

    const clean = () => {
      modal.classList.remove("show");
      if (okBtn) okBtn.onclick = null;
      if (cancelBtn) cancelBtn.onclick = null;
      if (closeBtn) closeBtn.onclick = null;
      modal.onclick = null;
      inp.onkeydown = null;
    };
    const doOk = () => { const v = inp.value; clean(); resolve(v); };
    if (okBtn) okBtn.onclick = doOk;
    if (cancelBtn) cancelBtn.onclick = () => { clean(); resolve(null); };
    if (closeBtn) closeBtn.onclick = () => { clean(); resolve(null); };
    modal.onclick = (e) => { if (e.target === modal) { clean(); resolve(null); } };
    inp.onkeydown = (e) => {
      if (e.key === "Enter") { e.preventDefault(); doOk(); }
      else if (e.key === "Escape") { e.preventDefault(); clean(); resolve(null); }
    };
  });
}

function bindGroupsAdd() {
  const inp = document.getElementById("groupsAddGid");
  const btn = document.getElementById("btnGroupsAdd");
  if (!inp || !btn) return;
  btn.onclick = async () => {
    const gid = (inp.value || "").trim();
    if (!/^\d{5,15}$/.test(gid)) { toast("请输入5-15位数字群号", "bad"); return; }
    btn.disabled = true;
    btn.textContent = "添加中...";
    try {
      const r = await getBridge().apiPost("groups/toggle", { gid, enabled: true });
      if (r && r.ok === false) { toast("添加失败: " + (r.msg || JSON.stringify(r)), "bad"); return; }
      toast("已成功添加群 " + gid, "ok");
      inp.value = "";
      await loadGroups();
    } catch(e) { toast("添加失败: " + e.message, "bad"); }
    finally {
      btn.disabled = false;
      btn.textContent = "➕ 添加";
    }
  };
  inp.onkeydown = (e) => { if (e.key === "Enter") btn.onclick(); };
}

let RAW_GROUPS = [];

async function loadGroups() {
  bindGroupsAdd();
  const box = document.getElementById("groupsBody");
  if (!box) return;
  box.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:16px;color:var(--muted)">加载中...</td></tr>`;
  try {
    const data = await getBridge().apiGet("groups/list");
    RAW_GROUPS = data.groups || data || [];
    renderGroupsTable();
  } catch(e) {
    box.innerHTML = `<tr><td colspan="5" style="color:var(--bad);text-align:center;padding:16px">加载失败: ${esc(e.message)}</td></tr>`;
  }
}

function renderGroupsTable() {
  const box = document.getElementById("groupsBody");
  if (!box) return;
  const kw = (document.getElementById("groupsSearch")?.value || "").trim().toLowerCase();
  let groups = [...RAW_GROUPS];
  if (kw) {
    groups = groups.filter(g => String(g.gid).toLowerCase().includes(kw) || (g.enabled ? "开启" : "关闭").includes(kw));
  }
  if (!groups.length) {
    box.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--muted)">暂无匹配的群聊数据<br><small>可上方手动输入群号添加</small></td></tr>`;
    return;
  }
  box.innerHTML = groups.map(g => {
    const gid = g.gid;
    const on = g.enabled !== false;
    const badge = on ? `<span class="badge badge-success">开启</span>` : `<span class="badge badge-bad">关闭</span>`;
    const testMark = g.is_test ? ` <small style="color:var(--muted)">(测试)</small>` : "";
    const maint = g.maintenance === true;
    const maintBadge = maint ? `<span class="badge badge-bad">维修中</span>` : `<span style="color:var(--muted)">—</span>`;
    return `<tr><td><code>${esc(gid)}</code>${testMark}</td><td>${g.member_count || 0}</td><td>${badge}</td><td>${maintBadge}</td><td><label class="switch" title="本群维修开关"><input type="checkbox" data-maint-gid="${esc(gid)}" ${maint ? "checked" : ""}><span class="slider-toggle"></span></label></td><td><label class="switch" title="群聊开关"><input type="checkbox" data-gid="${esc(gid)}" ${on ? "checked" : ""}><span class="slider-toggle"></span></label></td></tr>`;
  }).join("");
  box.querySelectorAll("input[data-gid]").forEach(inp => {
    inp.addEventListener("change", async () => {
      const gid = inp.dataset.gid;
      const on = inp.checked;
      inp.disabled = true;
      const row = inp.closest("tr");
      const badgeCell = row ? row.cells[2] : null;
      try {
        const r = await getBridge().apiPost("groups/toggle", { gid, enabled: on });
        if (r && r.ok === false) throw new Error(r.msg || "切换失败");
        const serverOn = (r && typeof r.enabled === "boolean") ? r.enabled : on;
        toast(`群 ${gid} 已${serverOn ? "开启" : "关闭"}`, serverOn ? "ok" : "bad");
        if (badgeCell) badgeCell.innerHTML = serverOn ? `<span class="badge badge-success">开启</span>` : `<span class="badge badge-bad">关闭</span>`;
        inp.checked = serverOn;
      } catch(e) {
        toast("切换失败: " + e.message, "bad");
        inp.checked = !on;
      } finally {
        inp.disabled = false;
      }
    });
  });
  box.querySelectorAll("input[data-maint-gid]").forEach(inp => {
    inp.addEventListener("change", async () => {
      const gid = inp.dataset.maintGid;
      const on = inp.checked;
      inp.disabled = true;
      try {
        const r = await getBridge().apiPost("groups/toggle", { gid, maintenance: on });
        if (r && r.ok === false) throw new Error(r.msg || "切换失败");
        const serverOn = (r && typeof r.maintenance === "boolean") ? r.maintenance : on;
        toast(`群 ${gid} ${serverOn ? "进入维修（仅@回复）" : "退出维修"}`, serverOn ? "bad" : "ok");
        await loadGroups();
      } catch(e) {
        toast("切换失败: " + e.message, "bad");
        inp.checked = !on;
      } finally {
        inp.disabled = false;
      }
    });
  });
}
document.getElementById("btnGroupsRefresh")?.addEventListener("click", () => loadGroups());

// 各页签加载器(零延迟即时响应)
const TAB_LOADERS = {
  overview: async () => { await loadOverviewReq(); try { await loadAnalytics(); } catch(e){} },
  users: async () => { return loadUsers(); },
  slave: async () => { return typeof loadSlaveUsers === "function" ? loadSlaveUsers() : Promise.resolve(); },
  spirit_users: async () => { return typeof loadSpiritUsers === "function" ? loadSpiritUsers() : Promise.resolve(); },
  config: async () => { return loadConfig(); },
  rank: async () => { const t = (document.getElementById("rankType") || {}).value || "money"; return loadRank(t); },
  cmds: async () => { return loadCommands(); },
  spirits: async () => { let r; try { r = await loadSpirits(); } catch(e) { try { err("tab spirits: " + e.message); } catch(_e){} } try { await loadShops(true); try { if (typeof refreshSpiritViews === "function") refreshSpiritViews(); } catch(_e){} } catch(e){} return r; },
  shops: async () => { return loadShops(); },
  backups: async () => {
    if (typeof loadBackupCfg === "function") try { await loadBackupCfg(); } catch (e) {}
    if (typeof loadRemoteWebDAVFiles === "function") try { await loadRemoteWebDAVFiles(); } catch (e) {}
    return typeof loadBackups === "function" ? loadBackups("") : Promise.resolve();
  },
  imgs: async () => { return loadImages(""); },
  groups: async () => { return loadGroups(); },
  about: async () => { try { await checkVersionUpdate(true); } catch (e) {} },
  logs: async () => { return loadLogs(); },
};
const TAB_DONE = {};

function initBackTop() {
  // 回到顶部：窗口滚动过半屏出现；点击回窗顶并顺带复位页内滚动区（图鉴/日志）
  try {
    const btn = document.getElementById("backTop");
    if (!btn || btn.dataset.bound) return;
    btn.dataset.bound = "1";
    const onScroll = () => {
      try {
        const y = window.scrollY || document.documentElement.scrollTop || 0;
        btn.style.display = y > 400 ? "" : "none";
      } catch (e) {}
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    btn.addEventListener("click", () => {
      try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { try { window.scrollTo(0, 0); } catch (err) {} }
      ["atlasBox", "logTerminal"].forEach((id) => {
        try { const el = document.getElementById(id); if (el && el.scrollTop > 0) el.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) {}
      });
      onScroll();
    });
    onScroll();
  } catch (e) {}
}

async function main() {
  initTheme();
  bindTabs();
  try { initBackTop(); } catch (e) {}
  try { bindShopOrderOnce(); } catch (e) {}
  const _b = getBridge();
  try {
    if (_b && typeof _b.ready === "function") {
      await Promise.race([
        _b.ready(),
        new Promise(r => setTimeout(r, 300))
      ]);
    }
  } catch (e) {}
  
  Promise.all([loadOverviewReq(), loadAnalytics()]).catch(() => {});
  TAB_DONE.overview = true;
}

// ---------- 图片库（根目录） ----------
let IMG_DIR = "";
let IMG_CACHE = [];   // 当前目录的 dirs+files 原始数据(供搜索)
let IMG_CLIP = "";    // 复制的路径
let IMG_SELECTED = ""; // 选中的文件/文件夹路径（用于复制/导出）


async function loadImages(dir) {
  try {
    if (dir === "0") dir = "";
    IMG_DIR = dir || "";
    const d = await getBridge().apiGet("images/list", { dir: IMG_DIR });
    IMG_CACHE = d;
    // 面包屑
    const segs = (d.dir || "").split("/").filter(Boolean);
    let crumb = `<a data-imgcrumb="">根目录</a>`;
    let acc = "";
    segs.forEach((s, i) => {
      acc += (acc ? "/" : "") + s;
      crumb += ` / <a data-imgcrumb="${esc(acc)}">${esc(s)}</a>`;
    });
    document.getElementById("imgCrumbs").innerHTML = `<span class="crumbs">${crumb}</span>`;
    document.querySelectorAll("#imgCrumbs a[data-imgcrumb]").forEach((a) =>
      a.addEventListener("click", () => loadImages(a.dataset.imgcrumb)));
    renderImages(d);
  } catch (e) {
    err("images: " + e.message);
  }
}

function renderImages(d) {
  const box = document.getElementById("imgBrowser");
  const q = (document.getElementById("imgSearch").value || "").trim().toLowerCase();
  // 供内置选图校验（是否为文件夹）
  window._imgIsDir = (p) => (d.dirs || []).some(x => x.path === p);
  const isShopPick = !!window.SHOP_PICK_TARGET;
  let html = `<div class="grid">`;
  (d.dirs || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    // 内置选图模式下：文件夹仅可双击进入，不可选中
    if (isShopPick) {
      html += `<div class="fcard" data-imgdir="${esc(x.path)}"><div class="fi">📁</div><div class="fn">${esc(x.name)}</div></div>`;
    } else {
      const selCls = IMG_SELECTED===x.path ? ' selected' : '';
      html += `<div class="fcard${selCls}" data-imgdir="${esc(x.path)}" data-selpath="${esc(x.path)}"><div class="fi">📁</div><div class="fn">${esc(x.name)}</div></div>`;
    }
  });
  (d.files || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    const ext = (x.name.split(".").pop()||"").toLowerCase();
    const isImg = ["png","jpg","jpeg","gif","webp","bmp","ico"].includes(ext);
    // 内置选图模式：仅展示图片文件
    if (isShopPick && !isImg) return;
    const selCls = IMG_SELECTED===x.path ? ' selected' : '';
    let ficon = "📄";
    if (isImg) ficon="";
    else if (ext==="json") ficon="📄";
    else if (ext==="md") ficon="📝";
    else if (ext==="txt") ficon="📃";
    else if (ext==="py") ficon="🐍";
    else if (ext==="db"||ext==="db-wal"||ext==="db-shm") ficon="🗄️";
    else if (ext==="ini") ficon="⚙️";
    else if (ext==="zip") ficon="🗜️";
    else if (ext==="log") ficon="📜";
    html += `<div class="icard${selCls}" data-imgsrc="${esc(x.img)}" data-imgname="${esc(x.name)}" data-imgpath="${esc(x.path)}" data-selpath="${esc(x.path)}">` +
      (ficon ? `<div style="height:120px;display:flex;align-items:center;justify-content:center;font-size:42px;background:var(--panel2)">${ficon}</div>` : `<img loading="lazy" decoding="async" src="${esc(_safeImgSrc(x.img))}" alt="">`) + `<div class="nm">${esc(x.name)}</div></div>`;
  });
  html += `</div>`;
  box.innerHTML = html;
  // 文件夹：单击选中（非选图模式）/双击进入
  box.querySelectorAll("[data-imgdir]").forEach((el) =>{
    el.addEventListener("click", (e) => {
      if (window.SHOP_PICK_TARGET) return;
      IMG_SELECTED = el.dataset.imgdir;
      box.querySelectorAll(".fcard, .icard").forEach(c => c.classList.remove("selected"));
      el.classList.add("selected");
    });
    el.addEventListener("dblclick", (e) => {
      loadImages(el.dataset.imgdir);
    });
  });
  // 文件：单击选中（高亮）
  box.querySelectorAll("[data-selpath]").forEach((el)=>{
    el.addEventListener("click", (e)=>{
      IMG_SELECTED = el.dataset.selpath;
      box.querySelectorAll(".fcard, .icard").forEach(c => c.classList.remove("selected"));
      el.classList.add("selected");
    });
  });
  // 图片点击：先选中再预览（不阻断选中）
  box.querySelectorAll("[data-imgsrc]").forEach((el) => {
    el.querySelector("img")?.addEventListener("click", (e) => {
      e.stopPropagation();
      const p = el.dataset.imgpath || el.dataset.selpath;
      if (p) {
        IMG_SELECTED = p;
        box.querySelectorAll(".fcard, .icard").forEach(c => c.classList.remove("selected"));
        el.classList.add("selected");
      }
      if (el.dataset.imgsrc) showLightbox(el.dataset.imgsrc, el.dataset.imgname);
    });
  });
  // 文件列表供搜索(懒加载图片已在上面)
  window._imgFiles = (d.files || []).map((x) => x.name);
}

function showLightbox(src, name) {
  const lb = document.getElementById("lightbox");
  if (!lb || !src) { if (lb) { lb.innerHTML = ""; } return; }
  lb.innerHTML = `<img src="${esc(_safeImgSrc(src))}"><div class="cap">${esc(name || "")}</div>`;
  lb.classList.add("show");
}

function closeLightbox() {
  const lb = document.getElementById("lightbox");
  if (lb) { lb.classList.remove("show"); lb.innerHTML = ""; }
}

function fileToBase64(file) {
  return new Promise((res, rej) => {
    try {
      const fr = new FileReader();
      fr.onload = () => {
        const s = String(fr.result || "");
        res(s.includes(",") ? s.split(",", 2)[1] : s);
      };
      fr.onerror = () => rej(new Error("文件读取失败"));
      fr.readAsDataURL(file);
    } catch (e) { rej(e); }
  });
}
async function postFile(api, extra, file) {
  // base64 JSON 直传：iframe 桥 postMessage 无法克隆 FormData，后端同样受理
  const b64 = await fileToBase64(file);
  if (!b64) throw new Error("文件读取失败");
  return getBridge().apiPost(api, { ...(extra || {}), filename: file.name, file_base64: b64 });
}
async function uploadImage(file) {
  if (!file) return;
  toast("上传中…", "");
  try {
    await postFile("images/upload?dir=" + encodeURIComponent(IMG_DIR || "data/img"), {}, file);
    toast("已上传", "ok");
    await loadImages(IMG_DIR);
  } catch (e) {
    err("上传失败: " + e.message);
  }
}

function bindTabs() {
  const btns = document.querySelectorAll(".tabs button");
  btns.forEach((b) => {
    b.addEventListener("click", () => {
      btns.forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("on"));
      const el = document.getElementById("tab-" + b.dataset.tab);
      if (el) el.classList.add("on");
      const tab = b.dataset.tab;
      if (tab === "logs") {
        if (typeof loadLogs === "function") loadLogs(false);
        if (typeof startLogsAutoRefresh === "function") startLogsAutoRefresh();
      } else {
        if (typeof stopLogsAutoRefresh === "function") stopLogsAutoRefresh();
      }
      // 切换 Tab 时保证当前选中按钮在可视区内
      try { b.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" }); } catch (e) {}
      // 总览页每次点击都刷新，确保机器人QQ等快捷配置与配置页保持一致（同一接口 ST._CONFIG）
      if (tab === "overview") {
        Promise.resolve(loadOverviewReq()).catch((e) => err("tab overview: " + e.message));
        Promise.resolve(loadStats()).catch(() => {});
        return;
      }
      if (!TAB_DONE[tab] && TAB_LOADERS[tab]) {
        TAB_DONE[tab] = true;
        // 失败回退未完成态：下次切回重跑（曾首次 hang 即永久占位，只能整页刷新）
        Promise.resolve(TAB_LOADERS[tab]()).then(() => {}).catch((e) => {
          try { TAB_DONE[tab] = false; } catch (_e) {}
          err("tab " + tab + ": " + e.message);
        });
      }
    });
  });

  // Tab 栏左右滚动箭头 + 滚轮横滑
  const tabsContainer = document.getElementById("mainTabs");
  document.getElementById("tabNavPrev")?.addEventListener("click", () => {
    if (tabsContainer) tabsContainer.scrollBy({ left: -160, behavior: "smooth" });
  });
  document.getElementById("tabNavNext")?.addEventListener("click", () => {
    if (tabsContainer) tabsContainer.scrollBy({ left: 160, behavior: "smooth" });
  });
  tabsContainer?.addEventListener("wheel", (e) => {
    if (Math.abs(e.deltaX) < Math.abs(e.deltaY)) {
      e.preventDefault();
      tabsContainer.scrollLeft += e.deltaY;
    }
  }, { passive: false });
}

function err(m) {
  const e = document.getElementById("footErr");
  if (e) e.textContent = "加载/操作异常: " + m;
  toast("操作异常：" + m, "bad");
  console.error(m);
}

// ---------- 总览 ----------
async function loadStats() {
  return loadAnalytics();
}

// 必填/关键配置: [节, 键, 标签, 类型, 提示] — 网络/机器人QQ已移除（完全自动）
const OV_REQ = [
  ["设置", "货币名称", "货币名称", "text", "金币/积分 等显示名"],
];

async function loadOverviewReq() {
  try {
    const cur = await getBridge().apiGet("config/get");
    // schema 默认回退：内存缺键时显示出厂默认值而非空白（如货币名称）
    let _defs = {};
    try {
      const _sch = await getBridge().apiGet("config/schema").catch(() => null);
      ((_sch && _sch.groups && _sch.groups["设置"]) || []).forEach((it) => { _defs[it.key] = it.default; });
    } catch (e) {}
    const box = document.getElementById("ovReq");
    box.innerHTML = OV_REQ.map(([sec, key, label, type, tip]) => {
      const v = ((cur || {})[sec] || {})[key] ?? _defs[key] ?? "";
      return `<div class="ov-field"><label>${esc(label)}</label>` +
        `<input data-ov-sec="${esc(sec)}" data-ov-key="${esc(key)}" type="${type === "int" ? "number" : "text"}" value="${esc(v)}">` +
        `<small>${esc(tip)}</small></div>`;
    }).join("") +
      `<div class="ov-field"><label style="visibility:hidden">.</label><button id="btnOvReqSave">保存必要配置</button></div>`;
    const b = document.getElementById("btnOvReqSave");
    if (b) b.addEventListener("click", saveOverviewReq);
  } catch (e) {
    err("必要配置: " + e.message);
  }
}

async function saveOverviewReq() {
  const toastMsg = (m, t) => { try { toast(m, t); } catch (e) {} };
  try {
    const payload = {};
    document.querySelectorAll("#ovReq [data-ov-sec]").forEach((inp) => {
      const sec = inp.dataset.ovSec, key = inp.dataset.ovKey;
      if (!payload[sec]) payload[sec] = {};
      payload[sec][key] = inp.type === "number" ? Number(inp.value) : inp.value.trim();
    });
    await getBridge().apiPost("config/save", payload);
    toastMsg("必要配置已保存", "ok");
    await loadOverviewReq();
    // 若配置页已加载过，同步刷新，使“网络.bot_uin”等在配置页立即可见
    if (TAB_DONE.config) {
      try { await loadConfig(); } catch (e) {}
    }
  } catch (e) {
    toastMsg("保存失败: " + e.message, "bad");
    err("保存必要配置失败: " + e.message);
  }
}

// ---------- 配置 ----------
function isFlag(v) {
  return ["真", "假", "true", "false", "1", "0"].includes(String(v));
}
function flagVal(v) {
  return String(v) === "真" || String(v) === "true" || String(v) === "1";
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// AstrBot 官方嵌套 schema 合法类型: int,float,bool,string,text,list,file,object,template_list
// 约定: 真/假 开关在 schema 保持 string(引擎用 =="真"), 由 isFlag 渲染 checkbox;
// text/list 用多行 textarea, string 单行, int/float 用 number
function isTextType(t) {
  return t === "text";
}
function isListType(t) {
  return t === "list";
}

const BALANCE_MODE_META = {
  standard: { icon: "🟢", label: "标准平衡模式", fg: "var(--ok)", bg: "rgba(52,199,89,0.12)", bd: "var(--ok)" },
  casual: { icon: "🟡", label: "休闲高福利模式", fg: "#EAB308", bg: "rgba(234,179,8,0.15)", bd: "rgba(234,179,8,0.3)" },
  hardcore: { icon: "🔴", label: "硬核博弈模式", fg: "var(--bad)", bg: "rgba(255,59,48,0.1)", bd: "var(--bad)" },
};
async function refreshBalanceBadges() {
  // 徽标按真实档位+漂移检测刷新（此前写死休闲，属显示问题）
  const paint = (mode, drift) => {
    const meta = BALANCE_MODE_META[mode] || BALANCE_MODE_META.standard;
    ["activeBalanceBadge1", "activeBalanceBadge2"].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (drift > 0) {
        el.textContent = `⚪ ${meta.label}（已偏离${drift}项）`;
        el.style.color = "var(--muted)"; el.style.background = "var(--panel2)"; el.style.border = "1px solid var(--line)";
        el.title = "数值与该档预设不一致，可点开重选覆盖";
      } else {
        el.textContent = `${meta.icon} 当前生效：${meta.label}`;
        el.style.color = meta.fg; el.style.background = meta.bg; el.style.border = `1px solid ${meta.bd}`;
        el.title = "点击切换数值平衡模式";
      }
    });
  };
  try {
    const st = await getBridge().apiGet("config/balance_state").catch(() => null);
    if (st && st.ok && st.mode) { paint(st.mode, st.mismatch || 0); return; }
  } catch (e) {}
  try {
    const cfg = await getBridge().apiGet("config/get").catch(() => null);
    const m = (cfg && (cfg._active_balance_mode || (cfg["设置"] && cfg["设置"]["平衡模式"]))) || "standard";
    paint(["standard", "casual", "hardcore"].includes(m) ? m : "standard", 0);
  } catch (e) {}
}
["activeBalanceBadge1", "activeBalanceBadge2"].forEach((id) => {
  document.getElementById(id)?.addEventListener("click", () => {
    try { if (typeof openAutoBalanceModal === "function") openAutoBalanceModal(); } catch (e) {}
  });
});
async function loadConfig() {
  try {
    const [schema, cur] = await Promise.all([
      getBridge().apiGet("config/schema"),
      getBridge().apiGet("config/get")
    ]);
    CFG = { schema, cur };
    const form = document.getElementById("cfgForm");
    if (!form) return;
    form.innerHTML = "";
    const { groups } = schema;
    const necessaryGroups = {};
    Object.keys(groups).forEach((sec) => {
      if (NECESSARY_SECTIONS.includes(sec)) necessaryGroups[sec] = groups[sec];
    });
    const effectiveGroups = Object.keys(necessaryGroups).length ? necessaryGroups : groups;

    for (const sec of Object.keys(effectiveGroups)) {
      const box = document.createElement("div");
      box.className = "cfg-sec";
      box.dataset.system = SYSTEM_MAP[sec] || "其它";
      box.innerHTML = `<h3 style="margin:0 0 10px;font-size:13.5px;display:flex;align-items:center;gap:6px">📌 ${esc(sec)} <span class="badge badge-primary" style="font-size:11px;font-weight:normal">${esc(SYSTEM_MAP[sec] || "基础")}</span></h3>`;
      for (const it of effectiveGroups[sec]) {
        const v = ((cur || {})[sec] || {})[it.key] ?? it.default;
        const attrs = `data-sec="${esc(sec)}" data-key="${esc(it.key)}"`;
        const row = document.createElement("div");
        row.className = "cfg-row";
        const small = `<small>${esc(it.desc || "")}</small>`;
        if (isFlag(it.default)) {
          row.className = "cfg-row has-checkbox";
          const chk = flagVal(v) ? "checked" : "";
          row.innerHTML = `<label>${esc(it.key)}</label>` +
            `<label class="switch"><input type="checkbox" ${chk} ${attrs}><span class="slider-toggle"></span></label>${small}`;
        } else if (isTextType(it.type) || isListType(it.type)) {
          row.innerHTML = `<label>${esc(it.key)}</label>` +
            `<textarea rows="${isListType(it.type) ? 3 : 2}" ${attrs}>${esc(v)}</textarea>${small}`;
        } else if (it.type === "int" && /^-?\d+$/.test(String(v))) {
          row.innerHTML = `<label>${esc(it.key)}</label>` +
            `<input type="number" step="1" value="${esc(v)}" ${attrs}>${small}`;
        } else if (it.type === "float" && !isNaN(parseFloat(v))) {
          row.innerHTML = `<label>${esc(it.key)}</label>` +
            `<input type="number" step="any" value="${esc(v)}" ${attrs}>${small}`;
        } else {
          row.innerHTML = `<label>${esc(it.key)}</label>` +
            `<input type="text" value="${esc(v)}" ${attrs}>${small}`;
        }
        box.appendChild(row);
      }
      form.appendChild(box);
    }
    try { refreshBalanceBadges(); } catch (e) {}
  } catch (e) {
    err("config: " + e.message);
  }
}
function filterCfg() {
  const q = (document.getElementById("cfgSearch").value || "").trim().toLowerCase();
  document.querySelectorAll("#cfgForm .cfg-sec").forEach((box) => {
    const sysMatch = CUR_SYSTEM === "全部" || box.dataset.system === CUR_SYSTEM;
    const txtMatch = !q || box.textContent.toLowerCase().includes(q);
    if (q) {
      box.style.display = txtMatch ? "" : "none";   // 搜索时忽略系统分类
    } else {
      box.style.display = sysMatch ? "" : "none";
    }
  });
}

function filterCmds() {
  const q = (document.getElementById("cmdSearch").value || "").trim().toLowerCase();
  document.querySelectorAll("#cmdList .cmd-block").forEach((b) => {
    b.style.display = !q || b.textContent.toLowerCase().includes(q) ? "" : "none";
  });

}



async function openAutoBalanceModal() {
  const modal = document.getElementById("appModal");
  if (!modal) return;
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");

  if (icon) icon.textContent = "🎯";
  if (title) title.textContent = "游戏奖励 / 惩罚 / 概率 · 智能数值平衡";
  if (inputWrap) inputWrap.style.display = "none";

  // 档位以 balance_state 逐档推断为准：出厂种子实为休闲数值但标记缺省 standard，
  // 直接读标记会 perpetual 误报偏离；推断命中哪档就预选哪档，只报真偏离
  let activeMode = "standard";
  let _driftInfo = "";
  try {
    const st = await getBridge().apiGet("config/balance_state").catch(() => null);
    if (st && st.ok && st.mode && ["standard", "casual", "hardcore"].includes(st.mode)) {
      activeMode = st.mode;
      if (st.mismatch > 0) {
        const _names = (st.mismatches || []).map((x) => x.key).join("、");
        const _mlabel = ((typeof BALANCE_MODE_META !== "undefined" && BALANCE_MODE_META[activeMode]) || {}).label || activeMode;
        _driftInfo = `<div style="font-size:12px;color:var(--warn);background:var(--warnSoft);border:1px solid var(--warn);border-radius:8px;padding:8px 10px;margin-bottom:12px">⚠️ 当前数值已偏离${_mlabel}（${st.mismatch}项不符${_names ? "：" + esc(_names) : ""}），可重选一键覆盖，或去指令页逐项手调。</div>`;
      }
    } else {
      const cfg = await getBridge().apiGet("config/get");
      const m = (cfg && (cfg._active_balance_mode || (cfg["设置"] && cfg["设置"]["平衡模式"]))) || "standard";
      activeMode = ["standard", "casual", "hardcore"].includes(m) ? m : "standard";
    }
  } catch (e) { activeMode = "standard"; }

  content.innerHTML = `
    <div style="font-size:12px;color:var(--muted);margin-bottom:12px;line-height:1.5">
      系统基于<strong>群博弈论与经济学精算模型</strong>，为你自动推算并一键匹配最佳货币奖励、惩罚倍率、抽奖爆率与奴隶身价成长曲线：
    </div>${_driftInfo}
    <div style="display:flex;flex-direction:column;gap:10px">
      <label style="display:flex;align-items:flex-start;gap:10px;padding:12px;background:var(--panel2);border:${activeMode === "standard" ? "2px solid var(--acc)" : "1px solid var(--line)"};border-radius:12px;cursor:pointer">
        <input type="radio" name="balanceMode" value="standard" ${activeMode === "standard" ? "checked" : ""} style="margin-top:3px">
        <div>
          <div style="font-weight:600;color:var(--text);font-size:13px">🟢 标准平衡模式（官方推荐 · 经济稳健）</div>
          <div style="font-size:11.5px;color:var(--muted);margin-top:2px">签到 300-800 + 连签 50，利率 2%，造反率 35%，祈福爆发 5%。平稳通胀，适合绝大多数群聊。</div>
        </div>
      </label>
      <label style="display:flex;align-items:flex-start;gap:10px;padding:12px;background:var(--panel2);border:${activeMode === "casual" ? "2px solid var(--acc)" : "1px solid var(--line)"};border-radius:12px;cursor:pointer">
        <input type="radio" name="balanceMode" value="casual" ${activeMode === "casual" ? "checked" : ""} style="margin-top:3px">
        <div>
          <div style="font-weight:600;color:var(--text);font-size:13px">🟡 休闲高福利模式（高爆率 · 活跃社群）</div>
          <div style="font-size:11.5px;color:var(--muted);margin-top:2px">签到 800-2000 + 连签 100，利率 3%，造反率 20%，祈福爆发 15%，赌博成功率 60%。低惩罚快节奏，极大激发互动。</div>
        </div>
      </label>
      <label style="display:flex;align-items:flex-start;gap:10px;padding:12px;background:var(--panel2);border:${activeMode === "hardcore" ? "2px solid var(--acc)" : "1px solid var(--line)"};border-radius:12px;cursor:pointer">
        <input type="radio" name="balanceMode" value="hardcore" ${activeMode === "hardcore" ? "checked" : ""} style="margin-top:3px">
        <div>
          <div style="font-weight:600;color:var(--text);font-size:13px">🔴 硬核博弈模式（高对抗 · 惩罚严酷）</div>
          <div style="font-size:11.5px;color:var(--muted);margin-top:2px">签到 150-400 + 连签 20，利率 1%，造反率 45%，祈福爆发 2%。高风险高回报，适合重度对抗型群友。</div>
        </div>
      </label>
    </div>
  `;

  // 选项高亮切换
  const radios = content.querySelectorAll("input[name='balanceMode']");
  radios.forEach(r => {
    r.onchange = () => {
      radios.forEach(x => {
        x.closest("label").style.borderColor = x.checked ? "var(--acc)" : "var(--line)";
        x.closest("label").style.borderWidth = x.checked ? "2px" : "1px";
      });
    };
  });

  if (cancelBtn) {
    cancelBtn.style.display = "";
    cancelBtn.textContent = "取消";
    cancelBtn.onclick = () => { modal.className = ""; };
  }
  const _closeBtn = document.getElementById("appModalClose");
  if (_closeBtn) _closeBtn.onclick = () => { modal.className = ""; };
  modal.onclick = (e) => { if (e.target === modal) modal.className = ""; };
  if (okBtn) {
    okBtn.textContent = "⚡ 一键智能匹配生效";
    okBtn.disabled = false;
    okBtn.onclick = async () => {
      const sel = content.querySelector("input[name='balanceMode']:checked");
      const mode = sel ? sel.value : "standard";
      okBtn.disabled = true;
      okBtn.textContent = "正在调优并落盘...";
      try {
        const r = await getBridge().apiPost("config/auto_balance", { mode });
        if (r && r.ok) {
          const _summary = mode === "casual" ? "签到800-2000+连签100，利率3%，造反20%" : (mode === "hardcore" ? "签到150-400+连签20，利率1%，造反45%" : "签到300-800+连签50，利率2%，造反35%");
          toast(`已成功应用【${mode === "standard" ? "标准平衡" : (mode === "casual" ? "休闲福利" : "硬核博弈")}】数值方案！${_summary}`, "ok");
          modal.className = "";
          try { await refreshBalanceBadges(); } catch (e) {}
          await loadConfig();
          if (typeof loadCommands === "function") try { await loadCommands(); } catch(e) {}
        } else {
          toast("调优失败: " + (r && (r.error || r.msg) ? (r.error || r.msg) : "未知错误"), "bad");
        }
      } catch(err) {
        toast("调优失败: " + err.message, "bad");
      } finally {
        okBtn.disabled = false;
        okBtn.textContent = "⚡ 一键智能匹配生效";
      }
    };
  }
  modal.className = "show";
}

async function saveConfig() {
  const msg = document.getElementById("saveMsg");
  msg.className = "msg";
  try {
    const payload = {};
    const inputs = document.querySelectorAll("#cfgForm .cfg-row [data-key]");
    inputs.forEach((inp) => {
      const sec = inp.dataset.sec;
      const key = inp.dataset.key;
      if (!payload[sec]) payload[sec] = {};
      payload[sec][key] =
        inp.type === "checkbox" ? (inp.checked ? "真" : "假") : inp.value;
    });
    await getBridge().apiPost("config/save", payload);
    msg.textContent = "配置已保存";
    msg.classList.add("ok");
    toast("配置已保存", "ok");
    await loadConfig();
    // 同步刷新总览的快捷配置（同一接口，机器人QQ等）
    try { await loadOverviewReq(); } catch (e) {}
  } catch (e) {
    msg.textContent = "保存失败: " + e.message;
    msg.classList.add("bad");
    toast("保存失败: " + e.message, "bad");
  }
}

// ---------- 排行 ----------
async function resetConfig() {
  const msg = document.getElementById("saveMsg");
  msg.className = "msg";
  try {
    // 仅恢复本页实际展示的节（cfgForm 内已渲染行），不碰其他页（指令数值/商城/图鉴等）
    const visibleSecs = new Set();
    document.querySelectorAll("#cfgForm .cfg-row [data-key]").forEach((inp) => {
      if (inp.dataset.sec) visibleSecs.add(inp.dataset.sec);
    });
    if (!visibleSecs.size) { toast("当前页无可恢复配置", "bad"); return; }
    const secList = [...visibleSecs].sort();
    if (!(await uiConfirm(`只恢复本页 ${secList.length} 节（${secList.join("、")}）为默认值？\n\n其他页（指令数值/商城/图鉴等）不受影响。`, "恢复本页默认"))) return;
    const { defaults } = CFG.schema;
    const payload = {};
    // defaults: {"系统__键": default}
    Object.keys(defaults).forEach((k) => {
      const [sec, key] = k.split("__");
      if (!sec || !key || !visibleSecs.has(sec)) return;
      if (!payload[sec]) payload[sec] = {};
      payload[sec][key] = defaults[k];
    });
    await getBridge().apiPost("config/save", payload);
    msg.textContent = "已恢复本页默认（" + secList.join("、") + "）";
    msg.classList.add("ok");
    toast("已恢复本页默认值", "ok");
    await loadConfig();
  } catch (e) {
    msg.textContent = "恢复失败: " + e.message;
    msg.classList.add("bad");
    toast("恢复失败: " + e.message, "bad");
  }
}

// ---------- 全部设置恢复默认（必要配置页专属，不动用户数据） ----------
async function resetAllConfig() {
  const msg = document.getElementById("saveMsg");
  // 白名单排除：备份与密钥、用户定制数据不动（只动数值/开关类设置节）
  const EXCLUDE = new Set(["备份配置", "商城图鉴", "精灵图鉴", "自定义指令配置", "群组开关配置"]);
  try {
    if (!CFG || !CFG.schema || !CFG.schema.defaults) { toast("配置尚未加载，请稍后重试", "bad"); return; }
    const { defaults } = CFG.schema;
    const payload = {};
    const secs = new Set();
    Object.keys(defaults).forEach((k) => {
      const i = k.indexOf("__");
      if (i < 0) return;
      const sec = k.slice(0, i), key = k.slice(i + 2);
      if (!sec || !key || EXCLUDE.has(sec)) return;
      if (!payload[sec]) payload[sec] = {};
      payload[sec][key] = defaults[k];
      secs.add(sec);
    });
    if (!secs.size) { toast("无可恢复配置", "bad"); return; }
    const secList = [...secs].sort();
    if (!(await uiConfirm(
      `将 ${secList.length} 节设置恢复为默认值，将覆盖当前设置（${secList.join("、")}）？\n\n` +
      `不动：备份配置（含WebDAV地址/账号/自动备份开关/间隔/保留数）、商城图鉴、精灵图鉴、自定义指令、群组开关；\n` +
      `不动用户数据（钱包/账户/群档案等）；旧数据不保留，保存前已自动快照，可到备份页恢复。`,
      "全部设置恢复默认"))) return;
    await getBridge().apiPost("config/save", payload);
    if (msg) { msg.textContent = "已恢复全部设置默认（备份与用户定制除外）"; msg.className = "msg ok"; }
    toast("已恢复全部设置默认值", "ok");
    await loadConfig();
    try { await loadCommands(); } catch (e) {}
  } catch (e) {
    if (msg) { msg.textContent = "恢复失败: " + e.message; msg.className = "msg bad"; }
    toast("恢复失败: " + e.message, "bad");
  }
}

async function loadRank(type) {
  try {
    const rows = await getBridge().apiGet("rank", { type });
    const body = document.getElementById("rankBody");
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--muted)">暂无榜单数据</td></tr>`;
      return;
    }
    const rankBadges = ["🥇", "🥈", "🥉"];
    body.innerHTML = rows
      .map((r, i) => {
        const rankIdx = i < 3 ? `<span style="font-size:16px">${rankBadges[i]}</span>` : `<span class="badge" style="background:var(--panel2)">${i + 1}</span>`;
        const valFormatted = typeof r.value === "number" ? r.value.toLocaleString() : esc(r.value);
        return `<tr>
          <td style="text-align:center">${rankIdx}</td>
          <td><strong>${esc(r.name || r.qq)}</strong></td>
          <td><code>${esc(r.qq)}</code></td>
          <td><span style="font-weight:700;color:var(--acc)">${valFormatted}</span></td>
        </tr>`;
      })
      .join("");
  } catch (e) {
    err("rank: " + e.message);
  }
}

// ---------- 用户 / 财富 ----------
let RAW_USERS = [];
let USER_GID_FILTER = "";
let _USER_GIDS = new Set();

function populateUserGidOptions() {
  const sel = document.getElementById("userGidFilter");
  if (!sel) return;
  // 每次按当前数据重建（不清会残留已无用户的旧群号）
  _USER_GIDS = new Set();
  (RAW_USERS || []).forEach(u => { if (u.gid) _USER_GIDS.add(String(u.gid)); });
  const cur = sel.value;
  // 重建选项：保留“全部群” + 已知 gid 排序
  const gids = Array.from(_USER_GIDS).sort();
  sel.innerHTML = `<option value="">全部群</option>` + gids.map(g => `<option value="${esc(g)}">${esc(g)}</option>`).join("");
  // 恢复之前的选中
  if (cur && _USER_GIDS.has(cur)) sel.value = cur;
  else if (USER_GID_FILTER) sel.value = USER_GID_FILTER;
}

async function loadUsers() {
  try {
    const sel = document.getElementById("userGidFilter");
    const gid = (sel?.value || USER_GID_FILTER || "").trim();
    USER_GID_FILTER = gid;
    const params = gid ? { gid } : {};
    RAW_USERS = await getBridge().apiGet("users", params);
    populateUserGidOptions();
    renderUserTable();
  } catch (e) {
    err("users: " + e.message);
  }
}

function filterUsers() {
  renderUserTable();
}

function renderUserTable() {
  const body = document.getElementById("userBody");
  if (!body) return;
  let users = [...RAW_USERS];
  // 前端二次 gid 过滤（兼容后端未过滤或缓存数据）
  const gidFilter = (document.getElementById("userGidFilter")?.value || USER_GID_FILTER || "").trim();
  if (gidFilter) {
    users = users.filter(u => String(u.gid) === String(gidFilter));
  }
  // 搜索关键字联动过滤 (QQ/昵称/群号)
  const kw = (document.getElementById("userSearch")?.value || "").trim().toLowerCase();
  if (kw) {
    users = users.filter(u =>
      String(u.qq || "").toLowerCase().includes(kw) ||
      String(u.name || "").toLowerCase().includes(kw) ||
      String(u.gid || "").toLowerCase().includes(kw)
    );
  }
  const sortMode = (document.getElementById("userSort")?.value || "money_desc");
  if (sortMode === "money_desc") users.sort((a, b) => (b.money || 0) - (a.money || 0));
  else if (sortMode === "money_asc") users.sort((a, b) => (a.money || 0) - (b.money || 0));
  else if (sortMode === "deposit_desc") users.sort((a, b) => (b.deposit || 0) - (a.deposit || 0));
  else if (sortMode === "deposit_asc") users.sort((a, b) => (a.deposit || 0) - (b.deposit || 0));
  else if (sortMode === "stamina_desc") users.sort((a, b) => (b.stamina || 0) - (a.stamina || 0));
  else if (sortMode === "stamina_asc") users.sort((a, b) => (a.stamina || 0) - (b.stamina || 0));
  else if (sortMode === "charm_desc") users.sort((a, b) => (b.charm || 0) - (a.charm || 0));
  else if (sortMode === "charm_asc") users.sort((a, b) => (a.charm || 0) - (b.charm || 0));
  else if (sortMode === "sign_desc") users.sort((a, b) => (b.sign || 0) - (a.sign || 0));
  else if (sortMode === "sign_asc") users.sort((a, b) => (a.sign || 0) - (b.sign || 0));
  else if (sortMode === "qq_asc") users.sort((a, b) => String(a.qq).localeCompare(String(b.qq)));
  else if (sortMode === "qq_desc") users.sort((a, b) => String(b.qq).localeCompare(String(a.qq)));
  else if (sortMode === "gid_asc") users.sort((a, b) => String(a.gid || "").localeCompare(String(b.gid || "")));
  else if (sortMode === "gid_desc") users.sort((a, b) => String(b.gid || "").localeCompare(String(a.gid || "")));

  const hint = document.getElementById("userHint");
  if (hint) {
    hint.innerHTML = `共 <strong>${RAW_USERS.length}</strong> 名用户（当前匹配 <strong>${users.length}</strong> 名） · 直接改动数值后点右侧「保存」生效 · 点击表头可快捷排序`;
  }
  if (!users.length) {
    body.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:24px;color:var(--muted)">暂无匹配的用户数据</td></tr>`;
    return;
  }
  body.innerHTML = users
    .map((u) => {
      const nm = u.name ? esc(u.name) : '<span style="color:var(--muted)">-</span>';
      const inp = (id, v, w = 64) =>
        `<input type="number" id="${id}_${u.qq}_${u.gid}" value="${v}" title="${v}" style="width:${w}px;font-size:12.5px;padding:5px 8px;font-variant-numeric:tabular-nums">`;
      return `<tr>
        <td><strong>${esc(u.qq)}</strong></td>
        <td>${nm}</td>
        <td><span class="badge badge-primary">${esc(u.gid)}</span></td>
        <td>${inp("mm", u.money, 125)}</td>
        <td>${inp("tt", u.stamina, 58)}</td>
        <td>${inp("ma", u.charm, 58)}</td>
        <td>${inp("jj", u.lottery_tickets, 58)}</td>
        <td>${inp("ck", u.deposit || 0, 135)}</td>
        <td><span class="badge badge-success">${u.sign || 0}次</span></td>
        <td style="white-space:nowrap"><button data-save="user" data-qq="${esc(u.qq)}" data-gid="${esc(u.gid)}" class="sm">保存</button> <button class="ghost sm" data-export="user" data-qq="${esc(u.qq)}" data-gid="${esc(u.gid)}">导出</button> <button class="ghost sm del" data-clear="user" data-qq="${esc(u.qq)}" data-gid="${esc(u.gid)}" title="彻底清除该用户全部数据（含奴隶、精灵与礼包资格）">清除</button></td>
      </tr>`;
    })
    .join("");
  // 单用户导出/清除/保存统一走 #userBody 事件委托（见下方绑定），此处不再逐行直绑，
  // 避免搜索过滤/排序重渲染后绑定丢失与重复绑定导致“按钮无效/点两次”。
}

let _CLEARING_USERS = new Set();
async function clearUserSingle(qq, gid) {
  qq = String(qq || "").trim();
  gid = String(gid || "").trim();
  if (!qq || !gid) return;
  const ckey = gid + ":" + qq;
  if (_CLEARING_USERS.has(ckey)) return;
  // iframe 沙箱下原生 confirm 会被拦截导致按钮“无效”，统一用自研 uiConfirm（规则六二次确认）
  const ok = await uiConfirm(
    `确定要彻底清除用户【${qq}】（群: ${gid}）的所有数据吗？\n\n` +
    `将一并清除以下内容：\n` +
    `1. 钱包货币、银行存款、体力、魅力、奖券与签到记录\n` +
    `2. 奴隶系统：解除奴隶身份，且其名下持有的奴隶将全部释放自由\n` +
    `3. 精灵系统：拥有的所有精灵、出战骑乘状态与背包道具全部清除\n` +
    `4. 重置新手礼包与精灵领养状态（该用户可重新领取新手礼包）\n\n` +
    `此操作立即生效且不可逆，是否确定清除？`,
    "危险操作确认"
  );
  if (!ok) return;

  _CLEARING_USERS.add(ckey);
  try {
    toast("正在清理用户数据...", "info");
    let res = null;
    try {
      res = await getBridge().apiPost("user/clear", { gid, qq });
    } catch (e) {
      // Bridge POST 异常时回退 GET（后端 user/clear 同时支持 GET/POST）
      try { res = await getBridge().apiGet("user/clear", { gid, qq }); } catch (e2) { throw e; }
    }
    if (res && (res.ok || res.saved || res.cleared)) {
      toast(res.msg || `用户 ${qq} 数据已彻底清除`, "ok");
      await loadUsers();
      if (typeof loadSlaveUsers === "function") try { await loadSlaveUsers(); } catch(e) {}
      if (typeof loadSpiritUsers === "function") try { await loadSpiritUsers(); } catch(e) {}
    } else {
      toast((res && (res.msg || res.error)) || "清除失败", "bad");
    }
  } catch (e) {
    toast("清除失败: " + e.message, "bad");
  } finally {
    _CLEARING_USERS.delete(ckey);
  }
}

async function clearUserManual() {
  const curGid = (document.getElementById("userGidFilter")?.value || (typeof USER_GID_FILTER !== "undefined" ? USER_GID_FILTER : "") || "").trim();
  // iframe 下原生 prompt 会被拦截，统一用 uiPrompt
  const qq = await uiPrompt("请输入要彻底清除数据的用户 QQ 号：", "", "清除单用户");
  if (qq === null || qq === undefined) return;
  if (!String(qq).trim() || !/^\d{5,12}$/.test(String(qq).trim())) { if (String(qq).trim()) toast("QQ 号格式不正确", "bad"); return; }
  const targetQq = String(qq).trim();
  let targetGid = curGid;
  if (!targetGid) {
    const gInput = await uiPrompt(`请输入用户【${targetQq}】所在的群号：`, "", "清除单用户");
    if (gInput === null || gInput === undefined) return;
    if (!String(gInput).trim()) {
      toast("已取消操作：必须提供群号", "bad");
      return;
    }
    targetGid = String(gInput).trim();
  }
  await clearUserSingle(targetQq, targetGid);
}

async function saveUserEdit(qq, gid, btn) {
  const get = (p) => { const el = document.getElementById(p + "_" + qq + "_" + gid); return el ? el.value : ""; };
  const payload = { qq, gid, money: get("mm"), stamina: get("tt"), charm: get("ma"), lottery_tickets: get("jj"), deposit: get("ck") };
  try {
    const r = await getBridge().apiPost("user/edit", payload);
    toast("用户数据已保存", "ok");
    if (btn) { btn.textContent = "已存"; setTimeout(() => { btn.textContent = "保存"; }, 1500); }
    await loadUsers();
    return r;
  } catch (e) {
    err("保存失败: " + e.message);
  }
}


async function cleanLeftUsers() {
  const gid = (document.getElementById("userGidFilter")?.value || USER_GID_FILTER || "").trim();
  const scopeText = gid ? `群 ${gid}` : "全库所有群聊";
  const ok = await uiConfirm(
    `⚠️ 确认清理【${scopeText}】的退群人员？

系统将自动对比群聊实时成员列表，彻底删除已退群人员的钱包货币、奴隶身价关系、精灵背包与全部档案数据！`,
    "清理退群人员"
  );
  if (!ok) return;
  toast("正在对比群成员并清理退群人员...", "ok");
  try {
    // 清理退群：调 users/clean_left（曾误调 users/export，res.ok 恒真致“清理0人”假成功）
    const res = await callApi("users/clean_left", {}, "GET");
    if (res && res.ok) {
      toast(`清理完成！已清理 ${res.cleaned_count || 0} 名退群人员数据`, "ok");
      await loadUsers();
      if (typeof loadSlaveUsers === "function") try { await loadSlaveUsers(); } catch(e) {}
      if (typeof loadSpiritUsers === "function") try { await loadSpiritUsers(); } catch(e) {}
    } else {
      toast("清理失败: " + (res && (res.error || res.msg) ? (res.error || res.msg) : "无法获取实时群成员，请确保 Bot 正常在线且在群内"), "bad");
    }
  } catch (err) {
    toast("清理失败: " + err.message, "bad");
  }
}

async function exportAllUsers() {
  const filename = `xbbot_users_all_${Date.now()}.json`;
  toast("正在导出全量用户数据...", "ok");
  try {
    // 单次 callApi（GET空结果不再回退POST，失败兜底在callApi内）
    const res = await callApi("users/export", {}, "GET");
    if (!res) throw new Error("接口无响应");
    if (res.error || res.msg) throw new Error(res.error || res.msg);

    let usersList = null;
    let base64Data = res.data || "";

    if (Array.isArray(res.users)) {
      usersList = res.users;
    } else if (res.data && typeof res.data === "object" && Array.isArray(res.data.users)) {
      usersList = res.data.users;
    } else if (res.result && typeof res.result === "object" && Array.isArray(res.result.users)) {
      usersList = res.result.users;
    }

    if (usersList) {
      const payload = {
        count: usersList.length,
        users: usersList,
        export_at: res.export_at || Math.floor(Date.now() / 1000),
        version: res.version || "2026w0911h"
      };
      const jsonStr = JSON.stringify(payload, null, 2);
      triggerExportResult({
        filename: res.filename || filename,
        mime: "application/json;charset=utf-8",
        rawText: jsonStr,
        base64Data: base64Data
      });
      toast(`已成功全量导出 ${usersList.length} 名用户数据`, "ok");
      return;
    }

    if (base64Data && typeof base64Data === "string") {
      triggerExportResult({
        filename: res.filename || filename,
        mime: "application/json;charset=utf-8",
        base64Data: base64Data
      });
      toast("已成功全量导出用户数据", "ok");
      return;
    }

    const fallbackStr = typeof res === "string" ? res : JSON.stringify(res, null, 2);
    triggerExportResult({
      filename: filename,
      mime: "application/json;charset=utf-8",
      rawText: fallbackStr
    });
    toast("已成功全量导出用户数据", "ok");
  } catch (err) {
    toast("导出失败: " + err.message, "bad");
  }
}
async function importAllUsers() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json,application/json";
  inp.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const txt = await file.text();
      const data = JSON.parse(txt);
      // 兼容单用户与全量
      const payload = data.users ? data : { users: [data] };
      const r = await getBridge().apiPost("users/import", payload);
      toast(`已导入 ${r.imported}/${r.total}`, "ok");
      await loadUsers();
    } catch (err) { toast("导入失败: " + err.message, "bad"); }
  };
  inp.click();
}
async function importSingleUser() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json,application/json";
  inp.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const txt = await file.text();
      const data = JSON.parse(txt);
      const r = await getBridge().apiPost("user/import", data);
      toast("已导入单用户", "ok");
      await loadUsers();
    } catch (err) { toast("导入失败: " + err.message, "bad"); }
  };
  inp.click();
}

// ---------- 指令(可编辑 唤醒词 / 回复内容 / 玩法数值) ----------
let CMD_CFG = {};           // 运行时配置(嵌套 dict) 供指令页读取/保存
let KNOWN_CMDS = new Set(); // 引擎指令白名单，供映射校验
let CMD_ENG = {};           // 指令->所属引擎键，供数值映射与权限显示
// 引擎->数值节：指令编辑器按所属系统自动列出全部可调数值（奖励/惩罚/概率/价格/间隔）
const ENG_NUM_SECTIONS = {
  slave: ["设置", "费用配置", "间隔配置", "概率配置", "祈福配置"],
  sign: ["签到配置", "抽奖配置", "新手配置", "点赞配置"],
  bank: ["银行配置"], ent: ["娱乐配置"], spirit: ["精灵配置"],
  ride: ["坐骑配置"], guild: ["帮派配置"], adventure: ["冒险配置"],
  superadmin: ["超管配置"],
};
const SYS_WAKE = {
  slave: "奴隶系统", sign: "签到系统", bank: "银行系统", ent: "娱乐系统",
  spirit: "精灵系统", ride: "坐骑系统",
  superadmin: "超管系统", guild: "帮派系统", adventure: "冒险系统",
};
const map2sys = SYS_WAKE;
// 玩法类指令 -> 关联配置格式(金额/奖励/概率/惩罚) [section, key, label, type]
const CMD_NUMS = {
  "签到": [["签到配置", "金钱下限", "现金下限", "int"], ["签到配置", "金钱上限", "现金上限", "int"],
    ["签到配置", "体力下限", "体力下限", "int"], ["签到配置", "体力上限", "体力上限", "int"],
    ["签到配置", "魅力下限", "魅力下限", "int"], ["签到配置", "魅力上限", "魅力上限", "int"],
    ["签到配置", "奖券下限", "奖券下限", "int"], ["签到配置", "奖券上限", "奖券上限", "int"]],
  "领取新手礼包": [["新手配置", "现金", "礼包现金", "int"], ["新手配置", "体力", "礼包体力", "int"],
    ["新手配置", "魅力", "礼包魅力", "int"], ["新手配置", "奖券", "礼包奖券", "int"]],
  "购买体力": [["签到配置", "体力价格", "体力价格", "int"]],
  "购买魅力": [["签到配置", "魅力价格", "魅力价格", "int"]],
  "抽奖": [["抽奖配置", "中奖率", "中奖率%", "int"], ["抽奖配置", "现金奖", "现金奖", "int"],
    ["抽奖配置", "体力奖", "体力奖", "int"], ["抽奖配置", "魅力奖", "魅力奖", "int"]],
  "存款": [["银行配置", "存款利率", "存款利率%", "int"], ["银行配置", "利息上限", "利息上限", "int"],
    ["银行配置", "存款期限", "存款期限(天)", "int"], ["银行配置", "存取款消耗体力", "消耗体力", "int"]],
  "取款": [["银行配置", "存款利率", "存款利率%", "int"], ["银行配置", "利息上限", "利息上限", "int"]],
  "强制取款": [["银行配置", "存款利率", "存款利率%", "int"], ["银行配置", "利息上限", "利息上限", "int"]],
  "转账": [["银行配置", "转账最小金额", "最小金额", "int"], ["银行配置", "转账接收额度", "接收额度", "int"],
    ["银行配置", "转账消耗体力", "消耗体力", "int"]],
  "发红包": [["银行配置", "红包_最小金额", "最小金额", "int"], ["银行配置", "红包_最大金额", "最大金额", "int"],
    ["银行配置", "红包_发体力", "发体力", "int"], ["银行配置", "红包_间隔时间", "间隔(秒)", "int"]],
  "抢红包": [["银行配置", "红包_抢体力", "抢体力", "int"], ["银行配置", "红包_抢魅力", "抢魅力", "int"],
    ["银行配置", "红包_基本魅力", "基础魅力", "int"]],
  "赌博": [["银行配置", "赌博成功概率", "成功概率%", "int"], ["银行配置", "赌博消耗体力", "消耗体力", "int"],
    ["银行配置", "赌博魅力减少", "魅力减少", "int"], ["银行配置", "赌博最大金额", "最大金额", "int"],
    ["银行配置", "赌博限定次数", "限定次数", "int"], ["银行配置", "赌博关押时间", "关押(分)", "int"]],
  "打劫": [["银行配置", "打劫成功概率", "成功概率%", "int"], ["银行配置", "打劫消耗体力", "消耗体力", "int"],
    ["银行配置", "打劫金钱下限", "金钱下限", "int"], ["银行配置", "打劫金钱上限", "金钱上限", "int"],
    ["银行配置", "打劫魅力减少", "魅力减少", "int"], ["银行配置", "打劫关押时间", "关押(分)", "int"]],
  "打劫银行": [["银行配置", "打劫银行成功概率", "成功概率%", "int"],
    ["银行配置", "打劫银行消耗体力", "消耗体力", "int"],
    ["银行配置", "打劫银行金钱下限", "金钱下限", "int"], ["银行配置", "打劫银行金钱上限", "金钱上限", "int"],
    ["银行配置", "打劫银行魅力减少", "魅力减少", "int"], ["银行配置", "打劫银行关押时间", "关押(分)", "int"]],
  "保释": [["银行配置", "保释金钱下限", "保释金下限", "int"], ["银行配置", "保释金钱上限", "保释金上限", "int"],
    ["银行配置", "保释消耗体力", "消耗体力", "int"], ["银行配置", "保释魅力减少", "魅力减少", "int"]],
  "我要越狱": [["银行配置", "越狱成功概率", "成功概率%", "int"], ["银行配置", "越狱消耗体力", "消耗体力", "int"],
    ["银行配置", "越狱魅力减少", "魅力减少", "int"], ["银行配置", "越狱关押时间", "关押(分)", "int"]],
  "精灵冒险": [["精灵配置", "挑战奖励_经验下限", "经验下限", "int"], ["精灵配置", "挑战奖励_经验上限", "经验上限", "int"],
    ["精灵配置", "挑战奖励_金钱下限", "金钱下限", "int"], ["精灵配置", "挑战奖励_金钱上限", "金钱上限", "int"],
    ["精灵配置", "等级加成下限", "等级加成下限", "int"], ["精灵配置", "等级加成上限", "等级加成上限", "int"],
    ["精灵配置", "冒险间隔", "冒险间隔(分)", "int"]],
  "丢弃精灵": [["精灵配置", "魅力减少", "魅力减少", "int"]],
  "保护": [["设置", "保护费用", "保护费用", "int"], ["设置", "保护时长小时", "保护时长(时)", "int"],
    ["间隔配置", "保护间隔", "保护间隔(分)", "int"]],
  "我要学习": [["设置", "奇遇触发概率", "奇遇概率%", "int"], ["间隔配置", "学习间隔", "学习间隔(分)", "int"]],
  "讨好": [["概率配置", "讨好概率", "讨好概率%", "int"], ["间隔配置", "讨好间隔", "讨好间隔(分)", "int"]],
  "造反": [["概率配置", "造反概率", "造反概率%", "int"], ["间隔配置", "造反间隔", "造反间隔(分)", "int"]],
  "十连抽": [["设置", "十连抽花费", "十连抽花费", "int"]],
  "三十连抽": [["设置", "三十连抽花费", "三十连抽花费", "int"]],
  "五十连抽": [["设置", "五十连抽花费", "五十连抽花费", "int"]],
  "买下": [["间隔配置", "购买间隔", "购买间隔(分)", "int"]],
  "折磨": [["间隔配置", "折磨间隔", "折磨间隔(分)", "int"]],
  "买奴隶位": [["设置", "奴隶位价格", "奴隶位价格", "int"]],
  "我要自由": [["费用配置", "初始身价", "初始身价", "int"]],
  "打架": [["间隔配置", "打架间隔", "打架间隔(分)", "int"]],
  "我要祈福": [["祈福配置", "祈福奖励下限", "奖励下限", "int"], ["祈福配置", "祈福奖励上限", "奖励上限", "int"],
    ["祈福配置", "人品爆发概率", "人品爆发概率%", "int"], ["祈福配置", "人品爆发奖励", "人品爆发奖励", "int"]],
  "升星": [["设置", "一星武器概率", "一星概率%", "int"], ["设置", "一星武器花费", "一星花费", "int"], ["设置", "一星武器消耗同武器数量", "一星消耗同武数", "int"], ["设置", "二星武器概率", "二星概率%", "int"], ["设置", "二星武器花费", "二星花费", "int"], ["设置", "二星武器消耗同武器数量", "二星消耗", "int"]],
  "升阶": [["设置", "一阶宝物概率", "一阶概率%", "int"], ["设置", "一阶宝物花费", "一阶花费", "int"]],
  "我要打工": [["间隔配置", "打工间隔", "打工间隔(分)", "int"], ["费用配置", "工资比例", "工资比例%", "int"]],
  "奴隶打工": [["间隔配置", "打工间隔", "打工间隔(分)", "int"], ["费用配置", "工资比例", "工资比例%", "int"]],
  "打工": [["间隔配置", "打工间隔", "打工间隔(分)", "int"]],
  "学习": [["间隔配置", "学习间隔", "学习间隔(分)", "int"], ["设置", "奇遇触发概率", "奇遇概率%", "int"]],
  "祈福": [["祈福配置", "祈福奖励下限", "奖励下限", "int"], ["祈福配置", "祈福奖励上限", "奖励上限", "int"]],
  "释放": [["间隔配置", "释放间隔", "释放间隔(分)", "int"]],
  "抽签": [["娱乐配置", "抽签造价", "抽签造价", "int"], ["娱乐配置", "抽签大吉奖励", "大吉奖励", "int"], ["娱乐配置", "抽签上签奖励", "上签奖励", "int"], ["娱乐配置", "抽签中签奖励", "中签奖励", "int"]],
  "猜拳": [["娱乐配置", "猜拳奖励金币", "奖励金币", "int"], ["娱乐配置", "猜拳奖励魅力", "奖励魅力", "int"], ["娱乐配置", "猜拳成功概率", "成功概率%", "int"], ["娱乐配置", "猜拳消耗体力", "消耗体力", "int"], ["娱乐配置", "猜拳需要金钱", "需要金钱", "int"]],
  "猜数": [["娱乐配置", "猜数奖励金币", "奖励金币", "int"], ["娱乐配置", "猜数奖励魅力", "奖励魅力", "int"], ["娱乐配置", "猜数消耗体力", "消耗体力", "int"], ["娱乐配置", "猜数需要金钱", "需要金钱", "int"]],
  "急转弯": [["娱乐配置", "急转弯奖励金币", "奖励金币", "int"], ["娱乐配置", "急转弯奖励魅力", "奖励魅力", "int"], ["娱乐配置", "急转弯消耗体力", "消耗体力", "int"], ["娱乐配置", "急转弯需要金钱", "需要金钱", "int"]],
  "猜字谜": [["娱乐配置", "猜字谜奖励金币", "奖励金币", "int"], ["娱乐配置", "猜字谜奖励魅力", "奖励魅力", "int"], ["娱乐配置", "猜字谜消耗体力", "消耗体力", "int"], ["娱乐配置", "猜字谜需要金钱", "需要金钱", "int"]],
  "接龙": [["娱乐配置", "接龙奖励金币", "奖励金币", "int"], ["娱乐配置", "接龙奖励魅力", "奖励魅力", "int"], ["娱乐配置", "接龙消耗体力", "消耗体力", "int"], ["娱乐配置", "接龙需要金钱", "需要金钱", "int"]],
  "答题": [["娱乐配置", "答题奖励金币", "奖励金币", "int"], ["娱乐配置", "答题奖励魅力", "奖励魅力", "int"], ["娱乐配置", "答题消耗体力", "消耗体力", "int"], ["娱乐配置", "答题需要金钱", "需要金钱", "int"]],
  "二四点": [["娱乐配置", "二四点奖励金币", "奖励金币", "int"], ["娱乐配置", "二四点奖励魅力", "奖励魅力", "int"], ["娱乐配置", "二四点消耗体力", "消耗体力", "int"], ["娱乐配置", "二四点需要金钱", "需要金钱", "int"]],
};

// 各玩法指令的默认回复示例(供指令页"默认回复"展示; 覆盖配置留空则用该默认)
// {变量} 为运行时动态数值占位符
const CMD_DEFAULT_REPLY = {
  "签到": "🏅 恭喜你签到成功！\r\n　奖励详情：\r\n　　　💵 货币 +{现金}\r\n　　　⚡ 体力 +{体力}\r\n　　　💄 魅力 +{魅力}\r\n　　　🎫 奖券 +{奖券}\r\n　　　🔥 第{天数}天连签 +{连签}\r\n当前货币：{当前}\r\n您是今天第{序号}个签到者！",
  "领取新手礼包": "恭喜您获得新手礼包一份！\r\n现金+{现金}\r\n体力+{体力}\r\n魅力+{魅力}\r\n奖券+{奖券}",
  "购买体力": "恭喜您花费{价格}货币，购买了{数量}点体力，您的体力提升到{当前}点！",
  "购买魅力": "恭喜您花费{价格}货币，购买了{数量}点魅力，您的魅力提升到{当前}点！",
  "个人信息": "您的账户信息如下：\r\n个人财富：{财富}\r\n签到次数：{签到}\r\n剩余体力：{体力}\r\n魅力指数：{魅力}\r\n奖券数量：{奖券}\r\n存款金额：{存款}",
  "抽奖": "恭喜，抽奖成功！获得{奖励}+{数值}",
  "存款": "存款成功！共存入：{金额}，上期结息：{利息}，当前总存款：{总额}",
  "取款": "取款成功！获得利息：{利息}，本次取款：{金额}，还剩存款：{剩余}",
  "强制取款": "强制取款成功！因未到取款时间，本次没有利息。本次取款：{金额}",
  "转账": "转账成功！您已向 {目标} 转入{金额}货币！",
  "发红包": "发红包啦！发了{金额}货币点，大家快抢吧！红包口令为：{口令}",
  "抢红包": "恭喜！你抢到了 {金额}货币，魅力+{魅力}！",
  "赌博": "赌博成功！你获得了{赢得}货币，净赚{净赚}！",
  "打劫": "打劫成功！你从 {目标} 处劫走{金额}货币！",
  "打劫银行": "打劫银行成功！获得{金额}货币！",
  "保释": "保释成功！花费{保释金}货币、{体力}体力，魅力-{魅力}。",
  "我要越狱": "越狱成功！扣除{体力}体力，你重获自由~",
  "买下": "成功买下{目标}\r\n本次买入花费：{花费}\r\n奴隶身价上涨：{上涨}\r\n奴隶现在身价：{身价}",
  "买奴隶位": "恭喜您花费{价格}货币\r\n买下一个奴隶位。\r\n当前可拥有奴隶上限：{上限}",
  "我要自由": "万恶的主人，大发善心，花费{价格}换取自由！",
  "保护": "恭喜您花费{费用}货币保护{目标}，剩余保护时间{分钟}分钟！",
  "折磨": "你对 [{目标}] 实施了折磨...\r\n【奇遇】{剧情}\r\n奴隶货币 +{数值}",
  "讨好": "摇摇尾巴~向你主人卖个萌，主人一开心给了你{金额}",
  "造反": "经过艰苦卓绝的战斗，你打败了万恶的主人，并恢复自由！抢走主人{金额}货币",
  "我要学习": "缴纳学费 {学费} 后开始学习! 武器经验 +{经验}\r\n🍀奇遇: {剧情}",
  "我要祈福": "笑~忍神大人心情不错，看着面前楚楚可怜的{名字}，一高兴赏了{金额}",
  "打架": "打架啦！\r\n我方派出奴隶：{队伍}\r\n对方派出奴隶：{队伍}\r\n本次战斗结果：胜利！获得对方赔款：{金额}",
  "精灵冒险": "【精灵冒险】来到{地图}，遭遇了野生的 Lv.{等级}「{精灵}」！",
  "丢弃精灵": "已丢弃精灵「{名字}」，魅力-{数值}",
  "升星": "成功升星{武器}！本次升星概率：{概率}%，武器不会消失哦~",
  "升阶": "升阶成功！本次升阶概率：{概率}%，本次升阶花费：{花费}",
};

let CMD_EDIT = { sys: "", cmd: "", isNew: false, mapCmd: "" };   // 当前模态框编辑的 系统/指令
let _CMD_CUST = {};          // 当次渲染的自定义指令节（供委托点击读取）
let _CMD_LIST_BOUND = false; // #cmdList 事件委托只绑一次，渲染不再逐行绑定

function _bindCmdListOnce() {
  const el = document.getElementById("cmdList");
  if (!el || _CMD_LIST_BOUND) return;
  _CMD_LIST_BOUND = true;
  el.addEventListener("click", (e) => {
    const addBtn = e.target.closest("#btnCmdAddCustom");
    if (addBtn && el.contains(addBtn)) {
      CMD_EDIT = { sys: "自定义", cmd: "", isNew: true, mapCmd: "" };
      openCmdEditor();
      return;
    }
    const a = e.target.closest("a.cmd-tag");
    if (!a || !el.contains(a)) return;
    CMD_EDIT.sys = a.dataset.sys;
    CMD_EDIT.cmd = a.dataset.cmd;
    CMD_EDIT.isNew = false;
    if (a.dataset.sys === "自定义") {
      const ce = (_CMD_CUST[a.dataset.cmd] || {});
      CMD_EDIT.mapCmd = (typeof ce === "object" && ce) ? (ce.command || "") : "";
    } else {
      CMD_EDIT.mapCmd = a.dataset.cmd;
    }
    openCmdEditor();
  });
  // toggle 不冒泡，用捕获在容器层统一接
  el.addEventListener("toggle", (e) => {
    const d = e.target;
    if (d && d.matches && d.matches("details.cmd-block") && d.open) {
      d.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, true);
  // 系统启用开关：列表上直接拨动即时保存生效（此前只在编辑器保存时顺带提交）
  el.addEventListener("change", (e) => {
    const inp = e.target && e.target.closest ? e.target.closest("input[data-syson]") : null;
    if (!inp || !el.contains(inp)) return;
    sysonImmediateSave(inp);
  });
  const exp = document.getElementById("btnCmdExpandAll");
  if (exp) exp.addEventListener("click", () => {
    document.querySelectorAll("#cmdList details.cmd-block").forEach((d) => { d.open = true; });
  });
  const col = document.getElementById("btnCmdCollapseAll");
  if (col) col.addEventListener("click", () => {
    document.querySelectorAll("#cmdList details.cmd-block").forEach((d) => { d.open = false; });
  });
}

async function loadCommands() {
  try {
    // 双接口并行（此前串行 2 RTT）
    const [cmds, cur] = await Promise.all([
      getBridge().apiGet("commands"),
      getBridge().apiGet("config/get")
    ]);
    CMD_CFG = cur || {};
    const wakeSec = CMD_CFG["唤醒词配置"] || {};
    const custSec = CMD_CFG["自定义指令配置"] || {};
    const onSec = CMD_CFG["系统开关配置"] || {};       // 系统级启用
    const disSec = CMD_CFG["指令启用配置"] || {};       // 指令级启用(假=禁用)
    const permSec = CMD_CFG["指令权限配置"] || {};       // 指令级权限(超管=仅超管)
    const setupSec = CMD_CFG["设置"] || {};
    const isOff = (v) => v === "假" || v === "0" || v === "false";
    const isOn = (v) => v === undefined || !isOff(v);
    const el = document.getElementById("cmdList");
    if (!el) return;
    // 重渲染前记住展开态，渲染后恢复（保存后不再全部收起）
    let _openSys = null;
    try {
      _openSys = new Set([...el.querySelectorAll("details.cmd-block[open]")].map((d) => d.dataset.sys));
    } catch (e) { _openSys = new Set(); }
    KNOWN_CMDS = new Set();
    CMD_ENG = {};
    Object.entries(cmds).forEach(([eng, arr]) => (arr || []).forEach((c) => {
      KNOWN_CMDS.add(c);
      if (!(c in CMD_ENG)) CMD_ENG[c] = eng;
    }));
    const blockHtml = Object.keys(cmds).filter(k => k !== "chat")
      .map((k) => {
        const sys = map2sys[k] || k;
        const wake = (wakeSec[sys] ?? sys);
        const wakeList = wake.split(/[|，,]/).map((s) => s.trim()).filter(Boolean);
        const seen = {};
        // 去掉「系统唤醒词」本身作为假指令的重复项(唤醒词已在块头部单独编辑)
        const items = (cmds[k] || []).filter((c) => {
          if (seen[c]) return false;
          seen[c] = 1;
          return wakeList.indexOf(c) < 0;
        });
        const sysChecked = isOn(onSec[sys]) ? "checked" : "";
        const tags = items.map((c) => {
          const cOn = isOn(disSec[c]);
          const onBg = cOn ? "" : "off";
          const isAdm = (((permSec[c] || "").trim()) === "超管");
          return `<a class="cmd-tag ${onBg}" data-on="${cOn ? "1" : "0"}" data-cmd="${esc(c)}" data-sys="${esc(sys)}">` +
            `${cOn ? '<span style="color:var(--ok);font-size:10px">●</span>' : '<span style="color:var(--muted);font-size:10px">○</span>'} ${isAdm ? "🔒" : ""}${esc(c)}</a>`;
        }).join("");
        return `<details class="cmd-block" data-sys="${esc(sys)}"><summary>` +
          `<span class="cmd-sys">${esc(sys)}</span>` +
          `<span class="cmd-count">${items.length} 条指令</span></summary>` +
          `<div class="cmd-wake">` +
          `<div class="cmd-wake-item"><label>启用系统</label><label class="switch"><input type="checkbox" data-syson="${esc(sys)}" ${sysChecked}><span class="slider-toggle"></span></label></div>` +
          `<div class="cmd-wake-item" style="flex:1"><label>唤醒词</label><input data-wake="${esc(sys)}" value="${esc(wake)}" placeholder="可用 | 分隔多个"></div>` +
          `</div>` +
          `<div class="cmd-tags">${tags || '<span class="hint">（交互式/无前缀触发）</span>'}</div>` +
          `</details>`;
      })
      .join("");
    const customTags = Object.keys(custSec).map((t) => {
      const cOn = isOn(disSec[t]);
      return `<a class="cmd-tag custom ${cOn ? "" : "off"}" data-on="${cOn ? "1" : "0"}" data-cmd="${esc(t)}" data-sys="自定义">` +
        `${cOn ? '<span style="color:var(--ok);font-size:10px">●</span>' : '<span style="color:var(--muted);font-size:10px">○</span>'} ${esc(t)}</a>`;
    }).join("");
    el.innerHTML =
      blockHtml +
      `<details class="cmd-block" data-sys="自定义"><summary>` +
        `<span class="cmd-sys">自定义指令</span>` +
        `<span class="cmd-count">${Object.keys(custSec).length} 条</span></summary>` +
        `<div class="cmd-tags">${customTags || '<span class="hint">暂无。新建：纯自定义（触发词→回复）或绑定已有引擎指令作别名。</span>'}</div>` +
        `<div class="toolbar" style="margin-top:8px"><button id="btnCmdAddCustom" class="ghost sm">＋ 添加自定义指令</button></div>` +
      `</details>`;
    _CMD_CUST = custSec || {};
    if (_openSys && _openSys.size) {
      el.querySelectorAll("details.cmd-block").forEach((d) => {
        if (_openSys.has(d.dataset.sys)) d.open = true;
      });
    }
    _bindCmdListOnce();
    try { refreshBalanceBadges(); } catch (e) {}
  } catch (e) {
    err("commands: " + e.message);
  }
}
function cmdAliasesFor(cmd) {
  const cust = CMD_CFG["自定义指令配置"] || {};
  return Object.keys(cust).filter((t) => cust[t] && cust[t].command === cmd && t !== cmd);
}

function openCmdEditor() {
  const { sys, cmd, isNew, mapCmd } = CMD_EDIT;
  const m = document.getElementById("cmdModal");
  if (!m) return;
  const curCmd = mapCmd || cmd;
  const ovSec = CMD_CFG["指令回复配置"] || {};
  const disSec = CMD_CFG["指令启用配置"] || {};
  const isOff = (v) => v === "假" || v === "0" || v === "false";
  // 启用键: 自定义指令(含别名)按触发词, 引擎指令按映射引擎指令名
  const effKey = (sys === "自定义") ? (cmd || "") : (mapCmd || cmd || "");
  const onBox = document.getElementById("cmdModalOn");
  if (onBox) onBox.checked = !isOff(disSec[effKey]);
  // 超管权限勾选：指令权限配置=超管（默认所有人）
  const admBox = document.getElementById("cmdModalAdmin");
  if (admBox) admBox.checked = (((CMD_CFG["指令权限配置"] || {})[effKey] || "").trim() === "超管");
  // 删除按钮: 仅编辑已有自定义指令时显示
  const delBtn = document.getElementById("cmdModalDel");
  if (delBtn) delBtn.style.display = (sys === "自定义" && !isNew) ? "" : "none";
  document.getElementById("cmdModalTitle").textContent = isNew ? "添加自定义指令" : ("编辑指令 · " + curCmd);
  (document.getElementById("cmdModalSysBadge") || document.getElementById("cmdModalSys") || {}).textContent = isNew ? "自定义指令" : sys;
  // 触发词: 可编辑(| 分隔多个); 内置指令默认=指令名(+已有别名)
  const nameInp = document.getElementById("cmdModalName");
  nameInp.value = isNew ? "" : [curCmd, ...cmdAliasesFor(curCmd)].join("|");
  nameInp.readOnly = false;
  document.getElementById("cmdModalCmd").value = mapCmd;
  document.getElementById("cmdModalCmd").readOnly = isNew ? false : true;
  document.getElementById("cmdModalReply").value = isNew ? "" : (ovSec[curCmd] ?? "");
  const note = document.getElementById("cmdModalCmdNote");
  if (note) {
    note.textContent = (!isNew && mapCmd === curCmd)
      ? "内置指令：触发词即指令名（可改/加，| 分隔多个）；映射引擎指令=本身。"
      : "留空=纯自定义指令；填入已有引擎指令则这些触发词作为它的别名。";
  }
  const dfltCmd = mapCmd || curCmd || "";
  const dfltTxt = CMD_DEFAULT_REPLY[dfltCmd] || (ovSec[dfltCmd] || "") || "";
  document.getElementById("cmdModalDflt").textContent = isNew
    ? "纯自定义指令：回复内容即返回文案，可直接写你想要的任意内容；也可在「映射引擎指令」填入已有指令来作为它的别名（此时回复覆盖模板对该引擎生效）。"
    : (dfltTxt
        ? "引擎默认回复（参考）：\r\n" + dfltTxt + "\r\n（{变量}=动态数值；留空回复=按引擎原样回复）"
        : "引擎默认回复为运行时动态生成（含变量/随机/状态判定），此处未收录示例；\r\n如需覆盖请直接填写回复模板，或用 {回复} 引用引擎原回复。留空=不覆盖。");
  renderCmdNums(mapCmd ? mapCmd : (isNew ? "" : curCmd), isNew);
  if (m) m.classList.add("show");
}

// 按目标引擎指令渲染玩法数值(纯自定义且未映射时提示)
function renderCmdNums(numCmd, isNew) {
  const holder = document.getElementById("cmdModalNums");
  if (!holder) return;
  if (!numCmd) {
    holder.innerHTML = `<small class="hint">纯自定义指令：回复内容即返回文案，无玩法数值；如需调整某引擎指令的数值，请把「映射引擎指令」填成它。</small>`;
    return;
  }
  let nums = CMD_NUMS[numCmd] || [];
  if (!nums.length && numCmd) {
    // 通用兜底：按指令名与键名/说明的关键词（二字重叠）精准匹配本系统数值，保证对得上、无关的不出现
    try {
      const _cjk = (s) => (String(s || "").match(/[\u4e00-\u9fff]/g) || []);
      const _bigrams = (s) => {
        const cs = _cjk(s), out = {};
        for (let i = 0; i + 1 < cs.length; i++) out[cs[i] + cs[i + 1]] = 1;
        return out;
      };
      const _cb = _bigrams(numCmd);
      const eng = (typeof CMD_ENG !== "undefined" && CMD_ENG[numCmd]) || "";
      const secs = ENG_NUM_SECTIONS[eng] || [];
      const scored = [];
      const seen = {};
      secs.forEach((sec) => {
        const grp = (CFG.schema && CFG.schema.groups && CFG.schema.groups[sec]) || [];
        grp.forEach((it) => {
          if (it.type !== "int" && it.type !== "float") return;
          const k = sec + "__" + it.key;
          if (seen[k]) return;
          seen[k] = 1;
          const _kb = _bigrams(it.key + (it.desc || ""));
          let hit = 0;
          Object.keys(_cb).forEach((b) => { if (_kb[b]) hit++; });
          if (hit > 0) scored.push([hit, sec, it]);
        });
      });
      scored.sort((a, b) => b[0] - a[0]);
      nums = scored.slice(0, 6).map(([s, sec, it]) => [sec, it.key, it.key, it.type]);
    } catch(e){}
  }
  if (!nums.length) {
    holder.innerHTML = `<small class="hint">该指令无关联可调数值。</small>`;
    return;
  }
  holder.innerHTML = nums.map(([sec, key, label]) => {
    const v = (CMD_CFG[sec] || {})[key] ?? "";
    return `<label class="cnum"><span>${esc(label)}</span>` +
      `<input type="number" data-cmd-num data-nsec="${esc(sec)}" data-nkey="${esc(key)}" value="${esc(v)}"></label>`;
  }).join("");
}

function closeCmdEditor() {
  const m = document.getElementById("cmdModal");
  if (m) m.classList.remove("show");
}

// 系统启用开关即时保存：收齐所有块头部状态一次 POST，失败回拨
async function sysonImmediateSave(inp) {
  inp.disabled = true;
  try {
    const onSec = {};
    document.querySelectorAll("#cmdList [data-syson]").forEach((x) => {
      onSec[x.dataset.syson] = x.checked ? "真" : "假";
    });
    const r = await getBridge().apiPost("config/save", { "系统开关配置": onSec });
    if (r && r.ok === false) throw new Error(r.msg || r.error || "保存失败");
    const sys = inp.dataset.syson;
    toast(`系统${sys}已${inp.checked ? "启用" : "关闭"}（即时生效）`, inp.checked ? "ok" : "bad");
    await loadCommands();
  } catch (err) {
    toast("系统开关保存失败: " + err.message, "bad");
    inp.checked = !inp.checked;
  } finally {
    inp.disabled = false;
  }
}

async function saveCmdEditor() {
  const name = document.getElementById("cmdModalName").value.trim();
  const mapCmd = document.getElementById("cmdModalCmd").value.trim();
  const reply = document.getElementById("cmdModalReply").value.trim();
  const msg = document.getElementById("cmdModalMsg");
  if (msg) msg.className = "msg";
  try {
    const payload = {};
    // 系统启用开关: 收所有块头部
    const onSec = {};
    document.querySelectorAll("#cmdList [data-syson]").forEach((inp) => {
      onSec[inp.dataset.syson] = inp.checked ? "真" : "假";
    });
    if (Object.keys(onSec).length) payload["系统开关配置"] = onSec;
    // 系统唤醒词: 收所有块头部
    const wakeSec = {};
    document.querySelectorAll("#cmdList [data-wake]").forEach((inp) => {
      wakeSec[inp.dataset.wake] = inp.value.trim();
    });
    if (Object.keys(wakeSec).length) payload["唤醒词配置"] = wakeSec;

    const cust = {};
    if (mapCmd) {
      if (!KNOWN_CMDS.has(mapCmd)) {
        if (msg) { msg.textContent = `映射的引擎指令「${mapCmd}」不存在，请留空走纯自定义或填已有指令`; msg.classList.add("bad"); }
        toast(`引擎指令「${mapCmd}」不存在，已拦截`, "bad");
        return;
      }
      // 映射 / 编辑已有引擎指令(含别名): 触发词=| 分隔, 全部当作该指令的触发词
      const trigs = name.split(/[|，,]/).map((s) => s.trim()).filter(Boolean);
      if (!trigs.length) { if (msg) { msg.textContent = "请填写触发词"; msg.classList.add("bad"); } return; }
      { const ov = {}; ov[mapCmd] = reply; payload["指令回复配置"] = ov; }
      const oldCust = (CMD_CFG["自定义指令配置"] || {});
      Object.keys(oldCust).forEach((t) => {
        const e = oldCust[t];
        if (!(e && e.command === mapCmd && t !== mapCmd)) cust[t] = e;
      });
      trigs.forEach((t) => {
        if (t && t !== mapCmd) cust[t] = { command: mapCmd, reply: "" };
      });
    } else {
      // 纯自定义指令
      if (!name) { if (msg) { msg.textContent = "请填写触发词"; msg.classList.add("bad"); } return; }
      if (!reply) { if (msg) { msg.textContent = "纯自定义指令需填写回复内容"; msg.classList.add("bad"); } return; }
      const oldCust = (CMD_CFG["自定义指令配置"] || {});
      Object.keys(oldCust).forEach((t) => { if (t !== name) cust[t] = oldCust[t]; });
      cust[name] = { command: "", reply: reply };
    }
    if (Object.keys(cust).length) payload["自定义指令配置"] = cust;

    // 指令级启用: 自定义指令按触发词记录, 引擎指令按映射引擎指令名记录
    const isCustom = (CMD_EDIT.sys === "自定义") || (name && !mapCmd && CMD_EDIT.isNew);
    const effKey = isCustom ? name : (mapCmd || name);
    const disSec = {};
    const onBox = document.getElementById("cmdModalOn");
    disSec[effKey] = (onBox && onBox.checked) ? "真" : "假";
    payload["指令启用配置"] = disSec;

    // 超管权限：勾选=超管（非超管静默），不勾选=所有人
    const admBox = document.getElementById("cmdModalAdmin");
    const permSec = {};
    permSec[effKey] = (admBox && admBox.checked) ? "超管" : "所有人";
    payload["指令权限配置"] = permSec;

    // 玩法数值(目标引擎指令)
    document.querySelectorAll("#cmdModal [data-cmd-num]").forEach((inp) => {
      const sec = inp.dataset.nsec, key = inp.dataset.nkey;
      if (!payload[sec]) payload[sec] = {};
      payload[sec][key] = inp.value === "" ? "" : Number(inp.value);
    });

    const r = await getBridge().apiPost("config/save", payload);
    if (msg) { msg.textContent = "指令已保存"; msg.classList.add("ok"); }
    toast("指令已保存", "ok");
    closeCmdEditor();
    await loadCommands();
  } catch (e) {
    if (msg) { msg.textContent = "保存失败: " + e.message; msg.classList.add("bad"); }
    toast("保存失败: " + e.message, "bad");
  }
}

// 删除自定义指令(移除 自定义指令配置 / 指令启用配置 / 指令回复配置 中对应项)
async function deleteCmdEditor() {
  const msg = document.getElementById("cmdModalMsg");
  if (msg) msg.className = "msg";
  try {
    const key = (CMD_EDIT && CMD_EDIT.cmd) || "";
    if (!key) { if (msg) { msg.textContent = "无触发词，无法删除"; msg.classList.add("bad"); } return; }
    const oldCust = (CMD_CFG["自定义指令配置"] || {});
    if (!(key in oldCust)) { if (msg) { msg.textContent = "该指令在配置中不存在，可能已删除"; msg.classList.add("bad"); } return; }
    if (!(await uiConfirm("确认删除自定义指令「" + key + "」？", "删除自定义指令"))) return;
    const cust = {};
    Object.keys(oldCust).forEach((t) => { if (t !== key) cust[t] = oldCust[t]; });
    const payload = { "自定义指令配置": cust };
    const disSec = {};
    const disSecOld = (CMD_CFG["指令启用配置"] || {});
    Object.keys(disSecOld).forEach((k) => { if (k !== key) disSec[k] = disSecOld[k]; });
    if (Object.keys(disSec).length) payload["指令启用配置"] = disSec;
    const ovOld = (CMD_CFG["指令回复配置"] || {});
    const ov = {};
    Object.keys(ovOld).forEach((k) => { if (k !== key) ov[k] = ovOld[k]; });
    payload["指令回复配置"] = ov;
    await getBridge().apiPost("config/save", payload);
    toast("已删除自定义指令", "ok");
    closeCmdEditor();
    await loadCommands();
  } catch (e) {
    if (msg) { msg.textContent = "删除失败: " + e.message; msg.classList.add("bad"); }
    toast("删除失败: " + e.message, "bad");
  }
}

// ---------- 精灵图鉴(地图/商城 两页; 地图内可展开精灵详情 + 搜索地图/精灵) ----------
let SPIRIT = null;          // {spirits, maps, shop}
let SPIRIT_CUR = "地图";    // 仅 "地图" | "商城"
let SPIRIT_DIRTY = false;
let SPIRIT_OPEN = {};       // mapName -> bool(展开详情)
let SPIRIT_CUSTOM = { maps: true, spirits: true, shop: true };  // false=展示内置默认未自定义

const SPIRIT_FIELDS = [
  ["type", "属性"], ["hp", "生命"], ["atk", "攻击"], ["def", "防御"],
  ["spa", "特攻"], ["spd", "特防"], ["spe", "速度"], ["lv", "进化等级"],
  ["evolve", "进化成"], ["img", "形象图"],
];
const SHOP_FIELDS = [["price", "价格"], ["attr", "类型"], ["effect", "效果"]];
const SHOP_ATTR_OPTS = ["精灵球", "等级", "HP", "攻击", "防御", "特攻", "特防", "进化"];
const SHOP_ATTR_HELP = { "精灵球": "收服率%", "等级": "奇异甜食+Lv数", "HP": "吐司类+生命", "攻击": "+攻击", "防御": "+防御", "特攻": "+特攻", "特防": "+特防", "进化": "进化液=1" };

let SPIRIT_TS = 0; // 最近成功加载时间戳：Tab 打开 5s 内复用，免重复 GET（loadShops 已顺带拉过时）
async function loadSpirits(force) {
  // 先占位（桥慢时不再空白卡死），两次渲染并一次（refreshSpiritViews 内已含 renderShop）
  try {
    const _ab = document.getElementById("atlasBox");
    if (_ab) _ab.innerHTML = `<div style="text-align:center;padding:24px;color:var(--muted)">图鉴加载中…</div>`;
    const _sb = document.getElementById("shopSpiritBox");
    if (_sb) _sb.innerHTML = `<div style="text-align:center;padding:16px;color:var(--muted)">商城加载中…</div>`;
  } catch (e) {}
  // instant 骨架：先同步画出宝物默认总览（零等待），精灵数据后台拉取后重绘；占位永不裸奔
  try { if (typeof renderAtlas === "function") renderAtlas(); } catch (e) {}
  try {
    // 5s 内复用（loadShops 刚拉过时免重复 GET）；导入后强制刷新，防读到旧内存
    let res = null;
    const _fresh = !force && (typeof SPIRIT !== "undefined" && SPIRIT && typeof SPIRIT === "object"
      && typeof SPIRIT_TS === "number" && SPIRIT_TS && (Date.now() - SPIRIT_TS < 5000));
    if (_fresh) res = SPIRIT;
    else res = await apiTimeout(getBridge().apiGet("spirits"), 20000, "spirits");
    SPIRIT = res || {};
    try { SPIRIT_TS = Date.now(); } catch (e) {}
    // 编辑区：有自定义用自定义；无则预填内置为起点并标记未自定义（保存后即转自定义）。
    // 用后端 _meta.configured 判定显式清空（_raw 恒含三键，不可用 in 判断）。
    // 兼容旧后端（无 _raw/_meta）：顶层即有效数据，直接沿用。
    try {
      const _hasMeta = res && res._raw && res._meta && res._meta.configured;
      if (_hasMeta) {
        const _raw = res._raw || {};
        const _bi = res._builtin || {};
        const _cf = res._meta.configured || {};
        SPIRIT_CUSTOM = { maps: true, spirits: true, shop: true };
        ["maps", "spirits", "shop"].forEach((k) => {
          const _r = (_raw && _raw[k]) || {};
          if (_r && Object.keys(_r).length) { SPIRIT[k] = _r; SPIRIT_CUSTOM[k] = true; }
          else if (_cf[k]) { SPIRIT[k] = {}; SPIRIT_CUSTOM[k] = true; }
          else {
            const _b = (_bi && _bi[k]) || {};
            if (_b && Object.keys(_b).length) {
              SPIRIT[k] = JSON.parse(JSON.stringify(_b));
              SPIRIT_CUSTOM[k] = false;
            } else { SPIRIT[k] = {}; SPIRIT_CUSTOM[k] = true; }
          }
        });
      } else {
        SPIRIT.maps = (res && res.maps) || {};
        SPIRIT.spirits = (res && res.spirits) || {};
        SPIRIT.shop = (res && res.shop) || {};
        SPIRIT_CUSTOM = { maps: true, spirits: true, shop: true };
      }
    } catch (e) {}
    SPIRIT_DIRTY = false;
    SPIRIT_OPEN = {};
    const msg = document.getElementById("spiritMsg");
    if (msg) { msg.className = "msg"; msg.textContent = ""; }
    refreshSpiritViews();
  } catch (e) {
    err("spirits: " + e.message);
    // 失败兜底：有缓存才试渲染旧数据（无缓存不掩盖，直接报错重试，防渲染默认值掩盖失败）
    try { if (typeof SPIRIT !== "undefined" && SPIRIT && Object.keys(SPIRIT).length) refreshSpiritViews(); } catch (_e) {}
    try {
      const _ab = document.getElementById("atlasBox");
      // 无数据强制报错（instant 骨架只是默认值，不能掩盖拉取失败），有缓存则保留旧数据只 toast
      const _noData = (typeof SPIRIT === "undefined" || !SPIRIT || !Object.keys(SPIRIT).length);
      if (_ab && (_noData || /加载中/.test(_ab.innerHTML || "") || !_ab.innerHTML.trim())) _ab.innerHTML = `<div style="text-align:center;padding:24px;color:var(--bad)">图鉴加载失败: ${esc(e.message || e)}<br><button class="ghost sm" onclick="loadSpirits()">重试</button></div>`;
      const _sb = document.getElementById("shopSpiritBox");
      if (_sb && /加载中/.test(_sb.innerHTML || "")) _sb.innerHTML = `<div style="text-align:center;padding:16px;color:var(--bad)">商城加载失败，可<button class="ghost sm" onclick="loadSpirits()">重试</button></div>`;
    } catch (_e) {}
  }
}

function _spiritBuiltinCount(kind) {
  try {
    const b = (SPIRIT && SPIRIT._builtin && SPIRIT._builtin[kind]) || {};
    return Object.keys(b).length;
  } catch (e) { return 0; }
}

function _spiritLoadBuiltin(kind) {
  try {
    const b = (SPIRIT && SPIRIT._builtin && SPIRIT._builtin[kind]) || null;
    if (!b || !Object.keys(b).length) { toast("无内置数据可载入", "bad"); return false; }
    SPIRIT[kind] = JSON.parse(JSON.stringify(b));
    SPIRIT_DIRTY = true;
    return true;
  } catch (e) { toast("载入失败: " + e.message, "bad"); return false; }
}

function spiritAttrCards(spirits, dropNames, assignMaps) {
  // 每个 drop 精灵一张属性卡(数据从 spirits dict 读, 缺失则 seed)
  // 进化目标下拉共用一份 datalist（首卡附带，避免重复 id）
  // assignMaps 非空时每卡附带地图下拉 + 分配按钮（孤儿精灵上架用）
  let _dl = "";
  try {
    if (!window._spDlDone) {
      const _all = Object.keys(spirits || {});
      if (_all.length) {
        _dl = `<datalist id="spEvolveList">` + _all.map((n) => `<option value="${esc(n)}">`).join("") + `</datalist>`;
        window._spDlDone = true;
      }
    }
  } catch (e) {}
  const _assignOpts = (assignMaps && assignMaps.length)
    ? assignMaps.map((m) => `<option value="${esc(m)}">${esc(m)}</option>`).join("") : "";
  return dropNames.map((sn) => {
    const it = spirits[sn] || { type: "", hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0, lv: 0, evolve: "否" };
    const _img = String(it.img || "").trim();
    const cells = SPIRIT_FIELDS.map(([fk, label]) => {
      const _list = fk === "evolve" ? ` list="spEvolveList"` : "";
      return `<div class="s-row"><small>${label}</small>` +
        `<input data-sp-spirit="${esc(sn)}" data-s-field="${fk}" value="${esc(it[fk] ?? "")}"${_list} style="width:78px"></div>`;
    });
    return `<div class="sp-card" data-sp="${esc(sn)}">
      <div class="sp-name">✦ <input data-sp-rename value="${esc(sn)}" title="直接改名，回车/失焦生效" style="width:110px;background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:2px 6px;font-size:12px;font-weight:600"></div>
      <div class="s-fields">${cells.join("")}
        <button class="s-del" data-del-spirit="${esc(sn)}">移除精灵</button></div>
      <div style="display:flex;gap:4px;margin-top:4px;flex-wrap:wrap">${_img ? `<button class="ghost sm" data-sp-view="${esc(_img)}">浏览图片</button>` : ""}<button class="ghost sm" data-sp-pick-upload="${esc(sn)}">外置选图</button><button class="ghost sm" data-sp-pick-builtin="${esc(sn)}">内置选图</button></div>
        ${_assignOpts ? `<div style="display:flex;gap:4px;margin-top:4px;align-items:center"><select data-assign-map="${esc(sn)}" style="flex:1;padding:4px 6px;border-radius:6px">${_assignOpts}</select><button class="ghost sm" data-assign-spirit="${esc(sn)}">分配进图</button></div>` : ""}
      </div>`;
  }).join("") + _dl;
}

// ---------- 图鉴总览（atlasBox：宝物/精灵地图；f11 专属，商城只调不用，独立方便导出导入与自定义） ----------
let ATLAS_CUR = "treasure";  // 总览分类：treasure | spirit（武器坐骑只在商城管理）
async function renderAtlas(curCfg){
  const box = document.getElementById("atlasBox");
  if (!box) return;
  if (ATLAS_CUR !== "treasure" && ATLAS_CUR !== "spirit") ATLAS_CUR = "treasure";
  try {
    let Treas = [];
    try {
      // 待保存优先：宝物增删先落本地，点保存商城图鉴时一并持久化
      if (window._TREAS_DIRTY && Array.isArray(window._TREAS_LIST)) {
        Treas = window._TREAS_LIST.filter(Boolean);
      } else {
        const curSec = (curCfg && curCfg["设置"]) || (CFG && CFG.cur && CFG.cur["设置"]) || {};
        Treas = (curSec["宝物"] || "酒神葫芦|四象护符").toString().split("|").filter(Boolean);
        window._TREAS_LIST = [...Treas];
        window._TREAS_DIRTY = false;
      }
    } catch(e) { Treas = ["酒神葫芦", "四象护符"]; }
    const _spiritMaps = (() => { try { return Object.keys((SPIRIT && SPIRIT.maps) || {}); } catch (e) { return []; } })();
    const _tabs = [["treasure", "🎁 宝物", Treas.length], ["spirit", "✨ 精灵", _spiritMaps.length]];
    let html = `<div style="display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap">` + _tabs.map(([k, label, n]) =>
      `<button class="ghost sm" data-atlas-tab="${k}" ${ATLAS_CUR === k ? 'disabled style="opacity:.45"' : ""}>${label} (${n})</button>`
    ).join("") + `</div><div style="display:flex;flex-direction:column;gap:8px">`;
    const _effOf = (n) => { try { const e = (window._TREAS_EFF || {})[n]; if (e && typeof e === "object") return String(e.effect || ""); return String(e || ""); } catch (e) { return ""; } };
    if (ATLAS_CUR === "treasure") {
      let h = `<div style="border:1px solid var(--line);border-radius:var(--radius-xs);padding:8px 10px;background:var(--panel2)"><div style="font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:6px;flex-wrap:wrap">奴隶系统-宝物 (${Treas.length}) <span style="margin-left:auto;display:inline-flex;gap:4px;flex-wrap:wrap"><button class="ghost sm" id="btnAtlasSaveTreasure">💾 保存宝物</button><button class="ghost sm" id="btnAtlasResetTreasure">↩️ 恢复默认</button><button class="ghost sm" id="btnAtlasAddTreasure">＋ 添加</button></span></div><div style="display:flex;flex-wrap:wrap;gap:5px">`;
      if (!Treas.length) h += `<span style="color:var(--muted)">暂无</span>`;
      else h += Treas.map(n => { const e = _effOf(n); return `<span class="badge badge-primary" style="font-size:11.5px;display:inline-flex;align-items:center;gap:5px;padding:3px 8px" title="${esc(e || "无自定义效果")}">🎁 ${esc(n)}${e ? "·" + esc(e.slice(0, 12)) : ""}<span style="cursor:pointer" data-atlas-edit-treasure="${esc(n)}" title="修改效果">✎</span><span style="cursor:pointer;font-weight:bold" data-atlas-del="奴隶系统-宝物|${esc(n)}" title="删除">×</span></span>`; }).join("");
      h += `</div><div class="hint" style="margin-top:6px">✎ 可改宝物效果（不止名字），× 删除；改动即时保存</div></div>`;
      html += h;
    }
    else if (ATLAS_CUR === "spirit") {
      const _maps = (() => { try { return (SPIRIT && SPIRIT.maps) || {}; } catch (e) { return {}; } })();
      const _spirits = (() => { try { return (SPIRIT && SPIRIT.spirits) || {}; } catch (e) { return {}; } })();
      const _names = Object.keys(_maps);
      try { window._spDlDone = false; } catch (e) {}
      let _orphans = [];
      try {
        const _used = new Set();
        Object.values(_maps || {}).forEach((m) => ((m && m.drops) || []).map(String).forEach((s) => _used.add(s)));
        _orphans = Object.keys(_spirits || {}).filter((n) => !_used.has(String(n)));
      } catch (e) {}
      let h = `<div style="border:1px solid var(--line);border-radius:var(--radius-xs);padding:8px 10px;background:var(--panel2)">`
        + `<div style="font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:6px;flex-wrap:wrap">精灵系统-精灵地图 (${_names.length})`
        + `<span style="margin-left:auto;display:inline-flex;gap:4px;flex-wrap:wrap">`
        + `<button class="ghost sm" id="btnAtlasSaveMaps">💾 保存精灵</button>`
        + `<button class="ghost sm" id="btnAtlasResetMaps">↩️ 恢复默认</button>`
        + `<button class="ghost sm" id="btnAtlasClearMaps">🧹 清空地图</button>`
        + `</span></div>`;
      if (!_names.length) {
        const _bc = (() => { try { return Object.keys((SPIRIT && SPIRIT._builtin && SPIRIT._builtin.maps) || {}).length; } catch (e) { return 0; } })();
        h += `<span style="color:var(--muted)">当前无自定义地图，运行中使用内置 ${_bc} 张</span>`;
      } else {
        h += `<div id="atlasSpiritCards" style="display:flex;flex-direction:column;gap:8px">` + spiritMapCardsHTML(_names, _maps, _spirits, "") + `</div>`;
      }
      if (_orphans.length) {
        h += `<div class="s-mapcard ${SPIRIT_OPEN["__orphans__"] ? "open" : ""}" data-map="__orphans__" style="margin-top:10px"><div class="s-maphead" data-map-toggle="__orphans__"><span class="s-mapname">🧩 未上架精灵 (${_orphans.length})</span><span class="s-maplv">不在任何地图掉落中</span><span class="s-arr">${SPIRIT_OPEN["__orphans__"] ? "▾" : "▸"}</span></div>${SPIRIT_OPEN["__orphans__"] ? `<div class="s-mapbody"><div class="hint" style="margin-bottom:6px">这些精灵不会在野外遭遇，可编辑后分配进图，或直接移除</div><div class="sp-spirits">${spiritAttrCards(_spirits, _orphans, _names)}</div></div>` : ``}</div>`;
      }
      h += `<div style="margin-top:8px"><button class="ghost sm" id="btnAtlasAddMap">＋ 添加地图</button></div>`;
      h += `<div class="hint" style="margin-top:6px">地图+属性一键保存/恢复，只动精灵范围</div></div>`;
      html += h;
    }
    else html += `<div style="border:1px solid var(--line);border-radius:var(--radius-xs);padding:8px 10px;background:var(--panel2)"><div style="color:var(--muted)">未知分类</div></div>`;
    html += `</div><div class="hint" style="margin-top:6px">宝物改动即时保存，只动各自范围；精灵卡改动点保存精灵；武器坐骑请到🛒商城管理</div>`;
    box.innerHTML = html;
    box.querySelectorAll("[data-atlas-tab]").forEach((b) => b.addEventListener("click", () => {
      ATLAS_CUR = b.dataset.atlasTab;
      renderAtlas();
    }));
    const persistTreasure = async () => {
      // 宝物名+效果即时持久化（图鉴页内闭环，不碰商城）
      const cleanEff = {};
      Object.entries(window._TREAS_EFF || {}).forEach(([k, v]) => {
        const s = (v && typeof v === "object") ? String(v.effect || "") : String(v || "");
        if (s.trim()) cleanEff[k] = s.trim();
      });
      const r = await getBridge().apiPost("config/save", {
        "设置": { "宝物": (window._TREAS_LIST || Treas).filter(Boolean).join("|") },
        "商城图鉴": { "treasure_effects": JSON.stringify(cleanEff) }
      });
      if (r && r.error) throw new Error(r.error);
      window._TREAS_DIRTY = false;
      try { if (CFG && CFG.cur && CFG.cur["设置"]) CFG.cur["设置"]["宝物"] = (window._TREAS_LIST || Treas).filter(Boolean).join("|"); } catch (e) {}
    };
    box.querySelectorAll("[data-atlas-del]").forEach(el => el.addEventListener("click", async () => {
      const [sys, name] = el.dataset.atlasDel.split("|");
      if (!(await uiConfirm(`确认删除 ${sys} "${name}"？`, "删除图鉴"))) return;
      try {
        if (sys.includes("宝物")) {
          window._TREAS_LIST = (window._TREAS_LIST || Treas).filter(x => x !== name);
          try { if (window._TREAS_EFF) delete window._TREAS_EFF[name]; } catch (e) {}
          await persistTreasure();
          toast("已删除并保存", "ok");
          renderAtlas();
        }
      } catch (e) { toast("删除失败: " + e.message, "bad"); }
    }));
    try {
      // 委托绑在 atlasBox 上（一次，多次渲染不重复），覆盖地图卡与未上架区
      bindSpiritMapCards(box);
    } catch (e) {}
    box.querySelectorAll("[data-atlas-edit-treasure]").forEach(el => el.addEventListener("click", async () => {
      const n = el.dataset.atlasEditTreasure;
      const cur = (() => { try { const e = (window._TREAS_EFF || {})[n]; if (e && typeof e === "object") return String(e.effect || ""); return String(e || ""); } catch (e) { return ""; } })();
      const v = await uiPrompt(`宝物「${n}」效果（留空用内置/通用）：`, cur, "修改宝物效果");
      if (v === null || v === undefined) return;
      window._TREAS_EFF = window._TREAS_EFF || {};
      if (String(v).trim()) window._TREAS_EFF[n] = String(v).trim();
      else delete window._TREAS_EFF[n];
      try { await persistTreasure(); toast("已保存", "ok"); }
      catch (e) { toast("保存失败: " + e.message, "bad"); }
      renderAtlas();
    }));
    document.getElementById("btnAtlasSaveMaps")?.addEventListener("click", () => saveSpiritKind("all"));
    document.getElementById("btnAtlasResetMaps")?.addEventListener("click", () => resetSpiritKind("all"));
    document.getElementById("btnAtlasClearMaps")?.addEventListener("click", async () => {
      if (!SPIRIT) { toast("请先加载图鉴", "bad"); return; }
      if (!(await uiConfirm("直接清空全部精灵地图？精灵保留（进未上架区），旧地图不保留（快照可回滚）。", "清空地图"))) return;
      try {
        SPIRIT.maps = {};
        await saveSpiritKind("all");
        refreshSpiritViews();
      } catch (e) { toast("清空失败: " + e.message, "bad"); }
    });
    document.getElementById("btnAtlasAddMap")?.addEventListener("click", async () => {
      if (!SPIRIT) { toast("请先加载图鉴", "bad"); return; }
      const n = await uiPrompt("输入新地图名称：", "", "添加地图");
      if (!n || !n.trim()) return;
      const maps = SPIRIT.maps || (SPIRIT.maps = {});
      if (!maps[n.trim()]) maps[n.trim()] = { lv: 1, drops: [] };
      SPIRIT_OPEN[n.trim()] = true;
      SPIRIT_DIRTY = true;
      refreshSpiritViews();
      toast("已添加地图，点保存精灵持久化", "ok");
    });
    document.getElementById("btnAtlasSaveTreasure")?.addEventListener("click", async () => {
      try { await persistTreasure(); toast("宝物已保存", "ok"); }
      catch (e) { toast("保存失败: " + e.message, "bad"); }
      renderAtlas();
    });
    document.getElementById("btnAtlasResetTreasure")?.addEventListener("click", async () => {
      if (!(await uiConfirm("直接恢复宝物为内置（酒神葫芦|四象护符）并清空自定义效果？旧数据不保留。", "恢复默认"))) return;
      try {
        window._TREAS_LIST = ["酒神葫芦", "四象护符"];
        window._TREAS_EFF = {};
        await persistTreasure();
        toast("已恢复默认", "ok");
      } catch (e) { toast("恢复失败: " + e.message, "bad"); }
      renderAtlas();
    });
    document.getElementById("btnAtlasAddTreasure")?.addEventListener("click", async () => {
      let n = await uiPrompt("输入宝物名（奴隶系统-宝物）：", "", "添加宝物");
      if (!n) return; n = n.trim(); if (!n) return;
      const _tl = window._TREAS_DIRTY ? (window._TREAS_LIST || []) : Treas;
      if (_tl.includes(n)) { toast("已存在", "bad"); return; }
      window._TREAS_LIST = [..._tl, n];
      const eff = await uiPrompt(`宝物「${n}」效果（可选，留空用通用）：`, "", "宝物效果");
      if (eff && String(eff).trim()) { window._TREAS_EFF = window._TREAS_EFF || {}; window._TREAS_EFF[n] = String(eff).trim(); }
      try { await persistTreasure(); toast("已添加并保存", "ok"); }
      catch (e) { window._TREAS_DIRTY = true; toast("保存失败: " + e.message, "bad"); }
      renderAtlas();
    });
  } catch (e) { box.innerHTML = `<span style="color:var(--muted)">图鉴加载失败: ${esc(e.message)}</span>`; }
}

function refreshSpiritViews() {
  // 上方地图编辑区已并入总览 ✨ 精灵页签，此处只刷总览与道具商城
  try { if (typeof ATLAS_CUR !== "undefined" && ATLAS_CUR === "spirit") renderAtlas(); } catch (e) {}
  try { if (typeof renderShop === "function") renderShop(); } catch (e) {}
}

// 通用排序：对象按 key 整体上移/下移一位（保持其余顺序），返回是否变动
function _moveKey(obj, key, dir) {
  try {
    const ks = Object.keys(obj || {});
    const i = ks.indexOf(key);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= ks.length) return false;
    const t = ks[i]; ks[i] = ks[j]; ks[j] = t;
    const out = {};
    ks.forEach((k) => { out[k] = obj[k]; });
    Object.keys(obj).forEach((k) => { delete obj[k]; });
    Object.keys(out).forEach((k) => { obj[k] = out[k]; });
    return true;
  } catch (e) { return false; }
}

// 精灵改名：spirits 主键 + 全地图掉落引用 + 进化指向同步更名；返回 ""=成功，否则为错误文案
function _renameSpirit(oldName, newName) {
  if (!SPIRIT || !oldName) return "参数缺失";
  oldName = String(oldName); newName = String(newName == null ? "" : newName).trim();
  if (!newName) return "新名不能为空";
  if (newName === oldName) return "";
  const spirits = SPIRIT.spirits || {};
  if (!spirits[oldName]) return "原精灵不存在";
  if (spirits[newName]) return "已存在同名精灵";
  spirits[newName] = spirits[oldName];
  delete spirits[oldName];
  Object.values(SPIRIT.maps || {}).forEach((m) => {
    if (m && Array.isArray(m.drops)) m.drops = m.drops.map((x) => (String(x) === oldName ? newName : x));
  });
  Object.values(spirits).forEach((it) => {
    if (it && typeof it === "object" && String(it.evolve || "") === oldName) it.evolve = newName;
  });
  SPIRIT_DIRTY = true;
  return "";
}

// 地图卡片 HTML（图鉴主体与总览精灵页签共用，同一可编辑样式）
function spiritMapCardsHTML(mapNames, maps, spirits, q) {
  // 脏条目隔离：单地图数据坏只跳过本卡，不整页空白（曾整页卡死）
  return mapNames.map((mname) => {
    try {
      const raw = (maps && maps[mname]) || {};
      const d = (raw && typeof raw === "object" && !Array.isArray(raw)) ? raw : {};
      let drops = d.drops;
      if (typeof drops === "string") drops = drops.split(/[,，]/).map((s) => String(s || "").trim()).filter(Boolean);
      if (!Array.isArray(drops)) drops = [];
      drops = drops.map(String);
    const open = q ? true : !!SPIRIT_OPEN[mname];
    return `<div class="s-mapcard ${open ? "open" : ""}" data-map="${esc(mname)}">
      <div class="s-maphead" data-map-toggle="${esc(mname)}">
        <span class="s-mapname">🗺 ${esc(mname)}</span>
        <span class="s-maplv">Lv.${esc(d.lv ?? 1)}</span>
        <span class="s-mapdrop">${esc(drops.join("、"))}</span>
        <span style="display:inline-flex;gap:2px;margin-left:auto"><button class="ghost sm" data-map-up="${esc(mname)}" title="上移">↑</button><button class="ghost sm" data-map-down="${esc(mname)}" title="下移">↓</button></span>
        <span class="s-arr">${open ? "▾" : "▸"}</span>
      </div>
      <div class="s-mapbody">
        <div class="s-fields" style="margin-bottom:8px">
          <div class="s-row"><small>推荐等级</small><input data-map-field="lv" value="${esc(d.lv ?? 1)}"></div>
          <div class="s-row" style="flex:0 1 66%"><small>出没精灵(逗号分隔)</small><input data-map-field="drops" value="${esc(drops.join("，"))}"></div>
          <button class="s-del" data-del-map="${esc(mname)}">删地图</button>
        </div>
        <div class="sp-spirits">${spiritAttrCards(spirits, drops)}</div>
        <button class="ghost" data-add-spirit="${esc(mname)}">＋ 添加精灵</button>
      </div>
    </div>`;
    } catch (e) {
      return `<div class="s-mapcard" style="border-color:var(--bad)"><div class="s-maphead"><span class="s-mapname">⚠️ ${esc(mname)} 数据损坏已跳过</span></div></div>`;
    }
  }).join("");
}

// 地图卡片事件绑定（两处共用；输入即时写回 SPIRIT，结构操作刷新两处视图）
function bindSpiritMapCards(root) {
  // 事件委托：整块只绑 input+click 各一次，多次渲染不重复；覆盖地图卡与未上架区
  if (!root || !SPIRIT) return;
  if (root.dataset.mapBound) return;
  root.dataset.mapBound = "1";
  const _maps = () => ((SPIRIT && SPIRIT.maps) || {});
  const _spirits = () => ((SPIRIT && SPIRIT.spirits) || {});
  const _setSpiritImg = (sn, path) => {
    if (!sn || !path || !SPIRIT) return false;
    const spirits = _spirits();
    if (!spirits[sn]) spirits[sn] = {};
    spirits[sn].img = path;
    SPIRIT_DIRTY = true;
    try {
      const card = root.querySelector(`.sp-card[data-sp="${CSS.escape(sn)}"] input[data-s-field="img"]`);
      if (card) card.value = path;
    } catch (e) {}
    return true;
  };
  const _spUpload = (sn) => {
    if (!sn) return;
    const inp = document.createElement("input"); inp.type = "file"; inp.accept = "image/*";
    inp.onchange = async (e) => {
      const file = e.target.files[0]; if (!file) return;
      try {
        const r = await postFile("images/upload?dir=" + encodeURIComponent("data/img/spirits"), {}, file);
        if (r && r.error) throw new Error(r.error);
        const path = (r && (r.path || (r.data && r.data.path))) || ("data/img/spirits/" + file.name);
        _setSpiritImg(sn, path);
        refreshSpiritViews();
        toast("形象图已绑定，点保存精灵生效", "ok");
      } catch (err) { toast("上传失败:" + (err.message || err), "bad"); }
    };
    inp.click();
  };
  const _spBuiltin = async (sn) => {
    if (!sn) return;
    window.SHOP_PICK_TARGET = sn; window.SHOP_PICK_KIND = "spirit";
    toast("已进入精灵图片目录，请单击选中图片后点“确定绑定”", "ok");
    document.querySelectorAll(".tabs button").forEach(x => x.classList.remove("on"));
    const rb = document.querySelector("[data-tab=\"imgs\"]"); if (rb) rb.classList.add("on");
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("on"));
    const tab = document.getElementById("tab-imgs"); if (tab) tab.classList.add("on");
    await loadImages("data/img/spirits");
    const old = document.getElementById("shopPickTip"); if (old) old.remove();
    const tip = document.createElement("div"); tip.id = "shopPickTip"; tip.style = "background:var(--accSoft);border:1px solid var(--acc);padding:8px 12px;border-radius:8px;margin-bottom:10px";
    tip.innerHTML = `<b>为精灵 "${esc(sn)}" 选择内置形象图：</b> 精灵目录 data/img/spirits，可上下导航，然后 <button class="ghost sm" id="btnShopPickConfirm">确定绑定</button> <button class="ghost sm" id="btnShopPickCancel">取消</button>`;
    const panel = document.querySelector("#tab-imgs .panel"); if (panel) panel.prepend(tip);
    const backToSpirits = () => {
      tip.remove(); window.SHOP_PICK_TARGET = null; window.SHOP_PICK_KIND = null;
      document.querySelectorAll(".tabs button").forEach(x => x.classList.remove("on"));
      const cb = document.querySelector("[data-tab=\"spirits\"]"); if (cb) cb.classList.add("on");
      document.querySelectorAll(".tab").forEach(x => x.classList.remove("on"));
      const stab = document.getElementById("tab-spirits"); if (stab) stab.classList.add("on");
    };
    document.getElementById("btnShopPickConfirm")?.addEventListener("click", () => {
      const sel = IMG_SELECTED;
      if (!sel) { toast("请先选中图片文件", "bad"); return; }
      const ext = (sel.split(".").pop() || "").toLowerCase();
      if (!["png", "jpg", "jpeg", "gif", "webp", "bmp", "ico"].includes(ext)) { toast("请选择图片文件", "bad"); return; }
      if (window._imgIsDir && window._imgIsDir(sel)) { toast("不能选择文件夹", "bad"); return; }
      _setSpiritImg(sn, sel);
      backToSpirits();
      refreshSpiritViews();
      toast("形象图已绑定，点保存精灵生效", "ok");
    });
    document.getElementById("btnShopPickCancel")?.addEventListener("click", () => { backToSpirits(); });
  };
  root.addEventListener("input", (e) => {
    const inp = e.target;
    if (!inp || !inp.matches) return;
    try {
      if (inp.matches("input[data-map-field]")) {
        const card = inp.closest(".s-mapcard");
        const mname = card ? card.dataset.map : "";
        const maps = _maps();
        if (!mname || mname === "__orphans__" || !maps[mname]) return;
        const mo = maps[mname];
        if (inp.dataset.mapField === "lv") mo.lv = Number(inp.value) || 1;
        else if (inp.dataset.mapField === "drops") mo.drops = String(inp.value).split(/[,，]/).map((s) => s.trim()).filter(Boolean);
        SPIRIT_DIRTY = true;
      } else if (inp.matches("input[data-sp-spirit]")) {
        const card = inp.closest(".sp-card");
        const sn = card ? card.dataset.sp : "";
        if (!sn) return;
        const spirits = _spirits();
        if (!spirits[sn]) spirits[sn] = {};
        const o = spirits[sn];
        const fk = inp.dataset.sField;
        o[fk] = ["hp", "atk", "def", "spa", "spd", "spe", "lv"].includes(fk) ? (Number(inp.value) || 0) : inp.value;
        SPIRIT_DIRTY = true;
      }
    } catch (err) {}
  });
  // 精灵改名：行内直接改（坐骑同款），回车/失焦生效，空/重名自动回滚显示
  root.addEventListener("change", (e) => {
    const inp = e.target;
    if (!inp || !inp.matches || !inp.matches("input[data-sp-rename]")) return;
    try {
      const card = inp.closest(".sp-card");
      const old = card ? card.dataset.sp : "";
      const nn = inp.value;
      if (!old || String(nn).trim() === String(old)) { try { inp.value = old; } catch (err) {} return; }
      const rerr = _renameSpirit(old, nn);
      if (rerr) toast(rerr, "bad");
      else toast(`已改名「${old}」→「${String(nn).trim()}」，点保存精灵生效`, "ok");
      refreshSpiritViews();
    } catch (err) {}
  });
  root.addEventListener("click", async (e) => {
    const t = e.target && e.target.closest ? e.target : null;
    if (!t) return;
    const maps = _maps();
    const spirits = _spirits();
    // 地图卡头部 ↑↓（先于 toggle 拦截，否则点排序会误触展开/收起）
    const mvBtn = t.closest("[data-map-up],[data-map-down]");
    if (mvBtn && root.contains(mvBtn)) {
      const mk = mvBtn.hasAttribute("data-map-up") ? mvBtn.dataset.mapUp : mvBtn.dataset.mapDown;
      if (mk && _moveKey(maps, mk, mvBtn.hasAttribute("data-map-up") ? -1 : 1)) {
        SPIRIT_DIRTY = true;
        refreshSpiritViews();
        toast("已排序，点保存精灵生效", "ok");
      }
      return;
    }
    const tgl = t.closest("[data-map-toggle]");
    if (tgl && root.contains(tgl)) {
      const m = tgl.dataset.mapToggle;
      SPIRIT_OPEN[m] = !SPIRIT_OPEN[m];
      refreshSpiritViews();
      return;
    }
    const b = t.closest("button");
    if (!b || !root.contains(b)) return;
    if (b.hasAttribute("data-del-map")) {
      const k = b.dataset.delMap;
      const _last = Object.keys(maps).length <= 1;
      if (!(await uiConfirm("确认删除地图 \"" + k + "\"？（点保存精灵生效）" + (_last ? "\n\n注意：这是最后一张，删光后运行时自动使用内置地图。" : ""), "删除地图"))) return;
      delete maps[k];
      SPIRIT_DIRTY = true;
      refreshSpiritViews();
      toast("已删除地图，点保存精灵生效", "ok");
    } else if (b.hasAttribute("data-del-spirit")) {
      const spName = b.dataset.delSpirit;
      if (!(await uiConfirm("确认移除精灵 \"" + spName + "\"？（点保存精灵生效）", "移除精灵"))) return;
      Object.keys(maps).forEach((mk) => {
        maps[mk].drops = (maps[mk].drops || []).map(String).filter((x) => x !== spName);
      });
      try { if (spirits && spirits[spName]) delete spirits[spName]; } catch (err) {}
      SPIRIT_DIRTY = true;
      refreshSpiritViews();
      toast("已移除精灵，点保存精灵生效", "ok");
    } else if (b.hasAttribute("data-assign-spirit")) {
      const spName = b.dataset.assignSpirit;
      const card = b.closest(".sp-card");
      const sel = card ? card.querySelector("[data-assign-map]") : null;
      const mk = sel ? sel.value : "";
      if (!mk || !maps[mk]) { toast("请先选择目标地图", "bad"); return; }
      const dd = maps[mk];
      if (!Array.isArray(dd.drops)) dd.drops = [];
      if (!dd.drops.map(String).includes(spName)) dd.drops.push(spName);
      SPIRIT_OPEN[mk] = true;
      SPIRIT_DIRTY = true;
      refreshSpiritViews();
      toast(`已将「${spName}」分配进「${mk}」，点保存精灵生效`, "ok");
    } else if (b.hasAttribute("data-sp-view")) {
      const p = b.dataset.spView;
      if (!p) return;
      try {
        const r = await getBridge().apiPost("images/thumb", { path: p });
        const thumb = r && (r.thumb || (r.data && r.data.thumb));
        if (r && r.error) throw new Error(r.error);
        if (thumb) showLightbox(thumb, String(p).split("/").pop());
        else toast("无预览", "bad");
      } catch (err) { toast("预览失败:" + (err.message || err), "bad"); }
    } else if (b.hasAttribute("data-add-spirit")) {
      openSpiritAddModal(b.dataset.addSpirit);
    } else if (b.hasAttribute("data-sp-pick-upload")) {
      _spUpload(b.dataset.spPickUpload);
    } else if (b.hasAttribute("data-sp-pick-builtin")) {
      _spBuiltin(b.dataset.spPickBuiltin);
    }
  });
}
let _SP_ADD_FILE = null;
let _SP_ADD_SRC = "";
function openSpiritAddModal(defMap) {
  const modal = document.getElementById("appModal");
  if (!modal || !SPIRIT) { toast("请先加载图鉴", "bad"); return; }
  _SP_ADD_FILE = null; _SP_ADD_SRC = "";
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");
  if (icon) icon.textContent = "✨";
  if (title) title.textContent = "添加精灵" + (defMap && defMap !== "__orphans__" ? "→" + defMap : "");
  if (inputWrap) inputWrap.style.display = "none";
  content.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:10px">
      <div style="display:flex;gap:8px">
        <div style="flex:2"><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">精灵名：</label>
          <input id="spAddName" style="width:100%;padding:6px 10px;border-radius:8px" placeholder="如：雷精灵"></div>
        <div style="flex:1"><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">属性：</label>
          <input id="spAddType" style="width:100%;padding:6px 10px;border-radius:8px" placeholder="火/水/木…"></div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">
        ${["hp|生命|40", "atk|攻击|40", "def|防御|40", "spa|特攻|40", "spd|特防|40", "spe|速度|40", "lv|进化等级|50"].map((s) => { const [k, l, d] = s.split("|"); return `<div><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">${l}：</label><input id="spAdd_${k}" type="number" value="${d}" style="width:100%;padding:6px 10px;border-radius:8px"></div>`; }).join("")}
        <div><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">进化成：</label><input id="spAddEvolve" value="否" style="width:100%;padding:6px 10px;border-radius:8px"></div>
      </div>
      <div><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">形象图（精灵目录 data/img/spirits）：</label>
        <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
          <button class="ghost sm" id="spAddPickUpload">外置选图（本地上传）</button>
          <button class="ghost sm" id="spAddPickBuiltin">内置选图（精灵目录）</button>
          <button class="ghost sm" id="spAddPreview">浏览图片</button>
          <span id="spAddImgTip" style="font-size:11.5px;color:var(--muted)">未选择（可后补）</span>
        </div></div>
      <div class="hint">保存后进地图掉落，点保存精灵生效；图片可先空后在卡片绑定</div>
    </div>`;
  const setTip = (t) => { const el = document.getElementById("spAddImgTip"); if (el) el.textContent = t; };
  window._spAddImgPath = "";
  document.getElementById("spAddPickUpload")?.addEventListener("click", () => {
    const inp = document.createElement("input"); inp.type = "file"; inp.accept = "image/*";
    inp.onchange = (e) => {
      const file = e.target.files[0]; if (!file) return;
      _SP_ADD_FILE = file; _SP_ADD_SRC = ""; window._spAddImgPath = "";
      setTip("本地：" + file.name);
    };
    inp.click();
  });
  document.getElementById("spAddPickBuiltin")?.addEventListener("click", async () => {
    modal.className = "";
    window.SHOP_PICK_TARGET = "__spadd__"; window.SHOP_PICK_KIND = "spadd";
    toast("已进入精灵图片目录，请选中后点确定", "ok");
    document.querySelectorAll(".tabs button").forEach(x => x.classList.remove("on"));
    const rb = document.querySelector("[data-tab=\"imgs\"]"); if (rb) rb.classList.add("on");
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("on"));
    const tab = document.getElementById("tab-imgs"); if (tab) tab.classList.add("on");
    await loadImages("data/img/spirits");
    const old = document.getElementById("shopPickTip"); if (old) old.remove();
    const tip = document.createElement("div"); tip.id = "shopPickTip"; tip.style = "background:var(--accSoft);border:1px solid var(--acc);padding:8px 12px;border-radius:8px;margin-bottom:10px";
    tip.innerHTML = `<b>为新精灵选择形象图：</b> 精灵目录 data/img/spirits，然后 <button class="ghost sm" id="btnShopPickConfirm">确定绑定</button> <button class="ghost sm" id="btnShopPickCancel">取消</button>`;
    const panel = document.querySelector("#tab-imgs .panel"); if (panel) panel.prepend(tip);
    const backToModal = () => { tip.remove(); window.SHOP_PICK_TARGET = null; window.SHOP_PICK_KIND = null; modal.className = "show"; };
    document.getElementById("btnShopPickConfirm")?.addEventListener("click", () => {
      const sel = IMG_SELECTED;
      if (!sel) { toast("请先选中图片文件", "bad"); return; }
      _SP_ADD_FILE = null; _SP_ADD_SRC = sel; window._spAddImgPath = sel;
      backToModal(); setTip("内置：" + sel);
    });
    document.getElementById("btnShopPickCancel")?.addEventListener("click", () => { backToModal(); });
  });
  document.getElementById("spAddPreview")?.addEventListener("click", async () => {
    let p = window._spAddImgPath || _SP_ADD_SRC || "";
    if (!p) { toast("请先选一张图片", "bad"); return; }
    try {
      const r = await getBridge().apiPost("images/thumb", { path: p });
      const thumb = r && (r.thumb || (r.data && r.data.thumb));
      if (thumb) showLightbox(thumb, String(p).split("/").pop());
      else toast("无预览", "bad");
    } catch (e) { toast("预览失败:" + e.message, "bad"); }
  });
  if (cancelBtn) { cancelBtn.style.display = ""; cancelBtn.textContent = "取消"; cancelBtn.onclick = () => { modal.className = ""; }; }
  if (okBtn) {
    okBtn.textContent = "确定添加"; okBtn.style.background = "var(--acc)"; okBtn.style.borderColor = "transparent";
    okBtn.onclick = async () => {
      const n = (document.getElementById("spAddName")?.value || "").trim();
      if (!n) { toast("请填写精灵名称", "bad"); return; }
      const spirits = SPIRIT.spirits || (SPIRIT.spirits = {});
      const maps = SPIRIT.maps || (SPIRIT.maps = {});
      if (spirits[n] !== undefined) { toast("已存在同名精灵", "bad"); return; }
      const num = (id, d) => { const v = Number(document.getElementById(id)?.value); return Number.isFinite(v) ? Math.max(0, v) : (d || 0); };
      let imgPath = window._spAddImgPath || _SP_ADD_SRC || "";
      try {
        if (_SP_ADD_FILE) {
          const r = await postFile("images/upload?dir=" + encodeURIComponent("data/img/spirits"), {}, _SP_ADD_FILE);
          if (r && r.error) throw new Error(r.error);
          imgPath = (r && (r.path || (r.data && r.data.path))) || ("data/img/spirits/" + _SP_ADD_FILE.name);
        }
      } catch (e) { toast("图片上传失败:" + e.message, "bad"); return; }
      spirits[n] = {
        type: (document.getElementById("spAddType")?.value || "").trim(),
        hp: num("spAdd_hp", 40), atk: num("spAdd_atk", 40), def: num("spAdd_def", 40),
        spa: num("spAdd_spa", 40), spd: num("spAdd_spd", 40), spe: num("spAdd_spe", 40),
        lv: num("spAdd_lv", 50), evolve: (document.getElementById("spAddEvolve")?.value || "否").trim() || "否",
        img: imgPath || ""
      };
      if (defMap && defMap !== "__orphans__") {
        const dd = maps[defMap] || (maps[defMap] = { lv: 1, drops: [] });
        if (!Array.isArray(dd.drops)) dd.drops = [];
        if (!dd.drops.map(String).includes(n)) dd.drops.push(n);
        SPIRIT_OPEN[defMap] = true;
      }
      SPIRIT_DIRTY = true;
      modal.className = "";
      refreshSpiritViews();
      toast("已添加精灵，点保存精灵生效", "ok");
    };
  }
  modal.className = "show";
  setTimeout(() => { try { document.getElementById("spAddName")?.focus(); } catch (e) {} }, 50);
}

function renderShop(q = "", forceOpen = false) {
  const body = document.getElementById("shopSpiritBox");
  if (!body) return;
  const shop = (SPIRIT && SPIRIT.shop) ? SPIRIT.shop : {};
  const names = Object.keys(shop).filter((k) => !q || k.toLowerCase().includes(q));
  const curDetails = body.querySelector("details");
  const wasOpen = curDetails ? curDetails.open : forceOpen;
  let html = `<details class="panel" style="margin:0"${wasOpen ? " open" : ""}><summary style="cursor:pointer;font-weight:600">🎒 精灵道具商城 — ${names.length} 件</summary>`;
  html += `<div class="hint" style="margin-top:8px">类型决定效果：精灵球=收服率% / 等级=奇异甜食+Lv / HP·攻击·防御·特攻·特防=+对应点数 / 进化=进化液。改完点保存道具，只写精灵道具。</div>`;
  html += `<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap"><button id="shopAddItemTop" class="ghost sm">＋ 添加精灵道具</button><button id="btnShopSpiritSave" class="ghost sm">💾 保存道具</button><button id="btnShopSpiritReset" class="ghost sm">↩️ 恢复默认</button><button class="ghost sm" data-shopsec-up="shop" title="上移">↑</button><button class="ghost sm" data-shopsec-down="shop" title="下移">↓</button></div>`;
  if (!Object.keys(shop).length && !q) {
    html += `<div class="hint" style="margin:8px 0">当前无自定义道具，运行中使用内置 ${_spiritBuiltinCount("shop")} 件`
      + ` <button class="ghost sm" id="btnSpiritUseBuiltinShop">载入内置为起点</button></div>`;
  }
  if (!names.length) {
    html += `<div class="hint" style="margin:10px 0">无匹配物品</div>`;
  } else {
    names.forEach((key) => {
      const it = shop[key] || {};
      const _attr = String(it.attr || "");
      const _help = SHOP_ATTR_HELP[_attr] || "选类型后看说明";
      const attrCell = `<div class="s-row"><small>类型</small><select data-s-field="attr" style="width:96px">${SHOP_ATTR_OPTS.map((o) => `<option value="${esc(o)}"${o === _attr ? " selected" : ""}>${esc(o)}</option>`).join("")}${_attr && !SHOP_ATTR_OPTS.includes(_attr) ? `<option value="${esc(_attr)}" selected>${esc(_attr)}</option>` : ""}</select></div>`;
      const cells = `<div class="s-row"><small>价格</small><input data-s-field="price" type="number" value="${esc(it.price ?? 0)}" style="width:80px"></div>` + attrCell + `<div class="s-row"><small>效果(${esc(_help)})</small><input data-s-field="effect" type="number" value="${esc(it.effect ?? 0)}" style="width:70px"></div>`;
      html += `<div class="s-fields" data-s-item="${esc(key)}" style="margin-top:8px">` +
        `<div class="s-row" style="font-weight:600;min-width:90px"><small>道具名</small><div style="padding-top:4px">${esc(key)}</div></div>` +
        cells +
        `<button class="s-del" data-del-key="${esc(key)}" style="margin-left:auto">删除</button></div>`;
    });
  }
  html += `</details>`;
  body.innerHTML = html;
  document.getElementById("btnSpiritUseBuiltinShop")?.addEventListener("click", () => {
    if (_spiritLoadBuiltin("shop")) { renderShop(q, true); toast("已载入内置道具，点保存道具生效", "ok"); }
  });
  document.getElementById("btnShopSpiritSave")?.addEventListener("click", () => saveSpiritKind("shop"));
  document.getElementById("btnShopSpiritReset")?.addEventListener("click", () => resetSpiritKind("shop"));

  body.querySelectorAll("[data-s-field]").forEach((inp) => {
    const _ev = inp.tagName === "SELECT" ? "change" : "input";
    inp.addEventListener(_ev, () => {
      const parent = inp.closest("[data-s-item]");
      if (!parent) return;
      const key = parent.dataset.sItem;
      const fk = inp.dataset.sField;
      if (shop[key]) {
        shop[key][fk] = ["price", "effect"].includes(fk) ? (Number(inp.value) || 0) : inp.value;
        SPIRIT_DIRTY = true;
        if (fk === "attr") renderShop(q, true);
      }
    });
  });
  body.querySelectorAll("[data-del-key]").forEach((b) =>
    b.addEventListener("click", async () => {
      const k = b.dataset.delKey;
      const _last = Object.keys(shop).length <= 1;
      if (!(await uiConfirm("确认删除 \"" + k + "\"？" + (_last ? "\n\n注意：这是最后一件，删光后运行时自动使用内置道具。" : ""), "删除物品"))) return;
      delete shop[k];
      SPIRIT_DIRTY = true;
      renderShop(q, true);
      toast("已删除，点保存道具生效", "ok");
    }));
  const add = body.querySelector("#shopAddItemTop");
  if (add) add.addEventListener("click", async () => { openShopItemAddModal(q); });
}
function openShopItemAddModal(q) {
  const modal = document.getElementById("appModal");
  if (!modal || !SPIRIT) return;
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");
  if (icon) icon.textContent = "🎒";
  if (title) title.textContent = "添加精灵道具";
  if (inputWrap) inputWrap.style.display = "none";
  content.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:10px">
      <div><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">道具名：</label>
        <input id="shopAddName" style="width:100%;padding:6px 10px;border-radius:8px" placeholder="如：超级球"></div>
      <div style="display:flex;gap:8px">
        <div style="flex:1"><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">价格：</label>
          <input id="shopAddPrice" type="number" value="300" style="width:100%;padding:6px 10px;border-radius:8px"></div>
        <div style="flex:1"><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">类型：</label>
          <select id="shopAddAttr" style="width:100%;padding:6px 10px;border-radius:8px">${SHOP_ATTR_OPTS.map((o) => `<option value="${o}">${o}</option>`).join("")}</select></div>
        <div style="flex:1"><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">效果：</label>
          <input id="shopAddEffect" type="number" value="10" style="width:100%;padding:6px 10px;border-radius:8px"></div>
      </div>
      <div class="hint" id="shopAddHelp">精灵球=收服率%；等级=+Lv；HP/攻击/防御/特攻/特防=+点数；进化=1</div>
    </div>`;
  document.getElementById("shopAddAttr")?.addEventListener("change", (e) => {
    const v = e.target.value;
    const h = document.getElementById("shopAddHelp");
    if (h) h.textContent = "当前类型 " + v + "：" + (SHOP_ATTR_HELP[v] || "");
  });
  if (cancelBtn) { cancelBtn.style.display = ""; cancelBtn.textContent = "取消"; cancelBtn.onclick = () => { modal.className = ""; }; }
  if (okBtn) {
    okBtn.textContent = "确定添加"; okBtn.style.background = "var(--acc)"; okBtn.style.borderColor = "transparent";
    okBtn.onclick = () => {
      const n = (document.getElementById("shopAddName")?.value || "").trim();
      if (!n) { toast("请填写道具名称", "bad"); return; }
      const shop = (SPIRIT.shop || (SPIRIT.shop = {}));
      if (shop[n] !== undefined) { toast("已存在同名道具", "bad"); return; }
      shop[n] = {
        price: Math.max(0, Number(document.getElementById("shopAddPrice")?.value) || 0),
        attr: (document.getElementById("shopAddAttr")?.value || "精灵球"),
        effect: Math.max(0, Number(document.getElementById("shopAddEffect")?.value) || 0)
      };
      SPIRIT_DIRTY = true;
      modal.className = "";
      renderShop(q || "", true);
      toast("已添加，点保存道具生效", "ok");
    };
  }
  modal.className = "show";
  setTimeout(() => { try { document.getElementById("shopAddName")?.focus(); } catch (e) {} }, 50);
}

const SPIRIT_KIND_LABEL = { maps: "地图", spirits: "属性", shop: "道具", all: "精灵" };
async function saveSpiritKind(kind, silent = false) {
  // 按系统保存：直接存 SPIRIT 状态（输入即时写回，与过滤/视图无关，杜绝搜后保存丢数据）
  // maps+spirits 已合并为 all 一键保存，避免只存一半丢形象图；shop 独立保存
  if (kind === "maps" || kind === "spirits") kind = "all";
  const msg = document.getElementById("spiritMsg");
  if (!SPIRIT) {
    if (!silent) toast("请先加载图鉴", "bad");
    return false; // 加载失败时如实返回失败，全部保存据此告警，不误报成功
  }
  if (!["all", "shop"].includes(kind)) return false;
  try {
    const payload = kind === "all" ? { maps: SPIRIT.maps || {}, spirits: SPIRIT.spirits || {} } : { shop: SPIRIT.shop || {} };
    const r = await getBridge().apiPost("spirits/save", payload);
    if (r && r.error) throw new Error(r.error);
    if (kind === "all") { SPIRIT_CUSTOM.maps = true; SPIRIT_CUSTOM.spirits = true; }
    else SPIRIT_CUSTOM[kind] = true;
    SPIRIT_DIRTY = false;
    const label = kind === "all" ? "精灵" : SPIRIT_KIND_LABEL[kind];
    if (!silent) {
      if (msg) { msg.className = "msg ok"; msg.textContent = label + "已保存"; }
      toast(label + "已保存", "ok");
    }
    return true;
  } catch (e) {
    if (!silent) {
      if (msg) { msg.className = "msg bad"; msg.textContent = "保存失败: " + e.message; }
      toast("保存失败: " + e.message, "bad");
    }
    return false;
  }
}
async function resetSpiritKind(kind) {
  // 按系统恢复内置：直接清理旧数据并持久化，不保留（数据库自有备份可回滚）
  // maps+spirits 合并为 all 一键恢复默认，shop 独立
  if (kind === "maps" || kind === "spirits") kind = "all";
  if (!SPIRIT) { toast("请先加载图鉴", "bad"); return; }
  if (!["all", "shop"].includes(kind)) return;
  const label = kind === "all" ? "精灵" : SPIRIT_KIND_LABEL[kind];
  if (!(await uiConfirm(`直接恢复${label}为内置默认？旧数据不保留。`, `恢复默认`))) return;
  try {
    if (kind === "all") {
      ["maps", "spirits"].forEach((k) => {
        const b = (SPIRIT._builtin && SPIRIT._builtin[k]) || {};
        SPIRIT[k] = JSON.parse(JSON.stringify(b));
        SPIRIT_CUSTOM[k] = true;
      });
      SPIRIT_OPEN = {};
      await getBridge().apiPost("spirits/save", { maps: SPIRIT.maps || {}, spirits: SPIRIT.spirits || {} });
    } else {
      const b = (SPIRIT._builtin && SPIRIT._builtin[kind]) || {};
      SPIRIT[kind] = JSON.parse(JSON.stringify(b));
      SPIRIT_CUSTOM[kind] = true;
      await getBridge().apiPost("spirits/save", { [kind]: SPIRIT[kind] || {} });
    }
    SPIRIT_DIRTY = false;
    try { renderShop(); } catch (e) {}
    refreshSpiritViews();
    toast(`已恢复${label}默认`, "ok");
  } catch (e) { toast("恢复失败: " + e.message, "bad"); }
}

async function exportSpirits() {
  // 导出与导入同一套格式：干净的 {spirits, maps, shop}；走统一导出通道（自动下载+弹窗手动兜底）
  try {
    const data = SPIRIT || await getBridge().apiGet("spirits");
    const clean = { spirits: (data && data.spirits) || {}, maps: (data && data.maps) || {}, shop: (data && data.shop) || {} };
    triggerExportResult({ filename: "xbbot_spirit_" + Date.now() + ".json", mime: "application/json;charset=utf-8", rawText: JSON.stringify(clean, null, 2) });
    toast("图鉴已导出", "ok");
  } catch (e) { toast("导出失败: " + e.message, "bad"); }
}
async function importSpirits() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json,application/json";
  inp.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try {
      // BOM 头（Windows 记事本存档常见）先剥，否则 JSON.parse 必炸，导出文件反而导不回
      const txt = (await file.text()).replace(/^\uFEFF/, "");
      const data = JSON.parse(txt);
      // 空图鉴导出的 {spirits:{},maps:{},shop:{}} 全空对象仍合法（旧代码按值真假判空文件直接拒掉）
      const has = data && typeof data === "object" && !Array.isArray(data)
        && ("spirits" in data || "maps" in data || "shop" in data);
      if (!has) throw new Error("JSON需包含 spirits/maps/shop（请用本页导出的文件）");
      const payload = {};
      ["spirits", "maps", "shop"].forEach((k) => { if (data[k] && typeof data[k] === "object" && !Array.isArray(data[k])) payload[k] = data[k]; });
      if (!Object.keys(payload).length) throw new Error("文件中无有效数据");
      const r = await getBridge().apiPost("spirits/save", payload);
      if (r && r.error) throw new Error(r.error);
      toast("已导入" + Object.keys(payload).join("、"), "ok");
      await loadSpirits(true);
    } catch (err) { toast("导入失败: " + err.message, "bad"); }
  };
  inp.click();
}

// ---------- 预设包 v2（图鉴＋宝物＋商城一次打包/恢复；武器图片二进制不在内，缺图跳过） ----------
function _presetAtlasPart(sp) {
  // 导出用原始自定义（_raw），不用渲染态：未自定义的节不把内置 baked 进包
  const out = {};
  try {
    if (!sp || typeof sp !== "object") return out;
    const _hasMeta = sp._raw && sp._meta;
    ["spirits", "maps", "shop"].forEach((k) => {
      const v = _hasMeta ? sp._raw[k] : sp[k];
      if (v && typeof v === "object" && !Array.isArray(v)) out[k] = v;
    });
  } catch (e) {}
  return out;
}
async function exportPreset() {
  // 打包：图鉴原始自定义＋宝物（内存优先，未保存的编辑也带上）＋商城 JSON 节；走统一导出通道
  try {
    toast("正在打包预设…", "");
    let sp = null;
    try { sp = (typeof SPIRIT !== "undefined" && SPIRIT) ? SPIRIT : null; } catch (e) { sp = null; }
    if (!sp || (!sp.maps && !sp.spirits && !sp.shop && !sp._raw)) {
      try { sp = await apiTimeout(getBridge().apiGet("spirits"), 20000, "spirits"); } catch (e) { sp = null; }
    }
    const cur = await apiTimeout(getBridge().apiGet("config/get"), 20000, "config/get");
    const shopSec = (cur && cur["商城图鉴"]) || {};
    const setSec = (cur && cur["设置"]) || {};
    let tlist = "";
    let teff = {};
    try {
      if (window._TREAS_DIRTY && Array.isArray(window._TREAS_LIST)) tlist = window._TREAS_LIST.filter(Boolean).join("|");
      else tlist = String(setSec["宝物"] || "");
      const _te = shopSec["treasure_effects"];
      if (_te && typeof _te === "object" && !Array.isArray(_te)) teff = _te;
      else if (typeof _te === "string" && _te.trim()) { try { teff = JSON.parse(_te); } catch (e) { teff = {}; } }
      if (window._TREAS_EFF && typeof window._TREAS_EFF === "object") teff = Object.assign({}, teff, window._TREAS_EFF);
    } catch (e) {}
    const shops = {};
    ["ride_shop", "weapon_attrs", "weapon_order"].forEach((k) => { if (shopSec[k] !== undefined) shops[k] = shopSec[k]; });
    const payload = {
      app: "astrbot_plugin_xbbot_beta", kind: "preset", version: 2,
      exported_at: new Date().toISOString(),
      from_version: (typeof FRONTEND_VER !== "undefined" ? FRONTEND_VER : ""),
      parts: { atlas: _presetAtlasPart(sp), treasure: { list: tlist, eff: teff }, shops }
    };
    triggerExportResult({ filename: "xbbot_preset_" + Date.now() + ".json", mime: "application/json;charset=utf-8", rawText: JSON.stringify(payload, null, 2) });
    toast("预设已打包", "ok");
  } catch (e) { toast("打包失败: " + (e.message || e), "bad"); }
}
async function importPreset() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json,application/json";
  inp.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const txt = (await file.text()).replace(/^\uFEFF/, "");
      const data = JSON.parse(txt);
      if (!data || typeof data !== "object" || data.kind !== "preset" || !data.parts || typeof data.parts !== "object")
        throw new Error("不是预设包（请用本页“预设打包”导出的文件）");
      const parts = data.parts;
      const _n = (o) => (o && typeof o === "object" ? Object.keys(o).length : 0);
      const cnt = [];
      if (parts.atlas && typeof parts.atlas === "object") {
        const bits = ["spirits", "maps", "shop"].filter((k) => parts.atlas[k] && typeof parts.atlas[k] === "object").map((k) => k + _n(parts.atlas[k]));
        if (bits.length) cnt.push("图鉴(" + bits.join("/") + ")");
      }
      if (parts.treasure && typeof parts.treasure === "object"
        && (parts.treasure.list || _n(parts.treasure.eff)))
        cnt.push("宝物" + String(parts.treasure.list || "").split("|").filter(Boolean).length + "件");
      if (parts.shops && typeof parts.shops === "object") {
        const bits = ["ride_shop", "weapon_attrs", "weapon_order"].filter((k) => parts.shops[k] !== undefined);
        if (bits.length) cnt.push("商城(" + bits.join("/") + ")");
      }
      if (!cnt.length) throw new Error("包内无有效数据");
      if (!(await uiConfirm("导入预设将覆盖：" + cnt.join("、") + "。\n先自动存一份配置快照，可回滚，继续？", "恢复预设"))) return;
      try { await getBridge().apiPost("backups/config/snapshot/save", {}); }
      catch (err) {
        if (!(await uiConfirm("快照失败（" + ((err && err.message) || err) + "），无回滚点仍继续？", "恢复预设"))) return;
      }
      const done = [], failed = [];
      try {
        const a = parts.atlas || {};
        const payload = {};
        ["spirits", "maps", "shop"].forEach((k) => { if (a[k] && typeof a[k] === "object") payload[k] = a[k]; });
        if (Object.keys(payload).length) {
          const r = await getBridge().apiPost("spirits/save", payload);
          if (r && r.error) throw new Error(r.error);
          done.push("图鉴");
        }
      } catch (err) { failed.push("图鉴:" + ((err && err.message) || err)); }
      try {
        const cfgPayload = {};
        if (parts.treasure && typeof parts.treasure === "object"
          && (parts.treasure.list !== undefined || parts.treasure.eff !== undefined)) {
          cfgPayload["设置"] = {};
          if (parts.treasure.list !== undefined) cfgPayload["设置"]["宝物"] = String(parts.treasure.list || "");
          cfgPayload["商城图鉴"] = {};
          const _eff = parts.treasure.eff;
          cfgPayload["商城图鉴"]["treasure_effects"] = (typeof _eff === "string") ? _eff : JSON.stringify(_eff || {});
        }
        if (parts.shops && typeof parts.shops === "object") {
          cfgPayload["商城图鉴"] = cfgPayload["商城图鉴"] || {};
          ["ride_shop", "weapon_attrs", "weapon_order"].forEach((k) => {
            if (parts.shops[k] !== undefined) cfgPayload["商城图鉴"][k] = parts.shops[k];
          });
        }
        if (Object.keys(cfgPayload).length) {
          const r = await getBridge().apiPost("config/save", cfgPayload);
          if (r && r.error) throw new Error(r.error);
          if (cfgPayload["设置"]) done.push("宝物");
          if (cfgPayload["商城图鉴"] && Object.keys(cfgPayload["商城图鉴"]).length) done.push("商城");
        }
      } catch (err) { failed.push("宝物/商城:" + ((err && err.message) || err)); }
      try { await loadSpirits(true); } catch (err) {}
      try { if (typeof loadShops === "function") await loadShops(); } catch (err) {}
      if (failed.length) toast("部分恢复失败：" + failed.join("；"), "bad");
      else toast("预设已恢复：" + done.join("、"), "ok");
    } catch (err) { toast("导入失败: " + ((err && err.message) || err), "bad"); }
  };
  inp.click();
}

// ---------- 事件绑定 ----------
document.getElementById("btnSave")?.addEventListener("click", saveConfig);
document.getElementById("btnAutoBalance")?.addEventListener("click", openAutoBalanceModal);
document.getElementById("btnAutoBalance2")?.addEventListener("click", openAutoBalanceModal);
document.getElementById("btnReset")?.addEventListener("click", resetConfig);
document.getElementById("btnResetAll")?.addEventListener("click", resetAllConfig);
const rkSel = document.getElementById("rankType");
rkSel?.addEventListener("change", () => loadRank(rkSel.value));
document.getElementById("btnRank")?.addEventListener("click", () => loadRank(rkSel ? rkSel.value : "money"));
document.getElementById("btnUsers")?.addEventListener("click", loadUsers);
document.getElementById("userSort")?.addEventListener("change", renderUserTable);
document.getElementById("userGidFilter")?.addEventListener("change", async () => {
  const sel = document.getElementById("userGidFilter");
  USER_GID_FILTER = (sel?.value || "").trim();
  await loadUsers();
});
document.getElementById("userBody")?.addEventListener("click", async (e) => {
  const bSave = e.target.closest("button[data-save]");
  if (bSave) { saveUserEdit(bSave.dataset.qq, bSave.dataset.gid, bSave); return; }
  const bExp = e.target.closest("button[data-export]");
  if (bExp) {
    try {
      const res = await getBridge().apiGet("user/export", { gid: bExp.dataset.gid, qq: bExp.dataset.qq });
      if (res && res.data) {
        downloadBase64File(res.data, res.filename || `xbbot_user_${bExp.dataset.qq}_${bExp.dataset.gid}.json`);
      } else if (res) {
        downloadJson(res, `xbbot_user_${bExp.dataset.qq}_${bExp.dataset.gid}.json`);
      }
    } catch (err) { toast("导出失败: " + err.message, "bad"); }
    return;
  }
  const bClr = e.target.closest("button[data-clear='user']");
  if (bClr) { clearUserSingle(bClr.dataset.qq, bClr.dataset.gid); return; }
});
["cfgSearch", "userSearch", "cmdSearch", "imgSearch", "slaveSearch", "spiritUserSearch", "groupsSearch"].forEach((id) => {
  const el = document.getElementById(id);
  if (el) {
    let _t = null;
    el.addEventListener("input", () => {
      if (_t) clearTimeout(_t);
      _t = setTimeout(() => {
        if (id === "cfgSearch") filterCfg();
        else if (id === "userSearch") filterUsers();
        else if (id === "cmdSearch") filterCmds();
        else if (id === "slaveSearch") renderSlaveTable();
        else if (id === "spiritUserSearch") renderSpiritUsersTable();
        else if (id === "groupsSearch") renderGroupsTable();
        else if (IMG_CACHE && IMG_CACHE.dir !== undefined) renderImages(IMG_CACHE);
      }, 200);
    });
  }
});
const lb = document.getElementById("lightbox");
if (lb) lb.addEventListener("click", closeLightbox);
document.getElementById("btnImgUp")?.addEventListener("click", () => {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = "image/*";
  inp.onchange = (e) => uploadImage(e.target.files[0]);
  inp.click();
});
document.getElementById("btnImgBack")?.addEventListener("click", () => {
  const parts = (IMG_DIR || "").split("/").filter(Boolean);
  parts.pop();
  loadImages(parts.join("/"));
});
document.getElementById("btnImgNewFolder")?.addEventListener("click", async () => {
  const name = await uiPrompt("新建文件夹名:", "", "新建文件夹");
  if (!name || !name.trim()) return;
  const nn = name.trim().replace(/[\/\\]/g, "");
  const target = (IMG_DIR ? IMG_DIR + "/" : "") + nn;
  try { await getBridge().apiPost("images/mkdir", { path: target }); toast("已创建文件夹", "ok"); await loadImages(IMG_DIR); } catch (e) { toast("创建失败: " + e.message, "bad"); }
});
document.getElementById("btnImgCopy")?.addEventListener("click", () => {
  if (!IMG_SELECTED) { toast("请先点击选中要复制的文件/文件夹", "bad"); return; }
  IMG_CLIP = IMG_SELECTED;
  toast("已复制: " + IMG_CLIP, "ok");
});
document.getElementById("btnImgPaste")?.addEventListener("click", async () => {
  if (!IMG_CLIP) { toast("请先复制", "bad"); return; }
  try { await getBridge().apiPost("images/copy", { src: IMG_CLIP, dst: IMG_DIR }); toast("已粘贴", "ok"); await loadImages(IMG_DIR); } catch (e) { toast("粘贴失败: " + e.message, "bad"); }
});
async function exportImages() {
  const p = IMG_SELECTED || IMG_DIR || "";
  const filename = (p ? p.split("/").pop() : "root") || "root";
  const defaultFn = (filename === "root" ? `xbbot_root_${Date.now()}.zip` : `${filename}.zip`);
  toast("正在打包导出文件/目录，请稍候...", "ok");
  try {
    // 单次 callApi（GET空结果不再回退POST，失败兜底在callApi内）
    const r = await callApi("images/export", { path: p }, "GET");
    if (!r) throw new Error("接口无响应");
    if (r.error || r.msg) throw new Error(r.error || r.msg);

    const outFn = r.filename || defaultFn;
    const base64Data = r.data || "";

    if (base64Data) {
      triggerExportResult({
        filename: outFn,
        mime: outFn.endsWith(".zip") ? "application/zip" : "application/octet-stream",
        base64Data: base64Data
      });
      toast("已成功导出 " + outFn, "ok");
      return;
    }

    const fallbackStr = typeof r === "string" ? r : JSON.stringify(r, null, 2);
    triggerExportResult({
      filename: outFn.replace(/\.zip$/, ".json"),
      mime: "application/json;charset=utf-8",
      rawText: fallbackStr
    });
    toast("已成功导出 " + outFn, "ok");
  } catch (e) {
    toast("导出失败: " + e.message, "bad");
  }
}
document.getElementById("btnImgExport")?.addEventListener("click", exportImages);
document.getElementById("btnImgImport")?.addEventListener("click", () => {
  const inp = document.createElement("input");
  inp.type = "file";
  inp.onchange = (e) => uploadImage(e.target.files[0]);
  inp.click();
});

document.getElementById("btnImgDelete")?.addEventListener("click", async () => {
  const sel = IMG_SELECTED || "";
  if (!sel) { toast("请先单击选中要删除的文件", "bad"); return; }
  if (!(await uiConfirm("确认删除 " + sel + "？", "删除文件"))) return;
  if (!(await uiConfirm("再次确认删除 \"" + sel + "\"？", "终极确认删除"))) return;
  try { await getBridge().apiPost("images/delete", { path: sel }); toast("已删除", "ok"); IMG_SELECTED=""; await loadImages(IMG_DIR); } catch (err) { toast("删除失败: " + err.message, "bad"); }
});
document.getElementById("btnImgRename")?.addEventListener("click", async () => {
  const sel = IMG_SELECTED || "";
  if (!sel) { toast("请先单击选中要重命名的文件", "bad"); return; }
  const cur = sel.split("/").pop();
  const nn = await uiPrompt("新文件名（含扩展名）:", cur, "重命名");
  if (!nn || nn === cur) return;
  try { await getBridge().apiPost("images/rename", { path: sel, name: nn }); toast("已重命名", "ok"); IMG_SELECTED=""; await loadImages(IMG_DIR); } catch (err) { toast("重命名失败: " + err.message, "bad"); }
});
// 指令编辑模态
const _btnCmdSave = document.getElementById("cmdModalSave") || document.getElementById("btnCmdModalSave");
const _btnCmdCancel = document.getElementById("cmdModalCancel") || document.getElementById("btnCmdModalCancel");
const _btnCmdDelete = document.getElementById("cmdModalDel") || document.getElementById("btnCmdModalDelete");
const _cmdModal = document.getElementById("cmdModal");
if (_btnCmdSave) _btnCmdSave.addEventListener("click", saveCmdEditor);
if (_btnCmdCancel) _btnCmdCancel.addEventListener("click", closeCmdEditor);
  document.getElementById("btnCmdModalClose")?.addEventListener("click", closeCmdEditor);
if (_btnCmdDelete) _btnCmdDelete.addEventListener("click", deleteCmdEditor);
if (_cmdModal) _cmdModal.addEventListener("click", (e) => {
  if (e.target === _cmdModal) closeCmdEditor();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeCmdEditor();
});
// 自定义指令: 填入「映射引擎指令」实时刷新其可调数值 + 常用变量帮助
const _cmdModalCmd = document.getElementById("cmdModalCmd");
if (_cmdModalCmd) _cmdModalCmd.addEventListener("input", () => {
  renderCmdNums(_cmdModalCmd.value.trim(), true);
});
document.getElementById("btnVarsHelp")?.addEventListener("click", () => {
  const h = document.getElementById("varsHelp");
  if (h) h.style.display = h.style.display === "none" ? "block" : "none";
});
document.querySelectorAll("#varsHelp .var-tag").forEach(el => {
  el.addEventListener("click", () => {
    const v = el.dataset.var || "";
    const ta = document.getElementById("cmdModalReply");
    if (!ta || !v) return;
    const s = ta.selectionStart || ta.value.length, e = ta.selectionEnd || ta.value.length;
    ta.value = ta.value.slice(0,s) + v + ta.value.slice(e);
    ta.focus(); ta.selectionStart = ta.selectionEnd = s + v.length;
  });
});

// 精灵图鉴（地图/属性在总览 ✨ 精灵页签分系统保存恢复，道具在商城页；加载按钮已删，Tab 打开自动拉取）
document.getElementById("btnSpiritExport")?.addEventListener("click", exportSpirits);
document.getElementById("btnPresetExport")?.addEventListener("click", exportPreset);
document.getElementById("btnPresetImport")?.addEventListener("click", importPreset);
document.getElementById("btnSpiritImport")?.addEventListener("click", importSpirits);

// 商城图鉴 (每商城独立栏 自由增删重命名+图片绑定)
const DEFAULT_RIDE_SHOP = {
  "企鹅": { price: 213250, img: "data/img/rides/企鹅.jpg" },
  "伞兵": { price: 500000, img: "data/img/rides/伞兵.jpg" },
  "宝驴": { price: 1000000, img: "data/img/rides/宝驴.jpg" },
  "保时捷": { price: 1500000, img: "data/img/rides/保时捷.jpg" },
  "法拉利": { price: 1500000, img: "data/img/rides/法拉利.jpg" },
  "玛莎拉蒂": { price: 1500000, img: "data/img/rides/玛莎拉蒂.jpg" },
  "劳斯莱斯": { price: 1500000, img: "data/img/rides/劳斯莱斯.jpg" },
  "布加迪威龙": { price: 1500000, img: "data/img/rides/布加迪威龙.jpg" },
  "私人航空": { price: 5000000, img: "data/img/rides/私人航空.jpg" },
  "老八": { price: 500000, img: "data/img/rides/老八.jpg" },
};
let SHOP_RIDE = {};
let SHOP_DIRTY = false;
let SHOP_RIDE_CUSTOM = true;   // false=当前展示的是内置默认（未自定义），保存后即转为自定义
let POOL_WEAPONS = { SSR: [], SR: [], R: [] };   // 抽奖武器池文件（可编辑：改名/改稀有度/删除/上传）

function _parseShopInput(raw, normalize) {
  // 统一入口：raw 可为 dict（生产内存归一形态）/ JSON 串 / 空。
  // 返回 {data, blank}：blank=true 从未配置；空对象+非blank=用户显式清空；corrupt 按清空处理并告警。
  if (raw === undefined || raw === null) return { data: {}, blank: true };
  if (typeof raw === "object" && !Array.isArray(raw)) {
    const keys = Object.keys(raw);
    if (!keys.length) return { data: {}, blank: false };
    try { return { data: normalize(raw), blank: false }; }
    catch (e) { return { data: {}, blank: false, corrupt: true }; }
  }
  const s = String(raw).trim();
  if (!s) return { data: {}, blank: true };
  try {
    const d = JSON.parse(s);
    if (typeof d === "object" && d && !Array.isArray(d)) {
      if (!Object.keys(d).length) return { data: {}, blank: false };
      return { data: normalize(d), blank: false };
    }
  } catch (e) {}
  return { data: {}, blank: false, corrupt: true };
}

function _normRideObj(d) {
  const out = {};
  Object.keys(d).forEach((k) => {
    const v = d[k];
    if (v && typeof v === "object" && !Array.isArray(v)) out[k] = { price: Number(v.price) || 0, img: String(v.img || "") };
    else out[k] = { price: Number(v) || 0, img: "" };
  });
  return out;
}

async function loadPool(skipAtlas = false) {
  // 抽奖武器池文件列表（生效目录，操作即时生效，无需保存；超时转空，不断整链）
  try {
    const d = await apiTimeout(getBridge().apiGet("weapons/pool"), 20000, "weapons/pool").catch(() => null);
    if (d && d.ok && d.pool) POOL_WEAPONS = d.pool;
  } catch (e) {}
  try {
    POOL_ATTRS = {};
    ["SSR", "SR", "R"].forEach((r) => ((POOL_WEAPONS && POOL_WEAPONS[r]) || []).forEach((it) => {
      const a = (it && it.attrs) || {};
      POOL_ATTRS[it.name] = { atk: Number(a.atk) || 0, desc: String(a.desc || "") };
    }));
    POOL_ATTRS_DIRTY = false;
  } catch (e) {}
  try { _applyPoolOrder(); } catch (e) {}
  try { renderPoolBox(); } catch (e) {}
}
function poolCount() {
  try { return ["SSR", "SR", "R"].reduce((n, r) => n + ((POOL_WEAPONS && POOL_WEAPONS[r]) || []).length, 0); } catch (e) { return 0; }
}
let POOL_ATTRS = {};
let POOL_ATTRS_DIRTY = false;
let _POOL_ORDER = null;       // {SSR:[...],SR:[...],R:[...]} | null=未加载则按名稳定排
function _applyPoolOrder() {
  // 按 weapon_order 排 POOL_WEAPONS：收录的按序，未收录的新文件按名追加，显示稳定不乱跳
  try {
    const ord = _POOL_ORDER || {};
    ["SSR", "SR", "R"].forEach((rar) => {
      const arr = (POOL_WEAPONS && POOL_WEAPONS[rar]) || [];
      const want = Array.isArray(ord[rar]) ? ord[rar].map(String) : [];
      if (!want.length) { arr.sort((a, b) => String(a.name).localeCompare(String(b.name), "zh")); return; }
      const pos = {};
      want.forEach((n, i) => { if (!(n in pos)) pos[n] = i; });
      arr.sort((a, b) => {
        const pa = (a.name in pos) ? pos[a.name] : 1e9;
        const pb = (b.name in pos) ? pos[b.name] : 1e9;
        if (pa !== pb) return pa - pb;
        return String(a.name).localeCompare(String(b.name), "zh");
      });
    });
  } catch (e) {}
}
function _savePoolOrder(rar) {
  // 从内存数组回写顺序（默认全栏；传 rar 则只写该栏），标脏待 persist
  try {
    const o = Object.assign({}, _POOL_ORDER || {});
    ["SSR", "SR", "R"].forEach((r) => {
      if (!rar || r === rar) o[r] = ((POOL_WEAPONS && POOL_WEAPONS[r]) || []).map((it) => it.name);
    });
    _POOL_ORDER = o;
  } catch (e) {}
}
async function _persistPoolOrder() {
  // 顺序即时持久化：商城图鉴.weapon_order（JSON 串，与 treasure_effects 同口径，不碰武器文件与属性）
  const o = _POOL_ORDER || { SSR: [], SR: [], R: [] };
  const r = await getBridge().apiPost("config/save", { "商城图鉴": { "weapon_order": JSON.stringify(o) } });
  if (r && r.error) throw new Error(r.error);
  try { if (CFG && CFG.cur && CFG.cur["商城图鉴"]) CFG.cur["商城图鉴"]["weapon_order"] = (typeof o === "string" ? o : JSON.stringify(o)); } catch (e) {}
}
function renderPoolBox(forceOpen=false){
  const box=document.getElementById("poolWeaponBox");
  if(!box) return;
  const curDetails=box.querySelector("details");
  const wasOpen=curDetails?curDetails.open:forceOpen;
  const openGroups = {};
  try { box.querySelectorAll("details[data-pool-group]").forEach((d) => { openGroups[d.dataset.poolGroup] = d.open; }); } catch (e) {}
  let html=`<details class="panel" style="margin:0"${wasOpen?" open":""}><summary style="cursor:pointer;font-weight:600">🎰 抽奖武器池 — ${poolCount()} 件</summary>`;
  html+=`<div class="hint" style="margin-top:8px">武器=图片文件本身：改名改文件名，稀有度改所在目录；攻击加成参战、描述进详情，改完点保存武器属性；↑↓ 排序即时保存</div>`;
  html+=`<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap"><button class="ghost sm" id="btnPoolUploadTop">＋ 添加武器</button><button class="ghost sm" id="btnPoolAttrsSave">💾 保存武器属性</button><button class="ghost sm" id="btnPoolAttrsReset">↩️ 恢复默认</button><button class="ghost sm" data-shopsec-up="pool" title="上移">↑</button><button class="ghost sm" data-shopsec-down="pool" title="下移">↓</button></div>`;
  ["SSR","SR","R"].forEach((rar)=>{
    const items=(POOL_WEAPONS&&POOL_WEAPONS[rar])||[];
    const open = openGroups[rar] !== undefined ? openGroups[rar] : false;
    html+=`<details data-pool-group="${rar}" style="margin-top:8px;border:1px solid var(--line);border-radius:8px;padding:6px 10px"${open?" open":""}><summary style="cursor:pointer;font-weight:600">${esc(rar)} (${items.length})</summary>`;
    if(!items.length){ html+=`<div class="hint">空</div>`; }
    items.forEach((it)=>{
      const name=it.name;
      const _ext=((it.file||"").split(".").pop()||"").toLowerCase();
      const _kb=(it.size!=null)?Math.max(1,Math.round(it.size/1024))+"KB":"";
      const pv = it.thumb
        ? `<img loading="lazy" decoding="async" src="${esc(it.thumb)}" data-pool-thumb="${esc(name)}" style="width:36px;height:36px;object-fit:cover;border:1px solid var(--line);border-radius:6px;cursor:zoom-in" title="点击放大" onerror="this.style.display='none'">`
        : `<span data-pool-thumb="${esc(name)}" style="display:inline-flex;align-items:center;cursor:zoom-in" title="点击放大"><span class="badge" style="font-size:11px" title="${esc(it.file||name)}">${esc(_ext||"?")}${_kb?" · "+_kb:""}</span></span>`;
      const pa = (POOL_ATTRS && POOL_ATTRS[name]) || { atk: 0, desc: "" };
      const _paAtk = Math.max(0, Number(pa.atk) || 0);
      const _paDesc = String(pa.desc || "");
      html+=`<div data-pool-item="${esc(rar)}|${esc(name)}" style="margin-top:6px">`+
        `<div style="font-size:11px;color:var(--muted);margin:0 2px 2px">📌 默认：攻击加成 +${esc(_paAtk)}${_paDesc ? " · " + esc(_paDesc.slice(0, 20)) : " · 无描述"} · 星级基础另计（★0+100→★5+1600）</div>`+
        `<div class="s-fields">`+
        `<div class="s-row" style="font-weight:600;min-width:90px"><div style="padding-top:4px">✦ ${esc(name)}</div></div>`+
        `<div class="s-row"><small>稀有度</small><select data-pool-rar>${["SSR","SR","R"].map((r)=>`<option value="${r}"${r===rar?" selected":""}>${r}</option>`).join("")}</select></div>`+
        `<div class="s-row"><small>攻击加成</small><input type="number" data-pool-atk value="${esc(pa.atk ?? 0)}" style="width:70px"></div>`+
        `<div class="s-row" style="flex:1"><small>描述</small><input data-pool-desc value="${esc(pa.desc ?? "")}" placeholder="详情页展示"></div>`+
        `<div style="display:flex;gap:4px;align-items:center;flex-wrap:wrap">${pv}<button class="ghost sm" data-pool-pick-upload>外置选图</button><button class="ghost sm" data-pool-pick-builtin>内置选图</button><button class="ghost sm" data-pool-rename>改名</button><button class="ghost sm" data-pool-up title="上移">↑</button><button class="ghost sm" data-pool-down title="下移">↓</button><button class="s-del" data-pool-del>删除</button></div>`+
        `</div></div>`;
    });
    html+=`</details>`;
  });
  html += `</details>`;
  box.innerHTML=html;
  // 分区展开时懒加载图片预览（自动匹配，展开才取，不卡首屏）
  box.querySelectorAll("details[data-pool-group]").forEach((d) => {
    d.addEventListener("toggle", () => {
      if (!d.open || d.dataset.thumbsLoaded) return;
      d.dataset.thumbsLoaded = "1";
      const rar = d.dataset.poolGroup;
      ((POOL_WEAPONS && POOL_WEAPONS[rar]) || []).forEach((it) => {
        if (it.thumb) return;
        getBridge().apiPost("weapons/pool/img", { name: it.name }).then((r) => {
          const thumb = r && (r.thumb || (r.data && r.data.thumb));
          if (!thumb || (r && r.error)) return;
          it.thumb = thumb;
          const slot = box.querySelector(`[data-pool-item="${CSS.escape(rar + "|" + it.name)}"] [data-pool-thumb]`);
          if (slot) slot.outerHTML = `<img loading="lazy" decoding="async" src="${esc(thumb)}" data-pool-thumb="${esc(it.name)}" style="width:36px;height:36px;object-fit:cover;border:1px solid var(--line);border-radius:6px;cursor:zoom-in" title="点击放大" onerror="this.style.display='none'">`;
        }).catch(() => {});
      });
    });
  });
  if (!box.dataset.thumbBound) {
    box.dataset.thumbBound = "1";
    box.addEventListener("click", async (e) => {
      const t = e.target.closest("[data-pool-thumb]");
      if (!t) return;
      const wrap = t.closest("[data-pool-item]");
      const nm = wrap ? wrap.dataset.poolItem.split("|").slice(1).join("|") : t.dataset.poolThumb;
      if (!nm) return;
      const cached = (() => { try { for (const r of ["SSR", "SR", "R"]) { const f = ((POOL_WEAPONS && POOL_WEAPONS[r]) || []).find((x) => x.name === nm); if (f && f.thumb) return f.thumb; } } catch (err) {} return ""; })();
      if (cached) { showLightbox(cached, nm); return; }
      try {
        const r = await getBridge().apiPost("weapons/pool/img", { name: nm });
        const thumb = r && (r.thumb || (r.data && r.data.thumb));
        if (r && r.error) throw new Error(r.error);
        if (thumb) showLightbox(thumb, nm);
        else toast("无预览", "bad");
      } catch (err) { toast("预览失败:" + (err.message || err), "bad"); }
    });
  }
  // 池内排序委托（一次）：同稀有度内上移/下移，顺序即时保存
  if (!box.dataset.poolSortBound) {
    box.dataset.poolSortBound = "1";
    box.addEventListener("click", async (e) => {
      const t = e.target && e.target.closest ? e.target : null;
      if (!t || !box.contains(t)) return;
      const up = t.closest("[data-pool-up]");
      const dn = t.closest("[data-pool-down]");
      if (!up && !dn) return;
      const wrap = (up || dn).closest("[data-pool-item]");
      if (!wrap) return;
      const parts = String(wrap.dataset.poolItem || "").split("|");
      const rar = parts[0] || null, nm = parts.slice(1).join("|") || null;
      const arr = (rar && POOL_WEAPONS && POOL_WEAPONS[rar]) || null;
      if (!arr || !nm) return;
      const i = arr.findIndex((it) => it && it.name === nm);
      const j = i + (up ? -1 : 1);
      if (i < 0 || j < 0 || j >= arr.length) return;
      const tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
      _savePoolOrder(rar);
      try { await _persistPoolOrder(); toast("已排序并保存", "ok"); }
      catch (err) { toast("保存失败: " + (err.message || err), "bad"); }
      try { renderPoolBox(true); } catch (err2) {}
    });
  }
  const _poolKey = (el) => {
    const wrap = el.closest("[data-pool-item]");
    if (!wrap) return [null, null];
    const parts = String(wrap.dataset.poolItem || "").split("|");
    return [parts[0] || null, parts.slice(1).join("|") || null];
  };
  box.querySelectorAll("[data-pool-rename]").forEach(b=>b.addEventListener("click", async()=>{
    const [, old] = _poolKey(b);
    if (!old) return;
    const nn = await uiPrompt(`武器「${old}」改名（只改文件名，不改扩展名）：`, old, "改名");
    if (!nn) return;
    const clean = String(nn).trim();
    if (!clean || clean === old) return;
    try {
      const r = await getBridge().apiPost("weapons/pool/rename", { old, new: clean });
      if (r && r.error) throw new Error(r.error);
      toast("已改名", "ok"); await loadPool();
    } catch (e) { toast("改名失败: " + e.message, "bad"); }
  }));
  box.querySelectorAll("[data-pool-rar]").forEach(sel=>sel.addEventListener("change", async(e)=>{
    const [rar, name] = _poolKey(e.target);
    const to = e.target.value;
    if (!name || !to || to === rar) return;
    try {
      const r = await getBridge().apiPost("weapons/pool/move", { name, to });
      if (r && r.error) throw new Error(r.error);
      toast(`已移入 ${to}`, "ok"); await loadPool();
    } catch (err) { toast("移动失败: " + err.message, "bad"); e.target.value = rar; }
  }));
  box.querySelectorAll("[data-pool-del]").forEach(b=>b.addEventListener("click", async()=>{
    const [, name] = _poolKey(b);
    if (!name) return;
    if (!(await uiConfirm(`确认删除抽奖武器「${name}」？文件将直接删除，即时生效。`, "删除武器"))) return;
    try {
      const r = await getBridge().apiPost("weapons/pool/delete", { name });
      if (r && r.error) throw new Error(r.error);
      toast("已删除", "ok"); await loadPool();
    } catch (e) { toast("删除失败: " + e.message, "bad"); }
  }));
  box.querySelectorAll("[data-pool-atk]").forEach(inp=>inp.addEventListener("input", ()=>{
    const [, name] = _poolKey(inp);
    if (!name) return;
    POOL_ATTRS[name] = POOL_ATTRS[name] || { atk: 0, desc: "" };
    POOL_ATTRS[name].atk = Math.max(0, Number(inp.value) || 0);
    POOL_ATTRS_DIRTY = true;
  }));
  box.querySelectorAll("[data-pool-desc]").forEach(inp=>inp.addEventListener("input", ()=>{
    const [, name] = _poolKey(inp);
    if (!name) return;
    POOL_ATTRS[name] = POOL_ATTRS[name] || { atk: 0, desc: "" };
    POOL_ATTRS[name].desc = inp.value;
    POOL_ATTRS_DIRTY = true;
  }));
  box.querySelectorAll("[data-pool-pick-upload]").forEach(b=>b.addEventListener("click", ()=>{
    const [rar, name] = _poolKey(b);
    if (!name) return;
    const inp = document.createElement("input"); inp.type = "file"; inp.accept = "image/*";
    inp.onchange = async (e) => {
      const file = e.target.files[0]; if (!file) return;
      try {
        const r = await postFile("weapons/pool/upload?rar=" + encodeURIComponent(rar || "SSR") + "&replace=1&name=" + encodeURIComponent(name), {}, file);
        if (r && r.error) throw new Error(r.error);
        toast("已换图", "ok"); await loadPool();
      } catch (err) { toast("换图失败: " + err.message, "bad"); }
    };
    inp.click();
  }));
  box.querySelectorAll("[data-pool-pick-builtin]").forEach(b=>b.addEventListener("click", async ()=>{
    const [rar, name] = _poolKey(b);
    if (!name) return;
    window.SHOP_PICK_TARGET = name; window.SHOP_PICK_KIND = "pool";
    toast("已进入武器图片目录，请单击选中后点确定", "ok");
    document.querySelectorAll(".tabs button").forEach(x=>x.classList.remove("on"));
    const rb=document.querySelector("[data-tab=\"imgs\"]"); if(rb) rb.classList.add("on");
    document.querySelectorAll(".tab").forEach(x=>x.classList.remove("on"));
    const tab=document.getElementById("tab-imgs"); if(tab) tab.classList.add("on");
    await loadImages("data/img/gacha/" + (rar || "SSR"));
    const old=document.getElementById("shopPickTip"); if(old) old.remove();
    const tip=document.createElement("div"); tip.id="shopPickTip"; tip.style="background:var(--accSoft);border:1px solid var(--acc);padding:8px 12px;border-radius:8px;margin-bottom:10px";
    tip.innerHTML=`<b>为武器 "${esc(name)}" 选择内置图：</b> 武器目录 data/img/gacha/${esc(rar || "SSR")}，然后 <button class="ghost sm" id="btnShopPickConfirm">确定绑定</button> <button class="ghost sm" id="btnShopPickCancel">取消</button>`;
    const panel=document.querySelector("#tab-imgs .panel"); if(panel) panel.prepend(tip);
    const backToShops=()=>{
      document.querySelectorAll(".tabs button").forEach(x=>x.classList.remove("on"));
      const cb=document.querySelector("[data-tab=\"shops\"]"); if(cb) cb.classList.add("on");
      document.querySelectorAll(".tab").forEach(x=>x.classList.remove("on"));
      const stab=document.getElementById("tab-shops"); if(stab) stab.classList.add("on");
    };
    document.getElementById("btnShopPickConfirm")?.addEventListener("click", async ()=>{
      const sel=IMG_SELECTED;
      if(!sel){ toast("请先选中图片文件","bad"); return; }
      const ext=(sel.split(".").pop()||"").toLowerCase();
      if(!["png","jpg","jpeg","gif","webp","bmp","ico"].includes(ext)){ toast("请选择图片文件","bad"); return; }
      if(window._imgIsDir && window._imgIsDir(sel)){ toast("不能选择文件夹","bad"); return; }
      try {
        const r = await getBridge().apiPost("weapons/pool/replace_path", { name, src: sel });
        if (r && r.error) throw new Error(r.error);
        toast("已换图", "ok"); tip.remove(); window.SHOP_PICK_TARGET=null; window.SHOP_PICK_KIND=null;
        backToShops(); await loadPool();
      } catch (e) { toast("换图失败: " + e.message, "bad"); }
    });
    document.getElementById("btnShopPickCancel")?.addEventListener("click", ()=>{ tip.remove(); window.SHOP_PICK_TARGET=null; window.SHOP_PICK_KIND=null; backToShops(); });
  }));
  document.getElementById("btnPoolAttrsSave")?.addEventListener("click", () => savePoolAttrs());
  document.getElementById("btnPoolAttrsReset")?.addEventListener("click", () => resetPoolAttrs());
  document.getElementById("btnPoolUploadTop")?.addEventListener("click", ()=>openPoolAddModal("SSR"));
}
async function savePoolAttrs(silent = false) {
  try {
    const clean = {};
    Object.entries(POOL_ATTRS || {}).forEach(([k, v]) => {
      const atk = Math.max(0, Number((v && v.atk) || 0));
      const desc = String((v && v.desc) || "").trim();
      if (atk || desc) clean[k] = { atk, desc };
    });
    const r = await getBridge().apiPost("weapons/pool/attrs", { attrs: clean });
    if (r && r.error) throw new Error(r.error);
    POOL_ATTRS_DIRTY = false;
    if (!silent) { toast("武器属性已保存", "ok"); await loadPool(); }
    return true;
  } catch (e) { if (!silent) toast("保存失败: " + e.message, "bad"); return false; }
}
async function resetPoolAttrs() {
  if (!(await uiConfirm("直接清空全部武器自定义属性（攻击加成/描述）？文件不受影响，旧数据不保留。", "恢复默认"))) return;
  try {
    const r = await getBridge().apiPost("weapons/pool/attrs", { attrs: {}, full: 1 });
    if (r && r.error) throw new Error(r.error);
    POOL_ATTRS = {}; POOL_ATTRS_DIRTY = false;
    toast("已恢复默认", "ok"); await loadPool();
  } catch (e) { toast("恢复失败: " + e.message, "bad"); }
}
function poolUploadTo(rar) {
  openPoolAddModal(rar || "SSR");
}
let _POOL_ADD_FILE = null;
let _POOL_ADD_SRC = "";
function openPoolAddModal(defRar) {
  const modal = document.getElementById("appModal");
  if (!modal) return;
  _POOL_ADD_FILE = null; _POOL_ADD_SRC = "";
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");
  if (icon) icon.textContent = "🎰";
  if (title) title.textContent = "添加武器";
  if (inputWrap) inputWrap.style.display = "none";
  content.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:10px">
      <div style="display:flex;gap:8px">
        <div style="flex:2"><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">武器名（即文件名）：</label>
          <input id="poolAddName" style="width:100%;padding:6px 10px;border-radius:8px" placeholder="如：雷鸣剑"></div>
        <div style="flex:1"><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">稀有度：</label>
          <select id="poolAddRar" style="width:100%;padding:6px 10px;border-radius:8px">${["SSR", "SR", "R"].map((r) => `<option value="${r}"${r === (defRar || "SSR") ? " selected" : ""}>${r}</option>`).join("")}</select></div>
      </div>
      <div style="display:flex;gap:8px">
        <div style="flex:1"><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">攻击加成（默认0）：</label>
          <input id="poolAddAtk" type="number" value="0" style="width:100%;padding:6px 10px;border-radius:8px"></div>
        <div style="flex:2"><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">描述（可选）：</label>
          <input id="poolAddDesc" style="width:100%;padding:6px 10px;border-radius:8px" placeholder="详情页展示"></div>
      </div>
      <div><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">图片：</label>
        <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
          <button class="ghost sm" id="poolAddPickUpload">外置选图（本地上传）</button>
          <button class="ghost sm" id="poolAddPickBuiltin">内置选图（服务器文件）</button>
          <span id="poolAddImgTip" style="font-size:11.5px;color:var(--muted)">未选择</span>
        </div></div>
      <div class="hint">图片必选其一；数值保存后在池行可改；文件即池，添加即时生效</div>
    </div>`;
  const setTip = (t) => { const el = document.getElementById("poolAddImgTip"); if (el) el.textContent = t; };
  document.getElementById("poolAddPickUpload")?.addEventListener("click", () => {
    const inp = document.createElement("input"); inp.type = "file"; inp.accept = "image/*";
    inp.onchange = (e) => {
      const file = e.target.files[0]; if (!file) return;
      _POOL_ADD_FILE = file; _POOL_ADD_SRC = "";
      setTip("本地：" + file.name);
    };
    inp.click();
  });
  document.getElementById("poolAddPickBuiltin")?.addEventListener("click", async () => {
    modal.className = "";
    window.SHOP_PICK_TARGET = "__pooladd__"; window.SHOP_PICK_KIND = "pooladd";
    const _rar0 = (document.getElementById("poolAddRar")?.value || "SSR");
    toast("已进入武器图片目录，请选中后点确定", "ok");
    document.querySelectorAll(".tabs button").forEach(x => x.classList.remove("on"));
    const rb = document.querySelector("[data-tab=\"imgs\"]"); if (rb) rb.classList.add("on");
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("on"));
    const tab = document.getElementById("tab-imgs"); if (tab) tab.classList.add("on");
    await loadImages("data/img/gacha/" + _rar0);
    const old = document.getElementById("shopPickTip"); if (old) old.remove();
    const tip = document.createElement("div"); tip.id = "shopPickTip"; tip.style = "background:var(--accSoft);border:1px solid var(--acc);padding:8px 12px;border-radius:8px;margin-bottom:10px";
    tip.innerHTML = `<b>为新武器选择内置图：</b> 武器目录 data/img/gacha/${_rar0}，然后 <button class="ghost sm" id="btnShopPickConfirm">确定绑定</button> <button class="ghost sm" id="btnShopPickCancel">取消</button>`;
    const panel = document.querySelector("#tab-imgs .panel"); if (panel) panel.prepend(tip);
    const backToModal = () => {
      tip.remove(); window.SHOP_PICK_TARGET = null; window.SHOP_PICK_KIND = null;
      modal.className = "show";
    };
    document.getElementById("btnShopPickConfirm")?.addEventListener("click", () => {
      const sel = IMG_SELECTED;
      if (!sel) { toast("请先选中图片文件", "bad"); return; }
      const ext = (sel.split(".").pop() || "").toLowerCase();
      if (!["png", "jpg", "jpeg", "gif", "webp", "bmp", "ico"].includes(ext)) { toast("请选择图片文件", "bad"); return; }
      if (window._imgIsDir && window._imgIsDir(sel)) { toast("不能选择文件夹", "bad"); return; }
      _POOL_ADD_FILE = null; _POOL_ADD_SRC = sel;
      backToModal(); setTip("内置：" + sel);
    });
    document.getElementById("btnShopPickCancel")?.addEventListener("click", () => { backToModal(); });
  });
  if (cancelBtn) {
    cancelBtn.style.display = "";
    cancelBtn.textContent = "取消";
    cancelBtn.onclick = () => { modal.className = ""; };
  }
  if (okBtn) {
    okBtn.textContent = "确定添加";
    okBtn.style.background = "var(--acc)";
    okBtn.style.borderColor = "transparent";
    okBtn.onclick = async () => {
      const n = (document.getElementById("poolAddName")?.value || "").trim();
      const rar = (document.getElementById("poolAddRar")?.value || "SSR");
      const atk = Math.max(0, Number(document.getElementById("poolAddAtk")?.value) || 0);
      const desc = (document.getElementById("poolAddDesc")?.value || "").trim();
      if (!n) { toast("请填写武器名称", "bad"); return; }
      try {
        if (_POOL_ADD_FILE) {
          const r = await postFile("weapons/pool/upload?rar=" + encodeURIComponent(rar) + "&name=" + encodeURIComponent(n), {}, _POOL_ADD_FILE);
          if (r && r.error) throw new Error(r.error);
        } else if (_POOL_ADD_SRC) {
          const r = await getBridge().apiPost("weapons/pool/replace_path", { rar, name: n, src: _POOL_ADD_SRC });
          if (r && r.error) throw new Error(r.error);
        } else { toast("请先选一张图片", "bad"); return; }
        if (atk || desc) {
          const r2 = await getBridge().apiPost("weapons/pool/attrs", { attrs: { [n]: { atk, desc } } });
          if (r2 && r2.error) throw new Error(r2.error);
        }
        modal.className = "";
        toast("已添加", "ok"); await loadPool();
      } catch (e) { toast("添加失败: " + e.message, "bad"); }
    };
  }
  modal.className = "show";
  setTimeout(() => { try { document.getElementById("poolAddName")?.focus(); } catch (e) {} }, 50);
}
function parseShopRide(raw) {
  // 兼容旧调用：只返回数据对象
  return _parseShopInput(raw, _normRideObj).data;
}
function syncShopRaw() {
  try {
    const el = document.getElementById("shopRide");
    if (el) {
      el.value = JSON.stringify(SHOP_RIDE, null, 2);
      // 只读镜像：手工改 JSON 不回读，以内存态为准，避免静默丢弃
      el.readOnly = true;
      el.title = "只读镜像，以上方卡片编辑+保存为准";
    }
  } catch (e) {}
}
function renderShopRideBox(forceOpen = false) {
  const box = document.getElementById("shopRideBox");
  if (!box) return;
  const entries = Object.entries(SHOP_RIDE);
  // 默认收起；若用户已手动展开或发生增删改，则保持展开
  const curDetails = box.querySelector("details");
  const wasOpen = curDetails ? curDetails.open : forceOpen;
  let html = `<details class="panel" style="margin:0"${wasOpen ? " open" : ""}><summary style="cursor:pointer;font-weight:600">🐴 坐骑商城 — ${entries.length} 件</summary>`;
  html += `<div class="hint" style="margin-top:8px">每行一个坐骑，支持改名、改价、删、绑图（图片路径如 data/img/rides/企鹅.jpg，留空自动匹配）</div>`;
  html += `<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap"><button class="ghost sm" id="btnRideAddTop">＋ 添加坐骑</button><button class="ghost sm" id="btnRideSaveTop">💾 保存坐骑</button><button class="ghost sm" id="btnRideReset">↩️ 恢复默认</button><button class="ghost sm" data-shopsec-up="ride" title="上移">↑</button><button class="ghost sm" data-shopsec-down="ride" title="下移">↓</button></div>`;
  if (!entries.length) {
    html += `<div class="hint" style="margin:8px 0">当前为空，运行时使用内置坐骑（${Object.keys(DEFAULT_RIDE_SHOP).length} 种）；可添加或恢复默认</div>`;
  }
  entries.forEach(([name, val]) => {
    let price = 0, img = "";
    if (val && typeof val === "object" && !Array.isArray(val)) { price = val.price ?? 0; img = val.img ?? ""; }
    else price = Number(val) || 0;
    // 自动匹配坐骑图片：自定义优先，否则按名称匹配 rides 目录
    let autoImg = "";
    if (!img) { try { autoImg = `data/img/rides/${name}.jpg`; } catch (e) { autoImg = ""; } }
    const showImg = img || autoImg;
    html += `<div class="s-fields" data-ride-item="${esc(name)}" style="margin-top:8px">` +
      `<div class="s-row"><small>坐骑名</small><input data-ride-name value="${esc(name)}"></div>` +
      `<div class="s-row"><small>价格</small><input type="number" data-ride-price value="${esc(price)}" style="width:90px"></div>` +
      `<div class="s-row" style="flex:1"><small>图片路径</small><input data-ride-img value="${esc(img)}" placeholder="data/img/..."></div>` +
      `<div style="display:flex;gap:4px;align-items:center;flex-wrap:wrap">${showImg ? `<button class="ghost sm" data-ride-view="${esc(showImg)}">浏览图片</button>` : `<span style="color:var(--muted);font-size:11px">无图</span>`}<button class="ghost sm" data-ride-pick="${esc(name)}">外置选图</button><button class="ghost sm" data-ride-pick-builtin="${esc(name)}">内置选图</button><button class="s-del" data-ride-del="${esc(name)}">删除</button></div>` +
      `</div>`;
  });
  html += `</details>`;
  box.innerHTML = html;
  box.querySelectorAll("[data-ride-name]").forEach(inp => inp.addEventListener("change", (e) => {
    const old = e.target.closest("[data-ride-item]").dataset.rideItem;
    const nn = e.target.value.trim();
    if (!nn || nn === old) { e.target.value = old; return; }
    if (SHOP_RIDE[nn] !== undefined) { toast("已存在同名", "bad"); e.target.value = old; return; }
    SHOP_RIDE[nn] = SHOP_RIDE[old]; delete SHOP_RIDE[old]; SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true);
  }));
  box.querySelectorAll("[data-ride-price]").forEach(inp => inp.addEventListener("change", (e) => {
    const k = e.target.closest("[data-ride-item]").dataset.rideItem;
    const v = SHOP_RIDE[k];
    const p = Number(e.target.value) || 0;
    if (v && typeof v === "object") SHOP_RIDE[k].price = p; else SHOP_RIDE[k] = p;
    SHOP_DIRTY=true; syncShopRaw();
  }));
  box.querySelectorAll("[data-ride-img]").forEach(inp => inp.addEventListener("change", (e) => {
    const k = e.target.closest("[data-ride-item]").dataset.rideItem;
    const v = SHOP_RIDE[k];
    const img = e.target.value.trim();
    if (v && typeof v === "object") { if (img) v.img = img; else { const p = v.price; SHOP_RIDE[k] = p; } }
    else { if (img) SHOP_RIDE[k] = { price: Number(v)||0, img }; }
    SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true);
  }));
  box.querySelectorAll("[data-ride-del]").forEach(b => b.addEventListener("click", async () => {
    const k = b.dataset.rideDel;
    const _last = Object.keys(SHOP_RIDE).length <= 1;
    if (!(await uiConfirm("确认删除坐骑 \"" + k + "\"？（需点击「保存坐骑」生效）" + (_last ? "\n\n注意：这是最后一只，删光后运行时自动使用内置坐骑。" : ""), "删除坐骑"))) return;
    delete SHOP_RIDE[k];
    SHOP_DIRTY = true;
    syncShopRaw();
    renderShopRideBox(true);
    toast("已删除坐骑，请点击「保存坐骑」持久化", "ok");
  }));
  box.querySelectorAll("[data-ride-pick-builtin]").forEach(b=> b.addEventListener("click", async ()=>{
    const k=b.dataset.ridePickBuiltin;
    // 跳转到坐骑目录让用户选择后点确定绑定（仅图片）
    window.SHOP_PICK_TARGET = k;
    toast("已进入坐骑图片目录，请单击选中后点“确定绑定”","ok");
    // 切换到根目录页并加载坐骑目录
    document.querySelectorAll(".tabs button").forEach(x=>x.classList.remove("on"));
    const rb=document.querySelector("[data-tab=\"imgs\"]"); if(rb) rb.classList.add("on");
    document.querySelectorAll(".tab").forEach(x=>x.classList.remove("on"));
    const tab=document.getElementById("tab-imgs"); if(tab) tab.classList.add("on");
    await loadImages("data/img/rides");
    // 在根目录顶部显示绑定提示（仅图片可选）
    const _oldTip = document.getElementById("shopPickTip"); if (_oldTip) _oldTip.remove();
    const tip=document.createElement("div"); tip.id="shopPickTip"; tip.style="background:var(--accSoft);border:1px solid var(--acc);padding:8px 12px;border-radius:8px;margin-bottom:10px";
    tip.innerHTML=`<b>为坐骑 "${esc(k)}" 选择内置图：</b> 坐骑目录 data/img/rides（png/jpg/gif等），然后 <button class="ghost sm" id="btnShopPickConfirm">确定绑定</button> <button class="ghost sm" id="btnShopPickCancel">取消</button>`;
    const panel=document.querySelector("#tab-imgs .panel"); if(panel) panel.prepend(tip);
    document.getElementById("btnShopPickConfirm")?.addEventListener("click", ()=>{
      const sel=IMG_SELECTED;
      if(!sel){ toast("请先选中图片文件","bad"); return; }
      const ext=(sel.split(".").pop()||"").toLowerCase();
      if(!["png","jpg","jpeg","gif","webp","bmp","ico"].includes(ext)){ toast("请选择图片文件（png/jpg/jpeg/gif/webp/bmp/ico），当前选择非图片","bad"); return; }
      // 校验是否为文件夹（无扩展名或在 dirs 中）
      if(window._imgIsDir && window._imgIsDir(sel)){ toast("请选择图片文件，不能选择文件夹","bad"); return; }
      const v=SHOP_RIDE[k];
      if(v && typeof v==="object") SHOP_RIDE[k].img=sel; else SHOP_RIDE[k]={price:Number(v)||0, img:sel};
      SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true); toast("已绑定 "+sel+"，需保存","ok");
      tip.remove(); window.SHOP_PICK_TARGET=null;
      // 切回商城页
      document.querySelectorAll(".tabs button").forEach(x=>x.classList.remove("on"));
      const cb=document.querySelector("[data-tab=\"shops\"]"); if(cb) cb.classList.add("on");
      document.querySelectorAll(".tab").forEach(x=>x.classList.remove("on"));
      const stab=document.getElementById("tab-shops"); if(stab) stab.classList.add("on");
    });
    document.getElementById("btnShopPickCancel")?.addEventListener("click", ()=>{ tip.remove(); window.SHOP_PICK_TARGET=null; });
  }));
  box.querySelectorAll("[data-ride-pick]").forEach(b => b.addEventListener("click", async () => {
    const k = b.dataset.ridePick;
    const inp = document.createElement("input"); inp.type="file"; inp.accept="image/*";
    inp.onchange = async (e) => {
      const file = e.target.files[0]; if (!file) return;
      try {
        const r = await postFile("images/upload?dir=" + encodeURIComponent("data/img/rides"), {}, file);
        if (r && r.error) throw new Error(r.error);
        const path = (r && (r.path || (r.data && r.data.path))) || ("data/img/rides/" + file.name);
        SHOP_RIDE[k] = (typeof SHOP_RIDE[k]==="object"? {...SHOP_RIDE[k], img: path} : {price: Number(SHOP_RIDE[k])||0, img: path}); SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true); toast("图片已上传并绑定，需保存","ok");
      } catch(err){ toast("上传失败:"+(err.message||err),"bad");}
    };
    inp.click();
  }));
  box.querySelectorAll("[data-ride-view]").forEach((b) => b.addEventListener("click", async () => {
    const p = b.dataset.rideView;
    if (!p) return;
    try {
      const r = await getBridge().apiPost("images/thumb", { path: p });
      const thumb = r && (r.thumb || (r.data && r.data.thumb));
      if (r && r.error) throw new Error(r.error);
      if (thumb) showLightbox(thumb, p.split("/").pop());
      else toast("无预览", "bad");
    } catch (err) { toast("预览失败:" + (err.message || err), "bad"); }
  }));
  const addBtn = document.getElementById("btnRideAddTop");
  if (addBtn) addBtn.addEventListener("click", () => openRideAddModal());
  const rideSaveBtn = document.getElementById("btnRideSaveTop");
  if (rideSaveBtn) rideSaveBtn.addEventListener("click", () => saveRideOnly());
  const resetBtn = document.getElementById("btnRideReset");
  if (resetBtn) resetBtn.addEventListener("click", async () => {
    if (!(await uiConfirm("直接恢复坐骑商城为内置默认？旧数据不保留。", "恢复默认"))) return;
    try {
      SHOP_RIDE = JSON.parse(JSON.stringify(DEFAULT_RIDE_SHOP));
      const cleanRide = {};
      Object.entries(SHOP_RIDE).forEach(([k, v]) => {
        if (v && typeof v === "object" && !Array.isArray(v)) {
          if (!v.img) cleanRide[k] = v.price;
          else cleanRide[k] = v;
        } else cleanRide[k] = v;
      });
      await getBridge().apiPost("config/save", { "商城图鉴": { "ride_shop": JSON.stringify(cleanRide) } });
      SHOP_DIRTY = false; SHOP_RIDE_CUSTOM = true;
      syncShopRaw(); renderShopRideBox(true);
      toast("已恢复默认", "ok");
    } catch (e) { toast("恢复失败: " + e.message, "bad"); }
  });
}
// 添加坐骑表单窗：名称 + 价格 + 图片路径一次填完
function openRideAddModal() {
  const modal = document.getElementById("appModal");
  if (!modal) return;
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");
  if (icon) icon.textContent = "🐴";
  if (title) title.textContent = "添加坐骑";
  if (inputWrap) inputWrap.style.display = "none";
  content.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:10px">
      <div><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">坐骑名称：</label>
        <input id="rideAddName" style="width:100%;padding:6px 10px;border-radius:8px" placeholder="如：汗血宝马"></div>
      <div><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">价格：</label>
        <input id="rideAddPrice" type="number" value="500000" style="width:100%;padding:6px 10px;border-radius:8px"></div>
      <div><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">图片（坐骑目录 data/img/rides，可选，留空自动匹配）：</label>
        <input id="rideAddImg" style="width:100%;padding:6px 10px;border-radius:8px" placeholder="data/img/rides/xxx.jpg">
        <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap"><button class="ghost sm" id="rideAddPickUpload">外置选图（本地上传）</button><button class="ghost sm" id="rideAddPickBuiltin">内置选图（坐骑目录）</button><button class="ghost sm" id="rideAddPreview">浏览图片</button><span id="rideAddImgTip" style="font-size:11.5px;color:var(--muted)">未选择</span></div></div>
      <div class="hint">保存后记得点「保存坐骑」持久化；图片也可在列表中用“外置选图/内置选图”绑定</div>
    </div>`;
  let _RIDE_ADD_FILE = null;
  const _rideSetTip = (t) => { const el = document.getElementById("rideAddImgTip"); if (el) el.textContent = t; };
  document.getElementById("rideAddPickUpload")?.addEventListener("click", () => {
    const inp = document.createElement("input"); inp.type = "file"; inp.accept = "image/*";
    inp.onchange = async (e) => {
      const file = e.target.files[0]; if (!file) return;
      try {
        const r = await postFile("images/upload?dir=" + encodeURIComponent("data/img/rides"), {}, file);
        if (r && r.error) throw new Error(r.error);
        const path = (r && (r.path || (r.data && r.data.path))) || ("data/img/rides/" + file.name);
        _RIDE_ADD_FILE = null;
        const ie = document.getElementById("rideAddImg");
        if (ie) ie.value = path;
        _rideSetTip("已上传：" + path);
      } catch (err) { toast("上传失败:" + (err.message || err), "bad"); }
    };
    inp.click();
  });
  document.getElementById("rideAddPreview")?.addEventListener("click", async () => {
    const p = (document.getElementById("rideAddImg")?.value || "").trim();
    if (!p) { toast("请先选一张图片", "bad"); return; }
    try {
      const r = await getBridge().apiPost("images/thumb", { path: p });
      const thumb = r && (r.thumb || (r.data && r.data.thumb));
      if (thumb) showLightbox(thumb, p.split("/").pop());
      else toast("无预览", "bad");
    } catch (e) { toast("预览失败:" + e.message, "bad"); }
  });
  document.getElementById("rideAddPickBuiltin")?.addEventListener("click", async () => {
    modal.className = "";
    window.SHOP_PICK_TARGET = "__rideadd__"; window.SHOP_PICK_KIND = "rideadd";
    toast("已进入坐骑图片目录，请单击选中后点确定", "ok");
    document.querySelectorAll(".tabs button").forEach(x => x.classList.remove("on"));
    const rb = document.querySelector("[data-tab=\"imgs\"]"); if (rb) rb.classList.add("on");
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("on"));
    const tab = document.getElementById("tab-imgs"); if (tab) tab.classList.add("on");
    await loadImages("data/img/rides");
    const old = document.getElementById("shopPickTip"); if (old) old.remove();
    const tip = document.createElement("div"); tip.id = "shopPickTip"; tip.style = "background:var(--accSoft);border:1px solid var(--acc);padding:8px 12px;border-radius:8px;margin-bottom:10px";
    tip.innerHTML = `<b>为新坐骑选择内置图：</b> 坐骑目录 data/img/rides，然后 <button class="ghost sm" id="btnShopPickConfirm">确定绑定</button> <button class="ghost sm" id="btnShopPickCancel">取消</button>`;
    const panel = document.querySelector("#tab-imgs .panel"); if (panel) panel.prepend(tip);
    const backToModal = () => {
      tip.remove(); window.SHOP_PICK_TARGET = null; window.SHOP_PICK_KIND = null;
      modal.className = "show";
    };
    document.getElementById("btnShopPickConfirm")?.addEventListener("click", () => {
      const sel = IMG_SELECTED;
      if (!sel) { toast("请先选中图片文件", "bad"); return; }
      const ext = (sel.split(".").pop() || "").toLowerCase();
      if (!["png", "jpg", "jpeg", "gif", "webp", "bmp", "ico"].includes(ext)) { toast("请选择图片文件", "bad"); return; }
      if (window._imgIsDir && window._imgIsDir(sel)) { toast("不能选择文件夹", "bad"); return; }
      backToModal();
      const inp = document.getElementById("rideAddImg");
      if (inp) inp.value = sel;
    });
    document.getElementById("btnShopPickCancel")?.addEventListener("click", () => { backToModal(); });
  });
  if (cancelBtn) {
    cancelBtn.style.display = "";
    cancelBtn.textContent = "取消";
    cancelBtn.onclick = () => { modal.className = ""; };
  }
  if (okBtn) {
    okBtn.textContent = "确定添加";
    okBtn.style.background = "var(--acc)";
    okBtn.style.borderColor = "transparent";
    okBtn.onclick = () => {
      const n = (document.getElementById("rideAddName")?.value || "").trim();
      const p = Number(document.getElementById("rideAddPrice")?.value) || 0;
      const img = (document.getElementById("rideAddImg")?.value || "").trim();
      if (!n) { toast("请填写坐骑名称", "bad"); return; }
      if (SHOP_RIDE[n] !== undefined) { toast("已存在同名坐骑", "bad"); return; }
      SHOP_RIDE[n] = { price: p, img };
      SHOP_DIRTY = true;
      syncShopRaw();
      try { renderShopRideBox(true); } catch (e) {}
      try { renderAtlas(); } catch (e) {}
      modal.className = "";
      toast("已添加坐骑，需保存", "ok");
    };
  }
  modal.className = "show";
  setTimeout(() => { try { document.getElementById("rideAddName")?.focus(); } catch (e) {} }, 50);
}
// 图鉴总览（ATLAS_CUR/renderAtlas）已归 f11_atlas.js 专属；商城只调不用，独立方便各自导出导入与自定义。

async function loadShops(skipAtlas = false) {
  const msg = document.getElementById("shopMsg");
  try {
    const [cur, spiritData] = await Promise.all([
      apiTimeout(getBridge().apiGet("config/get"), 20000, "config/get"),
      SPIRIT ? Promise.resolve(SPIRIT) : apiTimeout(getBridge().apiGet("spirits"), 20000, "spirits").catch(() => null)
    ]);
    if (spiritData) { SPIRIT = spiritData; try { SPIRIT_TS = Date.now(); } catch (e) {} }
    const sec = (cur || {})["商城图鉴"] || {};
    const _rr = _parseShopInput(sec["ride_shop"], _normRideObj);
    if (Object.keys(_rr.data).length) { SHOP_RIDE = _rr.data; SHOP_RIDE_CUSTOM = true; }
    else if (!_rr.blank) { SHOP_RIDE = {}; SHOP_RIDE_CUSTOM = true; }
    else { SHOP_RIDE = JSON.parse(JSON.stringify(DEFAULT_RIDE_SHOP)); SHOP_RIDE_CUSTOM = false; }
    if (_rr.corrupt) toast("坐骑商城配置损坏，已载入内置，保存将覆盖", "bad");
    try {
      const _so = sec["shop_order"];
      if (typeof _so === "string" && _so.trim()) {
        try {
          const d = JSON.parse(_so);
          if (Array.isArray(d) && d.length === 3 && ["ride", "pool", "shop"].every((k) => d.includes(k))) _SHOP_ORDER = d;
        } catch (e) {}
      }
    } catch (e) {}
    try {
      const _te = sec["weapon_order"];
      if (_te && typeof _te === "object" && !Array.isArray(_te)) _POOL_ORDER = { ..._te };
      else if (typeof _te === "string" && _te.trim()) { try { const d = JSON.parse(_te); if (d && typeof d === "object") _POOL_ORDER = d; } catch (e) {} }
    } catch (e) {}
    try {
      const _te = sec["treasure_effects"];
      if (_te && typeof _te === "object" && !Array.isArray(_te)) window._TREAS_EFF = { ..._te };
      else if (typeof _te === "string" && _te.trim()) { try { const d = JSON.parse(_te); if (d && typeof d === "object") window._TREAS_EFF = d; else window._TREAS_EFF = {}; } catch (e) { window._TREAS_EFF = {}; } }
      else window._TREAS_EFF = window._TREAS_EFF || {};
    } catch (e) { window._TREAS_EFF = window._TREAS_EFF || {}; }
    SHOP_DIRTY = false;
    syncShopRaw();
    renderShopRideBox();
    try { renderShop(); } catch (e) {}
    try { await loadPool(true); } catch (e) {}
    if (!skipAtlas) { try { renderAtlas(cur); } catch (e) {} }
    try { applyShopOrder(); } catch (e) {}
    if (msg) { msg.textContent = ""; msg.classList.remove("ok", "bad"); }
  } catch (e) {
    if (msg) { msg.textContent = "加载失败: " + e.message; msg.classList.add("bad"); }
  }
}
let _SHOP_ORDER = null; // ["ride","pool","shop"] | null=默认顺序
function applyShopOrder() {
  // 按 shop_order 重排商城三栏容器（只动 DOM 顺序，不碰数据）
  try {
    const order = (_SHOP_ORDER && _SHOP_ORDER.length === 3 &&
      ["ride", "pool", "shop"].every((k) => _SHOP_ORDER.includes(k))) ? _SHOP_ORDER : ["ride", "pool", "shop"];
    const parent = document.querySelector("#tab-shops .responsive-shop-grid > div");
    const map = { ride: document.getElementById("shopRideBox"), pool: document.getElementById("poolWeaponBox"), shop: document.getElementById("shopSpiritBox") };
    if (!parent || !map.ride || !map.pool || !map.shop) return;
    order.forEach((k, i) => {
      if (map[k]) {
        parent.appendChild(map[k]);
        map[k].style.marginTop = i === 0 ? "0" : "10px";
      }
    });
  } catch (e) {}
}
async function moveShopSection(key, dir) {
  const order = ((_SHOP_ORDER && _SHOP_ORDER.length === 3) ? [..._SHOP_ORDER] : ["ride", "pool", "shop"]);
  const i = order.indexOf(key), j = i + dir;
  if (i < 0 || j < 0 || j >= order.length) return;
  const t = order[i]; order[i] = order[j]; order[j] = t;
  _SHOP_ORDER = order;
  applyShopOrder();
  try {
    const r = await getBridge().apiPost("config/save", { "商城图鉴": { "shop_order": JSON.stringify(order) } });
    if (r && r.error) throw new Error(r.error);
    try { if (CFG && CFG.cur && CFG.cur["商城图鉴"]) CFG.cur["商城图鉴"]["shop_order"] = JSON.stringify(order); } catch (e) {}
    toast("商城排序已保存", "ok");
  } catch (e) { toast("排序保存失败: " + e.message, "bad"); }
}
function bindShopOrderOnce() {
  if (document.body.dataset.shopOrderBound) return;
  document.body.dataset.shopOrderBound = "1";
  document.addEventListener("click", (e) => {
    const t = e.target && e.target.closest ? e.target : null;
    if (!t) return;
    const up = t.closest("[data-shopsec-up]");
    const dn = t.closest("[data-shopsec-down]");
    if (!up && !dn) return;
    const key = up ? up.dataset.shopsecUp : dn.dataset.shopsecDown;
    if (key) moveShopSection(key, up ? -1 : 1);
  });
}
async function saveRideOnly(silent = false) {
  // 坐骑单独保存：只写 商城图鉴.ride_shop，不碰武器/精灵/宝物
  const msg = document.getElementById("shopMsg");
  try {
    const cleanRide = {};
    Object.entries(SHOP_RIDE).forEach(([k, v]) => {
      if (v && typeof v === "object" && !Array.isArray(v)) {
        if (!v.img) cleanRide[k] = v.price;
        else cleanRide[k] = v;
      } else cleanRide[k] = v;
    });
    await getBridge().apiPost("config/save", { "商城图鉴": { "ride_shop": JSON.stringify(cleanRide) } });
    SHOP_DIRTY = false;
    SHOP_RIDE_CUSTOM = true;
    syncShopRaw();
    if (!silent) {
      if (msg) { msg.textContent = "坐骑商城已保存"; msg.classList.add("ok"); }
      toast("坐骑商城已保存", "ok");
    }
    return true;
  } catch (e) {
    if (!silent) {
      if (msg) { msg.textContent = "保存失败: " + e.message; msg.classList.add("bad"); }
      toast("保存失败: " + e.message, "bad");
    }
    return false;
  }
}

async function saveShops() {
  // 顶部全部保存：坐骑 + 武器属性 + 精灵道具，各存各的范围，互不串写
  const msg = document.getElementById("shopMsg");
  if (msg) msg.className = "msg";
  const okRide = await saveRideOnly(true);
  const okPool = await savePoolAttrs(true);
  const okShop = await saveSpiritKind("shop", true);
  const bad = [];
  if (!okRide) bad.push("坐骑");
  if (!okPool) bad.push("武器属性");
  if (!okShop) bad.push("精灵道具");
  if (!bad.length) {
    if (msg) { msg.textContent = "商城已全部保存（坐骑/武器属性/精灵道具）"; msg.classList.add("ok"); }
    toast("商城已全部保存（坐骑/武器属性/精灵道具）", "ok");
  } else {
    if (msg) { msg.textContent = "部分保存失败：" + bad.join("、"); msg.classList.add("bad"); }
    toast("部分保存失败：" + bad.join("、"), "bad");
  }
}

async function exportShops() {
  // 商城全量导出：坐骑 + 武器属性/顺序 + 武器清单 + 精灵道具；走统一导出通道（自动下载+弹窗手动兜底）
  // 注意：武器图片二进制不在内，导入时缺图跳过并提示（属性会留待传图后生效）
  try {
    const cur = await getBridge().apiGet("config/get");
    const sec = (cur || {})["商城图鉴"] || {};
    const pool = [];
    try {
      ["SSR", "SR", "R"].forEach((rar) => ((POOL_WEAPONS && POOL_WEAPONS[rar]) || []).forEach((it) => {
        pool.push({ rar, name: it.name, attrs: (POOL_ATTRS && POOL_ATTRS[it.name]) || { atk: 0, desc: "" } });
      }));
    } catch (e) {}
    let spiritShop = {};
    try { spiritShop = (SPIRIT && SPIRIT.shop) || {}; } catch (e) {}
    const payload = {
      app: "astrbot_plugin_xbbot_beta", kind: "shop", version: 1,
      ride_shop: sec["ride_shop"] || "",
      weapon_attrs: sec["weapon_attrs"] || "",
      weapon_order: sec["weapon_order"] || "",
      spirit_shop: spiritShop,
      pool: pool
    };
    triggerExportResult({ filename: `xbbot_shop_${Date.now()}.json`, mime: "application/json;charset=utf-8", rawText: JSON.stringify(payload, null, 2) });
    toast("商城已导出", "ok");
  } catch (e) { toast("导出失败: " + e.message, "bad"); }
}
async function importShops() {
  const inp = document.createElement("input"); inp.type = "file"; inp.accept = ".json,application/json";
  inp.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const txt = await file.text(); const data = JSON.parse(txt);
      const done = [], failed = [];
      // 新格式：全量商城包
      if (data && (data.kind === "shop" || data.spirit_shop !== undefined || data.weapon_attrs !== undefined || Array.isArray(data.pool))) {
        if (data.ride_shop !== undefined) {
          const r = await getBridge().apiPost("config/save", { "商城图鉴": { "ride_shop": data.ride_shop } });
          if (r && r.error) throw new Error(r.error);
          done.push("坐骑");
        }
        if (data.weapon_attrs !== undefined) {
          let _attrs = data.weapon_attrs;
          if (typeof _attrs === "string" && _attrs.trim()) { try { _attrs = JSON.parse(_attrs); } catch (err) { _attrs = null; } }
          if (_attrs && typeof _attrs === "object") {
            const r = await getBridge().apiPost("weapons/pool/attrs", { attrs: _attrs, full: 1 });
            if (r && r.error) throw new Error(r.error);
            done.push("武器属性");
          }
        }
        if (data.weapon_order !== undefined) {
          const r = await getBridge().apiPost("config/save", { "商城图鉴": { "weapon_order": data.weapon_order } });
          if (r && r.error) throw new Error(r.error);
          done.push("武器顺序");
        }
        if (data.spirit_shop && typeof data.spirit_shop === "object") {
          const r = await getBridge().apiPost("spirits/save", { shop: data.spirit_shop });
          if (r && r.error) throw new Error(r.error);
          done.push("精灵道具");
        }
        if (Array.isArray(data.pool) && data.pool.length) {
          const have = new Set();
          try { ["SSR", "SR", "R"].forEach((rar) => ((POOL_WEAPONS && POOL_WEAPONS[rar]) || []).forEach((it) => have.add(rar + "|" + it.name))); } catch (err) {}
          const missing = data.pool.filter((p) => p && p.name && !have.has((p.rar || "") + "|" + p.name)).length;
          if (missing) failed.push(missing + "个武器图片缺失已跳过（属性已恢复，传图后生效）");
        }
        if (!done.length && !failed.length) throw new Error("文件中无有效数据");
        toast("商城已导入" + (done.length ? "：" + done.join("、") : "") + (failed.length ? "；" + failed.join("；") : ""), done.length ? "ok" : "bad");
        await loadShops();
        return;
      }
      // 兼容旧格式 {商城图鉴: {...}} / 直接 {ride_shop: "..."} / 裸商城JSON（仅坐骑）
      let sec = {};
      if (data["商城图鉴"]) sec = data["商城图鉴"];
      else if (data["ride_shop"] !== undefined) sec = data;
      else sec = data;
      const payload = {};
      if (sec["ride_shop"] !== undefined) payload["ride_shop"] = sec["ride_shop"];
      if (!Object.keys(payload).length) {
        // 可能是直接的 ride_shop 内容
        const keys = Object.keys(sec);
        if (keys.length) payload["ride_shop"] = JSON.stringify(sec);
        else throw new Error("未找到 ride_shop 数据");
      }
      await getBridge().apiPost("config/save", { "商城图鉴": payload });
      toast("商城已导入", "ok"); await loadShops();
    } catch (err) { toast("导入失败: " + err.message, "bad"); }
    // 注：本函数尾（}; inp.click(); }＋商城四按钮绑定）在 f13 头逐行续接，跨文件断句是 load-bearing，禁动。
  }; inp.click();
}
document.getElementById("btnShopLoad")?.addEventListener("click", loadShops);
document.getElementById("btnShopSave")?.addEventListener("click", saveShops);
document.getElementById("btnShopExport")?.addEventListener("click", exportShops);
document.getElementById("btnShopImport")?.addEventListener("click", importShops);
// ---------- 奴隶系统用户视图 ----------
let RAW_SLAVE_USERS = [];
async function loadSlaveUsers(){
  try{
    RAW_SLAVE_USERS = await getBridge().apiGet("slave/users");
    renderSlaveTable();
  }catch(e){ err("slave users: "+e.message); }
}

function renderSlaveTable() {
  const body = document.getElementById("slaveBody");
  if (!body) return;
  const q2 = (document.getElementById("slaveSearch")?.value || "").trim().toLowerCase();
  let rows = [...RAW_SLAVE_USERS];
  if (q2) {
    rows = rows.filter(r => (String(r.qq) + String(r.name || "") + String(r.owner || "") + String(r.gid || "")).toLowerCase().includes(q2));
  }
  const sortMode = document.getElementById("slaveSort")?.value || "price_desc";
  if (sortMode === "price_desc") rows.sort((a, b) => (b.price || 0) - (a.price || 0));
  else if (sortMode === "price_asc") rows.sort((a, b) => (a.price || 0) - (b.price || 0));
  else if (sortMode === "slaves_desc") rows.sort((a, b) => (b.slaves || 0) - (a.slaves || 0));
  else if (sortMode === "slaves_asc") rows.sort((a, b) => (a.slaves || 0) - (b.slaves || 0));
  else if (sortMode === "qq_asc") rows.sort((a, b) => String(a.qq).localeCompare(String(b.qq)));
  else if (sortMode === "qq_desc") rows.sort((a, b) => String(b.qq).localeCompare(String(a.qq)));

  const sHint = document.getElementById("slaveHint");
  if (sHint) {
    sHint.innerHTML = `共 <strong>${RAW_SLAVE_USERS.length}</strong> 条奴隶档案（当前匹配 <strong>${rows.length}</strong> 条） · 实时展示身价与主奴武装关系`;
  }
  let html = "";
  if (!rows.length) html = `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--muted)">暂无奴隶数据</td></tr>`;
  else html = rows.map(r => `<tr>
    <td><span class="badge badge-primary">${esc(r.gid)}</span></td>
    <td><strong>${esc(r.qq)}</strong></td>
    <td>${esc(r.name||"")}</td>
    <td>${r.owner ? `<span class="badge badge-purple">${esc(r.owner)}</span>` : '<span style="color:var(--muted)">自由身</span>'}</td>
    <td><span style="font-weight:700;color:var(--text)">${(r.price || 0).toLocaleString()}</span></td>
    <td><span class="badge badge-primary">${r.slaves || 0} 人</span></td>
    <td>${r.protect ? `<span class="badge badge-success">${esc(r.protect)}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
    <td>${r.weapons ? `<span class="badge badge-warn">${esc((r.weapons||"").slice(0,30))}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
  </tr>`).join("");
  body.innerHTML = html;
}

// ---------- 精灵系统用户视图 ----------
let RAW_SPIRIT_USERS = [];
async function loadSpiritUsers(){
  try{
    RAW_SPIRIT_USERS = await getBridge().apiGet("spirit/users");
    renderSpiritUsersTable();
  }catch(e){ err("spirit users: "+e.message); }
}

function renderSpiritUsersTable() {
  const body = document.getElementById("spiritUsersBody");
  if (!body) return;
  const q2 = (document.getElementById("spiritUserSearch")?.value || "").trim().toLowerCase();
  let rows = [...RAW_SPIRIT_USERS];
  if (q2) {
    rows = rows.filter(r => (String(r.qq) + String(r.name || "") + String(r.active || "") + String(r.best || "") + String(r.gid || "")).toLowerCase().includes(q2));
  }
  const sortMode = document.getElementById("spiritUserSort")?.value || "power_desc";
  if (sortMode === "power_desc") rows.sort((a, b) => (b.total_power || 0) - (a.total_power || 0));
  else if (sortMode === "power_asc") rows.sort((a, b) => (a.total_power || 0) - (b.total_power || 0));
  else if (sortMode === "level_desc") rows.sort((a, b) => (b.max_level || 0) - (a.max_level || 0));
  else if (sortMode === "level_asc") rows.sort((a, b) => (a.max_level || 0) - (b.max_level || 0));
  else if (sortMode === "count_desc") rows.sort((a, b) => (b.count || 0) - (a.count || 0));
  else if (sortMode === "count_asc") rows.sort((a, b) => (a.count || 0) - (b.count || 0));
  else if (sortMode === "qq_asc") rows.sort((a, b) => String(a.qq).localeCompare(String(b.qq)));
  else if (sortMode === "qq_desc") rows.sort((a, b) => String(b.qq).localeCompare(String(a.qq)));

  const spHint = document.getElementById("spiritUsersHint");
  if (spHint) {
    spHint.innerHTML = `共 <strong>${RAW_SPIRIT_USERS.length}</strong> 名训练师（当前匹配 <strong>${rows.length}</strong> 名） · 实时统计出战宝可梦与综合战力`;
  }
  let html = "";
  if (!rows.length) html = `<tr><td colspan="9" style="text-align:center;padding:24px;color:var(--muted)">暂无精灵数据</td></tr>`;
  else html = rows.map(r => `<tr>
    <td><span class="badge badge-primary">${esc(r.gid)}</span></td>
    <td><strong>${esc(r.qq)}</strong></td>
    <td>${esc(r.name||"")}</td>
    <td><span class="badge badge-primary">${r.count || 0} 只</span></td>
    <td>${r.active ? `<span class="badge badge-success">${esc(r.active)}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
    <td>${r.best ? `<span class="badge badge-purple">${esc(r.best)}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
    <td><span class="badge badge-warn">Lv.${r.max_level || 0}</span></td>
    <td><span style="font-weight:700;color:var(--text)">${(r.total_power || 0).toLocaleString()}</span></td>
    <td><span class="badge badge-primary">${r.bag_count || 0} 件</span></td>
  </tr>`).join("");
  body.innerHTML = html;
}
// 备份（文件夹式，与图片库一致）
let BACKUP_DIR = "";
let BACKUP_CACHE = null;
async function loadBackups(dir="") {
  try {
    BACKUP_DIR = dir || "";
    const d = await getBridge().apiGet("backups/list", BACKUP_DIR ? { dir: BACKUP_DIR } : {});
    BACKUP_CACHE = d;
    const crumbs = (d.dir || "").split("/").filter(Boolean);
    let crumb = `<a data-bkcrumb="">根目录</a>`;
    let acc = "";
    crumbs.forEach((s) => {
      acc += (acc ? "/" : "") + s;
      crumb += ` / <a data-bkcrumb="${esc(acc)}">${esc(s)}</a>`;
    });
    document.getElementById("backupCrumbs").innerHTML = `<span class="crumbs">${crumb}</span>`;
    document.querySelectorAll("#backupCrumbs a[data-bkcrumb]").forEach((a) => a.addEventListener("click", () => loadBackups(a.dataset.bkcrumb)));
    renderBackups(d);
  } catch (e) { err("backups: " + e.message); }
}
function renderBackups(d, _q) {
  const box = document.getElementById("backupBrowser");
  const q = (typeof _q === "string" ? _q : (document.getElementById("backupSearch")?.value || "")).trim().toLowerCase();
  if (typeof window.BACKUP_SELECTED === 'undefined') window.BACKUP_SELECTED = "";
  let html = `<div class="bk-list">`;
  (d.dirs || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    const selCls = window.BACKUP_SELECTED === x.path ? ' selected' : '';
    html += `<div class="bk-item${selCls}" data-bkdir="${esc(x.path)}" data-bksel="${esc(x.path)}">
      <div class="bk-icon">📁</div>
      <div class="bk-info">
        <div class="bk-name">${esc(x.name)}</div>
        <div class="bk-meta"><span>📅 日期目录 (双击进入)</span><span>🕒 ${esc(x.mtime || "")}</span></div>
      </div>
      <button class="ghost sm" style="pointer-events:none">进入 ➔</button>
    </div>`;
  });
  (d.files || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    const selCls = window.BACKUP_SELECTED === x.path ? ' selected' : '';
    html += `<div class="bk-item${selCls}" data-bkfile="${esc(x.path)}" data-bksel="${esc(x.path)}">
      <div class="bk-icon">💾</div>
      <div class="bk-info">
        <div class="bk-name">${esc(x.name)}</div>
        <div class="bk-meta"><span>📦 大小: ${esc(x.size || "0KB")}</span><span>🕒 备份时间: ${esc(x.mtime || "")}</span></div>
      </div>
      <span style="font-size:12px;color:var(--muted)">${selCls ? '✓ 已选中' : '单击选中'}</span>
    </div>`;
  });
  html += `</div>`;
  if (!(d.dirs || []).length && !(d.files || []).length) {
    html = `<div class="hint" style="padding:20px;text-align:center;background:var(--panel2);border-radius:8px">暂无备份文件，系统将每隔设定时间自动备份，您也可点击上方「立即备份」生成。</div>`;
  }
  box.innerHTML = html;
  // 单击选中（高亮），文件夹双击进入
  box.querySelectorAll("[data-bksel]").forEach((el) => {
    el.addEventListener("click", () => {
      window.BACKUP_SELECTED = el.dataset.bksel;
      box.querySelectorAll(".bk-item").forEach(c => c.classList.remove("selected"));
      el.classList.add("selected");
    });
  });
  box.querySelectorAll("[data-bkdir]").forEach((el) => {
    el.addEventListener("dblclick", () => loadBackups(el.dataset.bkdir));
  });
}
// 立即生成本地冷备（带防抖与忙态保护）
document.getElementById("btnBackupNow")?.addEventListener("click", async () => {
  const btn = document.getElementById("btnBackupNow");
  if (btn && btn.disabled) return;
  const origTxt = btn ? btn.textContent : "⚡ 立即备份";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ 正在生成备份...";
  }
  toast("正在打包并生成本地数据冷备...", "ok", 3000);
  try {
    const r = await getBridge().apiPost("backups/restore", { path: "__backup_now__" });
    toast("本地冷备已生成: " + (r && r.path ? r.path : "成功"), "ok", 4000);
    await loadBackups("");
  } catch (e) {
    await loadBackups("");
    toast("备份指令已下发，列表已刷新", "ok", 3000);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origTxt;
    }
  }
});
document.getElementById("btnBackupRefresh")?.addEventListener("click", () => loadBackups(BACKUP_DIR));

// 测试 WebDAV 连接
document.getElementById("btnWebDAVTest")?.addEventListener("click", async () => {
  const btn = document.getElementById("btnWebDAVTest");
  const msgEl = document.getElementById("backupCfgMsg");
  if (btn && btn.disabled) return;
  const origTxt = btn ? btn.textContent : "☁️ 测试 WebDAV";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ 测试连接中...";
  }
  if (msgEl) {
    msgEl.textContent = "正在发起 WebDAV 连接测试...";
    msgEl.className = "msg";
  }
  toast("正在连接测试 WebDAV...", "ok", 4000);
  try {
    const g = (id) => (document.getElementById(id) || {}).value ?? "";
    const payload = {
      url: g("wdUrl").trim(),
      user: g("wdUser").trim(),
      pwd: g("wdPwd"),
      dir: g("wdDir").trim()
    };
    const res = await getBridge().apiPost("backup/webdav/test", payload);
    if (res && res.ok) {
      const succMsg = res.msg || "WebDAV 连接与鉴权成功！";
      if (msgEl) { msgEl.textContent = "✅ " + succMsg; msgEl.className = "msg ok"; }
      toast("WebDAV 测试成功: " + succMsg, "ok", 6000);
      await loadRemoteWebDAVFiles();
    } else {
      const errMsg = (res && res.msg) ? res.msg : ((res && res.error) ? res.error : "未知错误");
      if (msgEl) { msgEl.textContent = "❌ " + errMsg; msgEl.className = "msg bad"; }
      toast("WebDAV 测试失败: " + errMsg, "bad", 8000);
      uiAlert(errMsg, "WebDAV 测试失败", "⚠️");
    }
  } catch (err) {
    const errMsg = err.message || String(err);
    if (msgEl) { msgEl.textContent = "❌ " + errMsg; msgEl.className = "msg bad"; }
    toast("WebDAV 测试异常: " + errMsg, "bad", 8000);
    uiAlert(errMsg, "WebDAV 测试异常", "⚠️");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origTxt;
    }
  }
});

// 立即上传至 WebDAV 云端
document.getElementById("btnWebDAVBackupNow")?.addEventListener("click", async () => {
  const btn = document.getElementById("btnWebDAVBackupNow");
  const msgEl = document.getElementById("backupCfgMsg");
  if (btn && btn.disabled) return;
  const origTxt = btn ? btn.textContent : "☁️ 立即上传云端";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ 正在上传云端...";
  }

  const sel = window.BACKUP_SELECTED || "";
  let payload = {};
  let desc = "本地最新冷备";
  if (sel) {
    const ext = (sel.split(".").pop() || "").toLowerCase();
    if (["db", "json"].includes(ext)) {
      payload.path = sel;
      desc = sel.split("/").pop();
    }
  }
  if (msgEl) {
    msgEl.textContent = `正在打包并上传 [${desc}] 至 WebDAV...`;
    msgEl.className = "msg";
  }
  toast(`正在上传 [${desc}] 至 WebDAV 云端...`, "ok", 4000);

  try {
    const res = await getBridge().apiPost("backup/webdav/upload", payload);
    if (res && res.ok) {
      const succMsg = res.msg || "已成功上传至 WebDAV 远端！";
      if (msgEl) { msgEl.textContent = "✅ " + succMsg; msgEl.className = "msg ok"; }
      toast("WebDAV 云备份成功: " + succMsg, "ok", 6000);
      await loadBackups(BACKUP_DIR);
      await loadRemoteWebDAVFiles();
    } else {
      const errMsg = (res && res.msg) ? res.msg : "未能完成上传";
      if (msgEl) { msgEl.textContent = "❌ " + errMsg; msgEl.className = "msg bad"; }
      toast("WebDAV 上传失败: " + errMsg, "bad", 8000);
      uiAlert(errMsg, "WebDAV 上传失败", "⚠️");
    }
  } catch (err) {
    const errMsg = err.message || String(err);
    if (msgEl) { msgEl.textContent = "❌ " + errMsg; msgEl.className = "msg bad"; }
    toast("WebDAV 上传异常: " + errMsg, "bad", 8000);
    uiAlert(errMsg, "WebDAV 上传异常", "⚠️");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origTxt;
    }
  }
});

// 格式化为中国上海时区 (UTC+8) 中文日期时间
function formatShanghaiDate(mtimeStr, fileName) {
  const s = String(mtimeStr || "").trim();
  if (s && s.includes("年") && s.includes("月")) {
    return s;
  }
  if (s) {
    try {
      const d = new Date(s);
      if (!isNaN(d.getTime())) {
        const formatter = new Intl.DateTimeFormat("zh-CN", {
          timeZone: "Asia/Shanghai",
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false
        });
        const parts = formatter.formatToParts(d);
        const get = (t) => (parts.find(p => p.type === t) || {}).value || "";
        return `${get("year")}年${get("month")}月${get("day")}日 ${get("hour")}:${get("minute")}:${get("second")}`;
      }
    } catch (e) {}
  }
  if (fileName) {
    const m = String(fileName).match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
    if (m) {
      return `${m[1]}年${m[2]}月${m[3]}日 ${m[4]}:${m[5]}:${m[6]}`;
    }
  }
  return s || "-";
}

// ---------- WebDAV 远端归档浏览、快捷热恢复与云端删除 ----------
let _WD_FILES = [];
let _WD_PAGE = 1;
const _WD_PAGE_SIZE = 10;
async function loadRemoteWebDAVFiles(fromCache) {
  const box = document.getElementById("webdavFilesList");
  if (!box) return;
  // 分页器一次性事件委托（box 本体不重建，翻页不丢绑定）
  if (!box.dataset.wdPagerBound) {
    box.dataset.wdPagerBound = "1";
    box.addEventListener("click", (e) => {
      const pg = e.target.closest("[data-wdpage]");
      if (!pg || pg.disabled) return;
      const v = pg.dataset.wdpage;
      const total = Math.max(1, Math.ceil((_WD_FILES || []).length / _WD_PAGE_SIZE));
      if (v === "prev") _WD_PAGE = Math.max(1, _WD_PAGE - 1);
      else if (v === "next") _WD_PAGE = Math.min(total, _WD_PAGE + 1);
      else _WD_PAGE = Math.min(total, Math.max(1, parseInt(v, 10) || 1));
      loadRemoteWebDAVFiles(true);
    });
  }
  if (fromCache && _WD_FILES && _WD_FILES.length) {
    // 直接用缓存翻页，不重复请求远端
  } else {
  box.innerHTML = `<div class="hint" style="padding:14px;text-align:center">⏳ 正在连接 WebDAV 查询远端目录归档...</div>`;
  try {
    const res = await getBridge().apiGet("backup/webdav/files", {});
    if (!res || !res.ok) {
      const errMsg = (res && res.msg) ? res.msg : ((res && res.error) ? res.error : "无法读取 WebDAV 远端列表，请先检查配置与网络连通性");
      box.innerHTML = `<div class="hint" style="padding:14px;text-align:center;color:var(--bad);background:var(--panel2);border-radius:8px">❌ 读取远端归档失败: ${esc(errMsg)}</div>`;
      return;
    }
    _WD_FILES = res.files || [];
    _WD_PAGE = 1;
    if (!_WD_FILES.length) {
      box.innerHTML = `<div class="hint" style="padding:14px;text-align:center;background:var(--panel2);border-radius:8px">云端远端目录下暂无归档文件，点击上方「立即上传云端」即可上传备份。</div>`;
      return;
    }
  } catch (e) {
    box.innerHTML = `<div class="hint" style="padding:14px;text-align:center;color:var(--bad)">❌ 查询异常: ${esc(e.message)}</div>`;
    return;
  }
  }
  try {
    const files = _WD_FILES || [];
    if (!files.length) {
      box.innerHTML = `<div class="hint" style="padding:14px;text-align:center;background:var(--panel2);border-radius:8px">云端远端目录下暂无归档文件，点击上方「立即上传云端」即可上传备份。</div>`;
      return;
    }
    const totalPages = Math.max(1, Math.ceil(files.length / _WD_PAGE_SIZE));
    if (_WD_PAGE > totalPages) _WD_PAGE = totalPages;
    if (_WD_PAGE < 1) _WD_PAGE = 1;
    const pageFiles = files.slice((_WD_PAGE - 1) * _WD_PAGE_SIZE, _WD_PAGE * _WD_PAGE_SIZE);
    let html = `<div class="hint" style="font-size:11.5px;margin-bottom:6px">共 ${files.length} 份云端归档 · 第 ${_WD_PAGE}/${totalPages} 页（每页 ${_WD_PAGE_SIZE} 份）</div>`;
    html += `<div style="display:flex;flex-direction:column;gap:6px">`;
    pageFiles.forEach((f) => {
      const isDb = f.name.endsWith(".db");
      const shDate = formatShanghaiDate(f.mtime, f.name);
      html += `
        <div style="display:flex;align-items:center;justify-content:space-between;background:var(--panel2);padding:10px 14px;border-radius:10px;border:1px solid var(--line);flex-wrap:wrap;gap:8px">
          <div style="display:flex;align-items:center;gap:10px;min-width:200px">
            <span style="font-size:20px">${isDb ? "🗄️" : "📄"}</span>
            <div>
              <div style="font-weight:600;font-size:13px;word-break:break-all">${esc(f.name)}</div>
              <div class="hint" style="font-size:11.5px;margin-top:2px">大小: ${esc(f.size || "-")} · 修改时间: ${esc(shDate)}</div>
            </div>
          </div>
          <div style="display:flex;gap:6px;align-items:center">
            ${isDb ? `<button class="ghost" data-wdrestore="${esc(f.name)}" style="color:var(--acc);border-color:var(--accBorder);font-size:12px;padding:4px 10px">🔄 快捷恢复</button>` : ""}
            <button class="ghost" data-wddelete="${esc(f.name)}" style="color:var(--bad);border-color:rgba(239,68,68,0.3);font-size:12px;padding:4px 10px" title="从 WebDAV 云端彻底删除此备份文件">🗑️ 删除</button>
          </div>
        </div>
      `;
    });
    html += `</div>`;
    if (totalPages > 1) {
      let nums = "";
      for (let p = 1; p <= totalPages; p++) {
        nums += `<button class="ghost sm" data-wdpage="${p}" ${p === _WD_PAGE ? 'disabled style="opacity:.45"' : ""}>${p}</button>`;
      }
      html += `<div style="display:flex;align-items:center;justify-content:center;gap:6px;margin-top:8px;flex-wrap:wrap">`
        + `<button class="ghost sm" data-wdpage="prev" ${_WD_PAGE <= 1 ? "disabled" : ""}>‹ 上一页</button>`
        + nums
        + `<button class="ghost sm" data-wdpage="next" ${_WD_PAGE >= totalPages ? "disabled" : ""}>下一页 ›</button></div>`;
    }
    box.innerHTML = html;

    // 绑定快捷恢复事件
    box.querySelectorAll("[data-wdrestore]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const fname = btn.dataset.wdrestore;
        const ok = await uiConfirm(
          `确认从 WebDAV 远端备份【${fname}】恢复数据库？\n\n注意：当前数据与配置将即刻被远端备份覆盖并热重载生效！`,
          "恢复远端云备份"
        );
        if (!ok) return;
        const origText = btn.textContent;
        btn.disabled = true;
        btn.textContent = "⏳ 正在下载并恢复...";
        toast(`正在从云端拉取 [${fname}] 并执行恢复...`, "ok", 6000);
        try {
          const r = await getBridge().apiPost("backup/webdav/restore", { file: fname });
          if (r && r.ok) {
            toast(`远端备份 [${fname}] 恢复成功！`, "ok", 6000);
            await loadBackups(BACKUP_DIR);
          } else {
            const err = (r && r.msg) ? r.msg : ((r && r.error) ? r.error : "恢复失败");
            toast(`恢复失败: ${err}`, "bad", 8000);
            uiAlert(err, "远端恢复失败", "⚠️");
          }
        } catch (e) {
          toast(`恢复异常: ${e.message}`, "bad", 8000);
          uiAlert(e.message || String(e), "远端恢复异常", "⚠️");
        } finally {
          btn.disabled = false;
          btn.textContent = origText;
        }
      });
    });

    // 绑定云端删除事件
    box.querySelectorAll("[data-wddelete]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const fname = btn.dataset.wddelete;
        const ok = await uiConfirm(
          `确定要从 WebDAV 云端彻底删除备份文件【${fname}】吗？\n\n注意：此操作将直接从云端服务器永久删除该文件，不可逆！`,
          "删除云端备份"
        );
        if (!ok) return;
        const origText = btn.textContent;
        btn.disabled = true;
        btn.textContent = "⏳ 删除中...";
        toast(`正在从云端删除 [${fname}]...`, "ok", 4000);
        try {
          const r = await getBridge().apiPost("backup/webdav/delete", { file: fname });
          if (r && r.ok) {
            toast(`云端备份 [${fname}] 已删除！`, "ok", 5000);
            await loadRemoteWebDAVFiles();
          } else {
            const err = (r && r.msg) ? r.msg : ((r && r.error) ? r.error : "删除失败");
            toast(`删除失败: ${err}`, "bad", 8000);
            uiAlert(err, "删除云端备份失败", "⚠️");
          }
        } catch (e) {
          toast(`删除异常: ${e.message}`, "bad", 8000);
          uiAlert(e.message || String(e), "删除云端备份异常", "⚠️");
        } finally {
          btn.disabled = false;
          btn.textContent = origText;
        }
      });
    });
  } catch (err) {
    box.innerHTML = `<div class="hint" style="padding:14px;text-align:center;color:var(--bad);background:var(--panel2);border-radius:8px">❌ 网络或服务异常: ${esc(err.message || String(err))}</div>`;
  }
}
document.getElementById("btnWebDAVRefreshFiles")?.addEventListener("click", () => loadRemoteWebDAVFiles());
let _backupSearchTimer = null;
document.getElementById("backupSearch")?.addEventListener("input", () => {
  if (_backupSearchTimer) clearTimeout(_backupSearchTimer);
  _backupSearchTimer = setTimeout(() => {
    // 有缓存走本地过滤，不发请求；无缓存才拉一次
    if (BACKUP_CACHE) { try { renderBackups(BACKUP_CACHE); return; } catch (e) {} }
    loadBackups(BACKUP_DIR);
  }, 300);
});
// 备份顶部操作：对选中项生效
document.getElementById("btnBackupDelete")?.addEventListener("click", async () => {
  const sel = window.BACKUP_SELECTED || "";
  if (!sel) { toast("请先单击选中要删除的备份", "bad"); return; }
  if (!(await uiConfirm("确认删除备份 " + sel + "？", "删除备份"))) return;
  if (!(await uiConfirm("再次确认删除 \"" + sel + "\"？", "终极确认删除"))) return;
  try { await getBridge().apiPost("backups/delete", { path: sel }); toast("已删除", "ok"); window.BACKUP_SELECTED=""; await loadBackups(BACKUP_DIR); } catch (err) { toast("删除失败: " + err.message, "bad"); }
});
document.getElementById("btnBackupRestore")?.addEventListener("click", async () => {
  const sel = window.BACKUP_SELECTED || "";
  if (!sel) { toast("请先单击选中要恢复的备份", "bad"); return; }
  if (!(await uiConfirm("确认恢复备份 " + sel + "？当前数据将被覆盖！", "恢复备份"))) return;
  try { await getBridge().apiPost("backups/restore", { path: sel }); toast("已恢复，需重启插件生效", "ok"); } catch (err) { toast("恢复失败: " + err.message, "bad"); }
});
document.getElementById("btnBackupExportSel")?.addEventListener("click", async () => {
  const sel = window.BACKUP_SELECTED || "";
  if (!sel) { toast("请先单击选中要导出的备份文件", "bad"); return; }
  const ext = (sel.split(".").pop() || "").toLowerCase();
  if (!["db", "json"].includes(ext)) { toast("请选择具体备份文件导出（.db 或 .json），不可导出文件夹", "bad"); return; }
  const filename = sel.split("/").pop() || "backup.db";
  toast("正在导出备份...", "ok");
  try {
    const _b = getBridge();
    if (_b && typeof _b.download === "function") {
      try {
        await _b.download("backups/export", { path: sel, raw: "1" }, filename);
        toast("已触发下载: " + filename, "ok");
        return;
      } catch (e) {}
    }
    const r = await callApi("backups/export", { path: sel }, "GET");
    if (r && r.data) {
      downloadBase64File(r.data, r.filename || filename);
      toast("已成功导出备份文件", "ok");
    } else {
      toast("导出失败: " + (r && r.error ? r.error : "无数据"), "bad");
    }
  } catch (err) { toast("导出失败: " + err.message, "bad"); }
});
document.getElementById("btnClearAll")?.addEventListener("click", async () => {
  if (!(await uiConfirm("⚠️ 确认清空所有数据？此操作将删除所有钱包/账户/群数据/备份且不可恢复！", "危险：清空所有数据"))) return;
  const input = await uiPrompt("为防止误操作，请输入“确认删除”以继续：", "", "清空所有数据");
  if (input !== "确认删除") { toast("输入不正确，已取消清空", "bad"); return; }
  if (!(await uiConfirm("最终确认：真的要彻底清空所有数据吗？", "终极确认清空"))) return;
  try {
    await getBridge().apiPost("admin/clear", {confirm: "确认删除", confirm2: "确认"});
    toast("已成功清空所有数据", "ok");
    await loadUsers();
    await loadBackups("");
    if (typeof loadStats === "function") try { await loadStats(); } catch(e) {}
    if (typeof loadSlaveUsers === "function") try { await loadSlaveUsers(); } catch(e) {}
  } catch (e) {
    toast("清空失败: " + e.message, "bad");
  }
});
// ---------- 备份管理：WebDAV 与自动备份配置 + 配置快照 ----------
function _setVal(id, v) {
  const el = document.getElementById(id);
  if (el) el.value = v ?? "";
}
function _setChk(id, v) {
  const el = document.getElementById(id);
  if (el) el.checked = (String(v) === "真" || String(v) === "true" || String(v) === "1");
}
async function loadBackupCfg() {
  try {
    const cur = await getBridge().apiGet("config/get");
    const b = (cur || {})["备份配置"] || {};
    _setChk("wdSwitch", b["WebDAV备份开关"] ?? "假");
    _setVal("wdUrl", b["WebDAV服务器地址"] ?? "");
    _setVal("wdUser", b["WebDAV用户名"] ?? "");
    _setVal("wdPwd", b["WebDAV应用密码"] ?? "");
    _setVal("wdDir", b["WebDAV远端目录"] ?? "/xbbot_backup/");
    _setChk("autoSwitch", b["自动备份开关"] ?? "真");
    _setVal("autoHours", b["备份间隔小时"] ?? "3");
    _setVal("autoKeep", b["保留备份数量"] ?? "30");
    // 远端列表由页签统一拉一次，此处不拉，防双请求
  } catch (e) { err("backup cfg: " + e.message); }
}
async function saveBackupCfg() {
  const msg = document.getElementById("backupCfgMsg");
  const say = (t, ok) => {
    if (msg) {
      msg.textContent = t;
      msg.classList.remove("ok", "bad");
      msg.classList.add(ok ? "ok" : "bad");
    }
    toast(t, ok ? "ok" : "bad");
  };
  try {
    const g = (id) => (document.getElementById(id) || {}).value ?? "";
    const payload = {"备份配置": {
      "WebDAV备份开关": document.getElementById("wdSwitch")?.checked ? "真" : "假",
      "WebDAV服务器地址": g("wdUrl").trim(),
      "WebDAV用户名": g("wdUser").trim(),
      "WebDAV应用密码": g("wdPwd"),
      "WebDAV远端目录": g("wdDir").trim() || "/xbbot_backup/",
      "自动备份开关": document.getElementById("autoSwitch")?.checked ? "真" : "假",
      "备份间隔小时": g("autoHours").trim() || "3",
      "保留备份数量": g("autoKeep").trim() || "30"
    }};
    const res = await getBridge().apiPost("config/save", payload);
    if (res && res.error) {
      say("保存失败: " + res.error, false);
      return;
    }
    // 优先校验后端直接回显的已持久化配置（密钥存独立文件，回显恒空，只核对非隐私键）
    const directCfg = (res && res["备份配置"]) ? res["备份配置"] : null;
    if (directCfg) {
      const savedSw = directCfg["WebDAV备份开关"] || "";
      if (savedSw && savedSw !== payload["备份配置"]["WebDAV备份开关"]) {
        say(`保存异常：备份开关保存未生效 (预期:${payload["备份配置"]["WebDAV备份开关"]}, 实际:${savedSw})`, false);
        return;
      }
    }
    // 存后二次读回校验（含保留数/间隔，存丢当场暴露）
    try {
      const cur = await getBridge().apiGet("config/get");
      const b = (cur || {})["备份配置"] || {};
      const savedUrl = b["WebDAV服务器地址"] || "";
      const savedSw = b["WebDAV备份开关"] || "";
      const savedKeep = b["保留备份数量"] ?? "";
      const savedHours = b["备份间隔小时"] ?? "";
      if (payload["备份配置"]["WebDAV服务器地址"] && savedUrl && savedUrl !== payload["备份配置"]["WebDAV服务器地址"]) {
        say(`保存异常：服务器地址读回不一致，请重试`, false);
        return;
      }
      if (savedSw && savedSw !== payload["备份配置"]["WebDAV备份开关"]) {
        say(`保存异常：备份开关读回不一致，请重试`, false);
        return;
      }
      if (savedKeep !== "" && String(savedKeep) !== String(payload["备份配置"]["保留备份数量"])) {
        say(`保存异常：保留数量读回不一致 (预期:${payload["备份配置"]["保留备份数量"]}, 实际:${savedKeep})，请重试`, false);
        return;
      }
      if (savedHours !== "" && String(savedHours) !== String(payload["备份配置"]["备份间隔小时"])) {
        say(`保存异常：备份间隔读回不一致 (预期:${payload["备份配置"]["备份间隔小时"]}, 实际:${savedHours})，请重试`, false);
        return;
      }
    } catch (readErr) {}
    say("备份配置已成功保存并校验生效", true);
    // 保存保留数量后即时按新值修剪本地+云端旧备份，让“保留 N 份”立即生效
    try {
      const pr = await getBridge().apiPost("backups/prune", {});
      if (pr && pr.ok) {
        toast(pr.msg || "旧备份已按保留数量修剪", "ok");
        try { await loadBackups(typeof BACKUP_DIR !== "undefined" ? BACKUP_DIR : ""); } catch (e) {}
      }
    } catch (e) {}
    try { loadRemoteWebDAVFiles(); } catch (e) {}
  } catch (e) { say("保存失败: " + e.message, false); }
}
document.getElementById("btnBackupCfgSave")?.addEventListener("click", saveBackupCfg);
document.getElementById("btnSlaveRefresh")?.addEventListener("click", loadSlaveUsers);
// slaveSearch/spiritUserSearch 已在上方统一200ms防抖，此处只留排序即时触发
document.getElementById("slaveSort")?.addEventListener("change", renderSlaveTable);
document.getElementById("btnSpiritUsersRefresh")?.addEventListener("click", loadSpiritUsers);
document.getElementById("spiritUserSort")?.addEventListener("change", renderSpiritUsersTable);

// 表头点击快速排序事件委托（导出/刷新类按钮走各自直绑，此处只留排序，防一点多发）
document.addEventListener("click", (e) => {
  const target = e.target.closest("[data-sort], [data-slavesort], [data-spiritsort]");
  if (!target) return;
  if (target.dataset.sort) {
    const key = target.dataset.sort;
    const sel = document.getElementById("userSort");
    if (sel) {
      const cur = sel.value;
      const asc = `${key}_asc`;
      const desc = `${key}_desc`;
      sel.value = cur === desc ? asc : desc;
      renderUserTable();
    }
  } else if (target.dataset.slavesort) {
    const key = target.dataset.slavesort;
    const sel = document.getElementById("slaveSort");
    if (sel) {
      const cur = sel.value;
      const asc = `${key}_asc`;
      const desc = `${key}_desc`;
      sel.value = cur === desc ? asc : desc;
      renderSlaveTable();
    }
  } else if (target.dataset.spiritsort) {
    const key = target.dataset.spiritsort;
    const sel = document.getElementById("spiritUserSort");
    if (sel) {
      const cur = sel.value;
      const asc = `${key}_asc`;
      const desc = `${key}_desc`;
      sel.value = cur === desc ? asc : desc;
      renderSpiritUsersTable();
    }
  }
});
// 暴露给 tabs 懒加载委托（避免 tabs 占位路由 404）
window.loadUsers = loadUsers; window.loadSlaveUsers = typeof loadSlaveUsers!=='undefined'?loadSlaveUsers:undefined;
window.loadSpiritUsers = typeof loadSpiritUsers!=='undefined'?loadSpiritUsers:undefined;
window.loadConfig = loadConfig; window.loadRank = loadRank; window.loadCommands = loadCommands;
window.loadSpirits = loadSpirits; window.loadShops = loadShops; window.exportPreset = exportPreset; window.importPreset = importPreset; window.loadBackups = typeof loadBackups!=='undefined'?loadBackups:undefined;
window.loadImages = loadImages; window.loadStats = loadStats; window.loadOverviewReq = loadOverviewReq;
document.getElementById("btnLegacyPick")?.addEventListener("click", () => {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".ini,.db,.json,.zip"; inp.multiple = true;
  inp.onchange = async (e) => {
    const files = Array.from(e.target.files || []); if (!files.length) return;
    const msg = document.getElementById("legacyMsg");
    if (msg) { msg.textContent = "导入中... ("+files.length+" 个文件)"; msg.className = "msg"; }
    let total=0, ok=0, last=null;
    for (const file of files) {
      try {
        const r = await getBridge().upload("import/legacy", file);
        last=r;
        if (r && !r.error) { ok++; total+= (r.imported||0); }
        else if (r && r.error) { toast("文件 "+file.name+" 失败: "+r.error, "bad"); }
      } catch (err) {
        toast("文件 "+file.name+" 失败: "+err.message, "bad");
      }
    }
    if (msg) {
      if (ok===files.length) { msg.textContent = "旧库导入成功: "+total+" 条，共 "+files.length+" 文件"; msg.classList.add("ok"); toast("旧库导入成功: "+total+" 条","ok"); }
      else { msg.textContent = "导入完成: "+ok+"/"+files.length+" 成功, 共 "+total+" 条"; msg.classList.add(ok?"ok":"bad"); }
    }
    await loadBackups("");
    await loadUsers();
    if (typeof loadSlaveUsers==="function") try{ await loadSlaveUsers(); }catch(e){}
  };
  inp.click();
});
// 用户全量导出导入与清理退群
document.getElementById("btnUsersExport")?.addEventListener("click", exportAllUsers);
document.getElementById("btnUsersImport")?.addEventListener("click", importAllUsers);
document.getElementById("btnUsersCleanLeft")?.addEventListener("click", cleanLeftUsers);
document.getElementById("btnUserClearManual")?.addEventListener("click", clearUserManual);

// 启动主逻辑
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => { main(); });
} else {
  main();
}



// ==================== 群生态与经济运行大屏 ====================
async function loadAnalytics() {
  try {
    const res = await getBridge().apiGet("analytics/overview");
    if (!res || !res.ok) return;

    const sum = res.summary || {};
    const fmt = (n) => Number(n || 0).toLocaleString();

    const el = (id) => document.getElementById(id);
    if (el("anaTotalUsers")) el("anaTotalUsers").textContent = `${fmt(sum.total_users)} 人`;
    if (el("anaTotalGroups")) el("anaTotalGroups").textContent = `开通群聊: ${fmt(sum.total_groups)} 个`;
    if (el("anaTotalEconomy")) el("anaTotalEconomy").textContent = fmt(sum.total_economy_pool);
    if (el("anaAvgMoney")) el("anaAvgMoney").textContent = `人均资产: ${fmt(sum.avg_money_per_user)}`;
    if (el("anaBankDeposit")) el("anaBankDeposit").textContent = fmt(sum.total_bank_deposit);
    if (el("anaBankUsers")) el("anaBankUsers").textContent = `储蓄玩家: ${fmt(sum.total_bank_users)} 人`;
    if (el("anaSlaveWorth")) el("anaSlaveWorth").textContent = fmt(sum.total_slave_worth);
    if (el("anaSlaveCount")) el("anaSlaveCount").textContent = `奴隶: ${sum.total_slaves_count || 0} 人 / 奴隶主: ${sum.total_masters_count || 0} 人`;
    if (el("anaSignCount")) el("anaSignCount").textContent = `${fmt(sum.total_sign_count)} 次`;
  } catch(e) {
    console.error("loadAnalytics error:", e);
  }
}

// ==================== 3. 批量全员 / 定向群福利空投 ====================
async function openAirdropModal() {
  const modal = document.getElementById("appModal");
  if (!modal) return;
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");

  if (icon) icon.textContent = "🎁";
  if (title) title.textContent = "批量资产空投与福利分发";
  if (inputWrap) inputWrap.style.display = "none";

  content.innerHTML = `
    <div style="font-size:12px;color:var(--muted);margin-bottom:12px">
      一键向全群或指定群所有玩家批量发放货币、体力或抽奖券福利（自动事务写入）：
    </div>
    <div style="display:flex;flex-direction:column;gap:10px">
      <div>
        <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">🎯 目标群聊 (留空则面向全库所有活跃玩家)：</label>
        <input id="dropGid" placeholder="输入群号 (留空全库)" style="width:100%;padding:7px 10px;border-radius:8px">
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
        <div>
          <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">💰 赠送货币：</label>
          <input type="number" id="dropMoney" value="1000" style="width:100%;padding:7px 10px;border-radius:8px">
        </div>
        <div>
          <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">⚡ 赠送体力：</label>
          <input type="number" id="dropStamina" value="100" style="width:100%;padding:7px 10px;border-radius:8px">
        </div>
        <div>
          <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">🎟️ 抽奖券：</label>
          <input type="number" id="dropTickets" value="5" style="width:100%;padding:7px 10px;border-radius:8px">
        </div>
      </div>
      <div>
        <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">📝 空投事由 / 备注：</label>
        <input id="dropReason" value="节日全员福利空投" style="width:100%;padding:7px 10px;border-radius:8px">
      </div>
    </div>
  `;

  if (cancelBtn) {
    cancelBtn.style.display = "";
    cancelBtn.textContent = "取消";
    cancelBtn.onclick = () => { modal.className = ""; };
  }
  if (okBtn) {
    okBtn.textContent = "🚀 立即发送全员空投";
    okBtn.onclick = async () => {
      const gid = (document.getElementById("dropGid")?.value || "").trim();
      const money = parseInt(document.getElementById("dropMoney")?.value || 0, 10);
      const stamina = parseInt(document.getElementById("dropStamina")?.value || 0, 10);
      const tickets = parseInt(document.getElementById("dropTickets")?.value || 0, 10);
      const reason = document.getElementById("dropReason")?.value || "全员福利空投";

      okBtn.disabled = true;
      okBtn.textContent = "正在分发空投...";
      try {
        const res = await getBridge().apiPost("users/airdrop", { gid, money, stamina, tickets, reason });
        if (res && res.ok) {
          toast(`🎉 空投发放成功！已成功为 ${res.target_count || 0} 名用户注入资产`, "ok");
          modal.className = "";
          await loadUsers();
          await loadAnalytics();
        } else {
          toast("空投失败: " + (res && (res.error || res.msg) ? (res.error || res.msg) : "未知错误"), "bad");
        }
      } catch(err) {
        toast("空投异常: " + err.message, "bad");
      } finally {
        okBtn.disabled = false;
        okBtn.onclick = null;
      }
    };
  }
  modal.className = "show";
}

// 绑定新模块事件监听（模拟器页签已下线，死绑定已删；空投按钮加防重）

// Tab 切换时自动加载大屏数据
const origInitNav = typeof initNav === "function" ? initNav : null;


async function calibrateSlavePrices() {
  if (!(await uiConfirm("确认一键校准全群所有玩家的奴隶身价？\n系统将自动检测全库所有身价为 0 或未初始化的用户，并批量匹配为当前配置的初始身价！", "一键校准全员身价"))) return;
  toast("正在智能校准全员奴隶身价...", "ok");
  try {
    const res = await getBridge().apiPost("slave/calibrate", {});
    if (res && res.ok) {
      toast(res.msg || `🎉 成功校准 ${res.fixed_count || 0} 名用户的奴隶身价！`, "ok");
      await loadSlaveUsers();
      if (typeof loadAnalytics === "function") try { await loadAnalytics(); } catch(e) {}
    } else {
      toast("校准失败: " + (res && res.error ? res.error : "未知错误"), "bad");
    }
  } catch(err) {
    toast("校准异常: " + err.message, "bad");
  }
}

document.getElementById("btnSlaveCalibrate")?.addEventListener("click", calibrateSlavePrices);


// 确保新模块在 DOM 加载完毕后自动绑定
function initNewModules() {
  const _air = document.getElementById("btnUsersAirdrop");
  if (_air && !_air.dataset.bound) { _air.dataset.bound = "1"; _air.addEventListener("click", openAirdropModal); }
  document.getElementById("btnCmdAddCustomTop")?.addEventListener("click", () => {
    const inner = document.getElementById("btnCmdAddCustom");
    if (inner) { inner.click(); return; }
    CMD_EDIT = { sys: "自定义", cmd: "", isNew: true, mapCmd: "" };
    openCmdEditor();
  });
  document.getElementById("btnDbDoctorOv")?.addEventListener("click", runDbDoctor);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initNewModules);
} else {
  initNewModules();
}


// ---------- 数据库健康体检与碎片整理 (Doctor / Vacuum) ----------
async function runDbDoctor() {
  toast("正在执行数据库健康体检与碎片整理...", "ok");
  try {
    const res = await getBridge().apiPost("backups/doctor", {});
    if (res && res.ok) {
      const tblInfo = res.tables ? Object.entries(res.tables).map(([k, v]) => `${k}: ${v} 行`).join(" | ") : "";
      const msg = `🎉 数据库体检与整理完成！\n\n· 完整性健康状态: ${res.integrity}\n· 整理前总大小: ${res.size_before}\n· 整理后总大小: ${res.size_after}\n· 释放碎片空间: ${res.saved}\n· 数据表行数统计: ${tblInfo}`;
      await uiAlert(msg, "数据库体检报告", "🩺");
      toast(res.msg || "体检完成", "ok");
      if (typeof loadBackups === "function") try { await loadBackups(""); } catch(e){}
    } else {
      toast("体检失败: " + (res && res.error ? res.error : "未知错误"), "bad");
    }
  } catch(err) {
    toast("体检异常: " + err.message, "bad");
  }
}

document.getElementById("btnDbDoctor")?.addEventListener("click", runDbDoctor);


// ---------- 在线版本检测系统 ----------
let LATEST_RELEASE_DATA = null;

let LATEST_DUAL = null; // 双通道检测结果 {beta, stable}：只查最新，不切换
function paintVerMatch() {
  // 前后端对账：两边版本不同即红字（更新只拉了一半的经典症状），免得对着旧包调新问题
  try {
    const fz = document.getElementById("aboutFrontendVer");
    if (fz && typeof FRONTEND_VER !== "undefined") fz.textContent = "v" + FRONTEND_VER;
    const warn = document.getElementById("verMismatch");
    const bv = (typeof LATEST_RELEASE_DATA !== "undefined" && LATEST_RELEASE_DATA && LATEST_RELEASE_DATA.current_version) || "";
    if (warn) {
      if (typeof FRONTEND_VER !== "undefined" && bv && String(FRONTEND_VER) !== String(bv)) {
        warn.style.display = "";
        warn.innerHTML = `⚠️ 前后端版本不一致：前端 v${esc(FRONTEND_VER)} / 后端 v${esc(bv)}。请 pull 最新代码后<b>完全重启 AstrBot</b>（仅重载插件不够）。`;
      } else warn.style.display = "none";
    }
  } catch (e) {}
}
async function _checkOneChannel(c) {
  // 单通道检测：成功即后端原样；失败转可显示错误对象（另一通道不受影响）
  try {
    const timeout = new Promise((_, rej) => setTimeout(() => rej(new Error("请求超时(20s)，请检查网络后重试")), 20000));
    const r = await Promise.race([getBridge().apiGet("version/check", { channel: c }), timeout]);
    if (r && (r.ok || r.has_update !== undefined || r.current_version)) return r;
    let raw = "";
    try { raw = JSON.stringify(r).slice(0, 120); } catch (e) {}
    return { ok: true, current_version: "", latest_version: "", has_update: false, channel: c, detect_error: "无有效响应" + (raw ? "：" + raw : "") };
  } catch (e) {
    return { ok: true, current_version: "", latest_version: "", has_update: false, channel: c, detect_error: (e && e.message) || String(e) };
  }
}
function _paintChannelRow(elId, res) {
  // 双通道行绘制：最新版 / 已是最新 / 检测失败 三态
  try {
    const el = document.getElementById(elId);
    if (!el) return;
    if (res && !res.detect_error && res.latest_version) {
      el.textContent = res.has_update ? ("v" + res.latest_version + "（有更新）") : ("v" + res.latest_version);
    } else {
      el.textContent = "检测失败" + (res && res.detect_error ? "：" + res.detect_error : "");
    }
  } catch (e) {}
}
async function checkVersionUpdate(silent = false) {
  const btn = document.getElementById("btnCheckUpdate");
  const statusEl = document.getElementById("checkUpdateStatus");
  try {
    if (!silent) toast("正在检测双通道最新版本...", "ok");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "⏳ 检测中…";
    }
    if (statusEl && !silent) {
      statusEl.style.display = "inline-flex";
      statusEl.style.color = "var(--muted)";
      statusEl.style.background = "var(--panel2)";
      statusEl.style.border = "1px solid var(--line)";
      statusEl.textContent = "⏳ 正在检测 BETA/正式版…";
    }
    // 双通道并查：BETA 查 xbtest 快照仓，正式查官方仓；单路失败不影响另一路
    const [resB, resS] = await Promise.all([_checkOneChannel("BETA"), _checkOneChannel("正式")]);
    LATEST_DUAL = { beta: resB, stable: resS };
    const cur = (resB && resB.current_version) || (resS && resS.current_version) || "";
    LATEST_RELEASE_DATA = { current_version: cur, beta: resB, stable: resS };
    try { paintVerMatch(); } catch (e) {}
    try {
      const av = document.getElementById("aboutVersion");
      if (av && cur) av.textContent = "v" + cur;
    } catch (e) {}
    _paintChannelRow("aboutLatestBeta", resB);
    _paintChannelRow("aboutLatestStable", resS);
    const updB = Boolean(resB && resB.has_update && resB.latest_version);
    const updS = Boolean(resS && resS.has_update && resS.latest_version);
    const failB = Boolean(!resB || resB.detect_error);
    const failS = Boolean(!resS || resS.detect_error);
    const updVer = updB ? resB.latest_version : (updS ? resS.latest_version : "");
    const badge = document.getElementById("verBadge");
    if (updVer) {
      if (btn) {
        btn.textContent = "🚀 发现新版 v" + updVer;
        btn.style.color = "var(--acc)";
        btn.style.borderColor = "var(--acc)";
        btn.style.background = "rgba(59,130,246,0.1)";
      }
      if (statusEl) {
        statusEl.style.display = "inline-flex";
        statusEl.style.color = "var(--acc)";
        statusEl.style.background = "rgba(59,130,246,0.12)";
        statusEl.style.border = "1px solid rgba(59,130,246,0.3)";
        const _which = updB && updS ? "BETA/正式均" : (updB ? "BETA " : "正式 ");
        statusEl.textContent = "🚀 " + _which + "发现新版本 v" + updVer + "（建议升级）";
      }
      if (badge) {
        badge.style.display = "inline-flex";
        badge.style.background = "linear-gradient(135deg, #3B82F6, #1D4ED8)";
        badge.textContent = "🚀 发现新版本 v" + updVer;
        badge.title = "点击查看双通道更新详情";
      }
      if (!silent) {
        toast("发现新版本: v" + updVer, "ok");
        showUpdateModal();
      }
    } else if (failB || failS) {
      if (btn) {
        btn.textContent = "⚠️ 重试检测";
        btn.style.color = "var(--warn)";
        btn.style.borderColor = "var(--warn)";
        btn.style.background = "rgba(255,149,0,0.08)";
      }
      if (statusEl) {
        if (!silent) {
          statusEl.style.display = "inline-flex";
          statusEl.style.color = "var(--warn)";
          statusEl.style.background = "rgba(255,149,0,0.12)";
          statusEl.style.border = "1px solid rgba(255,149,0,0.3)";
          const _fe = (failB && resB && resB.detect_error ? "BETA:" + resB.detect_error : "") + (failB && failS ? "；" : "") + (failS && resS && resS.detect_error ? "正式:" + resS.detect_error : "");
          statusEl.textContent = "⚠️ 检测失败：" + _fe;
        } else {
          statusEl.style.display = "none";
        }
      }
      if (badge) {
        badge.style.display = "inline-flex";
        badge.style.background = "linear-gradient(135deg,#F59E0B,#D97706)";
        badge.textContent = "⚠️ 更新检测失败";
        badge.title = "部分通道检测失败（点击重试）";
      }
      if (!silent) {
        toast("更新检测失败", "bad", 8000);
        showUpdateModal();
      }
    } else {
      if (btn) {
        btn.textContent = "🟢 已是最新 (v" + cur + ")";
        btn.style.color = "var(--ok)";
        btn.style.borderColor = "var(--ok)";
        btn.style.background = "rgba(52,199,89,0.08)";
      }
      if (statusEl) {
        statusEl.style.display = "none";
        statusEl.textContent = "";
      }
      if (badge) {
        // 双最新时徽标隐藏（顶栏已有版本号，不重复展示）
        badge.style.display = "none";
      }
      if (!silent) {
        showUpdateModal();
      }
    }
  } catch (err) {
    if (btn) {
      btn.textContent = "⚠️ 检测超时/失败";
      btn.style.color = "var(--warn)";
    }
    if (statusEl) {
      statusEl.style.display = "inline-flex";
      statusEl.style.color = "var(--warn)";
      statusEl.style.background = "rgba(255,149,0,0.12)";
      statusEl.style.border = "1px solid rgba(255,149,0,0.3)";
      statusEl.textContent = "⚠️ 请求失败: " + err.message;
    }
    if (!silent) toast("检测更新失败: " + err.message, "bad");
  } finally {
    if (btn) btn.disabled = false;
  }
}

function _channelCardHTML(title, icon, data) {
  // 单通道卡片：最新版/有更新/检测失败 三态（二卡并列，结构对称）
  const d = (data && typeof data === "object") ? data : {};
  const cur = d.current_version || "";
  const lat = d.latest_version || "";
  const isNew = Boolean(d.has_update && lat);
  const errStr = d.detect_error || "";
  let body = "";
  if (errStr) {
    body = `<div style="font-size:15px;font-weight:700;color:var(--warn)">检测失败</div>`
      + `<div style="font-size:11px;color:var(--muted);margin-top:4px">${esc(errStr)}</div>`;
  } else if (lat) {
    body = `<div style="font-size:15px;font-weight:700;color:${isNew ? "var(--acc)" : "var(--ok)"}">v${esc(lat)}${isNew ? "（有更新）" : ""}</div>`
      + (d.release_date ? `<div style="font-size:11px;color:var(--muted);margin-top:4px">发布于 ${esc(d.release_date)}</div>` : "")
      + (d.repo ? `<div style="font-size:11px;color:var(--muted);margin-top:2px">${esc(d.repo)}</div>` : "");
  } else {
    body = `<div style="font-size:15px;font-weight:700;color:var(--muted)">未知</div>`;
  }
  void cur;
  return `<div style="padding:10px 12px;background:var(--panel);border-radius:10px;border:1px solid var(--line)">`
    + `<div style="font-size:11px;color:var(--muted);margin-bottom:2px">${icon} ${esc(title)}</div>` + body + `</div>`;
}

function showUpdateModal() {
  // 双通道详情弹窗：当前本地＋BETA 最新＋正式最新（只查不切）
  const dual = (typeof LATEST_DUAL !== "undefined" && LATEST_DUAL) || {};
  const resB = dual.beta || {};
  const resS = dual.stable || {};
  const curVer = resB.current_version || resS.current_version || "未知";
  const updB = Boolean(resB.has_update && resB.latest_version);
  const updS = Boolean(resS.has_update && resS.latest_version);
  const failB = Boolean(!resB.latest_version);
  const failS = Boolean(!resS.latest_version);

  let statusCard = "";
  if (updB || updS) {
    const _which = updB && updS ? "BETA/正式均" : (updB ? "BETA " : "正式 ");
    const _ver = updB ? resB.latest_version : resS.latest_version;
    statusCard = `
<div style="padding:10px 12px;background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.25);border-radius:10px;font-size:12px;color:var(--acc);margin-top:10px;display:flex;align-items:center;gap:8px">
  <span style="font-size:18px">🚀</span>
  <div>
    <div style="font-weight:700">${_which}发现云端更新！建议升级至 v${esc(_ver)}</div>
    <div style="font-size:11px;color:var(--muted);margin-top:2px">前往 AstrBot 官方面板的「插件管理」页面，点击「更新」即可一键无损升级。</div>
  </div>
</div>`;
  } else if (failB || failS) {
    statusCard = `
<div style="padding:10px 12px;background:var(--warnSoft);border:1px solid rgba(255,149,0,0.25);border-radius:10px;font-size:12px;color:var(--warn);margin-top:10px;display:flex;align-items:center;gap:8px">
  <span style="font-size:18px">⚠️</span>
  <div>
    <div style="font-weight:700">部分通道检测未能连通</div>
    <div style="font-size:11px;color:var(--muted);margin-top:2px">${esc((failB && resB.detect_error ? "BETA:" + resB.detect_error : "") + (failB && failS ? "；" : "") + (failS && resS.detect_error ? "正式:" + resS.detect_error : ""))}</div>
  </div>
</div>`;
  } else {
    statusCard = `
<div style="padding:10px 12px;background:var(--okSoft);border:1px solid rgba(52,199,89,0.25);border-radius:10px;font-size:12px;color:var(--ok);margin-top:10px;display:flex;align-items:center;gap:8px">
  <span style="font-size:18px">✨</span>
  <div>
    <div style="font-weight:700">双通道均为最新版本 (v${esc(curVer)})</div>
    <div style="font-size:11px;color:var(--muted);margin-top:2px">当前运行代码已处于最新版本状态，运行良好，无需执行更新。</div>
  </div>
</div>`;
  }

  const modalHtml = `
<div style="background:var(--panel2);border-radius:14px;padding:12px 14px;border:1px solid var(--line);margin-bottom:12px">
  <div style="padding:10px 12px;background:var(--panel);border-radius:10px;border:1px solid var(--line);margin-bottom:10px">
    <div style="font-size:11px;color:var(--muted);margin-bottom:2px">当前本地运行版本</div>
    <div style="font-size:15px;font-weight:700;color:var(--text)">v${esc(curVer)}</div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
    ${_channelCardHTML("BETA 最新（xbtest 快照）", "🚀", resB)}
    ${_channelCardHTML("正式最新（官方 Release）", "🏷️", resS)}
  </div>
  ${statusCard}
</div>

<div style="font-size:12.5px;font-weight:600;color:var(--text);margin-bottom:6px">📝 BETA 更新日志</div>
<div style="background:var(--panel);border-radius:10px;padding:10px 12px;border:1px solid var(--line);font-size:12px;color:var(--text);max-height:120px;overflow-y:auto;white-space:pre-wrap;line-height:1.6;margin-bottom:10px">
${esc((resB && resB.changelog) || "暂无详细更新日志。")}
</div>
<div style="font-size:12.5px;font-weight:600;color:var(--text);margin-bottom:6px">📝 正式版更新日志</div>
<div style="background:var(--panel);border-radius:10px;padding:10px 12px;border:1px solid var(--line);font-size:12px;color:var(--text);max-height:120px;overflow-y:auto;white-space:pre-wrap;line-height:1.6">
${esc((resS && resS.changelog) || "暂无详细更新日志。")}
</div>
`;
  const isNew = updB || updS;
  const modalTitle = isNew ? "发现新版本" : ((failB || failS) ? "版本检测结果" : "版本检测：已是最新版本");
  const modalIcon = isNew ? "🚀" : ((failB || failS) ? "⚠️" : "✨");
  uiAlert(modalHtml, modalTitle, modalIcon);
}

// 绑定版本徽章与检查更新按钮（无切换：只查双通道最新）
document.getElementById("verBadge")?.addEventListener("click", () => {
  if (typeof LATEST_DUAL !== "undefined" && LATEST_DUAL) showUpdateModal();
  else checkVersionUpdate(false);
});
document.getElementById("btnCheckUpdate")?.addEventListener("click", () => checkVersionUpdate(false));
document.getElementById("checkUpdateStatus")?.addEventListener("click", () => {
  if (typeof LATEST_DUAL !== "undefined" && LATEST_DUAL) showUpdateModal();
  else checkVersionUpdate(false);
});

// 启动时静默检查一次
setTimeout(() => { checkVersionUpdate(true); }, 1500);

// ---------- 插件运行日志 ----------
let LOGS_CACHE = [];
let LOGS_TIMER = null;
let _LOGS_SIG = "";

function parseLogLine(raw) {
  // Line format: [YYYY-MM-DD HH:MM:SS] [LEVEL] msg
  const m = raw.match(/^\[(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\]\s+\[(INFO|WARN|ERROR)\]\s+(.*)$/);
  if (m) {
    return { ts: m[1], level: m[2], msg: m[3] };
  }
  return { ts: "", level: "INFO", msg: raw };
}

function renderLogs(logsList) {
  const container = document.getElementById("logTerminalContent");
  if (!container) return;
  if (!logsList || logsList.length === 0) {
    container.innerHTML = '<div class="log-empty">暂无匹配的运行日志</div>';
    return;
  }

  const linesHtml = logsList.map(raw => {
    const item = parseLogLine(raw);
    const lvlClass = item.level.toLowerCase();
    const tsHtml = item.ts ? `<span class="log-ts">[${esc(item.ts)}]</span>` : "";
    const badgeHtml = item.level ? `<span class="log-badge ${lvlClass}">${esc(item.level)}</span>` : "";
    return `<div class="log-line">${tsHtml}${badgeHtml}<span class="log-msg">${esc(item.msg)}</span></div>`;
  }).join("");

  container.innerHTML = linesHtml;

  const autoScroll = document.getElementById("logsAutoScroll");
  if (autoScroll && autoScroll.checked) {
    const terminal = document.getElementById("logTerminal");
    if (terminal) {
      terminal.scrollTop = terminal.scrollHeight;
    }
  }
}

async function loadLogs(isAuto = false) {
  try {
    const lvl = (document.getElementById("logsLevelFilter")?.value || "").trim();
    const kw = (document.getElementById("logsSearch")?.value || "").trim();
    const params = { limit: "500", level: lvl, keyword: kw };

    // 单次 callApi（GET空结果不再回退POST，防双倍请求；失败仅一次POST兜底在callApi内）
    const res = await callApi("logs", params, "GET");

    const data = (res && (res.result || res.data || res)) || {};
    const logsList = Array.isArray(data.logs) ? data.logs : (Array.isArray(res) ? res : []);

    // 内容无变化跳过重渲染：日志只追加，长度+首尾行一致即视为无更新，省 500 行 DOM 重建
    const _sig = logsList.length + "|" + (logsList[0] || "") + "|" + (logsList[logsList.length - 1] || "");
    if (isAuto && _sig === _LOGS_SIG) return true;
    _LOGS_SIG = _sig;
    LOGS_CACHE = logsList;
    renderLogs(LOGS_CACHE);

    const meta = document.getElementById("logsMetaInfo");
    if (meta) {
      const count = data.count !== undefined ? data.count : logsList.length;
      const total = data.total_lines !== undefined ? data.total_lines : logsList.length;
      const size = data.file_size_kb !== undefined ? data.file_size_kb : 0;
      const maxMb = data.max_file_mb !== undefined ? data.max_file_mb : 2.0;
      meta.textContent = `当前展示: ${count} / ${total} 行 | 文件大小: ${size} KB (上限 ${maxMb} MB)`;
    }
    return true;
  } catch (e) {
    const container = document.getElementById("logTerminalContent");
    if (container && (!LOGS_CACHE || LOGS_CACHE.length === 0)) {
      container.innerHTML = '<div class="log-empty">暂无运行日志记录</div>';
    }
    if (!isAuto) {
      toast("拉取日志未成功，请稍后重试", "bad");
    }
    return false;
  }
}

function startLogsAutoRefresh() {
  stopLogsAutoRefresh();
  const autoCheckbox = document.getElementById("logsAutoRefresh");
  const liveBadge = document.getElementById("logsLiveBadge");
  if (autoCheckbox && autoCheckbox.checked) {
    if (liveBadge) {
      liveBadge.innerHTML = '<span class="status-dot"></span> 实时监听';
      liveBadge.style.opacity = "1";
    }
    LOGS_TIMER = setInterval(() => {
      const logsTab = document.getElementById("tab-logs");
      if (logsTab && logsTab.classList.contains("on")) {
        loadLogs(true);
      } else {
        stopLogsAutoRefresh();
      }
    }, 3000);
  } else {
    if (liveBadge) {
      liveBadge.innerHTML = '<span class="status-dot" style="background:var(--muted)"></span> 已暂停';
      liveBadge.style.opacity = "0.7";
    }
  }
}

function stopLogsAutoRefresh() {
  if (LOGS_TIMER) {
    clearInterval(LOGS_TIMER);
    LOGS_TIMER = null;
  }
}

function initLogsEvents() {
  document.getElementById("logsAutoRefresh")?.addEventListener("change", () => {
    startLogsAutoRefresh();
  });
  document.getElementById("logsLevelFilter")?.addEventListener("change", () => {
    loadLogs(false);
  });
  let kwTimer = null;
  document.getElementById("logsSearch")?.addEventListener("input", () => {
    if (kwTimer) clearTimeout(kwTimer);
    kwTimer = setTimeout(() => loadLogs(false), 250);
  });
  document.getElementById("btnLogsRefresh")?.addEventListener("click", async () => {
    toast("正在刷新日志…", "ok");
    const ok = await loadLogs(false);
    if (ok) {
      toast("日志已刷新", "ok");
    }
  });
  document.getElementById("btnLogsCopy")?.addEventListener("click", () => {
    if (!LOGS_CACHE || LOGS_CACHE.length === 0) {
      toast("当前无日志可复制", "bad");
      return;
    }
    const text = LOGS_CACHE.join("\n");
    copyToClipboard(text);
  });
  document.getElementById("btnLogsExport")?.addEventListener("click", async () => {
    try {
      toast("正在准备导出日志…", "ok");
      let content = "";
      let filename = `xb_logs_${new Date().toISOString().slice(0, 10)}.log`;

      try {
        const res = await callApi("logs/export", {}, "POST");
        if (res && res.content) {
          content = res.content;
          if (res.filename) filename = res.filename;
        }
      } catch (e) {
        console.warn("API export failed, falling back to cached logs", e);
      }

      if (!content && LOGS_CACHE && LOGS_CACHE.length > 0) {
        content = LOGS_CACHE.join("\n");
      }

      if (!content) {
        toast("当前无日志可导出", "bad");
        return;
      }

      const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
      triggerDownload(blob, filename, content);
      toast("日志已成功导出", "ok");
    } catch (e) {
      toast("导出日志失败: " + e.message, "bad");
    }
  });
  document.getElementById("btnLogsClear")?.addEventListener("click", async () => {
    const ok = await uiConfirm("确定要清空当前的插件运行日志吗？\n清空后不可恢复（将重新从空文件开始记录）。", "清空日志");
    if (!ok) return;
    try {
      toast("正在清空日志…", "ok");
      const res = await callApi("logs/clear", {}, "POST");
      if (res && res.status === "error") {
        throw new Error(res.error || "清空失败");
      }
      toast((res && res.message) || "日志已清空", "ok");
      LOGS_CACHE = [];
      renderLogs([]);
      const meta = document.getElementById("logsMetaInfo");
      if (meta) meta.textContent = "当前展示: 0 / 0 行 | 文件大小: 0 KB (上限 2.0 MB)";
      await loadLogs(false);
    } catch (e) {
      toast("清空日志失败: " + e.message, "bad");
    }
  });
}

initLogsEvents();
