// ============================================================================
// Android 15 / Material 3 智能选择性导入中心 (Smart Selective Importer)
// ============================================================================
let _PARSED_IMPORT_PACKAGE = null;

function _analyzeImportPackage(data) {
  const recognized = [];
  EXPORT_MODULES.forEach(m => {
    const d = m.detect(data);
    if (d) {
      recognized.push({
        key: m.key,
        title: m.title,
        desc: m.desc,
        checked: m.defaultChecked,
        data: d
      });
    }
  });
  return recognized;
}

function showImportInspectModal(filename, parsedData) {
  const modal = document.getElementById("importHubModal");
  if (!modal) return;

  _PARSED_IMPORT_PACKAGE = { filename, data: parsedData };
  const modules = _analyzeImportPackage(parsedData);

  const fnEl = document.getElementById("importHubFileName");
  const infoEl = document.getElementById("importHubFileInfo");
  if (fnEl) fnEl.textContent = `📄 文件：${filename}`;
  if (infoEl) {
    const ver = parsedData.from_version || parsedData.version || "未知";
    const time = parsedData.exported_at ? new Date(parsedData.exported_at).toLocaleString() : "未知";
    infoEl.textContent = `版本来源: ${ver} ｜ 导出时间: ${time} ｜ 识别到 ${modules.length} 个独立模块`;
  }

  const listEl = document.getElementById("importHubModulesList");
  if (listEl) {
    if (modules.length === 0) {
      listEl.innerHTML = `<div style="padding:16px;text-align:center;color:var(--bad);background:var(--badSoft);border-radius:10px">⚠️ 无法在当前文件中识别出有效的插件模块，请确认文件格式是否正确。</div>`;
    } else {
      listEl.innerHTML = modules.map(m => `
        <div class="hub-mod-card" style="padding:12px 14px">
          <label class="hub-checkbox-label" style="display:flex;align-items:flex-start;gap:10px">
            <input type="checkbox" data-import-key="${esc(m.key)}" ${m.checked ? "checked" : ""} style="margin-top:2px">
            <div>
              <div class="hub-mod-title" style="font-size:13px">${esc(m.title)}</div>
              <div class="hub-mod-desc" style="font-size:11.5px">${esc(m.desc)}</div>
            </div>
          </label>
        </div>
      `).join("");
    }
  }

  modal.style.display = "flex";
  modal.classList.add("show");
}

function closeImportHub() {
  const modal = document.getElementById("importHubModal");
  if (modal) { modal.classList.remove("show"); modal.style.display = "none"; }
}

function openImportHub(file = null) {
  if (file) { _handleImportFile(file); return; }
  const inp = document.createElement("input");
  inp.type = "file";
  inp.accept = ".json,application/json";
  inp.onchange = (e) => { const f = e.target.files[0]; if (f) _handleImportFile(f); };
  inp.click();
}

async function _handleImportFile(file) {
  try {
    toast("正在解析导入文件…", "");
    const txt = (await file.text()).replace(/^\uFEFF/, "");
    const data = JSON.parse(txt);
    if (!data || typeof data !== "object") throw new Error("文件内容不是合法的 JSON 对象");
    showImportInspectModal(file.name, data);
  } catch (err) {
    toast("解析导入文件失败: " + (err.message || err), "bad");
  }
}

function initImportHubEvents() {
  if (window._IMPORT_HUB_INITIALIZED) return;
  window._IMPORT_HUB_INITIALIZED = true;

  document.getElementById("btnOpenImportHub")?.addEventListener("click", () => openImportHub());
  document.getElementById("importHubClose")?.addEventListener("click", closeImportHub);
  document.getElementById("importHubCancel")?.addEventListener("click", closeImportHub);

  document.getElementById("importHubDoImport")?.addEventListener("click", async () => {
    if (!_PARSED_IMPORT_PACKAGE) return;
    const { data } = _PARSED_IMPORT_PACKAGE;
    const modules = _analyzeImportPackage(data);

    const checkedKeys = new Set();
    document.querySelectorAll("#importHubModulesList input[data-import-key]:checked").forEach(inp => {
      checkedKeys.add(inp.dataset.importKey);
    });

    if (!checkedKeys.size) {
      toast("请至少选择一项需要导入应用的模块", "warn");
      return;
    }

    const doSnapshot = document.getElementById("importHubSnapshotChk")?.checked;
    const btn = document.getElementById("importHubDoImport");
    if (btn) { btn.disabled = true; btn.textContent = "正在应用中…"; }

    try {
      // 1. 自动快照保护（接口路径：backups/config/snapshot/save）
      if (doSnapshot) {
        try {
          await getBridge().apiPost("backups/config/snapshot/save", { note: `智能导入前自动快照_${Date.now()}` }).catch(() => null);
        } catch (_se) {}
      }

      const applied = [];
      for (const m of modules) {
        if (checkedKeys.has(m.key)) {
          const modDef = EXPORT_MODULES.find(x => x.key === m.key);
          if (modDef && modDef.apply) {
            await modDef.apply(m.data);
            applied.push(m.title.replace(/^[^\s]+\s*/, ""));
          }
        }
      }

      toast(`已成功安全导入：${applied.join("、")}`, "ok");
      closeImportHub();
    } catch (err) {
      toast("导入失败: " + (err.message || err), "bad");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "✅ 确认导入所选项目"; }
    }
  });
}

// 暴露到全局，各页面入口均可直接唤起
window.openExportHub = openExportHub;
window.closeExportHub = closeExportHub;
window.openImportHub = openImportHub;
window.closeImportHub = closeImportHub;
window.exportSingleModule = exportSingleModule;
window.exportSpiritsOnly = exportSpiritsOnly;
window.exportShopsOnly = exportShopsOnly;
window.exportTreasuresOnly = exportTreasuresOnly;
window.exportGameRulesOnly = exportGameRulesOnly;
window.initExportHubEvents = initExportHubEvents;
window.initImportHubEvents = initImportHubEvents;
window._analyzeImportPackage = _analyzeImportPackage;
function _formatModalText(msg) {
  if (!msg) return "";
  if (msg.includes("<div") || msg.includes("<strong") || msg.includes("<span") || msg.includes("<br")) {
    // 富文本直通（内部弹窗自拼）：先摘事件处理器属性，防后端文案（文件名/URL）带入的注入
    try {
      return String(msg).replace(/on\w+\s*=/gi, "on_=");
    } catch (e) {
      return "";
    }
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
    if (!data || data.error) throw new Error((data && (data.error || data.msg)) || "群聊列表接口异常");
    RAW_GROUPS = data.groups || data || [];
    renderGroupsTable();
  } catch(e) {
    box.innerHTML = `<tr><td colspan="5" style="color:var(--bad);text-align:center;padding:16px">加载失败: ${esc(e.message)}</td></tr>`;
    try { TAB_DONE.groups = false; } catch (_e) {}
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
    const p1 = typeof loadBackupCfg === "function" ? loadBackupCfg().catch(() => {}) : Promise.resolve();
    const p2 = typeof loadBackups === "function" ? loadBackups("").catch(() => {}) : Promise.resolve();
    if (typeof loadRemoteWebDAVFiles === "function") {
      setTimeout(() => { loadRemoteWebDAVFiles().catch(() => {}); }, 60);
    }
    await Promise.all([p1, p2]);
  },
  imgs: async () => { return loadImages(""); },
  groups: async () => { return loadGroups(); },
  about: async () => { return Promise.resolve(); },
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
  try { if (typeof initExportHubEvents === "function") initExportHubEvents(); } catch (e) {}
  try { if (typeof initImportHubEvents === "function") initImportHubEvents(); } catch (e) {}
  // 直连直访问下首屏前先暖好前缀（共用单航班，防首屏并发各跑 5 前缀的惊群）
  try {
    const _probeBridge = getBridge();
    if (!_probeBridge || (typeof _probeBridge.apiGet === "function" && String(_probeBridge.apiGet).includes("_warmPrefixOnce") === false)) {
      // 仅 fallback 分支有探针
      if (typeof _warmPrefixOnce === "function") { _warmPrefixOnce().catch(() => {}); }
    }
  } catch (e) {}
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
  // 空闲预取：总览首屏后，后台静默预热高频 Tab（用户/奴隶/群聊），切 Tab 即零等待
  const _idlePrefetch = () => {
    try {
      const cand = ["users", "slave", "groups"];
      cand.forEach((t, i) => {
        if (TAB_DONE[t]) return;
        setTimeout(() => {
          if (TAB_DONE[t] || !TAB_LOADERS[t]) return;
          TAB_DONE[t] = true;
          Promise.resolve(TAB_LOADERS[t]()).catch(() => { try { TAB_DONE[t] = false; } catch (e) {} });
        }, 600 + i * 400);
      });
    } catch (e) {}
  };
  try {
    if (typeof requestIdleCallback === "function") requestIdleCallback(_idlePrefetch, { timeout: 1500 });
    else setTimeout(_idlePrefetch, 900);
  } catch (e) { try { setTimeout(_idlePrefetch, 900); } catch (_e) {} }
}

