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
    btnDel.innerHTML = `删除选中 <span style="font-size:11px;opacity:0.85;font-weight:400">(${esc(fn)})</span>`;
    btnDel.title = `删除当前选中的文件或文件夹: ${IMG_SELECTED}`;
    if (btnRename) btnRename.title = `重命名当前选中的文件或文件夹: ${IMG_SELECTED}`;
  } else {
    btnDel.innerHTML = `删除选中`;
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
      <div class="fi"><svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg></div>
      <div class="fn">${esc(x.name)}</div>
    </div>`;
  });

  (d.files || []).forEach((x) => {
    if (q && !x.name.toLowerCase().includes(q)) return;
    const ext = (x.name.split(".").pop() || "").toLowerCase();
    const isImg = ["png","jpg","jpeg","gif","webp","bmp","ico"].includes(ext);
    if (isShopPick && !isImg) return;
    const selCls = IMG_SELECTED === x.path ? ' selected' : '';

    html += `<div class="icard${selCls}" data-imgsrc="${esc(x.img || "")}" data-imgname="${esc(x.name)}" data-selpath="${esc(x.path)}" title="${esc(x.name)} (双击看大图/单击选中)">
      ${isImg ? `<button type="button" class="img-preview-badge" data-action="preview" title="查看大图" style="position:absolute;top:6px;right:6px;background:rgba(0,0,0,0.55);color:#fff;border:none;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:2"><svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg></button>` : ""}
      ${!isImg ? `<div class="fi"><span class="badge" style="font-size:11px;font-weight:700">${esc((ext || "FILE").toUpperCase())}</span></div>` : `<img class="icard-img" loading="lazy" decoding="async" src="${esc(_safeImgSrc(x.img))}" alt="" style="height:88px;width:100%;object-fit:cover;border-radius:var(--radius-md);display:block">`}
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

  if (icon) icon.textContent = "";
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
            <button id="btnCopyTextPreview" class="ghost sm" style="padding:4px 12px;cursor:pointer">复制</button>
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
      copyBtn.textContent = "已复制";
      setTimeout(() => { copyBtn.textContent = "复制"; }, 1800);
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
    okBtn.textContent = "保存文件";
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
          okBtn.textContent = "保存文件";
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
  const btns = document.querySelectorAll("#sideNav button[data-tab]");
  btns.forEach((b) => {
    b.addEventListener("click", () => {
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
      if (tab === "overview") {
        if (!TAB_DONE.overview) {
          TAB_DONE.overview = true;
          Promise.resolve(loadOverviewReq()).catch((e) => err("tab overview: " + e.message));
          Promise.resolve(loadStats()).catch(() => {});
        }
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
}
// 悬浮岛式侧边栏交互（统一全平台驱动：桌面端顶栏按钮 + 手机端 FAB + 遮罩 + 键盘 ESC + 粒子动效）
function initSideNavCollapse() {
  const nav = document.getElementById("sideNav");
  if (!nav || nav._islandInited) return;
  nav._islandInited = true;

  const toggle = document.getElementById("sideNavToggle");
  const islandHead = nav.querySelector(".island-head");
  const backdrop = document.getElementById("islandBackdrop");
  const triggers = [
    document.getElementById("floatingIslandToggle"),
    document.getElementById("mobileIslandFab")
  ].filter(Boolean);

  nav.querySelectorAll("button[data-tab]").forEach((b) => {
    b.title = b.textContent.trim();
  });

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

  const setControlsState = (open, instant = false) => {
    if (instant) {
      nav.style.transition = "none";
      if (backdrop) backdrop.style.transition = "none";
    }
    nav.classList.toggle("collapsed", !open);
    nav.style.transform = "";
    nav.style.opacity = "";
    if (instant) {
      requestAnimationFrame(() => {
        nav.style.transition = "";
        if (backdrop) backdrop.style.transition = "";
      });
    } else {
      nav.style.transition = "";
    }
    if (backdrop) backdrop.classList.toggle("active", open);
    triggers.forEach((t) => {
      t.setAttribute("aria-expanded", open ? "true" : "false");
      t.classList.toggle("active", open);
    });
  };

  // 默认启动状态：强制收起
  isOpen = false;
  setControlsState(false, true);

  const getVisibleTrigger = () => {
    return triggers.find((t) => window.getComputedStyle(t).display !== "none") || triggers[0];
  };

  const closeIsland = (withAnim = true) => {
    if (!isOpen) return;
    isOpen = false;
    cancelActiveAnim();
    setControlsState(false);

    if (!withAnim) return;

    activeAnimCancel = triggerHarmonyDisintegrate(nav, () => {
      setControlsState(false, true);
      activeAnimCancel = null;
    });
  };

  const openIsland = (withAnim = true) => {
    if (isOpen) return;
    isOpen = true;
    cancelActiveAnim();
    setControlsState(true);

    if (!withAnim) return;

    activeAnimCancel = triggerHarmonyAssemble(nav, getVisibleTrigger(), () => {
      setControlsState(true);
      activeAnimCancel = null;
    });
  };

  // 触发入口统一绑定（PC 顶栏导航按钮 + 移动端右下角 FAB，一套逻辑全平台复用）
  triggers.forEach((t) => {
    t.addEventListener("click", (e) => {
      e.stopPropagation();
      isOpen ? closeIsland(true) : openIsland(true);
    });
  });

  // 收起入口（关闭按钮、顶部拖拽条、遮罩）
  [toggle, islandHead, backdrop].filter(Boolean).forEach((el) => {
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      closeIsland(true);
    });
  });

  // 点击全页面任意空白非导航区域收起
  document.addEventListener("click", (e) => {
    if (!isOpen) return;
    if (nav.contains(e.target)) return;
    if (triggers.some((t) => t.contains(e.target))) return;
    closeIsland(true);
  });

  // 点击导航选项触发粒子粉末崩解收起
  nav.querySelectorAll("button[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      closeIsland(true);
    });
  });

  // ESC 键收起
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen) closeIsland(true);
  });
}

// ---------- 鸿蒙组件粉末化消散特效 (HarmonyOS 1:1 Physical Powder Disintegration - 120 FPS 满帧引擎) ----------
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
  canvas.style.left = "0px";
  canvas.style.top = "0px";
  canvas.style.width = "100vw";
  canvas.style.height = "100vh";
  canvas.style.pointerEvents = "none";
  canvas.style.zIndex = "9999";
  document.body.appendChild(canvas);

  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const ctx = canvas.getContext("2d");

  const isDark = document.documentElement.dataset.theme === "dark";
  const primaryColor = getComputedStyle(document.documentElement).getPropertyValue("--m3-sys-color-primary").trim() || "#4A90D9";
  const colors = isDark
    ? [primaryColor, "#8AB8F0", "#D6E8FA", "#384556", "#A9C9F5", "#FFFFFF", "#CBD5E1"]
    : [primaryColor, "#64B5F6", "#D9E8F7", "#DFE6EF", "#FFFFFF", "#90CAF9", "#2196F3"];

  // 1:1 组件级表面网格微尘采样 (自适应几何尺寸，整屏呈现 2,000+ 物理紧密细沙)
  const cols = Math.max(16, Math.min(24, Math.round(rect.width / 14)));
  const rows = Math.max(20, Math.min(32, Math.round(rect.height / 20)));
  const stepX = rect.width / cols;
  const stepY = rect.height / rows;
  const particles = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const px = rect.left + (c + Math.random()) * stepX;
      const py = rect.top + (r + Math.random()) * stepY;
      const angle = Math.random() * Math.PI * 2;
      const speed = Math.random() * 2.8 + 0.4;
      particles.push({
        x: px,
        y: py,
        vx: Math.cos(angle) * speed * 0.7 + (Math.random() - 0.5) * 1.4,
        vy: Math.sin(angle) * speed * 0.45 - Math.random() * 2.0 - 0.7,
        size: Math.random() * 1.8 + 0.8,
        alpha: Math.random() * 0.3 + 0.7,
        decay: Math.random() * 0.019 + 0.015,
        color: colors[Math.floor(Math.random() * colors.length)],
        ox1: ((Math.random() - 0.5) * 10) | 0,
        oy1: ((Math.random() - 0.5) * 10) | 0,
        ox2: ((Math.random() - 0.5) * 18) | 0,
        oy2: ((Math.random() - 0.5) * 18) | 0,
        ox3: ((Math.random() - 0.5) * 26) | 0,
        oy3: ((Math.random() - 0.5) * 26) | 0,
      });
    }
  }

  // 元素本体瞬间微缩并消失，粉末即刻接管视觉呈现，彻底释放毛玻璃 GPU 资源
  el.style.transition = "transform 0.08s ease-out, opacity 0.06s ease-out";
  el.style.transform = "scale(0.975) translate3d(0, 6px, 0)";
  el.style.opacity = "0";

  let animId;
  const startTime = performance.now();

  function render(now) {
    const elapsed = now - startTime;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    let aliveCount = 0;
    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      if (p.alpha <= 0.01) continue;
      aliveCount++;

      p.x += p.vx;
      p.y += p.vy;
      p.vx *= 0.962;
      p.vy *= 0.962;
      p.vy -= 0.035;
      p.alpha -= p.decay;
      p.size = Math.max(0.4, p.size * 0.985);

      ctx.globalAlpha = Math.max(0, p.alpha);
      ctx.fillStyle = p.color;
      const sz = p.size | 0 || 1;
      const rx = (p.x - sz / 2) | 0;
      const ry = (p.y - sz / 2) | 0;

      // 1. 主微粒核
      ctx.fillRect(rx, ry, sz, sz);

      // 2. 1:1 伴生高密微尘 (4x 假渲染，实显 2,000+ 物理细沙)
      ctx.fillRect(rx + p.ox1, ry + p.oy1, 1, 1);
      ctx.fillRect(rx + p.ox2, ry + p.oy2, 1, 1);
      if (p.alpha > 0.14) {
        ctx.fillRect(rx + p.ox3, ry + p.oy3, 1, 1);
      }
    }

    if (aliveCount > 0 && elapsed < 520) {
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

// ---------- 鸿蒙粒子汇聚进入特效 (HarmonyOS 1:1 Physical Assembly - 120 FPS 满帧引擎) ----------
function triggerHarmonyAssemble(el, triggerEl, onComplete) {
  if (!el) {
    if (onComplete) onComplete();
    return () => {};
  }

  // 预先显示以便抓取真实物理尺寸
  el.style.transition = "none";
  el.classList.remove("collapsed");
  el.style.opacity = "0";
  el.style.transform = "scale(0.97) translate3d(0, 8px, 0)";
  const rect = el.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    el.style.opacity = "";
    el.style.transform = "";
    el.style.transition = "";
    if (onComplete) onComplete();
    return () => {};
  }

  // 发射源头坐标（PC 顶栏按钮 / 手机端 FAB 纯几何坐标自适应）
  const trigRect = triggerEl ? triggerEl.getBoundingClientRect() : {
    left: rect.left,
    top: rect.top - 40,
    width: 44,
    height: 36
  };
  const originX = trigRect.left + trigRect.width / 2;
  const originY = trigRect.top + trigRect.height / 2;

  const canvas = document.createElement("canvas");
  canvas.className = "harmony-powder-canvas";
  canvas.style.position = "fixed";
  canvas.style.left = "0px";
  canvas.style.top = "0px";
  canvas.style.width = "100vw";
  canvas.style.height = "100vh";
  canvas.style.pointerEvents = "none";
  canvas.style.zIndex = "9999";
  document.body.appendChild(canvas);

  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const ctx = canvas.getContext("2d");

  const isDark = document.documentElement.dataset.theme === "dark";
  const primaryColor = getComputedStyle(document.documentElement).getPropertyValue("--m3-sys-color-primary").trim() || "#4A90D9";
  const colors = isDark
    ? [primaryColor, "#8AB8F0", "#D6E8FA", "#384556", "#A9C9F5", "#FFFFFF", "#CBD5E1"]
    : [primaryColor, "#64B5F6", "#D9E8F7", "#DFE6EF", "#FFFFFF", "#90CAF9", "#2196F3"];

  const cols = Math.max(16, Math.min(24, Math.round(rect.width / 14)));
  const rows = Math.max(20, Math.min(32, Math.round(rect.height / 20)));
  const stepX = rect.width / cols;
  const stepY = rect.height / rows;
  const particles = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const destX = rect.left + (c + Math.random()) * stepX;
      const destY = rect.top + (r + Math.random()) * stepY;
      const isFromTrigger = Math.random() < 0.72;
      const startX = isFromTrigger ? (originX + (Math.random() - 0.5) * 36) : (destX + (Math.random() - 0.5) * 90);
      const startY = isFromTrigger ? (originY + (Math.random() - 0.5) * 28) : (destY + (Math.random() - 0.5) * 70 + 20);

      particles.push({
        startX,
        startY,
        destX,
        destY,
        delay: Math.random() * 80,
        duration: 220 + Math.random() * 110,
        size: Math.random() * 1.8 + 0.8,
        color: colors[Math.floor(Math.random() * colors.length)],
        swirl: (Math.random() - 0.5) * 16,
        ox1: ((Math.random() - 0.5) * 10) | 0,
        oy1: ((Math.random() - 0.5) * 10) | 0,
        ox2: ((Math.random() - 0.5) * 18) | 0,
        oy2: ((Math.random() - 0.5) * 18) | 0,
      });
    }
  }

  let animId;
  const startTime = performance.now();
  let cardRevealed = false;

  function render(now) {
    const elapsed = now - startTime;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

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

      ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
      ctx.fillStyle = p.color;
      const sz = p.size | 0 || 1;
      const rx = (curX - sz / 2) | 0;
      const ry = (curY - sz / 2) | 0;

      // 1. 主星尘微粒核
      ctx.fillRect(rx, ry, sz, sz);

      // 2. 伴生星尘微粒
      ctx.fillRect(rx + p.ox1, ry + p.oy1, 1, 1);
      ctx.fillRect(rx + p.ox2, ry + p.oy2, 1, 1);
    }

    if (!cardRevealed && elapsed >= 180) {
      cardRevealed = true;
      el.style.transition = "transform 0.22s cubic-bezier(0.18, 0.95, 0.25, 1.15), opacity 0.18s cubic-bezier(0.16, 1, 0.3, 1)";
      el.style.opacity = "1";
      el.style.transform = "scale(1) translate3d(0, 0, 0)";
    }

    if (activeCount > 0 && elapsed < 450) {
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

