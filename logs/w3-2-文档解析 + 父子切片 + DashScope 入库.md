两个依赖

uv add dashscope

uv add langchain-text-splitters

uv run python -c "import dashscope, langchain\_text\_splitters; print('ok', dashscope.\_\_version\_\_)"

为什么是 dashscope 而不是 langchain-community：你老项目那份 阿里云向量化.py 第 1 行自己写了「langchain-community 不再被官方维护，也不再推荐使用」。官方 SDK 更薄、更稳，也不用为了一个 embedding 拖进整个 community 包。



为什么是 langchain-text-splitters：方案 7.3 指定 RecursiveCharacterTextSplitter，它现在独立成包了，不再跟 langchain 主包走。轻量，纯文本处理。



api返回长这样：
resp.output = {

&#x20;   "embeddings": \[

&#x20;       {"text\_index": 0, "embedding": \[1024 个 float]},

&#x20;       {"text\_index": 2, "embedding": \[...]},

&#x20;       {"text\_index": 1, "embedding": \[...]},

&#x20;   ]

}

\*\*注意：\*\*返回数组的顺序\*\*不等于\*\*你传进去的顺序\*\*。\*\*





我的老代码也太简单了，不过community不维护了还是不用好了：



from langchain\_community.embeddings import DashScopeEmbeddings

embeddings = DashScopeEmbeddings(model="text-embedding-v4")



vector = embeddings.embed\_query(text)          # 单条 → list\[float]

vectors = embeddings.embed\_documents(texts)    # 批量 → list\[list\[float]]









\# `parent\\\\\\\_chunks` 表：\*\*为什么父块要回 Postgres\*\*



\*\*你的疑惑正是这里：既然 Milvus 里已经有 `raw\\\\\\\_content` 存父块全文了，为什么还要一张 Postgres 表？\*\*



\## 因为 `raw\\\\\\\_content` 是\*\*副本\*\*，`parent\\\\\\\_chunks` 才是\*\*权威\*\*



\*\*三个必须回 Postgres 的理由：\*\*



\### ① `VARCHAR(4096)` 存不下长章节



\*\*Milvus 的 `raw\\\\\\\_content` 是 `VARCHAR(4096)`。\*\*



\*\*一份技术文档的一整章可能有 8000 字。\*\* 超了怎么办：



\*\*插入直接报错，不截断\*\* —— 你没法「悄悄塞进去」。



\*\*所以必须有个\*\*无长度上限\*\*的地方存完整父块：Postgres 的 `Text` 类型（实际能存 1GB）。\*\*



\*\*这时候 Milvus 的 `raw\\\\\\\_content` 就只能截断（存前 4096 字），完整版以 `parent\\\\\\\_chunks.content` 为准。\*\*



\### ② 删文档要能列出「有哪些父块」



\*\*用户点「删除这篇文档」，你要：\*\*



1\. \*\*删 `documents` 这一行\*\*

2\. \*\*找到这篇文档的所有父块\*\* → 才能知道要去 Milvus 删哪些 `parent\\\\\\\_id` 下的子块

\*\*Postgres 里一句 SQL：\*\*



```

SELECT id FROM parent\\\\\\\_chunks WHERE doc\\\\\\\_id = 'a3f8...'

```



\*\*这一步必须在关系库里做。Milvus 没法「按 doc\_id 列出所有 parent\_id」—— 它能搜相似，不能做关系查询。\*\*





\### ③ 不依赖 Milvus 也能展示文档结构



\*\*前端想画一个「文档目录树」，用户点某一章看原文。\*\*



\*\*这只用到 `parent\\\\\\\_chunks`（`section\\\\\\\_path` + `content`），完全不需要 Milvus。\*\*



\*\*Milvus 挂了，浏览功能还得能用。\*\*





三张表、一个 Milvus 集合的完整关系：
users

&#x20; │

&#x20; └─ documents（一行一个上传物）

&#x20;      │  id = UUID

&#x20;      │  content\_hash = sha256（幂等去重）

&#x20;      │

&#x20;      ├─ parent\_chunks（一行 = 一个章节，权威全文）

&#x20;      │    id = sha1(doc\_id + section\_path + seq)\[:16]

&#x20;      │    content = 完整章节（无长度上限）

&#x20;      │

&#x20;      └─ Milvus child\_chunks\_v1（一行 = 一个子块）

&#x20;           child\_id = ...

&#x20;           parent\_id → parent\_chunks.id

&#x20;           content = 子块 200 字（用来搜）

&#x20;           raw\_content = 父块 1500 字（副本，可能截断）

&#x20;           dense / sparse = 向量





\*\*一次检索的数据流：\*\*



1\. \*\*问题 embed → 向量\*\*

2\. \*\*Milvus 混合检索 → 命中 3 个子块\*\*

3\. \*\*按 `parent\\\\\\\_id` 去重 → 得到 1 个父块\*\*

4\. \*\*取 Milvus 的 `raw\\\\\\\_content`（正常情况够用）\*\*

5\. \*\*如果 `raw\\\\\\\_content` 被截断（`char\\\\\\\_count > 4096`），回 Postgres 查 `parent\\\\\\\_chunks.content` 拿完整版\*\*

6\. \*\*拼进 prompt\*\*



\*\*第 5 步就是 `parent\\\\\\\_chunks` 存在的现实价值。\*\*













\# 一次完整请求长什么样（流程）



\## ① 上传文档



```

POST /api/v1/knowledge/documents

Content-Type: multipart/form-data

```



\*\*服务端返回（`DocumentOut`）：\*\*



```

{

\\\&#x20; "id": "a3f8c2d1-...",

\\\&#x20; "filename": "茅台2023年报.pdf",

\\\&#x20; "mime\\\\\\\_type": "application/pdf",

\\\&#x20; "size\\\\\\\_bytes": 8762,

\\\&#x20; "status": "uploaded",

\\\&#x20; "version": 1,

\\\&#x20; "page\\\\\\\_count": null,

\\\&#x20; "char\\\\\\\_count": null,

\\\&#x20; "is\\\\\\\_indexed": false,

\\\&#x20; "parser": null,

\\\&#x20; "error\\\\\\\_message": null,

\\\&#x20; "created\\\\\\\_at": "2026-11-19T11:00:00Z"

}

```



\*\*注意 `page\\\\\\\_count` / `char\\\\\\\_count` 是 `null`\*\* —— 因为还没解析。



\*\*10 秒后再查，同样的 `DocumentOut`，但：\*\*



```

{

\\\&#x20; "status": "indexed",

\\\&#x20; "page\\\\\\\_count": 12,

\\\&#x20; "char\\\\\\\_count": 8762,

\\\&#x20; "is\\\\\\\_indexed": true,

\\\&#x20; "parser": "pypdf"

}

```



\*\*同一个 schema，前后两次返回的内容不同 —— 这就是「状态机 + 轮询」的典型交互。\*\*



\## ② 检索



\*\*请求体（`SearchIn`）：\*\*



```

{

\\\&#x20; "query": "高粱占成本多少",

\\\&#x20; "top\\\\\\\_k": 20,

\\\&#x20; "doc\\\\\\\_ids": \\\\\\\["a3f8c2d1-..."]

}

```



\*\*响应体（`SearchOut`）：\*\*



```

{

\\\&#x20; "query": "高粱占成本多少",

\\\&#x20; "hits": \\\\\\\[

\\\&#x20;   {

\\\&#x20;     "child\\\\\\\_id": "doc1\\\\\\\_sec32\\\\\\\_c2",

\\\&#x20;     "doc\\\\\\\_id": "a3f8c2d1-...",

\\\&#x20;     "parent\\\\\\\_id": "9f2e3a...",

\\\&#x20;     "section\\\\\\\_path": "第3章 > 3.2 成本结构",

\\\&#x20;     "raw\\\\\\\_content": "茅台酒成本主要由……（完整 1500 字）",

\\\&#x20;     "score": 0.0328

\\\&#x20;   },

\\\&#x20;   {

\\\&#x20;     "child\\\\\\\_id": "doc1\\\\\\\_sec31\\\\\\\_c1",

\\\&#x20;     "doc\\\\\\\_id": "a3f8c2d1-...",

\\\&#x20;     "parent\\\\\\\_id": "7c1b9d...",

\\\&#x20;     "section\\\\\\\_path": "第3章 > 3.1 营收构成",

\\\&#x20;     "raw\\\\\\\_content": "……",

\\\&#x20;     "score": 0.0164

\\\&#x20;   }

\\\&#x20; ]

}

```



\*\*注意 `hits` 长度是 2，不是 20 —— 呼应用第五节「召回 20、返回 2（去重后）」。\*\*



\*\*前端拿到 `hits` → 渲染引用卡片 → 用户点某条 → 展开 `raw\\\\\\\_content`。\*\*



\*\*这就闭环了。\*\*





`dataclass` 自动生成四样东西：
生成	有什么用

\_\_init\_\_	ParsedDoc("...", 3, "pypdf") 直接构造

\_\_repr\_\_	print(parsed) 能看到内容，调 bug 时不用手拼

\_\_eq\_\_	parsed\_a == parsed\_b 按字段值比，不是比内存地址

\_\_hash\_\_	只有 frozen=True 时才给，能当 dict key









茅台2023年报.pdf

&#x20;  ↓ \_parse\_pdf

ParsedDoc(text="全年营收……", page\_count=12, parser="pypdf")

&#x20;  ↓ split\_parents（按标题栈切，超 3000 按段落切）

\[

&#x20; ParentBlock(section\_path="正文", content="第1段……\\n\\n第2段……"),   # 一整节 2800 字

&#x20; ...

]

&#x20;  ↓ split\_children（每 400 字递归切，重叠 60）

\[

&#x20; ChildBlock(parent\_index=0, section\_path="正文",

&#x20;            content="正文\\n第1段前 400 字……",        # 进向量、进 BM25

&#x20;            raw\_content="第1段前 400 字……"),          # 副本

&#x20; ChildBlock(parent\_index=0, section\_path="正文", ...),

&#x20; ChildBlock(parent\_index=1, section\_path="正文 (续1)", ...),

&#x20; ...

]

&#x20;  ↓ embed\_texts（对每个 child 的 content）

&#x20;  ↓ 拼 rows（parent\_index → parents\[i] 算出 parent\_id）

&#x20;  ↓ Milvus insert







`AnnSearchRequest` 到底是什么

> 我要在 \\\*\\\*某个字段\\\*\\\* 上，用 \\\*\\\*某个东西\\\*\\\*，按 \\\*\\\*某种度量\\\*\\\*，找 \\\*\\\*前 N 条\\\*\\\*，并且只要满足 \\\*\\\*某个条件\\\*\\\* 的。」



\*\*就是一句话打包成一个对象。\*\*



\## 五个参数逐个拆



AnnSearchRequest(

&#x20;   \[query\_vector],              # data

&#x20;   "dense",                      # anns\_field

&#x20;   {"metric\_type": "COSINE"},    # param

&#x20;   limit=top\_k,                  # limit

&#x20;   expr=expr,                    # expr

)



参数	是什么	为什么这么填

data	要搜的东西	稠密传 \[向量]，稀疏传 \[文本]

anns\_field	在哪个字段上搜	"dense" 或 "sparse"

param	搜索参数	metric\_type 必须和建索引时一致（COSINE / BM25）

limit	这一路要几条候选	传 top\_k，两路各取 top\_k 条

expr	标量过滤	把 user\_id == 4 下推给 Milvus，不拉全库回来再过滤





三个函数连起来的完整数据流：

【上传入库】

PDF → parser.parse\_document → ParsedDoc

&#x20;   → parser.split\_parents → list\[ParentBlock]

&#x20;   → parser.split\_children → list\[ChildBlock]

&#x20;   → embedding.embed\_texts(\[c.content ...]) → list\[向量]

&#x20;   → 拼 rows（parent\_index 反查 parent\_id）

&#x20;   → vector.insert\_children(client, rows)      ← 这个文件

&#x20;   → documents.status = "indexed"



【删除】

用户点删 → vector.delete\_by\_doc(client, doc\_id, user\_id)   ← 这个文件

&#x20;       → 删 documents / parent\_chunks（CASCADE）



【检索】

用户提问 → embedding.embed\_texts(\[query]) → query\_vector

&#x20;       → vector.hybrid\_search(client, query\_text, query\_vector, user\_id, top\_k)   ← 这个文件

&#x20;       → 去重后的父块列表

&#x20;       → SearchOut(query=..., hits=\[...])

