关于system消息或者说作为系统role：
东西	在哪

用户消息 / 助手回复 / 工具返回	在 state\["messages"] 里，会进 checkpointer

system prompt	一个外部常量，每次 model 调用时临时拼在最前面，不回写 state\*\*\*\*



这玩意也不进入checkpointer

因此我们自己建造的chat当中的message表里面的role也没必要存在



我发现一点，agent存的历史消息什么的，已经被checkpointer支配了，相当于我存的message表只是一个副本，我查找一个会话的历史消息，按代码来说，是去message表里面去查的，然后我如果删除的话，有个点，thread和chat都有删除的功能且都是删除整个会话，会不会在功能上有重复？好像又没有，删除chat的话，只是把message表相关的删了，但是thread还在，删除thread的逻辑是这样的：await self.session.delete(thread)

        await self.session.flush()，理论上直接把整个会话删了，但是问题来了，删了会话，但是message表里面还有消息啊，只是这个里面的thread\_id永远找不到了。其次，删除了整个聊天的messages的话，但是！问题来了，我删的是副本啊！理论上checkpointer里面是不是还保留！你去查查看我以前写的代码，我记得做过一个ai伴侣，可以把历史记录搞出来，理论上这里的历史记录应该是从checkpointer里面拿出来的，但我记不清了。



哦，不对！ForeignKey("chat\_threads.id", ondelete="CASCADE"),我写了外键约束，thread被删了，那就一起删！



1.我刚刚实际测试了一下，接入checkpointer之后，模型已经忘了这段会话的历史了，这很正常，因为现在是checkpointer在管 2.目前的问题在于checkpointer和thread表与chat表之间没有关系，我查历史记录也是查message表。3.我现在真的怀疑这个thread表和message表到底有什么用处！如果这两个都能从checkpointer里面直接查到，那不就是没用吗？至于sources、run\_id，这两我目前还没看到用到的地方



\# `thread` 表不能删 —— 它存的是 checkpointer 里没有的东西



\*\*checkpointer 的 `checkpoints` 表里只有这些字段：\*\*

thread\_id | checkpoint\_ns | checkpoint\_id | parent\_checkpoint\_id | checkpoint（序列化状态）| metadata | created\_at



没有：

字段	在哪	干什么

title	thread 表	前端会话列表显示什么名字

user\_id	thread 表	这个会话归谁（归属校验、越权防护）

active\_workflow	thread 表	P1 的流程状态

业务排序依据	thread.updated\_at	会话列表按 “最近聊过” 排序



\*\*果删了 `thread` 表：\*\*

\- \*\*`GET /threads` 返回不出来\*\*（没有标题、没有用户归属）

\- \*\*前端会话列表里全是裸 UUID，没有任何可读信息\*\*

\- \*\*归属校验无从下手\*\*（checkpointer 的 `thread\_id` 不带 `user\_id`，谁都能读）

\*\*所以 `thread` 表是 “会话的身份证和名片”，checkpointer 只是 “会话的记忆”。两者不是重复，是\*\*不同层\*\*。\*\*





tool\_calls在chunk.tool\_calls



目前的问题总结报告：

关于 Steward 的 `checkpointer` / `chat\_threads` / `messages` 三套存储，结论如下：

&#x09;存什么	谁写	谁读

checkpoints（Checkpointer 自动建）	Agent 执行状态（messages 列表，给模型看）	LangGraph 自动	Agent 自己

chat\_threads	会话元数据：title / user\_id / created\_at / active\_workflow	ThreadService	GET /threads（前端列表）

messages	业务消息：content + sources + run\_id	event\_stream 段 1 / 段 3	GET /threads/{id}/messages（前端历史）



\*\*真实缺口\*\*



\*\*方案 4.5 L538 原文：「删除会话时清 checkpoints」。当前 `ThreadService.delete\_thread` 没有 `checkpointer.adelete\_thread(thread\_id)`\*\*




\# 能不能直接给 `checkpoints` 加外键



\*\*我实测了（事务里加完立刻回滚，没留痕迹）：\*\*



```

BEGIN;

ALTER TABLE checkpoints ADD CONSTRAINT fk\_probe

&#x20;   FOREIGN KEY (thread\_id) REFERENCES chat\_threads(id) ON DELETE CASCADE;

\-- 结果：ALTER TABLE  ← 成功了

ROLLBACK;

```



\*\*技术上\*\*能加\*\*。PG 允许 `TEXT` 和 `VARCHAR(36)` 之间建外键（字符串类型兼容）。\*\*



\*\*加了之后，删 `chat\_threads` 会级联删 `checkpoints`—— 看起来问题解决了。\*\*



\## 但不该这么做，三个理由



\*\*① 方案 4.3 L525 原文：\*\*



> 

> \*\*`checkpoints` 系列表由 `langgraph-checkpoint-postgres` 的 `AsyncPostgresSaver.setup()` 自动创建，不要手工改。\*\*



\*\*手工加的约束，下次 `setup()` 跑（它是 `CREATE TABLE IF NOT EXISTS`）不会报错，也不会删掉你的外键 —— 但它\*\*不知道\*\*有这个东西。将来 LangGraph 升级、迁移脚本跑的时候，可能出意外。\*\*



\*\*② `checkpoint\_blobs` / `checkpoint\_writes` 也得一起加，共三张表、三个约束。\*\*你每加一张，将来就多一个 “升级时可能被搞坏” 的地方。\*\*



\*\*③ 最关键的：Checkpointer 有\*\*自己的删除语义\*\*。`adelete\_thread` 是幂等的、走它自己的 `psycopg` 连接池、内部按顺序删三张表。你加外键等于\*\*绕开它的删除路径\*\*，让 PG 替你干 —— 行为上可能对，但\*\*语义上错位\*\*。\*\*



\*\*打个比方：`adelete\_thread` 是 “打电话给 Checkpointer 说这个会话不要了，它自己去清理”；加外键是 “你趁它不在，直接把它的柜子搬空”。结果一样，但它的内部状态（比如 `checkpoint\_migrations` 的版本记录）没被通知到。\*\*





