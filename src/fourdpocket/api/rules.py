"""Automation rules CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.rule import Rule
from fourdpocket.models.user import User

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleCreate(BaseModel):
    name: str
    condition: dict  # JSON condition object
    action: dict     # JSON action object
    is_active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = None
    condition: dict | None = None
    action: dict | None = None
    is_active: bool | None = None


class RuleRead(BaseModel):
    id: str
    name: str
    condition: dict
    action: dict
    is_active: bool


@router.get("")
def list_rules(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RuleRead]:
    rules = db.exec(select(Rule).where(Rule.user_id == user.id)).all()
    return [RuleRead(id=str(r.id), name=r.name, condition=r.condition, action=r.action, is_active=r.is_active) for r in rules]


@router.post("", status_code=201)
def create_rule(
    body: RuleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleRead:
    rule = Rule(user_id=user.id, name=body.name, condition=body.condition, action=body.action, is_active=body.is_active)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return RuleRead(id=str(rule.id), name=rule.name, condition=rule.condition, action=rule.action, is_active=rule.is_active)


@router.patch("/{rule_id}")
def update_rule(
    rule_id: str,
    body: RuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleRead:
    rule = db.exec(select(Rule).where(Rule.id == rule_id, Rule.user_id == user.id)).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return RuleRead(id=str(rule.id), name=rule.name, condition=rule.condition, action=rule.action, is_active=rule.is_active)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rule = db.exec(select(Rule).where(Rule.id == rule_id, Rule.user_id == user.id)).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
