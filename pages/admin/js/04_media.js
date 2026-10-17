// ---------- 图片库（根目录） ----------
let IMG_DIR = "";
let IMG_CACHE = [];   // 当前目录的 dirs+files 原始数据(供搜索)
let IMG_CLIP = "";    // 复制的路径
let IMG_SELECTED = ""; // 选中的文件/文件夹路径（用于复制/导出）


function _updateImgSelectedDisplay() {
  const btnDel = document.getElementById("btnImgDelete");
  const btnRename = document.getElementById("btnImgRename");
  if (!btnDel) return;
  if (IMG_SELECTED) {
    const fn = IMG_SELECTED.split("/").pop() || IMG_SELECTED;
    btnDel.innerHTML = `🗑️ 删除选中 <span style="font-size:11px;opacity:0.85;font-weight:400">(${esc(fn)})</span>`;
    btnDel.title = `删除当前选中的文件或文件夹: ${IMG_SELECTED}`;
    if (btnRename) btnRename.title = `重命名当前选中的文件或文件夹: ${IMG_SELECTED}`;
  } else {
    btnDel.innerHTML = `🗑️ 删除选中`;
    btnDel.title = "请先单击选中要删除的文件或文件夹";
    if (btnRename) btnRename.title = "请先单击选中要重命名的文件或文件夹";
  }
}

async function loadImages(dir) {
  try {
    if (dir === "0") dir = "";
    IMG_DIR = dir || "";
    IMG_SELECTED = ""; // 切换目录重置选中，彻底杜绝跨目录幽灵删除与错位
    _updateImgSelectedDisplay();

    const d = await getBridge().apiGet("images/list", { dir: IMG_DIR });
    if (!d || d.error) throw new Error((d && (d.error || d.msg)) || "图片库接口异常");
    IMG_CACHE = d;
    // 面包屑
    const segs = (d.dir || "").split("/").filter(Boolean);
    let crumb = `<a data-imgcrumb="" class="crumb-link" title="返回根目录">根目录</a>`;
    let acc = "";
    segs.forEach((s, i) => {
      acc += (acc ? "/" : "") + s;
      crumb += ` <span class="crumb-sep">/</span> <a data-imgcrumb="${esc(acc)}" class="crumb-link" title="进入目录 ${esc(s)}">${esc(s)}</a>`;
    });
    document.getElementById("imgCrumbs").innerHTML = `<span class="crumbs">${crumb}</span>`;
    document.querySelectorAll("#imgCrumbs a[data-imgcrumb]").forEach((a) =>
      a.addEventListener("click", () => loadImages(a.dataset.imgcrumb)));
    renderImages(d);
  } catch (e) {
    err("images: " + e.message);
    try { TAB_DONE.imgs = false; } catch (_e) {}
  }
}

function renderImages(d) {
  const box = document.getElementById("imgBrowser");
  const q = (document.getElementById("imgSearch").value || "").trim().toLowerCase();
  window._imgIsDir = (p) => (d.dirs || []).some(x => x.path === p);
  const isShopPick = !!window.SHOP_PICK_TARGET;
  let html = `<div class="grid">`;

  (d.dirs || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    const selCls = IMG_SELECTED === x.path ? ' selected' : '';
    html += `<div class="fcard${selCls}" data-imgdir="${esc(x.path)}" title="${esc(x.name)} (双击进入)">
      <div class="fi">📁</div>
      <div class="fn">${esc(x.name)}</div>
    </div>`;
  });

  (d.files || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    const ext = (x.name.split(".").pop() || "").toLowerCase();
    const isImg = ["png","jpg","jpeg","gif","webp","bmp","ico"].includes(ext);
    if (isShopPick && !isImg) return;
    const selCls = IMG_SELECTED === x.path ? ' selected' : '';
    let ficon = "📄";
    if (isImg) ficon = "";
    else if (ext === "json") ficon = "📄";
    else if (ext === "md") ficon = "📝";
    else if (ext === "txt") ficon = "📃";
    else if (ext === "py") ficon = "🐍";
    else if (ext === "db" || ext === "db-wal" || ext === "db-shm") ficon = "🗄️";
    else if (ext === "ini") ficon = "⚙️";
    else if (ext === "zip") ficon = "🗜️";
    else if (ext === "log") ficon = "📜";

    html += `<div class="icard${selCls}" data-imgsrc="${esc(x.img || "")}" data-imgname="${esc(x.name)}" data-selpath="${esc(x.path)}" title="${esc(x.name)} (双击看大图/单击选中)">
      ${isImg ? `<button type="button" class="img-preview-badge" data-action="preview" title="查看大图" style="position:absolute;top:6px;right:6px;background:rgba(0,0,0,0.55);color:#fff;border:none;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:12px;z-index:2">👁️</button>` : ""}
      ${ficon ? `<div class="fi">${ficon}</div>` : `<img class="icard-img" loading="lazy" decoding="async" src="${esc(_safeImgSrc(x.img))}" alt="" style="height:88px;width:100%;object-fit:cover;border-radius:var(--radius-md);display:block">`}
      <div class="nm">${esc(x.name)}</div>
    </div>`;
  });

  html += `</div>`;
  box.innerHTML = html;

  // 异步自动拉取并填充当前图片卡片的真实缩略图（限流 5 并发，防 30 图同时打桥排队）
  const thumbCards = Array.from(box.querySelectorAll(".icard[data-selpath]")).filter((card) => {
    const ext = (card.dataset.selpath.split(".").pop() || "").toLowerCase();
    return ["png","jpg","jpeg","gif","webp","bmp","ico"].includes(ext);
  });
  let _thumbIdx = 0;
  async function _thumbWorker() {
    while (_thumbIdx < thumbCards.length) {
      const card = thumbCards[_thumbIdx++];
      const p = card.dataset.selpath;
      try {
        const res = await getBridge().apiGet("images/preview", { path: p });
        if (res && res.thumb) {
          card.dataset.imgsrc = res.thumb;
          const imgEl = card.querySelector("img");
          if (imgEl) imgEl.src = _safeImgSrc(res.thumb);
        }
      } catch (e) {}
    }
  }
  Array.from({ length: Math.min(5, thumbCards.length) }).forEach(() => _thumbWorker());

  async function _previewCard(card) {
    if (!card) return;
    const name = card.dataset.imgname || "";
    const p = card.dataset.selpath;
    if (!p) return;
    const ext = (p.split(".").pop() || "").toLowerCase();
    // 文本文件：走 images/text 在线浏览（json/md/txt/yaml/ini/log 等）
    if (["json","md","markdown","txt","text","yaml","yml","ini","cfg","toml","csv","log"].includes(ext)) {
      try {
        toast("正在载入文本预览…", "ok", 1200);
        const res = await getBridge().apiGet("images/text", { path: p });
        if (res && !res.error && typeof res.text === "string") {
          showTextPreview(name || p, res.text, !!res.truncated, p);
        } else {
          toast("文本预览失败: " + ((res && (res.error || res.msg)) || "未知错误"), "bad");
        }
      } catch(err) {
        toast("文本预览失败: " + (err.message || String(err)), "bad");
      }
      return;
    }
    let src = card.dataset.imgsrc;
    // data-imgsrc 缺失时为 ""（旧缓存可能是 "undefined" 字符串）：一律视为无图，走缩略图拉取
    if (!src || src === "undefined") src = "";
    if (src) {
      showLightbox(src, name);
      return;
    }
    try {
      toast("正在载入大图预览…", "ok", 1200);
      const res = await getBridge().apiGet("images/preview", { path: p });
      if (res && res.thumb) {
        card.dataset.imgsrc = res.thumb;
        const imgEl = card.querySelector("img");
        if (imgEl) imgEl.src = _safeImgSrc(res.thumb);
        showLightbox(res.thumb, name);
      } else {
        toast("预览图读取失败", "bad");
      }
    } catch(err) {
      toast("加载大图失败: " + (err.message || String(err)), "bad");
    }
  }

function showTextPreview(name, text, truncated, filePath) {
  const modal = document.getElementById("appModal");
  if (!modal) return;
  const icon = document.getElementById("appModalIcon");
  const title = document.getElementById("appModalTitle");
  const content = document.getElementById("appModalContent");
  const inputWrap = document.getElementById("appModalInputWrap");
  const cancelBtn = document.getElementById("appModalCancel");
  const okBtn = document.getElementById("appModalOk");
  const closeBtn = document.getElementById("appModalClose");
  const modalBox = modal.querySelector(".cmd-modal-box");
  if (modalBox) modalBox.classList.add("modal-wide");

  if (icon) icon.textContent = "✏️";
  if (title) title.textContent = String(name || "文本编辑器");
  if (inputWrap) inputWrap.style.display = "none";

  let isDirty = false;
  const initialText = String(text || "");

  if (content) {
    content.innerHTML = `
      <div style="margin:2px 0 6px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;gap:8px;flex-wrap:wrap">
          <span style="font-size:12px;color:var(--muted)" id="textEditorMeta">
            ${truncated ? '<span class="badge badge-warn" style="margin-right:6px">已截断前256KB</span>' : ''}
            <span>字数: ${initialText.length}</span>
            <span class="badge badge-success" style="margin-left:6px" id="textEditorDirtyBadge">未修改</span>
          </span>
          <div style="display:flex;gap:6px;align-items:center">
            <button id="btnCopyTextPreview" class="ghost sm" style="padding:4px 12px;cursor:pointer">📋 复制</button>
          </div>
        </div>
        <textarea class="text-editor-textarea" id="textEditorArea" spellcheck="false" placeholder="在此编辑文件内容…">${esc(initialText)}</textarea>
      </div>`;
  }

  const ta = document.getElementById("textEditorArea");
  const dirtyBadge = document.getElementById("textEditorDirtyBadge");
  const metaSpan = document.getElementById("textEditorMeta");
  const copyBtn = document.getElementById("btnCopyTextPreview");

  if (ta) {
    ta.addEventListener("input", () => {
      isDirty = (ta.value !== initialText);
      if (dirtyBadge) {
        if (isDirty) {
          dirtyBadge.className = "badge badge-warn";
          dirtyBadge.textContent = "● 未保存修改";
          dirtyBadge.style.display = "inline-flex";
        } else {
          dirtyBadge.className = "badge badge-success";
          dirtyBadge.textContent = "未修改";
        }
      }
    });

    ta.addEventListener("keydown", (e) => {
      if (e.key === "Tab") {
        e.preventDefault();
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        ta.value = ta.value.substring(0, start) + "  " + ta.value.substring(end);
        ta.selectionStart = ta.selectionEnd = start + 2;
        ta.dispatchEvent(new Event("input"));
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (okBtn) okBtn.click();
      }
    });
  }

  if (copyBtn && ta) {
    copyBtn.onclick = () => {
      copyToClipboard(ta.value);
      copyBtn.textContent = "✅ 已复制";
      setTimeout(() => { copyBtn.textContent = "📋 复制"; }, 1800);
    };
  }

  const doClose = async () => {
    if (isDirty) {
      let ok = false;
      try {
        // 文本编辑器占用 #appModal，须走独立 overlay 版（uiConfirm 会清掉编辑内容丢稿），见 01_theme 注释
        ok = await pageConfirm("文件已修改但尚未保存，确定要放弃修改并关闭吗？", "放弃修改");
      } catch (e) { ok = false; }
      if (!ok) return;
    }
    modal.className = "";
    if (modalBox) modalBox.classList.remove("modal-wide");
    if (cancelBtn) { cancelBtn.style.display = ""; cancelBtn.textContent = "取消"; }
    if (okBtn) { okBtn.textContent = "确定"; okBtn.onclick = null; }
    if (closeBtn) closeBtn.onclick = null;
    modal.onclick = null;
  };

  if (cancelBtn) {
    cancelBtn.style.display = "inline-flex";
    cancelBtn.textContent = "关闭";
    cancelBtn.onclick = doClose;
  }
  if (closeBtn) {
    closeBtn.onclick = doClose;
  }
  if (okBtn) {
    okBtn.textContent = "💾 保存文件";
    okBtn.onclick = async () => {
      if (!filePath) {
        toast("无法识别文件路径", "bad");
        return;
      }
      const newText = ta ? ta.value : "";
      okBtn.disabled = true;
      okBtn.textContent = "正在保存…";
      try {
        const res = await getBridge().apiPost("images/text/save", { path: filePath, text: newText });
        if (res && res.ok) {
          toast("文件已保存", "ok");
          isDirty = false;
          modal.className = "";
          if (modalBox) modalBox.classList.remove("modal-wide");
          if (cancelBtn) cancelBtn.style.display = "";
          okBtn.onclick = null;
          if (closeBtn) closeBtn.onclick = null;
          modal.onclick = null;
        } else {
          toast("保存失败: " + ((res && (res.error || res.msg)) || "未知错误"), "bad");
        }
      } catch (err) {
        toast("保存异常: " + (err.message || String(err)), "bad");
      } finally {
        if (okBtn) {
          okBtn.disabled = false;
          okBtn.textContent = "💾 保存文件";
        }
      }
    };
  }
  modal.onclick = (e) => {
    if (e.target === modal) doClose();
  };
  modal.className = "show";
}

  // 统一事件委托处理选择、双击与大图预览
  box.onclick = (e) => {
    // 点击查看大图按钮
    const prevBtn = e.target.closest('[data-action="preview"]');
    if (prevBtn) {
      e.stopPropagation();
      const card = prevBtn.closest(".icard");
      _previewCard(card);
      return;
    }

    const card = e.target.closest(".fcard, .icard");
    if (!card) return;

    if (window.SHOP_PICK_TARGET && card.dataset.imgdir) return; // 选图模式下文件夹仅可双击进入

    const path = card.dataset.imgdir || card.dataset.selpath;
    if (path) {
      IMG_SELECTED = path;
      box.querySelectorAll(".fcard, .icard").forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      _updateImgSelectedDisplay();
    }
  };

  box.ondblclick = (e) => {
    const card = e.target.closest(".fcard, .icard");
    if (!card) return;
    if (card.dataset.imgdir) {
      loadImages(card.dataset.imgdir);
    } else if (card.classList.contains("icard")) {
      _previewCard(card);
    }
  };

  window._imgFiles = (d.files || []).map((x) => x.name);
}

function showLightbox(src, name) {
  const lb = document.getElementById("lightbox");
  if (!lb || !src) { if (lb) { lb.innerHTML = ""; } return; }
  lb.innerHTML = `<img src="${esc(_safeImgSrc(src))}"><div class="cap">${esc(name || "")}</div>`;
  lb.classList.add("show");
}

function closeLightbox() {
  const lb = document.getElementById("lightbox");
  if (lb) { lb.classList.remove("show"); lb.innerHTML = ""; }
}

function fileToBase64(file) {
  return new Promise((res, rej) => {
    try {
      const fr = new FileReader();
      fr.onload = () => {
        const s = String(fr.result || "");
        res(s.includes(",") ? s.split(",", 2)[1] : s);
      };
      fr.onerror = () => rej(new Error("文件读取失败"));
      fr.readAsDataURL(file);
    } catch (e) { rej(e); }
  });
}

async function postFile(api, extra, file) {
  const b64 = await fileToBase64(file);
  if (!b64) throw new Error("文件读取失败");
  let ep = api;
  const q = {};
  try {
    const s = String(api || "");
    const qi = s.indexOf("?");
    if (qi >= 0) {
      ep = s.slice(0, qi);
      new URLSearchParams(s.slice(qi + 1)).forEach((v, k) => { q[k] = v; });
    }
  } catch (e) {}
  return getBridge().apiPost(ep, { ...q, ...(extra || {}), filename: file.name, file_base64: b64 });
}

async function uploadImage(file) {
  if (!file) return;
  toast("上传中…", "");
  try {
    await postFile("images/upload?dir=" + encodeURIComponent(IMG_DIR || "data/img"), {}, file);
    toast("已上传", "ok");
    await loadImages(IMG_DIR);
  } catch (e) {
    err("上传失败: " + e.message);
  }
}

function bindTabs() {
  const btns = document.querySelectorAll("#mainTabs button, #sideNav button[data-tab]");
  const TAB_GROUPS = {
    data: ["overview", "rank"],
    users: ["users", "slave", "spirit_users"],
    groups: ["groups"],
    rules: ["config", "cmds"],
    mall: ["shops", "spirits"],
    ops: ["backups", "imgs", "logs", "about"]
  };
  const _groupLastTab = {};
  function tabGroupOf(tab) {
    for (const g in TAB_GROUPS) if (TAB_GROUPS[g].indexOf(tab) >= 0) return g;
    return "data";
  }
  btns.forEach((b) => {
    b.addEventListener("click", () => {
      _groupLastTab[tabGroupOf(b.dataset.tab)] = b.dataset.tab;
      document.querySelectorAll("#tabGroups button").forEach((x) => x.classList.toggle("on", x.dataset.group === tabGroupOf(b.dataset.tab)));
      btns.forEach((x) => x.classList.toggle("on", x.dataset.tab === b.dataset.tab));
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("on"));
      const el = document.getElementById("tab-" + b.dataset.tab);
      if (el) el.classList.add("on");
      const tab = b.dataset.tab;
      if (tab === "logs") {
        if (typeof loadLogs === "function") loadLogs(false);
        if (typeof startLogsAutoRefresh === "function") startLogsAutoRefresh();
      } else {
        if (typeof stopLogsAutoRefresh === "function") stopLogsAutoRefresh();
      }
      try { b.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" }); } catch (e) {}
      if (tab === "overview") {
        Promise.resolve(loadOverviewReq()).catch((e) => err("tab overview: " + e.message));
        Promise.resolve(loadStats()).catch(() => {});
        return;
      }
      if (!TAB_DONE[tab] && TAB_LOADERS[tab]) {
        TAB_DONE[tab] = true;
        Promise.resolve(TAB_LOADERS[tab]()).then(() => {}).catch((e) => {
          try { TAB_DONE[tab] = false; } catch (_e) {}
          err("tab " + tab + ": " + e.message);
        });
      }
    });
  });

  function showGroup(g) {
    if (!TAB_GROUPS[g]) g = "data";
    document.querySelectorAll("#tabGroups button").forEach((x) => x.classList.toggle("on", x.dataset.group === g));
    btns.forEach((b) => { b.hidden = b.closest("#mainTabs") ? TAB_GROUPS[g].indexOf(b.dataset.tab) < 0 : false; });
  }
  document.querySelectorAll("#tabGroups button").forEach((gb) => {
    gb.addEventListener("click", () => {
      const g = gb.dataset.group;
      showGroup(g);
      const target = _groupLastTab[g] || TAB_GROUPS[g][0];
      const btn = target && document.querySelector('#mainTabs button[data-tab="' + target + '"]');
      if (btn) btn.click();
    });
  });
  document.querySelectorAll("#sideNav .side-group").forEach((grp) => {
    const title = grp.querySelector(".side-group-title");
    const first = grp.querySelector("button[data-tab]");
    if (title && first) {
      title.style.cursor = "pointer";
      title.addEventListener("click", () => {
        const g = tabGroupOf(first.dataset.tab);
        showGroup(g);
        const target = _groupLastTab[g] || first.dataset.tab;
        const btn = document.querySelector('#sideNav button[data-tab="' + target + '"]');
        if (btn) btn.click();
      });
    }
  });
  const _initOn = document.querySelector("#sideNav button.on") || document.querySelector("#mainTabs button.on");
  showGroup(tabGroupOf(_initOn ? _initOn.dataset.tab : "overview"));
  try {
    document.querySelector("#mainTabs button.on")?.scrollIntoView({ inline: "center", block: "nearest" });
  } catch (e) {}
}
// 悬浮岛式侧边栏交互（触发按钮、关闭按钮、背景遮罩、ESC快捷键、Tab点击自动收起）
function initSideNavCollapse() {
  const nav = document.getElementById("sideNav");
  const toggle = document.getElementById("sideNavToggle");
  const islandToggle = document.getElementById("floatingIslandToggle");
  const backdrop = document.getElementById("islandBackdrop");
  if (!nav) return;
  if (nav._islandInited) return;
  nav._islandInited = true;

  nav.querySelectorAll("button[data-tab]").forEach((b) => {
    const raw = b.textContent.trim();
    const i = raw.indexOf(" ");
    if (i > 0) b.innerHTML = raw.slice(0, i) + '<span class="side-nav-label">' + raw.slice(i + 1) + "</span>";
    b.title = raw;
  });

  // 权威显隐状态标（彻底消除异步动效延迟竞争导致的死锁与失效）
  let isOpen = false;
  let activeAnimCancel = null;

  const cancelActiveAnim = () => {
    if (activeAnimCancel) {
      try { activeAnimCancel(); } catch (e) {}
      activeAnimCancel = null;
    }
    document.querySelectorAll(".harmony-powder-canvas").forEach((c) => {
      try { c.parentNode.removeChild(c); } catch (e) {}
    });
  };

  const applyClosedDOM = () => {
    nav.classList.add("collapsed");
    nav.style.transform = "";
    nav.style.opacity = "";
    nav.style.transition = "";
    if (backdrop) backdrop.classList.remove("active");
    if (islandToggle) {
      islandToggle.setAttribute("aria-expanded", "false");
      islandToggle.classList.remove("active");
    }
  };

  const applyOpenDOM = () => {
    nav.classList.remove("collapsed");
    nav.style.transform = "";
    nav.style.opacity = "";
    nav.style.transition = "";
    if (backdrop) backdrop.classList.add("active");
    if (islandToggle) {
      islandToggle.setAttribute("aria-expanded", "true");
      islandToggle.classList.add("active");
    }
  };

  // 默认启动状态：强制收起
  isOpen = false;
  applyClosedDOM();

  // 关闭悬浮岛 (立即切换权威状态，支持高密粒子粉末崩解动效)
  const closeIsland = (withAnim = true) => {
    if (!isOpen) return;
    isOpen = false;
    cancelActiveAnim();

    // 立即更新控制按钮与遮罩状态，消除视觉延迟与点击拦截
    if (islandToggle) {
      islandToggle.setAttribute("aria-expanded", "false");
      islandToggle.classList.remove("active");
    }
    if (backdrop) backdrop.classList.remove("active");

    if (!withAnim) {
      applyClosedDOM();
      return;
    }

    activeAnimCancel = triggerHarmonyDisintegrate(nav, () => {
      applyClosedDOM();
      activeAnimCancel = null;
    });
  };

  // 展开悬浮岛 (立即切换权威状态，支持星尘逆向聚拢凝结入场)
  const openIsland = (withAnim = true) => {
    if (isOpen) return;
    isOpen = true;
    cancelActiveAnim();

    if (islandToggle) {
      islandToggle.setAttribute("aria-expanded", "true");
      islandToggle.classList.add("active");
    }
    if (backdrop) backdrop.classList.add("active");

    if (!withAnim) {
      applyOpenDOM();
      return;
    }

    activeAnimCancel = triggerHarmonyAssemble(nav, islandToggle, () => {
      applyOpenDOM();
      activeAnimCancel = null;
    });
  };

  // 顶栏导航按钮：权威状态翻转，任意频次极速连击零死锁
  if (islandToggle) {
    islandToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      if (isOpen) {
        closeIsland(true);
      } else {
        openIsland(true);
      }
    });
  }

  // 点击侧边栏关闭胶囊按钮
  if (toggle) {
    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      closeIsland(true);
    });
  }

  // 点击遮罩空白处收起
  if (backdrop) {
    backdrop.addEventListener("click", (e) => {
      e.stopPropagation();
      closeIsland(true);
    });
  }

  // 点击全页面任意空白非导航区域收起
  document.addEventListener("click", (e) => {
    if (!isOpen) return;
    if (nav.contains(e.target)) return;
    if (islandToggle && islandToggle.contains(e.target)) return;
    closeIsland(true);
  });

  // 点击导航选项自动平滑收起
  nav.querySelectorAll("button[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      closeIsland(true);
    });
  });

  // ESC 键收起
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen) {
      closeIsland(true);
    }
  });
}

// ---------- 鸿蒙组件粉末化消散特效 (HarmonyOS Powder Disintegration - 800+ 粒子高密慢速流光版) ----------
function triggerHarmonyDisintegrate(el, onComplete) {
  if (!el) {
    if (onComplete) onComplete();
    return () => {};
  }
  const rect = el.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    if (onComplete) onComplete();
    return () => {};
  }

  const canvas = document.createElement("canvas");
  canvas.className = "harmony-powder-canvas";
  canvas.style.position = "fixed";
  canvas.style.left = "0";
  canvas.style.top = "0";
  canvas.style.width = "100vw";
  canvas.style.height = "100vh";
  canvas.style.pointerEvents = "none";
  canvas.style.zIndex = "9999";
  document.body.appendChild(canvas);

  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = window.innerWidth * dpr;
  canvas.height = window.innerHeight * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const isDark = document.documentElement.dataset.theme === "dark";
  const primaryColor = getComputedStyle(document.documentElement).getPropertyValue("--m3-sys-color-primary").trim() || "#4A90D9";
  const colors = isDark
    ? [primaryColor, "#8AB8F0", "#D6E8FA", "#434E5E", "#232A33", "#A9C9F5", "#CBD5E1", "#FFFFFF"]
    : [primaryColor, "#64B5F6", "#D9E8F7", "#DFE6EF", "#FFFFFF", "#90CAF9", "#B0BEC5", "#E3F2FD"];

  // 极高密度粉末微粒 (750 ~ 880 颗微粉尘)
  const count = Math.min(Math.floor((rect.width * rect.height) / 95), 850);
  const particles = [];
  for (let i = 0; i < count; i++) {
    const px = rect.left + Math.random() * rect.width;
    const py = rect.top + Math.random() * rect.height;
    const angle = Math.random() * Math.PI * 2;
    // 稍稍慢一点点：速度调平缓，增强烟尘微粒的优雅悬浮感
    const speed = Math.random() * 3.6 + 0.6;
    particles.push({
      x: px,
      y: py,
      vx: Math.cos(angle) * speed * 0.7 + (Math.random() - 0.45) * 2.0,
      vy: Math.sin(angle) * speed * 0.7 - Math.random() * 2.2 - 0.5, // 向上轻盈袅袅微升
      size: Math.random() * 2.2 + 0.9,
      alpha: Math.random() * 0.35 + 0.65,
      decay: Math.random() * 0.014 + 0.009, // 衰减稍慢，约 700~900ms 优雅消隐
      color: colors[Math.floor(Math.random() * colors.length)],
      spin: Math.random() * 0.22 - 0.11,
      angle: Math.random() * Math.PI,
    });
  }

  // 元素本体瞬间崩解淡出并微缩
  el.style.transition = "transform 0.18s ease-out, opacity 0.15s ease-out";
  el.style.transform = "scale(0.96) translate3d(0, -4px, 0)";
  el.style.opacity = "0";

  let animId;
  const startTime = performance.now();

  function render(now) {
    const elapsed = now - startTime;
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

    let aliveCount = 0;
    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      if (p.alpha <= 0.01) continue;
      aliveCount++;

      p.x += p.vx;
      p.y += p.vy;
      p.vx *= 0.965; // 空气摩擦稍弱，更轻盈
      p.vy *= 0.965;
      p.vy -= 0.035; // 烟尘微浮
      p.alpha -= p.decay;
      p.size = Math.max(0.2, p.size * 0.985);
      p.angle += p.spin;

      ctx.save();
      ctx.globalAlpha = Math.max(0, p.alpha);
      ctx.fillStyle = p.color;
      ctx.translate(p.x, p.y);
      ctx.rotate(p.angle);
      ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
      ctx.restore();
    }

    if (aliveCount > 0 && elapsed < 950) {
      animId = requestAnimationFrame(render);
    } else {
      cancelAnimationFrame(animId);
      if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
      el.style.opacity = "";
      el.style.transform = "";
      el.style.transition = "";
      if (onComplete) onComplete();
    }
  }

  animId = requestAnimationFrame(render);

  return () => {
    cancelAnimationFrame(animId);
    if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
    el.style.opacity = "";
    el.style.transform = "";
    el.style.transition = "";
  };
}
window.triggerHarmonyDisintegrate = triggerHarmonyDisintegrate;

// ---------- 鸿蒙粒子汇聚进入特效 (HarmonyOS Particle Assembly - 800 颗高密星尘吸附版) ----------
function triggerHarmonyAssemble(el, triggerEl, onComplete) {
  if (!el) {
    if (onComplete) onComplete();
    return () => {};
  }

  // 预先显示以便抓取真实布局尺寸
  el.style.transition = "none";
  el.classList.remove("collapsed");
  el.style.opacity = "0";
  el.style.transform = "scale(0.96)";
  const rect = el.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    el.style.opacity = "";
    el.style.transform = "";
    el.style.transition = "";
    if (onComplete) onComplete();
    return () => {};
  }

  // 发射源头坐标
  const trigRect = triggerEl ? triggerEl.getBoundingClientRect() : { left: rect.left, top: rect.top - 40, width: 40, height: 30 };
  const originX = trigRect.left + trigRect.width / 2;
  const originY = trigRect.top + trigRect.height / 2;

  const canvas = document.createElement("canvas");
  canvas.className = "harmony-powder-canvas";
  canvas.style.position = "fixed";
  canvas.style.left = "0";
  canvas.style.top = "0";
  canvas.style.width = "100vw";
  canvas.style.height = "100vh";
  canvas.style.pointerEvents = "none";
  canvas.style.zIndex = "9999";
  document.body.appendChild(canvas);

  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = window.innerWidth * dpr;
  canvas.height = window.innerHeight * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const isDark = document.documentElement.dataset.theme === "dark";
  const primaryColor = getComputedStyle(document.documentElement).getPropertyValue("--m3-sys-color-primary").trim() || "#4A90D9";
  const colors = isDark
    ? [primaryColor, "#8AB8F0", "#D6E8FA", "#384556", "#A9C9F5", "#FFFFFF"]
    : [primaryColor, "#64B5F6", "#D9E8F7", "#DFE6EF", "#FFFFFF", "#90CAF9", "#2196F3"];

  // 700 ~ 850 颗汇聚微粉尘
  const count = Math.min(Math.floor((rect.width * rect.height) / 100), 800);
  const particles = [];
  for (let i = 0; i < count; i++) {
    const destX = rect.left + Math.random() * rect.width;
    const destY = rect.top + Math.random() * rect.height;
    const isFromTrigger = Math.random() < 0.65;
    const startX = isFromTrigger ? (originX + (Math.random() - 0.5) * 26) : (destX + (Math.random() - 0.5) * 140);
    const startY = isFromTrigger ? (originY + (Math.random() - 0.5) * 20) : (destY + (Math.random() - 0.5) * 90 - 30);

    // 稍稍慢一点点：流淌时长拉伸至 340~480ms，更加连贯细腻
    particles.push({
      startX,
      startY,
      destX,
      destY,
      delay: Math.random() * 120,
      duration: 320 + Math.random() * 160,
      size: Math.random() * 2.2 + 1.0,
      color: colors[Math.floor(Math.random() * colors.length)],
      swirl: (Math.random() - 0.5) * 20,
    });
  }

  let animId;
  const startTime = performance.now();
  let cardRevealed = false;

  function render(now) {
    const elapsed = now - startTime;
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

    let activeCount = 0;
    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      const t = (elapsed - p.delay) / p.duration;
      if (t < 0) {
        activeCount++;
        continue;
      }
      if (t > 1) continue;
      activeCount++;

      // 三次方平滑缓动吸附
      const ease = 1 - Math.pow(1 - t, 3);
      const curX = p.startX + (p.destX - p.startX) * ease + Math.sin(t * Math.PI) * p.swirl;
      const curY = p.startY + (p.destY - p.startY) * ease;
      const alpha = t < 0.25 ? (t / 0.25) : (1 - (t - 0.25) * 0.45);

      ctx.save();
      ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
      ctx.fillStyle = p.color;
      ctx.fillRect(curX - p.size / 2, curY - p.size / 2, p.size, p.size);
      ctx.restore();
    }

    // 粒子汇聚吸附至约 260ms 时，实体卡片以高阶弹性自愈凝结显现
    if (!cardRevealed && elapsed >= 260) {
      cardRevealed = true;
      el.style.transition = "transform 0.28s cubic-bezier(0.18, 0.95, 0.25, 1.15), opacity 0.24s ease-out";
      el.style.opacity = "1";
      el.style.transform = "scale(1)";
    }

    if (activeCount > 0 && elapsed < 650) {
      animId = requestAnimationFrame(render);
    } else {
      cancelAnimationFrame(animId);
      if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
      el.style.opacity = "";
      el.style.transform = "";
      el.style.transition = "";
      if (onComplete) onComplete();
    }
  }

  animId = requestAnimationFrame(render);

  return () => {
    cancelAnimationFrame(animId);
    if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
    el.style.opacity = "";
    el.style.transform = "";
    el.style.transition = "";
  };
}
window.triggerHarmonyAssemble = triggerHarmonyAssemble;
function err(m) {
  const e = document.getElementById("footErr");
  if (e) e.textContent = "加载/操作异常: " + m;
  toast("操作异常：" + m, "bad");
  console.error(m);
}

