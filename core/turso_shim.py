"""
Замена aiosqlite на Turso через libsql-client.
Автоматически подменяет sys.modules['aiosqlite'] когда задан TURSO_DATABASE_URL.
Совместим с текущим кодом: async with aiosqlite.connect(path) as db.
"""
import os

TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "").strip()
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()


class _Cursor:
    """Имитирует aiosqlite.Cursor."""

    def __init__(self, rows, lastrowid=None):
        self._rows = list(rows or [])
        self._idx = 0
        self.lastrowid = lastrowid

    async def fetchone(self):
        if self._idx < len(self._rows):
            row = self._rows[self._idx]
            self._idx += 1
            return row
        return None

    async def fetchall(self):
        rows = self._rows[self._idx:]
        self._idx = len(self._rows)
        return rows


class _Conn:
    """Имитирует aiosqlite.Connection."""

    def __init__(self, client):
        self._client = client

    async def execute(self, sql, params=None):
        params = list(params or [])
        try:
            result_set = await self._client.execute(sql, params)
        except Exception as e:
            print("Turso execute error:", e)
            print("SQL:", sql[:200])
            print("Params:", params)
            raise
        rows = list(getattr(result_set, "rows", []) or [])
        lastrowid = getattr(result_set, "last_insert_rowid", None)
        return _Cursor(rows, lastrowid)

    async def commit(self):
        # libsql-client работает в autocommit-режиме
        return

    async def close(self):
        try:
            await self._client.close()
        except Exception:
            pass


class _ConnectCtx:
    """Контекстный менеджер для async with aiosqlite.connect(path)."""

    def __init__(self, url=None):
        self._url = url
        self._client = None

    async def __aenter__(self):
        import libsql_client
        self._client = libsql_client.create_client(
            url=TURSO_URL,
            auth_token=TURSO_TOKEN,
        )
        # на случай, если create_client возвращает корутину
        if hasattr(self._client, "__await__"):
            self._client = await self._client
        return _Conn(self._client)

    async def __aexit__(self, exc_type, exc, tb):
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
        return False


def connect(path=None):
    """Тот же интерфейс что у aiosqlite.connect. path игнорируется."""
    return _ConnectCtx()
