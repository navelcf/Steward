吓死我了，我还以为一切要从底层开始写起，原来是教程没写好。



理论上langchain的底层就是langgraph，那么creat\_agent理论上就是画了一个简单的langgraph图，那理论上，我自定义一个langgraph图，也应该能够使用上自定义中间件或者自带中间件，结果居然不行，折中做法居然是creat\_agent先画图，再重新complie一下，这真的太奇怪了，但我不想再搞了，就这么做吧，理论上langgraph的图肯定少了某个能接入中间件的关键东西！



关于checkpoint



set\_up实际上建立了四张表：
checkpoint\_migrations    ← 记录“建表建到第几版了”，防止重复执行

checkpoints              ← 核心表：每个存档点一行

checkpoint\_blobs         ← 大块内容（state 里每个 channel 的序列化数据）

checkpoint\_writes        ← 中途的未决写入（崩溃恢复用）





表	存什么	大小

checkpoints	一行 = 一个存档点。但里面主要是指针：channel\_values 和 channel\_versions（哪个 channel 指向哪个版本）	很小（JSON）

checkpoint\_blobs	真正的内容：每个 channel 每个版本序列化后一份	大





\*\*所以 “快照” 这个说法要拆开：\*\*



\- \*\*`checkpoints` 里的那一行，可以理解成\*\*目录页\*\*（这一版里 `messages` 指向 v7，`plan` 指向 v3）\*\*

\- \*\*`checkpoint\_blobs` 里才是\*\*正文 \*\*\*\*



关于工具落表：

`param\_schema`—— 模型靠它知道 “这个工具怎么用”

param\_schema: Mapped\[dict] = mapped\_column(JSONB, nullable=False)





class SearchArgs(BaseModel):

&#x20;   keyword: str = Field(description="要检索的关键词，必填")      # ← 参数级 description

&#x20;   top\_k: int = Field(default=5, description="返回几条，默认 5")





@tool("search\_contract", args\_schema=SearchArgs)

def search\_contract(keyword: str, top\_k: int = 5) -> str:

&#x20;   """按关键词检索合同条款；只在你需要引用具体条款时调用，返回带条款号的片段。"""

&#x20;   # ↑ 这个 docstring 就是顶层的 description







langchain会将它变成：

{

&#x20; "description": "按关键词检索合同条款；只在你需要引用具体条款时调用，返回带条款号的片段。",

&#x20; "properties": {

&#x20;   "keyword": {

&#x20;     "description": "要检索的关键词，必填",

&#x20;     "title": "Keyword",

&#x20;     "type": "string"

&#x20;   },

&#x20;   "top\_k": {

&#x20;     "default": 5,

&#x20;     "description": "返回几条，默认 5",

&#x20;     "title": "Top K",

&#x20;     "type": "integer"

&#x20;   }

&#x20; },

&#x20; "required": \["keyword"],

&#x20; "title": "search\_contract",

&#x20; "type": "object"

}

所以这里要使用jsonb格式









1\.、`messages` 和 checkpointer 的四张表：职责完全不同



\*\*先把你那句“thread 表我能理解”接上：\*\*



\*\*`thread\_id` 在 old 项目里是\*\*你传给 checkpointer 的一个字符串\*\*，它只是个键。\*\*



\*\*但在 Steward 里，`chat\_threads` 是一张\*\*真表\*\*——它管的是“会话归属谁”（`user\_id`）、标题是什么、什么时候建的。\*\*



\*\*checkpointer 不知道 `user\_id` 是谁。它只知道“有个 thread\_id 叫 xxx”。\*\*



\*\*所以 `chat\_threads` 存在的理由：多用户。checkpointer 从设计上就假设“一个进程一个会话”，它没有用户概念。\*\*



\---



\*\*然后是最核心的问题：`messages` 表为什么还要建？\*\*



\*\*看 checkpointer 的四张表存的是什么：\*\*



| 表 | 存什么 | 格式 |

|---|---|---|

| \*\*`checkpoints`\*\* | \*\*state 的\*\*目录\*\*（哪个 channel 指向哪个版本）\*\* | \*\*JSON\*\* |

| \*\*`checkpoint\_blobs`\*\* | \*\*state 每个 channel 的内容（`messages` 那个 list 整个序列化）\*\* | \*\*msgpack/orm 二进制\*\* |

| \*\*`checkpoint\_writes`\*\* | \*\*中途未提交的写入\*\* | \*\*同上\*\* |

| \*\*`checkpoint\_migrations`\*\* | \*\*建表版本记录\*\* | \*\*——\*\* |



\*\*所以“历史消息”在哪里？在 `checkpoint\_blobs` 里，\*\*作为一个整体序列化的 list\*\*。\*\*



\*\*这带来四个死问题：\*\*



\*\*① 查不了\*\*



\*\*你想“只查这个会话最近 5 条”，`aget\_state` 只能把\*\*整个 list\*\* 反序列化出来，然后在内存里切。\*\*



\*\*20 条还行，5 万条就撑爆内存。而 `messages` 表可以 `LIMIT 5 OFFSET ...`。\*\*



\*\*② 没时间\*\*



\*\*`AIMessage` / `HumanMessage` 都没有 `created\_at`（之前实测过，字段列表里根本没有）。\*\*



\*\*而 `messages` 表有 `created\_at`，前端要“按时间排”只有这张表能给。\*\*



\*\*③ 格式给了前端也用不了\*\*



\*\*`checkpoint\_blobs` 里是 LangChain 的对象序列化（`type='msgpack'` 之类的二进制）。\*\*



\*\*前端拿到没法直接显示。`MessageOut`（`id/role/content/created\_at`）是\*\*你要的契约\*\*，不是 LangChain 的格式。\*\*



\*\*④ `sources` / `run\_id` 无处安放\*\*



\*\*`AIMessage` 里没有 `sources` 字段。硬塞进 `additional\_kwargs` 又违反方案 8.4「不能把业务数据塞 State」。\*\*



\*\*而 `messages` 表里有这两列。\*\*



\*\*所以结论是：\*\*



\*\*checkpointer 存的是\*\*“给模型下次接着聊的东西”\*\*——一份可以精确恢复的 state。\*\*

\*\*`messages` 存的是\*\*“给人看、给接口返回、给审计查的东西”\*\*——一条条有 id、有时间、有角色的行。\*\*



\*\*两者内容\*\*重叠\*\*（都记了对话），但读者不同、格式不同、用途不同。\*\*



\*\*你在 Day 1 建这张表不是白做，它补的正是 checkpointer 那四张表\*\*从设计上就不提供的四样东西\*\*。\*\*\*\*



\---



\# 四、三张表，一张总图



\*\*你现在有三类数据，各归各管：\*\*



| 数据 | 归谁管 | 存在哪 | 谁在读它 |

|---|---|---|---|

| \*\*能调什么、要不要人批\*\* | \*\*你（业务）\*\* | \*\*`tool\_registry`\*\* | \*\*Agent 组 prompt、审批流程\*\* |

| \*\*跑到哪了、下轮从哪接\*\* | \*\*LangGraph（框架）\*\* | \*\*`checkpoints` 四张表\*\* | \*\*Agent 自己\*\* |

| \*\*说过什么、给谁看\*\* | \*\*你（业务）\*\* | \*\*`messages`\*\* | \*\*前端、历史接口、审计\*\* |

| \*\*会话是谁的\*\* | \*\*你（业务）\*\* | \*\*`chat\_threads`\*\* | \*\*归属校验、列表\*\* |



\*\*LangGraph 只负责中间那一行。上面、下面那三行都是\*\*你的事\*\*，因为它不知道“用户”这个概念，也不管“接口契约”。\*\*



\*\*所以不是“重复建设”，是\*\*职责分层\*\*：\*\*



\*\*- 框架管“它能恢复的运行状态”\*\*

\- \*\*你管“产品要展示和约束的东西”\*\*



\---



\*\*如果只记一句：\*\*



\*\*docstring 就是模型读到的中文说明（`description`）；`@tool` 是定义、`tool\_registry` 是登记，策略必须能不发版就改；checkpointer 存“能恢复的 state”，`messages` 存“能查询的行”。\*\*





我发现这些大模型越来越会认梗了，说明这种梗的出现频率已经相当高了。

\*\*如果你加了个 `DELETE /tools/{name}`：\*\*



\*\*1. 调用它 → 表里那行被删了\*\*

\*\*2. 服务重启 → `ensure\_registered` 扫一遍代码里的 `@tool` → 发现 `search\_contract` 不在表里 → \*\*又插回去\*\*

\*\*3. 你删了个寂寞\*\*





寂寞这种词理论上和删除或者失败应该毫无关系啊。







