#!/usr/bin/env python3
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time

SECTION_RE = re.compile(r"(?ms)^\[status_line\][ \t]*\r?\n.*?(?=^\[|\Z)")
COMMAND_RE = re.compile(r"(?m)^command\s*=.*$")
CMD_UNSAFE = set(' &|<>^()%"!,;=')


def build_command(target):
    if os.name == "nt":
        executable = sys.executable
        if not any(char in CMD_UNSAFE for char in executable + target):
            command = executable + " " + target
        else:
            command = subprocess.list2cmdline([executable, target])
    else:
        command = shlex.join(["python3", target])
    return "command = " + json.dumps(command, ensure_ascii=False)


def atomic_write(path, text):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    existing_mode = stat.S_IMODE(os.stat(path).st_mode) if os.path.exists(path) else 0o600
    fd, temporary = tempfile.mkstemp(prefix=".tui-", dir=directory)
    try:
        os.fchmod(fd, existing_mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(tui_path, target):
    text = open(tui_path, encoding="utf-8").read() if os.path.exists(tui_path) else ""
    if text and not text.endswith("\n"):
        text += "\n"
    match = SECTION_RE.search(text)
    section = match.group(0) if match else ""
    if target in section or target.replace("\\", "\\\\") in section:
        print("Already configured: " + target)
        return 0

    if os.path.exists(tui_path):
        backup = tui_path + "." + time.strftime("%Y%m%d-%H%M%S") + ".bak"
        shutil.copy2(tui_path, backup)
        print("Backup: " + backup)

    command_line = build_command(target)
    if match:
        def replace_section(found):
            body = found.group(0)
            if COMMAND_RE.search(body):
                return COMMAND_RE.sub(lambda _: command_line, body, count=1)
            return body.rstrip("\n") + "\n" + command_line + "\n"

        text = SECTION_RE.sub(replace_section, text, count=1)
    else:
        text += "\n[status_line]\n" + command_line + "\n"
    atomic_write(tui_path, text)
    print("Configured: " + tui_path)
    print("Run /reload-tui in Kimi Code to activate the status line.")
    return 0


def main():
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(plugin_dir, "statusline.py")
    if not os.path.isfile(target):
        print("Missing statusline.py", file=sys.stderr)
        return 1
    kimi_home = os.environ.get("KIMI_CODE_HOME", os.path.expanduser("~/.kimi-code"))
    return install(os.path.join(kimi_home, "tui.toml"), target)


if __name__ == "__main__":
    sys.exit(main())
