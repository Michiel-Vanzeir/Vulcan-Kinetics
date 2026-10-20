from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

NodeType = Literal["Department", "Project", "Team", "Subteam", "Person"]


class CreateNodeIn(BaseModel):
    type: NodeType
    name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    parent_ids: list[str] = []
    email: Optional[str] = None   # Person only
    phone: Optional[str] = None   # Person only


class LinkIn(BaseModel):
    parent_id: str


class KnowledgeIn(BaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)   # embedded together with title + summary
    importance: int = Field(ge=1, le=5)
    occurred_at: datetime
    source_type: str
    source_uri: str
    holder_ids: list[str] = Field(min_length=1)
    supersedes_id: Optional[str] = None
