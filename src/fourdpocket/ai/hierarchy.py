"""Smart tag hierarchy - auto-nesting based on domain knowledge."""

import logging
import uuid

from sqlmodel import Session, select

from fourdpocket.models.tag import Tag

logger = logging.getLogger(__name__)

# Known domain mappings: child -> parent path
HIERARCHY_MAP = {
    # Programming languages
    "python": "programming", "javascript": "programming", "typescript": "programming",
    "rust": "programming", "go": "programming", "java": "programming",
    "c++": "programming", "c#": "programming", "ruby": "programming",
    "php": "programming", "swift": "programming", "kotlin": "programming",
    "scala": "programming", "haskell": "programming", "elixir": "programming",
    # Web frameworks
    "react": "frontend", "vue": "frontend", "angular": "frontend",
    "svelte": "frontend", "nextjs": "frontend", "nuxt": "frontend",
    "tailwind": "frontend", "css": "frontend", "html": "frontend",
    # Backend frameworks
    "fastapi": "backend", "django": "backend", "flask": "backend",
    "express": "backend", "nestjs": "backend", "rails": "backend",
    "spring": "backend",
    # DevOps
    "kubernetes": "devops", "docker": "devops", "terraform": "devops",
    "ansible": "devops", "jenkins": "devops", "github-actions": "devops",
    "ci-cd": "devops", "aws": "devops", "gcp": "devops", "azure": "devops",
    # AI/ML
    "machine-learning": "ai", "deep-learning": "ai", "nlp": "ai",
    "computer-vision": "ai", "llm": "ai", "rag": "ai",
    "langchain": "ai", "pytorch": "ai", "tensorflow": "ai",
    "transformers": "ai", "embeddings": "ai", "fine-tuning": "ai",
    # Data
    "sql": "data", "postgresql": "data", "mongodb": "data",
    "redis": "data", "elasticsearch": "data", "data-engineering": "data",
    "analytics": "data", "data-science": "data",
    # Design
    "ui-design": "design", "ux-design": "design", "figma": "design",
    "typography": "design", "color-theory": "design",
    # Meta categories
    "frontend": "programming", "backend": "programming",
    "ai": "technology", "devops": "technology", "data": "technology",
    "security": "technology", "networking": "technology",
    "programming": "technology",
    # Content types
    "tutorial": "content-type", "comparison": "content-type",
    "guide": "content-type", "reference": "content-type",
    "opinion": "content-type", "news": "content-type",
    # Other domains
    "cooking": "lifestyle", "recipe": "cooking", "baking": "cooking",
    "fitness": "lifestyle", "travel": "lifestyle",
    "finance": "business", "startup": "business", "marketing": "business",
    "productivity": "business",
}


def apply_hierarchy(tag_name: str, user_id: uuid.UUID, db: Session) -> None:
    """Apply hierarchy to a tag based on domain knowledge.

    If tag_name is 'python' and HIERARCHY_MAP says python -> programming,
    find or create the 'programming' tag and set it as parent.
    """
    slug = tag_name.lower().strip()
    parent_name = HIERARCHY_MAP.get(slug)
    if not parent_name:
        return

    # Find the child tag
    child_tag = db.exec(
        select(Tag).where(Tag.user_id == user_id, Tag.slug == slug)
    ).first()
    if not child_tag or child_tag.parent_id is not None:
        return  # Already has a parent or doesn't exist

    # Find or create parent tag
    parent_slug = parent_name.lower().strip()
    parent_tag = db.exec(
        select(Tag).where(Tag.user_id == user_id, Tag.slug == parent_slug)
    ).first()

    if not parent_tag:
        parent_tag = Tag(
            user_id=user_id,
            name=parent_name,
            slug=parent_slug,
            ai_generated=True,
        )
        db.add(parent_tag)
        db.flush()

    child_tag.parent_id = parent_tag.id
    db.add(child_tag)
    db.commit()

    logger.debug("Set tag hierarchy: %s -> %s", tag_name, parent_name)

    # Recursively apply hierarchy to the parent
    apply_hierarchy(parent_name, user_id, db)
