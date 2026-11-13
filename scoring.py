#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数码产品「需求 → 推荐」顾问 —— 多属性加权打分引擎

核心能力：
  1. 需求解析：自然语言需求 → 维度权重（动态）+ 预算硬约束
  2. 多属性加权打分：60 款 × 15 参数 → 四大维度得分 → 加权总分
  3. 可解释拆解：每个维度得分可回溯到具体参数
  4. 反事实对比：预算 +Δ 复用同一打分函数，对比推荐变化

用法：
  python scoring.py                                  # 跑内置样例需求
  python scoring.py "预算5000，主要拍照，偶尔游戏，要轻"   # 命令行传入需求
"""

import csv
import re
import sys

# ======================== 配置区 ========================

DIMENSIONS = ["拍照", "性能", "便携", "续航"]

# 需求关键词 → 维度
KEYWORDS = {
    "拍照": ["拍照", "摄像", "影像", "相机", "摄影", "自拍", "拍视频", "vlog", "Vlog"],
    "性能": ["游戏", "性能", "跑分", "芯片", "流畅", "打游戏", "处理器", "电竞"],
    "便携": ["轻", "薄", "便携", "手感", "小巧", "重量", "单手", "不重"],
    "续航": ["续航", "电池", "充电", "待机", "电量"],
}

# 强度修饰词
STRONG = ["主要", "重点", "最", "很", "特别", "优先", "极致", "就要", "只", "非常", "第一"]
WEAK = ["偶尔", "次要", "不怎么", "无所谓", "不太", "随便", "轻度", "一点"]

# 指标定义：字段名 -> (类型, 维度内权重)
#   类型 max=越大越好  min=越小越好  tele=长焦定性  uw=超广角定性  sensor=传感器底尺寸
METRICS = {
    "拍照": [
        ("主摄传感器(英寸)", "sensor", 1.0),
        ("主摄像素(万)", "pixel", 0.5),
        ("长焦镜头", "tele", 0.8),
        ("超广角镜头", "uw", 0.3),
        ("DxOMark拍照分", "max", 0.6),
    ],
    "性能": [
        ("安兔兔跑分", "max", 1.0),
        ("RAM(GB)", "max", 0.5),
    ],
    "便携": [
        ("重量(g)", "min", 1.0),
        ("厚度(mm)", "min", 0.7),
    ],
    "续航": [
        ("电池容量(mAh)", "max", 1.0),
        ("快充功率(W)", "max", 0.6),
    ],
}


# ======================== 数据清洗 ========================

def to_num(s):
    """从文本提取第一个数字（float），失败返回 None"""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else None


def parse_tele(s):
    """长焦：优先光学变焦倍数；纯数字变焦不算真长焦（缺失给中性分 40）"""
    if not s or not str(s).strip():
        return 40.0
    s = str(s)
    # 优先提取「光学变焦」倍数（兼容 3.5x / 3.5X / 3.7倍 写法）
    m = re.search(r"(\d+(?:\.\d+)?)\s*[xX倍]?\s*光学", s)
    if m:
        x = float(m.group(1))
        return min(100.0, 30 + x * 20)  # 3x→90, 5x→100(封顶)
    # 只有数字变焦（无光学），接近无长焦
    if "数字变焦" in s and "光学" not in s:
        return 35.0
    # 兜底：提取任意「X倍」
    m2 = re.search(r"(\d+(?:\.\d+)?)\s*[xX倍]", s)
    if m2:
        x = float(m2.group(1))
        return min(100.0, 30 + x * 20)
    return 50.0


def pixel_score(n):
    """主摄像素（万）→ 0-100：5000万为甜点（旗舰大底标配），高于5000万视为营销缓降"""
    if n is None:
        return None
    if n <= 5000:
        return round(n / 5000 * 95, 1)  # 0-5000万: 0→95
    return round(max(85.0, 95 - (n - 5000) / 15000 * 10), 1)  # 5000万以上缓降，2亿→85


def parse_uw(s):
    """超广角：有=100，无/空=60（空可能是未抓取，给偏中性分）"""
    if s and str(s).strip():
        return 100.0
    return 60.0


def parse_sensor(s):
    """传感器底尺寸：解析 1/x 英寸，返回底的对角线长度（英寸，越大越好）"""
    if not s or not str(s).strip():
        return None
    m = re.search(r"1/(\d+(?:\.\d+)?)", str(s))
    if m:
        return 1.0 / float(m.group(1))  # 1/1.28 → 0.78；1/2 → 0.5
    return None


def load_products(path="products.csv"):
    """读 products.csv，清洗出可用于打分的结构"""
    products = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            p = {
                "id": r["产品ID"].strip(),
                "brand": r["品牌"].strip(),
                "model": r["型号"].strip(),
                "price": to_num(r["价格(元)"]) or 999999,
            }
            p["raw"] = {k: v for k, v in r.items()}
            products.append(p)
    return products


# ======================== 需求解析 ========================

def parse_budget(text):
    """从需求文本提取预算数字（元）"""
    m = re.search(r"(\d{3,6})\s*元?", text)
    if m:
        return float(m.group(1))
    m = re.search(r"预算\s*(\d+(?:\.\d+)?)\s*[万千kK]", text)
    if m:
        v = float(m.group(1))
        return v * 10000 if ("万" in m.group(0) or "w" in m.group(0).lower() or "W" in m.group(0)) else v * 1000
    return None


def parse_requirements(text):
    """自然语言需求 → {budget, weights(维度权重), hit(命中关键词)}

    修饰词按「关键词上下文」就近判断，而非全局：例如「主要拍照、偶尔游戏」
    → 拍照=strong、性能=weak，而不是全局统一 strong/weak。
    """
    weights = {d: 0.25 for d in DIMENSIONS}
    hit = {d: [] for d in DIMENSIONS}

    for dim, kws in KEYWORDS.items():
        modifier = None  # None / "strong" / "weak"
        for kw in kws:
            idx = text.find(kw)
            if idx < 0:
                continue
            hit[dim].append(kw)
            before = text[max(0, idx - 3):idx]          # 关键词前 3 字
            after = text[idx + len(kw): idx + len(kw) + 3]  # 关键词后 3 字
            if modifier is None and any(w in before for w in STRONG):
                modifier = "strong"
            if modifier is None and any(w in before or w in after for w in WEAK):
                modifier = "weak"

        if modifier == "strong":
            weights[dim] = 0.25 * 2.0
        elif modifier == "weak":
            weights[dim] = 0.25 * 0.5
        elif hit[dim]:
            weights[dim] = 0.25 * 1.5

    # 归一化权重，总和 = 1
    total = sum(weights.values())
    weights = {d: round(w / total, 3) for d, w in weights.items()}

    return {
        "budget": parse_budget(text),
        "weights": weights,
        "hit": hit,
    }


# ======================== 打分 ========================

def _metric_raw(p, field, ftype):
    """取单个指标原始分（0-100，缺失返回 None）"""
    val = p["raw"].get(field, "")
    if ftype == "max":
        n = to_num(val)
        return n
    elif ftype == "min":
        return to_num(val)
    elif ftype == "tele":
        return parse_tele(val)
    elif ftype == "uw":
        return parse_uw(val)
    elif ftype == "sensor":
        return parse_sensor(val)
    elif ftype == "pixel":
        return pixel_score(to_num(val))
    return None


def build_norm(products):
    """对每个数值指标做 min-max 归一化，得到各产品各指标的 0-100 分（缺失为 None）"""
    # 收集每个 max/min 指标的取值分布
    dist = {}  # field -> [values]
    for field, ftype, _w in _all_metrics():
        if ftype in ("max", "min"):
            vals = [to_num(p["raw"].get(field, "")) for p in products]
            vals = [v for v in vals if v is not None]
            dist[field] = (min(vals), max(vals)) if vals else (0, 0)

    norm = {}
    for p in products:
        norm[p["id"]] = {}
        for field, ftype, _w in _all_metrics():
            raw = _metric_raw(p, field, ftype)
            if raw is None:
                norm[p["id"]][field] = None
                continue
            if ftype == "max":
                lo, hi = dist[field]
                s = (raw - lo) / (hi - lo) * 100 if hi > lo else 50
            elif ftype == "min":
                lo, hi = dist[field]
                s = (hi - raw) / (hi - lo) * 100 if hi > lo else 50  # 越小越好
            else:
                s = raw  # tele/uw/sensor 已是 0-100
            norm[p["id"]][field] = round(s, 1)
    return norm


def _all_metrics():
    for dim in DIMENSIONS:
        for field, ftype, w in METRICS[dim]:
            yield field, ftype, w


def calc_dim_score(norm_of_product, dim):
    """维度得分：指标加权平均，缺失指标用「有值指标加权均值」填充（不惩罚缺失）"""
    scores = []
    w_have = 0.0
    for field, ftype, w in METRICS[dim]:
        v = norm_of_product.get(field)
        if v is not None:
            scores.append(v * w)
            w_have += w
    if w_have == 0:
        return 50.0
    avg = sum(scores) / w_have
    w_total = sum(w for _, _, w in METRICS[dim])
    return round((sum(scores) + avg * (w_total - w_have)) / w_total, 1)


def score_products(products, norm, weights, budget):
    """预算过滤 + 加权打分，返回按总分降序的候选列表"""
    cands = [p for p in products if p["price"] <= budget]
    for p in cands:
        p["_dims"] = {}
        for dim in DIMENSIONS:
            p["_dims"][dim] = calc_dim_score(norm[p["id"]], dim)
        p["_total"] = round(sum(weights[d] * p["_dims"][d] for d in DIMENSIONS), 1)
    cands.sort(key=lambda x: x["_total"], reverse=True)
    return cands


# ======================== 可解释输出 ========================

def _fmt_metric(p, field, ftype):
    """指标原始值的人类可读形式"""
    v = p["raw"].get(field, "").strip()
    if not v:
        return "-"
    if field in ("重量(g)", "厚度(mm)", "屏幕尺寸(英寸)"):
        return v
    if field == "安兔兔跑分":
        return v + "万"
    if field in ("主摄像素(万)",):
        return v + "万像素"
    if field in ("电池容量(mAh)",):
        return v + "mAh"
    if field in ("快充功率(W)",):
        return v + "W"
    if field == "长焦镜头":
        m = re.search(r"(\d+(?:\.\d+)?)\s*倍", v)
        return m.group(1) + "x" if m else "有"
    if field == "超广角镜头":
        return "有" if v else "-"
    return v[:20]


def explain(p, norm, weights, rank=None):
    """生成单款推荐的可解释拆解文本"""
    lines = []
    prefix = "{}. ".format(rank + 1) if rank is not None else ""
    lines.append("【{}】{}  总分 {}  (¥{:.0f})".format(p["brand"], p["model"], p["_total"], p["price"]))
    for dim in DIMENSIONS:
        w = weights[dim]
        parts = []
        for field, ftype, _w in METRICS[dim]:
            parts.append("{}={}".format(field.split("(")[0], _fmt_metric(p, field, ftype)))
        lines.append("  · {} {}分 (权重{:.0%})  |  {}".format(dim, p["_dims"][dim], w, "  ".join(parts)))
    return "\n".join(lines)


def recommend(text, top_k=3):
    """主入口：需求文本 → Top-K 推荐"""
    products = load_products()
    norm = build_norm(products)
    req = parse_requirements(text)
    cands = score_products(products, norm, req["weights"], req["budget"])
    return req, cands[:top_k], norm


def counterfactual(text, delta=500):
    """反事实对比：预算 +delta 后推荐变化"""
    products = load_products()
    norm = build_norm(products)
    req = parse_requirements(text)

    base = score_products(products, norm, req["weights"], req["budget"])[:3]
    req2 = dict(req)
    req2["budget"] = req["budget"] + delta
    plus = score_products(products, norm, req2["weights"], req2["budget"])[:3]

    base_ids = [p["id"] for p in base]
    return req, base, plus


# ======================== 演示 ========================

def print_recommend(text):
    req, top, norm = recommend(text, top_k=3)
    print("=" * 70)
    print("需求：{}".format(text))
    print("预算约束：¥{:.0f}   维度权重：{}".format(req["budget"], req["weights"]))
    print("=" * 70)
    for i, p in enumerate(top):
        print(explain(p, norm, req["weights"], rank=i))
        print()


def print_counterfactual(text, delta=500):
    req, base, plus = counterfactual(text, delta)
    print("=" * 70)
    print("反事实对比：预算 {:.0f} → {:.0f}（+{}）".format(req["budget"], req["budget"] + delta, delta))
    print("=" * 70)
    print("【原始预算 ¥{:.0f} 的 Top3】".format(req["budget"]))
    for p in base:
        print("  {}  {}  总分{}  拍照{}分".format(p["brand"], p["model"], p["_total"], p["_dims"]["拍照"]))
    print()
    print("【预算 ¥{:.0f} 的 Top3】".format(req["budget"] + delta))
    for p in plus:
        print("  {}  {}  总分{}  拍照{}分".format(p["brand"], p["model"], p["_total"], p["_dims"]["拍照"]))
    print()
    # 变化分析
    base_ids = set(p["id"] for p in base)
    plus_ids = set(p["id"] for p in plus)
    new_in = [p for p in plus if p["id"] not in base_ids]
    dropped = [p for p in base if p["id"] not in plus_ids]
    if new_in:
        print("多花 ¥{} 新进入榜单：{}".format(delta, "、".join("{}（总分{}，拍照{}）".format(p["model"], p["_total"], p["_dims"]["拍照"]) for p in new_in)))
    if dropped:
        print("被挤出的机型：{}".format("、".join(p["model"] for p in dropped)))
    if not new_in and not dropped:
        print("多花 ¥{} 后 Top3 无变化——当前预算内已有足够好的选择。".format(delta))


def main():
    sample = "预算5000，主要拍照，偶尔游戏，要轻"
    text = sys.argv[1] if len(sys.argv) > 1 else sample
    print_recommend(text)
    print()
    print_counterfactual(text, delta=500)


if __name__ == "__main__":
    main()
