from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

import asyncpg  # type: ignore[import-untyped]

MIGRATION_LOCK_ID = 8_613_337_421
DEFAULT_MIGRATION_DIRECTORY = Path("/app/supabase/migrations")


def migration_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.sql") if path.is_file())


def migration_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def apply_migrations(
    database_url: str, directory: Path = DEFAULT_MIGRATION_DIRECTORY
) -> None:
    files = migration_files(directory)
    if not files:
        raise RuntimeError(f"no migration files found in {directory}")

    connection = await asyncpg.connect(asyncpg_url(database_url))
    await connection.execute("select pg_advisory_lock($1)", MIGRATION_LOCK_ID)
    try:
        await connection.execute("create schema if not exists vendorlens_internal")
        await connection.execute(
            "create table if not exists vendorlens_internal.schema_migrations ("
            "name text primary key, checksum char(64) not null, "
            "applied_at timestamptz not null default now())"
        )
        for path in files:
            checksum = migration_checksum(path)
            applied = await connection.fetchval(
                "select checksum from vendorlens_internal.schema_migrations where name = $1",
                path.name,
            )
            if applied is not None:
                if applied != checksum:
                    raise RuntimeError(f"checksum mismatch for applied migration {path.name}")
                continue
            async with connection.transaction():
                await connection.execute(path.read_text(encoding="utf-8"))
                await connection.execute(
                    "insert into vendorlens_internal.schema_migrations(name, checksum) "
                    "values ($1, $2)",
                    path.name,
                    checksum,
                )
    finally:
        await connection.execute("select pg_advisory_unlock($1)", MIGRATION_LOCK_ID)
        await connection.close()


def run() -> None:
    database_url = os.environ.get("VENDORLENS_DATABASE_URL")
    if not database_url:
        raise RuntimeError("VENDORLENS_DATABASE_URL is required for migrations")
    asyncio.run(apply_migrations(database_url))


if __name__ == "__main__":
    run()
