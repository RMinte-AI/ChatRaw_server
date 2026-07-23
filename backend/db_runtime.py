import sqlite3
from contextlib import contextmanager
from pathlib import Path


DEFAULT_BUSY_TIMEOUT_MS = 5_000


def open_database(
    db_path: str,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    read_only: bool = False,
) -> sqlite3.Connection:
    path = Path(db_path).resolve()
    if read_only:
        connection = sqlite3.connect(
            f"{path.as_uri()}?mode=ro",
            uri=True,
            timeout=busy_timeout_ms / 1_000,
        )
    else:
        connection = sqlite3.connect(
            str(path),
            timeout=busy_timeout_ms / 1_000,
        )

    connection.row_factory = sqlite3.Row
    connection.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


@contextmanager
def database_connection(
    db_path: str,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    write: bool = False,
    immediate: bool = False,
):
    connection = open_database(
        db_path,
        busy_timeout_ms=busy_timeout_ms,
        read_only=not write,
    )
    try:
        if write and immediate:
            connection.execute("BEGIN IMMEDIATE")
        yield connection
        if write:
            connection.commit()
    except BaseException:
        if write:
            connection.rollback()
        raise
    finally:
        connection.close()
