---
description: Configure status-line items, colors, thresholds, and reset countdowns
---

Configure Kimi Quota Statusline Secure according to the user's request:

$ARGUMENTS

1. Determine `KIMI_CODE_HOME`; use `~/.kimi-code` when it is unset. The settings file is `$KIMI_CODE_HOME/quota-statusline.json`.
2. Read the existing settings file if present and preserve unrelated fields. If it does not exist, create a minimal JSON file containing only the requested settings.
3. Supported fields:
   - `items`: an ordered array containing any of `mode`, `model`, `plan`, `5h`, `7d`, `month`, `git`, `cwd`.
   - `colors`: boolean.
   - `warning_below`: number from 0 to 100.
   - `critical_below`: number from 0 to 100 and no greater than `warning_below`.
   - `show_reset`: boolean.
4. Do not modify `statusline.py`, `tui.toml`, credentials, cache files, or the plugin manifest. Do not add hooks or run installation commands.
5. Validate the resulting JSON and show the user the updated settings. A reload is unnecessary because the status-line command reads this file on each run.

Default settings:

```json
{
  "items": ["mode", "model", "plan", "5h", "7d", "month", "git", "cwd"],
  "colors": true,
  "warning_below": 20,
  "critical_below": 10,
  "show_reset": true
}
```

Colors apply only to quota blocks: green at or above `warning_below`, orange below it, and red below `critical_below`. `NO_COLOR` and `KIMI_QUOTA_NOCOLOR=1` disable ANSI colors regardless of this configuration. Unavailable quota windows are omitted.
