import re
from pathlib import Path


def test_alembic_revision_ids_fit_version_column_limit():
    versions_dir = Path(__file__).resolve().parents[1] / "migrations" / "versions"
    revision_pattern = re.compile(r'^revision\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
    over_limit = []
    for migration_path in versions_dir.glob("*.py"):
        source = migration_path.read_text(encoding="utf-8")
        match = revision_pattern.search(source)
        if match and len(match.group(1)) > 32:
            over_limit.append((migration_path.name, match.group(1), len(match.group(1))))
    assert not over_limit, f"Alembic revision IDs must be at most 32 characters: {over_limit}"
