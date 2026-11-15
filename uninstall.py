#!/usr/bin/env python3
import os
import re
import shutil
import stat
import sys
import tempfile
import time

SECTION_RE = re.compile(r"(?ms)^\[status_line\][ \t]*\r?\n.*?(?=^\[|\Z)")


def atomic_write(path, text):
    directory = os.path.dirname(path)
    existing_mode = stat.S_IMODE(os.stat(path).st_mode)
    fd, temporary = tempfile.mkstemp(prefix=".tui-", dir=directory)
    try:
        os.fchmod(fd, existing_mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def uninstall(tui_path, plugin_dir):
    if not os.path.exists(tui_path):
        print("No tui.toml found; nothing to remove")
        return 0
    text = open(tui_path, encoding="utf-8").read()
    if plugin_dir not in text and plugin_dir.replace("\\", "\\\\") not in text:
        print("This plugin is not configured; nothing to remove")
        return 0

    backup = tui_path + "." + time.strftime("%Y%m%d-%H%M%S") + ".bak"
    shutil.copy2(tui_path, backup)
    print("Backup: " + backup)

    def replace_section(match):
        body = match.group(0)

        def is_ours(line):
            if not re.match(r"\s*command\s*=", line):
                return False
            value = line.split("=", 1)[1].replace("\\\\", "\\")
            return plugin_dir in value and "statusline.py" in value

        body = "\n".join(line for line in body.split("\n") if not is_ours(line))
        remainder = body.split("\n", 1)[1] if "\n" in body else ""
        if not re.search(r"(?m)^[a-zA-Z_]+\s*=", remainder):
            return ""
        return body

    text = SECTION_RE.sub(replace_section, text)
    atomic_write(tui_path, text)
    print("Removed the plugin status-line command from: " + tui_path)
    print("Run /reload-tui in Kimi Code to restore the default status line.")
    return 0


def main():
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    kimi_home = os.environ.get("KIMI_CODE_HOME", os.path.expanduser("~/.kimi-code"))
    return uninstall(os.path.join(kimi_home, "tui.toml"), plugin_dir)


if __name__ == "__main__":
    sys.exit(main())
