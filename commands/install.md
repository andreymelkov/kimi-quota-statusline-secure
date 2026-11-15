---
description: Configure the secure quota status line
---

Install Kimi Quota Statusline Secure:

1. Use Bash to run `python3 ~/.kimi-code/plugins/managed/kimi-quota-statusline-secure/install.py`. On Windows, run `python install.py` from the managed plugin directory. If the default path does not exist, locate `install.py` in the current managed plugin directory.
2. The installer backs up `tui.toml` and sets only `[status_line].command`. It does not install dependencies or run external validation tools.
3. Tell the user to run `/reload-tui` to activate the status line.
