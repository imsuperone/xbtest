// ---------- 奴隶系统用户视图 ----------
let RAW_SLAVE_USERS = [];
async function loadSlaveUsers(){
  try{
    RAW_SLAVE_USERS = await getBridge().apiGet("slave/users");
    if (!Array.isArray(RAW_SLAVE_USERS)) throw new Error((RAW_SLAVE_USERS && (RAW_SLAVE_USERS.error || RAW_SLAVE_USERS.msg)) || "奴隶用户接口异常");
    renderSlaveTable();
  }catch(e){ err("slave users: "+e.message); try { TAB_DONE.slave = false; } catch(_e){} }
}

function formatWeaponsCell(weaponsStr) {
  if (!weaponsStr) return '<span style="color:var(--muted)">-</span>';
  const list = String(weaponsStr).split('|').map(s => s.trim()).filter(Boolean);
  if (!list.length) return '<span style="color:var(--muted)">-</span>';
  const maxShow = 2;
  const show = list.slice(0, maxShow);
  const badges = show.map(w => `<span class="badge badge-warn" style="white-space:nowrap;font-size:11px;padding:2px 7px;line-height:1.2">${esc(w)}</span>`).join('');
  const more = list.length > maxShow ? `<span class="badge badge-primary" style="white-space:nowrap;font-size:11px;padding:2px 6px;cursor:pointer;line-height:1.2" title="${esc(list.join('\n'))}">+${list.length - maxShow}</span>` : '';
  return `<div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center;min-width:160px;max-width:240px">${badges}${more}</div>`;
}

function formatProtectCell(protectStr) {
  if (!protectStr) return '<span style="color:var(--muted)">-</span>';
  return `<span class="badge badge-success" style="white-space:nowrap;font-size:11px;padding:2px 7px;line-height:1.2">${esc(protectStr)}</span>`;
}

function renderSlaveTable() {
  const body = document.getElementById("slaveBody");
  if (!body) return;
  const q2 = (document.getElementById("slaveSearch")?.value || "").trim().toLowerCase();
  let rows = [...RAW_SLAVE_USERS];
  if (q2) {
    rows = rows.filter(r => (String(r.qq) + String(r.name || "") + String(r.owner || "") + String(r.gid || "")).toLowerCase().includes(q2));
  }
  const sortMode = document.getElementById("slaveSort")?.value || "price_desc";
  if (sortMode === "price_desc") rows.sort((a, b) => (b.price || 0) - (a.price || 0));
  else if (sortMode === "price_asc") rows.sort((a, b) => (a.price || 0) - (b.price || 0));
  else if (sortMode === "slaves_desc") rows.sort((a, b) => (b.slaves || 0) - (a.slaves || 0));
  else if (sortMode === "slaves_asc") rows.sort((a, b) => (a.slaves || 0) - (b.slaves || 0));
  else if (sortMode === "qq_asc") rows.sort((a, b) => String(a.qq).localeCompare(String(b.qq)));
  else if (sortMode === "qq_desc") rows.sort((a, b) => String(b.qq).localeCompare(String(a.qq)));

  const sHint = document.getElementById("slaveHint");
  if (sHint) {
    sHint.innerHTML = `共 <strong>${RAW_SLAVE_USERS.length}</strong> 条奴隶档案（当前匹配 <strong>${rows.length}</strong> 条） · 实时展示身价与主奴武装关系`;
  }
  let html = "";
  if (!rows.length) html = `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--muted)">暂无奴隶数据</td></tr>`;
  else html = rows.map(r => `<tr>
    <td><span class="badge badge-primary">${esc(r.gid)}</span></td>
    <td><strong>${esc(r.qq)}</strong></td>
    <td>${esc(r.name||"")}</td>
    <td>${r.owner ? `<span class="badge badge-purple">${esc(r.owner)}</span>` : '<span style="color:var(--muted)">自由身</span>'}</td>
    <td><span style="font-weight:700;color:var(--text)">${(r.price || 0).toLocaleString()}</span></td>
    <td><span class="badge badge-primary">${r.slaves || 0} 人</span></td>
    <td>${formatProtectCell(r.protect)}</td>
    <td>${formatWeaponsCell(r.weapons)}</td>
  </tr>`).join("");
  body.innerHTML = html;
}

// ---------- 精灵系统用户视图 ----------
let RAW_SPIRIT_USERS = [];
async function loadSpiritUsers(){
  try{
    RAW_SPIRIT_USERS = await getBridge().apiGet("spirit/users");
    if (!Array.isArray(RAW_SPIRIT_USERS)) throw new Error((RAW_SPIRIT_USERS && (RAW_SPIRIT_USERS.error || RAW_SPIRIT_USERS.msg)) || "精灵用户接口异常");
    renderSpiritUsersTable();
  }catch(e){ err("spirit users: "+e.message); try { TAB_DONE.spirit_users = false; } catch(_e){} }
}

function renderSpiritUsersTable() {
  const body = document.getElementById("spiritUsersBody");
  if (!body) return;
  const q2 = (document.getElementById("spiritUserSearch")?.value || "").trim().toLowerCase();
  let rows = [...RAW_SPIRIT_USERS];
  if (q2) {
    rows = rows.filter(r => (String(r.qq) + String(r.name || "") + String(r.active || "") + String(r.best || "") + String(r.gid || "")).toLowerCase().includes(q2));
  }
  const sortMode = document.getElementById("spiritUserSort")?.value || "power_desc";
  if (sortMode === "power_desc") rows.sort((a, b) => (b.total_power || 0) - (a.total_power || 0));
  else if (sortMode === "power_asc") rows.sort((a, b) => (a.total_power || 0) - (b.total_power || 0));
  else if (sortMode === "level_desc") rows.sort((a, b) => (b.max_level || 0) - (a.max_level || 0));
  else if (sortMode === "level_asc") rows.sort((a, b) => (a.max_level || 0) - (b.max_level || 0));
  else if (sortMode === "count_desc") rows.sort((a, b) => (b.count || 0) - (a.count || 0));
  else if (sortMode === "count_asc") rows.sort((a, b) => (a.count || 0) - (b.count || 0));
  else if (sortMode === "qq_asc") rows.sort((a, b) => String(a.qq).localeCompare(String(b.qq)));
  else if (sortMode === "qq_desc") rows.sort((a, b) => String(b.qq).localeCompare(String(a.qq)));

  const spHint = document.getElementById("spiritUsersHint");
  if (spHint) {
    spHint.innerHTML = `共 <strong>${RAW_SPIRIT_USERS.length}</strong> 名训练师（当前匹配 <strong>${rows.length}</strong> 名） · 统计出战精灵与综合战力`;
  }
  let html = "";
  if (!rows.length) html = `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--muted)">暂无精灵数据</td></tr>`;
  else html = rows.map(r => `<tr>
    <td><span class="badge badge-primary">${esc(r.gid)}</span></td>
    <td><strong>${esc(r.qq)}</strong></td>
    <td>${esc(r.name||"")}</td>
    <td><span class="badge badge-primary">${r.count || 0} 只</span></td>
    <td>${r.active ? `<span class="badge badge-success">${esc(r.active)}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
    <td>${r.best ? `<span class="badge badge-purple">${esc(r.best)}</span>` : '<span style="color:var(--muted)">-</span>'}</td>
    <td><span class="badge badge-warn">Lv.${r.max_level || 0}</span></td>
    <td><span style="font-weight:700;color:var(--text)">${(r.total_power || 0).toLocaleString()}</span></td>
  </tr>`).join("");
  body.innerHTML = html;
}
// 备份（文件夹式，与图片库一致）
let BACKUP_DIR = "";
let BACKUP_CACHE = null;
async function loadBackups(dir="") {
  try {
    BACKUP_DIR = dir || "";
    const d = await getBridge().apiGet("backups/list", BACKUP_DIR ? { dir: BACKUP_DIR } : {});
    if (!d || d.error) throw new Error((d && (d.error || d.msg)) || "备份列表接口异常");
    BACKUP_CACHE = d;
    const crumbs = (d.dir || "").split("/").filter(Boolean);
    let crumb = `<a data-bkcrumb="" class="crumb-link" title="返回根目录">📁 备份根目录</a>`;
    let acc = "";
    crumbs.forEach((s) => {
      acc += (acc ? "/" : "") + s;
      crumb += ` <span class="crumb-sep">/</span> <a data-bkcrumb="${esc(acc)}" class="crumb-link" title="进入目录 ${esc(s)}">📁 ${esc(s)}</a>`;
    });
    document.getElementById("backupCrumbs").innerHTML = `<span class="crumbs">${crumb}</span>`;
    document.querySelectorAll("#backupCrumbs a[data-bkcrumb]").forEach((a) => a.addEventListener("click", () => loadBackups(a.dataset.bkcrumb)));
    renderBackups(d);
  } catch (e) { err("backups: " + e.message); try { TAB_DONE.backups = false; } catch (_e) {} }
}
function renderBackups(d, _q) {
  const box = document.getElementById("backupBrowser");
  const q = (typeof _q === "string" ? _q : (document.getElementById("backupSearch")?.value || "")).trim().toLowerCase();
  if (typeof window.BACKUP_SELECTED === 'undefined') window.BACKUP_SELECTED = "";
  let html = `<div class="bk-list">`;
  (d.dirs || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    const selCls = window.BACKUP_SELECTED === x.path ? ' selected' : '';
    html += `<div class="bk-item${selCls}" data-bkdir="${esc(x.path)}" data-bksel="${esc(x.path)}">
      <div class="bk-icon" style="font-size:24px;line-height:1;display:flex;align-items:center;justify-content:center">📁</div>
      <div class="bk-info">
        <div class="bk-name">
          <span>${esc(x.name)}</span>
        </div>
        <div class="bk-meta"><span>双击进入查看快照</span><span>${esc(x.mtime || "")}</span></div>
      </div>
      <button class="ghost sm" style="pointer-events:none">进入 ➔</button>
    </div>`;
  });
  (d.files || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    const selCls = window.BACKUP_SELECTED === x.path ? ' selected' : '';
    const ext = (x.name.split(".").pop() || "").toLowerCase();
    const isDb = ["db", "sqlite", "sqlite3"].includes(ext);
    const isJson = ext === "json";
    const isZip = ["zip", "gz", "tar"].includes(ext);

    let icon = "📄";
    if (isDb) {
      icon = "🗄️";
    } else if (isJson) {
      icon = "📋";
    } else if (isZip) {
      icon = "📦";
    }

    html += `<div class="bk-item${selCls}" data-bkfile="${esc(x.path)}" data-bksel="${esc(x.path)}">
      <div class="bk-icon" style="font-size:24px;line-height:1;display:flex;align-items:center;justify-content:center">${icon}</div>
      <div class="bk-info">
        <div class="bk-name">
          <span>${esc(x.name)}</span>
        </div>
        <div class="bk-meta"><span>大小: ${esc(x.size || "0KB")}</span><span>备份时间: ${esc(x.mtime || "")}</span></div>
      </div>
      <span style="font-size:12px;color:var(--muted)">${selCls ? '✅ 已选中' : '⚪ 单击选中'}</span>
    </div>`;
  });
  html += `</div>`;
  if (!(d.dirs || []).length && !(d.files || []).length) {
    html = `<div class="hint" style="padding:20px;text-align:center;background:var(--panel);border:1px solid var(--line);border-radius:8px">暂无备份文件，系统将每隔设定时间自动备份，您也可点击上方「立即备份」生成。</div>`;
  }
  box.innerHTML = html;
  // 单击选中（高亮），文件夹双击进入
  box.querySelectorAll("[data-bksel]").forEach((el) => {
    el.addEventListener("click", () => {
      window.BACKUP_SELECTED = el.dataset.bksel;
      box.querySelectorAll(".bk-item").forEach(c => c.classList.remove("selected"));
      el.classList.add("selected");
    });
  });
  box.querySelectorAll("[data-bkdir]").forEach((el) => {
    el.addEventListener("dblclick", () => loadBackups(el.dataset.bkdir));
  });
}
// 立即生成本地冷备（带防抖与忙态保护）
document.getElementById("btnBackupNow")?.addEventListener("click", async () => {
  const btn = document.getElementById("btnBackupNow");
  if (btn && btn.disabled) return;
  const origTxt = btn ? btn.textContent : "立即备份";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "正在生成备份...";
  }
  toast("正在打包并生成本地数据冷备...", "ok", 3000);
  try {
    const r = await getBridge().apiPost("backups/create", {});
    if (r && r.ok && r.path) {
      toast("本地冷备已生成: " + r.path, "ok", 4000);
    } else {
      toast("备份失败: " + ((r && (r.error || r.msg)) || "服务端未返回路径"), "bad", 5000);
    }
    await loadBackups("");
  } catch (e) {
    await loadBackups("");
    toast("备份失败: " + ((e && e.message) || e || "请求异常"), "bad", 5000);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origTxt;
    }
  }
});
document.getElementById("btnBackupRefresh")?.addEventListener("click", () => loadBackups(BACKUP_DIR));

// 测试 WebDAV 连接
document.getElementById("btnWebDAVTest")?.addEventListener("click", async () => {
  const btn = document.getElementById("btnWebDAVTest");
  const msgEl = document.getElementById("backupCfgMsg");
  if (btn && btn.disabled) return;
  const origTxt = btn ? btn.textContent : "测试 WebDAV";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "测试连接中...";
  }
  if (msgEl) {
    msgEl.textContent = "正在发起 WebDAV 连接测试...";
    msgEl.className = "msg";
  }
  toast("正在连接测试 WebDAV...", "ok", 4000);
  try {
    const g = (id) => (document.getElementById(id) || {}).value ?? "";
    const payload = {
      url: g("wdUrl").trim(),
      user: g("wdUser").trim(),
      pwd: g("wdPwd"),
      dir: g("wdDir").trim()
    };
    const res = await getBridge().apiPost("backup/webdav/test", payload);
    if (res && res.ok) {
      const succMsg = res.msg || "WebDAV 连接与鉴权成功";
      if (msgEl) { msgEl.textContent = succMsg; msgEl.className = "msg ok"; }
      toast("WebDAV 测试成功: " + succMsg, "ok", 6000);
      await loadRemoteWebDAVFiles();
    } else {
      const errMsg = (res && res.msg) ? res.msg : ((res && res.error) ? res.error : "未知错误");
      if (msgEl) { msgEl.textContent = errMsg; msgEl.className = "msg bad"; }
      toast("WebDAV 测试失败: " + errMsg, "bad", 8000);
      uiAlert(errMsg, "WebDAV 测试失败");
    }
  } catch (err) {
    const errMsg = err.message || String(err);
    if (msgEl) { msgEl.textContent = errMsg; msgEl.className = "msg bad"; }
    toast("WebDAV 测试异常: " + errMsg, "bad", 8000);
    uiAlert(errMsg, "WebDAV 测试异常");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origTxt;
    }
  }
});

// 立即上传至 WebDAV 云端
document.getElementById("btnWebDAVBackupNow")?.addEventListener("click", async () => {
  const btn = document.getElementById("btnWebDAVBackupNow");
  const msgEl = document.getElementById("backupCfgMsg");
  if (btn && btn.disabled) return;
  const origTxt = btn ? btn.textContent : "立即上传云端";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "正在上传云端...";
  }

  const sel = window.BACKUP_SELECTED || "";
  let payload = {};
  let desc = "本地最新冷备";
  if (sel) {
    const ext = (sel.split(".").pop() || "").toLowerCase();
    if (["db", "json"].includes(ext)) {
      payload.path = sel;
      desc = sel.split("/").pop();
    } else {
      // .zip 等非备份文件禁默默传最新：此前静默改传，用户以为传了选中包
      if (msgEl) { msgEl.textContent = "请先选中 .db/.json 备份文件（不可上传 .zip 包）"; msgEl.className = "msg bad"; }
      toast("请先选中 .db/.json 备份文件", "bad");
      if (btn) { btn.disabled = false; btn.textContent = origTxt; }
      return;
    }
  }
  if (msgEl) {
    msgEl.textContent = `正在打包并上传 [${desc}] 至 WebDAV...`;
    msgEl.className = "msg";
  }
  toast(`正在上传 [${desc}] 至 WebDAV 云端...`, "ok", 4000);

  try {
    const res = await getBridge().apiPost("backup/webdav/upload", payload);
    if (res && res.ok) {
      const succMsg = res.msg || "已上传至 WebDAV 云端";
      if (msgEl) { msgEl.textContent = succMsg; msgEl.className = "msg ok"; }
      toast("WebDAV 云备份成功: " + succMsg, "ok", 6000);
      await loadBackups(BACKUP_DIR);
      await loadRemoteWebDAVFiles();
    } else {
      const errMsg = (res && res.msg) ? res.msg : "未能完成上传";
      if (msgEl) { msgEl.textContent = errMsg; msgEl.className = "msg bad"; }
      toast("WebDAV 上传失败: " + errMsg, "bad", 8000);
      uiAlert(errMsg, "WebDAV 上传失败");
    }
  } catch (err) {
    const errMsg = err.message || String(err);
    if (msgEl) { msgEl.textContent = errMsg; msgEl.className = "msg bad"; }
    toast("WebDAV 上传异常: " + errMsg, "bad", 8000);
    uiAlert(errMsg, "WebDAV 上传异常");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origTxt;
    }
  }
});

// 格式化为中国上海时区 (UTC+8) 中文日期时间
function formatShanghaiDate(mtimeStr, fileName) {
  const s = String(mtimeStr || "").trim();
  if (s && s.includes("年") && s.includes("月")) {
    return s;
  }
  if (s) {
    try {
      const d = new Date(s);
      if (!isNaN(d.getTime())) {
        const formatter = new Intl.DateTimeFormat("zh-CN", {
          timeZone: "Asia/Shanghai",
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false
        });
        const parts = formatter.formatToParts(d);
        const get = (t) => (parts.find(p => p.type === t) || {}).value || "";
        return `${get("year")}年${get("month")}月${get("day")}日 ${get("hour")}:${get("minute")}:${get("second")}`;
      }
    } catch (e) {}
  }
  if (fileName) {
    const m = String(fileName).match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
    if (m) {
      return `${m[1]}年${m[2]}月${m[3]}日 ${m[4]}:${m[5]}:${m[6]}`;
    }
  }
  return s || "-";
}



// ---------- 精灵系统背包独立大表与弹窗视图 ----------
let RAW_SPIRIT_BAG_ITEMS = [];

function getItemCategory(name) {
  const n = String(name || "");
  if (n.includes("球")) return { cat: "ball", label: "精灵球类", cls: "badge-primary" };
  if (n.includes("果") || n.includes("洗练")) return { cat: "fruit", label: "洗练果实", cls: "badge-success" };
  if (n.includes("结晶") || n.includes("液") || n.includes("源")) return { cat: "crystal", label: "进化结晶", cls: "badge-purple" };
  if (n.includes("糖") || n.includes("甜食")) return { cat: "candy", label: "经验糖果", cls: "badge-warn" };
  return { cat: "other", label: "特殊道具", cls: "badge-secondary" };
}

async function loadSpiritBag() {
  try {
    if (!RAW_SPIRIT_USERS || !RAW_SPIRIT_USERS.length) {
      RAW_SPIRIT_USERS = await getBridge().apiGet("spirit/users");
      if (!Array.isArray(RAW_SPIRIT_USERS)) RAW_SPIRIT_USERS = [];
    }
    // 扁平化所有训练师的背包项
    const items = [];
    for (const u of RAW_SPIRIT_USERS) {
      const bag = (u && typeof u.bag === "object" && u.bag) ? u.bag : {};
      for (const [itemName, count] of Object.entries(bag)) {
        const num = parseInt(count, 10) || 0;
        if (num <= 0) continue;
        const catInfo = getItemCategory(itemName);
        items.push({
          gid: u.gid,
          qq: u.qq,
          userName: u.name || u.qq,
          itemName: itemName,
          count: num,
          category: catInfo.cat,
          categoryLabel: catInfo.label,
          categoryCls: catInfo.cls
        });
      }
    }
    RAW_SPIRIT_BAG_ITEMS = items;
    renderSpiritBagTable();
  } catch(e) {
    err("load spirit bag: " + e.message);
    try { TAB_DONE.spirit_bag = false; } catch(_e){}
  }
}

function renderSpiritBagTable() {
  const body = document.getElementById("spiritBagBody");
  if (!body) return;
  const q = (document.getElementById("spiritBagSearch")?.value || "").trim().toLowerCase();
  const filterCat = document.getElementById("spiritBagFilter")?.value || "all";
  const sortMode = document.getElementById("spiritBagSort")?.value || "count_desc";

  let list = [...RAW_SPIRIT_BAG_ITEMS];
  if (filterCat !== "all") {
    list = list.filter(it => it.category === filterCat);
  }
  if (q) {
    list = list.filter(it => (String(it.qq) + String(it.gid) + String(it.userName) + String(it.itemName)).toLowerCase().includes(q));
  }

  if (sortMode === "count_desc") list.sort((a, b) => b.count - a.count);
  else if (sortMode === "count_asc") list.sort((a, b) => a.count - b.count);
  else if (sortMode === "qq_asc") list.sort((a, b) => String(a.qq).localeCompare(String(b.qq)));
  else if (sortMode === "item_asc") list.sort((a, b) => String(a.itemName).localeCompare(String(b.itemName)));

  const hint = document.getElementById("spiritBagHint");
  if (hint) {
    hint.innerHTML = `共统计到 <strong>${RAW_SPIRIT_BAG_ITEMS.length}</strong> 条道具记录（当前匹配 <strong>${list.length}</strong> 条） · 涵盖全群训练师背包资产`;
  }

  if (!list.length) {
    body.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--muted)">暂无背包道具数据</td></tr>`;
    return;
  }

  body.innerHTML = list.map(it => `<tr>
    <td><span class="badge badge-primary">${esc(it.gid)}</span></td>
    <td><strong>${esc(it.qq)}</strong></td>
    <td>${esc(it.userName)}</td>
    <td><strong style="color:var(--text)">${esc(it.itemName)}</strong></td>
    <td><span class="badge badge-warn" style="font-weight:700">×${it.count}</span></td>
    <td><span class="badge ${it.categoryCls}">${esc(it.categoryLabel)}</span></td>
    <td><button class="ghost sm" onclick="showTrainerBagModal('${esc(it.gid)}','${esc(it.qq)}')">查看全背包</button></td>
  </tr>`).join("");
}

function showTrainerBagModal(gid, qq) {
  const modal = document.getElementById("modalSpiritBagDetail");
  if (!modal) return;
  const user = (RAW_SPIRIT_USERS || []).find(u => String(u.gid) === String(gid) && String(u.qq) === String(qq));
  const title = document.getElementById("modalSpiritBagTitle");
  const content = document.getElementById("modalSpiritBagContent");

  const userName = user ? (user.name || user.qq) : qq;
  if (title) title.innerHTML = `🎒 训练师背包明细 · ${esc(userName)} <span style="font-size:12px;color:var(--muted)">(QQ:${esc(qq)} · 群:${esc(gid)})</span>`;

  const bag = (user && typeof user.bag === "object" && user.bag) ? user.bag : {};
  const entries = Object.entries(bag).filter(([_, n]) => (parseInt(n, 10) || 0) > 0);

  if (!entries.length) {
    content.innerHTML = `<div style="text-align:center;padding:32px;color:var(--muted)">该训练师当前背包空空如也，暂未拥有任何道具物品。</div>`;
  } else {
    content.innerHTML = `<div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(140px, 1fr));gap:12px;padding:8px 0">
      ${entries.map(([name, count]) => {
        const cat = getItemCategory(name);
        return `<div style="background:var(--bg-card,#f9f9f9);border:1px solid var(--border,#e5e5e5);border-radius:8px;padding:12px;text-align:center">
          <div style="font-size:13px;font-weight:700;margin-bottom:6px">${esc(name)}</div>
          <div style="font-size:18px;font-weight:800;color:var(--warn,#d97706);margin-bottom:6px">×${count}</div>
          <span class="badge ${cat.cls}" style="font-size:10px">${cat.label}</span>
        </div>`;
      }).join("")}
    </div>`;
  }
  modal.style.display = "flex";
}

// 绑定搜索与过滤事件
document.addEventListener("DOMContentLoaded", () => {
  const bSearch = document.getElementById("spiritBagSearch");
  const bFilter = document.getElementById("spiritBagFilter");
  const bSort = document.getElementById("spiritBagSort");
  const bRefresh = document.getElementById("btnSpiritBagRefresh");
  const bClose = document.getElementById("modalSpiritBagClose");
  const bModal = document.getElementById("modalSpiritBagDetail");

  if (bSearch) bSearch.addEventListener("input", renderSpiritBagTable);
  if (bFilter) bFilter.addEventListener("change", renderSpiritBagTable);
  if (bSort) bSort.addEventListener("change", renderSpiritBagTable);
  if (bRefresh) bRefresh.addEventListener("click", () => {
    RAW_SPIRIT_USERS = [];
    loadSpiritBag();
  });
  if (bClose) bClose.addEventListener("click", () => {
    if (bModal) bModal.style.display = "none";
  });
  if (bModal) bModal.addEventListener("click", (e) => {
    if (e.target === bModal) bModal.style.display = "none";
  });
});
