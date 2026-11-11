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


class DatabaseSettings(EnvSettings):
    host: str = Field(alias="DB_HOST", default="127.0.0.1")
    port: int = Field(alias="DB_PORT", default=5432)
    name: str = Field(alias="DB_NAME", default="steward")
    user: str = Field(alias="DB_USER", default="steward")
    password: str = Field(alias="DB_PASSWORD", default="")
    echo: bool = Field(alias="DB_ECHO", default=False)
    pool_size: int = Field(alias="DB_POOL_SIZE", default=5)
    max_overflow: int = Field(alias="DB_MAX_OVERFLOW", default=10)
    pool_recycle: int = Field(alias="DB_POOL_RECYCLE", default=1800)

    @computed_field
    @property
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


class AuthSettings(EnvSettings):
    # 故意不设默认值：忘了配就直接启动失败，比悄悄用弱密钥安全
    secret: str = Field(alias="JWT_SECRET", min_length=32)
    expire_minutes: int = Field(alias="JWT_EXPIRE_MINUTES", default=120)


class LoggingSettings(EnvSettings):
    level: str = Field(alias="LOGGING_LEVEL", default="INFO")


class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


settings = Settings()
