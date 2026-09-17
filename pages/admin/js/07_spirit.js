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
    // 宝物数值同批自加载（图鉴页不再依赖先进商城页；失败不挡精灵渲染）
    try { await ensureTreasureEff(); } catch (e) {}
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
    // 8 项核心数值（HP、物攻、物防、特攻、特防、速度、等级、进化），4列自适应微槽网格
    const coreAttrs = [
      ["hp", "HP"], ["atk", "物攻"], ["def", "物防"], ["spa", "特攻"],
      ["spd", "特防"], ["spe", "速度"], ["lv", "等级"], ["evolve", "进化"]
    ];
    const coreCells = coreAttrs.map(([fk, label]) => {
      const _list = fk === "evolve" ? ` list="spEvolveList"` : "";
      return `<div class="s-slot"><span class="s-slot-lab">${label}</span>` +
        `<input class="s-slot-val" data-sp-spirit="${esc(sn)}" data-s-field="${fk}" value="${esc(it[fk] ?? "")}"${_list} title="可编辑数值"></div>`;
    });
    return `<div class="sp-card" data-sp="${esc(sn)}">
      <div class="sp-header">
        <div class="sp-name">✦ <input class="sp-rename-inp" data-sp-rename value="${esc(sn)}" title="直接修改精灵名，回车/失焦生效"></div>
        <button type="button" class="s-del" data-del-spirit="${esc(sn)}" title="移除此精灵">✕ 移除</button>
      </div>
      <div class="sp-core-grid">${coreCells.join("")}</div>
      <div class="sp-extra-row">
        <div class="s-slot-h"><span class="s-slot-lab">属性:</span><input class="s-slot-val-inline" data-sp-spirit="${esc(sn)}" data-s-field="type" value="${esc(it.type ?? "")}" placeholder="水/火/草…"></div>
        <div class="s-slot-h"><span class="s-slot-lab">图片:</span><input class="s-slot-val-inline" data-sp-spirit="${esc(sn)}" data-s-field="img" value="${esc(it.img ?? "")}" placeholder="文件名"></div>
      </div>
      <div class="sp-actions">
        ${_img ? `<button type="button" class="ghost sm" data-sp-view="${esc(_img)}">查看图片</button>` : ""}
        <button type="button" class="ghost sm" data-sp-pick-upload="${esc(sn)}">上传图片</button>
        <button type="button" class="ghost sm" data-sp-pick-builtin="${esc(sn)}">内置图片</button>
      </div>
      ${_assignOpts ? `<div class="sp-assign-row"><select data-assign-map="${esc(sn)}" class="sp-assign-select">${_assignOpts}</select><button type="button" class="ghost sm sp-assign-btn" data-assign-spirit="${esc(sn)}">分配进图</button></div>` : ""}
    </div>`;
  }).join("") + _dl;
}

// ---------- 宝物效果库自加载（图鉴页直读数值，不再依赖先进商城页） ----------
// 与 08_shop.js loadShops 内 _norm1 同构：treasures 结构表优先，老 treasure_effects 只读兼容。
// 脏编辑（_TREAS_DIRTY）永不覆盖；并发复用同一 promise。
function _normTreasureEffMap(src) {
  const out = {};
  try {
    Object.entries(src || {}).forEach(([k, v]) => {
      if (v && typeof v === "object" && !Array.isArray(v)) {
        const _t = String(v.type || "");
        out[k] = {
          effect: String(v.effect || v.desc || ""),
          type: (_treasureTypeOk(_t) ? _t : ""),
          value: Math.max(0, Number(v.value) || 0)
        };
      } else if (v && String(v).trim()) {
        out[k] = { effect: String(v).trim(), type: "", value: 0 };
      }
    });
  } catch (e) {}
  return out;
}
let _TREAS_EFF_LOADING = null;
async function ensureTreasureEff(force) {
  try {
    if (!force && window._TREAS_DIRTY) return window._TREAS_EFF || {};
    if (!force && window._TREAS_EFF && Object.keys(window._TREAS_EFF).length) return window._TREAS_EFF;
    if (_TREAS_EFF_LOADING && !force) { try { await _TREAS_EFF_LOADING; } catch (e) {} return window._TREAS_EFF || {}; }
    _TREAS_EFF_LOADING = (async () => {
      const cur = await apiTimeout(getBridge().apiGet("config/get"), 20000, "config/get");
      const shopSec = (cur && cur["商城图鉴"]) || {};
      let src = shopSec["treasures"];
      if (!src || typeof src !== "object" || Array.isArray(src)) {
        const _old = shopSec["treasure_effects"];
        if (typeof _old === "string" && _old.trim()) { try { src = JSON.parse(_old); } catch (e) { src = null; } }
        else src = _old;
      }
      const norm = _normTreasureEffMap(src);
      if (Object.keys(norm).length) window._TREAS_EFF = norm;
      else if (!window._TREAS_EFF) window._TREAS_EFF = {};
      // 名单同步（未脏时）：设置.宝物为准，顺手回填 CFG.cur 供 renderAtlas 即时渲染
      try {
        if (!window._TREAS_DIRTY) {
          const _setSec = (cur && cur["设置"]) || {};
          const _lst = String(_setSec["宝物"] || "").split("|").map((s) => s.trim()).filter(Boolean);
          if (_lst.length) {
            window._TREAS_LIST = _lst;
            try { if (typeof CFG !== "undefined" && CFG && CFG.cur) { CFG.cur["设置"] = CFG.cur["设置"] || {}; CFG.cur["设置"]["宝物"] = _lst.join("|"); } } catch (e) {}
          }
        }
      } catch (e) {}
    })();
    await _TREAS_EFF_LOADING;
  } catch (e) {}
  _TREAS_EFF_LOADING = null;
  window._TREAS_EFF = window._TREAS_EFF || {};
  return window._TREAS_EFF;
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
        // 默认名单与后端 games/config/shop.py TREASURES 内置表同构（改后端表时此处同改）
        Treas = (curSec["宝物"] || "酒神葫芦|四象护符|金蟾|玉如意|雷公锤|夜明珠").toString().split("|").filter(Boolean);
        window._TREAS_LIST = [...Treas];
        window._TREAS_DIRTY = false;
      }
    } catch(e) { Treas = ["酒神葫芦", "四象护符", "金蟾", "玉如意", "雷公锤", "夜明珠"]; }
    const _spiritMaps = (() => { try { return Object.keys((SPIRIT && SPIRIT.maps) || {}); } catch (e) { return []; } })();
    const _tabs = [["treasure", "🎁 宝物", Treas.length], ["spirit", "✨ 精灵", _spiritMaps.length]];
    const _q = String((typeof window._ATLAS_Q !== "undefined" && window._ATLAS_Q) || "").trim();
    const _ql = _q.toLowerCase();
    let html = `<div class="atlas-top-bar">`
      + `<div class="atlas-seg-tabs">`
      + _tabs.map(([k, label, n]) => `<button type="button" class="atlas-seg-btn ${ATLAS_CUR === k ? "active" : ""}" data-atlas-tab="${k}" title="切换到${label}">${label} (${n})</button>`).join("")
      + `</div>`
      + `<div class="atlas-search-wrap"><span class="atlas-search-ic">🔍</span><input id="atlasSearch" placeholder="搜索宝物 / 地图 / 精灵…" value="${esc(_q)}"></div>`
      + `</div><div class="atlas-body-flow">`;
    // 内置回退与后端 games/config/shop.py TREASURES 同构（含真实 type/value，改后端表时此处同改）
    const _TREAS_BUILTIN = {
      "酒神葫芦": { effect: "造反免罪：持有时造反直接成功，恢复自由并劫掠主人", type: "pardon", value: 1 },
      "四象护符": { effect: "打架护盾：己方被打败/打赢时免被偷走奴隶", type: "shield", value: 1 },
      "金蟾": { effect: "打工工资 +20%", type: "work", value: 20 },
      "玉如意": { effect: "身价加成 +10%（计入战斗力）", type: "worth", value: 10 },
      "雷公锤": { effect: "主人战力 +500", type: "atk", value: 500 },
      "夜明珠": { effect: "纯收藏，无实战效果", type: "", value: 0 }
    };
    try { window._TREAS_BUILTIN = _TREAS_BUILTIN; } catch (e) {}
    const _effOf = (n) => { try { const e = (window._TREAS_EFF || {})[n]; if (e && typeof e === "object") return String(e.effect || ""); if (e) return String(e); const b = _TREAS_BUILTIN[n]; return b ? b.effect : ""; } catch (e) { return ""; } };
    const _treOf = (n) => { try { const e = (window._TREAS_EFF || {})[n]; if (e && typeof e === "object") return e; if (e) return { effect: String(e), type: "", value: 0 }; return _TREAS_BUILTIN[n] || null; } catch (e) { return null; } };
    const _valOf = (n) => { try { const o = _treOf(n); return (o && o.value !== undefined) ? (Number(o.value) || 0) : 0; } catch (e) { return 0; } };
    const _typeTag = (n) => { try { const o = _treOf(n) || {}; const t = String(o.type || ""); const v = Number(o.value) || 0; if (t === "atk" && v > 0) return "攻" + v; if (t === "shield") return "盾"; if (t === "pardon") return "免"; if ((t === "work" || t === "worth") && v > 0) return (t === "work" ? "工" : "价") + v + "%"; return ""; } catch (e) { return ""; } };
    // 内置表挂 window，供编辑弹窗回填当前生效值（未定制宝物打开✎不再空白）
    if (ATLAS_CUR === "treasure") {
      let h = `<div class="tre-panel"><div class="tre-header"><div class="tre-header-title"><span>奴隶系统 · 宝物效果库</span><span class="badge badge-primary">${Treas.length} 种</span></div><div class="tre-header-actions"><button type="button" class="btn sm" id="btnAtlasSaveTreasure">保存宝物</button><button type="button" class="ghost sm" id="btnAtlasResetTreasure">恢复默认</button><button type="button" class="ghost sm" id="btnAtlasAddTreasure">添加宝物</button></div></div><div class="tre-grid">`;
      const _ft = Treas.filter((n) => !_ql || String(n).toLowerCase().includes(_ql) || _effOf(n).toLowerCase().includes(_ql));
      if (!_ft.length) h += `<div class="atlas-empty-hint">${_q ? "无匹配宝物" : "暂无宝物数据"}</div>`;
      else h += _ft.map(n => {
        const e = _effOf(n);
        const _tag = _typeTag(n);
        return `<div class="tre-card" data-treasure="${esc(n)}">`
          + `<div class="tre-card-top">`
          + `<div class="tre-card-title"><strong>${esc(n)}</strong>${_tag ? `<span class="badge badge-primary">${esc(_tag)}</span>` : ""}</div>`
          + `<div class="tre-card-actions"><button type="button" class="icon-action-btn" data-atlas-edit-treasure="${esc(n)}" title="编辑效果类型与数值">✎</button><button type="button" class="icon-action-btn del" data-atlas-del="奴隶系统-宝物|${esc(n)}" title="删除此宝物">✕</button></div>`
          + `</div>`
          + `<div class="tre-card-val-row" style="display:flex;align-items:center;gap:6px;margin:6px 0">`
          + `<span style="font-size:11.5px;color:var(--muted);font-weight:600">效果数值:</span>`
          + `<input type="number" min="0" class="tre-card-val-inp" data-treas-val="${esc(n)}" value="${_valOf(n)}" style="width:72px;height:26px;font-size:12px;text-align:center;padding:2px 4px;border-radius:6px;border:1px solid var(--line)" title="可直接编辑数值">`
          + `</div>`
          + `<div class="tre-card-desc">${e ? esc(e.slice(0, 80)) : `<span style="color:var(--muted)">无自定义效果</span>`}</div>`
          + `</div>`;
      }).join("");
      h += `</div><div class="hint" style="margin-top:10px">提示：数值可直接在卡片上输入修改，点击 ✎ 可更换属性类型，改动后点击上方「保存宝物」生效。</div></div>`;
      html += h;
    }
    else if (ATLAS_CUR === "spirit") {
      const _maps = (() => { try { return (SPIRIT && SPIRIT.maps) || {}; } catch (e) { return {}; } })();
      const _spirits = (() => { try { return (SPIRIT && SPIRIT.spirits) || {}; } catch (e) { return {}; } })();
      const _mapHit = (m) => {
        if (!_ql) return true;
        try {
          if (String(m).toLowerCase().includes(_ql)) return true;
          return ((_maps[m] && _maps[m].drops) || []).map(String).join("、").toLowerCase().includes(_ql);
        } catch (e) { return false; }
      };
      const _names = Object.keys(_maps).filter(_mapHit);
      try { window._spDlDone = false; } catch (e) {}
      let _orphans = [];
      try {
        const _used = new Set();
        Object.values(_maps || {}).forEach((m) => ((m && m.drops) || []).map(String).forEach((s) => _used.add(s)));
        _orphans = Object.keys(_spirits || {}).filter((n) => !_used.has(String(n)));
      } catch (e) {}
      let h = `<div class="tre-panel">`
        + `<div class="tre-header"><div class="tre-header-title"><span>精灵系统 · 探索地图</span><span class="badge badge-primary">${_names.length} 张</span></div>`
        + `<div class="tre-header-actions">`
        + `<button type="button" class="ghost sm" id="btnAtlasExpandAll" title="全部展开">全部展开</button>`
        + `<button type="button" class="ghost sm" id="btnAtlasCollapseAll" title="全部收起">全部收起</button>`
        + `<button type="button" class="btn sm" id="btnAtlasSaveMaps">保存精灵</button>`
        + `<button type="button" class="ghost sm" id="btnAtlasResetMaps">恢复默认</button>`
        + `<button type="button" class="ghost sm del" id="btnAtlasClearMaps">清空地图</button>`
        + `</div></div>`;
      if (!_names.length) {
        const _bc = (() => { try { return Object.keys((SPIRIT && SPIRIT._builtin && SPIRIT._builtin.maps) || {}).length; } catch (e) { return 0; } })();
        h += `<span style="color:var(--muted)">当前无自定义地图，运行中使用内置 ${_bc} 张</span>`;
      } else {
        h += `<div id="atlasSpiritCards" style="display:flex;flex-direction:column;gap:8px">` + spiritMapCardsHTML(_names, _maps, _spirits, "") + `</div>`;
      }
      if (_orphans.length) {
        const _or = _orphans.filter((n) => !_ql || String(n).toLowerCase().includes(_ql));
        if (_or.length) {
          h += `<div class="s-mapcard ${SPIRIT_OPEN["__orphans__"] ? "open" : ""}" data-map="__orphans__" style="margin-top:10px"><div class="s-maphead" data-map-toggle="__orphans__"><span class="s-mapname">🧩 未上架精灵 (${_or.length})</span><span class="s-maplv">不在任何地图掉落中</span><span class="s-arr">${SPIRIT_OPEN["__orphans__"] ? "▾" : "▸"}</span></div>${SPIRIT_OPEN["__orphans__"] ? `<div class="s-mapbody"><div class="hint" style="margin-bottom:6px">这些精灵不会在野外遭遇，可编辑后分配进图，或直接移除</div><div class="sp-spirits">${spiritAttrCards(_spirits, _or, _names)}</div></div>` : ``}</div>`;
        }
      }
      h += `<div style="margin-top:8px"><button class="ghost sm" id="btnAtlasAddMap">＋ 添加地图</button></div>`;
      h += `<div class="hint" style="margin-top:6px">地图+属性一键保存/恢复，只动精灵范围</div></div>`;
      html += h;
    }
    else html += `<div class="card" style="border:1px solid var(--line);border-radius:var(--radius-xs);padding:8px 10px"><div style="color:var(--muted)">未知分类</div></div>`;
    html += `</div><div class="hint" style="margin-top:6px">顶栏可搜宝物/地图/精灵；宝物改动即时保存；精灵卡改动点保存精灵；武器坐骑请到🛒商城管理</div>`;
    box.innerHTML = html;
    box.querySelectorAll("[data-atlas-tab]").forEach((b) => b.addEventListener("click", () => {
      ATLAS_CUR = b.dataset.atlasTab;
      renderAtlas();
    }));
    // 搜索框：防抖重绘 + 焦点恢复（重绘会换掉 input 节点）
    try {
      const _si = box.querySelector("#atlasSearch");
      if (_si) {
        let _t = null;
        _si.addEventListener("input", () => {
          if (_t) clearTimeout(_t);
          _t = setTimeout(() => {
            window._ATLAS_Q = _si.value;
            const _pos = _si.selectionStart;
            window._ATLAS_FOCUS = true;
            renderAtlas();
            try {
              const _n = document.getElementById("atlasSearch");
              if (_n) { _n.focus(); _n.setSelectionRange(_pos, _pos); }
            } catch (e) {}
            window._ATLAS_FOCUS = false;
          }, 250);
        });
        if (window._ATLAS_FOCUS) { try { _si.focus(); } catch (e) {} }
      }
    } catch (e) {}
    document.getElementById("btnAtlasExpandAll")?.addEventListener("click", () => {
      try {
        Object.keys((SPIRIT && SPIRIT.maps) || {}).forEach((m) => { SPIRIT_OPEN[m] = true; });
        SPIRIT_OPEN["__orphans__"] = true;
      } catch (e) {}
      refreshSpiritViews();
    });
    document.getElementById("btnAtlasCollapseAll")?.addEventListener("click", () => {
      SPIRIT_OPEN = {};
      refreshSpiritViews();
    });
    const persistTreasure = async (delNames) => {
      // 宝物名+结构效果即时持久化（图鉴页内闭环，不碰商城；单一家 treasures，老 treasure_effects 只读兼容不再写）
      // delNames: 已删宝物名数组，显式 null 清 sidecar（merge 语义缺键≠删除，不传即复活）
      const items = {};
      Object.entries(window._TREAS_EFF || {}).forEach(([k, v]) => {
        if (v && typeof v === "object") {
          const _t = String(v.type || "");
          let _v = Number(v.value) || 0;
          if (_v < 0) _v = 0;
          items[k] = { type: (_treasureTypeOk(_t) ? _t : ""), value: _v, desc: String(v.effect || "") };
        } else if (v && String(v).trim()) {
          items[k] = { type: "", value: 0, desc: String(v).trim() };
        }
      });
      try {
        (delNames || []).forEach((k) => { if (k) items[String(k)] = null; });
      } catch (e) {}
      const r = await getBridge().apiPost("config/save", {
        "设置": { "宝物": (window._TREAS_LIST || Treas).filter(Boolean).join("|") },
        "商城图鉴": { "treasures": items }
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
          await persistTreasure([name]);
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
      openTreasureEditModal(el.dataset.atlasEditTreasure);
    }));
    box.querySelectorAll("[data-treas-val]").forEach(inp => inp.addEventListener("change", (e) => {
      const n = e.target.dataset.treasVal;
      const v = Math.max(0, Number(e.target.value) || 0);
      if (!window._TREAS_EFF) window._TREAS_EFF = {};
      const cur = _treOf(n) || { type: "", value: 0, effect: "" };
      window._TREAS_EFF[n] = {
        type: cur.type || "",
        value: v,
        effect: cur.effect || cur.desc || ""
      };
      window._TREAS_DIRTY = true;
      toast(`已修改 "${n}" 数值: ${v} (需点击保存宝物)`, "ok", 1500);
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
      if (!(await uiConfirm("直接恢复宝物为内置6件（酒神葫芦|四象护符|金蟾|玉如意|雷公锤|夜明珠）并清空自定义效果？旧数据不保留。", "恢复默认"))) return;
      try {
        const _old = [...(window._TREAS_LIST || []), ...Object.keys(window._TREAS_EFF || {})];
        window._TREAS_LIST = ["酒神葫芦", "四象护符", "金蟾", "玉如意", "雷公锤", "夜明珠"];
        window._TREAS_EFF = {};
        await persistTreasure(_old);
        toast("已恢复默认", "ok");
      } catch (e) { toast("恢复失败: " + e.message, "bad"); }
      renderAtlas();
    });
    document.getElementById("btnAtlasAddTreasure")?.addEventListener("click", async () => {
      let n = await uiPrompt("输入宝物名（奴隶系统-宝物）：", "", "添加宝物");
      if (!n) return; n = n.trim(); if (!n) return;
      // 名单以 | 分隔，宝物名禁 | 与首尾空格（否则存档名单解析错位）
      if (/[|｜]/.test(n)) { toast("宝物名不能包含 |", "bad"); return; }
      const _tl = window._TREAS_DIRTY ? (window._TREAS_LIST || []) : Treas;
      if (_tl.includes(n)) { toast("已存在", "bad"); return; }
      window._TREAS_LIST = [..._tl, n];
      window._TREAS_EFF = window._TREAS_EFF || {};
      if (!window._TREAS_EFF[n]) window._TREAS_EFF[n] = { effect: "", type: "", value: 0 };
      window._TREAS_DIRTY = true;
      renderAtlas();
      // 类型+数值+文案一次填完（编辑弹窗确定即保存，取消则保留名单稍后点保存宝物）
      try { openTreasureEditModal(n); } catch (e) {}
    });
  } catch (e) { box.innerHTML = `<span style="color:var(--muted)">图鉴加载失败: ${esc(e.message)}</span>`; }
}

const TREASURE_TYPES = [["", "无（纯收藏）"], ["atk", "攻击加成"], ["shield", "护盾（免被偷）"], ["pardon", "免罪（造反免罚）"], ["work", "打工加成%"], ["worth", "身价加成%"]];
function _treasureTypeOk(t) { return ["atk", "shield", "pardon", "work", "worth"].includes(String(t || "")); }
function openTreasureEditModal(name) {
  const modal = document.getElementById("appModal");
  if (!modal) return;
  const cur = (() => { try { const e = (window._TREAS_EFF || {})[name]; if (e && typeof e === "object") return e; if (e) return { effect: String(e), type: "", value: 0 }; const b = (window._TREAS_BUILTIN || {})[name]; if (b && typeof b === "object") return { effect: String(b.effect || ""), type: String(b.type || ""), value: Number(b.value) || 0 }; return { effect: "", type: "", value: 0 }; } catch (e) { return { effect: "", type: "", value: 0 }; } })();
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");
  if (icon) icon.textContent = "🎁";
  if (title) title.textContent = "编辑宝物「" + name + "」";
  if (inputWrap) inputWrap.style.display = "none";
  content.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:10px">
      <div><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">效果文案（留空用内置/通用）：</label>
        <input id="treEditDesc" value="${esc(cur.effect || "")}" style="width:100%;padding:6px 10px;border-radius:8px"></div>
      <div style="display:flex;gap:8px">
        <div style="flex:1"><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">实效类型：</label>
          <select id="treEditType" style="width:100%;padding:6px 10px;border-radius:8px">${TREASURE_TYPES.map(([v, l]) => `<option value="${v}"${String(cur.type || "") === v ? " selected" : ""}>${l}</option>`).join("")}</select></div>
        <div style="flex:1"><label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:3px">数值（攻击/打工%/身价%用）：</label>
          <input id="treEditValue" type="number" min="0" value="${Number(cur.value) || 0}" style="width:100%;padding:6px 10px;border-radius:8px"></div>
      </div>
      <div class="hint">攻击计入主人战力；护盾防打架被偷；免罪防造反被罚；打工加成主人全队工资；身价加成战斗力身价部分。保存后即时生效。</div>
    </div>`;
  if (cancelBtn) { cancelBtn.style.display = ""; cancelBtn.textContent = "取消"; cancelBtn.onclick = () => { modal.className = ""; }; }
  if (okBtn) {
    okBtn.textContent = "保存宝物"; okBtn.style.background = "var(--acc)"; okBtn.style.borderColor = "transparent";
    okBtn.onclick = async () => {
      const desc = (document.getElementById("treEditDesc")?.value || "").trim();
      const type = document.getElementById("treEditType")?.value || "";
      const value = Math.max(0, Number(document.getElementById("treEditValue")?.value) || 0);
      window._TREAS_EFF = window._TREAS_EFF || {};
      // 清空即删键：显式 null 穿透 merge（缺键≠删除，不传即复活）
      if (!desc && !type) { delete window._TREAS_EFF[name]; try { await persistTreasure([name]); toast("已保存", "ok"); } catch (e) { toast("保存失败: " + e.message, "bad"); } }
      else {
        window._TREAS_EFF[name] = { effect: desc, type: (_treasureTypeOk(type) ? type : ""), value };
        try { await persistTreasure(); toast("已保存", "ok"); }
        catch (e) { toast("保存失败: " + e.message, "bad"); }
      }
      modal.className = "";
      renderAtlas();
    };
  }
  modal.className = "show";
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
        <div class="s-map-settings">
          <div class="s-slot-h"><span class="s-slot-lab">推荐等级:</span><input class="s-slot-val-inline" data-map-field="lv" value="${esc(d.lv ?? 1)}" style="width:48px;text-align:center"></div>
          <div class="s-slot-h" style="flex:1;min-width:180px"><span class="s-slot-lab">出没精灵(逗号分隔):</span><input class="s-slot-val-inline" data-map-field="drops" value="${esc(drops.join("，"))}" style="flex:1"></div>
          <button type="button" class="s-del" data-del-map="${esc(mname)}" title="删除此地图">删除地图</button>
        </div>
        <div class="sp-spirits">${spiritAttrCards(spirits, drops)}</div>
        <button type="button" class="btn sm tonal" data-add-spirit="${esc(mname)}" style="margin-top:10px">添加精灵</button>
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
      // 引号选择器内不用 CSS.escape（转义值≠属性原值致静默 miss），改 dataset 比对
      const _inp = Array.from(root.querySelectorAll('.sp-card input[data-s-field="img"]'));
      const card = _inp.find((el) => { try { return el.closest(".sp-card").dataset.sp === sn; } catch (e) { return false; } }) || null;
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
    // v3 结构宝物优先（treasures 新家），老 treasure_effects 只读兼容
    const _normT = (o) => {
      const out = {};
      try {
        Object.entries(o || {}).forEach(([k, v]) => {
          if (v && typeof v === "object" && !Array.isArray(v)) {
            out[k] = { effect: String(v.effect || v.desc || ""), type: (_treasureTypeOk(String(v.type || "")) ? String(v.type) : ""), value: Math.max(0, Number(v.value) || 0) };
          } else if (v && String(v).trim()) {
            out[k] = { effect: String(v).trim(), type: "", value: 0 };
          }
        });
      } catch (e) {}
      return out;
    };
    let _titems = {};
    try {
      if (window._TREAS_DIRTY && Array.isArray(window._TREAS_LIST)) tlist = window._TREAS_LIST.filter(Boolean).join("|");
      else tlist = String(setSec["宝物"] || "");
      const _tn = shopSec["treasures"];
      if (_tn && typeof _tn === "object" && !Array.isArray(_tn) && Object.keys(_tn).length) {
        _titems = _normT(_tn);
        teff = {};
        Object.entries(_titems).forEach(([k, v]) => { if (v.effect) teff[k] = v.effect; });
      } else {
        const _te = shopSec["treasure_effects"];
        if (_te && typeof _te === "object" && !Array.isArray(_te)) teff = _te;
        else if (typeof _te === "string" && _te.trim()) { try { teff = JSON.parse(_te); } catch (e) { teff = {}; } }
        _titems = _normT(teff);
      }
      if (window._TREAS_EFF && typeof window._TREAS_EFF === "object") {
        const _m = _normT(window._TREAS_EFF);
        teff = Object.assign({}, teff, window._TREAS_EFF);
        _titems = Object.assign({}, _titems, _m);
      }
    } catch (e) {}
    const shops = {};
    ["ride_shop", "weapon_attrs", "weapon_order"].forEach((k) => { if (shopSec[k] !== undefined) shops[k] = shopSec[k]; });
    const payload = {
      app: "astrbot_plugin_xbbot_beta", kind: "preset", version: 3,
      exported_at: new Date().toISOString(),
      from_version: (typeof FRONTEND_VER !== "undefined" ? FRONTEND_VER : ""),
      parts: { atlas: _presetAtlasPart(sp), treasure: { list: tlist, eff: teff, items: _titems }, shops }
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
        && (parts.treasure.list || _n(parts.treasure.eff) || _n(parts.treasure.items)))
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
          && (parts.treasure.list !== undefined || parts.treasure.eff !== undefined || parts.treasure.items !== undefined)) {
          cfgPayload["设置"] = {};
          if (parts.treasure.list !== undefined) cfgPayload["设置"]["宝物"] = String(parts.treasure.list || "");
          cfgPayload["商城图鉴"] = {};
          // v3 结构优先；v2 老包按 eff 换算
          const _items = (parts.treasure.items && typeof parts.treasure.items === "object") ? parts.treasure.items : null;
          if (_items) {
            const _clean = {};
            Object.entries(_items).forEach(([k, v]) => {
              if (v && typeof v === "object" && !Array.isArray(v)) {
                const _t = String(v.type || "");
                _clean[k] = { type: (_treasureTypeOk(_t) ? _t : ""), value: Math.max(0, Number(v.value) || 0), desc: String(v.effect || v.desc || "") };
              } else if (v && String(v).trim()) {
                _clean[k] = { type: "", value: 0, desc: String(v).trim() };
              }
            });
            cfgPayload["商城图鉴"]["treasures"] = _clean;
          } else {
            const _eff = parts.treasure.eff;
            const _norm = {};
            const _src = (typeof _eff === "string") ? (() => { try { return JSON.parse(_eff); } catch (e) { return {}; } })() : (_eff || {});
            Object.entries(_src).forEach(([k, v]) => {
              if (v && typeof v === "object" && !Array.isArray(v)) _norm[k] = { type: "", value: 0, desc: String(v.effect || v.desc || "") };
              else if (v && String(v).trim()) _norm[k] = { type: "", value: 0, desc: String(v).trim() };
            });
            cfgPayload["商城图鉴"]["treasures"] = _norm;
          }
          // 老 treasure_effects 整键清理（已换算进 treasures，双源不再并存）
          cfgPayload["商城图鉴"]["treasure_effects"] = null;
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

