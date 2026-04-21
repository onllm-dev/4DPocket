"""Automation rules CRUD endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from fourdpocket.api.deps import get_current_user, get_db, require_pat_editor
from fourdpocket.models.rule import Rule
from fourdpocket.models.user import User

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleCondition(BaseModel):
    type: Literal["url_matches", "source_platform", "title_contains", "content_contains", "has_tag"]
    value: str


class RuleAction(BaseModel):
    type: Literal["add_tag", "add_to_collection", "set_favorite", "archive"]
    value: str | None = None


class RuleCreate(BaseModel):
    name: str
    condition: RuleCondition
    action: RuleAction
    is_active: bool = True

    model_config = {"extra": "forbid"}


class RuleUpdate(BaseModel):
    name: str | None = None
    condition: RuleCondition | None = None
    action: RuleAction | None = None
    is_active: bool | None = None


class RuleRead(BaseModel):
    id: uuid.UUID
    name: str
    condition: dict
    action: dict
    is_active: bool
    created_at: datetime
    user_id: uuid.UUID
    model_config = {"from_attributes": True}


@router.get("")
def list_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[RuleRead]:
    rules = db.exec(select(Rule).where(Rule.user_id == current_user.id).offset(offset).limit(limit)).all()
    return rules


@router.post("", status_code=201)
def create_rule(
    body: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
) -> RuleRead:
    rule = Rule(
        user_id=current_user.id,
        name=body.name,
        condition=body.condition.model_dump(),
        action=body.action.model_dump(),
        is_active=body.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/{rule_id}")
def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
) -> RuleRead:
    rule = db.exec(select(Rule).where(Rule.id == rule_id, Rule.user_id == current_user.id)).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    rule = db.exec(select(Rule).where(Rule.id == rule_id, Rule.user_id == current_user.id)).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
