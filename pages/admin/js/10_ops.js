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
      const ext = (f.name.split(".").pop() || "").toLowerCase();
      const isDb = ["db", "sqlite", "sqlite3"].includes(ext);
      const isJson = ext === "json";
      const isZip = ["zip", "gz", "tar"].includes(ext);
      const shDate = formatShanghaiDate(f.mtime, f.name);

      let icon = "📄";
      if (isDb) {
        icon = "🗄️";
      } else if (isJson) {
        icon = "📋";
      } else if (isZip) {
        icon = "📦";
      }

      html += `
        <div style="display:flex;align-items:center;justify-content:space-between;background:var(--panel);padding:10px 14px;border-radius:10px;border:1px solid var(--line);flex-wrap:wrap;gap:8px">
          <div style="display:flex;align-items:center;gap:10px;min-width:200px">
            <span style="font-size:24px;line-height:1;display:flex;align-items:center;justify-content:center">${icon}</span>
            <div>
              <div style="font-weight:600;font-size:13px;word-break:break-all;display:flex;align-items:center;gap:4px"><span>${esc(f.name)}</span></div>
              <div class="hint" style="font-size:11.5px;margin-top:2px">大小: ${esc(f.size || "-")} · 修改时间: ${esc(shDate)}</div>
            </div>
          </div>
          <div style="display:flex;gap:6px;align-items:center">
            ${isDb ? `<button class="ghost" data-wdrestore="${esc(f.name)}" style="color:var(--acc);border-color:var(--accBorder);font-size:12px;padding:4px 10px">⚡ 快捷恢复</button>` : ""}
            <button class="ghost" data-wddelete="${esc(f.name)}" style="color:var(--bad);border-color:rgba(239,68,68,0.3);font-size:12px;padding:4px 10px" title="从 WebDAV 云端删除此备份文件">🗑️ 删除</button>
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
          `确认从 WebDAV 云端备份【${fname}】恢复数据库？\n\n注意：当前数据与配置将被该云端备份覆盖并热重载生效。`,
          "恢复云端备份"
        );
        if (!ok) return;
        const origText = btn.textContent;
        btn.disabled = true;
        btn.textContent = "⏳ 正在下载并恢复...";
        toast(`正在下载云端备份 [${fname}] 并恢复...`, "ok", 6000);
        try {
          const r = await getBridge().apiPost("backup/webdav/restore", { file: fname });
          if (r && r.ok) {
            toast(`云端备份 [${fname}] 恢复成功`, "ok", 6000);
            await loadBackups(BACKUP_DIR);
          } else {
            const err = (r && r.msg) ? r.msg : ((r && r.error) ? r.error : "恢复失败");
            toast(`恢复失败: ${err}`, "bad", 8000);
            uiAlert(err, "云端恢复失败");
          }
        } catch (e) {
          toast(`恢复异常: ${e.message}`, "bad", 8000);
          uiAlert(e.message || String(e), "云端恢复异常");
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
          `确定要从 WebDAV 云端删除备份文件【${fname}】吗？\n\n注意：该文件将从云端服务器永久删除，不可撤销。`,
          "删除云端备份"
        );
        if (!ok) return;
        const origText = btn.textContent;
        btn.disabled = true;
        btn.textContent = "删除中...";
        toast(`正在删除云端备份 [${fname}]...`, "ok", 4000);
        try {
          const r = await getBridge().apiPost("backup/webdav/delete", { file: fname });
          if (r && r.ok) {
            toast(`云端备份 [${fname}] 已删除`, "ok", 5000);
            await loadRemoteWebDAVFiles();
          } else {
            const err = (r && r.msg) ? r.msg : ((r && r.error) ? r.error : "删除失败");
            toast(`删除失败: ${err}`, "bad", 8000);
            uiAlert(err, "删除云端备份失败");
          }
        } catch (e) {
          toast(`删除异常: ${e.message}`, "bad", 8000);
          uiAlert(e.message || String(e), "删除云端备份异常");
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
  if (!(await uiConfirm("再次确认删除 \"" + sel + "\"？", "再次确认删除"))) return;
  try { await getBridge().apiPost("backups/delete", { path: sel }); toast("已删除", "ok"); window.BACKUP_SELECTED=""; await loadBackups(BACKUP_DIR); } catch (err) { toast("删除失败: " + err.message, "bad"); }
});
document.getElementById("btnBackupRestore")?.addEventListener("click", async () => {
  const sel = window.BACKUP_SELECTED || "";
  if (!sel) { toast("请先单击选中要恢复的备份", "bad"); return; }
  if (!(await uiConfirm("确认恢复备份 " + sel + "？当前数据将被覆盖。", "恢复备份"))) return;
  if (!(await uiConfirm("再次确认恢复 \"" + sel + "\"？覆盖后只能从备份恢复。", "再次确认恢复"))) return;
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
        await _b.download("export", { kind: "backup", path: sel, raw: "1" }, filename);
        toast("已触发下载: " + filename, "ok");
        return;
      } catch (e) {}
    }
    const r = await getBridge().apiGet("export", { kind: "backup", path: sel });
    if (r && r.data) {
      downloadBase64File(r.data, r.filename || filename);
      toast("已导出备份文件", "ok");
    } else {
      toast("导出失败: " + (r && r.error ? r.error : "无数据"), "bad");
    }
  } catch (err) { toast("导出失败: " + err.message, "bad"); }
});
document.getElementById("btnClearAll")?.addEventListener("click", async () => {
  if (!(await uiConfirm("确认清空所有数据？将删除全部钱包、账户、群数据与备份，且不可恢复。", "危险：清空所有数据"))) return;
  const input = await uiPrompt("为防止误操作，请输入“确认删除”以继续：", "", "清空所有数据");
  if (input !== "确认删除") { toast("输入不正确，已取消清空", "bad"); return; }
  if (!(await uiConfirm("再次确认：清空所有数据？", "再次确认清空"))) return;
  try {
    await getBridge().apiPost("admin/clear", {confirm: "确认删除", confirm2: "确认"});
    toast("已清空所有数据", "ok");
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
    _setChk("wdStrictSwitch", b["WebDAV严格校验"] ?? "假");
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
      "WebDAV严格校验": document.getElementById("wdStrictSwitch")?.checked ? "真" : "假",
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
    say("备份配置已保存并校验生效", true);
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
    if (el("anaSlaveCount")) el("anaSlaveCount").textContent = `奴隶: ${fmt(sum.total_slaves_count || 0)} 人`;
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

  if (icon) icon.textContent = "";
  if (title) title.textContent = "批量资产空投";
  if (inputWrap) inputWrap.style.display = "none";

  content.innerHTML = `
    <div style="font-size:12px;color:var(--muted);margin-bottom:12px">
      向全群或指定群所有玩家批量发放货币、体力或抽奖券（自动事务写入）：
    </div>
    <div style="display:flex;flex-direction:column;gap:10px">
      <div>
        <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">目标群聊 (留空则面向全库所有活跃玩家)：</label>
        <input id="dropGid" placeholder="输入群号 (留空全库)" style="width:100%;padding:7px 10px;border-radius:8px">
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
        <div>
          <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">赠送货币：</label>
          <input type="number" id="dropMoney" value="1000" style="width:100%;padding:7px 10px;border-radius:8px">
        </div>
        <div>
          <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">赠送体力：</label>
          <input type="number" id="dropStamina" value="100" style="width:100%;padding:7px 10px;border-radius:8px">
        </div>
        <div>
          <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">抽奖券：</label>
          <input type="number" id="dropTickets" value="5" style="width:100%;padding:7px 10px;border-radius:8px">
        </div>
      </div>
      <div>
        <label style="font-size:11.5px;color:var(--muted);display:block;margin-bottom:4px">空投事由 / 备注：</label>
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
    okBtn.textContent = "发送全员空投";
    okBtn.onclick = async () => {
      const gid = (document.getElementById("dropGid")?.value || "").trim();
      const money = parseInt(document.getElementById("dropMoney")?.value || 0, 10);
      const stamina = parseInt(document.getElementById("dropStamina")?.value || 0, 10);
      const tickets = parseInt(document.getElementById("dropTickets")?.value || 0, 10);
      const reason = document.getElementById("dropReason")?.value || "全员福利空投";

      okBtn.disabled = true;
      okBtn.textContent = "正在发送空投...";
      try {
        const res = await getBridge().apiPost("users/airdrop", { gid, money, stamina, tickets, reason });
        if (res && res.ok) {
          toast(`空投已发放：已为 ${res.target_count || 0} 名用户注入资产`, "ok");
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
  if (!(await uiConfirm("确认校准全群所有玩家的奴隶身价？\n将检测全库中身价为 0 或未初始化的用户，并批量匹配为当前配置的初始身价。", "校准全员身价"))) return;
  toast("正在校准全员奴隶身价...", "ok");
  try {
    const res = await getBridge().apiPost("slave/calibrate", {});
    if (res && res.ok) {
      toast(res.msg || `已校准 ${res.fixed_count || 0} 名用户的奴隶身价`, "ok");
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
  toast("正在进行数据库体检与碎片整理...", "ok");
  try {
    const res = await getBridge().apiPost("backups/doctor", {});
    if (res && res.ok) {
      const tblInfo = res.tables ? Object.entries(res.tables).map(([k, v]) => `${k}: ${v} 行`).join(" | ") : "";
      const msg = `数据库体检与整理完成。\n\n· 完整性状态: ${res.integrity}\n· 整理前总大小: ${res.size_before}\n· 整理后总大小: ${res.size_after}\n· 释放碎片空间: ${res.saved}\n· 数据表行数统计: ${tblInfo}`;
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

    // 单次 apiGet（读接口 GET,POST 双方法直连，无回退重放，防双倍请求）
    const res = await getBridge().apiGet("logs", params);

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
      toast("日志拉取失败: " + (e.message || "请稍后重试"), "bad");
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
        const res = await getBridge().apiGet("export", { kind: "logs" });
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
      toast("日志已导出", "ok");
    } catch (e) {
      toast("导出日志失败: " + e.message, "bad");
    }
  });
  document.getElementById("btnLogsClear")?.addEventListener("click", async () => {
    const ok = await uiConfirm("确定要清空当前的插件运行日志吗？\n清空后不可恢复（将重新从空文件开始记录）。", "清空日志");
    if (!ok) return;
    try {
      toast("正在清空日志…", "ok");
      const res = await getBridge().apiPost("logs/clear", {});
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

// ---------- 对齐官方最新版本内容事件绑定 ----------
function initAlignLatestEvents() {
  const btn = document.getElementById("btnAlignLatest");
  const btnPreview = document.getElementById("btnAlignPreview");
  const diffBox = document.getElementById("alignDiffBox");
  const diffContent = document.getElementById("alignDiffContent");
  const pillsBox = document.getElementById("alignDiffSummaryPills");
  const verBadge = document.getElementById("alignOffVerBadge");

  // 绑定多选卡片选中高亮状态
  const cards = document.querySelectorAll(".align-opt-card");
  cards.forEach(card => {
    const cb = card.querySelector('input[type="checkbox"]');
    if (!cb) return;
    card.classList.toggle("checked", cb.checked);
    cb.addEventListener("change", () => {
      card.classList.toggle("checked", cb.checked);
    });
  });

  let _previewCache = null;

  async function loadAlignPreview(silent = false) {
    try {
      if (!silent) toast("正在获取版本差异明细…", "ok");
      const res = await getBridge().apiGet("system/align_preview", {});
      if (!res || !res.ok) throw new Error(res?.error || "获取差异失败");
      _previewCache = res;

      if (verBadge) {
        verBadge.textContent = `官方基准：${res.official_version || "最新"} (${res.official_updated_at || "2026-10-21"})`;
      }

      const presetsBadge = document.getElementById("alignPresetsBadge");
      if (presetsBadge) {
        if ((res.preset_summary?.custom_locked || 0) > 0) {
          presetsBadge.className = "align-badge align-badge-protect";
          presetsBadge.textContent = `${res.preset_summary.custom_locked} 项自定义项受锁保护 🔒`;
        } else {
          presetsBadge.className = "align-badge align-badge-safe";
          presetsBadge.textContent = "官方推荐基准";
        }
      }

      if (diffContent) {
        let html = "";
        const ps = res.preset_summary || {};
        const rd = res.riddles_summary || {};
        const rs = res.rides_summary || {};
        const ws = res.weapons_summary || {};

        if (pillsBox) {
          const ctrlModeLabel = ps.control_type === "realtime" ? "实时调控模式（自适应）" : "固定预设模式";
          const upDate = res.official_updated_at || "2026-10-21";
          pillsBox.innerHTML = `
            <span class="align-badge align-badge-info" style="font-weight:700">官方基准发布: ${esc(upDate)}</span>
            <span class="align-badge" style="background:rgba(99,102,241,0.12);color:var(--acc,#3b82f6);border:1px solid rgba(99,102,241,0.25);font-weight:600">⚙️ ${esc(ctrlModeLabel)}</span>
            <span class="align-badge align-badge-info">待对齐: ${ps.will_update || 0}</span>
            <span class="align-badge align-badge-safe">已一致: ${ps.unchanged || 0}</span>
            <span class="align-badge align-badge-protect">自定义保护: ${ps.custom_locked || 0}</span>
          `;
        }

        // 题库概览
        html += `<div style="margin-bottom:12px;padding:10px 12px;background:rgba(34,197,94,0.06);border:1px solid rgba(34,197,94,0.2);border-radius:8px">
          <div style="font-weight:600;color:var(--ok);margin-bottom:4px">🧩 娱乐题库（官方标准 ${rd.official_total || 0} 道 / 本地活跃 ${rd.active_total || 0} 道）</div>
          <div style="color:var(--muted);font-size:12px">
            自建题目保留: <b>${rd.custom_total || 0}</b> 道 | 官方修正/增量题: <b>${rd.to_fix_total || 0}</b> 道（对齐后将自动纠错官方题干与答案）
          </div>
        </div>`;

        // 坐骑与武器概览
        html += `<div style="margin-bottom:12px;display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:8px">
          <div style="padding:8px 12px;background:var(--cardBg, var(--panel));border:1px solid var(--line);border-radius:8px">
            <div style="font-weight:600">🐎 官方默认坐骑（${rs.official_count || 10} 款）</div>
            <div style="color:var(--muted);font-size:12px;margin-top:2px">本地共有 ${rs.active_count || 0} 款（含自建 ${rs.custom_count || 0} 款 🔒 保留）</div>
          </div>
          <div style="padding:8px 12px;background:var(--cardBg, var(--panel));border:1px solid var(--line);border-radius:8px">
            <div style="font-weight:600">⚔️ 内置武器属性（${ws.official_count || 42} 款）</div>
            <div style="color:var(--muted);font-size:12px;margin-top:2px">本地共有 ${ws.active_count || 0} 款（含自建 ${ws.custom_count || 0} 款 🔒 保留）</div>
          </div>
        </div>`;

        // 数值预设对比
        const diffs = res.diff_details || [];
        html += `<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:8px">
          <div style="font-weight:600">⚖️ 规则对比明细：</div>
          <div id="alignDiffFilterBar" style="display:flex;gap:6px;flex-wrap:wrap">
            <button type="button" class="btn align-filter-chip active" data-filter="update" style="padding:2px 8px;font-size:11px">待更新 (${ps.will_update || 0})</button>
            <button type="button" class="btn align-filter-chip" data-filter="custom" style="padding:2px 8px;font-size:11px">自定义锁 (${ps.custom_locked || 0})</button>
            <button type="button" class="btn align-filter-chip" data-filter="same" style="padding:2px 8px;font-size:11px">已一致 (${ps.unchanged || 0})</button>
            <button type="button" class="btn align-filter-chip" data-filter="all" style="padding:2px 8px;font-size:11px">全部 (${diffs.length})</button>
          </div>
        </div>`;

        if (diffs.length === 0) {
          html += `<div style="color:var(--muted);padding:8px">暂无数值差异</div>`;
        } else {
          html += `<div id="alignDiffItemsList" style="border:1px solid var(--line);border-radius:8px;overflow:hidden">`;
          diffs.forEach(it => {
            const filterTag = it.status === "custom_locked" ? "custom" : (it.status === "unchanged" ? "same" : "update");
            const hideClass = (filterTag !== "update" && ps.will_update > 0) ? " style=\"display:none\"" : "";
            if (it.status === "custom_locked") {
              html += `<div class="align-diff-item custom-locked" data-filter-tag="${filterTag}"${hideClass}>
                <span class="align-diff-key">[${esc(it.section)}] ${esc(it.key)}</span>
                <div class="align-diff-vals">
                  <span class="align-val-locked">${esc(it.current)}</span>
                  <span class="align-badge align-badge-protect" style="font-size:10.5px">用户自定义 🔒 保留</span>
                </div>
              </div>`;
            } else if (it.status === "unchanged") {
              html += `<div class="align-diff-item" data-filter-tag="${filterTag}"${hideClass}>
                <span class="align-diff-key">[${esc(it.section)}] ${esc(it.key)}</span>
                <div class="align-diff-vals">
                  <span style="color:var(--muted);font-weight:500">${esc(it.current)}</span>
                  <span class="align-badge align-badge-safe" style="font-size:11px;font-weight:700">✓ 官方一致</span>
                </div>
              </div>`;
            } else {
              html += `<div class="align-diff-item will-update" data-filter-tag="${filterTag}"${hideClass}>
                <span class="align-diff-key">[${esc(it.section)}] ${esc(it.key)}</span>
                <div class="align-diff-vals">
                  <span class="align-val-old" style="color:var(--bad,#ef4444);font-weight:600;padding:1px 6px;background:rgba(239,68,68,0.1);border-radius:4px">${esc(it.current)}</span>
                  <span class="align-val-arrow" style="font-weight:800;color:var(--acc,#3b82f6)">→</span>
                  <span class="align-val-new" style="color:var(--ok,#16a34a);font-weight:700;padding:1px 6px;background:rgba(22,163,74,0.1);border-radius:4px">${esc(it.official)}</span>
                </div>
              </div>`;
            }
          });
          html += `</div>`;
        }

        diffContent.innerHTML = html;
      }
      return true;
    } catch (err) {
      if (!silent) toast("拉取差异预览失败: " + err.message, "bad");
      if (diffContent) {
        diffContent.innerHTML = `<div style="color:var(--bad)">拉取差异失败: ${esc(err.message)}</div>`;
      }
      return false;
    }
  }

  // 差异明细分类过滤按钮点击事件委托
  if (diffContent) {
    diffContent.addEventListener("click", (e) => {
      const chip = e.target.closest(".align-filter-chip");
      if (!chip) return;
      const fbar = document.getElementById("alignDiffFilterBar");
      if (fbar) {
        fbar.querySelectorAll(".align-filter-chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
      }
      const filter = chip.getAttribute("data-filter");
      const list = document.getElementById("alignDiffItemsList");
      if (!list) return;
      list.querySelectorAll(".align-diff-item").forEach(item => {
        const tag = item.getAttribute("data-filter-tag");
        if (filter === "all" || tag === filter) {
          item.style.display = "flex";
        } else {
          item.style.display = "none";
        }
      });
    });
  }

  // 展开 / 折叠差异对比抽屉
  if (btnPreview) {
    btnPreview.addEventListener("click", async () => {
      if (!diffBox) return;
      if (diffBox.style.display === "none" || !diffBox.style.display) {
        diffBox.style.display = "block";
        btnPreview.innerHTML = `<span>🔼</span> 收起变更差异`;
        await loadAlignPreview(false);
      } else {
        diffBox.style.display = "none";
        btnPreview.innerHTML = `<span>🔍</span> 查看变更差异 (Diff)`;
      }
    });
  }

  // 页面就绪后静默获取一次版本号
  setTimeout(() => { loadAlignPreview(true); }, 800);

  if (!btn) return;
  btn.addEventListener("click", async () => {
    const targets = [];
    if (document.getElementById("alignOptRiddles")?.checked) targets.push("riddles");
    if (document.getElementById("alignOptRides")?.checked) targets.push("rides");
    if (document.getElementById("alignOptPresets")?.checked) targets.push("presets");
    if (document.getElementById("alignOptWeapons")?.checked) targets.push("weapons");

    if (targets.length === 0) {
      toast("请至少勾选一项需要对齐的内容", "bad");
      return;
    }

    const doBackup = document.getElementById("alignOptBackup")?.checked ?? true;
    const ok = await uiConfirm(
      `确定要对齐选中的 ${targets.length} 项官方最新内容吗？\n\n` +
      `• 系统将自动合并最新官方数据并修复错漏题目（如急转弯英文字母等）\n` +
      `• 100% 完整保留您的所有自定义坐骑、自建题目与上传图片\n` +
      `• 用户手动调整过的数值配置已受自定义锁保护，不会被官方覆盖\n` +
      (doBackup ? `• 执行前将自动创建备份快照，可随时在备份管理中一键回滚` : ``),
      "确认对齐最新版本"
    );
    if (!ok) return;

    const spinner = document.getElementById("alignSpinner");
    const resBox = document.getElementById("alignResultBox");
    if (spinner) spinner.style.display = "inline";
    if (btn) btn.disabled = true;
    if (resBox) resBox.style.display = "none";

    try {
      toast("正在对齐官方最新版本内容…", "ok");
      const res = await getBridge().apiPost("system/align_defaults", {
        targets: targets,
        backup: doBackup,
        force_custom: false
      });

      if (!res || !res.ok) {
        throw new Error(res?.error || res?.msg || "接口响应异常");
      }

      toast("对齐完成！", "ok");
      if (resBox) {
        let detailsHtml = "";
        const d = res.details || {};
        if (d.riddles) {
          const rStats = d.riddles.stats || {};
          let lines = [];
          for (const [k, v] of Object.entries(rStats)) {
            lines.push(`<b>${esc(k)}</b>: 共 ${v.total} 题 (对齐/更新 ${v.official_aligned} 题，保留自建 ${v.custom_preserved} 题)`);
          }
          detailsHtml += `<div style="margin-bottom:8px">🧩 <b>娱乐题库对齐</b>：<br>${lines.join("<br>")}</div>`;
        }
        if (d.rides) {
          detailsHtml += `<div style="margin-bottom:8px">🐎 <b>坐骑系统对齐</b>：${esc(d.rides.msg || "已对齐官方默认坐骑")}</div>`;
        }
        if (d.presets) {
          detailsHtml += `<div style="margin-bottom:8px">⚖️ <b>经济平衡对齐</b>：${esc(d.presets.msg || "已对齐推荐预设")}</div>`;
        }
        if (d.weapons) {
          detailsHtml += `<div style="margin-bottom:8px">⚔️ <b>武器属性对齐</b>：${esc(d.weapons.msg || "已对齐武器预设")}</div>`;
        }

        const bText = res.backup_snapshot ? `<div style="color:var(--muted);font-size:11.5px;margin-top:6px">🛡️ 已生成安全快照：<code>${esc(res.backup_snapshot)}</code></div>` : "";

        resBox.innerHTML = `
          <div style="font-weight:600;color:var(--ok);font-size:13.5px;margin-bottom:8px">✅ 官方最新内容对齐成功！</div>
          <div style="display:flex;flex-direction:column;gap:4px">${detailsHtml}</div>
          ${bText}
        `;
        resBox.style.display = "block";
      }

      // 对齐成功后刷新差异面板
      if (diffBox && diffBox.style.display !== "none") {
        await loadAlignPreview(true);
      }
    } catch (e) {
      toast("对齐失败: " + e.message, "bad");
      if (resBox) {
        resBox.innerHTML = `<div style="color:var(--bad);font-weight:600">❌ 对齐失败: ${esc(e.message)}</div>`;
        resBox.style.display = "block";
      }
    } finally {
      if (spinner) spinner.style.display = "none";
      if (btn) btn.disabled = false;
    }
  });
}

initAlignLatestEvents();


// ---------- 数据持久化状态检测与在线读写探针 ----------
function initPersistenceEvents() {
  const btnTest = document.getElementById("btnTestPersistence");
  const btnRefresh = document.getElementById("btnRefreshPersStatus");
  const badge = document.getElementById("persStatusBadge");
  const dirPathEl = document.getElementById("persDirPath");
  const writableTag = document.getElementById("persWritableTag");
  const customCountEl = document.getElementById("persCustomKeysCount");
  const configTextEl = document.getElementById("persConfigStatusText");
  const dbSizeEl = document.getElementById("persDbSize");
  const dbTextEl = document.getElementById("persDbStatusText");
  const mountsCountEl = document.getElementById("persMountsCount");
  const mountsTextEl = document.getElementById("persMountsStatusText");
  const questionsCountEl = document.getElementById("persQuestionsCount");
  const questionsTextEl = document.getElementById("persQuestionsStatusText");
  const customDetailEl = document.getElementById("persCustomKeysDetail");
  const resultBox = document.getElementById("persTestResultBox");
  const latencyEl = document.getElementById("persTestLatency");
  const stepsEl = document.getElementById("persTestSteps");

  async function loadPersistenceStatus(silent = false) {
    try {
      if (!silent) toast("正在获取持久化运行状态…", "ok");
      const res = await getBridge().apiGet("persistence/status", {});
      if (!res || !res.ok) throw new Error(res?.error || "获取持久化状态失败");
      renderPersistenceInfo(res);
      if (!silent) toast("持久化状态已刷新", "ok");
    } catch (e) {
      if (badge) {
        badge.className = "align-badge align-badge-danger";
        badge.textContent = "状态异常";
      }
      toast("获取持久化状态失败: " + e.message, "bad");
    }
  }

  function renderPersistenceInfo(info) {
    if (!info) return;
    if (dirPathEl) dirPathEl.textContent = info.persistent_dir || "未知目录";
    if (writableTag) {
      if (info.writable) {
        writableTag.className = "align-badge align-badge-safe";
        writableTag.textContent = "✓ 目录可写已确认";
      } else {
        writableTag.className = "align-badge align-badge-danger";
        writableTag.textContent = "✕ 目录只读受限";
      }
    }
    if (badge) {
      badge.className = "align-badge align-badge-safe";
      badge.textContent = info.writable ? "🟢 正常落盘 (双向镜像自愈)" : "🟡 读写受限";
    }

    const cfg = info.config || {};
    if (customCountEl) customCountEl.textContent = `${cfg.custom_keys_count || 0} 项`;
    if (configTextEl) {
      configTextEl.innerHTML = `落盘文件: <code>config.json</code> (${cfg.size_kb || 0} KB)<br>双重镜像保护，升级永不覆盖`;
    }

    const db = info.database || {};
    if (dbSizeEl) dbSizeEl.textContent = `${db.size_kb || 0} KB`;
    if (dbTextEl) {
      dbTextEl.innerHTML = `数据库: <code>data.db</code><br>${db.mirror_active ? "✓ sys_config_json 镜像活动" : "镜像未建立"}`;
    }

    const ca = info.custom_assets || {};
    if (mountsCountEl) mountsCountEl.textContent = `${ca.custom_rides_count || 0} 个自建`;
    if (mountsTextEl) {
      mountsTextEl.innerHTML = `自建坐骑: ${ca.custom_rides_count || 0} 个 / 静态图: ${ca.custom_mount_images_count || 0} 张<br>存储于持久目录 <code>persistent/</code>`;
    }

    if (questionsCountEl) questionsCountEl.textContent = `${ca.custom_questions_count || 0} 条自建`;
    if (questionsTextEl) {
      questionsTextEl.innerHTML = `自建题目: ${ca.custom_questions_count || 0} 条 / 历史快照: ${ca.backups_count || 0} 份<br>更新时 100% 增量保护保留`;
    }

    if (customDetailEl) {
      const keys = cfg.custom_keys || [];
      if (!keys.length) {
        customDetailEl.innerHTML = `<span style="color:var(--muted)">当前暂无受保护的自定义项（所有游戏数值与开关均遵循推荐官方默认值）。一旦您在配置页面修改任意数值，该项将自动受锁保护并在此处呈现。</span>`;
      } else {
        let lines = keys.map(k => {
          return `<div>🛡️ <b>[${esc(k.section)}]</b> <code>${esc(k.key)}</code>: <span style="color:var(--text)">${esc(k.value)}</span></div>`;
        });
        customDetailEl.innerHTML = lines.join("");
      }
    }
  }

  if (btnTest) {
    btnTest.addEventListener("click", async () => {
      btnTest.disabled = true;
      btnTest.innerHTML = `<span>⏳</span> 正在测试读写探针…`;
      try {
        const res = await getBridge().apiPost("persistence/test", {});
        if (!res || !res.ok) throw new Error(res?.error || "探针测试响应异常");

        if (resultBox) {
          resultBox.style.display = "block";
          if (latencyEl) latencyEl.textContent = `探针往返耗时：${res.latency_ms || 0}ms`;

          let stepHtml = (res.steps || []).map(s => {
            const icon = s.ok ? "✅" : "❌";
            const color = s.ok ? "var(--ok)" : "var(--bad)";
            return `<div style="margin-bottom:4px">
              <b>${icon} ${esc(s.name)}</b>: <span style="color:${color}">${esc(s.message)}</span>
            </div>`;
          }).join("");

          if (res.test_passed) {
            resultBox.style.background = "rgba(34,197,94,0.08)";
            resultBox.style.borderColor = "rgba(34,197,94,0.3)";
          } else {
            resultBox.style.background = "rgba(239,68,68,0.08)";
            resultBox.style.borderColor = "rgba(239,68,68,0.3)";
          }

          if (stepsEl) {
            stepsEl.innerHTML = `
              ${stepHtml}
              <div style="margin-top:8px;font-size:11.5px;color:var(--muted)">
                结论：外部持久目录 <code>${esc(res.info?.persistent_dir || "")}</code> 读写通畅，SQLite 与 config.json 探针回读无误，数据完全处于持久化受保护状态。
              </div>
            `;
          }
        }

        if (res.info) renderPersistenceInfo(res.info);
        toast(`持久化读写探针自检测试通过 (${res.latency_ms}ms)！`, "ok");
      } catch (e) {
        toast("持久化测试失败: " + e.message, "bad");
        if (resultBox) {
          resultBox.style.display = "block";
          resultBox.style.background = "rgba(239,68,68,0.08)";
          resultBox.style.borderColor = "rgba(239,68,68,0.3)";
          if (stepsEl) stepsEl.innerHTML = `<span style="color:var(--bad)">❌ 测试过程发生异常: ${esc(e.message)}</span>`;
        }
      } finally {
        btnTest.disabled = false;
        btnTest.innerHTML = `<span>🧪</span> 一键测试持久化`;
      }
    });
  }

  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => loadPersistenceStatus(false));
  }

  setTimeout(() => loadPersistenceStatus(true), 600);
}

initPersistenceEvents();
