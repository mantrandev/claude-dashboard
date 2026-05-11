#!/usr/bin/env python3
import json, os, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta

PORT = 4242
HOME = os.path.expanduser("~")

ACCOUNTS = [
    {"name": "Jang",     "alias": "claude-g",        "dir": f"{HOME}/.claude-account1"},
    {"name": "Man",      "alias": "claude-crossian",  "dir": f"{HOME}/.claude-account2"},
    {"name": "Hao",      "alias": "claude-h",         "dir": f"{HOME}/.claude-account3"},
    {"name": "Tan",      "alias": "claude-t",         "dir": f"{HOME}/.claude-account4"},
    {"name": "personal", "alias": "claude-mine",      "dir": f"{HOME}/.claude"},
]

MODEL_SHORT = {
    "claude-opus-4-7":            "Opus 4.7",
    "claude-opus-4-6":            "Opus 4.6",
    "claude-sonnet-4-6":          "Sonnet 4.6",
    "claude-haiku-4-5-20251001":  "Haiku 4.5",
    "claude-sonnet-4-5-20250929": "Sonnet 4.5",
    "claude-opus-4-5-20251101":   "Opus 4.5",
}

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None

def fmt_num(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)

def time_until(ts):
    diff = int(ts) - int(time.time())
    if diff <= 0:
        return "now"
    h, rem = divmod(diff, 3600)
    m = rem // 60
    if h >= 24:
        d, hr = divmod(h, 24)
        return f"{d}d {hr}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"

def bar_color(pct):
    if pct >= 80:
        return "#f85149"
    if pct >= 50:
        return "#f0883e"
    return "#3fb950"

def render_quota_bar(label, pct, resets_at):
    pct = int(float(pct or 0))
    color = bar_color(pct)
    reset_str = time_until(resets_at) if resets_at and int(resets_at) > 0 else None
    reset_html = f'<span style="color:#6e7681">↺ {reset_str}</span>' if reset_str else ""
    return f"""
      <div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
          <span class="section-label">{label}</span>
          <span style="font-size:11px;color:{color}">{pct}% &nbsp;{reset_html}</span>
        </div>
        <div style="background:#21262d;height:6px;border-radius:3px;overflow:hidden">
          <div style="width:{pct}%;height:100%;background:{color};border-radius:3px"></div>
        </div>
      </div>"""

def last_n_days(daily, n):
    cutoff = (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
    return [d for d in daily if d["date"] >= cutoff]

def stats_from_history(history_path):
    from collections import defaultdict
    daily = defaultdict(int)
    try:
        path = os.path.realpath(history_path)
        with open(path) as f:
            for line in f:
                try:
                    d = json.loads(line)
                    ts = d.get("timestamp", 0)
                    if ts:
                        date = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                        daily[date] += 1
                except Exception:
                    pass
    except Exception:
        return None
    if not daily:
        return None
    activity = [{"date": k, "messageCount": v, "sessionCount": 0, "toolCallCount": 0}
                for k, v in sorted(daily.items())]
    return {
        "dailyActivity": activity,
        "modelUsage": {},
        "totalMessages": sum(daily.values()),
        "totalSessions": 0,
        "firstSessionDate": sorted(daily.keys())[0],
        "_from_history": True,
    }

def render_card(acc):
    stats  = load_json(f"{acc['dir']}/stats-cache.json")
    if not stats:
        history_path = f"{acc['dir']}/history.jsonl"
        if os.path.exists(history_path):
            stats = stats_from_history(history_path)
    limits = load_json(f"{acc['dir']}/rate-limits-cache.json")
    today  = datetime.now().strftime("%Y-%m-%d")

    # quota section
    if limits:
        fh = limits.get("five_hour") or {}
        sd = limits.get("seven_day") or {}
        updated_at = limits.get("updated_at", 0)
        updated_str = datetime.fromtimestamp(updated_at).strftime("%H:%M") if updated_at else "?"
        quota_html = f"""
      <div class="section-label" style="margin-bottom:6px">Quota</div>
      {render_quota_bar("5h", fh.get("used_percentage", 0), fh.get("resets_at", 0))}
      <div style="height:6px"></div>
      {render_quota_bar("7d", sd.get("used_percentage", 0), sd.get("resets_at", 0))}
      <div style="font-size:10px;color:#484f58;margin-top:2px">Last session update: {updated_str}</div>
      <div class="divider"></div>"""
    else:
        quota_html = f'<div class="no-data">No quota data — active session required</div><div class="divider"></div>'

    # stats section
    if not stats:
        return f"""
    <div class="card">
      <div class="card-header">
        <span class="account-name">{acc['name']}</span>
        <span class="alias">{acc['alias']}</span>
      </div>
      {quota_html}
      <div class="no-data">No usage stats</div>
    </div>"""

    daily     = stats.get("dailyActivity", [])
    daily_map = {d["date"]: d for d in daily}
    today_d   = daily_map.get(today, {})

    msgs_today     = today_d.get("messageCount", 0)
    sessions_today = today_d.get("sessionCount", 0)
    tools_today    = today_d.get("toolCallCount", 0)

    week      = last_n_days(daily, 7)
    msgs_7d   = sum(d["messageCount"] for d in week)
    sessions_7d = sum(d["sessionCount"] for d in week)

    total_msgs     = stats.get("totalMessages", 0)
    total_sessions = stats.get("totalSessions", 0)
    first_date     = (stats.get("firstSessionDate") or "")[:10] or "?"
    last_active    = daily[-1]["date"] if daily else "?"

    model_rows = ""
    for mid, mu in sorted(stats.get("modelUsage", {}).items(), key=lambda x: -(x[1].get("outputTokens", 0))):
        out_tok = mu.get("outputTokens", 0)
        if not out_tok:
            continue
        short = MODEL_SHORT.get(mid, mid.split("-")[-1])
        model_rows += f'<div class="model-row"><span class="model-name">{short}</span><span class="model-tok">{fmt_num(out_tok)} out</span></div>'

    return f"""
    <div class="card">
      <div class="card-header">
        <span class="account-name">{acc['name']}</span>
        <span class="alias">{acc['alias']}</span>
      </div>
      {quota_html}
      <div class="section-label">Today</div>
      <div class="stat-row">
        <div class="stat"><div class="stat-val">{fmt_num(msgs_today)}</div><div class="stat-lbl">messages</div></div>
        <div class="stat"><div class="stat-val">{sessions_today}</div><div class="stat-lbl">sessions</div></div>
        <div class="stat"><div class="stat-val">{fmt_num(tools_today)}</div><div class="stat-lbl">tool calls</div></div>
      </div>

      <div class="section-label">Last 7 days</div>
      <div class="stat-row">
        <div class="stat"><div class="stat-val">{fmt_num(msgs_7d)}</div><div class="stat-lbl">messages</div></div>
        <div class="stat"><div class="stat-val">{sessions_7d}</div><div class="stat-lbl">sessions</div></div>
      </div>

      <div class="divider"></div>
      <div class="section-label">Models</div>
      <div class="model-list">{model_rows or '<span class="dim">—</span>'}</div>

      <div class="divider"></div>
      <div class="footer-row">
        <span class="dim">Since {first_date}</span>
        <span class="dim">{fmt_num(total_msgs)} msgs · {total_sessions} sessions</span>
      </div>
      <div class="footer-row">
        <span class="dim">Last active: {last_active}</span>
      </div>
    </div>"""

def generate_html():
    cards   = "\n".join(render_card(a) for a in ACCOUNTS)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Claude Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d1117; color: #e6edf3; font-family: 'JetBrains Mono', 'SF Mono', monospace; padding: 28px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 18px; display: flex; flex-direction: column; gap: 10px; }}
  .card-header {{ display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid #30363d; padding-bottom: 10px; margin-bottom: 2px; }}
  .account-name {{ font-size: 15px; font-weight: 600; color: #58a6ff; }}
  .alias {{ font-size: 11px; color: #484f58; }}
  .section-label {{ font-size: 10px; color: #6e7681; text-transform: uppercase; letter-spacing: 0.6px; }}
  .stat-row {{ display: flex; justify-content: space-around; }}
  .stat {{ text-align: center; }}
  .stat-val {{ font-size: 20px; color: #e6edf3; font-weight: 600; }}
  .stat-lbl {{ font-size: 10px; color: #6e7681; margin-top: 2px; }}
  .model-list {{ display: flex; flex-direction: column; gap: 4px; }}
  .model-row {{ display: flex; justify-content: space-between; font-size: 12px; }}
  .model-name {{ color: #c9d1d9; }}
  .model-tok {{ color: #6e7681; }}
  .divider {{ border-top: 1px solid #21262d; }}
  .footer-row {{ display: flex; justify-content: space-between; font-size: 10px; }}
  .dim {{ color: #484f58; }}
  .no-data {{ color: #484f58; font-size: 12px; font-style: italic; padding: 4px 0; }}
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:20px">
  <div>
    <div style="font-size:18px;color:#f0883e;font-weight:600">Claude Accounts</div>
    <div style="font-size:11px;color:#484f58;margin-top:2px">Refreshed {now_str} &nbsp;·&nbsp; <a href="/" style="color:#58a6ff;text-decoration:none">↺ refresh</a></div>
  </div>
</div>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px">
{cards}
</div>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        html = generate_html()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    s = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"http://localhost:{PORT}")
    s.serve_forever()
