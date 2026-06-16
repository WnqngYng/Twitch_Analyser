from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def write_json_report(analysis: dict[str, Any], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")


def write_html_report(analysis: dict[str, Any], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_html(analysis), encoding="utf-8")


def render_html(analysis: dict[str, Any]) -> str:
    summary = analysis.get("summary", {})
    events = analysis.get("events", [])
    campaign_recs = analysis.get("recommendations", {}).get("campaign", [])
    event_recs = analysis.get("recommendations", {}).get("events", {})
    chart_data = json.dumps(
        [
            {
                "id": event["event_id"],
                "lift": event["engagement_lift"],
                "sentiment": event["response"]["sentiment_avg"],
                "messages": event["response"]["message_count"],
            }
            for event in events
        ]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Twitch Promotion Campaign Report</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #64748b;
      --line: #d8dee9;
      --panel: #ffffff;
      --page: #f5f7fb;
      --teal: #0f766e;
      --red: #b42318;
      --amber: #b45309;
      --blue: #2563eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--page);
      line-height: 1.5;
    }}
    header {{
      background: #101828;
      color: #fff;
      padding: 28px clamp(20px, 5vw, 64px);
      border-bottom: 4px solid var(--teal);
    }}
    header h1 {{
      margin: 0 0 6px;
      font-size: clamp(1.8rem, 4vw, 3rem);
      letter-spacing: 0;
    }}
    header p {{ margin: 0; color: #cbd5e1; }}
    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 24px auto 56px;
    }}
    section {{
      margin: 24px 0;
    }}
    h2 {{
      font-size: 1.15rem;
      margin: 0 0 12px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }}
    .metric, .panel, table {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }}
    .metric {{ padding: 16px; }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 0.84rem;
    }}
    .metric strong {{
      display: block;
      font-size: 1.8rem;
      margin-top: 4px;
    }}
    .panel {{ padding: 18px; }}
    .recommendations {{
      display: grid;
      gap: 10px;
      padding-left: 18px;
      margin: 0;
    }}
    .chart {{
      display: grid;
      gap: 10px;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: 90px 1fr 70px;
      gap: 10px;
      align-items: center;
      font-size: 0.92rem;
    }}
    .bar {{
      height: 12px;
      background: #e2e8f0;
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar span {{
      display: block;
      min-width: 2px;
      height: 100%;
      background: var(--teal);
      border-radius: inherit;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
    }}
    th, td {{
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      font-size: 0.92rem;
    }}
    th {{
      background: #eef2f7;
      color: #334155;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .tag {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      background: #e0f2fe;
      color: #075985;
      font-size: 0.78rem;
      white-space: nowrap;
    }}
    .positive {{ color: var(--teal); font-weight: 700; }}
    .negative {{ color: var(--red); font-weight: 700; }}
    .neutral {{ color: var(--muted); font-weight: 700; }}
    details {{
      margin-top: 10px;
    }}
    summary {{
      cursor: pointer;
      color: var(--blue);
      font-weight: 700;
    }}
    blockquote {{
      margin: 8px 0;
      padding: 8px 10px;
      border-left: 3px solid var(--line);
      background: #f8fafc;
      color: #334155;
    }}
    @media (max-width: 720px) {{
      .bar-row {{ grid-template-columns: 1fr; }}
      table, thead, tbody, th, td, tr {{ display: block; }}
      thead {{ display: none; }}
      tr {{ border-bottom: 1px solid var(--line); }}
      td {{ border: 0; padding: 8px 12px; }}
      td::before {{
        content: attr(data-label);
        display: block;
        font-size: 0.72rem;
        color: var(--muted);
        text-transform: uppercase;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Twitch Promotion Campaign Report</h1>
    <p>Influencer promotion detection, viewer response analysis, and optimization suggestions.</p>
  </header>
  <main>
    <section class="grid">
      {metric("Messages", summary.get("message_count", 0))}
      {metric("Unique Chatters", summary.get("unique_chatters", 0))}
      {metric("Promotions", summary.get("detected_promotions", 0))}
      {metric("Avg Lift", percent(summary.get("avg_engagement_lift", 0)))}
      {metric("Avg Sentiment", summary.get("avg_response_sentiment", 0))}
      {metric("Best Event", summary.get("best_event") or "None")}
    </section>

    <section class="panel">
      <h2>Campaign Recommendations</h2>
      <ol class="recommendations">
        {"".join(f"<li>{html.escape(item)}</li>" for item in campaign_recs)}
      </ol>
    </section>

    <section class="panel">
      <h2>Promotion Performance</h2>
      <div id="chart" class="chart"></div>
    </section>

    <section>
      <h2>Detected Promotional Moments</h2>
      {events_table(events, event_recs)}
    </section>
  </main>
  <script>
    const data = {chart_data};
    const chart = document.querySelector("#chart");
    const maxLift = Math.max(0.1, ...data.map(item => Math.abs(item.lift)));
    if (data.length === 0) {{
      chart.textContent = "No promotional events detected.";
    }} else {{
      chart.innerHTML = data.map(item => {{
        const width = Math.max(2, Math.round((Math.abs(item.lift) / maxLift) * 100));
        const value = `${{Math.round(item.lift * 100)}}%`;
        return `<div class="bar-row">
          <strong>${{item.id}}</strong>
          <div class="bar"><span style="width:${{width}}%"></span></div>
          <span>${{value}}</span>
        </div>`;
      }}).join("");
    }}
  </script>
</body>
</html>
"""


def metric(label: str, value: object) -> str:
    return f'<div class="metric"><span>{html.escape(label)}</span><strong>{html.escape(str(value))}</strong></div>'


def percent(value: float) -> str:
    return f"{round(value * 100)}%"


def events_table(events: list[dict[str, Any]], event_recs: dict[str, list[str]]) -> str:
    if not events:
        return '<div class="panel">No promotional events were detected.</div>'

    rows = []
    for event in events:
        response = event["response"]
        sentiment_class = "positive" if response["sentiment_avg"] > 0.05 else "negative" if response["sentiment_avg"] < -0.05 else "neutral"
        samples = "".join(
            f"<blockquote><strong>{html.escape(sample['user'])}</strong>: {html.escape(sample['message'])}</blockquote>"
            for sample in response.get("sample_comments", [])
        )
        recs = "".join(f"<li>{html.escape(item)}</li>" for item in event_recs.get(event["event_id"], []))
        rows.append(
            f"""<tr>
  <td data-label="Event"><strong>{html.escape(event["event_id"])}</strong><br>{html.escape(event["timestamp"])}</td>
  <td data-label="Influencer">{html.escape(event["influencer"])}<br><span class="tag">{html.escape(event["cta_type"])}</span></td>
  <td data-label="Message">{html.escape(event["message"])}</td>
  <td data-label="Response">{response["message_count"]} messages<br>{response["unique_chatters"]} chatters<br>{percent(event["engagement_lift"])} lift</td>
  <td data-label="Sentiment"><span class="{sentiment_class}">{response["sentiment_avg"]}</span><br>{html.escape(str(response.get("sentiment_counts", {})))}</td>
  <td data-label="Details">
    <details>
      <summary>View comments and suggestions</summary>
      {samples}
      <ol>{recs}</ol>
    </details>
  </td>
</tr>"""
        )

    return f"""<table>
  <thead>
    <tr>
      <th>Event</th>
      <th>Influencer</th>
      <th>Promotion</th>
      <th>Response</th>
      <th>Sentiment</th>
      <th>Details</th>
    </tr>
  </thead>
  <tbody>
    {"".join(rows)}
  </tbody>
</table>"""
