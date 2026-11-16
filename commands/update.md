---
description: Update the plugin to the latest stable GitHub release
---

Update Kimi Quota Statusline Secure:

1. Use Bash to run `python3 ~/.kimi-code/plugins/managed/kimi-quota-statusline-secure/update.py`. On Windows, run `python update.py` from the managed plugin directory. If the default path does not exist, locate `update.py` in the current managed plugin directory.
2. The updater fetches the latest stable release from the official project repository, validates its archive and security policy, backs up the current installation, and updates the managed copy and `installed.json` together.
3. If the system asks the user to approve the command, explain that approval is required. If the user declines or cancels, stop and report that the update was cancelled; do not bypass the cancellation.
4. After a successful update, tell the user to run `/reload` and `/reload-tui`. If already up to date, no reload is needed.
5. Do not install dependencies, use GitHub credentials, or replace the updater with a different download command.
