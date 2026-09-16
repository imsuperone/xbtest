const PLUGIN_ID = "astrbot_plugin_xbbot_beta";
// 构建时由 build_frontend.py 注入当前 metadata 版本（与后端对账用；源里永远是占位）
const FRONTEND_VER = "2026w0915f";

let _WORKING_API_PREFIX = null;

function cleanEndpointAndParams(endpoint, params) {
  let ep = String(endpoint || "").replace(/^\/+/, "");
  let mergedParams = (params && typeof params === "object") ? Object.assign({}, params) : {};
  if (ep.includes("?")) {
    const qIdx = ep.indexOf("?");
    const qStr = ep.slice(qIdx + 1);
    ep = ep.slice(0, qIdx);
    if (qStr) {
      try {
        const urlParams = new URLSearchParams(qStr);
        for (const [k, v] of urlParams.entries()) {
          if (!(k in mergedParams)) {
            mergedParams[k] = v;
          }
        }
      } catch (e) {}
    }
  }
  return { ep, params: mergedParams };
}

// 传文件类读接口不加超时（备份/镜像导出按体积走，服务端自有熔断；加了会误杀大文件下载）
const _NO_TIMEOUT_GET = /^(backups\/export|images\/export|user\/export|users\/export)/;

// 直连探测单航班（并发探测共用一个 promise，防首屏 3 并发各跑 5 前缀=15 次 fetch 的惊群）
let _PREFIX_PROBE_P = null;
function _warmPrefixOnce() {
  if (_WORKING_API_PREFIX !== null || _PREFIX_PROBE_P) return _PREFIX_PROBE_P;
  const probe = "config/get";
  const prefixes = [`/api/plugins/${PLUGIN_ID}/`, `/${PLUGIN_ID}/`, `api/`, `./api/`, ``];
  _PREFIX_PROBE_P = (async () => {
    for (const p of prefixes) {
      try {
        const r = await fetch(p + probe + "?_warm=1");
        if (r.ok) { _WORKING_API_PREFIX = p; break; }
      } catch (e) {}
    }
  })().finally(() => { _PREFIX_PROBE_P = null; });
  return _PREFIX_PROBE_P;
}

function getBridge() {
  let rawBridge = null;
  try {
    if (window.bridge && typeof window.bridge.apiGet === "function") rawBridge = window.bridge;
    else if (window.AstrBotPluginPage && typeof window.AstrBotPluginPage.apiGet === "function") rawBridge = window.AstrBotPluginPage;
    else {
      try {
        if (window.parent && window.parent.AstrBotPluginPage && typeof window.parent.AstrBotPluginPage.apiGet === "function") {
          rawBridge = window.parent.AstrBotPluginPage;
        } else if (window.parent && window.parent.bridge && typeof window.parent.bridge.apiGet === "function") {
          rawBridge = window.parent.bridge;
        }
      } catch (e) {}
    }
  } catch (e) {}

  if (rawBridge) {
    return {
      apiGet(endpoint, params) {
        const { ep, params: cleanParams } = cleanEndpointAndParams(endpoint, params);
        const _p = (cleanParams && Object.keys(cleanParams).length > 0)
          ? rawBridge.apiGet(ep, cleanParams)
          : rawBridge.apiGet(ep);
        // 读超时 30s（传文件类排除）；写操作另有服务端熔断，此处只治读 hung
        return _NO_TIMEOUT_GET.test(ep) ? _p : apiTimeout(_p, 30000, ep);
      },
      apiPost(endpoint, data) {
        const { ep } = cleanEndpointAndParams(endpoint);
        // 写超时 30s：黑洞 POST 不再 eternal hang（调用方 disabled 按钮可解开）
        return apiTimeout(rawBridge.apiPost(ep, data || {}), 30000, ep);
      },
      async upload(endpoint, file) {
        // 真桥无原生 upload，走 base64-JSON 直传（与 fallback 对齐，禁裸 FormData 走桥）
        return postFile(endpoint, {}, file);
      },
      download(endpoint, params, filename) {
        const { ep, params: cleanParams } = cleanEndpointAndParams(endpoint, params);
        if (typeof rawBridge.download === "function") {
          return rawBridge.download(ep, cleanParams, filename);
        }
      }
      // 注：真桥无原生 upload，此处转 postFile base64-JSON（禁裸 FormData 走桥）
    };
  }

  return {
    apiGet(endpoint, params) {
      const { ep, params: cleanParams } = cleanEndpointAndParams(endpoint, params);
      const _run = async () => {
      let fullEp = ep;
      if (cleanParams && Object.keys(cleanParams).length > 0) {
        fullEp += "?" + new URLSearchParams(cleanParams).toString();
      }
      if (_WORKING_API_PREFIX !== null) {
        try {
          const r = await fetch(_WORKING_API_PREFIX + fullEp);
          if (r.ok) return await r.json();
        } catch (err) {}
      } else if (_PREFIX_PROBE_P) {
        try { await _PREFIX_PROBE_P; } catch (e) {}
        if (_WORKING_API_PREFIX !== null) {
          try {
            const r = await fetch(_WORKING_API_PREFIX + fullEp);
            if (r.ok) return await r.json();
          } catch (err) {}
        }
      }
      const prefixes = [`/api/plugins/${PLUGIN_ID}/`, `/${PLUGIN_ID}/`, `api/`, `./api/`, ``];
      for (const p of prefixes) {
        try {
          const r = await fetch(p + fullEp);
          if (r.ok) {
            _WORKING_API_PREFIX = p;
            return await r.json();
          }
        } catch (err) {}
      }
      const r = await fetch(fullEp);
      return await r.json();
      };
      const _p = _run();
      return _NO_TIMEOUT_GET.test(ep) ? _p : apiTimeout(_p, 30000, ep);
    },
    async apiPost(endpoint, data) {
      const { ep } = cleanEndpointAndParams(endpoint);
      const _run = async () => {
      if (_WORKING_API_PREFIX !== null) {
        try {
          const r = await fetch(_WORKING_API_PREFIX + ep, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data || {})
          });
          if (r.ok) return await r.json();
        } catch (err) {}
      } else if (_PREFIX_PROBE_P) {
        try { await _PREFIX_PROBE_P; } catch (e) {}
        if (_WORKING_API_PREFIX !== null) {
          try {
            const r = await fetch(_WORKING_API_PREFIX + ep, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(data || {})
            });
            if (r.ok) return await r.json();
          } catch (err) {}
        }
      }
      const prefixes = [`/api/plugins/${PLUGIN_ID}/`, `/${PLUGIN_ID}/`, `api/`, `./api/`, ``];
      for (const p of prefixes) {
        try {
          const r = await fetch(p + ep, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data || {})
          });
          if (r.ok) {
            _WORKING_API_PREFIX = p;
            return await r.json();
          }
        } catch (err) {}
      }
      const r = await fetch(ep, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data || {})
      });
      return await r.json();
      };
      return apiTimeout(_run(), 30000, ep);
    },
    async upload(endpoint, file) {
      // 已收口：禁用裸 FormData，一律走 postFile base64-JSON（法则12）
      return postFile(endpoint, {}, file);
    }
  };
}
let CFG = {};

// 请求超时竞速（桥 sequential fallback 无超时，环境黑洞会 eternal hang：
// Tab 首次加载卡死即此因。超时转拒绝，调用方显示可重试错误，不再永久占位）。
function apiTimeout(promise, ms, label) {
  const t = (typeof ms === "number" && ms > 0) ? ms : 20000;
  let timer = null;
  try {
    return Promise.race([
      Promise.resolve(promise),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("请求超时(" + Math.round(t / 1000) + "s)" + (label ? ":" + label : "") + "，点重试")), t);
        try { if (timer && typeof timer.unref === "function") timer.unref(); } catch (e) {}
      })
    ]).finally(() => { try { if (timer) clearTimeout(timer); } catch (e) {} });
  } catch (e) {
    return Promise.resolve(promise);
  }
}

// 各配置节归属系统（用于分类）+ 必要/玩法分层
const NECESSARY_SECTIONS = ["总开关配置", "群组开关配置", "网络", "维护配置"];
// 备份配置（含 WebDAV）已迁移至「备份管理」Tab 专属卡片，不在配置页重复渲染
const GAMEPLAY_SECTIONS = ["签到配置","抽奖配置","新手配置","点赞配置","银行配置","娱乐配置","精灵配置","坐骑配置","帮派配置","冒险配置","祈福配置","概率配置","唤醒词配置"];
const SYSTEM_MAP = {
  "设置": "奴隶系统", "费用配置": "奴隶系统", "间隔配置": "奴隶系统",
  "概率配置": "奴隶系统", "祈福配置": "奴隶系统",
  "签到配置": "签到系统", "抽奖配置": "签到系统",
  "新手配置": "签到系统", "点赞配置": "签到系统",
  "银行配置": "银行系统", "娱乐配置": "娱乐系统",
  "精灵配置": "精灵系统",
  "坐骑配置": "坐骑系统", "帮派配置": "帮派系统",
  "超管配置": "超管系统", "冒险配置": "冒险系统",
  "商城图鉴": "商城图鉴", "精灵图鉴": "精灵图鉴",
  "备份配置": "备份", "网络": "网络", "唤醒词配置": "唤醒词",
};
let CUR_SYSTEM = "全部";

