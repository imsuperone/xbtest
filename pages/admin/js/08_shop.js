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
document.getElementById("btnOpenPersistent")?.addEventListener("click", async () => {
  try { await loadImages("persistent"); } catch (err) { toast("打开失败: " + (err.message || err), "bad"); }
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
  if (e.key === "Escape") {
    closeCmdEditor();
    closeLightbox();
  }
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
  "企鹅": { price: 213250, img: "data/games/img/rides/企鹅.jpg" },
  "伞兵": { price: 500000, img: "data/games/img/rides/伞兵.jpg" },
  "宝驴": { price: 1000000, img: "data/games/img/rides/宝驴.jpg" },
  "保时捷": { price: 1500000, img: "data/games/img/rides/保时捷.jpg" },
  "法拉利": { price: 1500000, img: "data/games/img/rides/法拉利.jpg" },
  "玛莎拉蒂": { price: 1500000, img: "data/games/img/rides/玛莎拉蒂.jpg" },
  "劳斯莱斯": { price: 1500000, img: "data/games/img/rides/劳斯莱斯.jpg" },
  "布加迪威龙": { price: 1500000, img: "data/games/img/rides/布加迪威龙.jpg" },
  "私人航空": { price: 5000000, img: "data/games/img/rides/私人航空.jpg" },
  "老八": { price: 500000, img: "data/games/img/rides/老八.jpg" },
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
          const _key = rar + "|" + it.name;
          let slot = null;
          box.querySelectorAll("[data-pool-item]").forEach((host) => {
            if (!slot && host.dataset && host.dataset.poolItem === _key) slot = host.querySelector("[data-pool-thumb]");
          });
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
      // 显式下发零值：后端见 {atk:0,desc:""} 即删键；省略即保留，清不掉
      clean[k] = { atk, desc };
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
  html += `<div class="hint" style="margin-top:8px">每行一个坐骑，支持改名、改价、删、绑图（图片路径如 data/games/img/rides/企鹅.jpg，留空自动匹配）</div>`;
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
    if (!img) { try { autoImg = `data/games/img/rides/${name}.jpg`; } catch (e) { autoImg = ""; } }
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
    await loadImages("data/games/img/rides");
    // 在根目录顶部显示绑定提示（仅图片可选）
    const _oldTip = document.getElementById("shopPickTip"); if (_oldTip) _oldTip.remove();
    const tip=document.createElement("div"); tip.id="shopPickTip"; tip.style="background:var(--accSoft);border:1px solid var(--acc);padding:8px 12px;border-radius:8px;margin-bottom:10px";
    tip.innerHTML=`<b>为坐骑 "${esc(k)}" 选择内置图：</b> 坐骑目录 data/games/img/rides（png/jpg/gif等），然后 <button class="ghost sm" id="btnShopPickConfirm">确定绑定</button> <button class="ghost sm" id="btnShopPickCancel">取消</button>`;
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
        const r = await postFile("images/upload?dir=" + encodeURIComponent("data/games/img/rides"), {}, file);
        if (r && r.error) throw new Error(r.error);
        const path = (r && (r.path || (r.data && r.data.path))) || ("data/games/img/rides/" + file.name);
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
    await getBridge().apiPost("config/save", { "商城图鉴": { "ride_shop": JSON.stringify(cleanRide) } }).then((r) => {
      if (r && r.error) throw new Error(r.error);
    });
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
      <div><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">图片（坐骑目录 data/games/img/rides，可选，留空自动匹配）：</label>
        <input id="rideAddImg" style="width:100%;padding:6px 10px;border-radius:8px" placeholder="data/games/img/rides/xxx.jpg">
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
        const r = await postFile("images/upload?dir=" + encodeURIComponent("data/games/img/rides"), {}, file);
        if (r && r.error) throw new Error(r.error);
        const path = (r && (r.path || (r.data && r.data.path))) || ("data/games/img/rides/" + file.name);
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
    await loadImages("data/games/img/rides");
    const old = document.getElementById("shopPickTip"); if (old) old.remove();
    const tip = document.createElement("div"); tip.id = "shopPickTip"; tip.style = "background:var(--accSoft);border:1px solid var(--acc);padding:8px 12px;border-radius:8px;margin-bottom:10px";
    tip.innerHTML = `<b>为新坐骑选择内置图：</b> 坐骑目录 data/games/img/rides，然后 <button class="ghost sm" id="btnShopPickConfirm">确定绑定</button> <button class="ghost sm" id="btnShopPickCancel">取消</button>`;
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
  // instant 骨架：内存/内置先画出来（零等待），后台拉取后重绘；盒子永不空白
  try {
    if (!SHOP_RIDE || !Object.keys(SHOP_RIDE).length) {
      SHOP_RIDE = JSON.parse(JSON.stringify(DEFAULT_RIDE_SHOP));
      SHOP_RIDE_CUSTOM = false;
    }
    renderShopRideBox();
  } catch (e) {}
  try { renderPoolBox(); } catch (e) {}
  try { if (typeof renderShop === "function") renderShop(); } catch (e) {}
  try {
    const _pb = document.getElementById("poolWeaponBox");
    if (_pb && !_pb.innerHTML.trim()) _pb.innerHTML = `<div style="text-align:center;padding:16px;color:var(--muted)">武器池加载中…</div>`;
    const _rb = document.getElementById("shopRideBox");
    if (_rb && !_rb.innerHTML.trim()) _rb.innerHTML = `<div style="text-align:center;padding:16px;color:var(--muted)">坐骑商城加载中…</div>`;
  } catch (e) {}
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
      // 宝物新家优先（treasures 结构表），老 treasure_effects 只读兼容
      const _tn = sec["treasures"];
      const _norm1 = (o) => {
        const out = {};
        try {
          Object.entries(o || {}).forEach(([k, v]) => {
            if (v && typeof v === "object" && !Array.isArray(v)) {
              const _t = String(v.type || "");
              out[k] = { effect: String(v.effect || v.desc || ""), type: (["atk", "shield", "pardon", "work", "worth"].includes(_t) ? _t : ""), value: Math.max(0, Number(v.value) || 0) };
            } else if (v && String(v).trim()) {
              out[k] = { effect: String(v).trim(), type: "", value: 0 };
            }
          });
        } catch (e) {}
        return out;
      };
      const _newEff = _norm1((_tn && typeof _tn === "object" && !Array.isArray(_tn)) ? _tn : null);
      if (Object.keys(_newEff).length) { window._TREAS_EFF = _newEff; }
      else {
        const _te = sec["treasure_effects"];
        if (_te && typeof _te === "object" && !Array.isArray(_te)) window._TREAS_EFF = _norm1(_te);
        else if (typeof _te === "string" && _te.trim()) { try { const d = JSON.parse(_te); if (d && typeof d === "object") window._TREAS_EFF = _norm1(d); else window._TREAS_EFF = {}; } catch (e) { window._TREAS_EFF = {}; } }
        else window._TREAS_EFF = window._TREAS_EFF || {};
      }
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
    // 失败兜底：还停留在加载占位的盒子给可重试错误（骨架已画出时不受影响）
    try {
      ["poolWeaponBox", "shopRideBox"].forEach((id) => {
        const _b = document.getElementById(id);
        if (_b && /加载中/.test(_b.innerHTML || "")) _b.innerHTML = `<div style="text-align:center;padding:16px;color:var(--bad)">加载失败，可<button class="ghost sm" onclick="loadShops()">重试</button></div>`;
      });
    } catch (_e) {}
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
  }; inp.click();
}
document.getElementById("btnShopLoad")?.addEventListener("click", loadShops);
document.getElementById("btnShopSave")?.addEventListener("click", saveShops);
document.getElementById("btnShopExport")?.addEventListener("click", exportShops);
document.getElementById("btnShopImport")?.addEventListener("click", importShops);
