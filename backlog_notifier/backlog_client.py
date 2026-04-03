"""Backlog REST API クライアント。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)


class BacklogClient:
    """Backlog API v2 の薄いラッパー。"""

    def __init__(self, space_id: str, api_key: str, base_url: str | None = None) -> None:
        self._base_url = base_url or f"https://{space_id}.backlog.com/api/v2"
        self._api_key = api_key
        self._session = requests.Session()
        self._session.params = {"apiKey": api_key}  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_project_id(self, project_key: str) -> int:
        """プロジェクトキーからプロジェクト ID を取得する。"""
        resp = self._session.get(f"{self._base_url}/projects/{project_key}")
        resp.raise_for_status()
        return int(resp.json()["id"])

    def get_recently_updated_issues(
        self,
        project_key: str,
        hours: int,
    ) -> list[dict[str, Any]]:
        """指定時間以内に更新または作成されたチケットを全件返す。

        Backlog API の updatedSince / createdSince は ISO 8601 日付（YYYY-MM-DD）
        しか受け付けないため、取得後に Python 側で時刻フィルタをかける。
        """
        since_dt = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
        project_id = self.get_project_id(project_key)

        issues: list[dict[str, Any]] = []
        offset = 0
        count = 100  # Backlog API の最大件数

        while True:
            params = {
                "projectId[]": project_id,
                "count": count,
                "offset": offset,
                "order": "desc",
                "sort": "updated",
            }
            resp = self._session.get(f"{self._base_url}/issues", params=params)
            resp.raise_for_status()
            batch: list[dict[str, Any]] = resp.json()

            if not batch:
                break

            for issue in batch:
                updated = _parse_backlog_datetime(issue.get("updated") or "")
                created = _parse_backlog_datetime(issue.get("created") or "")

                if updated and updated >= since_dt:
                    issue["_change_type"] = (
                        "新規追加" if created and created >= since_dt else "更新"
                    )
                    issues.append(issue)
                elif created and created >= since_dt:
                    issue["_change_type"] = "新規追加"
                    issues.append(issue)
                else:
                    # updated DESC で並んでいるので、閾値を下回ったら終了
                    return issues

            if len(batch) < count:
                break
            offset += count

        return issues

    def build_issue_url(self, space_id: str, project_key: str, issue_key: str) -> str:
        return f"https://{space_id}.backlog.com/view/{issue_key}"


# ------------------------------------------------------------------
# Internal utilities
# ------------------------------------------------------------------

def _parse_backlog_datetime(value: str) -> datetime | None:
    """Backlog が返す ISO 8601 文字列を timezone-aware datetime に変換する。"""
    if not value:
        return None
    try:
        # Backlog は "2024-01-23T12:34:56Z" 形式で返す
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("日時パース失敗: %s", value)
        return None
