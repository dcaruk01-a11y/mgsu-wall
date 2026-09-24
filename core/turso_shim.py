"""
Замена aiosqlite на Turso через прямой HTTP API (v2/pipeline).
Работает с любым Python, использует httpx (уже в проекте).
"""
import os
import httpx

TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "").strip()
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()

# Приводим URL к виду https://xxx.turso.io
if TURSO_URL.startswith("libsql://"):
    BASE_URL = "https://" + TURSO_URL[len("libsql://"):]
elif TURSO_URL.startswith("turso://"):
    BASE_URL = "https://" + TURSO_URL[len("turso://"):]
elif TURSO_URL.startswith("https://"):
    BASE_URL = TURSO_URL
else:
    BASE_URL = TURSO_URL

PIPELINE_URL = BASE_URL.rstrip("/") + "/v2/pipeline"


def _to_turso_arg(v):
    """Python-значение → формат аргумента Turso."""
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": "1" if v else "0"}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    if isinstance(v, (bytes, bytearray)):
        import base64
        return {"type": "blob", "value": base64.b64encode(bytes(v)).decode()}
    return {"type": "text", "value": str(v)}


def _from_turso_cell(cell):
    """Ячейка Turso → Python-значение."""
    if cell is None:
        return None
    t = cell.get("type")
    v = cell.get("value")
    if t == "null":
        return None
    if t == "integer":
        try:
            return int(v)
        except Exception:
            return v
    if t == "float":
        try:
            return float(v)
        except Exception:
            return v
    if t == "blob":
        import base64
        try:
            return base64.b64decode(v or "")
        except Exception:
            return v
    return v


class _Cursor:
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
    def __init__(self, client):
        self._client = client

    async def execute(self, sql, params=None):
        params = list(params or [])
        args = [_to_turso_arg(p) for p in params]

        payload = {
            "requests": [
                {"type": "execute", "stmt": {"sql": sql, "args": args}},
                {"type": "close"},
            ]
        }
        headers = {
            "Authorization": f"Bearer {TURSO_TOKEN}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as hc:
            r = await hc.post(PIPELINE_URL, json=payload, headers=headers)

        if r.status_code != 200:
            print("Turso HTTP error:", r.status_code, r.text[:300])
            raise RuntimeError(f"Turso HTTP {r.status_code}: {r.text[:200]}")

        data = r.json()
        results = data.get("results", [])
        if not results:
            return _Cursor([], None)

        first = results[0]
        if first.get("type") != "ok":
            err = first.get("error", {})
            print("Turso query error:", err)
            print("SQL:", sql[:200])
            print("Params:", params)
            raise RuntimeError(f"Turso error: {err.get('message', 'unknown')}")

        response = first.get("response", {}) or {}
        result = response.get("result", {}) or {}

        # rows — массив массивов ячеек
        raw_rows = result.get("rows", []) or []
        rows = [tuple(_from_turso_cell(cell) for cell in row) for row in raw_rows]

        # lastrowid — приходит при INSERT
        lastrowid = result.get("last_insert_rowid")
        if lastrowid is not None:
            try:
                lastrowid = int(lastrowid)
            except Exception:
                pass

        return _Cursor(rows, lastrowid)

    async def commit(self):
        return

    async def close(self):
        return


class _ConnectCtx:
    def __init__(self, url=None):
        self._url = url

    async def __aenter__(self):
        return _Conn(None)

    async def __aexit__(self, exc_type, exc, tb):
        return False


def connect(path=None):
    return _ConnectCtx()
