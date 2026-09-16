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
        const res = await getBridge().apiGet("images/thumb", { path: p });
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
        const res = await callApi("images/text", { path: p }, "GET");
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
      const res = await callApi("images/thumb", { path: p }, "GET");
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

  const doClose = () => {
    if (isDirty) {
      if (!confirm("文件已修改但尚未保存，确定要放弃修改并关闭吗？")) return;
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
        const res = await callApi("images/text/save", { path: filePath, text: newText }, "POST");
        if (res && res.ok) {
          toast("文件保存成功！", "ok");
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
  const btns = document.querySelectorAll(".tabs button");
  btns.forEach((b) => {
    b.addEventListener("click", () => {
      btns.forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
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

  const tabsContainer = document.getElementById("mainTabs");
  document.getElementById("tabNavPrev")?.addEventListener("click", () => {
    if (tabsContainer) tabsContainer.scrollBy({ left: -160, behavior: "smooth" });
  });
  document.getElementById("tabNavNext")?.addEventListener("click", () => {
    if (tabsContainer) tabsContainer.scrollBy({ left: 160, behavior: "smooth" });
  });
  tabsContainer?.addEventListener("wheel", (e) => {
    if (Math.abs(e.deltaX) < Math.abs(e.deltaY)) {
      e.preventDefault();
      tabsContainer.scrollLeft += e.deltaY;
    }
  }, { passive: false });
}
function err(m) {
  const e = document.getElementById("footErr");
  if (e) e.textContent = "加载/操作异常: " + m;
  toast("操作异常：" + m, "bad");
  console.error(m);
}

