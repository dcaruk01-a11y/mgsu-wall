"""
Пакет core.

Если заданы переменные TURSO_DATABASE_URL и TURSO_AUTH_TOKEN —
все модули автоматически используют Turso вместо локального SQLite.
Это делается через подмену sys.modules['aiosqlite'] до того,
как его импортирует первый модуль из core.
"""
import os
import sys

TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "").strip()
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()

if TURSO_URL and TURSO_TOKEN:
    try:
        from . import turso_shim as _shim
        sys.modules["aiosqlite"] = _shim
        print("✅ Turso mode enabled:", TURSO_URL)
    except Exception as e:
        print("❌ Turso shim failed:", e)
        print("   falling back to local SQLite")
else:
    print("ℹ️ Local SQLite mode (no TURSO_DATABASE_URL)")
