// ============================================================================
// Android 15 / Material 3 模块化数据定义表 (Data-Driven Hub Architecture)
// ============================================================================
const EXPORT_MODULES = [
  {
    key: "atlas",
    title: "📖 精灵与地图图鉴",
    desc: "包含精灵属性数值、地图探索配置、掉落概率与商城",
    defaultChecked: true,
    gather: async () => {
      let sp = (typeof SPIRIT !== "undefined" && SPIRIT) || null;
      if (!sp || (!sp.maps && !sp.spirits && !sp._raw)) {
        try { sp = await apiTimeout(getBridge().apiGet("spirits"), 20000, "spirits"); } catch (e) { sp = null; }
      }
      const out = {};
      if (sp && typeof sp === "object") {
        const raw = (sp._raw && sp._meta) ? sp._raw : sp;
        ["spirits", "maps", "shop"].forEach(k => { if (raw[k] && typeof raw[k] === "object") out[k] = raw[k]; });
      }
      return out;
    },
    apply: async (data) => {
      await getBridge().apiPost("spirits/save", data);
      try { await loadSpirits(true); } catch (e) {}
    },
    detect: (d) => (d.kind === "spirits" || d.spirits || d.parts?.atlas) ? (d.parts?.atlas || (d.spirits ? { spirits: d.spirits, maps: d.maps, shop: d.shop } : null)) : null
  },
  {
    key: "shops",
    title: "🛒 坐骑商城与武器库",
    desc: "包含商城坐骑上架列表、抽奖武器加成与顺序",
    defaultChecked: true,
    gather: (cfg) => {
      const sec = (cfg && cfg["商城图鉴"]) || {};
      const pool = [];
      try {
        ["SSR", "SR", "R"].forEach(rar => ((window.POOL_WEAPONS && window.POOL_WEAPONS[rar]) || []).forEach(it => {
          pool.push({ rar, name: it.name, attrs: (window.POOL_ATTRS && window.POOL_ATTRS[it.name]) || { atk: 0, desc: "" } });
        }));
      } catch (e) {}
      return { ride_shop: sec.ride_shop || "", weapon_attrs: sec.weapon_attrs || "", weapon_order: sec.weapon_order || "", pool };
    },
    apply: async (data) => {
      const p = {};
      ["ride_shop", "weapon_attrs", "weapon_order"].forEach(k => { if (data[k] !== undefined) p[k] = data[k]; });
      await getBridge().apiPost("config/save", { "商城图鉴": p });
      try { await loadShops(); } catch (e) {}
    },
    detect: (d) => (d.kind === "shops" || d.parts?.shops || d.ride_shop !== undefined) ? (d.parts?.shops || { ride_shop: d.ride_shop, weapon_attrs: d.weapon_attrs, weapon_order: d.weapon_order, pool: d.pool }) : null
  },
  {
    key: "treasures",
    title: "🔮 宝物专有效果库",
    desc: "包含宝物卡片清单、加成效果类型与自定义文案",
    defaultChecked: true,
    gather: (cfg) => {
      const sec = (cfg && cfg["商城图鉴"]) || {};
      const setSec = (cfg && cfg["设置"]) || {};
      const list = (window._TREAS_DIRTY && Array.isArray(window._TREAS_LIST)) ? window._TREAS_LIST.filter(Boolean).join("|") : String(setSec["宝物"] || "");
      let eff = {}, items = {};
      try {
        const raw = sec["treasures"] || sec["treasure_effects"];
        if (typeof raw === "object" && !Array.isArray(raw)) eff = raw;
        else if (typeof raw === "string" && raw.trim()) { try { eff = JSON.parse(raw); } catch (e) {} }
        if (window._TREAS_EFF && typeof window._TREAS_EFF === "object") eff = Object.assign({}, eff, window._TREAS_EFF);
        Object.entries(eff).forEach(([k, v]) => {
          items[k] = (v && typeof v === "object") ? { effect: String(v.effect || v.desc || ""), type: String(v.type || ""), value: Number(v.value) || 0 } : { effect: String(v || ""), type: "", value: 0 };
        });
      } catch (e) {}
      return { list, eff, items };
    },
    apply: async (data) => {
      const p = {}, sp = {};
      if (data.list !== undefined) p["宝物"] = data.list;
      if (data.items) sp["treasures"] = data.items;
      if (data.eff) sp["treasure_effects"] = data.eff;
      await getBridge().apiPost("config/save", { "设置": p, "商城图鉴": sp });
    },
    detect: (d) => (d.kind === "treasures" || d.parts?.treasures || d.parts?.treasure || d.treasures) ? (d.parts?.treasures || d.parts?.treasure || d.treasures) : null
  },
  {
    key: "rules",
    title: "⚙️ 玩法规则与数值",
    desc: "包含28大系统玩法数值与自定义指令回复（零玩家数据）",
    defaultChecked: false,
    gather: (cfg) => {
      const clean = {}, EX = new Set(["备份配置", "webdav_secret", "商城图鉴"]);
      Object.keys(cfg || {}).forEach(k => { if (!EX.has(k)) clean[k] = cfg[k]; });
      return clean;
    },
    apply: async (data) => {
      await getBridge().apiPost("config/save", data);
      try { await loadConfig(); } catch (e) {}
    },
    detect: (d) => (d.kind === "gamerules" || d.parts?.rules || d.rules) ? (d.parts?.rules || d.rules) : null
  },
  {
    key: "users",
    title: "👤 玩家资产与经济账本",
    desc: "包含全群玩家金币钱包、奴隶买卖关系与背包资产",
    defaultChecked: false,
    gather: async () => {
      try {
        const res = await callApi("users/export", {}, "GET");
        return (res && (res.users || res.result?.users)) || [];
      } catch (e) { return []; }
    },
    apply: async (data) => {
      if (Array.isArray(data)) {
        await callApi("users/import", { users: data }, "POST");
        try { await loadUsers(); } catch (e) {}
      }
    },
    detect: (d) => (d.users || d.parts?.users) ? (d.users || d.parts?.users) : null
  }
];

// 单项纯净导出通用调度
async function exportSingleModule(modKey) {
  const mod = EXPORT_MODULES.find(m => m.key === modKey);
  if (!mod) return;
  try {
    toast(`正在读取${mod.title}…`, "");
    const cur = (modKey === "shops" || modKey === "treasures" || modKey === "rules") ? await apiTimeout(getBridge().apiGet("config/get"), 20000, "config/get") : null;
    const data = await mod.gather(cur);
    const payload = {
      app: typeof PLUGIN_ID !== "undefined" ? PLUGIN_ID : "astrbot_plugin_xbbot_beta",
      kind: modKey,
      version: 1,
      exported_at: new Date().toISOString(),
      [modKey]: data
    };
    triggerExportResult({
      filename: `xbbot_${modKey}_${Date.now()}.json`,
      mime: "application/json;charset=utf-8",
      rawText: JSON.stringify(payload, null, 2)
    });
    toast(`${mod.title}已导出`, "ok");
  } catch (e) { toast(`导出失败: ${e.message || e}`, "bad"); }
}

const exportSpiritsOnly = () => exportSingleModule("atlas");
const exportShopsOnly = () => exportSingleModule("shops");
const exportTreasuresOnly = () => exportSingleModule("treasures");
const exportGameRulesOnly = () => exportSingleModule("rules");

// 更新导出中心勾选计数与实时摘要（含卡片 picked 高亮同步，单源：预设/点卡/点框全走此处）
function updateExportHubSummary() {
  const selected = [];
  const mapIds = { atlas: "chkExpAtlas", shops: "chkExpShops", treasures: "chkExpTreasures", rules: "chkExpGameRules", users: "chkExpUsers" };
  EXPORT_MODULES.forEach(m => {
    const chk = document.getElementById(mapIds[m.key]);
    if (chk?.checked) selected.push(m.title.replace(/^[^\s]+\s*/, ""));
    try { chk?.closest(".hub-mod-card")?.classList.toggle("picked", !!(chk && chk.checked)); } catch (e) {}
  });

  const sumTxt = document.getElementById("exportHubSummaryText");
  const doBtn = document.getElementById("exportHubDoExport");
  if (sumTxt) {
    if (selected.length === 0) {
      sumTxt.innerHTML = `<span style="color:var(--bad)">未勾选任何项目（请至少选择 1 项导出）</span>`;
      if (doBtn) doBtn.disabled = true;
    } else {
      sumTxt.innerHTML = `已选择 <strong>${selected.length}</strong> 个项目：[${selected.join(" · ")}]`;
      if (doBtn) doBtn.disabled = false;
    }
  }
}

// 打开 Android 15 风格模块化导出中心
function openExportHub(presetKey = "") {
  const modal = document.getElementById("exportHubModal");
  if (!modal) return;
  const mapIds = { atlas: "chkExpAtlas", shops: "chkExpShops", treasures: "chkExpTreasures", rules: "chkExpGameRules", users: "chkExpUsers" };

  const presets = {
    atlas_gear: ["atlas", "shops", "treasures"],
    atlas: ["atlas", "shops", "treasures"],
    game_rules: ["rules"],
    users_only: ["users"],
    full_all: ["atlas", "shops", "treasures", "rules", "users"],
    reset_none: []
  };

  if (presetKey && presets[presetKey] !== undefined) {
    const active = new Set(presets[presetKey]);
    Object.entries(mapIds).forEach(([k, id]) => {
      const el = document.getElementById(id);
      if (el) el.checked = active.has(k);
    });
  }
  updateExportHubSummary();
  modal.style.display = "flex";
  modal.classList.add("show");
}

function closeExportHub() {
  const modal = document.getElementById("exportHubModal");
  if (modal) { modal.classList.remove("show"); modal.style.display = "none"; }
}

// 绑定导出中心事件
function initExportHubEvents() {
  if (window._EXPORT_HUB_INITIALIZED) return;
  window._EXPORT_HUB_INITIALIZED = true;

  document.getElementById("btnOpenExportHub")?.addEventListener("click", () => openExportHub("atlas_gear"));
  document.getElementById("exportHubClose")?.addEventListener("click", closeExportHub);
  document.getElementById("exportHubCancel")?.addEventListener("click", closeExportHub);

  document.querySelectorAll(".preset-pill[data-preset]").forEach(btn => {
    btn.addEventListener("click", () => openExportHub(btn.dataset.preset));
  });

  ["chkExpAtlas", "chkExpShops", "chkExpTreasures", "chkExpGameRules", "chkExpUsers"].forEach(id => {
    document.getElementById(id)?.addEventListener("change", updateExportHubSummary);
  });

  // 整卡点击切换勾选（“仅导出本项”按钮除外，其自带 stopPropagation 不冒泡到卡片）
  document.querySelectorAll("#exportHubModal .hub-mod-card").forEach(card => {
    card.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      const chk = card.querySelector('input[type="checkbox"]');
      if (chk) { chk.checked = !chk.checked; updateExportHubSummary(); }
    });
  });

  document.getElementById("btnSoloExportAtlas")?.addEventListener("click", (e) => { e.stopPropagation(); exportSpiritsOnly(); });
  document.getElementById("btnSoloExportShops")?.addEventListener("click", (e) => { e.stopPropagation(); exportShopsOnly(); });
  document.getElementById("btnSoloExportTreasures")?.addEventListener("click", (e) => { e.stopPropagation(); exportTreasuresOnly(); });
  document.getElementById("btnSoloExportRules")?.addEventListener("click", (e) => { e.stopPropagation(); exportGameRulesOnly(); });
  document.getElementById("btnSoloExportUsers")?.addEventListener("click", (e) => { e.stopPropagation(); exportAllUsers(); });

  document.getElementById("exportHubDoExport")?.addEventListener("click", async () => {
    const mapIds = { atlas: "chkExpAtlas", shops: "chkExpShops", treasures: "chkExpTreasures", rules: "chkExpGameRules", users: "chkExpUsers" };
    const selectedMods = EXPORT_MODULES.filter(m => document.getElementById(mapIds[m.key])?.checked);

    if (!selectedMods.length) {
      toast("请至少选择一项需要导出的内容", "warn");
      return;
    }

    try {
      toast("正在收集所选模块数据…", "");
      let cur = null;
      if (selectedMods.some(m => m.key === "shops" || m.key === "treasures" || m.key === "rules")) {
        cur = await apiTimeout(getBridge().apiGet("config/get"), 20000, "config/get");
      }

      const parts = {};
      for (const m of selectedMods) {
        parts[m.key] = await m.gather(cur);
      }

      const payload = {
        app: typeof PLUGIN_ID !== "undefined" ? PLUGIN_ID : "astrbot_plugin_xbbot_beta",
        kind: "modular_preset",
        version: 4,
        exported_at: new Date().toISOString(),
        from_version: (typeof FRONTEND_VER !== "undefined" ? FRONTEND_VER : ""),
        parts
      };

      triggerExportResult({
        filename: `xbbot_custom_preset_${Date.now()}.json`,
        mime: "application/json;charset=utf-8",
        rawText: JSON.stringify(payload, null, 2)
      });
      toast(`已成功打包 ${selectedMods.length} 个独立模块`, "ok");
      closeExportHub();
    } catch (err) {
      toast("打包导出失败: " + (err.message || err), "bad");
    }
  });
}

