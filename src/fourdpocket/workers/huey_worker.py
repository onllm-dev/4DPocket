"""Huey worker entry point - runs as: python -m fourdpocket.workers.huey_worker"""

import logging
import os
import sys
from pathlib import Path

# In development (source tree), chdir to project root for relative path resolution.
# In pip install mode, paths come from config (absolute) so CWD doesn't matter.
_project_root = Path(__file__).parent.parent.parent
if (_project_root / "pyproject.toml").exists():
    os.chdir(_project_root)
    _src_path = _project_root / "src"
    if str(_src_path) not in sys.path:
        sys.path.insert(0, str(_src_path))

# Import all task modules so Huey can discover them
from fourdpocket.workers import huey  # noqa: F401
from fourdpocket.workers.ai_enrichment import enrich_item  # noqa: F401
from fourdpocket.workers.archiver import archive_page  # noqa: F401
from fourdpocket.workers.fetcher import fetch_and_process_url  # noqa: F401
from fourdpocket.workers.media_downloader import download_media  # noqa: F401
from fourdpocket.workers.rss_worker import poll_all_feeds  # noqa: F401
from fourdpocket.workers.rule_engine import run_rules_for_item  # noqa: F401
from fourdpocket.workers.scheduler import cleanup_stale_tasks, reprocess_pending_items  # noqa: F401
from fourdpocket.workers.screenshot import capture_screenshot  # noqa: F401

if __name__ == "__main__":
    sys.argv = ["huey_consumer.py", "fourdpocket.workers.huey"]

    from huey.bin.huey_consumer import consumer_main
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s:%(message)s")
    sys.exit(consumer_main())
