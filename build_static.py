#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成纯静态 HTML 网页（零外部依赖，数据内嵌 + JS 本地打分）。

把 scoring.py 的打分逻辑用 JS 重写，products.csv / reviews.csv 数据内嵌 JSON，
所有图表用 SVG 自绘（不依赖 CDN），保证网络差时也能流畅使用。

用法：python build_static.py  ->  生成「数码产品推荐顾问_网页.html」
"""

import csv
import json

OUT = "数码产品推荐顾问_网页.html"


def load_rows(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    products = load_rows("products.csv")
    reviews = load_rows("reviews.csv")
    products_json = json.dumps(products, ensure_ascii=False).replace("</", "<\\/")
    reviews_json = json.dumps(reviews, ensure_ascii=False).replace("</", "<\\/")

    html = HTML_TEMPLATE.replace("__PRODUCTS_JSON__", products_json) \
                        .replace("__REVIEWS_JSON__", reviews_json)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成：{}（{} 款产品，{} 条评测）".format(OUT, len(products), len(reviews)))


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>数码产品推荐顾问</title>
<style>
  :root {
    --primary: #4f46e5; --primary-2: #7c3aed;
    --red: #e11d48; --blue: #2563eb; --green: #16a34a; --orange: #ea580c;
    --bg: #f1f5f9; --card: #ffffff; --line: #e2e8f0; --text: #0f172a; --muted: #64748b;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
      "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text);
    line-height: 1.6; padding-bottom: 48px;
  }
  .wrap { max-width: 1120px; margin: 0 auto; padding: 20px 16px; }

  /* 顶部 hero */
  .hero {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 55%, #a855f7 100%);
    border-radius: 18px; padding: 34px 26px; color: #fff; text-align: center;
    margin-bottom: 16px; box-shadow: 0 10px 28px rgba(79, 70, 229, .28);
  }
  .hero h1 { font-size: 27px; font-weight: 800; color: #fff; letter-spacing: .5px; }
  .hero p { color: rgba(255,255,255,.88); font-size: 14px; margin-top: 8px; }

  .card { background: var(--card); border: 1px solid var(--line); border-radius: 16px;
    padding: 20px 22px; margin-top: 16px; box-shadow: 0 2px 10px rgba(15,23,42,.06); }
  .card h2 { font-size: 18px; margin-bottom: 14px; padding-bottom: 10px;
    border-bottom: 1px solid var(--line); display: flex; align-items: center; gap: 8px; }
  .card h2 .step { display: inline-flex; align-items: center; justify-content: center;
    width: 26px; height: 26px; border-radius: 8px; background: linear-gradient(135deg,#4f46e5,#7c3aed);
    color: #fff; font-size: 14px; font-weight: 700; flex-shrink: 0; }
  .card-head { display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 10px; margin-bottom: 14px; padding-bottom: 10px;
    border-bottom: 1px solid var(--line); }
  .card-head h2 { margin: 0; padding: 0; border-bottom: none; }
  .hint { font-size: 12px; color: var(--muted); font-weight: normal; }

  /* 输入区 */
  .input-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; }
  .input-row .field { flex: 1 1 240px; }
  .input-row label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; font-weight: 600; }
  .input-row select, .input-row input {
    width: 100%; padding: 11px 13px; border: 1px solid var(--line); border-radius: 10px;
    font-size: 14px; background: #fff; color: var(--text); transition: border-color .15s, box-shadow .15s; }
  .input-row input:focus, .input-row select:focus {
    outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(79,70,229,.12); }

  /* 指标卡 */
  .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
  .metric { position: relative; background: #fff; border: 1px solid var(--line);
    border-radius: 12px; padding: 16px 12px 13px; text-align: center;
    box-shadow: 0 1px 3px rgba(15,23,42,.04); overflow: hidden; }
  .metric::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: var(--ac, var(--primary)); }
  .metric .v { font-size: 24px; font-weight: 800; color: var(--tc, var(--text)); }
  .metric .k { font-size: 12px; color: var(--muted); margin-top: 3px; }

  /* 两栏 */
  .cols { display: grid; grid-template-columns: 1fr 1.4fr; gap: 16px; }
  @media (max-width: 760px) { .cols { grid-template-columns: 1fr; }
    .metrics { grid-template-columns: repeat(2, 1fr); } }
  .sub-label { font-size: 13px; color: var(--muted); margin-bottom: 6px; font-weight: 600; }

  /* 权重条 */
  .wbar-row { display: flex; align-items: center; margin-bottom: 12px; gap: 8px; }
  .wbar-row .dim { width: 34px; font-size: 13px; text-align: right; flex-shrink: 0; font-weight: 600; }
  .wbar-row .track { flex: 1; height: 16px; background: #eef1f5; border-radius: 8px; overflow: hidden; }
  .wbar-row .fill { height: 100%; border-radius: 8px; transition: width .3s; }
  .wbar-row .pct { width: 44px; font-size: 12px; color: var(--muted); font-weight: 600; }

  /* 价格直方图 */
  .hist { display: flex; align-items: flex-end; gap: 4px; height: 150px; padding-top: 12px; }
  .hist .bar { flex: 1; background: linear-gradient(180deg, #e11d48, #fb7185);
    border-radius: 4px 4px 0 0; min-height: 2px; position: relative; opacity: .9; }
  .hist .bar span { position: absolute; top: -18px; left: 50%; transform: translateX(-50%);
    font-size: 11px; color: var(--muted); }

  /* 候选数量选择按钮 */
  .seg { display: flex; align-items: center; gap: 6px; }
  .seg .seg-label { font-size: 12px; color: var(--muted); margin-right: 4px; font-weight: 600; }
  .seg button {
    min-width: 36px; height: 30px; padding: 0 10px; border: 1px solid var(--line);
    border-radius: 8px; background: #fff; color: var(--muted); cursor: pointer;
    font-size: 13px; font-weight: 700; transition: all .15s; font-family: inherit; }
  .seg button:hover { border-color: var(--primary); color: var(--primary); }
  .seg button.on { background: var(--primary); border-color: var(--primary); color: #fff;
    box-shadow: 0 2px 6px rgba(79,70,229,.32); }

  /* 候选卡片 */
  .cand-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(185px, 1fr)); gap: 12px; }
  .cand { border: 2px solid var(--line); border-radius: 14px; padding: 14px; cursor: pointer;
    transition: all .18s ease; background: #fff; text-align: left; font-family: inherit;
    position: relative; }
  .cand:hover { border-color: var(--primary); transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(15,23,42,.08); }
  .cand.sel { border-color: var(--primary); background: #f5f3ff;
    box-shadow: 0 6px 18px rgba(79,70,229,.18); }
  .cand .rank { position: absolute; top: 10px; right: 10px; width: 26px; height: 26px;
    border-radius: 50%; background: #f1f5f9; color: var(--muted);
    display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; }
  .cand.sel .rank { background: var(--primary); color: #fff; }
  .cand .name { font-weight: 700; font-size: 15px; margin: 2px 0 8px; padding-right: 30px; }
  .cand .price { font-size: 19px; font-weight: 800; color: var(--primary); }
  .cand .total { font-size: 13px; color: var(--muted); margin-top: 2px; }
  .cand .best { font-size: 12px; color: var(--green); margin-top: 8px; padding-top: 8px;
    border-top: 1px dashed var(--line); }

  /* 优势区 */
  .adv-summary { background: #f5f3ff; border: 1px solid #e0d9ff; border-left: 4px solid var(--primary);
    border-radius: 10px; padding: 13px 15px; font-size: 14px; margin-bottom: 16px; }
  .dim-line { font-size: 14px; margin-bottom: 10px; }
  .dim-line b { display: inline-block; min-width: 42px; }
  .score-tag { font-weight: 700; padding: 2px 9px; border-radius: 999px; margin: 0 5px; font-size: 13px; }
  blockquote { border-left: 3px solid var(--primary); padding: 6px 12px; margin: 7px 0;
    color: #334155; font-size: 13px; background: #f8fafc; border-radius: 0 8px 8px 0; }
  .src { color: var(--muted); font-size: 12px; }

  .cf-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  @media (max-width: 760px) { .cf-cols { grid-template-columns: 1fr; } }
  .tip { font-size: 14px; padding: 11px 15px; border-radius: 10px; margin-top: 10px; font-weight: 500; }
  .tip.ok { background: #f0fdf4; border: 1px solid #bbf7d0; color: #15803d; }
  .tip.warn { background: #fff7ed; border: 1px solid #fed7aa; color: #c2410c; }
  .empty { color: var(--muted); text-align: center; padding: 40px 0; }
  .svg-box { display: flex; justify-content: center; }
</style>
</head>
<body>
<div class="wrap">

  <div class="hero">
    <h1>📱 数码产品「需求 → 推荐」顾问</h1>
    <p>先看预算 → 挑候选 → 看所选手机的具体优势，每个结论都可回溯到参数或评测原文</p>
  </div>

  <!-- 输入区 -->
  <div class="card">
    <div class="input-row">
      <div class="field" style="flex:1 1 200px;">
        <label>预设场景</label>
        <select id="preset"></select>
      </div>
      <div class="field" style="flex:2 1 320px;">
        <label>需求描述（可自由修改）</label>
        <input id="req" type="text" placeholder="例如：预算5000，主要拍照，偶尔游戏，要轻">
      </div>
    </div>
  </div>

  <!-- ① 价格 -->
  <div class="card">
    <h2><span class="step">1</span>价格</h2>
    <div class="metrics" id="metrics"></div>
    <div class="cols" style="margin-top:16px;">
      <div>
        <div class="sub-label">候选机型价格分布</div>
        <div class="hist" id="hist"></div>
      </div>
      <div>
        <div class="sub-label">你的需求权重</div>
        <div id="wbar"></div>
      </div>
    </div>
  </div>

  <!-- ② 候选手机 -->
  <div class="card">
    <div class="card-head">
      <h2><span class="step">2</span>候选手机 <span class="hint">（点击卡片查看具体优势）</span></h2>
      <div class="seg" id="topn-seg">
        <span class="seg-label">候选数量</span>
        <button class="on" data-n="3">3</button>
        <button data-n="5">5</button>
        <button data-n="8">8</button>
        <button data-n="10">10</button>
      </div>
    </div>
    <div class="svg-box" id="radar_cmp" style="margin-bottom:16px;"></div>
    <div class="cand-grid" id="cands"></div>
  </div>

  <!-- ③ 所选手机优势 -->
  <div class="card">
    <h2><span class="step">3</span>所选手机的具体优势</h2>
    <div id="adv"></div>
  </div>

  <!-- ④ 反事实对比 -->
  <div class="card">
    <h2><span class="step">4</span>反事实对比：预算 +500</h2>
    <div id="cf"></div>
  </div>

</div>

<script>
// ==================== 内嵌数据 ====================
var PRODUCTS = __PRODUCTS_JSON__;
var REVIEWS = __REVIEWS_JSON__;

// ==================== 打分引擎（对照 scoring.py）====================
var DIMENSIONS = ["拍照", "性能", "便携", "续航"];
var DIM_COLORS = { "拍照": "#e11d48", "性能": "#2563eb", "便携": "#16a34a", "续航": "#ea580c" };
var PALETTE = ["#e11d48", "#2563eb", "#16a34a", "#ea580c", "#7c3aed", "#0891b2",
               "#ca8a04", "#db2777", "#059669", "#dc2626"];

var KEYWORDS = {
  "拍照": ["拍照", "摄像", "影像", "相机", "摄影", "自拍", "拍视频", "vlog", "Vlog"],
  "性能": ["游戏", "性能", "跑分", "芯片", "流畅", "打游戏", "处理器", "电竞"],
  "便携": ["轻", "薄", "便携", "手感", "小巧", "重量", "单手", "不重"],
  "续航": ["续航", "电池", "充电", "待机", "电量"]
};
var STRONG = ["主要", "重点", "最", "很", "特别", "优先", "极致", "就要", "只", "非常", "第一"];
var WEAK = ["偶尔", "次要", "不怎么", "无所谓", "不太", "随便", "轻度", "一点"];

var METRICS = {
  "拍照": [
    ["主摄传感器(英寸)", "sensor", 1.0],
    ["主摄像素(万)", "pixel", 0.5],
    ["长焦镜头", "tele", 0.8],
    ["超广角镜头", "uw", 0.3],
    ["DxOMark拍照分", "max", 0.6]
  ],
  "性能": [
    ["安兔兔跑分", "max", 1.0],
    ["RAM(GB)", "max", 0.5]
  ],
  "便携": [
    ["重量(g)", "min", 1.0],
    ["厚度(mm)", "min", 0.7]
  ],
  "续航": [
    ["电池容量(mAh)", "max", 1.0],
    ["快充功率(W)", "max", 0.6]
  ]
};

function toNum(s) {
  if (s === null || s === undefined) return null;
  s = String(s).trim();
  if (!s) return null;
  var m = s.match(/(\d+(?:\.\d+)?)/);
  return m ? parseFloat(m[1]) : null;
}
function parseTele(s) {
  if (!s || !String(s).trim()) return 40.0;
  s = String(s);
  var m = s.match(/(\d+(?:\.\d+)?)\s*[xX倍]?\s*光学/);
  if (m) return Math.min(100, 30 + parseFloat(m[1]) * 20);
  if (s.indexOf("数字变焦") >= 0 && s.indexOf("光学") < 0) return 35.0;
  var m2 = s.match(/(\d+(?:\.\d+)?)\s*[xX倍]/);
  if (m2) return Math.min(100, 30 + parseFloat(m2[1]) * 20);
  return 50.0;
}
function pixelScore(n) {
  if (n === null) return null;
  if (n <= 5000) return Math.round(n / 5000 * 95 * 10) / 10;
  return Math.round(Math.max(85.0, 95 - (n - 5000) / 15000 * 10) * 10) / 10;
}
function parseUw(s) { return (s && String(s).trim()) ? 100.0 : 60.0; }
function parseSensor(s) {
  if (!s || !String(s).trim()) return null;
  var m = String(s).match(/1\/(\d+(?:\.\d+)?)/);
  return m ? 1.0 / parseFloat(m[1]) : null;
}
function metricRaw(p, field, ftype) {
  var val = p[field] || "";
  if (ftype === "max" || ftype === "min") return toNum(val);
  if (ftype === "tele") return parseTele(val);
  if (ftype === "uw") return parseUw(val);
  if (ftype === "sensor") return parseSensor(val);
  if (ftype === "pixel") return pixelScore(toNum(val));
  return null;
}
function allMetrics() {
  var out = [];
  DIMENSIONS.forEach(function (d) { METRICS[d].forEach(function (m) { out.push(m); }); });
  return out;
}
function buildNorm(products) {
  var dist = {};
  allMetrics().forEach(function (m) {
    var field = m[0], ftype = m[1];
    if (ftype === "max" || ftype === "min") {
      var vals = [];
      products.forEach(function (p) { var v = toNum(p[field]); if (v !== null) vals.push(v); });
      dist[field] = vals.length ? [Math.min.apply(null, vals), Math.max.apply(null, vals)] : [0, 0];
    }
  });
  var norm = {};
  products.forEach(function (p) {
    norm[p["产品ID"]] = {};
    allMetrics().forEach(function (m) {
      var field = m[0], ftype = m[1];
      var raw = metricRaw(p, field, ftype);
      var s;
      if (raw === null) { s = null; }
      else if (ftype === "max") {
        var lo = dist[field][0], hi = dist[field][1];
        s = hi > lo ? (raw - lo) / (hi - lo) * 100 : 50;
      } else if (ftype === "min") {
        var lo = dist[field][0], hi = dist[field][1];
        s = hi > lo ? (hi - raw) / (hi - lo) * 100 : 50;
      } else { s = raw; }
      norm[p["产品ID"]][field] = s === null ? null : Math.round(s * 10) / 10;
    });
  });
  return norm;
}
function calcDimScore(np, dim) {
  var scores = [], wHave = 0;
  METRICS[dim].forEach(function (m) {
    var v = np[m[0]];
    if (v !== null && v !== undefined) { scores.push(v * m[2]); wHave += m[2]; }
  });
  if (wHave === 0) return 50.0;
  var avg = scores.reduce(function (a, b) { return a + b; }, 0) / wHave;
  var wTotal = METRICS[dim].reduce(function (a, m) { return a + m[2]; }, 0);
  var r = (scores.reduce(function (a, b) { return a + b; }, 0) + avg * (wTotal - wHave)) / wTotal;
  return Math.round(r * 10) / 10;
}
function scoreProducts(products, norm, weights, budget) {
  var cands = products.filter(function (p) { return p._price <= budget; });
  cands.forEach(function (p) {
    p._dims = {};
    DIMENSIONS.forEach(function (d) { p._dims[d] = calcDimScore(norm[p["产品ID"]], d); });
    var t = 0;
    DIMENSIONS.forEach(function (d) { t += weights[d] * p._dims[d]; });
    p._total = Math.round(t * 10) / 10;
  });
  cands.sort(function (a, b) { return b._total - a._total; });
  return cands;
}
function parseBudget(text) {
  var m = text.match(/(\d{3,6})\s*元?/);
  if (m) return parseFloat(m[1]);
  var m2 = text.match(/预算\s*(\d+(?:\.\d+)?)\s*[万千kK]/);
  if (m2) {
    var v = parseFloat(m2[1]);
    return (m2[0].indexOf("万") >= 0 || /[wW]/.test(m2[0])) ? v * 10000 : v * 1000;
  }
  return null;
}
function parseRequirements(text) {
  var weights = {}, hit = {};
  DIMENSIONS.forEach(function (d) { weights[d] = 0.25; hit[d] = []; });
  DIMENSIONS.forEach(function (dim) {
    var modifier = null;
    KEYWORDS[dim].forEach(function (kw) {
      var idx = text.indexOf(kw);
      if (idx < 0) return;
      hit[dim].push(kw);
      var before = text.substring(Math.max(0, idx - 3), idx);
      var after = text.substring(idx + kw.length, idx + kw.length + 3);
      if (modifier === null && STRONG.some(function (w) { return before.indexOf(w) >= 0; })) modifier = "strong";
      if (modifier === null && WEAK.some(function (w) { return before.indexOf(w) >= 0 || after.indexOf(w) >= 0; })) modifier = "weak";
    });
    if (modifier === "strong") weights[dim] = 0.5;
    else if (modifier === "weak") weights[dim] = 0.125;
    else if (hit[dim].length) weights[dim] = 0.375;
  });
  var total = DIMENSIONS.reduce(function (a, d) { return a + weights[d]; }, 0);
  DIMENSIONS.forEach(function (d) { weights[d] = Math.round(weights[d] / total * 1000) / 1000; });
  return { budget: parseBudget(text), weights: weights, hit: hit };
}

// ==================== 数据预处理 ====================
PRODUCTS.forEach(function (p) { p._price = toNum(p["价格(元)"]) || 999999; });
var NORM = buildNorm(PRODUCTS);

// ==================== 可视化 ====================
function hexRgba(hex, a) {
  var r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  return "rgba(" + r + "," + g + "," + b + "," + a + ")";
}
function radarSVG(seriesList, labels, size) {
  var w = size, h = size, cx = w / 2, cy = h / 2, R = Math.min(w, h) / 2 - 44;
  var dirs = [[0, -1], [1, 0], [0, 1], [-1, 0]]; // 上、右、下、左
  function pt(d, v) { var r = R * v / 100; return [cx + d[0] * r, cy + d[1] * r]; }
  var s = '<svg width="100%" viewBox="0 0 ' + w + ' ' + h + '" style="max-width:' + size + 'px;">';
  var grid = '';
  for (var lv = 1; lv <= 5; lv++) {
    var rr = R * lv / 5;
    var pts = dirs.map(function (d) { return (cx + d[0] * rr).toFixed(1) + ',' + (cy + d[1] * rr).toFixed(1); }).join(' ');
    grid += '<polygon points="' + pts + '" fill="none" stroke="#e2e8f0" stroke-width="1"/>';
  }
  dirs.forEach(function (d) {
    grid += '<line x1="' + cx + '" y1="' + cy + '" x2="' + (cx + d[0] * R) + '" y2="' + (cy + d[1] * R) + '" stroke="#e2e8f0" stroke-width="1"/>';
  });
  s += grid;
  seriesList.forEach(function (sr) {
    var pts = sr.values.map(function (v, i) { var p = pt(dirs[i], v); return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' ');
    s += '<polygon points="' + pts + '" fill="' + (sr.fill || hexRgba(sr.color, 0.12)) + '" stroke="' + sr.color + '" stroke-width="2"/>';
    sr.values.forEach(function (v, i) { var p = pt(dirs[i], v); s += '<circle cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="3" fill="' + sr.color + '"/>'; });
  });
  var lp = [
    [cx, cy - R - 16, 'middle'], [cx + R + 20, cy, 'start'],
    [cx, cy + R + 22, 'middle'], [cx - R - 20, cy, 'end']
  ];
  labels.forEach(function (lb, i) {
    s += '<text x="' + lp[i][0] + '" y="' + lp[i][1] + '" text-anchor="' + lp[i][2] +
      '" font-size="12" fill="#64748b" dominant-baseline="middle">' + lb + '</text>';
  });
  s += '</svg>';
  return s;
}

function renderWeightBar(weights) {
  var html = '';
  DIMENSIONS.forEach(function (d) {
    var pct = Math.round(weights[d] * 100);
    html += '<div class="wbar-row"><span class="dim">' + d + '</span>' +
      '<div class="track"><div class="fill" style="width:' + pct + '%;background:' + DIM_COLORS[d] + ';"></div></div>' +
      '<span class="pct">' + pct + '%</span></div>';
  });
  return html;
}
function renderHist(prices) {
  var min = Math.min.apply(null, prices), max = Math.max.apply(null, prices);
  var range = max - min || 1;
  var bins = new Array(8).fill(0);
  prices.forEach(function (pp) { bins[Math.min(7, Math.floor((pp - min) / range * 8))]++; });
  var maxC = Math.max.apply(null, bins) || 1;
  var html = '';
  bins.forEach(function (c) {
    var hh = Math.max(3, c / maxC * 120);
    html += '<div class="bar" style="height:' + hh + 'px;" title="' + c + ' 款">' +
      (c ? '<span>' + c + '</span>' : '') + '</div>';
  });
  return html;
}

// ==================== 评测检索 ====================
function searchReviews(model, id) {
  return REVIEWS.filter(function (r) {
    return r["产品型号"] === model || r["产品ID"] === id;
  });
}

// ==================== 格式化 ====================
function fmtParam(p, field) {
  var v = (p[field] || "").toString().trim();
  if (!v) return "-";
  if (field === "安兔兔跑分") return v + "万";
  if (field === "主摄像素(万)") return v + "万像素";
  if (field === "电池容量(mAh)") return v + "mAh";
  if (field === "快充功率(W)") return v + "W";
  if (field === "重量(g)") return v + "g";
  if (field === "厚度(mm)") return v + "mm";
  if (field === "屏幕尺寸(英寸)") return v + "英寸";
  if (field === "价格(元)") return "¥" + v;
  return v;
}

// ==================== 渲染 ====================
var PRESETS = {
  "经典：5000 拍照轻薄": "预算5000，主要拍照，偶尔游戏，要轻",
  "游戏 + 续航": "预算3000，主要打游戏，续航要好",
  "高端影像": "预算8000，主要拍照，拍视频",
  "极致轻薄": "预算4500，主要轻薄，手感要好",
  "极致续航": "预算2800，主要续航，充电快",
  "旗舰全能": "预算12000，旗舰，拍照性能都要",
  "自拍优先": "预算3500，主要自拍，拍照",
  "视频 vlog": "预算5500，主要拍视频，vlog",
  "极致拍照长焦": "预算10000，极致拍照，长焦",
  "千元耐用": "预算1999，最便宜，能打电话就行"
};

var state = { selectedId: null, topN: 3, req: null, cands: [] };

function esc(s) { return String(s).replace(/[&<>"']/g, function (c) {
  return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

function coreAdvantage(p) {
  var ranked = DIMENSIONS.slice().sort(function (a, b) { return p._dims[b] - p._dims[a]; });
  var parts = ranked.slice(0, 2).map(function (d) {
    var items = METRICS[d].map(function (m) {
      return m[0].split("(")[0] + " " + fmtParam(p, m[0]);
    }).join("、");
    return "<b>" + d + " " + p._dims[d] + " 分</b>（" + items + "）";
  });
  return parts.join(" · ");
}

function render() {
  var text = document.getElementById("req").value;
  if (!text.trim()) {
    document.getElementById("metrics").innerHTML = '<div class="empty">请输入需求，或选择预设场景</div>';
    document.getElementById("hist").innerHTML = ""; document.getElementById("wbar").innerHTML = "";
    document.getElementById("radar_cmp").innerHTML = ""; document.getElementById("cands").innerHTML = "";
    document.getElementById("adv").innerHTML = ""; document.getElementById("cf").innerHTML = "";
    return;
  }
  var req = parseRequirements(text);
  if (!req.budget) { req.budget = 5000; }
  var cands = scoreProducts(PRODUCTS, NORM, req.weights, req.budget);
  if (!cands.length) {
    document.getElementById("cands").innerHTML = '<div class="empty">该预算下暂无候选机型，请调高预算</div>';
    document.getElementById("metrics").innerHTML = "";
    document.getElementById("adv").innerHTML = ""; document.getElementById("cf").innerHTML = "";
    document.getElementById("radar_cmp").innerHTML = ""; document.getElementById("hist").innerHTML = "";
    document.getElementById("wbar").innerHTML = "";
    return;
  }
  var top3 = cands.slice(0, 3);
  var shown = cands.slice(0, Math.max(1, state.topN || 3));
  state.req = req; state.cands = cands; state.top = shown;

  // 选中状态
  var validIds = {};
  shown.forEach(function (p) { validIds[p["产品ID"]] = true; });
  if (!state.selectedId || !validIds[state.selectedId]) state.selectedId = shown[0]["产品ID"];

  // ① 价格
  var priceMin = cands[cands.length - 1]._price, priceMax = cands[0]._price;
  document.getElementById("metrics").innerHTML =
    '<div class="metric" style="--ac:#4f46e5;--tc:#4f46e5;"><div class="v">¥' + Math.round(req.budget) + '</div><div class="k">你的预算</div></div>' +
    '<div class="metric" style="--ac:#2563eb;--tc:#2563eb;"><div class="v">' + cands.length + ' 款</div><div class="k">预算内候选</div></div>' +
    '<div class="metric" style="--ac:#16a34a;--tc:#16a34a;"><div class="v">¥' + Math.round(priceMin) + '</div><div class="k">最低价</div></div>' +
    '<div class="metric" style="--ac:#e11d48;--tc:#e11d48;"><div class="v">¥' + Math.round(priceMax) + '</div><div class="k">最高价</div></div>';
  document.getElementById("hist").innerHTML = renderHist(cands.map(function (p) { return p._price; }));
  document.getElementById("wbar").innerHTML = renderWeightBar(req.weights);

  // ② 候选手机
  var cmpCount = Math.min(6, shown.length);
  var cmpSeries = shown.slice(0, cmpCount).map(function (p, i) {
    return { color: PALETTE[i % PALETTE.length], values: DIMENSIONS.map(function (d) { return p._dims[d]; }) };
  });
  document.getElementById("radar_cmp").innerHTML = radarSVG(cmpSeries, DIMENSIONS, 420);

  var cards = '';
  shown.forEach(function (p, i) {
    var sel = p["产品ID"] === state.selectedId;
    var best = DIMENSIONS.slice().sort(function (a, b) { return p._dims[b] - p._dims[a]; })[0];
    cards += '<button class="cand' + (sel ? ' sel' : '') + '" onclick="select(\'' + p["产品ID"] + '\')">' +
      '<div class="rank">' + (i + 1) + '</div>' +
      '<div class="name">' + esc(p["品牌"] + " " + p["型号"]) + '</div>' +
      '<div class="price">¥' + Math.round(p._price) + '</div>' +
      '<div class="total">总分 ' + p._total + '</div>' +
      '<div class="best">优势：' + best + ' ' + p._dims[best] + ' 分</div></button>';
  });
  document.getElementById("cands").innerHTML = cards;

  // ③ 所选手机优势
  var sel = null;
  shown.forEach(function (p) { if (p["产品ID"] === state.selectedId) sel = p; });
  if (sel) {
    var advHtml = '<div class="adv-summary">🏆 <b>核心优势</b>：' + coreAdvantage(sel) + '</div>';
    advHtml += '<div class="cols">';
    advHtml += '<div><div class="sub-label">' +
      esc(sel["品牌"] + " " + sel["型号"]) + ' — 四维度得分</div>' +
      '<div class="svg-box">' + radarSVG([{ color: "#4f46e5", fill: "rgba(79,70,229,.15)", values: DIMENSIONS.map(function (d) { return sel._dims[d]; }) }], DIMENSIONS, 360) + '</div></div>';
    advHtml += '<div><div class="sub-label">逐维度优势拆解（得分 ← 参数）</div>';
    DIMENSIONS.forEach(function (d) {
      var items = METRICS[d].map(function (m) { return m[0].split("(")[0] + "=" + fmtParam(sel, m[0]); }).join("　");
      advHtml += '<div class="dim-line"><b>' + d + '</b>' +
        '<span class="score-tag" style="background:' + hexRgba(DIM_COLORS[d], 0.14) + ';color:' + DIM_COLORS[d] + ';">' +
        sel._dims[d] + ' 分</span><span style="color:var(--muted);font-size:12px;">权重 ' + Math.round(req.weights[d] * 100) + '%</span>　' +
        '<span style="font-size:12px;">' + items + '</span></div>';
    });
    advHtml += '<div class="sub-label" style="margin:12px 0 6px;">评测原文佐证</div>';
    var hits = searchReviews(sel["型号"], sel["产品ID"]);
    if (hits.length) {
      var byDim = {};
      hits.forEach(function (h) { (byDim[h["维度"]] = byDim[h["维度"]] || []).push(h); });
      DIMENSIONS.forEach(function (d) {
        if (byDim[d]) {
          advHtml += '<div style="font-size:13px;font-weight:600;margin-top:4px;">' + d + '</div>';
          byDim[d].forEach(function (h) {
            advHtml += '<blockquote>「' + esc(h["摘录原文"]) + '」<div class="src">—— 来源：' + esc(h["来源媒体"]) + '</div></blockquote>';
          });
        }
      });
    } else {
      advHtml += '<div class="src">暂无该机型的评测收录</div>';
    }
    advHtml += '</div></div>';
    document.getElementById("adv").innerHTML = advHtml;
  }

  // ④ 反事实对比（固定对比 Top-3）
  var plus = scoreProducts(PRODUCTS, NORM, req.weights, req.budget + 500).slice(0, 3);
  var baseIds = {}, plusIds = {};
  top3.forEach(function (p) { baseIds[p["产品ID"]] = true; });
  plus.forEach(function (p) { plusIds[p["产品ID"]] = true; });
  var newIn = plus.filter(function (p) { return !baseIds[p["产品ID"]]; });
  var dropped = top3.filter(function (p) { return !plusIds[p["产品ID"]]; });

  var cfHtml = '<div class="cf-cols"><div><div class="sub-label">原始预算 ¥' +
    Math.round(req.budget) + ' 的 Top-3</div>' +
    top3.map(function (p) { return '<div class="dim-line">' + esc(p["品牌"] + " " + p["型号"]) + '（总分 ' + p._total + '）</div>'; }).join('') + '</div>';
  cfHtml += '<div><div class="sub-label">预算 ¥' +
    Math.round(req.budget + 500) + ' 的 Top-3</div>' +
    plus.map(function (p) { return '<div class="dim-line">' + esc(p["品牌"] + " " + p["型号"]) + '（总分 ' + p._total + '）</div>'; }).join('') + '</div></div>';
  if (newIn.length) {
    cfHtml += '<div class="tip warn">→ 新进入：' + newIn.map(function (p) { return esc(p["型号"]) + '（¥' + Math.round(p._price) + '，总分 ' + p._total + '）'; }).join('、') + '</div>';
  }
  if (dropped.length) {
    cfHtml += '<div class="tip warn">→ 被挤出：' + dropped.map(function (p) { return esc(p["型号"]); }).join('、') + '</div>';
  }
  if (!newIn.length && !dropped.length) {
    cfHtml += '<div class="tip ok">多花 ¥500 后 Top-3 无变化——当前预算内已是最优选择，不建议加预算。</div>';
  }
  document.getElementById("cf").innerHTML = cfHtml;
}

function select(id) { state.selectedId = id; render(); }
function setTopN(n) {
  state.topN = n;
  document.querySelectorAll("#topn-seg button").forEach(function (b) {
    if (parseInt(b.getAttribute("data-n"), 10) === n) b.classList.add("on");
    else b.classList.remove("on");
  });
  render();
}

// ==================== 初始化 ====================
(function init() {
  var sel = document.getElementById("preset");
  Object.keys(PRESETS).forEach(function (k) {
    var o = document.createElement("option"); o.value = PRESETS[k]; o.textContent = k; sel.appendChild(o);
  });
  document.getElementById("req").value = PRESETS[Object.keys(PRESETS)[0]];
  sel.addEventListener("change", function () { document.getElementById("req").value = sel.value; render(); });
  document.getElementById("req").addEventListener("input", render);
  document.querySelectorAll("#topn-seg button").forEach(function (b) {
    b.addEventListener("click", function () { setTopN(parseInt(b.getAttribute("data-n"), 10)); });
  });
  render();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
