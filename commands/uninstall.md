---
description: Restore the default Kimi Code status line
---

Uninstall the status-line configuration for Kimi Quota Statusline Secure:

1. Use Bash to run `python3 ~/.kimi-code/plugins/managed/kimi-quota-statusline-secure/uninstall.py`. On Windows, run `python uninstall.py` from the managed plugin directory. If the default path does not exist, locate `uninstall.py` in the current managed plugin directory.
2. The uninstaller backs up `tui.toml` and removes only this plugin's `[status_line].command` entry.
3. Tell the user to run `/reload-tui`.
4. To remove the plugin commands as well, the user can run `/plugins remove kimi-quota-statusline-secure` and then `/reload`.
