// ---------- 用户 / 财富 ----------
let RAW_USERS = [];
let USER_GID_FILTER = "";
let _USER_GIDS = new Set();

function populateUserGidOptions() {
  const sel = document.getElementById("userGidFilter");
  if (!sel) return;
  // 每次按当前数据重建（不清会残留已无用户的旧群号）
  _USER_GIDS = new Set();
  (RAW_USERS || []).forEach(u => { if (u.gid) _USER_GIDS.add(String(u.gid)); });
  const cur = sel.value;
  // 重建选项：保留“全部群” + 已知 gid 排序
  const gids = Array.from(_USER_GIDS).sort();
  sel.innerHTML = `<option value="">全部群</option>` + gids.map(g => `<option value="${esc(g)}">${esc(g)}</option>`).join("");
  // 恢复之前的选中
  if (cur && _USER_GIDS.has(cur)) sel.value = cur;
  else if (USER_GID_FILTER) sel.value = USER_GID_FILTER;
}

async function loadUsers() {
  try {
    const sel = document.getElementById("userGidFilter");
    const gid = (sel?.value || USER_GID_FILTER || "").trim();
    USER_GID_FILTER = gid;
    const params = gid ? { gid } : {};
    RAW_USERS = await getBridge().apiGet("users", params);
    if (!Array.isArray(RAW_USERS)) throw new Error((RAW_USERS && (RAW_USERS.error || RAW_USERS.msg)) || "用户列表接口异常");
    populateUserGidOptions();
    renderUserTable();
  } catch (e) {
    err("users: " + e.message);
    try { TAB_DONE.users = false; } catch (_e) {}
  }
}

function filterUsers() {
  renderUserTable();
}

function renderUserTable() {
  const body = document.getElementById("userBody");
  if (!body) return;
  let users = [...RAW_USERS];
  // 前端二次 gid 过滤（兼容后端未过滤或缓存数据）
  const gidFilter = (document.getElementById("userGidFilter")?.value || USER_GID_FILTER || "").trim();
  if (gidFilter) {
    users = users.filter(u => String(u.gid) === String(gidFilter));
  }
  // 搜索关键字联动过滤 (QQ/昵称/群号)
  const kw = (document.getElementById("userSearch")?.value || "").trim().toLowerCase();
  if (kw) {
    users = users.filter(u =>
      String(u.qq || "").toLowerCase().includes(kw) ||
      String(u.name || "").toLowerCase().includes(kw) ||
      String(u.gid || "").toLowerCase().includes(kw)
    );
  }
  const sortMode = (document.getElementById("userSort")?.value || "money_desc");
  if (sortMode === "money_desc") users.sort((a, b) => (b.money || 0) - (a.money || 0));
  else if (sortMode === "money_asc") users.sort((a, b) => (a.money || 0) - (b.money || 0));
  else if (sortMode === "deposit_desc") users.sort((a, b) => (b.deposit || 0) - (a.deposit || 0));
  else if (sortMode === "deposit_asc") users.sort((a, b) => (a.deposit || 0) - (b.deposit || 0));
  else if (sortMode === "stamina_desc") users.sort((a, b) => (b.stamina || 0) - (a.stamina || 0));
  else if (sortMode === "stamina_asc") users.sort((a, b) => (a.stamina || 0) - (b.stamina || 0));
  else if (sortMode === "charm_desc") users.sort((a, b) => (b.charm || 0) - (a.charm || 0));
  else if (sortMode === "charm_asc") users.sort((a, b) => (a.charm || 0) - (b.charm || 0));
  else if (sortMode === "tickets_desc") users.sort((a, b) => (b.lottery_tickets || 0) - (a.lottery_tickets || 0));
  else if (sortMode === "tickets_asc") users.sort((a, b) => (a.lottery_tickets || 0) - (b.lottery_tickets || 0));
  else if (sortMode === "sign_desc") users.sort((a, b) => (b.sign || 0) - (a.sign || 0));
  else if (sortMode === "sign_asc") users.sort((a, b) => (a.sign || 0) - (b.sign || 0));
  else if (sortMode === "qq_asc") users.sort((a, b) => String(a.qq).localeCompare(String(b.qq)));
  else if (sortMode === "qq_desc") users.sort((a, b) => String(b.qq).localeCompare(String(a.qq)));
  else if (sortMode === "gid_asc") users.sort((a, b) => String(a.gid || "").localeCompare(String(b.gid || "")));
  else if (sortMode === "gid_desc") users.sort((a, b) => String(b.gid || "").localeCompare(String(a.gid || "")));

  const hint = document.getElementById("userHint");
  if (hint) {
    hint.innerHTML = `共 <strong>${RAW_USERS.length}</strong> 名用户（当前匹配 <strong>${users.length}</strong> 名） · 直接改动数值后点右侧「保存」生效 · 点击表头可快捷排序`;
  }
  if (!users.length) {
    body.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:24px;color:var(--muted)">暂无匹配的用户数据</td></tr>`;
    return;
  }
  body.innerHTML = users
    .map((u) => {
      const nm = u.name ? esc(u.name) : '<span style="color:var(--muted)">-</span>';
      const inp = (id, v, w = 64) =>
        `<input type="number" id="${id}_${esc(u.qq)}_${esc(u.gid)}" value="${esc(v)}" title="${esc(v)}" style="width:${w}px;min-width:${w}px;font-size:12.5px;padding:5px 6px;font-variant-numeric:tabular-nums">`;
      return `<tr>
        <td><strong>${esc(u.qq)}</strong></td>
        <td>${nm}</td>
        <td><span class="badge badge-primary">${esc(u.gid)}</span></td>
        <td>${inp("mm", u.money, 96)}</td>
        <td>${inp("ck", u.deposit || 0, 96)}</td>
        <td>${inp("tt", u.stamina, 52)}</td>
        <td>${inp("ma", u.charm, 52)}</td>
        <td>${inp("jj", u.lottery_tickets || 0, 52)}</td>
        <td><span class="badge badge-success">${u.sign || 0}次</span></td>
        <td style="white-space:nowrap;text-align:center"><button data-save="user" data-qq="${esc(u.qq)}" data-gid="${esc(u.gid)}" class="sm">保存</button> <button class="ghost sm" data-export="user" data-qq="${esc(u.qq)}" data-gid="${esc(u.gid)}">导出</button> <button class="ghost sm del" data-clear="user" data-qq="${esc(u.qq)}" data-gid="${esc(u.gid)}" title="彻底清除该用户全部数据（含奴隶、精灵与礼包资格）">清除</button></td>
      </tr>`;
    })
    .join("");
  // 单用户导出/清除/保存统一走 #userBody 事件委托（见下方绑定），此处不再逐行直绑，
  // 避免搜索过滤/排序重渲染后绑定丢失与重复绑定导致“按钮无效/点两次”。
}

let _CLEARING_USERS = new Set();
async function clearUserSingle(qq, gid) {
  qq = String(qq || "").trim();
  gid = String(gid || "").trim();
  if (!qq || !gid) return;
  const ckey = gid + ":" + qq;
  if (_CLEARING_USERS.has(ckey)) return;
  // iframe 沙箱下原生 confirm 会被拦截导致按钮“无效”，统一用自研 uiConfirm（规则六二次确认）
  const ok = await uiConfirm(
    `确定要彻底清除用户【${qq}】（群: ${gid}）的所有数据吗？\n\n` +
    `将一并清除以下内容：\n` +
    `1. 钱包货币、银行存款、体力、魅力、奖券与签到记录\n` +
    `2. 奴隶系统：解除奴隶身份，且其名下持有的奴隶将全部释放自由\n` +
    `3. 精灵系统：拥有的所有精灵、出战骑乘状态与背包道具全部清除\n` +
    `4. 重置新手礼包与精灵领养状态（该用户可重新领取新手礼包）\n\n` +
    `此操作立即生效且不可逆，是否确定清除？`,
    "危险操作确认"
  );
  if (!ok) return;

  _CLEARING_USERS.add(ckey);
  try {
    toast("正在清理用户数据...", "info");
    let res = null;
    try {
      res = await getBridge().apiPost("user/clear", { gid, qq });
    } catch (e) {
      // 清除是破坏性操作，只允许 POST；禁止降级为可被预取的 GET。
    }
    if (res && (res.ok || res.saved || res.cleared)) {
      toast(res.msg || `用户 ${qq} 数据已彻底清除`, "ok");
      await loadUsers();
      if (typeof loadSlaveUsers === "function") try { await loadSlaveUsers(); } catch(e) {}
      if (typeof loadSpiritUsers === "function") try { await loadSpiritUsers(); } catch(e) {}
    } else {
      toast((res && (res.msg || res.error)) || "清除失败", "bad");
    }
  } catch (e) {
    toast("清除失败: " + e.message, "bad");
  } finally {
    _CLEARING_USERS.delete(ckey);
  }
}

async function clearUserManual() {
  const curGid = (document.getElementById("userGidFilter")?.value || (typeof USER_GID_FILTER !== "undefined" ? USER_GID_FILTER : "") || "").trim();
  // iframe 下原生 prompt 会被拦截，统一用 uiPrompt
  const qq = await uiPrompt("请输入要彻底清除数据的用户 QQ 号：", "", "清除单用户");
  if (qq === null || qq === undefined) return;
  if (!String(qq).trim() || !/^\d{5,12}$/.test(String(qq).trim())) { if (String(qq).trim()) toast("QQ 号格式不正确", "bad"); return; }
  const targetQq = String(qq).trim();
  let targetGid = curGid;
  if (!targetGid) {
    const gInput = await uiPrompt(`请输入用户【${targetQq}】所在的群号：`, "", "清除单用户");
    if (gInput === null || gInput === undefined) return;
    if (!String(gInput).trim()) {
      toast("已取消操作：必须提供群号", "bad");
      return;
    }
    targetGid = String(gInput).trim();
  }
  await clearUserSingle(targetQq, targetGid);
}

async function saveUserEdit(qq, gid, btn) {
  const get = (p) => { const el = document.getElementById(p + "_" + qq + "_" + gid); return el ? el.value : ""; };
  const payload = { qq, gid, money: get("mm"), stamina: get("tt"), charm: get("ma"), lottery_tickets: get("jj"), deposit: get("ck") };
  try {
    const r = await getBridge().apiPost("user/edit", payload);
    if (r && r.error) throw new Error(r.error);
    toast("用户数据已保存", "ok");
    if (btn) { btn.textContent = "已存"; setTimeout(() => { btn.textContent = "保存"; }, 1500); }
    await loadUsers();
    return r;
  } catch (e) {
    err("保存失败: " + e.message);
  }
}


async function cleanLeftUsers() {
  const gid = (document.getElementById("userGidFilter")?.value || USER_GID_FILTER || "").trim();
  const scopeText = gid ? `群 ${gid}` : "全库所有群聊";
  const ok = await uiConfirm(
    `⚠️ 确认清理【${scopeText}】的退群人员？

系统将自动对比群聊实时成员列表，彻底删除已退群人员的钱包货币、奴隶身价关系、精灵背包与全部档案数据！`,
    "清理退群人员"
  );
  if (!ok) return;
  toast("正在对比群成员并清理退群人员...", "ok");
  try {
    // 清理退群：调 users/clean_left（曾误调 users/export，res.ok 恒真致“清理0人”假成功）
    // POST：GET 有副作用，禁走读通道（预取/重试误触发批量删除）
    const res = await callApi("users/clean_left", {}, "POST");
    if (res && res.ok) {
      toast(`清理完成！已清理 ${res.cleaned_count || 0} 名退群人员数据`, "ok");
      await loadUsers();
      if (typeof loadSlaveUsers === "function") try { await loadSlaveUsers(); } catch(e) {}
      if (typeof loadSpiritUsers === "function") try { await loadSpiritUsers(); } catch(e) {}
    } else {
      toast("清理失败: " + (res && (res.error || res.msg) ? (res.error || res.msg) : "无法获取实时群成员，请确保 Bot 正常在线且在群内"), "bad");
    }
  } catch (err) {
    toast("清理失败: " + err.message, "bad");
  }
}

async function exportAllUsers() {
  const filename = `xbbot_users_all_${Date.now()}.json`;
  toast("正在导出全量用户数据...", "ok");
  try {
    // 单次 callApi（GET空结果不再回退POST，失败兜底在callApi内）
    const res = await callApi("users/export", {}, "GET");
    if (!res) throw new Error("接口无响应");
    if (res.error || res.msg) throw new Error(res.error || res.msg);

    let usersList = null;
    let base64Data = res.data || "";

    if (Array.isArray(res.users)) {
      usersList = res.users;
    } else if (res.data && typeof res.data === "object" && Array.isArray(res.data.users)) {
      usersList = res.data.users;
    } else if (res.result && typeof res.result === "object" && Array.isArray(res.result.users)) {
      usersList = res.result.users;
    }

    if (usersList) {
      const payload = {
        count: usersList.length,
        users: usersList,
        export_at: res.export_at || Math.floor(Date.now() / 1000),
        version: res.version || "2026w0915e"
      };
      const jsonStr = JSON.stringify(payload, null, 2);
      triggerExportResult({
        filename: res.filename || filename,
        mime: "application/json;charset=utf-8",
        rawText: jsonStr,
        base64Data: base64Data
      });
      toast(`已成功全量导出 ${usersList.length} 名用户数据`, "ok");
      return;
    }

    if (base64Data && typeof base64Data === "string") {
      triggerExportResult({
        filename: res.filename || filename,
        mime: "application/json;charset=utf-8",
        base64Data: base64Data
      });
      toast("已成功全量导出用户数据", "ok");
      return;
    }

    const fallbackStr = typeof res === "string" ? res : JSON.stringify(res, null, 2);
    triggerExportResult({
      filename: filename,
      mime: "application/json;charset=utf-8",
      rawText: fallbackStr
    });
    toast("已成功全量导出用户数据", "ok");
  } catch (err) {
    toast("导出失败: " + err.message, "bad");
  }
}
async function importAllUsers() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json,application/json";
  inp.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const txt = await file.text();
      const data = JSON.parse(txt);
      // 兼容单用户与全量
      const payload = data.users ? data : { users: [data] };
      const r = await getBridge().apiPost("users/import", payload);
      toast(`已导入 ${r.imported}/${r.total}`, "ok");
      await loadUsers();
    } catch (err) { toast("导入失败: " + err.message, "bad"); }
  };
  inp.click();
}

// ---------- 指令(可编辑 唤醒词 / 回复内容 / 玩法数值) ----------
let CMD_CFG = {};           // 运行时配置(嵌套 dict) 供指令页读取/保存
let KNOWN_CMDS = new Set(); // 引擎指令白名单，供映射校验
let CMD_ENG = {};           // 指令->所属引擎键，供数值映射与权限显示
// 引擎->数值节：指令编辑器按所属系统自动列出全部可调数值（奖励/惩罚/概率/价格/间隔）
const ENG_NUM_SECTIONS = {
  slave: ["设置", "费用配置", "间隔配置", "概率配置", "祈福配置"],
  sign: ["签到配置", "抽奖配置", "新手配置", "点赞配置"],
  bank: ["银行配置"], ent: ["娱乐配置"], spirit: ["精灵配置"],
  ride: ["坐骑配置"], guild: ["帮派配置"], adventure: ["冒险配置"],
  superadmin: ["超管配置"],
};
const SYS_WAKE = {
  slave: "奴隶系统", sign: "签到系统", bank: "银行系统", ent: "娱乐系统",
  spirit: "精灵系统", ride: "坐骑系统",
  superadmin: "超管系统", guild: "帮派系统", adventure: "冒险系统",
};
const map2sys = SYS_WAKE;
// 玩法类指令 -> 关联配置格式(金额/奖励/概率/惩罚) [section, key, label, type]
const CMD_NUMS = {
  "签到": [["签到配置", "金钱下限", "现金下限", "int"], ["签到配置", "金钱上限", "现金上限", "int"],
    ["签到配置", "体力下限", "体力下限", "int"], ["签到配置", "体力上限", "体力上限", "int"],
    ["签到配置", "魅力下限", "魅力下限", "int"], ["签到配置", "魅力上限", "魅力上限", "int"],
    ["签到配置", "奖券下限", "奖券下限", "int"], ["签到配置", "奖券上限", "奖券上限", "int"]],
  "领取新手礼包": [["新手配置", "现金", "礼包现金", "int"], ["新手配置", "体力", "礼包体力", "int"],
    ["新手配置", "魅力", "礼包魅力", "int"], ["新手配置", "奖券", "礼包奖券", "int"]],
  "购买体力": [["签到配置", "体力价格", "体力价格", "int"]],
  "购买魅力": [["签到配置", "魅力价格", "魅力价格", "int"]],
  "抽奖": [["抽奖配置", "中奖率", "中奖率%", "int"], ["抽奖配置", "现金奖", "现金奖", "int"],
    ["抽奖配置", "体力奖", "体力奖", "int"], ["抽奖配置", "魅力奖", "魅力奖", "int"]],
  "存款": [["银行配置", "存款利率", "存款利率%", "int"], ["银行配置", "利息上限", "利息上限", "int"],
    ["银行配置", "存款期限", "存款期限(天)", "int"], ["银行配置", "存取款消耗体力", "消耗体力", "int"]],
  "取款": [["银行配置", "存款利率", "存款利率%", "int"], ["银行配置", "利息上限", "利息上限", "int"]],
  "强制取款": [["银行配置", "存款利率", "存款利率%", "int"], ["银行配置", "利息上限", "利息上限", "int"]],
  "转账": [["银行配置", "转账最小金额", "最小金额", "int"], ["银行配置", "转账接收额度", "接收额度", "int"],
    ["银行配置", "转账消耗体力", "消耗体力", "int"]],
  "发红包": [["银行配置", "红包_最小金额", "最小金额", "int"], ["银行配置", "红包_最大金额", "最大金额", "int"],
    ["银行配置", "红包_发体力", "发体力", "int"], ["银行配置", "红包_间隔时间", "间隔(秒)", "int"]],
  "抢红包": [["银行配置", "红包_抢体力", "抢体力", "int"], ["银行配置", "红包_抢魅力", "抢魅力", "int"],
    ["银行配置", "红包_基本魅力", "基础魅力", "int"]],
  "赌博": [["银行配置", "赌博成功概率", "成功概率%", "int"], ["银行配置", "赌博消耗体力", "消耗体力", "int"],
    ["银行配置", "赌博魅力减少", "魅力减少", "int"], ["银行配置", "赌博最大金额", "最大金额", "int"],
    ["银行配置", "赌博限定次数", "限定次数", "int"], ["银行配置", "赌博关押时间", "关押(分)", "int"]],
  "打劫": [["银行配置", "打劫成功概率", "成功概率%", "int"], ["银行配置", "打劫消耗体力", "消耗体力", "int"],
    ["银行配置", "打劫金钱下限", "金钱下限", "int"], ["银行配置", "打劫金钱上限", "金钱上限", "int"],
    ["银行配置", "打劫魅力减少", "魅力减少", "int"], ["银行配置", "打劫关押时间", "关押(分)", "int"]],
  "打劫银行": [["银行配置", "打劫银行成功概率", "成功概率%", "int"],
    ["银行配置", "打劫银行消耗体力", "消耗体力", "int"],
    ["银行配置", "打劫银行金钱下限", "金钱下限", "int"], ["银行配置", "打劫银行金钱上限", "金钱上限", "int"],
    ["银行配置", "打劫银行魅力减少", "魅力减少", "int"], ["银行配置", "打劫银行关押时间", "关押(分)", "int"]],
  "保释": [["银行配置", "保释金钱下限", "保释金下限", "int"], ["银行配置", "保释金钱上限", "保释金上限", "int"],
    ["银行配置", "保释消耗体力", "消耗体力", "int"], ["银行配置", "保释魅力减少", "魅力减少", "int"]],
  "我要越狱": [["银行配置", "越狱成功概率", "成功概率%", "int"], ["银行配置", "越狱消耗体力", "消耗体力", "int"],
    ["银行配置", "越狱魅力减少", "魅力减少", "int"], ["银行配置", "越狱关押时间", "关押(分)", "int"]],
  "精灵冒险": [["精灵配置", "挑战奖励_经验下限", "经验下限", "int"], ["精灵配置", "挑战奖励_经验上限", "经验上限", "int"],
    ["精灵配置", "挑战奖励_金钱下限", "金钱下限", "int"], ["精灵配置", "挑战奖励_金钱上限", "金钱上限", "int"],
    ["精灵配置", "等级加成下限", "等级加成下限", "int"], ["精灵配置", "等级加成上限", "等级加成上限", "int"],
    ["精灵配置", "冒险间隔", "冒险间隔(分)", "int"]],
  "丢弃精灵": [["精灵配置", "魅力减少", "魅力减少", "int"]],
  "保护": [["设置", "保护费用", "保护费用", "int"], ["设置", "保护时长小时", "保护时长(时)", "int"],
    ["间隔配置", "保护间隔", "保护间隔(分)", "int"]],
  "我要学习": [["设置", "奇遇触发概率", "奇遇概率%", "int"], ["间隔配置", "学习间隔", "学习间隔(分)", "int"]],
  "讨好": [["概率配置", "讨好概率", "讨好概率%", "int"], ["间隔配置", "讨好间隔", "讨好间隔(分)", "int"]],
  "造反": [["概率配置", "造反概率", "造反概率%", "int"], ["间隔配置", "造反间隔", "造反间隔(分)", "int"]],
  "十连抽": [["设置", "十连抽花费", "十连抽花费", "int"]],
  "三十连抽": [["设置", "三十连抽花费", "三十连抽花费", "int"]],
  "五十连抽": [["设置", "五十连抽花费", "五十连抽花费", "int"]],
  "买下": [["间隔配置", "购买间隔", "购买间隔(分)", "int"]],
  "折磨": [["间隔配置", "折磨间隔", "折磨间隔(分)", "int"]],
  "买奴隶位": [["设置", "奴隶位价格", "奴隶位价格", "int"]],
  "我要自由": [["费用配置", "初始身价", "初始身价", "int"]],
  "打架": [["间隔配置", "打架间隔", "打架间隔(分)", "int"]],
  "我要祈福": [["祈福配置", "祈福奖励下限", "奖励下限", "int"], ["祈福配置", "祈福奖励上限", "奖励上限", "int"],
    ["祈福配置", "人品爆发概率", "人品爆发概率%", "int"], ["祈福配置", "人品爆发奖励", "人品爆发奖励", "int"]],
  "升星": [["设置", "一星武器概率", "一星概率%", "int"], ["设置", "一星武器花费", "一星花费", "int"], ["设置", "一星武器消耗同武器数量", "一星消耗同武数", "int"], ["设置", "二星武器概率", "二星概率%", "int"], ["设置", "二星武器花费", "二星花费", "int"], ["设置", "二星武器消耗同武器数量", "二星消耗", "int"]],
  "升阶": [["设置", "一阶宝物概率", "一阶概率%", "int"], ["设置", "一阶宝物花费", "一阶花费", "int"]],
  "我要打工": [["间隔配置", "打工间隔", "打工间隔(分)", "int"], ["费用配置", "工资比例", "工资比例%", "int"]],
  "奴隶打工": [["间隔配置", "打工间隔", "打工间隔(分)", "int"], ["费用配置", "工资比例", "工资比例%", "int"]],
  "打工": [["间隔配置", "打工间隔", "打工间隔(分)", "int"]],
  "学习": [["间隔配置", "学习间隔", "学习间隔(分)", "int"], ["设置", "奇遇触发概率", "奇遇概率%", "int"]],
  "祈福": [["祈福配置", "祈福奖励下限", "奖励下限", "int"], ["祈福配置", "祈福奖励上限", "奖励上限", "int"]],
  "释放": [["间隔配置", "释放间隔", "释放间隔(分)", "int"]],
  "抽签": [["娱乐配置", "抽签造价", "抽签造价", "int"], ["娱乐配置", "抽签大吉奖励", "大吉奖励", "int"], ["娱乐配置", "抽签上签奖励", "上签奖励", "int"], ["娱乐配置", "抽签中签奖励", "中签奖励", "int"]],
  "猜拳": [["娱乐配置", "猜拳奖励金币", "奖励金币", "int"], ["娱乐配置", "猜拳奖励魅力", "奖励魅力", "int"], ["娱乐配置", "猜拳成功概率", "成功概率%", "int"], ["娱乐配置", "猜拳消耗体力", "消耗体力", "int"], ["娱乐配置", "猜拳需要金钱", "需要金钱", "int"]],
  "猜数": [["娱乐配置", "猜数奖励金币", "奖励金币", "int"], ["娱乐配置", "猜数奖励魅力", "奖励魅力", "int"], ["娱乐配置", "猜数消耗体力", "消耗体力", "int"], ["娱乐配置", "猜数需要金钱", "需要金钱", "int"]],
  "急转弯": [["娱乐配置", "急转弯奖励金币", "奖励金币", "int"], ["娱乐配置", "急转弯奖励魅力", "奖励魅力", "int"], ["娱乐配置", "急转弯消耗体力", "消耗体力", "int"], ["娱乐配置", "急转弯需要金钱", "需要金钱", "int"]],
  "猜字谜": [["娱乐配置", "猜字谜奖励金币", "奖励金币", "int"], ["娱乐配置", "猜字谜奖励魅力", "奖励魅力", "int"], ["娱乐配置", "猜字谜消耗体力", "消耗体力", "int"], ["娱乐配置", "猜字谜需要金钱", "需要金钱", "int"]],
  "接龙": [["娱乐配置", "接龙奖励金币", "奖励金币", "int"], ["娱乐配置", "接龙奖励魅力", "奖励魅力", "int"], ["娱乐配置", "接龙消耗体力", "消耗体力", "int"], ["娱乐配置", "接龙需要金钱", "需要金钱", "int"]],
  "答题": [["娱乐配置", "答题奖励金币", "奖励金币", "int"], ["娱乐配置", "答题奖励魅力", "奖励魅力", "int"], ["娱乐配置", "答题消耗体力", "消耗体力", "int"], ["娱乐配置", "答题需要金钱", "需要金钱", "int"]],
  "二四点": [["娱乐配置", "二四点奖励金币", "奖励金币", "int"], ["娱乐配置", "二四点奖励魅力", "奖励魅力", "int"], ["娱乐配置", "二四点消耗体力", "消耗体力", "int"], ["娱乐配置", "二四点需要金钱", "需要金钱", "int"]],
};

// 各玩法指令的默认回复示例(供指令页"默认回复"展示; 覆盖配置留空则用该默认)
// {变量} 为运行时动态数值占位符
const CMD_DEFAULT_REPLY = {
  "签到": "🏅 恭喜你签到成功！\r\n　奖励详情：\r\n　　　💵 货币 +{现金}\r\n　　　⚡ 体力 +{体力}\r\n　　　💄 魅力 +{魅力}\r\n　　　🎫 奖券 +{奖券}\r\n　　　🔥 第{天数}天连签 +{连签}\r\n当前货币：{当前}\r\n您是今天第{序号}个签到者！",
  "领取新手礼包": "恭喜您获得新手礼包一份！\r\n现金+{现金}\r\n体力+{体力}\r\n魅力+{魅力}\r\n奖券+{奖券}",
  "购买体力": "恭喜您花费{价格}货币，购买了{数量}点体力，您的体力提升到{当前}点！",
  "购买魅力": "恭喜您花费{价格}货币，购买了{数量}点魅力，您的魅力提升到{当前}点！",
  "个人信息": "您的账户信息如下：\r\n个人财富：{财富}\r\n签到次数：{签到}\r\n剩余体力：{体力}\r\n魅力指数：{魅力}\r\n奖券数量：{奖券}\r\n存款金额：{存款}",
  "抽奖": "恭喜，抽奖成功！获得{奖励}+{数值}",
  "存款": "存款成功！共存入：{金额}，上期结息：{利息}，当前总存款：{总额}",
  "取款": "取款成功！获得利息：{利息}，本次取款：{金额}，还剩存款：{剩余}",
  "强制取款": "强制取款成功！因未到取款时间，本次没有利息。本次取款：{金额}",
  "转账": "转账成功！您已向 {目标} 转入{金额}货币！",
  "发红包": "发红包啦！发了{金额}货币点，大家快抢吧！红包口令为：{口令}",
  "抢红包": "恭喜！你抢到了 {金额}货币，魅力+{魅力}！",
  "赌博": "赌博成功！你获得了{赢得}货币，净赚{净赚}！",
  "打劫": "打劫成功！你从 {目标} 处劫走{金额}货币！",
  "打劫银行": "打劫银行成功！获得{金额}货币！",
  "保释": "保释成功！花费{保释金}货币、{体力}体力，魅力-{魅力}。",
  "我要越狱": "越狱成功！扣除{体力}体力，你重获自由~",
  "买下": "成功买下{目标}\r\n本次买入花费：{花费}\r\n奴隶身价上涨：{上涨}\r\n奴隶现在身价：{身价}",
  "买奴隶位": "恭喜您花费{价格}货币\r\n买下一个奴隶位。\r\n当前可拥有奴隶上限：{上限}",
  "我要自由": "万恶的主人，大发善心，花费{价格}换取自由！",
  "保护": "恭喜您花费{费用}货币保护{目标}，剩余保护时间{分钟}分钟！",
  "折磨": "你对 [{目标}] 实施了折磨...\r\n【奇遇】{剧情}\r\n奴隶货币 +{数值}",
  "讨好": "摇摇尾巴~向你主人卖个萌，主人一开心给了你{金额}",
  "造反": "经过艰苦卓绝的战斗，你打败了万恶的主人，并恢复自由！抢走主人{金额}货币",
  "我要学习": "缴纳学费 {学费} 后开始学习! 武器经验 +{经验}\r\n🍀奇遇: {剧情}",
  "我要祈福": "笑~忍神大人心情不错，看着面前楚楚可怜的{名字}，一高兴赏了{金额}",
  "打架": "打架啦！\r\n我方派出奴隶：{队伍}\r\n对方派出奴隶：{队伍}\r\n本次战斗结果：胜利！获得对方赔款：{金额}",
  "精灵冒险": "【精灵冒险】来到{地图}，遭遇了野生的 Lv.{等级}「{精灵}」！",
  "丢弃精灵": "已丢弃精灵「{名字}」，魅力-{数值}",
  "升星": "成功升星{武器}！本次升星概率：{概率}%，武器不会消失哦~",
  "升阶": "升阶成功！本次升阶概率：{概率}%，本次升阶花费：{花费}",
};

let CMD_EDIT = { sys: "", cmd: "", isNew: false, mapCmd: "" };   // 当前模态框编辑的 系统/指令
let _CMD_CUST = {};          // 当次渲染的自定义指令节（供委托点击读取）
let _CMD_LIST_BOUND = false; // #cmdList 事件委托只绑一次，渲染不再逐行绑定

function _bindCmdListOnce() {
  const el = document.getElementById("cmdList");
  if (!el || _CMD_LIST_BOUND) return;
  _CMD_LIST_BOUND = true;
  el.addEventListener("click", (e) => {
    const addBtn = e.target.closest("#btnCmdAddCustom");
    if (addBtn && el.contains(addBtn)) {
      CMD_EDIT = { sys: "自定义", cmd: "", isNew: true, mapCmd: "" };
      openCmdEditor();
      return;
    }
    const a = e.target.closest("a.cmd-tag");
    if (!a || !el.contains(a)) return;
    CMD_EDIT.sys = a.dataset.sys;
    CMD_EDIT.cmd = a.dataset.cmd;
    CMD_EDIT.isNew = false;
    if (a.dataset.sys === "自定义") {
      const ce = (_CMD_CUST[a.dataset.cmd] || {});
      CMD_EDIT.mapCmd = (typeof ce === "object" && ce) ? (ce.command || "") : "";
    } else {
      CMD_EDIT.mapCmd = a.dataset.cmd;
    }
    openCmdEditor();
  });
  // toggle 不冒泡，用捕获在容器层统一接
  el.addEventListener("toggle", (e) => {
    const d = e.target;
    if (d && d.matches && d.matches("details.cmd-block") && d.open) {
      d.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, true);
  // 系统启用开关：列表上直接拨动即时保存生效（此前只在编辑器保存时顺带提交）
  el.addEventListener("change", (e) => {
    const inp = e.target && e.target.closest ? e.target.closest("input[data-syson]") : null;
    if (!inp || !el.contains(inp)) return;
    sysonImmediateSave(inp);
  });
  const exp = document.getElementById("btnCmdExpandAll");
  if (exp) exp.addEventListener("click", () => {
    document.querySelectorAll("#cmdList details.cmd-block").forEach((d) => { d.open = true; });
  });
  const col = document.getElementById("btnCmdCollapseAll");
  if (col) col.addEventListener("click", () => {
    document.querySelectorAll("#cmdList details.cmd-block").forEach((d) => { d.open = false; });
  });
}

async function loadCommands() {
  try {
    // 双接口并行（此前串行 2 RTT）
    const [cmds, cur] = await Promise.all([
      getBridge().apiGet("commands"),
      getBridge().apiGet("config/get")
    ]);
    CMD_CFG = cur || {};
    const wakeSec = CMD_CFG["唤醒词配置"] || {};
    const custSec = CMD_CFG["自定义指令配置"] || {};
    const onSec = CMD_CFG["系统开关配置"] || {};       // 系统级启用
    const disSec = CMD_CFG["指令启用配置"] || {};       // 指令级启用(假=禁用)
    const permSec = CMD_CFG["指令权限配置"] || {};       // 指令级权限(超管=仅超管)
    const setupSec = CMD_CFG["设置"] || {};
    const isOff = (v) => v === "假" || v === "0" || v === "false";
    const isOn = (v) => v === undefined || !isOff(v);
    const el = document.getElementById("cmdList");
    if (!el) return;
    // 重渲染前记住展开态，渲染后恢复（保存后不再全部收起）
    let _openSys = null;
    try {
      _openSys = new Set([...el.querySelectorAll("details.cmd-block[open]")].map((d) => d.dataset.sys));
    } catch (e) { _openSys = new Set(); }
    KNOWN_CMDS = new Set();
    CMD_ENG = {};
    Object.entries(cmds).forEach(([eng, arr]) => (arr || []).forEach((c) => {
      KNOWN_CMDS.add(c);
      if (!(c in CMD_ENG)) CMD_ENG[c] = eng;
    }));
    const blockHtml = Object.keys(cmds).filter(k => k !== "chat")
      .map((k) => {
        const sys = map2sys[k] || k;
        const wake = (wakeSec[sys] ?? sys);
        const wakeList = wake.split(/[|，,]/).map((s) => s.trim()).filter(Boolean);
        const seen = {};
        // 去掉「系统唤醒词」本身作为假指令的重复项(唤醒词已在块头部单独编辑)
        const items = (cmds[k] || []).filter((c) => {
          if (seen[c]) return false;
          seen[c] = 1;
          return wakeList.indexOf(c) < 0;
        });
        const sysChecked = isOn(onSec[sys]) ? "checked" : "";
        const tags = items.map((c) => {
          const cOn = isOn(disSec[c]);
          const onBg = cOn ? "" : "off";
          const isAdm = (((permSec[c] || "").trim()) === "超管");
          return `<a class="cmd-tag ${onBg}" data-on="${cOn ? "1" : "0"}" data-cmd="${esc(c)}" data-sys="${esc(sys)}">` +
            `${cOn ? '<span style="color:var(--ok);font-size:10px">●</span>' : '<span style="color:var(--muted);font-size:10px">○</span>'} ${isAdm ? "🔒" : ""}${esc(c)}</a>`;
        }).join("");
        return `<details class="cmd-block" data-sys="${esc(sys)}"><summary>` +
          `<span class="cmd-sys">${esc(sys)}</span>` +
          `<span class="cmd-count">${items.length} 条指令</span></summary>` +
          `<div class="cmd-wake">` +
          `<div class="cmd-wake-item"><label>启用系统</label><label class="switch"><input type="checkbox" data-syson="${esc(sys)}" ${sysChecked}><span class="slider-toggle"></span></label></div>` +
          `<div class="cmd-wake-item" style="flex:1"><label>唤醒词</label><input data-wake="${esc(sys)}" value="${esc(wake)}" placeholder="可用 | 分隔多个"></div>` +
          `</div>` +
          `<div class="cmd-tags">${tags || '<span class="hint">（交互式/无前缀触发）</span>'}</div>` +
          `</details>`;
      })
      .join("");
    const customTags = Object.keys(custSec).map((t) => {
      const cOn = isOn(disSec[t]);
      return `<a class="cmd-tag custom ${cOn ? "" : "off"}" data-on="${cOn ? "1" : "0"}" data-cmd="${esc(t)}" data-sys="自定义">` +
        `${cOn ? '<span style="color:var(--ok);font-size:10px">●</span>' : '<span style="color:var(--muted);font-size:10px">○</span>'} ${esc(t)}</a>`;
    }).join("");
    el.innerHTML =
      blockHtml +
      `<details class="cmd-block" data-sys="自定义"><summary>` +
        `<span class="cmd-sys">自定义指令</span>` +
        `<span class="cmd-count">${Object.keys(custSec).length} 条</span></summary>` +
        `<div class="cmd-tags">${customTags || '<span class="hint">暂无。新建：纯自定义（触发词→回复）或绑定已有引擎指令作别名。</span>'}</div>` +
        `<div class="toolbar" style="margin-top:8px"><button id="btnCmdAddCustom" class="ghost sm">＋ 添加自定义指令</button></div>` +
      `</details>`;
    _CMD_CUST = custSec || {};
    if (_openSys && _openSys.size) {
      el.querySelectorAll("details.cmd-block").forEach((d) => {
        if (_openSys.has(d.dataset.sys)) d.open = true;
      });
    }
    _bindCmdListOnce();
    try { refreshBalanceBadges(); } catch (e) {}
  } catch (e) {
    err("commands: " + e.message);
    try { TAB_DONE.cmds = false; } catch (_e) {}
  }
}
function cmdAliasesFor(cmd) {
  const cust = CMD_CFG["自定义指令配置"] || {};
  return Object.keys(cust).filter((t) => cust[t] && cust[t].command === cmd && t !== cmd);
}

function openCmdEditor() {
  const { sys, cmd, isNew, mapCmd } = CMD_EDIT;
  const m = document.getElementById("cmdModal");
  if (!m) return;
  const curCmd = mapCmd || cmd;
  const ovSec = CMD_CFG["指令回复配置"] || {};
  const disSec = CMD_CFG["指令启用配置"] || {};
  const isOff = (v) => v === "假" || v === "0" || v === "false";
  // 启用键: 自定义指令(含别名)按触发词, 引擎指令按映射引擎指令名
  const effKey = (sys === "自定义") ? (cmd || "") : (mapCmd || cmd || "");
  const onBox = document.getElementById("cmdModalOn");
  if (onBox) onBox.checked = !isOff(disSec[effKey]);
  // 超管权限勾选：指令权限配置=超管（默认所有人）
  const admBox = document.getElementById("cmdModalAdmin");
  if (admBox) admBox.checked = (((CMD_CFG["指令权限配置"] || {})[effKey] || "").trim() === "超管");
  // 删除按钮: 仅编辑已有自定义指令时显示
  const delBtn = document.getElementById("cmdModalDel");
  if (delBtn) delBtn.style.display = (sys === "自定义" && !isNew) ? "" : "none";
  document.getElementById("cmdModalTitle").textContent = isNew ? "添加自定义指令" : ("编辑指令 · " + curCmd);
  (document.getElementById("cmdModalSysBadge") || document.getElementById("cmdModalSys") || {}).textContent = isNew ? "自定义指令" : sys;
  // 触发词: 可编辑(| 分隔多个); 内置指令默认=指令名(+已有别名)
  const nameInp = document.getElementById("cmdModalName");
  nameInp.value = isNew ? "" : [curCmd, ...cmdAliasesFor(curCmd)].join("|");
  nameInp.readOnly = false;
  document.getElementById("cmdModalCmd").value = mapCmd;
  document.getElementById("cmdModalCmd").readOnly = isNew ? false : true;
  document.getElementById("cmdModalReply").value = isNew ? "" : (ovSec[curCmd] ?? "");
  const note = document.getElementById("cmdModalCmdNote");
  if (note) {
    note.textContent = (!isNew && mapCmd === curCmd)
      ? "内置指令：触发词即指令名（可改/加，| 分隔多个）；映射引擎指令=本身。"
      : "留空=纯自定义指令；填入已有引擎指令则这些触发词作为它的别名。";
  }
  const dfltCmd = mapCmd || curCmd || "";
  const dfltTxt = CMD_DEFAULT_REPLY[dfltCmd] || (ovSec[dfltCmd] || "") || "";
  document.getElementById("cmdModalDflt").textContent = isNew
    ? "纯自定义指令：回复内容即返回文案，可直接写你想要的任意内容；也可在「映射引擎指令」填入已有指令来作为它的别名（此时回复覆盖模板对该引擎生效）。"
    : (dfltTxt
        ? "引擎默认回复（参考）：\r\n" + dfltTxt + "\r\n（{变量}=动态数值；留空回复=按引擎原样回复）"
        : "引擎默认回复为运行时动态生成（含变量/随机/状态判定），此处未收录示例；\r\n如需覆盖请直接填写回复模板，或用 {回复} 引用引擎原回复。留空=不覆盖。");
  renderCmdNums(mapCmd ? mapCmd : (isNew ? "" : curCmd), isNew);
  if (m) m.classList.add("show");
}

// 按目标引擎指令渲染玩法数值(纯自定义且未映射时提示)
function renderCmdNums(numCmd, isNew) {
  const holder = document.getElementById("cmdModalNums");
  if (!holder) return;
  if (!numCmd) {
    holder.innerHTML = `<small class="hint">纯自定义指令：回复内容即返回文案，无玩法数值；如需调整某引擎指令的数值，请把「映射引擎指令」填成它。</small>`;
    return;
  }
  let nums = CMD_NUMS[numCmd] || [];
  if (!nums.length && numCmd) {
    // 通用兜底：按指令名与键名/说明的关键词（二字重叠）精准匹配本系统数值，保证对得上、无关的不出现
    try {
      const _cjk = (s) => (String(s || "").match(/[\u4e00-\u9fff]/g) || []);
      const _bigrams = (s) => {
        const cs = _cjk(s), out = {};
        for (let i = 0; i + 1 < cs.length; i++) out[cs[i] + cs[i + 1]] = 1;
        return out;
      };
      const _cb = _bigrams(numCmd);
      const eng = (typeof CMD_ENG !== "undefined" && CMD_ENG[numCmd]) || "";
      const secs = ENG_NUM_SECTIONS[eng] || [];
      const scored = [];
      const seen = {};
      secs.forEach((sec) => {
        const grp = (CFG.schema && CFG.schema.groups && CFG.schema.groups[sec]) || [];
        grp.forEach((it) => {
          if (it.type !== "int" && it.type !== "float") return;
          const k = sec + "__" + it.key;
          if (seen[k]) return;
          seen[k] = 1;
          const _kb = _bigrams(it.key + (it.desc || ""));
          let hit = 0;
          Object.keys(_cb).forEach((b) => { if (_kb[b]) hit++; });
          if (hit > 0) scored.push([hit, sec, it]);
        });
      });
      scored.sort((a, b) => b[0] - a[0]);
      nums = scored.slice(0, 6).map(([s, sec, it]) => [sec, it.key, it.key, it.type]);
    } catch(e){}
  }
  if (!nums.length) {
    holder.innerHTML = `<small class="hint">该指令无关联可调数值。</small>`;
    return;
  }
  holder.innerHTML = nums.map(([sec, key, label]) => {
    const v = (CMD_CFG[sec] || {})[key] ?? "";
    return `<label class="cnum"><span>${esc(label)}</span>` +
      `<input type="number" data-cmd-num data-nsec="${esc(sec)}" data-nkey="${esc(key)}" value="${esc(v)}"></label>`;
  }).join("");
}

function closeCmdEditor() {
  const m = document.getElementById("cmdModal");
  if (m) m.classList.remove("show");
}

// 系统启用开关即时保存：收齐所有块头部状态一次 POST，失败回拨
async function sysonImmediateSave(inp) {
  inp.disabled = true;
  try {
    const onSec = {};
    document.querySelectorAll("#cmdList [data-syson]").forEach((x) => {
      onSec[x.dataset.syson] = x.checked ? "真" : "假";
    });
    const r = await getBridge().apiPost("config/save", { "系统开关配置": onSec });
    if (r && r.ok === false) throw new Error(r.msg || r.error || "保存失败");
    const sys = inp.dataset.syson;
    toast(`系统${sys}已${inp.checked ? "启用" : "关闭"}（即时生效）`, inp.checked ? "ok" : "bad");
    await loadCommands();
  } catch (err) {
    toast("系统开关保存失败: " + err.message, "bad");
    inp.checked = !inp.checked;
  } finally {
    inp.disabled = false;
  }
}

async function saveCmdEditor() {
  const name = document.getElementById("cmdModalName").value.trim();
  const mapCmd = document.getElementById("cmdModalCmd").value.trim();
  const reply = document.getElementById("cmdModalReply").value.trim();
  const msg = document.getElementById("cmdModalMsg");
  if (msg) msg.className = "msg";
  try {
    const payload = {};
    // 系统启用开关: 收所有块头部
    const onSec = {};
    document.querySelectorAll("#cmdList [data-syson]").forEach((inp) => {
      onSec[inp.dataset.syson] = inp.checked ? "真" : "假";
    });
    if (Object.keys(onSec).length) payload["系统开关配置"] = onSec;
    // 系统唤醒词: 收所有块头部
    const wakeSec = {};
    document.querySelectorAll("#cmdList [data-wake]").forEach((inp) => {
      wakeSec[inp.dataset.wake] = inp.value.trim();
    });
    if (Object.keys(wakeSec).length) payload["唤醒词配置"] = wakeSec;

    const cust = {};
    // 改名旧词：后文 null 块靠“payload 缺键”删键，两处保留循环须先剔旧词，否则改名变复制
    const _oldName = (typeof CMD_EDIT !== "undefined" && CMD_EDIT && !CMD_EDIT.isNew) ? String(CMD_EDIT.cmd || "").trim() : "";
    const _renaming = !!(_oldName && _oldName !== name);
    if (mapCmd) {
      if (!KNOWN_CMDS.has(mapCmd)) {
        if (msg) { msg.textContent = `映射的引擎指令「${mapCmd}」不存在，请留空走纯自定义或填已有指令`; msg.classList.add("bad"); }
        toast(`引擎指令「${mapCmd}」不存在，已拦截`, "bad");
        return;
      }
      // 映射 / 编辑已有引擎指令(含别名): 触发词=| 分隔, 全部当作该指令的触发词
      const trigs = name.split(/[|，,]/).map((s) => s.trim()).filter(Boolean);
      if (!trigs.length) { if (msg) { msg.textContent = "请填写触发词"; msg.classList.add("bad"); } return; }
      { const ov = {}; ov[mapCmd] = reply; payload["指令回复配置"] = ov; }
      const oldCust = (CMD_CFG["自定义指令配置"] || {});
      Object.keys(oldCust).forEach((t) => {
        const e = oldCust[t];
        if (_renaming && t === _oldName) return;
        if (!(e && e.command === mapCmd && t !== mapCmd)) cust[t] = e;
      });
      trigs.forEach((t) => {
        if (t && t !== mapCmd) cust[t] = { command: mapCmd, reply: "" };
      });
    } else {
      // 纯自定义指令
      if (!name) { if (msg) { msg.textContent = "请填写触发词"; msg.classList.add("bad"); } return; }
      if (!reply) { if (msg) { msg.textContent = "纯自定义指令需填写回复内容"; msg.classList.add("bad"); } return; }
      const oldCust = (CMD_CFG["自定义指令配置"] || {});
      Object.keys(oldCust).forEach((t) => { if (t !== name && !(_renaming && t === _oldName)) cust[t] = oldCust[t]; });
      cust[name] = { command: "", reply: reply };
    }
    if (Object.keys(cust).length) payload["自定义指令配置"] = cust;

    // 指令级启用: 自定义指令按触发词记录, 引擎指令按映射引擎指令名记录
    const isCustom = (CMD_EDIT.sys === "自定义") || (name && !mapCmd && CMD_EDIT.isNew);
    const effKey = isCustom ? name : (mapCmd || name);
    const disSec = {};
    const onBox = document.getElementById("cmdModalOn");
    disSec[effKey] = (onBox && onBox.checked) ? "真" : "假";
    payload["指令启用配置"] = disSec;

    // 超管权限：勾选=超管（非超管静默），不勾选=所有人
    const admBox = document.getElementById("cmdModalAdmin");
    const permSec = {};
    permSec[effKey] = (admBox && admBox.checked) ? "超管" : "所有人";
    payload["指令权限配置"] = permSec;

    // 玩法数值(目标引擎指令)
    document.querySelectorAll("#cmdModal [data-cmd-num]").forEach((inp) => {
      const sec = inp.dataset.nsec, key = inp.dataset.nkey;
      if (!payload[sec]) payload[sec] = {};
      payload[sec][key] = inp.value === "" ? "" : Number(inp.value);
    });

    // 改名清旧键：纯自定义改触发词时旧词在四节中残留即幽灵（显式 null 删键）
    try {
      const _old = (CMD_EDIT && !CMD_EDIT.isNew) ? String(CMD_EDIT.cmd || "").trim() : "";
      if (_old && _old !== name) {
        ["自定义指令配置", "指令启用配置", "指令回复配置", "指令权限配置"].forEach((sec) => {
          const _has = (CMD_CFG[sec] || {}).hasOwnProperty(_old);
          if (_has) {
            if (!payload[sec] || typeof payload[sec] !== "object") payload[sec] = {};
            if (payload[sec][_old] === undefined) payload[sec][_old] = null;
          }
        });
      }
    } catch (e) {}
    const r = await getBridge().apiPost("config/save", payload);
    if (r && r.error) throw new Error(r.error);
    if (msg) { msg.textContent = "指令已保存"; msg.classList.add("ok"); }
    toast("指令已保存", "ok");
    closeCmdEditor();
    await loadCommands();
  } catch (e) {
    if (msg) { msg.textContent = "保存失败: " + e.message; msg.classList.add("bad"); }
    toast("保存失败: " + e.message, "bad");
  }
}

// 删除自定义指令(移除 自定义指令配置 / 指令启用配置 / 指令回复配置 中对应项)
async function deleteCmdEditor() {
  const msg = document.getElementById("cmdModalMsg");
  if (msg) msg.className = "msg";
  try {
    const key = (CMD_EDIT && CMD_EDIT.cmd) || "";
    if (!key) { if (msg) { msg.textContent = "无触发词，无法删除"; msg.classList.add("bad"); } return; }
    const oldCust = (CMD_CFG["自定义指令配置"] || {});
    if (!(key in oldCust)) { if (msg) { msg.textContent = "该指令在配置中不存在，可能已删除"; msg.classList.add("bad"); } return; }
    if (!(await uiConfirm("确认删除自定义指令「" + key + "」？", "删除自定义指令"))) return;
    const cust = {};
    Object.keys(oldCust).forEach((t) => { if (t !== key) cust[t] = oldCust[t]; });
    const payload = { "自定义指令配置": cust };
    payload["自定义指令配置"][key] = null; // 显式删键（后端 merge 语义下缺键≠删除）
    const disSec = {};
    const disSecOld = (CMD_CFG["指令启用配置"] || {});
    Object.keys(disSecOld).forEach((k) => { if (k !== key) disSec[k] = disSecOld[k]; });
    if (Object.keys(disSec).length) payload["指令启用配置"] = disSec;
    payload["指令启用配置"] = payload["指令启用配置"] || {};
    payload["指令启用配置"][key] = null;
    const ovOld = (CMD_CFG["指令回复配置"] || {});
    const ov = {};
    Object.keys(ovOld).forEach((k) => { if (k !== key) ov[k] = ovOld[k]; });
    payload["指令回复配置"] = ov;
    payload["指令回复配置"][key] = null;
    const permOld = (CMD_CFG["指令权限配置"] || {});
    if (permOld[key] !== undefined) payload["指令权限配置"] = { [key]: null };
    await getBridge().apiPost("config/save", payload).then((r) => {
      if (r && r.error) throw new Error(r.error);
    });
    toast("已删除自定义指令", "ok");
    closeCmdEditor();
    await loadCommands();
  } catch (e) {
    if (msg) { msg.textContent = "删除失败: " + e.message; msg.classList.add("bad"); }
    toast("删除失败: " + e.message, "bad");
  }
}

