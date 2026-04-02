"""Instance-level settings (singleton row)."""

from sqlmodel import Column, Field, SQLModel

try:
    from sqlalchemy import JSON
except ImportError:
    from sqlmodel import JSON


class InstanceSettings(SQLModel, table=True):
    __tablename__ = "instance_settings"

    id: int = Field(default=1, primary_key=True)  # singleton
    instance_name: str = Field(default="4DPocket")
    registration_enabled: bool = Field(default=True)
    registration_mode: str = Field(default="open")  # "open", "invite", "disabled"
    default_user_role: str = Field(default="user")
    max_users: int | None = None
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON, default="{}"))
