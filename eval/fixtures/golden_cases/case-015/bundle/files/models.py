"""User domain models with Pydantic validation."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

RESERVED_USERNAMES = frozenset({"admin", "root", "system", "null", "undefined"})


class Role(StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    display_name: str = Field(min_length=1, max_length=100)
    email: str
    role: Role = Role.VIEWER

    @field_validator("username")
    @classmethod
    def username_not_reserved(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9_]+$", v):
            raise ValueError("Username must be lowercase alphanumeric with underscores")
        if v in RESERVED_USERNAMES:
            raise ValueError(f"Username '{v}' is reserved")
        return v

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Display name cannot be blank or whitespace-only")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    email: str
    role: Role
    created_at: datetime

    model_config = {"from_attributes": True}
