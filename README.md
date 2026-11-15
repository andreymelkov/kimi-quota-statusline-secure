# Kimi Quota Statusline Secure

A minimal, privacy-focused Kimi Code plugin that displays session information and the **remaining** quota for the rolling 5-hour, 7-day, and monthly windows, plus reset countdowns when supplied by the API.

Default example:

```text
MANUAL · K3 · 5h 77% 2h14m · 7d 59% 3d4h · month 88% 12d1h · ⎇ main · project
```

Quota blocks are green by default, orange below 20% remaining, and red below 10%. A `~` prefix marks data older than 10 minutes. Windows unavailable for the current plan are omitted; in particular, newer Kimi plans may not provide a 7-day window.

## Security and privacy

- No plugin hooks, MCP servers, system-prompt additions, local HTTP server, or session-log access.
- No third-party Python dependencies.
- OAuth access tokens are read only from the existing Kimi Code credential file and are never written to the cache or logs.
- Requests are limited to `https://api.kimi.com/coding/v1/usages` and `https://api.kimi.ai/coding/v1/usages`.
- HTTP redirects, non-HTTPS URLs, non-default ports, URL credentials, and environment-configured proxies are blocked.
- API responses are size-limited and validated before use.
- On POSIX systems, the cache is created with mode `0600`. It contains only quota percentages, reset timestamps, and refresh timestamps—never OAuth tokens, prompts, project paths, or status-line input.
- Model, permission mode, Plan mode, Git branch, and working directory come only from the status-line `stdin` snapshot. Snapshot text is stripped of control characters before rendering and is never persisted.
- Background refreshes use a fixed Python command without a shell.
- The installer and uninstaller modify only the plugin's `[status_line].command` entry and back up `tui.toml` first.

The plugin reads `config.toml` only to select the existing managed Kimi Code endpoint and credential slot. It does not refresh OAuth tokens; expired credentials result in cached or unavailable data until Kimi Code refreshes them.

Direct connections are intentional. Users on networks that require an HTTP proxy will see `Kimi quota: unavailable` rather than sending credentials through an implicitly configured proxy.

## Requirements

- Kimi Code CLI 0.30.0 or newer with `[status_line]` support
- Python 3.9 or newer
- An existing OAuth login to Kimi Code

## Install or update

```text
/plugins install https://github.com/andreymelkov/kimi-quota-statusline-secure
/reload
```

For a new installation, configure the status line:

```text
/kimi-quota-statusline-secure:install
/reload-tui
```

For a reproducible installation, use a release or commit URL instead of the moving default branch:

```text
/plugins install https://github.com/andreymelkov/kimi-quota-statusline-secure/commit/<full-commit-sha>
```

For a local checkout:

```text
/plugins install /absolute/path/to/kimi-quota-statusline-secure
/reload
/kimi-quota-statusline-secure:install
/reload-tui
```

The custom command replaces the built-in first footer line with the configurable display. Other `tui.toml` settings are preserved.

## Configuration

The plugin reads `$KIMI_CODE_HOME/quota-statusline.json` on every invocation. If `KIMI_CODE_HOME` is unset, the path is `~/.kimi-code/quota-statusline.json`. The file is optional; defaults are used when it is absent.

Ask Kimi Code to change the settings:

```text
/kimi-quota-statusline-secure:configure hide git and cwd, set warning to 25 and critical to 15
```

Or edit the JSON directly:

```json
{
  "items": ["mode", "model", "plan", "5h", "7d", "month", "git", "cwd"],
  "colors": true,
  "warning_below": 20,
  "critical_below": 10,
  "show_reset": true
}
```

Settings:

| Field | Meaning |
| --- | --- |
| `items` | Ordered blocks to display. Allowed values: `mode`, `model`, `plan`, `5h`, `7d`, `month`, `git`, `cwd`. Remove a block to hide it. `plan` appears only in Plan mode. |
| `colors` | Enables ANSI colors for quota blocks. Defaults to `true`. |
| `warning_below` | Remaining percentage below which a quota becomes orange. Defaults to `20`. |
| `critical_below` | Remaining percentage below which a quota becomes red. Defaults to `10`. Must not exceed `warning_below`. |
| `show_reset` | Shows reset countdowns supplied by the API. Defaults to `true`. |

At exactly `warning_below`, the quota is green; at exactly `critical_below`, it is orange. Set `NO_COLOR` or `KIMI_QUOTA_NOCOLOR=1` to disable colors regardless of the configuration. Changes apply automatically on the next status-line refresh; `/reload-tui` is not required.

## Refresh behavior

The status line reads the local cache and starts at most one detached refresh when the cache is over 60 seconds old. A refresh fetches the official usages endpoint with an 8-second timeout. If fetching fails, existing quota data remains visible and is marked stale after 10 minutes.

## Uninstall

Restore the built-in status line:

```text
/kimi-quota-statusline-secure:uninstall
/reload-tui
```

Remove the plugin commands and managed installation record:

```text
/plugins remove kimi-quota-statusline-secure
/reload
```

Kimi Code may leave the managed plugin copy on disk after removal. Optional plugin files can be deleted manually:

```text
~/.kimi-code/quota-statusline-cache.json
~/.kimi-code/quota-statusline-refresh.lock
~/.kimi-code/quota-statusline.json
```

If `KIMI_CODE_HOME` is set, those files and `tui.toml` live under that directory instead.

## License

MIT
