from pathlib import Path

from vendorlens_worker.migrate import asyncpg_url, migration_checksum, migration_files


def test_migration_files_are_sorted_and_ignore_non_sql(tmp_path: Path) -> None:
    later = tmp_path / "202609230002_later.sql"
    first = tmp_path / "202609230001_first.sql"
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    later.write_text("select 2;", encoding="utf-8")
    first.write_text("select 1;", encoding="utf-8")

    assert migration_files(tmp_path) == [first, later]
    assert len(migration_checksum(first)) == 64


def test_asyncpg_url_removes_sqlalchemy_driver_name() -> None:
    assert (
        asyncpg_url("postgresql+asyncpg://user:pass@database.example/postgres")
        == "postgresql://user:pass@database.example/postgres"
    )
