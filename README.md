# claude-dashboard

Local web dashboard for monitoring Claude account quotas and usage across multiple accounts.

![dashboard preview](https://github.com/user-attachments/assets/placeholder)

## What it shows

- **Quota bars** — 5h and 7d rate limit usage with time-to-reset (populated after first session)
- **Today** — messages, sessions, tool calls
- **Last 7 days** — messages and session count
- **Models** — output token breakdown per model
- **All-time** — total messages, sessions, first active date

## Setup

### 1. Account directories

Claude Code stores each account's data under a directory prefix. Create one per account:

```
~/.claude              # personal / default
~/.claude-account1     # account 2
~/.claude-account2     # account 3
~/.claude-account3     # account 4
~/.claude-account4     # account 5
```

### 2. Configure accounts in server.py

Edit the `ACCOUNTS` list to match your setup:

```python
ACCOUNTS = [
    {"name": "Display Name", "alias": "your-alias", "dir": "/Users/you/.claude-account1"},
    ...
]
```

### 3. Enable quota tracking (optional)

To see 5h/7d quota bars, add this block to your `statusline-command.sh` after the rate limit variables are parsed:

```bash
if [ -n "${CLAUDE_CONFIG_DIR:-}" ] && [ -d "${CLAUDE_CONFIG_DIR}" ]; then
  _rl_now=$(date +%s)
  echo "$input" | jq "{updated_at: $_rl_now, five_hour: .rate_limits.five_hour, seven_day: .rate_limits.seven_day}" > "${CLAUDE_CONFIG_DIR}/rate-limits-cache.json" 2>/dev/null || true
fi
```

And configure `statusLine` in each account's `settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash /path/to/statusline-command.sh"
  }
}
```

Quota data updates automatically each time a session turn completes.

### 4. Shell alias

Add to `~/.zshrc` or `~/.bashrc`:

```bash
function claude-dashboard() {
  if ! lsof -ti:4242 >/dev/null 2>&1; then
    nohup python3 ~/path/to/dashboard/server.py >/dev/null 2>&1 &
    sleep 0.4
  fi
  open http://localhost:4242
}
```

### 5. Run

```bash
claude-dashboard
```

Or manually:

```bash
python3 server.py
# open http://localhost:4242
```

No dependencies — stdlib only.
