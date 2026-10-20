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
  const iconEl = document.getElementById("appModalIcon");
  const inputWrap = document.getElementById("appModalInputWrap");
  const okBtn = document.getElementById("appModalOk");
  const cancelBtn = document.getElementById("appModalCancel");
  const closeBtn = document.getElementById("appModalClose");

  if (iconEl) iconEl.textContent = "✏️";
  if (inputWrap) inputWrap.style.display = "none";
  if (titleEl) titleEl.textContent = isNew ? "添加新题目" : `编辑题目 #${idx + 1}`;
  if (contentEl) {
    contentEl.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:12px;padding:4px 0">
        <div>
          <label style="font-size:12.5px;font-weight:600;color:var(--text);display:block;margin-bottom:4px">题目内容 / 谜面 / 问题：</label>
          <textarea id="popQText" rows="3" style="width:100%;font-size:13.5px;padding:8px 10px;border-radius:10px" placeholder="输入题目内容…">${esc(curItem.q || "")}</textarea>
        </div>
        <div>
          <label style="font-size:12.5px;font-weight:600;color:var(--text);display:block;margin-bottom:4px">标准答案 / 多个备选答案：</label>
          <input id="popQAns" type="text" style="width:100%;font-size:13.5px;padding:8px 10px;border-radius:10px" placeholder="如：番茄 / 西红柿（支持用 / 或 | 填入多个答案）" value="${esc(curItem.a || "")}">
        </div>
        <div class="hint" style="font-size:11.5px;line-height:1.5">
          💡 <b>多答案支持</b>：支持使用 <code>/</code> 或 <code>|</code> 录入多个备选答案（例如：<code>自行车 / 单车</code>、<code>李白 | 青莲居士</code>），玩家答中任意一个均判定正确！<br>
          修改确认后将更新到编辑列表，需点击右上角「保存当前题库」落盘生效。
        </div>
      </div>
    `;
  }

  const closeModal = () => {
    modal.classList.remove("show", "open");
    if (inputWrap) inputWrap.style.display = "none";
    if (okBtn) okBtn.onclick = null;
    if (cancelBtn) cancelBtn.onclick = null;
    if (closeBtn) closeBtn.onclick = null;
    modal.onclick = null;
  };

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
    closeModal();
    renderQuestions();
  };

  if (okBtn) {
    okBtn.textContent = isNew ? "确认添加" : "保存修改";
    okBtn.style.background = "var(--acc)";
    okBtn.style.borderColor = "transparent";
    okBtn.onclick = saveHandler;
  }
  if (cancelBtn) {
    cancelBtn.textContent = "取消";
    cancelBtn.onclick = closeModal;
  }
  if (closeBtn) {
    closeBtn.onclick = closeModal;
  }
  modal.onclick = (e) => {
    if (e.target === modal) closeModal();
  };

  modal.classList.add("show", "open");
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

async function exportQuestions() {
  const bankNames = { trick: "急转弯", miri: "猜字谜", quiz: "知识问答", chain: "成语接龙" };
  const curName = bankNames[_Q_BANK] || "当前题库";
  const curCount = (_Q_DATA[_Q_BANK] || []).length;
  const modal = document.getElementById("appModal");
  if (!modal) return;

  const titleEl = document.getElementById("appModalTitle");
  const contentEl = document.getElementById("appModalContent");
  const iconEl = document.getElementById("appModalIcon");
  const inputWrap = document.getElementById("appModalInputWrap");
  const okBtn = document.getElementById("appModalOk");
  const cancelBtn = document.getElementById("appModalCancel");
  const closeBtn = document.getElementById("appModalClose");

  if (iconEl) iconEl.textContent = "📤";
  if (inputWrap) inputWrap.style.display = "none";
  if (titleEl) titleEl.textContent = "导出题库";
  if (contentEl) {
    contentEl.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:12px;padding:4px 0">
        <div style="font-size:13px;color:var(--text-muted);line-height:1.6">
          题库支持完整自由导出。你可以选择打包导出四大题库（便于跨机器人/备份全量迁移），或仅导出当前正在查看的分类。
        </div>
        <div style="display:grid;grid-template-columns:1fr;gap:10px">
          <button type="button" id="btnExportAllPack" class="m3-btn m3-btn-tonal" style="padding:12px 14px;text-align:left;display:flex;align-items:flex-start;gap:12px;border-radius:12px;cursor:pointer">
            <span style="font-size:24px;line-height:1">📦</span>
            <div style="flex:1">
              <div style="font-weight:700;font-size:13.5px;color:var(--text);margin-bottom:3px">打包导出全部四大题库 (JSON)</div>
              <div style="font-size:12px;color:var(--text-muted);line-height:1.4">一次性导出【急转弯、猜字谜、知识问答、成语接龙】全部题库数据，完整备份，随时可一键导入恢复</div>
            </div>
          </button>
          <button type="button" id="btnExportCurrentBank" class="m3-btn m3-btn-tonal" style="padding:12px 14px;text-align:left;display:flex;align-items:flex-start;gap:12px;border-radius:12px;cursor:pointer">
            <span style="font-size:24px;line-height:1">📄</span>
            <div style="flex:1">
              <div style="font-weight:700;font-size:13.5px;color:var(--text);margin-bottom:3px">仅导出当前【${esc(curName)}】题库 (JSON)</div>
              <div style="font-size:12px;color:var(--text-muted);line-height:1.4">当前共 ${curCount} 条题目，格式清晰规范，支持自行在文本编辑器中修改编辑后重新导入</div>
            </div>
          </button>
        </div>
        <div class="hint" style="font-size:11.5px;color:var(--text-muted);line-height:1.5">
          💡 导出的 JSON 题库文件符合通用标准规范，包含分类元数据与词条列表，可在任意实例的 WebUI 中直接导入。
        </div>
      </div>
    `;
  }

  const closeModal = () => {
    modal.classList.remove("show", "open");
    if (inputWrap) inputWrap.style.display = "none";
    if (okBtn) {
      okBtn.style.display = "";
      okBtn.onclick = null;
    }
    if (cancelBtn) cancelBtn.onclick = null;
    if (closeBtn) closeBtn.onclick = null;
    modal.onclick = null;
  };

  const padZero = (n) => String(n).padStart(2, "0");
  const getTs = () => {
    const d = new Date();
    return `${d.getFullYear()}${padZero(d.getMonth() + 1)}${padZero(d.getDate())}_${padZero(d.getHours())}${padZero(d.getMinutes())}`;
  };

  document.getElementById("btnExportAllPack")?.addEventListener("click", async () => {
    const btn = document.getElementById("btnExportAllPack");
    if (btn) btn.disabled = true;
    try {
      toast("正在生成全量题库包...", "info", 2000);
      const res = await getBridge().apiGet("questions/export");
      if (res && res.ok) {
        downloadJson(res, `xbbot_questions_all_${getTs()}.json`);
        closeModal();
      } else {
        toast("导出失败: " + ((res && res.error) || "未知错误"), "bad", 5000);
      }
    } catch (e) {
      toast("导出异常: " + e.message, "bad", 5000);
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  document.getElementById("btnExportCurrentBank")?.addEventListener("click", async () => {
    const btn = document.getElementById("btnExportCurrentBank");
    if (btn) btn.disabled = true;
    try {
      toast(`正在导出【${curName}】题库...`, "info", 2000);
      const res = await getBridge().apiGet("questions/export", { bank: _Q_BANK });
      if (res && res.ok) {
        downloadJson(res, `xbbot_${_Q_BANK}_${getTs()}.json`);
        closeModal();
      } else {
        toast("导出失败: " + ((res && res.error) || "未知错误"), "bad", 5000);
      }
    } catch (e) {
      toast("导出异常: " + e.message, "bad", 5000);
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  if (okBtn) okBtn.style.display = "none";
  if (cancelBtn) {
    cancelBtn.style.display = "";
    cancelBtn.textContent = "关闭";
    cancelBtn.onclick = closeModal;
  }
  if (closeBtn) closeBtn.onclick = closeModal;
  modal.onclick = (e) => {
    if (e.target === modal) closeModal();
  };

  modal.classList.add("show", "open");
}

async function importQuestions() {
  const bankNames = { trick: "急转弯", miri: "猜字谜", quiz: "知识问答", chain: "成语接龙" };
  const modal = document.getElementById("appModal");
  if (!modal) return;

  const titleEl = document.getElementById("appModalTitle");
  const contentEl = document.getElementById("appModalContent");
  const iconEl = document.getElementById("appModalIcon");
  const inputWrap = document.getElementById("appModalInputWrap");
  const okBtn = document.getElementById("appModalOk");
  const cancelBtn = document.getElementById("appModalCancel");
  const closeBtn = document.getElementById("appModalClose");

  if (iconEl) iconEl.textContent = "📥";
  if (inputWrap) inputWrap.style.display = "none";
  if (titleEl) titleEl.textContent = "导入题库";
  if (contentEl) {
    contentEl.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:12px;padding:4px 0">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <label class="m3-btn m3-btn-tonal" style="cursor:pointer;padding:7px 14px;font-size:12.5px;display:inline-flex;align-items:center;gap:6px">
            📁 选择本地文件 (.json / .txt / .csv)
            <input type="file" id="popQImportFile" accept=".json,.txt,.csv" style="display:none">
          </label>
          <span id="popQImportFileTip" style="font-size:12px;color:var(--text-muted);word-break:break-all">未选择文件（也可以直接在下方粘贴文本）</span>
        </div>

        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
            <label style="font-size:12.5px;font-weight:600;color:var(--text)">题库内容 / 粘贴文本：</label>
            <button type="button" id="btnPopQClearText" class="m3-btn" style="padding:2px 8px;font-size:11.5px">清空输入</button>
          </div>
          <textarea id="popQImportContent" rows="7" style="width:100%;font-size:12px;font-family:monospace;padding:8px 10px;border-radius:10px;line-height:1.4" placeholder="在此粘贴 JSON 或纯文本内容：&#10;• 全量打包包 JSON：{ &quot;kind&quot;: &quot;questions_all&quot;, &quot;banks&quot;: {...} }&#10;• 单库 JSON 数组：[{ &quot;q&quot;: &quot;题目&quot;, &quot;a&quot;: &quot;答案&quot; }, ...] 或 [&quot;成语1&quot;, &quot;成语2&quot;]&#10;• TXT 纯文本（每行一条）：&#10;  - 问答类格式：题目 ---- 答案  或  谜面 | 谜底  或  问题 : 答案&#10;  - 成语接龙格式：每行一个成语"></textarea>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div>
            <label style="font-size:12px;font-weight:600;color:var(--text);display:block;margin-bottom:4px">目标题库分类：</label>
            <select id="popQImportBank" style="width:100%;font-size:12.5px;padding:6px 8px;border-radius:8px">
              <option value="auto">⚡ 智能识别（全量包自动多库全量导入）</option>
              <option value="trick" ${_Q_BANK === "trick" ? "selected" : ""}>急转弯 (trick)</option>
              <option value="miri" ${_Q_BANK === "miri" ? "selected" : ""}>猜字谜 (miri)</option>
              <option value="quiz" ${_Q_BANK === "quiz" ? "selected" : ""}>知识问答 (quiz)</option>
              <option value="chain" ${_Q_BANK === "chain" ? "selected" : ""}>成语接龙 (chain)</option>
            </select>
          </div>
          <div>
            <label style="font-size:12px;font-weight:600;color:var(--text);display:block;margin-bottom:4px">导入策略：</label>
            <select id="popQImportMode" style="width:100%;font-size:12.5px;padding:6px 8px;border-radius:8px">
              <option value="append" selected>➕ 追加合并（去重保留已有，推荐）</option>
              <option value="replace">⚠️ 覆盖现有（清空原有数据再导入）</option>
            </select>
          </div>
        </div>

        <div class="hint" style="font-size:11.5px;line-height:1.5;color:var(--text-muted)">
          💡 <b>格式与生效说明</b>：<br>
          - 纯文本导入问答类题库时，支持以 <code>----</code>、<code>|</code>、<code>\t</code>、<code>——</code> 或 <code>:</code> 作为问题与答案的分隔符；多答案可用 <code>/</code> 隔开。<br>
          - 导入完成后将自动安全落盘并刷新娱乐系统运行时缓存，即时生效，无需重启机器人。
        </div>
      </div>
    `;
  }

  const closeModal = () => {
    modal.classList.remove("show", "open");
    if (inputWrap) inputWrap.style.display = "none";
    if (okBtn) {
      okBtn.style.display = "";
      okBtn.onclick = null;
    }
    if (cancelBtn) cancelBtn.onclick = null;
    if (closeBtn) closeBtn.onclick = null;
    modal.onclick = null;
  };

  const fileInput = document.getElementById("popQImportFile");
  const fileTip = document.getElementById("popQImportFileTip");
  const contentArea = document.getElementById("popQImportContent");
  const bankSelect = document.getElementById("popQImportBank");
  const modeSelect = document.getElementById("popQImportMode");
  const clearBtn = document.getElementById("btnPopQClearText");

  clearBtn?.addEventListener("click", () => {
    if (contentArea) contentArea.value = "";
    if (fileInput) fileInput.value = "";
    if (fileTip) fileTip.textContent = "未选择文件（也可以直接在下方粘贴文本）";
  });

  fileInput?.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) return;
    if (fileTip) fileTip.textContent = `已载入: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    const reader = new FileReader();
    reader.onload = (e) => {
      const rawText = String(e.target.result || "").replace(/^\uFEFF/, "");
      if (contentArea) contentArea.value = rawText;
      try {
        const parsed = JSON.parse(rawText);
        if (parsed && (parsed.kind === "questions_all" || parsed.banks)) {
          if (bankSelect) bankSelect.value = "auto";
          toast("已识别为四大题库全量包文件", "ok", 3000);
        } else if (parsed && parsed.bank && bankSelect && bankSelect.querySelector(`option[value="${parsed.bank}"]`)) {
          bankSelect.value = parsed.bank;
          toast(`已识别为【${bankNames[parsed.bank] || parsed.bank}】题库文件`, "ok", 3000);
        }
      } catch (_) {}
    };
    reader.onerror = () => toast("读取文件失败", "bad");
    reader.readAsText(file, "utf-8");
  });

  const submitImport = async () => {
    const rawContent = (contentArea?.value || "").trim();
    if (!rawContent) {
      toast("请先选择题库文件或粘贴题库内容", "bad");
      return;
    }

    const selBank = bankSelect?.value || "auto";
    const selMode = modeSelect?.value || "append";

    let payload = { mode: selMode };
    let isFullPack = false;

    try {
      const parsed = JSON.parse(rawContent);
      if (parsed && (parsed.kind === "questions_all" || (parsed.banks && typeof parsed.banks === "object"))) {
        payload.banks = parsed.banks;
        isFullPack = true;
      } else if (parsed && parsed.bank && Array.isArray(parsed.items)) {
        payload.bank = selBank === "auto" ? parsed.bank : selBank;
        payload.items = parsed.items;
      } else if (Array.isArray(parsed)) {
        payload.bank = selBank === "auto" ? _Q_BANK : selBank;
        payload.items = parsed;
      } else {
        payload.bank = selBank === "auto" ? _Q_BANK : selBank;
        payload.text = rawContent;
      }
    } catch (_) {
      // 纯文本导入
      payload.bank = selBank === "auto" ? _Q_BANK : selBank;
      payload.text = rawContent;
    }

    if (selMode === "replace") {
      const targetDesc = isFullPack ? "全量四大题库" : `【${bankNames[payload.bank] || payload.bank}】题库`;
      if (!(await uiConfirm(`当前选择【覆盖现有】，系统将清空目标 ${targetDesc} 的原有全部数据并写入导入数据，确认覆盖吗？`, "确认覆盖导入"))) {
        return;
      }
    }

    if (okBtn) {
      okBtn.disabled = true;
      okBtn.textContent = "正在导入...";
    }

    try {
      const res = await getBridge().apiPost("questions/import", payload);
      if (res && res.ok) {
        toast(res.msg || "题库导入成功！", "ok", 5000);
        closeModal();
        await loadQuestions();
      } else {
        toast("导入失败: " + ((res && res.error) || "未知错误"), "bad", 6000);
      }
    } catch (e) {
      toast("导入异常: " + e.message, "bad", 6000);
    } finally {
      if (okBtn) {
        okBtn.disabled = false;
        okBtn.textContent = "确认导入";
      }
    }
  };

  if (okBtn) {
    okBtn.style.display = "";
    okBtn.textContent = "确认导入";
    okBtn.style.background = "var(--acc)";
    okBtn.style.borderColor = "transparent";
    okBtn.onclick = submitImport;
  }
  if (cancelBtn) {
    cancelBtn.style.display = "";
    cancelBtn.textContent = "取消";
    cancelBtn.onclick = closeModal;
  }
  if (closeBtn) closeBtn.onclick = closeModal;
  modal.onclick = (e) => {
    if (e.target === modal) closeModal();
  };

  modal.classList.add("show", "open");
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

  // 导出题库（支持导出当前分类或全量四大题库打包）
  document.getElementById("btnQExport")?.addEventListener("click", () => {
    exportQuestions();
  });

  // 导入题库（支持 JSON、TXT、CSV，支持覆盖与追加去重）
  document.getElementById("btnQImport")?.addEventListener("click", () => {
    importQuestions();
  });

  // 恢复默认题库（从只读种子文件重置当前分类或全部）
  document.getElementById("btnQRestoreDefault")?.addEventListener("click", async () => {
    const bankNames = { trick: "急转弯", miri: "猜字谜", quiz: "知识问答", chain: "成语接龙" };
    const curName = bankNames[_Q_BANK] || "当前题库";
    const tip = `确认将【${curName}】恢复为系统内置默认题库吗？\n恢复后将自动写入系统内置的丰富种子题库并即时生效（当前分类的未保存修改或自定义题目将被覆盖）。`;
    if (!(await uiConfirm(tip, `恢复${curName}默认题库`))) return;

    const btn = document.getElementById("btnQRestoreDefault");
    if (btn && btn.disabled) return;
    const origTxt = btn ? btn.textContent : "↩️ 恢复默认题库";
    if (btn) { btn.disabled = true; btn.textContent = "正在恢复..."; }
    try {
      const res = await getBridge().apiPost("questions/reset", { bank: _Q_BANK });
      if (res && res.ok) {
        toast(res.msg || `已恢复【${curName}】为系统默认题库！`, "ok", 4000);
        await loadQuestions();
      } else {
        toast("恢复失败: " + ((res && res.error) || "未知错误"), "bad", 5000);
      }
    } catch (e) {
      toast("恢复异常: " + e.message, "bad", 5000);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = origTxt; }
    }
  });

  // 保存当前题库
  document.getElementById("btnQSave")?.addEventListener("click", () => {
    saveCurrentQuestions();
  });

  // 清空当前词库
  document.getElementById("btnQClear")?.addEventListener("click", async () => {
    const bankNames = { trick: "急转弯", miri: "猜字谜", quiz: "知识问答", chain: "成语接龙" };
    const curName = bankNames[_Q_BANK] || "当前题库";
    const curCount = (_Q_DATA[_Q_BANK] || []).length;
    if (curCount === 0) {
      toast(`【${curName}】当前已是空白词库，无需清空`, "info");
      return;
    }
    const tip = `确定要清空【${curName}】的全部 ${curCount} 条词库数据吗？\n清空后你可以自由添加自己的专属词条或保持空白，需点击「保存当前题库」落盘生效。`;
    if (!(await uiConfirm(tip, `清空${curName}词库`))) return;
    _Q_DATA[_Q_BANK] = [];
    renderQuestions();
    toast(`已清空【${curName}】全部词条，请点击「保存当前题库」落盘生效`, "ok", 4500);
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
