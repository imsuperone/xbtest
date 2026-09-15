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
  // 徽标按真实档位+漂移检测刷新（此前写死休闲，属显示问题）
  const paint = (mode, drift) => {
    const meta = BALANCE_MODE_META[mode] || BALANCE_MODE_META.standard;
    ["activeBalanceBadge1", "activeBalanceBadge2"].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (drift > 0) {
        el.textContent = `⚪ ${meta.label}（已偏离${drift}项）`;
        el.style.color = "var(--muted)"; el.style.background = "var(--panel)"; el.style.border = "1px solid var(--line)";
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
      <label class="card" style="display:flex;align-items:flex-start;gap:10px;padding:12px;border:${activeMode === "standard" ? "2px solid var(--acc)" : "1px solid var(--line)"};border-radius:12px;cursor:pointer">
        <input type="radio" name="balanceMode" value="standard" ${activeMode === "standard" ? "checked" : ""} style="margin-top:3px">
        <div>
          <div style="font-weight:600;color:var(--text);font-size:13px">🟢 标准平衡模式（官方推荐 · 经济稳健）</div>
          <div style="font-size:11.5px;color:var(--muted);margin-top:2px">签到 300-800 + 连签 50，利率 2%，造反率 35%，祈福爆发 5%。平稳通胀，适合绝大多数群聊。</div>
        </div>
      </label>
      <label class="card" style="display:flex;align-items:flex-start;gap:10px;padding:12px;border:${activeMode === "casual" ? "2px solid var(--acc)" : "1px solid var(--line)"};border-radius:12px;cursor:pointer">
        <input type="radio" name="balanceMode" value="casual" ${activeMode === "casual" ? "checked" : ""} style="margin-top:3px">
        <div>
          <div style="font-weight:600;color:var(--text);font-size:13px">🟡 休闲高福利模式（高爆率 · 活跃社群）</div>
          <div style="font-size:11.5px;color:var(--muted);margin-top:2px">签到 800-2000 + 连签 100，利率 3%，造反率 20%，祈福爆发 15%，赌博成功率 60%。低惩罚快节奏，极大激发互动。</div>
        </div>
      </label>
      <label class="card" style="display:flex;align-items:flex-start;gap:10px;padding:12px;border:${activeMode === "hardcore" ? "2px solid var(--acc)" : "1px solid var(--line)"};border-radius:12px;cursor:pointer">
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

