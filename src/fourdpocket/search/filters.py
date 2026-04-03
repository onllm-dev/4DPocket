"""Parse search filter syntax into backend-specific expressions."""

import re


def parse_filters(filter_string: str) -> dict:
    """Parse filter syntax like 'type:youtube tag:ml after:2024-01' into a dict.

    Supported filters:
    - type:<item_type>
    - source:<source_platform> or platform:<source_platform>
    - tag:<tag_name>
    - after:<date>
    - before:<date>
    - is:favorite or is:archived
    - has:transcript or has:summary
    """
    filters = {}

    # Extract key:value pairs
    pattern = r'(\w+):([^\s]+)'
    matches = re.findall(pattern, filter_string)

    # Remaining text after removing filters is the search query
    query = re.sub(pattern, '', filter_string).strip()
    if query:
        filters['query'] = query

    for key, value in matches:
        key = key.lower()
        value = value.strip('"\'')

        if key == 'type':
            filters['item_type'] = value
        elif key in ('source', 'platform'):
            filters['source_platform'] = value
        elif key == 'tag':
            filters.setdefault('tags', []).append(value)
        elif key == 'after':
            filters['after'] = value
        elif key == 'before':
            filters['before'] = value
        elif key == 'is':
            if value == 'favorite':
                filters['is_favorite'] = True
            elif value == 'archived':
                filters['is_archived'] = True
        elif key == 'has':
            filters.setdefault('has', []).append(value)

    return filters


def to_meilisearch_filter(parsed: dict, user_id: str) -> str:
    """Convert parsed filters to Meilisearch filter string."""
    parts = [f'user_id = "{user_id}"']

    if 'item_type' in parsed:
        parts.append(f'item_type = "{parsed["item_type"]}"')
    if 'source_platform' in parsed:
        parts.append(f'source_platform = "{parsed["source_platform"]}"')
    if parsed.get('is_favorite'):
        parts.append('is_favorite = true')
    if parsed.get('is_archived'):
        parts.append('is_archived = true')

    return " AND ".join(parts)
