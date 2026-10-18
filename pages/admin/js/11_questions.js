// ---------- 题库设置（急转弯、猜字谜、答题、成语接龙 在线管理与增删改） ----------
let _Q_BANK = "trick";
let _Q_DATA = { trick: [], miri: [], quiz: [], chain: [] };
let _Q_FILTER = "";

async function loadQuestions() {
  try {
    const res = await getBridge().apiGet("questions/list");
    if (res && res.ok && res.banks) {
      Object.keys(res.banks).forEach((k) => {
        _Q_DATA[k] = res.banks[k].items || [];
        const cntEl = document.getElementById(`qCount-${k}`);
        if (cntEl) cntEl.textContent = _Q_DATA[k].length;
      });
      renderQuestions();
    } else {
      err("读取题库失败: " + ((res && res.error) || "数据为空"));
    }
  } catch (e) {
    err("loadQuestions: " + e.message);
  }
}

function renderQuestions() {
  const box = document.getElementById("qListBox");
  if (!box) return;

  const items = _Q_DATA[_Q_BANK] || [];
  const q = (_Q_FILTER || "").trim().toLowerCase();
  const isChain = _Q_BANK === "chain";

  let filtered = [];
  if (isChain) {
    filtered = items.map((word, idx) => ({ word, origIdx: idx }))
      .filter((x) => !q || String(x.word).toLowerCase().includes(q));
  } else {
    filtered = items.map((item, idx) => ({ item, origIdx: idx }))
      .filter((x) => {
        if (!q) return true;
        const qText = String(x.item.q || "").toLowerCase();
        const aText = String(x.item.a || "").toLowerCase();
        return qText.includes(q) || aText.includes(q);
      });
  }

  // 更新当前标签数量显示
  const cntEl = document.getElementById(`qCount-${_Q_BANK}`);
  if (cntEl) cntEl.textContent = items.length;

  if (!items.length) {
    box.innerHTML = `<div class="hint" style="padding:28px 16px;text-align:center;background:var(--panel);border:1px solid var(--line);border-radius:12px">暂无题库数据，点击右上角「＋ 添加词条」新增。</div>`;
    return;
  }

  if (isChain) {
    let chipsHtml = filtered.map((x) => `
      <div class="q-chain-chip" style="display:inline-flex;align-items:center;gap:6px;padding:6px 12px;background:var(--panel);border:1px solid var(--line);border-radius:10px;font-size:13px;font-weight:600">
        <span>${esc(x.word)}</span>
        <button type="button" class="icon-action-btn" data-q-edit="${x.origIdx}" title="修改成语" style="width:20px;height:20px;font-size:12px">✎</button>
        <button type="button" class="icon-action-btn del" data-q-del="${x.origIdx}" title="删除" style="width:20px;height:20px;font-size:12px">✕</button>
      </div>
    `).join("");

    box.innerHTML = `
      <div style="font-size:12.5px;color:var(--muted);margin-bottom:8px">当前显示 ${filtered.length} / 共 ${items.length} 条成语（支持搜索过滤与自由增删）</div>
      <div style="display:flex;flex-wrap:wrap;gap:8px">${chipsHtml || '<div class="hint">无匹配成语</div>'}</div>
    `;
  } else {
    let rowsHtml = filtered.map((x, i) => `
      <div class="q-item-row" style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;background:var(--panel);border:1px solid var(--line);border-radius:12px;margin-bottom:8px;flex-wrap:wrap">
        <div style="display:flex;align-items:flex-start;gap:10px;flex:1;min-width:260px">
          <span style="font-size:12px;font-weight:700;color:var(--muted);padding:2px 6px;background:var(--m3-sys-color-surface-container);border-radius:6px;margin-top:2px">#${x.origIdx + 1}</span>
          <div style="flex:1">
            <div style="font-weight:600;font-size:13.5px;color:var(--text);line-height:1.45">${esc(x.item.q || "")}</div>
            <div style="font-size:12.5px;color:var(--acc);margin-top:4px;display:flex;align-items:center;gap:4px">
              <span style="font-weight:700;font-size:11px;padding:1px 5px;background:rgba(var(--accSoftRgb, 74,144,217),0.15);border-radius:4px">答案</span>
              <span>${esc(x.item.a || "")}</span>
            </div>
          </div>
        </div>
        <div style="display:flex;gap:6px;align-items:center">
          <button type="button" class="ghost sm" data-q-edit="${x.origIdx}">✎ 编辑</button>
          <button type="button" class="ghost sm del" data-q-del="${x.origIdx}">🗑️ 删除</button>
        </div>
      </div>
    `).join("");

    box.innerHTML = `
      <div style="font-size:12.5px;color:var(--muted);margin-bottom:8px">当前显示 ${filtered.length} / 共 ${items.length} 道题目</div>
      <div>${rowsHtml || '<div class="hint" style="padding:16px;text-align:center">无匹配题目</div>'}</div>
    `;
  }

  // 绑定编辑事件
  box.querySelectorAll("[data-q-edit]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.dataset.qEdit);
      openQuestionEditor(idx);
    });
  });

  // 绑定删除事件
  box.querySelectorAll("[data-q-del]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const idx = Number(btn.dataset.qDel);
      const isChain = _Q_BANK === "chain";
      const targetTxt = isChain ? _Q_DATA[_Q_BANK][idx] : (_Q_DATA[_Q_BANK][idx] ? _Q_DATA[_Q_BANK][idx].q : "");
      if (!(await uiConfirm(`确认删除词条【${targetTxt}】？\n删除后需点击「保存当前题库」生效。`, "删除题库词条"))) return;
      _Q_DATA[_Q_BANK].splice(idx, 1);
      toast("已从当前题库移除该词条，请点击保存", "ok");
      renderQuestions();
    });
  });
}

async function openQuestionEditor(idx = -1) {
  const isNew = idx < 0;
  const isChain = _Q_BANK === "chain";

  if (isChain) {
    const curVal = isNew ? "" : (_Q_DATA[_Q_BANK][idx] || "");
    const res = await uiPrompt("请输入四字成语：", curVal, isNew ? "添加接龙成语" : "编辑成语");
    if (!res || !res.trim()) return;
    const cleanWord = res.trim();
    if (isNew) {
      _Q_DATA[_Q_BANK].push(cleanWord);
      toast(`已添加成语「${cleanWord}」，请点击保存生效`, "ok");
    } else {
      _Q_DATA[_Q_BANK][idx] = cleanWord;
      toast(`已修改成语为「${cleanWord}」，请点击保存生效`, "ok");
    }
    renderQuestions();
    return;
  }

  // QA 模式弹窗
  const curItem = isNew ? { q: "", a: "" } : (_Q_DATA[_Q_BANK][idx] || { q: "", a: "" });
  const modal = document.getElementById("appModal");
  if (!modal) return;

  const titleEl = document.getElementById("appModalTitle");
  const contentEl = document.getElementById("appModalContent");
  const actBtn = document.getElementById("appModalAction");

  if (titleEl) titleEl.textContent = isNew ? "添加新题目" : `编辑题目 #${idx + 1}`;
  if (contentEl) {
    contentEl.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:12px;padding:4px 0">
        <div>
          <label style="font-size:12.5px;font-weight:600;color:var(--text);display:block;margin-bottom:4px">题目内容 / 谜面 / 问题：</label>
          <textarea id="popQText" rows="3" style="width:100%;font-size:13.5px;padding:8px 10px;border-radius:10px" placeholder="输入题目内容…">${esc(curItem.q || "")}</textarea>
        </div>
        <div>
          <label style="font-size:12.5px;font-weight:600;color:var(--text);display:block;margin-bottom:4px">标准答案 / 谜底：</label>
          <input id="popQAns" type="text" style="width:100%;font-size:13.5px;padding:8px 10px;border-radius:10px" placeholder="输入参考答案…" value="${esc(curItem.a || "")}">
        </div>
        <div class="hint" style="font-size:11.5px">修改确认后将更新到编辑列表，需点击「保存当前题库」持久化落盘。</div>
      </div>
    `;
  }

  modal.classList.add("show");
  modal.classList.add("open");

  const saveHandler = () => {
    const qText = (document.getElementById("popQText")?.value || "").trim();
    const aText = (document.getElementById("popQAns")?.value || "").trim();
    if (!qText) {
      toast("题目内容不能为空", "bad");
      return;
    }
    if (!aText) {
      toast("题目答案不能为空", "bad");
      return;
    }
    if (isNew) {
      _Q_DATA[_Q_BANK].unshift({ q: qText, a: aText });
      toast("已添加新题目，请点击右上角「保存当前题库」生效", "ok");
    } else {
      _Q_DATA[_Q_BANK][idx] = { q: qText, a: aText };
      toast("已更新题目内容，请点击右上角「保存当前题库」生效", "ok");
    }
    modal.classList.remove("show", "open");
    renderQuestions();
    if (actBtn) actBtn.removeEventListener("click", saveHandler);
  };

  if (actBtn) {
    actBtn.textContent = isNew ? "确认添加" : "保存修改";
    actBtn.onclick = saveHandler;
  }
}

async function saveCurrentQuestions() {
  const btn = document.getElementById("btnQSave");
  if (btn && btn.disabled) return;
  const origTxt = btn ? btn.textContent : "保存当前题库";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "正在保存...";
  }

  try {
    const items = _Q_DATA[_Q_BANK] || [];
    const res = await getBridge().apiPost("questions/save", {
      bank: _Q_BANK,
      items: items
    });
    if (res && res.ok) {
      toast(res.msg || "题库保存成功！已即时生效", "ok", 4000);
      await loadQuestions();
    } else {
      toast("保存失败: " + ((res && res.error) || "未知错误"), "bad", 6000);
    }
  } catch (e) {
    toast("保存异常: " + e.message, "bad", 6000);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origTxt;
    }
  }
}

function initQuestionsView() {
  // 切换题库类型
  document.querySelectorAll("#qBankTabs button[data-bank]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#qBankTabs button[data-bank]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      _Q_BANK = btn.dataset.bank;
      renderQuestions();
    });
  });

  // 搜索题库
  const searchInput = document.getElementById("qSearch");
  if (searchInput) {
    let t = null;
    searchInput.addEventListener("input", () => {
      if (t) clearTimeout(t);
      t = setTimeout(() => {
        _Q_FILTER = searchInput.value || "";
        renderQuestions();
      }, 200);
    });
  }

  // 添加词条
  document.getElementById("btnQAdd")?.addEventListener("click", () => {
    openQuestionEditor(-1);
  });

  // 刷新题库
  document.getElementById("btnQRefresh")?.addEventListener("click", () => {
    toast("正在刷新题库...", "ok", 2000);
    loadQuestions();
  });

  // 保存当前题库
  document.getElementById("btnQSave")?.addEventListener("click", () => {
    saveCurrentQuestions();
  });

  // 恢复重载题库
  document.getElementById("btnQReset")?.addEventListener("click", async () => {
    if (!(await uiConfirm(`确认放弃当前未保存的修改，重新从文件加载当前题库吗？`, "重载题库"))) return;
    await loadQuestions();
    toast("已重新加载题库", "ok");
  });
}

// 页面加载就绪时绑定事件
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initQuestionsView);
} else {
  initQuestionsView();
}
