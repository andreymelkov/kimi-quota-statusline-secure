# Kimi Quota Statusline Secure

A minimal, privacy-focused Kimi Code plugin that displays the **remaining** quota for the rolling 5-hour, 7-day, and monthly windows, plus reset countdowns when supplied by the API.

Example:

```text
5h 77% 2h14m · 7d 59% 3d4h · month 88% 12d1h
```

A `~` prefix marks data older than 10 minutes. Windows unavailable for the current plan are omitted.

## Security and privacy

- No plugin hooks, MCP servers, system-prompt additions, local HTTP server, or session-log access.
- No third-party Python dependencies.
- OAuth access tokens are read only from the existing Kimi Code credential file and are never written to the cache or logs.
- Requests are limited to `https://api.kimi.com/coding/v1/usages` and `https://api.kimi.ai/coding/v1/usages`.
- HTTP redirects, non-HTTPS URLs, non-default ports, URL credentials, and environment-configured proxies are blocked.
- API responses are size-limited and validated before use.
- On POSIX systems, the cache is created with mode `0600`. It contains only quota percentages, reset timestamps, and refresh timestamps—never OAuth tokens, prompts, project paths, or status-line input.
- Background refreshes use a fixed Python command without a shell.
- The installer and uninstaller modify only the plugin's `[status_line].command` entry and back up `tui.toml` first.

The plugin reads `config.toml` only to select the existing managed Kimi Code endpoint and credential slot. It does not refresh OAuth tokens; expired credentials result in cached or unavailable data until Kimi Code refreshes them.

Direct connections are intentional. Users on networks that require an HTTP proxy will see `Kimi quota: unavailable` rather than sending credentials through an implicitly configured proxy.

## Requirements

- Kimi Code CLI 0.30.0 or newer with `[status_line]` support
- Python 3.9 or newer
- An existing OAuth login to Kimi Code

## Install

After publishing the repository, run:

```text
/plugins install https://github.com/andreymelkov/kimi-quota-statusline-secure
```

Then reload Kimi Code to register the plugin commands:

```text
/reload
```

Configure the status line:

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

The custom command replaces the built-in first footer line with the quota display. Other `tui.toml` settings are preserved.

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

Kimi Code may leave the managed plugin copy on disk after removal. The optional cache and lock files can be deleted manually:

```text
~/.kimi-code/quota-statusline-cache.json
~/.kimi-code/quota-statusline-refresh.lock
```

If `KIMI_CODE_HOME` is set, those files and `tui.toml` live under that directory instead.

## License

MIT
