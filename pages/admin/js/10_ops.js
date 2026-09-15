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
      box.innerHTML = `<div class="hint" style="padding:14px;text-align:center;color:var(--bad);background:var(--panel);border:1px solid var(--line);border-radius:8px">❌ 读取远端归档失败: ${esc(errMsg)}</div>`;
      return;
    }
    _WD_FILES = res.files || [];
    _WD_PAGE = 1;
    if (!_WD_FILES.length) {
      box.innerHTML = `<div class="hint" style="padding:14px;text-align:center;background:var(--panel);border:1px solid var(--line);border-radius:8px">云端远端目录下暂无归档文件，点击上方「立即上传云端」即可上传备份。</div>`;
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
      box.innerHTML = `<div class="hint" style="padding:14px;text-align:center;background:var(--panel);border:1px solid var(--line);border-radius:8px">云端远端目录下暂无归档文件，点击上方「立即上传云端」即可上传备份。</div>`;
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
        <div style="display:flex;align-items:center;justify-content:space-between;background:var(--panel);padding:10px 14px;border-radius:10px;border:1px solid var(--line);flex-wrap:wrap;gap:8px">
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
    box.innerHTML = `<div class="hint" style="padding:14px;text-align:center;color:var(--bad);background:var(--panel);border:1px solid var(--line);border-radius:8px">❌ 网络或服务异常: ${esc(err.message || String(err))}</div>`;
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
  if (!(await uiConfirm("再次确认恢复 \"" + sel + "\"？覆盖后只能从备份恢复！", "终极确认恢复"))) return;
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

// 关于页检测更新已下线（用户拍板）：版本走静态文本（bump 同步），后端 version/check 路由保留（超管聊天指令用）。
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
    const terminal = document.getElementById("logTerminal") || document.getElementById("logBox");
    if (terminal) {
      terminal.scrollTop = terminal.scrollHeight;
    }
  }
}

async function loadLogs(isAuto = false) {
  try {
    let lvl = (document.getElementById("logsLevelFilter")?.value || "").trim();
    if (lvl === "ALL") lvl = "";
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
      meta.textContent = `当前展示: ${count} / 近${total}行 | 文件大小: ${size} KB (上限 ${maxMb} MB)`;
    }
    return true;
  } catch (e) {
    const container = document.getElementById("logTerminalContent");
    if (container && (!LOGS_CACHE || LOGS_CACHE.length === 0)) {
      container.innerHTML = `<div class="log-empty" style="color:var(--bad)">拉取日志异常: ${esc(e.message || "网络或服务错误")} (可点击刷新重试)</div>`;
    }
    if (!isAuto) {
      toast("拉取日志未成功: " + (e.message || "请稍后重试"), "bad");
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
      if (res && (res.status === "error" || res.error)) {
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
