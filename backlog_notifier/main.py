"""Backlog 更新チケット通知ツール エントリーポイント。

使い方:
    python -m backlog_notifier [--config CONFIG_PATH]

オプション:
    --config  設定ファイルのパス（省略時: backlog_notifier/config.yaml）
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from backlog_notifier.backlog_client import BacklogClient
from backlog_notifier.email_builder import build_eml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        logger.error("設定ファイルが見つかりません: %s", config_path)
        sys.exit(1)
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Backlog 更新チケット通知ツール")
    parser.add_argument(
        "--config",
        default="backlog_notifier/config.yaml",
        help="設定ファイルのパス (default: backlog_notifier/config.yaml)",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)

    # --- Backlog 設定 ---
    bl_cfg = config.get("backlog", {})
    space_id: str = bl_cfg["space_id"]
    api_key: str = bl_cfg["api_key"]
    project_key: str = bl_cfg["project_key"]
    hours: int = int(bl_cfg.get("hours", 24))

    # --- メール設定 ---
    mail_cfg = config.get("email", {})
    from_addr: str = mail_cfg["from"]
    to_addr: str = mail_cfg["to"]
    subject: str = mail_cfg.get("subject", "Backlog 更新チケット通知")
    output_dir: str = mail_cfg.get("output_dir", "./output")

    logger.info(
        "チケット取得開始 — プロジェクト: %s、対象: 直近 %d 時間", project_key, hours
    )

    # client = BacklogClient(space_id=space_id, api_key=api_key)
    client = BacklogClient(
        space_id="dummy",
        api_key="dummy",
        base_url="http://localhost:8080/api/v2",
    )

    try:
        issues = client.get_recently_updated_issues(
            project_key=project_key,
            hours=hours,
        )
    except Exception as exc:
        logger.error("Backlog API エラー: %s", exc)
        sys.exit(1)

    logger.info("取得チケット数: %d 件", len(issues))

    eml_path = build_eml(
        issues=issues,
        space_id=space_id,
        project_key=project_key,
        hours=hours,
        from_addr=from_addr,
        to_addr=to_addr,
        subject=subject,
        output_dir=output_dir,
    )

    print(f"✅ EMLファイルを生成しました: {eml_path}")


if __name__ == "__main__":
    main()
