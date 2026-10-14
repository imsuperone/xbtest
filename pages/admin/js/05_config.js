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
    // 并行拉取（此前串行多付一次往返）
    const [cur, _schRaw] = await Promise.all([
      getBridge().apiGet("config/get"),
      getBridge().apiGet("config/schema").catch(() => null)
    ]);
    let _defs = {};
    try {
      ((_schRaw && _schRaw.groups && _schRaw.groups["设置"]) || []).forEach((it) => { _defs[it.key] = it.default; });
    } catch (e) {}
    const box = document.getElementById("ovReq");
    box.innerHTML = OV_REQ.map(([sec, key, label, type, tip]) => {
      const v = ((cur || {})[sec] || {})[key] ?? _defs[key] ?? "";
      return `<div class="ov-field"><label>${esc(label)}</label>` +
        `<input data-ov-sec="${esc(sec)}" data-ov-key="${esc(key)}" type="${type === "int" ? "number" : "text"}" value="${esc(v)}">` +
        `<small>${esc(tip)}</small></div>`;
    }).join("") +
      `<div class="ov-field"><label class="ov-field-spacer">.</label><button id="btnOvReqSave">保存必要配置</button></div>`;
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
      // 数字框清空=保持原值：Number("")===0 会把清空误存成 0
      if (inp.type === "number" && String(inp.value || "").trim() === "") return;
      payload[sec][key] = inp.type === "number" ? Number(inp.value) : inp.value.trim();
    });
    await getBridge().apiPost("config/save", payload).then((r) => {
      if (r && r.error) throw new Error(r.error);
    });
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
  const paint = (ctrl, mode, drift, rt, mismatches) => {
    const meta = BALANCE_MODE_META[mode] || BALANCE_MODE_META.standard;
    ["activeBalanceBadge1", "activeBalanceBadge2"].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.style.display = "inline-flex";
      el.style.alignItems = "center";
      el.style.cursor = "pointer";
      if (ctrl === "realtime") {
        const phase = (rt && rt.phase) || "⚖️ 均衡稳态期";
        const fm = rt && rt.faucet_mult !== undefined ? rt.faucet_mult : 1.0;
        const sm = rt && rt.sink_mult !== undefined ? rt.sink_mult : 1.0;
        el.textContent = `⚡ 实时模式 · ${phase} (产出${fm}x/回收${sm}x)`;
        el.style.color = "#6366f1";
        el.style.background = "rgba(99,102,241,0.13)";
        el.style.border = "1px solid rgba(99,102,241,0.38)";
        el.title = `${(rt && rt.summary) || "实时动态调控运行中"}\n基准：${meta.label} | 活跃玩家：${(rt && rt.player_count) || 0}人 | 中位资产：${((rt && rt.median_wealth) || 0).toLocaleString()} | 人均：${((rt && rt.avg_wealth) || 0).toLocaleString()}`;
      } else if (drift > 0) {
        el.textContent = `📌 固定 · ${meta.label}（已偏离${drift}项）`;
        el.style.color = "var(--acc)";
        el.style.background = "rgba(99,102,241,0.1)";
        el.style.border = "1px solid var(--accBorder)";
        const tips = (mismatches || []).map(x => `${x.sec}.${x.key}: 当前=${x.actual} (预设=${x.expected})`).join("\n");
        el.title = `当前在 [${meta.label}] 基础上自定义修改了 ${drift} 项核心指标:\n${tips}`;
      } else {
        el.textContent = `📌 固定 · ${meta.icon} ${meta.label}`;
        el.style.color = meta.fg;
        el.style.background = meta.bg;
        el.style.border = `1px solid ${meta.bd}`;
        el.title = "点击切换固定模式（标准/休闲/硬核）或实时调整模式";
      }
    });
  };
  try {
    const st = await getBridge().apiGet("config/balance_state").catch(() => null);
    if (st && st.ok && st.mode) {
      paint(st.control_type || "fixed", st.mode, st.mismatch_count ?? st.mismatch ?? 0, st.realtime_metrics || {}, st.mismatches || []);
      return st;
    }
  } catch (e) {}
  try {
    const cfg = await getBridge().apiGet("config/get").catch(() => null);
    const ctrl = (cfg && (cfg._balance_control_type || (cfg["设置"] && cfg["设置"]["调控模式"]))) || "realtime";
    const m = (cfg && (cfg._active_balance_mode || (cfg["设置"] && cfg["设置"]["平衡模式"]))) || "casual";
    paint(ctrl === "fixed" ? "fixed" : "realtime", ["standard", "casual", "hardcore"].includes(m) ? m : "casual", 0, (cfg && cfg._realtime_balance_meta) || {}, []);
  } catch (e) {}
  return null;
}
["activeBalanceBadge1", "activeBalanceBadge2", "btnAutoBalance", "btnAutoBalance2"].forEach((id) => {
  const el = document.getElementById(id);
  if (el && !el.dataset.balBound) {
    el.dataset.balBound = "1";
    el.addEventListener("click", () => {
      try { if (typeof openAutoBalanceModal === "function") openAutoBalanceModal(); } catch (e) {}
    });
  }
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
        const infoHtml = `<div class="cfg-info"><div class="cfg-lab">${esc(it.key)}</div>${it.desc ? `<div class="cfg-help">${esc(it.desc)}</div>` : ""}</div>`;
        if (isFlag(it.default)) {
          row.className = "cfg-row has-checkbox";
          const chk = flagVal(v) ? "checked" : "";
          row.innerHTML = infoHtml +
            `<div class="cfg-ctrl"><label class="switch"><input type="checkbox" ${chk} ${attrs}><span class="slider-toggle"></span></label></div>`;
        } else if (isTextType(it.type) || isListType(it.type)) {
          row.innerHTML = infoHtml +
            `<div class="cfg-ctrl" style="flex:1;max-width:360px"><textarea rows="${isListType(it.type) ? 3 : 2}" ${attrs} style="width:100%">${esc(v)}</textarea></div>`;
        } else if (it.type === "int" && /^-?\d+$/.test(String(v))) {
          row.innerHTML = infoHtml +
            `<div class="cfg-ctrl"><input type="number" step="1" value="${esc(v)}" ${attrs} style="width:140px"></div>`;
        } else if (it.type === "float" && !isNaN(parseFloat(v))) {
          row.innerHTML = infoHtml +
            `<div class="cfg-ctrl"><input type="number" step="any" value="${esc(v)}" ${attrs} style="width:140px"></div>`;
        } else {
          row.innerHTML = infoHtml +
            `<div class="cfg-ctrl" style="flex:1;max-width:320px"><input type="text" value="${esc(v)}" ${attrs} style="width:100%"></div>`;
        }
        box.appendChild(row);
      }
      form.appendChild(box);
    }
    try { refreshBalanceBadges(); } catch (e) {}
  } catch (e) {
    err("config: " + e.message);
    try { TAB_DONE.config = false; } catch (_e) {}
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

  if (icon) icon.textContent = "⚖️";
  if (title) title.textContent = "智能数值调控中心（固定模式 / 实时调整模式）";
  if (inputWrap) inputWrap.style.display = "none";

  let curCtrl = "realtime";
  let activeMode = "casual";
  let rt = {};
  let rtMap = {};
  let presetsFixed = {};
  let presetsRealtime = {};
  let currentValues = {};
  let sysSections = [
    { id: "slave", name: "⛓️ 奴隶系统", sections: ["设置", "费用配置", "间隔配置", "概率配置", "祈福配置"] },
    { id: "sign", name: "📅 签到系统", sections: ["签到配置", "打卡配置", "抽奖配置", "新手配置", "点赞配置"] },
    { id: "bank", name: "🏦 银行系统", sections: ["银行配置"] },
    { id: "ent", name: "🎪 娱乐系统", sections: ["娱乐配置"] },
    { id: "spirit", name: "🐾 精灵系统", sections: ["精灵配置"] },
    { id: "ride", name: "🐎 坐骑系统", sections: ["坐骑配置"] },
    { id: "sect", name: "🏯 帮派系统", sections: ["帮派配置"] },
    { id: "adv", name: "🗺️ 冒险系统", sections: ["冒险配置"] },
  ];
  let _driftInfo = "";
  try {
    const st = await refreshBalanceBadges();
    if (st && st.ok) {
      curCtrl = st.control_type === "fixed" ? "fixed" : "realtime";
      if (st.mode && ["standard", "casual", "hardcore"].includes(st.mode)) {
        activeMode = st.mode;
      }
      rt = st.realtime_metrics || {};
      rtMap = st.realtime_metrics_map || {};
      presetsFixed = st.presets || {};
      presetsRealtime = st.realtime_presets || {};
      currentValues = st.current_values || {};
      if (Array.isArray(st.system_sections) && st.system_sections.length) {
        sysSections = st.system_sections;
      }
      const mm = st.mismatch_count ?? st.mismatch ?? 0;
      const _mlabel = (BALANCE_MODE_META[activeMode] || {}).label || activeMode;
      if (curCtrl === "realtime") {
        _driftInfo = `<div class="bal-drift-banner" style="color:#6366f1;background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.35)">
          ⚡ 当前运行：<strong>实时调整模式</strong>（基准：${_mlabel} · <strong>${esc(rt.phase || "⚖️ 均衡稳态期")}</strong>）
          <div style="margin-top:3px;font-size:11.5px;color:var(--muted)">${esc(rt.summary || "系统正根据全服实时资产动态调节产出与回收倍率")}</div>
        </div>`;
      } else if (mm > 0) {
        const _names = (st.mismatches || []).map((x) => `${x.key}=${x.actual}`).join("、");
        _driftInfo = `<div class="bal-drift-banner" style="color:var(--warn);background:var(--warnSoft);border:1px solid var(--warn)">⚠️ 当前处于<strong>固定模式</strong>，但与「${_mlabel}」有 ${mm} 项自定义偏移${_names ? "（" + esc(_names) + "）" : ""}。可在下方查看具体数值对比，或重新应用预设对齐。</div>`;
      } else {
        _driftInfo = `<div class="bal-drift-banner" style="color:var(--ok);background:var(--okSoft);border:1px solid var(--ok)">📌 当前运行：<strong>固定模式 · ${_mlabel}</strong>（全系统数值参数 100% 同步生效中）</div>`;
      }
    }
  } catch (e) { activeMode = "casual"; }

  const fmt = (n) => Number(n || 0).toLocaleString();
  const getPresetFor = (ctrl, m) => {
    const src = ctrl === "realtime" ? presetsRealtime : presetsFixed;
    return (src && src[m]) || (presetsFixed && presetsFixed[m]) || {};
  };
  const gv = (p, sec, k, d = "") => ((p[sec] || {})[k] ?? d);
  const buildCardSummary = (ctrl, m) => {
    const p = getPresetFor(ctrl, m);
    if (!p || !Object.keys(p).length) return "";
    const tagCls = ctrl === "realtime" ? "tag-rt" : "tag-fix";
    const tagTxt = ctrl === "realtime" ? "⚡ 实时动态值" : "📌 固定预设值";
    const pills = [
      `<span class="bal-sum-pill ${tagCls}">${tagTxt}</span>`,
      `<span class="bal-sum-pill">签到 <strong>${gv(p,"签到配置","金钱下限")}~${gv(p,"签到配置","金钱上限")}</strong> (+${gv(p,"签到配置","连签加成")})</span>`,
      `<span class="bal-sum-pill">搬砖 <strong>${gv(p,"费用配置","搬砖收益下限")}~${gv(p,"费用配置","搬砖收益上限")}</strong></span>`,
      `<span class="bal-sum-pill">打工 <strong>${gv(p,"费用配置","打工收益下限")}~${gv(p,"费用配置","打工收益上限")}</strong></span>`,
      `<span class="bal-sum-pill">抽卡 <strong>${gv(p,"设置","抽武器花费")} / 十连${gv(p,"设置","十连抽花费")}</strong></span>`,
      `<span class="bal-sum-pill">初始身价 <strong>${gv(p,"费用配置","初始身价")}</strong></span>`,
      `<span class="bal-sum-pill">奴隶位 <strong>${gv(p,"设置","奴隶个数")}/${gv(p,"设置","奴隶个数上限")}</strong> (买位${gv(p,"设置","奴隶位价格")})</span>`,
      `<span class="bal-sum-pill">利率 <strong>${gv(p,"银行配置","存款利率")}%</strong> (上限${gv(p,"银行配置","利息上限")}/日${gv(p,"银行配置","每日结息次数")}次)</span>`,
      `<span class="bal-sum-pill">精灵挑战 <strong>${gv(p,"精灵配置","挑战奖励_金钱下限")}~${gv(p,"精灵配置","挑战奖励_金钱上限")}</strong></span>`,
      `<span class="bal-sum-pill">企鹅坐骑 <strong>${gv(p,"坐骑配置","价格_企鹅")}</strong></span>`,
    ];
    return pills.join("");
  };

  content.innerHTML = `
    ${_driftInfo}
    <div class="bal-mode-grid">
      <div role="button" tabindex="0" id="balTabFixed" class="bal-mode-tab ${curCtrl === "fixed" ? "active-fixed" : ""}">
        <div class="bal-mode-tab-title">📌 固定预设模式</div>
        <div class="bal-mode-tab-sub">标准 / 休闲 / 硬核三档静态锁定</div>
      </div>
      <div role="button" tabindex="0" id="balTabRealtime" class="bal-mode-tab ${curCtrl === "realtime" ? "active-realtime" : ""}">
        <div class="bal-mode-tab-title">⚡ 实时调整模式</div>
        <div class="bal-mode-tab-sub">感知全服资产与通胀率自动调节</div>
      </div>
    </div>

    <div id="balRealtimePanel" class="bal-rt-panel" style="display:${curCtrl === "realtime" ? "block" : "none"}">
      <div class="bal-rt-head">
        <span class="bal-rt-title">📡 全服实时经济遥测指标</span>
        <span id="balRtPhaseBadge" class="bal-rt-badge">${esc(rt.phase || "⚖️ 均衡稳态期")} · 通胀指数 ${rt.inflation_index ?? 0}</span>
      </div>
      <div class="bal-rt-kpi-grid">
        <div class="bal-rt-kpi">
          <div class="bal-rt-kpi-lbl">活跃玩家</div>
          <div class="bal-rt-kpi-val">${fmt(rt.player_count)} 人</div>
        </div>
        <div class="bal-rt-kpi">
          <div class="bal-rt-kpi-lbl">中位资产</div>
          <div class="bal-rt-kpi-val">${fmt(rt.median_wealth)}</div>
        </div>
        <div class="bal-rt-kpi">
          <div class="bal-rt-kpi-lbl">人均资产</div>
          <div class="bal-rt-kpi-val">${fmt(rt.avg_wealth)}</div>
        </div>
        <div class="bal-rt-kpi">
          <div class="bal-rt-kpi-lbl">前10%占比</div>
          <div class="bal-rt-kpi-val">${Math.round((rt.top10_share || 0) * 100)}%</div>
        </div>
      </div>
      <div class="bal-rt-mult-grid">
        <div class="bal-rt-mult-item">
          <span style="font-size:11.5px;color:var(--muted)">💧 水龙头产出倍率</span>
          <strong id="balRtFaucetMult" style="font-size:13.5px;color:var(--ok)">${rt.faucet_mult ?? 1.0}x</strong>
        </div>
        <div class="bal-rt-mult-item">
          <span style="font-size:11.5px;color:var(--muted)">🔥 金币回收消耗倍率</span>
          <strong id="balRtSinkMult" style="font-size:13.5px;color:#d97706">${rt.sink_mult ?? 1.0}x</strong>
        </div>
      </div>
      <div class="bal-rt-note">
        💡 <strong>实时调控原理：</strong>每 10 分钟自动采集全服【现金+存款】分布（65%中位数+35%均值防巨鲸失真）。开荒期自动提产出降物价；通胀期自动收紧水龙头、抬升抽卡/升星/坐骑/罚款回收池。下方可切换不同基准档位查看实时折算后的具体数值：
      </div>
    </div>

    <div id="balPresetListTitle" style="font-size:12px;font-weight:600;color:var(--muted);margin-bottom:8px;line-height:1.4">
      ${curCtrl === "realtime" ? "🎯 选择实时调整的【基准锚点档位】（点击任意档位即可预览实时折算后的完整数值）：" : "📌 选择固定模式下的【预设档位】（点击任意档位即可预览全部 8 大系统的完整数值）："}
    </div>
    <div class="bal-opt-list">
      <label class="bal-opt-card ${activeMode === "standard" ? "active" : ""}">
        <input type="radio" name="balanceMode" value="standard" ${activeMode === "standard" ? "checked" : ""}>
        <div class="bal-opt-body">
          <div class="bal-opt-title">🟢 标准平衡模式（推荐 · 经济稳健）</div>
          <div id="balCardSum_standard" class="bal-sum-pills">${buildCardSummary(curCtrl, "standard")}</div>
        </div>
      </label>
      <label class="bal-opt-card ${activeMode === "casual" ? "active" : ""}">
        <input type="radio" name="balanceMode" value="casual" ${activeMode === "casual" ? "checked" : ""}>
        <div class="bal-opt-body">
          <div class="bal-opt-title">🟡 休闲高福利模式（高爆率 · 爽游节奏）</div>
          <div id="balCardSum_casual" class="bal-sum-pills">${buildCardSummary(curCtrl, "casual")}</div>
        </div>
      </label>
      <label class="bal-opt-card ${activeMode === "hardcore" ? "active" : ""}">
        <input type="radio" name="balanceMode" value="hardcore" ${activeMode === "hardcore" ? "checked" : ""}>
        <div class="bal-opt-body">
          <div class="bal-opt-title">🔴 硬核博弈模式（防通胀 · 高对抗）</div>
          <div id="balCardSum_hardcore" class="bal-sum-pills">${buildCardSummary(curCtrl, "hardcore")}</div>
        </div>
      </label>
    </div>

    <div class="bal-detail-box">
      <div class="bal-detail-head">
        <div class="bal-detail-title" id="balDetailTitle">📋 具体数值全览</div>
        <input type="search" id="balDetailSearch" class="bal-search-input" placeholder="🔍 搜索参数名（如：奴隶、利率、抽武器、企鹅）">
      </div>
      <div id="balSysTabs" class="bal-sys-tabs"></div>
      <div id="balDetailTableWrap" class="bal-detail-table-wrap"></div>
    </div>
  `;

  const tabFixed = document.getElementById("balTabFixed");
  const tabRealtime = document.getElementById("balTabRealtime");
  const rtPanel = document.getElementById("balRealtimePanel");
  const listTitle = document.getElementById("balPresetListTitle");
  const sysTabsEl = document.getElementById("balSysTabs");
  const detailWrap = document.getElementById("balDetailTableWrap");
  const detailTitle = document.getElementById("balDetailTitle");
  const detailSearch = document.getElementById("balDetailSearch");

  let selectedSysId = "all";

  const renderSysTabs = () => {
    if (!sysTabsEl) return;
    const allTabs = [{ id: "all", name: "全部系统" }, ...sysSections];
    sysTabsEl.innerHTML = allTabs.map((t) => {
      const active = t.id === selectedSysId;
      return `<span role="button" tabindex="0" data-sys-tab="${esc(t.id)}" class="bal-sys-pill ${active ? "active" : ""}">${esc(t.name)}</span>`;
    }).join("");
    sysTabsEl.querySelectorAll("[data-sys-tab]").forEach((btn) => {
      btn.onclick = () => {
        selectedSysId = btn.dataset.sysTab || "all";
        renderSysTabs();
        renderDetailTable();
      };
    });
  };

  const renderDetailTable = () => {
    if (!detailWrap) return;
    const selRadio = content.querySelector("input[name='balanceMode']:checked");
    const selMode = selRadio ? selRadio.value : activeMode;
    const targetPreset = getPresetFor(curCtrl, selMode);
    const modeLabel = (BALANCE_MODE_META[selMode] || {}).label || selMode;
    const ctrlLabel = curCtrl === "realtime" ? "⚡ 实时调整模式" : "📌 固定预设模式";
    const kw = (detailSearch ? detailSearch.value : "").trim().toLowerCase();

    // 更新实时遥测面板中与所选基准档位对应的倍率
    if (curCtrl === "realtime" && rtMap && rtMap[selMode]) {
      const mRt = rtMap[selMode];
      const badgeEl = document.getElementById("balRtPhaseBadge");
      const fEl = document.getElementById("balRtFaucetMult");
      const sEl = document.getElementById("balRtSinkMult");
      if (badgeEl) badgeEl.textContent = `${mRt.phase || "⚖️ 均衡稳态期"} · 通胀指数 ${mRt.inflation_index ?? 0}`;
      if (fEl) fEl.textContent = `${mRt.faucet_mult ?? 1.0}x`;
      if (sEl) sEl.textContent = `${mRt.sink_mult ?? 1.0}x`;
    }

    const groupsToShow = selectedSysId === "all"
      ? sysSections
      : sysSections.filter((s) => s.id === selectedSysId);

    let totalCount = 0;
    let diffCount = 0;
    const blocks = [];

    groupsToShow.forEach((sysObj) => {
      const rows = [];
      (sysObj.sections || []).forEach((sec) => {
        const kv = targetPreset[sec] || {};
        const curKv = currentValues[sec] || {};
        Object.keys(kv).forEach((k) => {
          if (kw && !(`${sysObj.name} ${sec} ${k}`.toLowerCase().includes(kw))) return;
          const targetVal = String(kv[k] ?? "");
          const curVal = String(curKv[k] ?? targetVal);
          const isDiff = curVal !== "" && curVal !== targetVal;
          totalCount++;
          if (isDiff) diffCount++;
          rows.push(`
            <div class="bal-param-row ${isDiff ? "is-diff" : ""}">
              <div style="min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="[${esc(sec)}] ${esc(k)}">
                <span style="color:var(--muted);font-size:10.5px">[${esc(sec)}]</span> <strong>${esc(k)}</strong>
              </div>
              <div style="display:flex;align-items:center;gap:6px;flex-shrink:0">
                ${isDiff
                  ? `<span style="color:var(--muted);font-size:10.5px;text-decoration:line-through" title="当前生效值">${esc(curVal)}</span><span style="color:var(--warn);font-weight:700">→ ${esc(targetVal)}</span>`
                  : `<span style="color:var(--ok);font-weight:700">${esc(targetVal)}</span><span style="color:var(--muted);font-size:10px">✓</span>`}
              </div>
            </div>
          `);
        });
      });
      if (rows.length) {
        blocks.push(`
          <div style="margin-bottom:8px">
            <div style="font-size:11.5px;font-weight:700;color:var(--acc);margin:4px 0 6px 2px">${esc(sysObj.name)}（${rows.length} 项）</div>
            <div class="bal-param-grid">${rows.join("")}</div>
          </div>
        `);
      }
    });

    if (detailTitle) {
      detailTitle.innerHTML = `📋 具体数值全览 · <span style="color:var(--acc)">${esc(ctrlLabel)} / ${esc(modeLabel)}</span> <span style="font-size:11px;font-weight:400;color:var(--muted)">（共 ${totalCount} 项参数${diffCount > 0 ? `，其中 <strong style="color:var(--warn)">${diffCount} 项</strong>与当前生效值不同` : "，与当前生效值 100% 一致"}）</span>`;
    }
    detailWrap.innerHTML = blocks.length
      ? blocks.join("")
      : `<div style="padding:16px;text-align:center;color:var(--muted);font-size:12px">未找到匹配的参数项</div>`;
  };

  const refreshCardSummaries = () => {
    ["standard", "casual", "hardcore"].forEach((m) => {
      const el = document.getElementById(`balCardSum_${m}`);
      if (el) el.innerHTML = buildCardSummary(curCtrl, m);
    });
  };

  const updateCtrlUI = (nextCtrl) => {
    curCtrl = nextCtrl;
    if (tabFixed) {
      tabFixed.classList.toggle("active-fixed", curCtrl === "fixed");
    }
    if (tabRealtime) {
      tabRealtime.classList.toggle("active-realtime", curCtrl === "realtime");
    }
    if (rtPanel) rtPanel.style.display = curCtrl === "realtime" ? "block" : "none";
    if (listTitle) {
      listTitle.textContent = curCtrl === "realtime"
        ? "🎯 选择实时调整的【基准锚点档位】（点击任意档位即可预览实时折算后的完整数值）："
        : "📌 选择固定模式下的【预设档位】（点击任意档位即可预览全部 8 大系统的完整数值）：";
    }
    if (okBtn) {
      okBtn.textContent = curCtrl === "realtime" ? "⚡ 开启并立即执行实时调控" : "📌 应用所选固定预设";
    }
    refreshCardSummaries();
    renderDetailTable();
  };

  if (tabFixed) tabFixed.onclick = () => updateCtrlUI("fixed");
  if (tabRealtime) tabRealtime.onclick = () => updateCtrlUI("realtime");
  if (detailSearch) detailSearch.oninput = () => renderDetailTable();

  // 选项高亮切换 + 实时刷新具体数值表
  const radios = content.querySelectorAll("input[name='balanceMode']");
  radios.forEach(r => {
    r.onchange = () => {
      radios.forEach(x => {
        const lbl = x.closest("label");
        if (lbl) lbl.classList.toggle("active", x.checked);
      });
      renderDetailTable();
    };
  });

  renderSysTabs();
  renderDetailTable();

  if (cancelBtn) {
    cancelBtn.style.display = "";
    cancelBtn.textContent = "取消";
    cancelBtn.onclick = () => { modal.className = ""; };
  }
  const _closeBtn = document.getElementById("appModalClose");
  if (_closeBtn) _closeBtn.onclick = () => { modal.className = ""; };
  modal.onclick = (e) => { if (e.target === modal) modal.className = ""; };
  if (okBtn) {
    okBtn.textContent = curCtrl === "realtime" ? "⚡ 开启并立即执行实时调控" : "📌 应用所选固定预设";
    okBtn.disabled = false;
    okBtn.onclick = async () => {
      const sel = content.querySelector("input[name='balanceMode']:checked");
      const mode = sel ? sel.value : "standard";
      okBtn.disabled = true;
      okBtn.textContent = curCtrl === "realtime" ? "正在采集全服经济并调控..." : "正在应用固定预设...";
      try {
        const r = await getBridge().apiPost("config/auto_balance", { control_type: curCtrl, mode });
        if (r && r.ok) {
          toast(r.msg || "智能数值调控已生效", "ok", 4500);
          modal.className = "";
          try { await refreshBalanceBadges(); } catch (e) {}
          await loadConfig();
          if (typeof loadCommands === "function") try { await loadCommands(); } catch(e) {}
          if (typeof loadShops === "function") try { await loadShops(); } catch(e) {}
          if (typeof loadSlaveUsers === "function") try { await loadSlaveUsers(); } catch(e) {}
        } else {
          toast("应用失败: " + (r && (r.error || r.msg) ? (r.error || r.msg) : "未知错误"), "bad");
        }
      } catch(err) {
        toast("应用失败: " + err.message, "bad");
      } finally {
        okBtn.disabled = false;
        okBtn.textContent = curCtrl === "realtime" ? "⚡ 开启并立即执行实时调控" : "📌 应用所选固定预设";
      }
    };
  }
  modal.className = "show bal-modal";
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
    await getBridge().apiPost("config/save", payload).then((r) => {
      if (r && r.error) throw new Error(r.error);
    });
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
      // 搜索隐藏行不计入：否则“搜后恢复”误带隐藏节
      try {
        const box = inp.closest(".cfg-sec");
        if (box && box.style.display === "none") return;
      } catch (e) {}
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
    await getBridge().apiPost("config/save", payload).then((r) => {
      if (r && r.error) throw new Error(r.error);
    });
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
    await getBridge().apiPost("config/save", payload).then((r) => {
      if (r && r.error) throw new Error(r.error);
    });
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
    if (!Array.isArray(rows)) throw new Error((rows && (rows.error || rows.msg)) || "排行榜接口异常");
    const body = document.getElementById("rankBody");
    if (!body) return;
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--muted)">暂无榜单数据</td></tr>`;
      return;
    }
    const rankBadges = ["🥇", "🥈", "🥉"];
    body.innerHTML = rows
      .map((r, i) => {
        const rankIdx = i < 3 ? `<span style="font-size:16px">${rankBadges[i]}</span>` : `<span class="badge" style="background:var(--panel);border:1px solid var(--line);color:var(--text)">${i + 1}</span>`;
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
    try { TAB_DONE.rank = false; } catch (_e) {}
  }
}

