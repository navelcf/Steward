# 整个项目唯一的「配置入口」。
# 以后任何地方要读端口、数据库地址、密钥，
# 都写 from steward.core.config import settings，不再各自 os.getenv(...)。
# 这样改配置只改一处，也不会有人把密钥硬编码在业务代码里。


from __future__ import annotations


# 一行开关，作用是让本文件里所有类型注解延迟解析。
# 好处是可以先写 `def f(x: Foo)`，而 `Foo` 在文件后面才定义。
# 这份代码里没有这种用法，所以这行目前没有任何实际作用，是模板习惯。

from pathlib import Path

from pydantic import Field, computed_field

# `Field` 是 Pydantic 的一个函数，
# 返回一个「字段描述」给字段挂上
# `alias`（外部名字）、`default`（兜底）、`min_length`（长度限制）


from pydantic_settings import BaseSettings, SettingsConfigDict


# BaseSettings,继承它，获得「自动去环境变量和 .env 找值」的能力
# SettingsConfigDict一个带类型提示的字典类型,只用来给 `model_config` 赋值，规定能写哪些参数

from sqlalchemy.engine import URL

# 表示数据库连接串把 drivername / 账号 / 密码 / 主机 / 端口 / 库名分开存，避免手拼字符串


# src/steward/core/config.py 往上数 3 层才是项目根 E:\Steward：
# core -> steward -> src -> 项目根。手册里的平铺布局只需要 parents[2]。
APP_ROOT = Path(__file__).resolve().parents[3]
# 居然还有这种写法！resolve是转为绝对路径


class EnvSettings(BaseSettings):
    # 所有配置分组的公共基类：统一从项目根 .env 读取。

    model_config = SettingsConfigDict(
        env_file=(APP_ROOT / ".env",),
        env_file_encoding="utf-8",
        extra="ignore",  # 文件里有、但字段里没定义的键：丢掉不报错
        case_sensitive=False,  # 键名大小写不敏感
    )


class AppSettings(EnvSettings):
    name: str = Field(alias="APP_NAME", default="Steward")
    host: str = Field(alias="APP_HOST", default="127.0.0.1")
    port: int = Field(alias="APP_PORT", default=8001)
    debug: bool = Field(alias="APP_DEBUG", default=True)
    # 允许跨域的前端地址，逗号分隔；dev 用 3100（3000 被 Attu 占了）。
    cors_origins: str = Field(
        alias="CORS_ORIGINS",
        default="http://localhost:3100,http://127.0.0.1:3100",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        # 逗号分隔转列表；顺手去掉空白项，避免 "a,,b" 这种脏值。
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


class DatabaseSettings(EnvSettings):
    host: str = Field(alias="DB_HOST", default="127.0.0.1")
    port: int = Field(alias="DB_PORT", default=5432)
    name: str = Field(alias="DB_NAME", default="steward")
    user: str = Field(alias="DB_USER", default="steward")
    password: str = Field(alias="DB_PASSWORD", default="")
    echo: bool = Field(alias="DB_ECHO", default=False)  # sql语句
    pool_size: int = Field(alias="DB_POOL_SIZE", default=5)  # 连接池大小
    max_overflow: int = Field(alias="DB_MAX_OVERFLOW", default=10)  # 连接池溢出最大值
    pool_recycle: int = Field(alias="DB_POOL_RECYCLE", default=1800)  # 连接池回收时间

    @computed_field  # 加了 `@computed_field`，Pydantic 就把这个属性当成一个「算出来的字段」
    @property  # a.url 访问属性，直接取，不用括号
    def url(self) -> str:
        # 交给 SQLAlchemy 的 asyncpg 连接串。

        # 用 URL.create 而不是手拼字符串：密码里的 @ : / 会被自动转义，
        # 手册附录 B 的 InvalidPasswordError 从根上就不会发生。

        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.name,
        ).render_as_string(hide_password=False)
        # render_as_string: 把 URL 对象转为字符串，hide_password: 不隐藏密码

    # 项目中的 SQLAlchemy 使用 asyncpg 驱动，而 PostgreSQL Checkpointer 使用 psycopg 驱动。
    # 二者访问的是同一个数据库，但连接地址的协议不同。
    # Checkpointer 的串不能写 +psycopg，psycopg_pool 要的是标准 libpq URI。
    # 继续用 URL.create 而不是手拼 —— 密码里有 @ / : / / 会被自动转义，和 Day 2 一个道理。
    @computed_field
    @property
    def checkpoint_url(self) -> str:
        # psycopg 用标准 libpq URI，drivername 是 postgresql，不能带 +asyncpg。
        return URL.create(
            drivername="postgresql",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.name,
        ).render_as_string(hide_password=False)


class AuthSettings(EnvSettings):
    # 故意不设默认值：忘了配就直接启动失败，比悄悄用弱密钥安全
    secret: str = Field(alias="JWT_SECRET", min_length=32)
    expire_minutes: int = Field(alias="JWT_EXPIRE_MINUTES", default=120)


class LoggingSettings(EnvSettings):
    level: str = Field(alias="LOGGING_LEVEL", default="INFO")


class LlmSettings(EnvSettings):
    # 模型相关配置；api_key 不给默认值，忘配就启动失败（快速失败）。
    api_key: str = Field(
        alias="DEEPSEEK_API_KEY",
        min_length=1,
    )
    # OpenAI 兼容根地址，不带 /v1；
    base_url: str = Field(
        alias="DEEPSEEK_BASE_URL",
        default="https://api.deepseek.com",
    )
    # 换模型只改 .env 这一行的值，代码不动。
    chat_model: str = Field(
        alias="CHAT_MODEL",
        default="deepseek-flash",
    )
    # 思考模式开关：enabled / disabled；默认关闭，官方默认是开启。
    thinking: str = Field(
        alias="CHAT_THINKING",
        default="disabled",
        pattern="^(enabled|disabled)$",
    )
    # temperature 在思考模式不生效；默认已关闭思考，这个值才真正起作用。
    temperature: float = Field(
        alias="CHAT_TEMPERATURE",
        default=0.3,
    )
    # 8 万是 ADR-03 定的产品阈值，不是模型能力上限，不随 1M 上下文放大。
    max_doc_tokens: int = Field(
        alias="MAX_DOC_TOKENS",
        default=80000,
    )
    stream_usage: bool = Field(
        alias="STREAM_USAGE",
        default=True,
    )


class MilvusSettings(EnvSettings):
    # Milvus 连接信息；localhost 用 127.0.0.1，容器内互访用服务名。
    host: str = Field(alias="MILVUS_HOST", default="127.0.0.1")
    port: int = Field(alias="MILVUS_PORT", default=19530)
    # 集合名带版本号，改 schema 时建 v2 而不是原地改（方案 7.4 L911）。
    collection: str = Field(alias="MILVUS_COLLECTION", default="child_chunks_v1")
    # dense 维度；和 embedding 模型输出必须一致（方案定 1024）。
    dim: int = Field(alias="EMBEDDING_DIM", default=1024)

    @computed_field
    @property
    def uri(self) -> str:
        # MilvusClient 要 http:// 前缀，不是 host:port。
        return f"http://{self.host}:{self.port}"


class EmbeddingSettings(EnvSettings):
    # 百炼 API Key；embedding 专用，和 DeepSeek 的 key 不是同一个。
    api_key: str = Field(alias="DASHSCOPE_API_KEY", min_length=1)
    # 换模型只改这一行；维度跟着模型走，但 Milvus 集合已按 1024 建好。
    model: str = Field(alias="EMBEDDING_MODEL", default="text-embedding-v4")


class RagSettings(EnvSettings):
    # 双路召回各取多少条候选（方案 7.8：默认 20，范围 10–50）。
    top_k: int = Field(alias="RAG_TOP_K", default=20, ge=10, le=50)
    # 最终送给模型几个父块（方案 7.8：默认 6，范围 3–10）。
    # 注意这是「父块数」，不是「子块数」——父块动辄 2000 字，6 个已经够大。
    final_k: int = Field(alias="RAG_FINAL_K", default=6, ge=3, le=10)
    # dense 路的最低余弦相似度。低于它的命中直接丢掉，见 Step 3.5 —— 这是「查不到就说没有」的开关。
    min_score: float = Field(alias="RAG_MIN_SCORE", default=0.35, ge=0.0, le=1.0)


class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    milvus: MilvusSettings = Field(default_factory=MilvusSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    rag: RagSettings = Field(default_factory=RagSettings)


settings = Settings()
