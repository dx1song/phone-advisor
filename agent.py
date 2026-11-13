#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数码产品「需求 → 推荐」顾问 —— LangChain 双工具编排

两个工具：
  1. query_products  参数查询：多属性加权打分 → Top-3 + 分维度拆解 + 反事实对比
  2. search_reviews  评测检索：从评测库检索定性评价原文 + 来源（RAG）

LLM：DeepSeek（OpenAI 兼容），无 key 时自动降级为「确定性编排」保证可跑。

用法：
  python agent.py "预算5000，主要拍照，偶尔游戏，要轻"
"""

import os
import sys

from scoring import recommend, counterfactual, explain, load_products, build_norm

from rag import ReviewIndex

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

import csv

# ==================== 评测摘录库（RAG 数据源） ====================

REVIEWS = []
with open("reviews.csv", encoding="utf-8-sig") as _f:
    REVIEWS = list(csv.DictReader(_f))

# 向量索引：DashScope text-embedding-v3 语义向量（缓存落盘，reviews 变化自动重建）
_INDEX = ReviewIndex()


def _fmt_reviews(rows):
    """把评测摘录格式化为可读文本（含维度、原文、产品、来源、可选相似度）"""
    if not rows:
        return "（无该机型的评测摘录）"
    lines = []
    for r in rows:
        line = "· [{}] {}（{}，来源：{}，{}）".format(
            r["维度"], r["摘录原文"], r.get("产品型号", ""), r["来源媒体"], r["摘录日期"])
        if r.get("_score") is not None:
            line += "  [相似度 {:.2f}]".format(r["_score"])
        lines.append(line)
    return "\n".join(lines)


# ==================== 工具1：参数查询 ====================

@tool
def query_products(requirement: str) -> str:
    """根据用户需求（含预算、拍照/游戏/轻便/续航等偏好），对 60 款手机参数库做多属性加权打分。
    返回：Top-3 推荐、每款的分维度得分拆解，以及「预算 +500」的反事实对比。
    输入：一句自然语言需求，如「预算5000，主要拍照，偶尔游戏，要轻」。
    在生成最终推荐前，必须先调用本工具获取打分结果。"""
    try:
        req, top, norm = recommend(requirement, top_k=3)
        lines = []
        lines.append("需求解析：预算约束 ¥{:.0f}，维度权重 {}".format(req["budget"], req["weights"]))
        lines.append("")
        lines.append("【Top-3 推荐（按总分降序）】")
        for i, p in enumerate(top):
            lines.append(explain(p, norm, req["weights"], rank=i))
        lines.append("")

        # 反事实：预算 +500
        _, base, plus = counterfactual(requirement, 500)
        lines.append("【反事实对比：预算 ¥{:.0f} → ¥{:.0f}】".format(req["budget"], req["budget"] + 500))
        base_ids = [p["id"] for p in base]
        plus_ids = [p["id"] for p in plus]
        new_in = [p for p in plus if p["id"] not in base_ids]
        dropped = [p for p in base if p["id"] not in plus_ids]
        if new_in:
            for p in new_in:
                lines.append("· 新进入：{}（¥{:.0f}，总分 {}，拍照 {}）".format(
                    p["model"], p["price"], p["_total"], p["_dims"]["拍照"]))
        if dropped:
            lines.append("· 被挤出：{}".format("、".join(p["model"] for p in dropped)))
        if not new_in and not dropped:
            lines.append("· Top-3 无变化（当前预算内已是最优选择）")
        return "\n".join(lines)
    except Exception as e:
        return "参数查询出错：{}".format(e)


# ==================== 工具2：评测检索 ====================

@tool
def search_reviews(query: str, product: str = "", dimension: str = "") -> str:
    """语义检索评测摘录，返回关于拍照、性能、便携、续航、屏幕、自拍、视频等维度的定性评价原文及来源媒体。
    用于给推荐结果提供「引用评测原文佐证」。
    参数：
      query=检索意图，可以是产品型号（如「一加 15」），也可以是描述性需求（如「夜景拍照强、机身轻」）。
      product=可选，指定产品型号时精确返回该型号的评测（型号名或产品ID）。
      dimension=可选，维度过滤（拍照/性能/便携/续航/屏幕/自拍/视频/系统）。"""
    hits, mode = _INDEX.search(query, dimension=dimension, product=product, top_k=5)
    if mode == "exact":
        if not hits:
            return "未找到「{}」的评测摘录（评测库当前覆盖 21 款机型）。".format(product or query)
        return "「{}」的评测摘录：\n{}".format(product or query, _fmt_reviews(hits))
    if not hits:
        return "未检索到与「{}」相关的评测摘录。".format(query)
    return "与「{}」语义相关的评测摘录：\n{}".format(query, _fmt_reviews(hits))


# ==================== LLM 接入 ====================

def get_llm():
    """优先 DeepSeek，其次 DashScope（通义），均 OpenAI 兼容"""
    if os.environ.get("DEEPSEEK_API_KEY"):
        return ChatOpenAI(
            model="deepseek-chat",
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
            temperature=0.3,
        )
    if os.environ.get("DASHSCOPE_API_KEY"):
        return ChatOpenAI(
            model="qwen-plus",
            api_key=os.environ["DASHSCOPE_API_KEY"],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0.3,
        )
    return None


SYSTEM_PROMPT = """你是一位数码产品推荐顾问，擅长给出可解释、可验证的推荐。你有两个工具：

1. query_products(requirement)：查询 60 款手机参数库做多属性加权打分，返回 Top-3 推荐、每款的分维度得分拆解，以及「预算 +500」的反事实对比。

2. search_reviews(query, product, dimension)：语义检索评测摘录。传 product 可精确查某款机型的评测；传 query 描述性需求（如「夜景拍照强、机身轻」）可做语义召回，返回定性评价的原文引用及来源媒体。

推荐流程（务必按顺序）：
1. 先调用 query_products 获取该需求的 Top-3 推荐和打分拆解。
2. 对 Top-3 中每一款，调用 search_reviews(product=<该款型号>) 检索该款评测原文作为佐证；若某款无评测收录，可用 search_reviews(query=<该需求的核心诉求>) 语义召回相近机型的证据，并如实说明。
3. 综合打分与评测证据，输出最终推荐。

最终输出要求：
- 3 款推荐，每款给出分维度得分拆解（拍照/性能/便携/续航），并引用 search_reviews 返回的评测原文（注明来源媒体）佐证结论。
- 给出「预算 +500」的反事实对比，说明多花的钱换来了什么。
- 若某款没有评测摘录，如实说明「暂无收录的评测原文」，不要编造。
- 语言简洁，面向普通消费者。"""


def run_agent(requirement):
    """LLM Agent 编排（langgraph react agent）"""
    llm = get_llm()
    if llm is None:
        return None
    tools = [query_products, search_reviews]
    agent = create_agent(llm, tools, system_prompt=SYSTEM_PROMPT)
    result = agent.invoke({"messages": [("user", requirement)]})
    messages = result["messages"]
    for m in reversed(messages):
        if getattr(m, "type", "") == "ai" and getattr(m, "content", ""):
            return m.content
    return "（未生成回答）"


def run_deterministic(requirement):
    """无 LLM 时的确定性编排：直接串起两个工具，拼出完整链路（保证可跑）"""
    out = []
    out.append("=" * 66)
    out.append("需求：{}".format(requirement))
    out.append("=" * 66)
    out.append("")
    # 工具1：参数查询
    q = query_products.invoke({"requirement": requirement})
    out.append("【工具1 · query_products 参数查询】")
    out.append(q)
    out.append("")
    # 工具2：对 Top-3 每款检索评测
    req, top, norm = recommend(requirement, top_k=3)
    out.append("【工具2 · search_reviews 评测检索】")
    for p in top:
        out.append("—— {} 的评测证据 ——".format(p["model"]))
        r = search_reviews.invoke({"query": p["model"], "product": p["model"], "dimension": ""})
        out.append(r)
        out.append("")
    return "\n".join(out)


def main():
    requirement = sys.argv[1] if len(sys.argv) > 1 else "预算5000，主要拍照，偶尔游戏，要轻"
    llm = get_llm()
    if llm:
        print("（使用 LLM 编排：{}）".format("DeepSeek" if os.environ.get("DEEPSEEK_API_KEY") else "通义千问"))
        try:
            text = run_agent(requirement)
            print(text)
            return
        except Exception as e:
            print("LLM 调用失败，降级为确定性编排：{}\n".format(e))
    else:
        print("（未检测到 LLM API key，使用确定性编排）")
    print(run_deterministic(requirement))


if __name__ == "__main__":
    main()
