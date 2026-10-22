/**
 * 12_fishing.js — 钓鱼与水族馆管理后台模块
 * 涵盖 105 种鱼类图鉴展示、增删改查、生态水域/品质筛选、JSON导入导出、恢复默认与群友实时运行大屏
 */

let _fishingAllFishes = [];
let _fishingCurrentZone = "all";
let _fishingCurrentQuality = "all";
let _fishingSearchKeyword = "";
let _fishingOverviewData = null;

async function loadFishing(force = false) {
  try {
    const p1 = api("fishing/overview").catch(() => null);
    const p2 = api("fishing/fishes").catch(() => null);
    const [ovResp, fResp] = await Promise.all([p1, p2]);

    if (ovResp && ovResp.code === 0) {
      _fishingOverviewData = ovResp;
      renderFishingOverview(ovResp);
    }
    if (fResp && fResp.code === 0) {
      _fishingAllFishes = fResp.data || [];
      renderFishingGrid();
    }
  } catch (e) {
    toast("加载钓鱼系统数据失败: " + e.message, "bad");
  }
}

function renderFishingOverview(data) {
  const elSp = document.getElementById("fishingStatSpecies");
  const elPonds = document.getElementById("fishingStatPonds");
  const elAqFishes = document.getElementById("fishingStatAquariumFishes");
  const elBkFishes = document.getElementById("fishingStatBucketFishes");

  if (elSp) elSp.innerText = data.total_species || 0;
  if (elPonds) elPonds.innerText = data.active_ponds || 0;
  if (elAqFishes) elAqFishes.innerText = data.total_aquarium_fishes || 0;
  if (elBkFishes) elBkFishes.innerText = data.total_bucket_fishes || 0;

  // 更新水域分段标签计数
  const zones = data.zones || {};
  document.querySelectorAll("[data-fish-zone]").forEach(btn => {
    const z = btn.getAttribute("data-fish-zone");
    const countSpan = btn.querySelector(".zone-count");
    if (countSpan) {
      if (z === "all") {
        countSpan.innerText = data.total_species || 0;
      } else {
        countSpan.innerText = zones[z] || 0;
      }
    }
  });
}

function getQualityBadgeStyle(quality) {
  switch (quality) {
    case "幻彩神话":
      return "background:linear-gradient(135deg, #f093fb 0%, #f5576c 100%);color:#fff;font-weight:700;";
    case "橙色传说":
      return "background:#ff9800;color:#fff;font-weight:700;";
    case "紫色史诗":
      return "background:#9c27b0;color:#fff;font-weight:600;";
    case "蓝色稀有":
      return "background:#2196f3;color:#fff;";
    case "绿色优秀":
      return "background:#4caf50;color:#fff;";
    default:
      return "background:var(--cardBg, #f0f0f0);color:var(--text, #333);border:1px solid var(--line, #ddd);";
  }
}

function renderFishingGrid() {
  const container = document.getElementById("fishingGridBox");
  if (!container) return;

  const kw = _fishingSearchKeyword.trim().toLowerCase();
  const filtered = _fishingAllFishes.filter(f => {
    if (_fishingCurrentZone !== "all" && f.zone !== _fishingCurrentZone) return false;
    if (_fishingCurrentQuality !== "all" && f.quality !== _fishingCurrentQuality) return false;
    if (kw) {
      const n = (f.name || "").toLowerCase();
      const d = (f.desc || "").toLowerCase();
      const id = (f.id || "").toLowerCase();
      if (!n.includes(kw) && !d.includes(kw) && !id.includes(kw)) return false;
    }
    return true;
  });

  const countBadge = document.getElementById("fishingFilterResultCount");
  if (countBadge) countBadge.innerText = filtered.length;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:48px 16px;color:var(--muted)">
        <div style="font-size:36px;margin-bottom:8px">🎣</div>
        <div style="font-size:14px">暂无符合条件的鱼类品种</div>
        <div style="font-size:12px;margin-top:4px">请尝试切换水域、品质或清空搜索关键字</div>
      </div>
    `;
    return;
  }

  let html = "";
  for (const f of filtered) {
    const qStyle = getQualityBadgeStyle(f.quality);
    const isMyth = f.quality === "幻彩神话";
    const borderGlow = isMyth ? "border:1.5px solid #f093fb;box-shadow:0 0 12px rgba(240,147,251,0.25);" : "border:1px solid var(--line);";

    html += `
      <div class="card" style="display:flex;flex-direction:column;justify-content:space-between;padding:14px 16px;border-radius:16px;background:var(--cardBg);${borderGlow};transition:transform .15s ease,box-shadow .15s ease">
        <div>
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px">
            <div style="display:flex;align-items:center;gap:10px">
              <span style="font-size:28px;line-height:1">${f.icon || "🐟"}</span>
              <div>
                <div style="font-weight:700;font-size:14px;color:var(--text);display:flex;align-items:center;gap:6px">
                  ${escapeHtml(f.name || "未命名")}
                  ${isMyth ? "<span title='神话物种具备双S金冠潜力'>👑</span>" : ""}
                </div>
                <div style="font-size:11px;color:var(--muted);margin-top:2px">${escapeHtml(f.zone || "自然水域")}</div>
              </div>
            </div>
            <span style="font-size:11px;padding:3px 8px;border-radius:12px;white-space:nowrap;${qStyle}">${escapeHtml(f.quality || "普通")}</span>
          </div>

          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:12px 0 8px">
            <span style="font-size:11px;padding:2px 8px;background:var(--bg);border:1px solid var(--line);border-radius:6px;color:var(--text)">📐 ${escapeHtml(f.size || "小型")}</span>
            <span style="font-size:11px;padding:2px 8px;background:var(--bg);border:1px solid var(--line);border-radius:6px;color:var(--text)">⚖️ ${f.min_weight || 0.1} ~ ${f.max_weight || 1.0} kg</span>
            <span style="font-size:11px;padding:2px 8px;background:var(--bg);border:1px solid var(--line);border-radius:6px;color:var(--pri)">💰 基准: ${f.base_price || 50} 金币</span>
          </div>

          <div style="font-size:12px;color:var(--muted);line-height:1.45;min-height:34px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">
            ${escapeHtml(f.desc || "暂无生态简介描述。")}
          </div>
        </div>

        <div style="display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-top:12px;padding-top:10px;border-top:1px dashed var(--line)">
          <button class="ghost sm" type="button" onclick="openFishEditModal('${f.id}')" style="font-size:12px;padding:4px 10px">✏️ 编辑</button>
          <button class="ghost sm del" type="button" onclick="deleteFishItem('${f.id}', '${escapeHtml(f.name)}')" style="font-size:12px;padding:4px 10px">🗑️ 删除</button>
        </div>
      </div>
    `;
  }

  container.innerHTML = html;
}

// ==================== 模态弹窗与编辑 ====================
function openFishEditModal(fishId = null) {
  let fish = {
    id: "",
    name: "",
    zone: _fishingCurrentZone !== "all" ? _fishingCurrentZone : "淡水湖泊与溪流",
    quality: "白色普通",
    size: "小型",
    min_weight: 0.5,
    max_weight: 2.0,
    base_price: 50,
    icon: "🐟",
    desc: ""
  };

  if (fishId) {
    const hit = _fishingAllFishes.find(x => x.id === fishId);
    if (hit) fish = { ...hit };
  }

  document.getElementById("fishFormId").value = fish.id || "";
  document.getElementById("fishFormName").value = fish.name || "";
  document.getElementById("fishFormZone").value = fish.zone || "淡水湖泊与溪流";
  document.getElementById("fishFormQuality").value = fish.quality || "白色普通";
  document.getElementById("fishFormSize").value = fish.size || "小型";
  document.getElementById("fishFormMinWeight").value = fish.min_weight || 0.5;
  document.getElementById("fishFormMaxWeight").value = fish.max_weight || 2.0;
  document.getElementById("fishFormBasePrice").value = fish.base_price || 50;
  document.getElementById("fishFormIcon").value = fish.icon || "🐟";
  document.getElementById("fishFormDesc").value = fish.desc || "";

  document.getElementById("modalFishEditTitle").innerText = fishId ? "✏️ 编辑鱼类品种" : "＋ 新增鱼类品种";
  const modal = document.getElementById("modalFishEdit");
  if (modal) modal.style.display = "flex";
}

function closeFishEditModal() {
  const modal = document.getElementById("modalFishEdit");
  if (modal) modal.style.display = "none";
}

async function saveFishForm() {
  const name = document.getElementById("fishFormName").value.trim();
  if (!name) {
    toast("鱼类名称不能为空哦！", "bad");
    return;
  }

  const fish = {
    id: document.getElementById("fishFormId").value.trim(),
    name: name,
    zone: document.getElementById("fishFormZone").value,
    quality: document.getElementById("fishFormQuality").value,
    size: document.getElementById("fishFormSize").value,
    min_weight: parseFloat(document.getElementById("fishFormMinWeight").value) || 0.5,
    max_weight: parseFloat(document.getElementById("fishFormMaxWeight").value) || 2.0,
    base_price: parseInt(document.getElementById("fishFormBasePrice").value) || 50,
    icon: document.getElementById("fishFormIcon").value.trim() || "🐟",
    desc: document.getElementById("fishFormDesc").value.trim()
  };

  if (fish.max_weight < fish.min_weight) {
    toast("最大重量必须大于或等于最小重量！", "bad");
    return;
  }

  try {
    const res = await api("fishing/fish/save", { method: "POST", body: { fish } });
    if (res && res.code === 0) {
      toast("保存鱼类品种成功！", "ok");
      closeFishEditModal();
      await loadFishing(true);
    } else {
      toast("保存失败: " + (res.error || res.msg || "未知错误"), "bad");
    }
  } catch (e) {
    toast("网络异常: " + e.message, "bad");
  }
}

async function deleteFishItem(id, name) {
  if (!confirm(`确定要彻底删除鱼类【${name}】吗？删除后玩家将无法钓出该品种。`)) return;
  try {
    const res = await api("fishing/fish/delete", { method: "POST", body: { id } });
    if (res && res.code === 0) {
      toast(`已成功删除【${name}】！`, "ok");
      await loadFishing(true);
    } else {
      toast("删除失败: " + (res.error || res.msg || "未知错误"), "bad");
    }
  } catch (e) {
    toast("删除异常: " + e.message, "bad");
  }
}

async function restoreDefaultFishes() {
  if (!confirm("⚠️ 确定要将全水域鱼类品种恢复为系统初始的 105 种预设吗？\n自制的自定义品种将会被覆盖替换。")) return;
  try {
    const res = await api("fishing/reset", { method: "POST" });
    if (res && res.code === 0) {
      toast(res.msg || "已恢复默认 105 种鱼类图鉴！", "ok");
      await loadFishing(true);
    } else {
      toast("恢复失败: " + (res.error || res.msg || "未知错误"), "bad");
    }
  } catch (e) {
    toast("恢复异常: " + e.message, "bad");
  }
}

// ==================== 导出与导入 ====================
async function exportFishingJSON() {
  try {
    const res = await api("fishing/export");
    if (res && res.code === 0) {
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `fishing_fishes_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast("导出鱼类图鉴 JSON 成功！", "ok");
    }
  } catch (e) {
    toast("导出失败: " + e.message, "bad");
  }
}

function openFishingImportModal() {
  const modal = document.getElementById("modalFishingImport");
  if (modal) modal.style.display = "flex";
}

function closeFishingImportModal() {
  const modal = document.getElementById("modalFishingImport");
  if (modal) modal.style.display = "none";
}

async function doFishingImport() {
  const text = document.getElementById("fishingImportText").value.trim();
  const mode = document.getElementById("fishingImportMode").value;
  if (!text) {
    toast("请粘贴或选择要导入的 JSON 内容！", "bad");
    return;
  }

  let parsed = null;
  try {
    parsed = JSON.parse(text);
  } catch (e) {
    toast("JSON 语法解析错误，请检查格式！", "bad");
    return;
  }

  const list = Array.isArray(parsed) ? parsed : (parsed.fishes || parsed.data || []);
  if (!Array.isArray(list) || list.length === 0) {
    toast("未检测到有效的鱼类数组数据！", "bad");
    return;
  }

  try {
    const res = await api("fishing/import", { method: "POST", body: { fishes: list, mode: mode } });
    if (res && res.code === 0) {
      toast(res.msg || "导入成功！", "ok");
      closeFishingImportModal();
      document.getElementById("fishingImportText").value = "";
      await loadFishing(true);
    } else {
      toast("导入失败: " + (res.error || res.msg || "未知错误"), "bad");
    }
  } catch (e) {
    toast("网络异常: " + e.message, "bad");
  }
}

// ==================== 实时群友监控大屏 ====================
async function openFishingRuntimeMonitor() {
  const modal = document.getElementById("modalFishingRuntime");
  if (modal) modal.style.display = "flex";

  const box = document.getElementById("fishingRuntimeListBox");
  if (box) box.innerHTML = '<div style="text-align:center;padding:24px;color:var(--muted)">正在实时拉取全群鱼塘与水族馆挂机状态…</div>';

  try {
    const res = await api("fishing/runtime_list");
    if (res && res.code === 0) {
      const list = res.data || [];
      if (list.length === 0) {
        box.innerHTML = '<div style="text-align:center;padding:32px;color:var(--muted)">当前群聊中暂无玩家建立鱼塘或存放展鱼哦~</div>';
        return;
      }
      let html = `
        <table class="tbl" style="width:100%;font-size:12px">
          <thead>
            <tr>
              <th>群号 / QQ</th>
              <th>窝料种类</th>
              <th>鱼塘状态</th>
              <th>水桶存量</th>
              <th>水族馆展馆</th>
              <th>展出鱼数</th>
              <th>水质健康度</th>
              <th>图鉴进度</th>
            </tr>
          </thead>
          <tbody>
      `;
      for (const item of list) {
        html += `
          <tr>
            <td>
              <span style="font-weight:600">${escapeHtml(item.qq)}</span>
              <div style="font-size:11px;color:var(--muted)">群: ${escapeHtml(item.gid)}</div>
            </td>
            <td>${escapeHtml(item.pond_bait)}</td>
            <td><span class="m3-badge-counter" style="background:var(--cardBg);border:1px solid var(--line);color:var(--pri)">${escapeHtml(item.pond_status)}</span></td>
            <td>${item.bucket_count} / ${item.bucket_cap}</td>
            <td>${escapeHtml(item.aquarium_name)}</td>
            <td>${item.aquarium_fishes} / ${item.aquarium_cap}</td>
            <td>
              <span style="font-weight:600;color:${item.water_quality >= 80 ? 'var(--ok)' : (item.water_quality >= 50 ? 'orange' : 'var(--bad)')}">
                💧 ${item.water_quality} / 100
              </span>
            </td>
            <td>📖 ${item.atlas_count} 种</td>
          </tr>
        `;
      }
      html += `</tbody></table>`;
      box.innerHTML = html;
    }
  } catch (e) {
    if (box) box.innerHTML = `<div style="text-align:center;padding:24px;color:var(--bad)">拉取失败: ${e.message}</div>`;
  }
}

function closeFishingRuntimeMonitor() {
  const modal = document.getElementById("modalFishingRuntime");
  if (modal) modal.style.display = "none";
}

// ==================== 事件绑定与初始化 ====================
document.addEventListener("DOMContentLoaded", () => {
  // 水域过滤切换
  document.querySelectorAll("[data-fish-zone]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-fish-zone]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      _fishingCurrentZone = btn.getAttribute("data-fish-zone");
      renderFishingGrid();
    });
  });

  // 品质过滤
  document.getElementById("fishQualityFilter")?.addEventListener("change", (e) => {
    _fishingCurrentQuality = e.target.value;
    renderFishingGrid();
  });

  // 搜索关键字防抖
  let searchTimer = null;
  document.getElementById("fishSearchInput")?.addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      _fishingSearchKeyword = e.target.value;
      renderFishingGrid();
    }, 200);
  });

  // 顶部操作栏事件
  document.getElementById("btnFishAdd")?.addEventListener("click", () => openFishEditModal(null));
  document.getElementById("btnFishRefresh")?.addEventListener("click", () => loadFishing(true));
  document.getElementById("btnFishExport")?.addEventListener("click", exportFishingJSON);
  document.getElementById("btnFishImport")?.addEventListener("click", openFishingImportModal);
  document.getElementById("btnFishResetDefault")?.addEventListener("click", restoreDefaultFishes);
  document.getElementById("btnFishRuntime")?.addEventListener("click", openFishingRuntimeMonitor);

  // 弹窗关闭与保存
  document.getElementById("modalFishEditClose")?.addEventListener("click", closeFishEditModal);
  document.getElementById("fishFormCancel")?.addEventListener("click", closeFishEditModal);
  document.getElementById("fishFormSave")?.addEventListener("click", saveFishForm);

  document.getElementById("modalFishImportClose")?.addEventListener("click", closeFishingImportModal);
  document.getElementById("fishImportCancel")?.addEventListener("click", closeFishingImportModal);
  document.getElementById("fishImportDo")?.addEventListener("click", doFishingImport);

  document.getElementById("modalFishRuntimeClose")?.addEventListener("click", closeFishingRuntimeMonitor);

  // 文件选择器读取 JSON
  document.getElementById("fishImportFileInput")?.addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (evt) => {
        const text = evt.target.result;
        document.getElementById("fishingImportText").value = text;
      };
      reader.readAsText(file, "UTF-8");
    }
  });
});
