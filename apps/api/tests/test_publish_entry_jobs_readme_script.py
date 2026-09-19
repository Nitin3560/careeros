from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_publish_script_exists_and_updates_entry_readme():
    script = ROOT / "scripts" / "publish_entry_jobs_readme.sh"
    content = script.read_text()

    assert "scripts/backfill_jobs.py" in content
    assert "fetch_amazon_jobs" in content
    assert "scripts/update_entry_jobs_readme.py" in content
    assert "git commit -m \"Update entry-level job README feed\"" in content
