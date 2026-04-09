"""Huey worker entry point - runs as: python -m fourdpocket.workers.huey_worker"""

import sys
import os
import logging
from pathlib import Path

# Ensure we're in the project root so relative paths resolve correctly
PROJECT_ROOT = Path(__file__).parent.parent.parent
os.chdir(PROJECT_ROOT)

# Ensure src/ is on the path
src_path = PROJECT_ROOT / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import all task modules so Huey can discover them
from fourdpocket.workers import huey  # noqa: F401
from fourdpocket.workers.fetcher import fetch_and_process_url  # noqa: F401
from fourdpocket.workers.screenshot import capture_screenshot  # noqa: F401
from fourdpocket.workers.ai_enrichment import enrich_item  # noqa: F401
from fourdpocket.workers.archiver import archive_page  # noqa: F401
from fourdpocket.workers.media_downloader import download_media  # noqa: F401
from fourdpocket.workers.rss_worker import poll_all_feeds  # noqa: F401
from fourdpocket.workers.rule_engine import run_rules_for_item  # noqa: F401
from fourdpocket.workers.scheduler import cleanup_stale_tasks, reprocess_pending_items  # noqa: F401

if __name__ == "__main__":
    sys.argv = ["huey_consumer.py", "fourdpocket.workers.huey"]

    from huey.bin.huey_consumer import consumer_main
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s:%(message)s")
    sys.exit(consumer_main())
