#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG 检索层 —— 评测摘录向量化 + 语义检索

把 search_reviews 从「型号精确匹配」升级为真正的向量 RAG：
  1. 每条评测摘录（维度 + 原文）编码为语义向量
  2. 检索时把查询意图也编码为向量，做余弦相似度召回
  3. 支持「型号精确匹配」与「语义检索」两种模式：
       - product 指定型号 → 精确返回该型号摘录（兼容原能力）
       - 否则 → 语义检索，按意图召回最相关的定性证据

embedding 方案（自动降级）：
  - 优先 DashScope text-embedding-v3（OpenAI 兼容，1024 维）
  - 无 key 时降级为本地字符 bigram TF-IDF（纯 numpy，零外部依赖）

向量缓存：首次构建后落盘 review_vectors.npy / review_vectors.json，
reviews.csv 内容变化时自动重建，避免每次启动重复调用 embedding。

用法：
  from rag import ReviewIndex
  idx = ReviewIndex()
  hits, mode = idx.search("夜景拍照强、机身轻", top_k=5)
"""

import csv
import hashlib
import json
import os
import re

import numpy as np

DIMENSIONS = ["拍照", "性能", "便携", "续航", "屏幕", "自拍", "视频", "系统"]

VEC_CACHE = "review_vectors.npy"
META_CACHE = "review_vectors.json"


def load_reviews(path="reviews.csv"):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ==================== embedding ====================

def _dashscope_embed(texts, batch_size=10, timeout=60):
    """DashScope text-embedding-v3，返回 (n, 1024) float32 矩阵；失败返回 None"""
    import requests
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key or not texts:
        return None
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
    out = []
    try:
        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            r = requests.post(
                url,
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                json={"model": "text-embedding-v3", "input": chunk},
                timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()["data"]
            data.sort(key=lambda x: x["index"])
            out.extend(d["embedding"] for d in data)
        return np.array(out, dtype=np.float32)
    except Exception:
        return None


def _bigrams(s):
    s = re.sub(r"\s+", "", str(s))
    if len(s) < 2:
        return [s] if s else []
    return [s[i:i + 2] for i in range(len(s) - 1)]


def _l2(m):
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return m / n


# ==================== 索引 ====================

class ReviewIndex:
    def __init__(self, path="reviews.csv"):
        self.reviews = load_reviews(path)
        self.texts = ["{}：{}".format(r["维度"], r["摘录原文"]) for r in self.reviews]
        self.vocab = None
        self.idf = None
        self.vectors, self.embedder = self._build_or_load(path)

    # ---------- 构建 / 缓存 ----------
    def _build_or_load(self, path):
        h = hashlib.md5(open(path, "rb").read()).hexdigest()
        if os.path.exists(VEC_CACHE) and os.path.exists(META_CACHE):
            try:
                meta = json.load(open(META_CACHE, encoding="utf-8"))
                if meta.get("hash") == h and meta.get("n") == len(self.reviews):
                    emb = meta.get("embedder", "tfidf")
                    # 缓存是 dashscope 向量但当前无 key → 跳过缓存，重建本地 TF-IDF
                    if emb == "dashscope" and not os.environ.get("DASHSCOPE_API_KEY"):
                        pass
                    else:
                        return np.load(VEC_CACHE), emb
            except Exception:
                pass
        # 重建
        vec = _dashscope_embed(self.texts)
        if vec is not None:
            embedder = "dashscope"
        else:
            embedder = "tfidf"
            self._build_vocab()
            vec = self._tfidf_matrix()
        vec = _l2(vec)
        try:
            np.save(VEC_CACHE, vec)
            json.dump({"hash": h, "n": len(self.reviews), "embedder": embedder},
                      open(META_CACHE, "w", encoding="utf-8"))
        except Exception:
            pass  # 缓存写入失败不影响运行（沙箱只读等场景）
        return vec, embedder

    def _build_vocab(self):
        docs = [_bigrams(t) for t in self.texts]
        vocab = sorted({b for d in docs for b in d})
        self.vocab = {b: i for i, b in enumerate(vocab)}
        n = len(docs)
        X = np.zeros((n, len(vocab)), dtype=np.float32)
        for i, d in enumerate(docs):
            for b in d:
                X[i, self.vocab[b]] += 1
        df = (X > 0).sum(axis=0)
        self.idf = np.log((n + 1) / (df + 1)) + 1

    def _tfidf_matrix(self):
        docs = [_bigrams(t) for t in self.texts]
        X = np.zeros((len(docs), len(self.vocab)), dtype=np.float32)
        for i, d in enumerate(docs):
            for b in d:
                if b in self.vocab:
                    X[i, self.vocab[b]] += 1
        return X * self.idf

    def _embed_query(self, query):
        if self.embedder == "dashscope":
            v = _dashscope_embed([query])
            if v is not None:
                return _l2(v)
        # 降级：同一词表 TF-IDF
        if self.vocab is None:
            self._build_vocab()
        d = _bigrams(query)
        x = np.zeros(len(self.vocab), dtype=np.float32)
        for b in d:
            if b in self.vocab:
                x[self.vocab[b]] += 1
        x = x * self.idf
        return _l2(x.reshape(1, -1))

    # ---------- 检索 ----------
    def search(self, query, dimension="", product="", top_k=5):
        """返回 (hits: list[dict], mode: 'exact'|'semantic')
        hits 每项含 review 字段 + _score（语义模式）"""
        # 1) 型号精确匹配（兼容原能力）
        if product:
            pid = str(product).strip()
            matches = [r for r in self.reviews
                       if r["产品ID"].strip() == pid or r["产品型号"].strip() == pid]
            if matches:
                if dimension:
                    matches = [r for r in matches if r["维度"] == dimension]
                return [dict(r) for r in matches], "exact"

        # 2) 语义检索
        qvec = self._embed_query(query)
        scores = (self.vectors @ qvec.T).ravel()
        order = np.argsort(-scores)

        hits = []
        seen_models = {}
        for i in order:
            r = self.reviews[i]
            if dimension and r["维度"] != dimension:
                continue
            model = r["产品型号"]
            # 多样性约束：同一机型最多保留 2 条
            if seen_models.get(model, 0) >= 2:
                continue
            item = dict(r)
            item["_score"] = float(scores[i])
            hits.append(item)
            seen_models[model] = seen_models.get(model, 0) + 1
            if len(hits) >= top_k:
                break
        return hits, "semantic"


def _fmt_hits(hits, mode):
    if not hits:
        return "（未检索到相关评测摘录）"
    lines = []
    for h in hits:
        line = "· [{}] {}（{}，来源：{}，{}）".format(
            h["维度"], h["摘录原文"], h["产品型号"], h["来源媒体"], h["摘录日期"])
        if mode == "semantic":
            line += "  [相似度 {:.2f}]".format(h.get("_score", 0))
        lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    idx = ReviewIndex()
    print("embedder:", idx.embedder, "| 向量数:", len(idx.vectors), "| 维度:", idx.vectors.shape[1])
    print()
    for q, dim in [("夜景拍照强、机身轻", ""), ("打游戏帧率稳、续航长", ""), ("续航久、电池大", ""), ("自拍好看、人像自然", "")]:
        hits, mode = idx.search(q, dimension=dim, top_k=3)
        print("=== 语义查询：{} ===".format(q))
        print(_fmt_hits(hits, mode))
        print()
