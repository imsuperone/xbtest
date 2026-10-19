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
    // 单次 apiGet（读接口 GET,POST 双方法直连，无回退重放）
    const r = await getBridge().apiGet("export", { kind: "images", path: p });
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
      toast("已导出 " + outFn, "ok");
      return;
    }

    const fallbackStr = typeof r === "string" ? r : JSON.stringify(r, null, 2);
    triggerExportResult({
      filename: outFn.replace(/\.zip$/, ".json"),
      mime: "application/json;charset=utf-8",
      rawText: fallbackStr
    });
    toast("已导出 " + outFn, "ok");
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
  if (!(await uiConfirm("再次确认删除 \"" + sel + "\"？", "再次确认删除"))) return;
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

// 精灵图鉴（地图/属性在图鉴列表页签分系统保存恢复，道具在商城页；加载按钮已删，Tab 打开自动拉取）
document.getElementById("btnSpiritExport")?.addEventListener("click", exportSpirits);
document.getElementById("btnPresetExport")?.addEventListener("click", exportPreset);
document.getElementById("btnPresetImport")?.addEventListener("click", importPreset);
document.getElementById("btnSpiritImport")?.addEventListener("click", importSpirits);

// 商城图鉴 (每商城独立栏 自由增删重命名+图片绑定)
const DEFAULT_RIDE_SHOP = {
  "企鹅": { price: 213250, img: "data/img/rides/企鹅.jpg", buff: 6, buff_type: "work" },
  "伞兵": { price: 500000, img: "data/img/rides/伞兵.jpg", buff: 10, buff_type: "atk" },
  "宝驴": { price: 1000000, img: "data/img/rides/宝驴.jpg", buff: 10, buff_type: "work" },
  "保时捷": { price: 1500000, img: "data/img/rides/保时捷.jpg", buff: 10, buff_type: "travel" },
  "法拉利": { price: 1500000, img: "data/img/rides/法拉利.jpg", buff: 10, buff_type: "travel" },
  "玛莎拉蒂": { price: 1500000, img: "data/img/rides/玛莎拉蒂.jpg", buff: 10, buff_type: "travel" },
  "劳斯莱斯": { price: 1500000, img: "data/img/rides/劳斯莱斯.jpg", buff: 10, buff_type: "work" },
  "布加迪威龙": { price: 1500000, img: "data/img/rides/布加迪威龙.jpg", buff: 10, buff_type: "atk" },
  "私人航空": { price: 5000000, img: "data/img/rides/私人航空.jpg", buff: 15, buff_type: "all" },
  "老八": { price: 500000, img: "data/img/rides/老八.jpg", buff: 10, buff_type: "atk" },
};

const RARITY_DEFAULT_ATK = {
  "SSR": 300,
  "SR": 150,
  "R": 50,
};

const DEFAULT_WEAPON_ATTRS = {
  // SSR (7)
  "鬼泪村正": { atk: 500, desc: "东瀛妖刀，斩风断水，嗜血封喉" },
  "雷鸣剑": { atk: 450, desc: "引九天神雷，剑气如龙" },
  "神使沧溟": { atk: 420, desc: "海神圣物，碧波万顷化为护体剑罡" },
  "炎宿朱雀": { atk: 400, desc: "四象朱雀精魂铸造，烈焰焚尽万物" },
  "祝融": { atk: 380, desc: "火神本命神兵，炽热流金" },
  "老八脑!": { atk: 350, desc: "奥利给战神之力，秘制能量震撼全场" },
  "钻石剑": { atk: 320, desc: "璀璨夺目，坚不可摧的绝世名锋" },

  // SR (20)
  "双弦寒冰弓": { atk: 200, desc: "极北万年玄冰雕琢，矢出霜华凝滞" },
  "绝地光剑": { atk: 195, desc: "原力凝聚的高能离子刃，斩断一切" },
  "西斯光剑": { atk: 195, desc: "暗黑原力猩红光刃，狂暴而凌厉" },
  "村正": { atk: 190, desc: "千锤百炼的锋刃，隐隐散发血色微光" },
  "烈炎": { atk: 185, desc: "纯阳烈焰凝聚的长刃，触之焦灼" },
  "追雷弓": { atk: 185, desc: "伴雷而鸣，箭矢引落电光石火" },
  "寒晶苦无": { atk: 180, desc: "幽暗阴影中的致命杀招，彻骨冰冷" },
  "绝寒弓": { atk: 180, desc: "冻结生机的霜雪之矢，穿云贯日" },
  "雷元剑": { atk: 180, desc: "雷元淬炼而成，出鞘隐带电闪雷鸣" },
  "烈焰刀": { atk: 175, desc: "炽焰缠绕之刀，劈砍伴随烈焰轰鸣" },
  "苍雪剑": { atk: 175, desc: "剑身宛若白雪皑皑，剑出寒气逼人" },
  "永恒之晶": { atk: 170, desc: "封印古老秘术的棱晶，魔力流转不休" },
  "疾风弓": { atk: 170, desc: "轻巧迅捷，箭出如长风呼啸疾驰" },
  "爆炎辣锅": { atk: 165, desc: "香辣爆裂，特级厨艺化为刚猛爆发" },
  "龙鳞扇": { atk: 165, desc: "真龙之鳞编织，扇风如龙威浩荡" },
  "火漩团扇": { atk: 160, desc: "挥舞激荡烈火狂岚，扇卷火舌席卷敌阵" },
  "琅君玉箫": { atk: 155, desc: "温润青玉所铸，箫声激荡暗藏杀机" },
  "爱疯20": { atk: 150, desc: "超前黑科技武装，量子信号全频压制" },
  "秘制豪串": { atk: 140, desc: "江湖豪杰最爱，饱腹之余豪气干云" },
  "铁剑": { atk: 120, desc: "百炼精铁锻造，朴实沉稳的防身利器" },

  // R (15)
  "光剑强化型": { atk: 80, desc: "强化能量回路的光剑，嗡鸣作响" },
  "尚方宝剑": { atk: 80, desc: "官府佩剑，颇有几分威严与锋芒" },
  "冰阵剑": { atk: 75, desc: "附带基础冰阵刻印，稍显凌厉" },
  "大太刀": { atk: 70, desc: "沉重大太刀，力道刚猛沉实" },
  "火焰刀": { atk: 70, desc: "粗铁涂覆火油之刀，灼灼生烟" },
  "大锤": { atk: 65, desc: "粗重铁锤，砸下势大力沉" },
  "破魔矢": { atk: 65, desc: "巫祝祈福之箭矢，微破邪气" },
  "雷弓": { atk: 65, desc: "弓臂缠绕铜丝，引微弱电光" },
  "上上签": { atk: 60, desc: "大吉大利，福星高照逢凶化吉" },
  "寒冰弓": { atk: 60, desc: "简朴寒木弓，射程与韧性兼备" },
  "旋风扇": { atk: 55, desc: "轻巧羽扇，挥起微弱旋风" },
  "火之扇": { atk: 55, desc: "微热小扇，带着淡淡火星" },
  "豪肉叉": { atk: 50, desc: "野外狩猎叉具，结实耐用" },
  "青箫": { atk: 45, desc: "寻常竹箫，清幽悦耳" },
  "木剑": { atk: 30, desc: "新手练习用木剑，安全实用" },
};

let SHOP_RIDE = {};
let SHOP_DIRTY = false;
let SHOP_RIDE_CUSTOM = true;   // false=当前展示的是内置默认（未自定义），保存后即转为自定义
let POOL_WEAPONS = { SSR: [], SR: [], R: [] };   // 抽奖武器池文件（可编辑：改名/改稀有度/删除/上传）

// 缩略图内存缓存与并发受控队列（避免并发大量拉取阻塞界面）
const _SHOP_THUMB_CACHE = new Map();
const _SHOP_THUMB_QUEUE = [];
let _SHOP_THUMB_FETCHING = 0;
const _MAX_CONCURRENT_THUMBS = 4;

function _processShopThumbQueue() {
  while (_SHOP_THUMB_FETCHING < _MAX_CONCURRENT_THUMBS && _SHOP_THUMB_QUEUE.length > 0) {
    const task = _SHOP_THUMB_QUEUE.shift();
    if (!task) break;
    const { key, isPath, callback } = task;
    if (_SHOP_THUMB_CACHE.has(key)) {
      try { callback(_SHOP_THUMB_CACHE.get(key)); } catch (e) {}
      continue;
    }
    _SHOP_THUMB_FETCHING++;
    const param = isPath ? { path: key } : { name: key };
    getBridge().apiPost("images/preview", param).then((r) => {
      const thumb = r && (r.thumb || (r.data && r.data.thumb));
      if (thumb) {
        _SHOP_THUMB_CACHE.set(key, thumb);
        try { callback(thumb); } catch (e) {}
      }
    }).catch(() => {}).finally(() => {
      _SHOP_THUMB_FETCHING--;
      _processShopThumbQueue();
    });
  }
}

function requestShopThumb(key, isPath, callback) {
  if (!key) return;
  if (_SHOP_THUMB_CACHE.has(key)) {
    try { callback(_SHOP_THUMB_CACHE.get(key)); } catch (e) {}
    return;
  }
  _SHOP_THUMB_QUEUE.push({ key, isPath, callback });
  _processShopThumbQueue();
}

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
    const defType = (DEFAULT_RIDE_SHOP[k] && DEFAULT_RIDE_SHOP[k].buff_type) || "all";
    if (v && typeof v === "object" && !Array.isArray(v)) {
      let bt = v.buff_type;
      if (!bt || (bt === "all" && defType !== "all")) {
        bt = defType;
      }
      out[k] = {
        price: Number(v.price) || 0,
        img: String(v.img || ""),
        buff: (v.buff !== undefined && v.buff !== "" && !isNaN(Number(v.buff))) ? Number(v.buff) : undefined,
        buff_type: String(bt || "all")
      };
    } else {
      out[k] = { price: Number(v) || 0, img: "", buff: undefined, buff_type: defType };
    }
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
      const defA = (DEFAULT_WEAPON_ATTRS && DEFAULT_WEAPON_ATTRS[it.name]) || {};
      const defAtk = defA.atk || (RARITY_DEFAULT_ATK[r] || 50);
      const curAtk = (a.atk !== undefined && a.atk !== null && a.atk !== 0 && a.atk !== "") ? Number(a.atk) : defAtk;
      const curDesc = (a.desc !== undefined && a.desc !== null && a.desc !== "") ? String(a.desc) : (defA.desc || "");
      POOL_ATTRS[it.name] = { atk: curAtk, desc: curDesc };
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
let POOL_FILTER_RAR = "ALL";
let POOL_SEARCH_KW = "";
function renderPoolBox(forceOpen = false) {
  const box = document.getElementById("poolWeaponBox");
  if (!box) return;
  if (typeof bindShopSubnavOnce === "function") bindShopSubnavOnce();
  if (typeof updateShopBadges === "function") updateShopBadges();

  const total = poolCount();
  const rarList = ["SSR", "SR", "R"];
  const kw = (POOL_SEARCH_KW || "").toLowerCase().trim();

  let html = `<div class="shop-section-card">`;
  html += `
    <div class="shop-section-head">
      <div class="shop-section-title-wrap">
        <div class="shop-section-title">
          <span>🎰 抽奖武器池</span>
          <span class="m3-badge-counter">${total} 件</span>
        </div>
        <div class="shop-section-subtitle">武器即图片文件本身；改名改文件名，稀有度改所在目录；攻击加成参战、描述进详情</div>
      </div>
      <div class="shop-section-actions">
        <input class="m3-input sm" id="poolSearchInput" placeholder="🔍 搜索武器名..." value="${esc(POOL_SEARCH_KW)}" style="width:140px">
        <button class="btn sm" id="btnPoolUploadTop">＋ 添加武器</button>
        <button class="ghost sm" id="btnPoolAttrsSave">💾 保存武器属性</button>
        <button class="ghost sm" id="btnPoolAttrsReset">↩️ 恢复默认</button>
      </div>
    </div>
  `;

  // 稀有度筛选分段条
  html += `
    <div class="m3-segmented-control" style="margin-bottom:14px;max-width:520px">
      <button class="seg-item ${POOL_FILTER_RAR === 'ALL' ? 'active' : ''}" data-pool-filter="ALL">
        <span>✨ 全部 (${total})</span>
      </button>
      ${rarList.map(r => {
        const count = ((POOL_WEAPONS && POOL_WEAPONS[r]) || []).length;
        return `<button class="seg-item ${POOL_FILTER_RAR === r ? 'active' : ''}" data-pool-filter="${r}">
          <span>${r === 'SSR' ? '👑 SSR' : (r === 'SR' ? '💎 SR' : '🗡️ R')} (${count})</span>
        </button>`;
      }).join('')}
    </div>
  `;

  const displayRars = POOL_FILTER_RAR === "ALL" ? rarList : [POOL_FILTER_RAR];
  let renderedCount = 0;

  html += `<div class="shop-cards-grid weapon-pool-grid">`;
  displayRars.forEach((rar) => {
    const items = (POOL_WEAPONS && POOL_WEAPONS[rar]) || [];
    items.forEach((it) => {
      const name = it.name;
      if (kw && !name.toLowerCase().includes(kw)) return;
      renderedCount++;
      const _ext = ((it.file || "").split(".").pop() || "").toLowerCase();
      const _sz = Number(it.size) || 0;
      const _kb = _sz ? (_sz >= 1024 * 1024 ? (_sz / 1024 / 1024).toFixed(1) + "MB" : Math.max(1, Math.round(_sz / 1024)) + "KB") : "";
      const defA = (DEFAULT_WEAPON_ATTRS && DEFAULT_WEAPON_ATTRS[name]) || {};
      const defAtk = defA.atk || (RARITY_DEFAULT_ATK[rar] || 50);
      const pa = (POOL_ATTRS && POOL_ATTRS[name]) || {};
      const _paAtk = (pa.atk !== undefined && pa.atk !== null && pa.atk !== 0 && pa.atk !== "") ? Math.max(0, Number(pa.atk) || 0) : defAtk;
      const _paDesc = (pa.desc !== undefined && pa.desc !== null && pa.desc !== "") ? String(pa.desc) : String(defA.desc || "");
      const thumb = it.thumb || _SHOP_THUMB_CACHE.get(name) || "";
      if (thumb) it.thumb = thumb;

      html += `
        <div class="weapon-item-card rarity-${rar.toLowerCase()}" data-pool-item="${esc(rar)}|${esc(name)}">
          <div class="weapon-card-header">
            <div class="weapon-title-area">
              <span class="rarity-chip rarity-chip-${rar.toLowerCase()}">${esc(rar)}</span>
              <span class="weapon-name-display" data-pool-rename title="点击改名">✦ ${esc(name)}</span>
            </div>
            <div class="weapon-quick-actions">
              <select class="m3-select weapon-rar-select" data-pool-rar title="切换稀有度" style="padding:2px 6px;font-size:12px;font-weight:700">
                ${rarList.map(r => `<option value="${r}"${r === rar ? ' selected' : ''}>${r}</option>`).join('')}
              </select>
              <button class="m3-sort-btn" data-pool-up title="上移排序">▲</button>
              <button class="m3-sort-btn" data-pool-down title="下移排序">▼</button>
              <button class="m3-icon-btn m3-btn-danger" data-pool-del title="删除此武器">🗑️</button>
            </div>
          </div>
          <div class="weapon-card-top">
            <div class="weapon-thumb-wrap" data-pool-thumb-wrap="${esc(name)}" data-pool-thumb="${esc(name)}" title="点击放大预览">
              ${thumb ? `<img src="${esc(thumb)}" alt="${esc(name)}">` : `<span class="rarity-chip rarity-chip-${rar.toLowerCase()}">${esc(rar)}</span>`}
            </div>
            <div class="weapon-card-main">
              <div class="ride-row-split" style="gap:8px">
                <div class="input-with-label" title="攻击加成数值" style="flex:0 0 145px;min-width:140px">
                  <span class="input-label" style="font-size:11.5px;font-weight:700">⚔️ 攻击</span>
                  <input class="m3-input" type="number" data-pool-atk value="${esc(_paAtk)}" style="flex:1;min-width:0;width:100%;padding:4px 6px;text-align:right;font-weight:700">
                </div>
                <input class="m3-input weapon-desc-input" data-pool-desc value="${esc(_paDesc)}" placeholder="背景/特性描述..." style="flex:1;min-width:0" title="武器特性与背景描述">
              </div>
            </div>
          </div>
          <div class="weapon-card-footer" style="display:flex;align-items:center;justify-content:space-between;gap:6px;padding-top:6px;border-top:1px dashed var(--line)">
            <div style="display:flex;gap:6px;flex-wrap:wrap">
              <button class="ghost sm" data-pool-rename>✏️ 改名</button>
              <button class="ghost sm" data-pool-pick-builtin>📂 内置换图</button>
              <button class="ghost sm" data-pool-pick-upload>⬆️ 本地换图</button>
            </div>
            <span class="weapon-file-hint">${esc(_ext)}${_kb ? " · " + esc(_kb) : ""}</span>
          </div>
        </div>
      `;
    });
  });
  html += `</div>`;

  if (renderedCount === 0) {
    html += `<div class="hint" style="text-align:center;padding:24px 0">当前稀有度分类或搜索条件下无武器</div>`;
  }
  html += `</div>`;
  box.innerHTML = html;

  // 受控队列懒加载武器缩略图（并发限流 4，防卡顿与阻塞）
  displayRars.forEach((rar) => {
    ((POOL_WEAPONS && POOL_WEAPONS[rar]) || []).forEach((it) => {
      const nm = it.name;
      if (kw && !nm.toLowerCase().includes(kw)) return;
      if (it.thumb || _SHOP_THUMB_CACHE.has(nm)) return;
      requestShopThumb(nm, false, (thumb) => {
        it.thumb = thumb;
        box.querySelectorAll(`[data-pool-thumb-wrap="${CSS.escape ? CSS.escape(nm) : nm}"]`).forEach((slot) => {
          slot.innerHTML = `<img src="${esc(thumb)}" alt="${esc(nm)}">`;
        });
      });
    });
  });

  // 搜索框事件
  const sInp = document.getElementById("poolSearchInput");
  if (sInp) {
    sInp.addEventListener("input", (e) => {
      POOL_SEARCH_KW = e.target.value;
      renderPoolBox(true);
      const reInp = document.getElementById("poolSearchInput");
      if (reInp) { reInp.focus(); reInp.selectionStart = reInp.selectionEnd = reInp.value.length; }
    });
  }

  // 稀有度筛选按钮
  box.querySelectorAll("[data-pool-filter]").forEach((b) => {
    b.addEventListener("click", () => {
      POOL_FILTER_RAR = b.dataset.poolFilter;
      renderPoolBox(true);
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
      const cached = (() => {
        try {
          if (_SHOP_THUMB_CACHE.has(nm)) return _SHOP_THUMB_CACHE.get(nm);
          for (const r of ["SSR", "SR", "R"]) {
            const f = ((POOL_WEAPONS && POOL_WEAPONS[r]) || []).find((x) => x.name === nm);
            if (f && f.thumb) return f.thumb;
          }
        } catch (err) {}
        return "";
      })();
      if (cached) { showLightbox(cached, nm); return; }
      try {
        const r = await getBridge().apiPost("images/preview", { name: nm });
        const thumb = r && (r.thumb || (r.data && r.data.thumb));
        if (r && r.error) throw new Error(r.error);
        if (thumb) {
          _SHOP_THUMB_CACHE.set(nm, thumb);
          showLightbox(thumb, nm);
        } else toast("无预览", "bad");
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
  if (icon) icon.textContent = "";
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
let RIDE_SEARCH_KW = "";
let CURRENT_SHOP_SUBTAB = "ride";

function bindShopSubnavOnce() {
  const bar = document.getElementById("shopSubnavBar");
  if (!bar || bar.dataset.bound) return;
  bar.dataset.bound = "1";
  bar.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-shop-subtab]");
    if (!btn) return;
    const tab = btn.dataset.shopSubtab;
    setShopSubtab(tab);
  });
}

function setShopSubtab(tab) {
  CURRENT_SHOP_SUBTAB = tab || "ride";
  document.querySelectorAll("#shopSubnavBar .seg-item").forEach((b) => {
    b.classList.toggle("active", b.dataset.shopSubtab === CURRENT_SHOP_SUBTAB);
  });
  const rBox = document.getElementById("shopRideBox");
  const pBox = document.getElementById("poolWeaponBox");
  const sBox = document.getElementById("shopSpiritBox");
  if (rBox) rBox.style.display = (CURRENT_SHOP_SUBTAB === "ride" || CURRENT_SHOP_SUBTAB === "all") ? "" : "none";
  if (pBox) pBox.style.display = (CURRENT_SHOP_SUBTAB === "pool" || CURRENT_SHOP_SUBTAB === "all") ? "" : "none";
  if (sBox) sBox.style.display = (CURRENT_SHOP_SUBTAB === "spirit" || CURRENT_SHOP_SUBTAB === "all") ? "" : "none";
  updateShopBadges();
}

function updateShopBadges() {
  const rB = document.getElementById("shopRideBadge");
  if (rB) rB.textContent = Object.keys(SHOP_RIDE || {}).length;
  const pB = document.getElementById("shopPoolBadge");
  if (pB) pB.textContent = poolCount();
  const sB = document.getElementById("shopSpiritBadge");
  const spData = (typeof SPIRIT !== "undefined" && SPIRIT) ? SPIRIT : (window.SPIRIT || {});
  const spShop = (spData && spData.shop) || {};
  if (sB) sB.textContent = Object.keys(spShop).length;
}

function renderShopRideBox(forceOpen = false) {
  const box = document.getElementById("shopRideBox");
  if (!box) return;
  bindShopSubnavOnce();
  updateShopBadges();

  const allEntries = Object.entries(SHOP_RIDE);
  const kw = (RIDE_SEARCH_KW || "").toLowerCase().trim();
  const entries = kw ? allEntries.filter(([k]) => k.toLowerCase().includes(kw)) : allEntries;

  let html = `<div class="shop-section-card">`;
  html += `
    <div class="shop-section-head">
      <div class="shop-section-title-wrap">
        <div class="shop-section-title">
          <span>🐎 坐骑商城</span>
          <span class="m3-badge-counter">${allEntries.length} 件</span>
        </div>
        <div class="shop-section-subtitle">自定义坐骑售价、加成属性（战力/打工/旅行）、图片路径与新增坐骑</div>
      </div>
      <div class="shop-section-actions">
        <input class="m3-input sm" id="rideSearchInput" placeholder="🔍 搜索坐骑名..." value="${esc(RIDE_SEARCH_KW)}" style="width:140px">
        <button class="btn sm" id="btnRideAddTop">＋ 添加坐骑</button>
        <button class="ghost sm" id="btnRideSaveTop">💾 保存坐骑</button>
        <button class="ghost sm" id="btnRideReset">↩️ 恢复默认</button>
      </div>
    </div>
  `;

  if (!entries.length) {
    if (kw) {
      html += `<div class="hint" style="text-align:center;padding:24px 0">无匹配坐骑，可清空搜索词</div>`;
    } else {
      html += `<div class="hint" style="text-align:center;padding:24px 0">当前为空，运行时使用内置坐骑（${Object.keys(DEFAULT_RIDE_SHOP).length} 种）；可点击上方「＋ 添加坐骑」或「恢复默认」</div>`;
    }
  } else {
    html += `<div class="shop-cards-grid">`;
    entries.forEach(([name, val]) => {
      let price = 0, img = "", buff = undefined, buff_type = "all";
      if (val && typeof val === "object" && !Array.isArray(val)) {
        price = val.price ?? 0;
        img = val.img ?? "";
        buff = val.buff;
        buff_type = val.buff_type || "all";
      } else {
        price = Number(val) || 0;
      }
      let autoImg = "";
      if (!img) { try { autoImg = `data/img/rides/${name}.jpg`; } catch (e) { autoImg = ""; } }
      const showImg = img || autoImg;
      const calcDefaultBuff = (p) => {
        p = Number(p) || 0;
        if (p >= 2000000) return 15;
        if (p >= 500000) return 10;
        if (p >= 100000) return 6;
        if (p > 0) return 3;
        return 0;
      };
      const curBuff = (buff !== undefined && buff !== "" && !isNaN(Number(buff))) ? Number(buff) : calcDefaultBuff(price);

      const cachedRideThumb = showImg ? _SHOP_THUMB_CACHE.get(showImg) : "";

      html += `
        <div class="ride-item-card" data-ride-item="${esc(name)}">
          <div class="ride-card-top">
            <div class="ride-thumb-wrap" data-ride-thumb-wrap="${esc(name)}" ${showImg ? `data-ride-view="${esc(showImg)}" title="点击放大图片"` : `title="暂无图片"`}>
              ${cachedRideThumb ? `<img src="${esc(cachedRideThumb)}" alt="${esc(name)}">` : (showImg ? `<div class="thumb-loading-ph">🐎</div>` : `<div class="ride-thumb-empty">🐎</div>`)}
              ${showImg ? `<span class="thumb-zoom-icon">🔍</span>` : ``}
            </div>
            <div class="ride-card-info">
              <div class="ride-row-split">
                <input class="m3-input ride-name-input" data-ride-name value="${esc(name)}" placeholder="坐骑名称" title="坐骑名称">
                <button class="m3-icon-btn m3-btn-danger" data-ride-del="${esc(name)}" title="删除此坐骑">🗑️</button>
              </div>
              <div class="ride-row-split" style="gap:6px">
                <div class="input-with-label" title="购买所需金币" style="flex:1;min-width:0">
                  <span class="input-label">💰 价格</span>
                  <input class="m3-input" type="number" data-ride-price value="${esc(price)}" style="flex:1;min-width:40px;width:100%">
                </div>
                <div class="input-with-label" title="乘坐加成百分比（直接影响战力、搬砖工钱、远征金币）" style="flex:0 0 95px">
                  <span class="input-label">⚡ 加成</span>
                  <input class="m3-input" type="number" data-ride-buff value="${esc(curBuff)}" style="width:38px;padding:2px 2px;text-align:center">
                  <span class="input-unit">%</span>
                </div>
              </div>
              <div class="ride-buff-type-row">
                <select class="m3-select" data-ride-buff-type title="加成类型选择">
                  <option value="all"${buff_type === "all" ? " selected" : ""}>⭐ 综合全能 (战力+打工+旅行)</option>
                  <option value="atk"${buff_type === "atk" ? " selected" : ""}>⚔️ 战力加成</option>
                  <option value="work"${buff_type === "work" ? " selected" : ""}>💼 打工收益</option>
                  <option value="travel"${buff_type === "travel" ? " selected" : ""}>🌍 旅行金币</option>
                </select>
              </div>
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:6px">
            <input class="m3-input ride-img-input" data-ride-img value="${esc(img)}" placeholder="图片相对路径（留空自动匹配 data/img/rides/${esc(name)}.jpg）">
            <div class="ride-card-actions">
              <div style="display:flex;gap:6px">
                <button class="ghost sm" data-ride-pick-builtin="${esc(name)}">📂 内置选图</button>
                <button class="ghost sm" data-ride-pick="${esc(name)}">⬆️ 上传绑图</button>
              </div>
              <span style="font-size:11.5px;color:var(--acc);font-weight:600">加成 +${esc(curBuff)}%</span>
            </div>
          </div>
        </div>
      `;
    });
    html += `</div>`;
  }
  html += `</div>`;
  box.innerHTML = html;

  // 批量受控队列加载坐骑缩略图（并发限流 4，带内存缓存）
  entries.forEach(([name, val]) => {
    let img = (val && typeof val === "object" && !Array.isArray(val)) ? (val.img ?? "") : "";
    let autoImg = "";
    if (!img) { try { autoImg = `data/img/rides/${name}.jpg`; } catch (e) { autoImg = ""; } }
    const showImg = img || autoImg;
    if (!showImg || _SHOP_THUMB_CACHE.has(showImg)) return;
    requestShopThumb(showImg, true, (thumb) => {
      const card = box.querySelector(`[data-ride-item="${esc(name)}"]`);
      const slot = card ? card.querySelector(".ride-thumb-wrap") : null;
      if (slot) {
        slot.innerHTML = `<img src="${esc(thumb)}" alt="${esc(name)}"><span class="thumb-zoom-icon">🔍</span>`;
      }
    });
  });

  // 搜索框事件
  const sInp = document.getElementById("rideSearchInput");
  if (sInp) {
    sInp.addEventListener("input", (e) => {
      RIDE_SEARCH_KW = e.target.value;
      renderShopRideBox(true);
      const reInp = document.getElementById("rideSearchInput");
      if (reInp) { reInp.focus(); reInp.selectionStart = reInp.selectionEnd = reInp.value.length; }
    });
  }

  box.querySelectorAll("[data-ride-name]").forEach(inp => inp.addEventListener("change", (e) => {
    const old = e.target.closest("[data-ride-item]").dataset.rideItem;
    const nn = e.target.value.trim();
    if (!nn || nn === old) { e.target.value = old; return; }
    if (SHOP_RIDE[nn] !== undefined) { toast("已存在同名坐骑", "bad"); e.target.value = old; return; }
    SHOP_RIDE[nn] = SHOP_RIDE[old]; delete SHOP_RIDE[old]; SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true);
  }));

  box.querySelectorAll("[data-ride-price]").forEach(inp => inp.addEventListener("change", (e) => {
    const k = e.target.closest("[data-ride-item]").dataset.rideItem;
    const v = SHOP_RIDE[k];
    const p = Number(e.target.value) || 0;
    if (v && typeof v === "object") SHOP_RIDE[k].price = p; else SHOP_RIDE[k] = { price: p };
    SHOP_DIRTY=true; syncShopRaw();
  }));

  box.querySelectorAll("[data-ride-buff]").forEach(inp => inp.addEventListener("change", (e) => {
    const k = e.target.closest("[data-ride-item]").dataset.rideItem;
    const v = SHOP_RIDE[k];
    const b = Number(e.target.value) || 0;
    if (v && typeof v === "object") SHOP_RIDE[k].buff = b; else SHOP_RIDE[k] = { price: Number(v)||0, buff: b };
    SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true);
  }));

  box.querySelectorAll("[data-ride-buff-type]").forEach(sel => sel.addEventListener("change", (e) => {
    const k = e.target.closest("[data-ride-item]").dataset.rideItem;
    const v = SHOP_RIDE[k];
    const bt = sel.value;
    if (v && typeof v === "object") SHOP_RIDE[k].buff_type = bt; else SHOP_RIDE[k] = { price: Number(v)||0, buff_type: bt };
    SHOP_DIRTY=true; syncShopRaw();
  }));

  box.querySelectorAll("[data-ride-img]").forEach(inp => inp.addEventListener("change", (e) => {
    const k = e.target.closest("[data-ride-item]").dataset.rideItem;
    const v = SHOP_RIDE[k];
    const img = e.target.value.trim();
    if (v && typeof v === "object") { v.img = img; }
    else { SHOP_RIDE[k] = { price: Number(v)||0, img }; }
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
    window.SHOP_PICK_TARGET = k;
    toast("已进入坐骑图片目录，请单击选中后点“确定绑定”","ok");
    document.querySelectorAll(".tabs button").forEach(x=>x.classList.remove("on"));
    const rb=document.querySelector("[data-tab=\"imgs\"]"); if(rb) rb.classList.add("on");
    document.querySelectorAll(".tab").forEach(x=>x.classList.remove("on"));
    const tab=document.getElementById("tab-imgs"); if(tab) tab.classList.add("on");
    await loadImages("data/img/rides");
    const _oldTip = document.getElementById("shopPickTip"); if (_oldTip) _oldTip.remove();
    const tip=document.createElement("div"); tip.id="shopPickTip"; tip.style="background:var(--accSoft);border:1px solid var(--acc);padding:8px 12px;border-radius:8px;margin-bottom:10px";
    tip.innerHTML=`<b>为坐骑 "${esc(k)}" 选择内置图：</b> 坐骑目录 data/img/rides，然后 <button class="ghost sm" id="btnShopPickConfirm">确定绑定</button> <button class="ghost sm" id="btnShopPickCancel">取消</button>`;
    const panel=document.querySelector("#tab-imgs .panel"); if(panel) panel.prepend(tip);
    document.getElementById("btnShopPickConfirm")?.addEventListener("click", ()=>{
      const sel=IMG_SELECTED;
      if(!sel){ toast("请先选中图片文件","bad"); return; }
      const ext=(sel.split(".").pop()||"").toLowerCase();
      if(!["png","jpg","jpeg","gif","webp","bmp","ico"].includes(ext)){ toast("请选择图片文件","bad"); return; }
      if(window._imgIsDir && window._imgIsDir(sel)){ toast("不能选择文件夹","bad"); return; }
      const v=SHOP_RIDE[k];
      if(v && typeof v==="object") SHOP_RIDE[k].img=sel; else SHOP_RIDE[k]={price:Number(v)||0, img:sel};
      SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true); toast("已绑定 "+sel+"，需保存","ok");
      tip.remove(); window.SHOP_PICK_TARGET=null;
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
        SHOP_RIDE[k] = (typeof SHOP_RIDE[k]==="object"? {...SHOP_RIDE[k], img: path} : {price: Number(SHOP_RIDE[k])||0, img: path});
        SHOP_DIRTY=true; syncShopRaw(); renderShopRideBox(true); toast("图片已上传并绑定，需保存","ok");
      } catch(err){ toast("上传失败:"+(err.message||err),"bad");}
    };
    inp.click();
  }));

  box.querySelectorAll("[data-ride-view]").forEach((b) => b.addEventListener("click", async () => {
    const p = b.dataset.rideView;
    if (!p) return;
    if (_SHOP_THUMB_CACHE.has(p)) {
      showLightbox(_SHOP_THUMB_CACHE.get(p), p.split("/").pop());
      return;
    }
    try {
      const r = await getBridge().apiPost("images/preview", { path: p });
      const thumb = r && (r.thumb || (r.data && r.data.thumb));
      if (r && r.error) throw new Error(r.error);
      if (thumb) {
        _SHOP_THUMB_CACHE.set(p, thumb);
        showLightbox(thumb, p.split("/").pop());
      } else toast("无预览", "bad");
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
          const item = { price: Number(v.price) || 0 };
          if (v.img) item.img = v.img;
          if (v.buff !== undefined && v.buff !== "") item.buff = Number(v.buff);
          if (v.buff_type && v.buff_type !== "all") item.buff_type = v.buff_type;
          cleanRide[k] = item;
        } else cleanRide[k] = Number(v) || 0;
      });
      await getBridge().apiPost("config/save", { "商城图鉴": { "ride_shop": JSON.stringify(cleanRide) } });
      SHOP_DIRTY = false; SHOP_RIDE_CUSTOM = true;
      syncShopRaw(); renderShopRideBox(true);
      toast("已恢复默认", "ok");
    } catch (e) { toast("恢复失败: " + e.message, "bad"); }
  });
}

// 添加坐骑表单窗：名称 + 价格 + 加成 + 图片路径一次填完
function openRideAddModal() {
  const modal = document.getElementById("appModal");
  if (!modal) return;
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");
  if (icon) icon.textContent = "";
  if (title) title.textContent = "添加坐骑";
  if (inputWrap) inputWrap.style.display = "none";
  content.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:12px">
      <div>
        <label style="font-size:12px;font-weight:600;color:var(--text);display:block;margin-bottom:4px">坐骑名称：</label>
        <input class="m3-input" id="rideAddName" style="width:100%" placeholder="如：赤兔马">
      </div>
      <div style="display:flex;gap:10px">
        <div style="flex:1">
          <label style="font-size:12px;font-weight:600;color:var(--text);display:block;margin-bottom:4px">售价（金币）：</label>
          <input class="m3-input" id="rideAddPrice" type="number" value="500000" style="width:100%">
        </div>
        <div style="width:110px">
          <label style="font-size:12px;font-weight:600;color:var(--text);display:block;margin-bottom:4px">加成 (%)：</label>
          <input class="m3-input" id="rideAddBuff" type="number" value="10" style="width:100%">
        </div>
      </div>
      <div>
        <label style="font-size:12px;font-weight:600;color:var(--text);display:block;margin-bottom:4px">加成类型：</label>
        <select class="m3-select" id="rideAddBuffType" style="width:100%">
          <option value="all">⭐ 综合全能 (战力+打工+旅行)</option>
          <option value="atk">⚔️ 战力加成</option>
          <option value="work">💼 打工收益</option>
          <option value="travel">🌍 旅行金币</option>
        </select>
      </div>
      <div>
        <label style="font-size:12px;font-weight:600;color:var(--text);display:block;margin-bottom:4px">图片（相对路径，留空自动匹配）：</label>
        <input class="m3-input" id="rideAddImg" style="width:100%" placeholder="data/img/rides/xxx.jpg">
        <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">
          <button class="ghost sm" id="rideAddPickUpload">⬆️ 本地上传</button>
          <button class="ghost sm" id="rideAddPickBuiltin">📂 内置选图</button>
          <button class="ghost sm" id="rideAddPreview">🔍 预览图片</button>
          <span id="rideAddImgTip" style="font-size:11.5px;color:var(--muted);align-self:center">未选择</span>
        </div>
      </div>
      <div class="hint" style="margin-top:2px">添加后记得点「保存坐骑」持久化落盘</div>
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
      const r = await getBridge().apiPost("images/preview", { path: p });
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
      const bEl = document.getElementById("rideAddBuff");
      const buff = bEl ? (Number(bEl.value) || 0) : 10;
      const btEl = document.getElementById("rideAddBuffType");
      const buff_type = btEl ? btEl.value : "all";
      const img = (document.getElementById("rideAddImg")?.value || "").trim();
      if (!n) { toast("请填写坐骑名称", "bad"); return; }
      if (SHOP_RIDE[n] !== undefined) { toast("已存在同名坐骑", "bad"); return; }
      SHOP_RIDE[n] = { price: p, img, buff, buff_type };
      SHOP_DIRTY = true;
      syncShopRaw();
      try { renderShopRideBox(true); } catch (e) {}
      try { renderAtlas(); } catch (e) {}
      modal.className = "";
      toast("已添加坐骑，请点击「保存坐骑」持久化", "ok");
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
      (typeof SPIRIT !== "undefined" && SPIRIT) ? Promise.resolve(SPIRIT) : apiTimeout(getBridge().apiGet("spirits"), 20000, "spirits").catch(() => null)
    ]);
    if (spiritData) {
      if (typeof SPIRIT !== "undefined") SPIRIT = spiritData;
      window.SPIRIT = spiritData;
      try { SPIRIT_TS = Date.now(); } catch (e) {}
    }
    updateShopBadges();
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
      // 口径与 07 自加载同构：内存 {effect, effects[]}；07 未加载时回退老单体
      const _tn = sec["treasures"];
      const _norm1 = (typeof _normTreasureEffMap === "function") ? _normTreasureEffMap : ((o) => {
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
      });
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
    try { setShopSubtab(CURRENT_SHOP_SUBTAB || "ride"); } catch (e) {}
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
        const item = { price: Number(v.price) || 0 };
        if (v.img) item.img = String(v.img).trim();
        if (v.buff !== undefined && v.buff !== "" && !isNaN(Number(v.buff))) item.buff = Number(v.buff);
        if (v.buff_type && v.buff_type !== "all") item.buff_type = String(v.buff_type).trim();
        cleanRide[k] = item;
      } else {
        cleanRide[k] = { price: Number(v) || 0 };
      }
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
      // BOM 头先剥（记事本存档常见，不剥 JSON.parse 必炸）
      const txt = (await file.text()).replace(/^\uFEFF/, ""); const data = JSON.parse(txt);
      // 导出中心单项包 {kind:"shops", shops:{…}} 先解包；其余格式原样
      const pkg = (data && data.kind === "shops" && data.shops && typeof data.shops === "object") ? data.shops : data;
      const done = [], failed = [];
      // 新格式：全量商城包
      if (pkg && (pkg.kind === "shop" || data.kind === "shops" || pkg.spirit_shop !== undefined || pkg.weapon_attrs !== undefined || Array.isArray(pkg.pool))) {
        if (pkg.ride_shop !== undefined) {
          const r = await getBridge().apiPost("config/save", { "商城图鉴": { "ride_shop": pkg.ride_shop } });
          if (r && r.error) throw new Error(r.error);
          done.push("坐骑");
        }
        if (pkg.weapon_attrs !== undefined) {
          let _attrs = pkg.weapon_attrs;
          if (typeof _attrs === "string" && _attrs.trim()) { try { _attrs = JSON.parse(_attrs); } catch (err) { _attrs = null; } }
          if (_attrs && typeof _attrs === "object") {
            const r = await getBridge().apiPost("weapons/pool/attrs", { attrs: _attrs, full: 1 });
            if (r && r.error) throw new Error(r.error);
            done.push("武器属性");
          }
        }
        if (pkg.weapon_order !== undefined) {
          const r = await getBridge().apiPost("config/save", { "商城图鉴": { "weapon_order": pkg.weapon_order } });
          if (r && r.error) throw new Error(r.error);
          done.push("武器顺序");
        }
        if (pkg.spirit_shop && typeof pkg.spirit_shop === "object") {
          const r = await getBridge().apiPost("spirits/save", { shop: pkg.spirit_shop });
          if (r && r.error) throw new Error(r.error);
          done.push("精灵道具");
        }
        if (Array.isArray(pkg.pool) && pkg.pool.length) {
          const have = new Set();
          try { ["SSR", "SR", "R"].forEach((rar) => ((POOL_WEAPONS && POOL_WEAPONS[rar]) || []).forEach((it) => have.add(rar + "|" + it.name))); } catch (err) {}
          const missing = pkg.pool.filter((p) => p && p.name && !have.has((p.rar || "") + "|" + p.name)).length;
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
