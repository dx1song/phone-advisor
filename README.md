# 数码产品「需求 → 推荐」顾问

输入一句需求（如「预算5000，主要拍照，偶尔游戏，要轻」），输出推荐机型 + 打分拆解 + 评测佐证 + 反事实对比。

## 一、网页版（推荐，零依赖）

直接双击打开 **`数码产品推荐顾问_网页.html`** 即可使用，无需安装任何环境、无需联网。

- 60 款手机参数 + 100 条评测摘录全部内嵌在页面里
- 打分在浏览器本地完成，网络再差也不卡
- 支持「候选数量」切换（3 / 5 / 8 / 10 款）
- 页面结构：① 价格 → ② 候选手机 → ③ 所选手机优势 → ④ 反事实对比

## 二、后端命令行（可选）

后端功能（打分引擎 / RAG 检索 / LLM 编排）需要 Python 3.9+：

```bash
pip install -r requirements.txt
```

```bash
# 打分引擎（纯标准库，装不装依赖都能跑）
python scoring.py "预算5000，主要拍照，偶尔游戏，要轻"

# LLM 双工具编排（需 langchain，可选配 DEEPSEEK_API_KEY / DASHSCOPE_API_KEY）
python agent.py "预算8000，主要拍照，拍视频"
```

> 说明：`agent.py` 无 LLM key 时自动降级为「确定性编排」，仍能输出完整推荐链路。

## 文件说明

| 文件 | 作用 |
|---|---|
| 数码产品推荐顾问_网页.html | 网页主入口（静态版，替代原 Streamlit 页面） |
| scoring.py | 多属性加权打分引擎 |
| rag.py | 评测摘录向量检索（RAG） |
| agent.py | LLM 双工具编排 |
| build_static.py | 重新生成静态网页的脚本（改数据后重跑） |
| products.csv | 60 款手机参数库 |
| reviews.csv | 100 条评测摘录 |

## 重新生成网页

若修改了 `products.csv` / `reviews.csv`，可重新生成静态网页：

```bash
python build_static.py
```
