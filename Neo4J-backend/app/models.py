from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

NodeType = Literal["Department", "Project", "Team", "Subteam", "Person", "Client"]


class CreateNodeIn(BaseModel):
    type: NodeType
    name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    parent_ids: list[str] = []
    client_ids: list[str] = []    # Project only
    email: Optional[str] = None   # Person only
    phone: Optional[str] = None   # Person only


class LinkIn(BaseModel):
    parent_id: str


class ClientLinkIn(BaseModel):
    client_id: str


class KnowledgeIn(BaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)   # embedded together with title + summary
    importance: int = Field(ge=1, le=5)
    occurred_at: datetime
    source_type: str
    source_uri: str
    holder_ids: list[str] = Field(min_length=1)
    client_ids: list[str] = []
    supersedes_id: Optional[str] = None


class KnowledgeRevisionIn(BaseModel):
    """Only the fields that change; everything else is copied from the revised item.
    Lists (keywords, holder_ids, client_ids) replace the old list when given."""
    model_config = ConfigDict(extra="forbid")  # a typo'd field would otherwise silently change nothing

    title: Optional[str] = Field(default=None, min_length=1)
    summary: Optional[str] = Field(default=None, min_length=1)
    keywords: Optional[list[str]] = Field(default=None, min_length=1)
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    occurred_at: Optional[datetime] = None   # defaults to now: a revision is a new event
    source_type: Optional[str] = None
    source_uri: Optional[str] = None
    holder_ids: Optional[list[str]] = Field(default=None, min_length=1)
    client_ids: Optional[list[str]] = None
