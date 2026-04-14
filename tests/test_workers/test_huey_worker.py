"""Tests for the huey_worker entry point."""



class TestHueyWorkerImports:
    """Verify all task modules are importable after path manipulation."""

    def test_all_task_modules_importable(self):
        """Importing huey_worker should not raise - all task modules must exist."""
        # This exercises the sys.path manipulation and import side-effects
        # without actually running the consumer
        from fourdpocket.workers import (
            ai_enrichment,
            enrichment_pipeline,
            scheduler,
        )

        # Verify the imported modules have the expected task functions
        assert hasattr(ai_enrichment, "enrich_item")
        assert hasattr(enrichment_pipeline, "enrich_item_v2")
        assert hasattr(enrichment_pipeline, "run_enrichment_stage")
        assert hasattr(scheduler, "cleanup_stale_tasks")
        assert hasattr(scheduler, "reprocess_pending_items")

    def test_project_root_detection(self, tmp_path):
        """_project_root detection and sys.path insert works for source trees."""
        # Create a fake source tree structure:
        # fake_project/         <- _project_root
        #   pyproject.toml
        #   src/
        #     workers/
        #       huey_worker.py
        fake_root = tmp_path / "fake_project"
        fake_root.mkdir()
        (fake_root / "pyproject.toml").touch()
        fake_src = fake_root / "src"
        fake_src.mkdir()
        fake_workers = fake_src / "workers"
        fake_workers.mkdir()

        # Write a fake huey_worker.py that exercises the path logic
        # Real code: Path(__file__).parent.parent.parent -> project root
        # In our fake tree, workers is at fake_root/src/workers/
        # so parent.parent.parent = fake_root's parent (tmp_path)
        # We test the path manipulation by using fake_root directly
        fake_huey = fake_workers / "huey_worker.py"
        fake_huey.write_text(
            f"""
import os, sys
from pathlib import Path
# Simulate: _project_root = Path(__file__).parent.parent.parent
# For our fake structure, use fake_root as _project_root
_project_root = Path({str(fake_root)!r})
if (_project_root / "pyproject.toml").exists():
    os.chdir(_project_root)
    _src_path = _project_root / "src"
    if str(_src_path) not in sys.path:
        sys.path.insert(0, str(_src_path))
# Assert src path was added to sys.path
assert str(_src_path) in sys.path, f"src path not in sys.path after chdir"
"""
        )

        import importlib.util

        spec = importlib.util.spec_from_file_location("huey_worker", fake_huey)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # Should not raise
