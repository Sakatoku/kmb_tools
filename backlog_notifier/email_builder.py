"""チケット一覧から .eml ファイルを生成するモジュール。"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# メール本文の HTML テンプレート（依存ライブラリを増やさないよう f-string で生成）
_HTML_STYLE = """\
<style>
  body { font-family: "Helvetica Neue", Arial, sans-serif; color: #333; }
  h2   { color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 6px; }
  p.summary { color: #555; }
  table { border-collapse: collapse; width: 100%; margin-top: 16px; }
  th  { background: #1a73e8; color: #fff; text-align: left;
        padding: 8px 12px; font-size: 13px; }
  td  { padding: 8px 12px; font-size: 13px; border-bottom: 1px solid #e0e0e0;
        vertical-align: top; }
  tr:hover td { background: #f5f9ff; }
  .badge-new    { background: #34a853; color: #fff; border-radius: 4px;
                  padding: 2px 6px; font-size: 11px; }
  .badge-update { background: #fbbc04; color: #333; border-radius: 4px;
                  padding: 2px 6px; font-size: 11px; }
  a { color: #1a73e8; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .footer { margin-top: 24px; font-size: 11px; color: #999; }
</style>"""


def build_eml(
    issues: list[dict[str, Any]],
    space_id: str,
    project_key: str,
    hours: int,
    from_addr: str,
    to_addr: str,
    subject: str,
    output_dir: str | Path,
) -> Path:
    """チケット一覧から .eml ファイルを生成して保存し、ファイルパスを返す。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    html_body = _render_html(issues, space_id, project_key, hours)
    text_body = _render_plain(issues, space_id, hours)

    msg = MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = datetime.now(tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg["MIME-Version"] = "1.0"

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    eml_path = output_path / f"backlog_notify_{timestamp}.eml"
    eml_path.write_text(msg.as_string(), encoding="utf-8")

    logger.info("EMLファイルを保存しました: %s", eml_path)
    return eml_path


# ------------------------------------------------------------------
# Internal renderers
# ------------------------------------------------------------------

def _render_html(
    issues: list[dict[str, Any]],
    space_id: str,
    project_key: str,
    hours: int,
) -> str:
    if not issues:
        body_content = "<p>対象期間内に更新・追加されたチケットはありませんでした。</p>"
    else:
        rows = "\n".join(_issue_row(i, space_id) for i in issues)
        body_content = f"""
        <table>
          <thead>
            <tr>
              <th>種別</th>
              <th>チケットID</th>
              <th>件名</th>
              <th>状態</th>
              <th>担当者</th>
              <th>更新日時</th>
            </tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>"""

    count_label = f"{len(issues)} 件" if issues else "0 件"
    project_esc = html.escape(project_key)

    return f"""\
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8">{_HTML_STYLE}</head>
<body>
  <h2>Backlog 更新チケット通知</h2>
  <p class="summary">
    プロジェクト: <strong>{project_esc}</strong> ／
    直近 <strong>{hours} 時間</strong> 以内の更新・新規追加 ：
    <strong>{count_label}</strong>
  </p>
  {body_content}
  <p class="footer">このメールは kmb_tools/backlog_notifier によって自動生成されました。</p>
</body>
</html>"""


def _issue_row(issue: dict[str, Any], space_id: str) -> str:
    change_type = issue.get("_change_type", "更新")
    badge_class = "badge-new" if change_type == "新規追加" else "badge-update"
    badge = f'<span class="{badge_class}">{html.escape(change_type)}</span>'

    issue_key = html.escape(issue.get("issueKey", ""))
    issue_url = f"https://{html.escape(space_id)}.backlog.com/view/{issue_key}"
    summary = html.escape(issue.get("summary", ""))
    status = html.escape(_nested(issue, "status", "name"))
    assignee = html.escape(_nested(issue, "assignee", "name") or "未設定")
    updated = _format_dt(issue.get("updated", ""))

    return (
        f"<tr>"
        f"<td>{badge}</td>"
        f'<td><a href="{issue_url}">{issue_key}</a></td>'
        f"<td>{summary}</td>"
        f"<td>{status}</td>"
        f"<td>{assignee}</td>"
        f"<td>{updated}</td>"
        f"</tr>"
    )


def _render_plain(
    issues: list[dict[str, Any]],
    space_id: str,
    hours: int,
) -> str:
    lines: list[str] = [
        "Backlog 更新チケット通知",
        "=" * 40,
        f"直近 {hours} 時間以内の更新・新規追加: {len(issues)} 件",
        "",
    ]
    if not issues:
        lines.append("対象期間内に更新・追加されたチケットはありませんでした。")
    else:
        for issue in issues:
            issue_key = issue.get("issueKey", "")
            lines.append(f"[{issue.get('_change_type', '更新')}] {issue_key}")
            lines.append(f"  件名    : {issue.get('summary', '')}")
            lines.append(f"  状態    : {_nested(issue, 'status', 'name')}")
            lines.append(f"  担当者  : {_nested(issue, 'assignee', 'name') or '未設定'}")
            lines.append(f"  更新日時: {_format_dt(issue.get('updated', ''))}")
            lines.append(f"  URL     : https://{space_id}.backlog.com/view/{issue_key}")
            lines.append("")

    lines.append("--")
    lines.append("このメールは kmb_tools/backlog_notifier によって自動生成されました。")
    return "\n".join(lines)


def _nested(obj: dict[str, Any], *keys: str) -> str:
    """ネストされた dict から安全に文字列値を取り出す。"""
    cur: Any = obj
    for key in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return cur or ""


def _format_dt(value: str) -> str:
    """Backlog の ISO 8601 文字列を JST 表示に変換する（タイムゾーン変換は行わない）。"""
    if not value:
        return ""
    return value.replace("T", " ").replace("Z", " UTC")
