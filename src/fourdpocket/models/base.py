"""Shared model mixins and enums."""

import enum
from datetime import datetime, timezone


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"
    guest = "guest"


class ItemType(str, enum.Enum):
    url = "url"
    note = "note"
    image = "image"
    pdf = "pdf"
    code_snippet = "code_snippet"


class SourcePlatform(str, enum.Enum):
    youtube = "youtube"
    instagram = "instagram"
    reddit = "reddit"
    twitter = "twitter"
    threads = "threads"
    tiktok = "tiktok"
    github = "github"
    hackernews = "hackernews"
    stackoverflow = "stackoverflow"
    mastodon = "mastodon"
    substack = "substack"
    medium = "medium"
    linkedin = "linkedin"
    spotify = "spotify"
    generic = "generic"


class ShareMode(str, enum.Enum):
    private = "private"
    link = "link"
    invite = "invite"


class ReadingStatus(str, enum.Enum):
    unread = "unread"
    reading_list = "reading_list"
    read = "read"


class ApiTokenRole(str, enum.Enum):
    viewer = "viewer"
    editor = "editor"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
