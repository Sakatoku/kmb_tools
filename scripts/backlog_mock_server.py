#!/usr/bin/env python3
"""Backlog API モックサーバー（ローカルテスト用）。

標準ライブラリのみで動作します。追加インストール不要。

使い方:
    python scripts/backlog_mock_server.py [--port PORT]
    # デフォルト: http://localhost:8080

BacklogClient への接続:
    client = BacklogClient(
        space_id="dummy",
        api_key="dummy",
        base_url="http://localhost:8080/api/v2",
    )

実装済みエンドポイント:
    GET /api/v2/projects/{projectKey}
    GET /api/v2/issues
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# サンプルデータ
# ---------------------------------------------------------------------------

_NOW = datetime.now(tz=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


PROJECTS: dict[str, dict] = {
    "TEST": {"id": 100, "projectKey": "TEST", "name": "テストプロジェクト", "archived": False},
    "DEMO": {"id": 200, "projectKey": "DEMO", "name": "デモプロジェクト", "archived": False},
}

ISSUES: list[dict] = [
    {
        "id": 1001,
        "issueKey": "TEST-1",
        "projectId": 100,
        "summary": "サンプルチケット（更新済み）",
        "description": "このチケットは直近1時間以内に更新されました。",
        "status": {"id": 2, "name": "処理中"},
        "assignee": {"id": 10, "name": "山田 太郎"},
        "priority": {"id": 3, "name": "中"},
        "created": _iso(_NOW - timedelta(hours=48)),
        "updated": _iso(_NOW - timedelta(hours=1)),
    },
    {
        "id": 1002,
        "issueKey": "TEST-2",
        "projectId": 100,
        "summary": "新規チケット（直近2時間）",
        "description": "このチケットは直近2時間以内に作成されました。",
        "status": {"id": 1, "name": "未対応"},
        "assignee": None,
        "priority": {"id": 2, "name": "高"},
        "created": _iso(_NOW - timedelta(hours=2)),
        "updated": _iso(_NOW - timedelta(hours=2)),
    },
    {
        "id": 1003,
        "issueKey": "TEST-3",
        "projectId": 100,
        "summary": "古いチケット（対象外）",
        "description": "このチケットは5日前に更新されました。通常フィルタには引っかかりません。",
        "status": {"id": 3, "name": "処理済み"},
        "assignee": {"id": 11, "name": "鈴木 花子"},
        "priority": {"id": 3, "name": "中"},
        "created": _iso(_NOW - timedelta(days=30)),
        "updated": _iso(_NOW - timedelta(days=5)),
    },
    {
        "id": 2001,
        "issueKey": "DEMO-1",
        "projectId": 200,
        "summary": "デモプロジェクトのチケット",
        "description": "DEMO プロジェクト用サンプルチケットです。",
        "status": {"id": 1, "name": "未対応"},
        "assignee": {"id": 12, "name": "佐藤 次郎"},
        "priority": {"id": 3, "name": "中"},
        "created": _iso(_NOW - timedelta(hours=3)),
        "updated": _iso(_NOW - timedelta(hours=3)),
    },
]

# ---------------------------------------------------------------------------
# ハンドラー
# ---------------------------------------------------------------------------

class BacklogMockHandler(BaseHTTPRequestHandler):

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)

        # GET /api/v2/projects/{projectKey}
        if path.startswith("/api/v2/projects/"):
            project_key = path.removeprefix("/api/v2/projects/")
            project = PROJECTS.get(project_key)
            if project is None:
                self._send_json({"message": "No project."}, status=404)
            else:
                self._send_json(project)
            return

        # GET /api/v2/issues
        if path == "/api/v2/issues":
            project_ids = [int(v) for v in qs.get("projectId[]", [])]
            count = int(qs.get("count", [100])[0])
            offset = int(qs.get("offset", [0])[0])

            filtered = [
                issue for issue in ISSUES
                if not project_ids or issue["projectId"] in project_ids
            ]
            # updatedの降順（サンプルデータは既に降順だが念のためソート）
            filtered.sort(key=lambda i: i["updated"], reverse=True)

            page = filtered[offset: offset + count]
            self._send_json(page)
            return

        self._send_json({"message": "Not found."}, status=404)

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[mock] {self.address_string()} - {fmt % args}")


# ---------------------------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Backlog API モックサーバー")
    parser.add_argument("--port", type=int, default=8080, help="待受ポート (default: 8080)")
    args = parser.parse_args()

    server = HTTPServer(("localhost", args.port), BacklogMockHandler)
    print(f"Backlog モックサーバー起動: http://localhost:{args.port}/api/v2")
    print("終了: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nサーバーを停止しました。")


if __name__ == "__main__":
    main()
