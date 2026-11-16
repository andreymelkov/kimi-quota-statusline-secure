#!/usr/bin/env python3
import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath

PLUGIN_ID = "kimi-quota-statusline-secure"
REPOSITORY_OWNER = "andreymelkov"
REPOSITORY_NAME = "kimi-quota-statusline-secure"
REPOSITORY_URL = "https://github.com/andreymelkov/kimi-quota-statusline-secure"
API_ROOT = "https://api.github.com/repos/andreymelkov/kimi-quota-statusline-secure"
USER_AGENT = "kimi-quota-statusline-secure-updater/1.2.0"
MAX_API_BYTES = 1_000_000
MAX_ARCHIVE_BYTES = 4_000_000
MAX_UNPACKED_BYTES = 16_000_000
MAX_ARCHIVE_FILES = 256
REQUEST_TIMEOUT_SECONDS = 15
FORBIDDEN_MANIFEST_FIELDS = {
    "hooks",
    "mcpServers",
    "systemPrompt",
    "systemPromptPath",
    "sessionStart",
    "agents",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.URLError("Redirects are disabled")


def http_get(url, max_bytes):
    parsed = urllib.parse.urlsplit(url)
    allowed = (
        (parsed.scheme == "https" and parsed.hostname == "api.github.com" and parsed.path.startswith("/repos/" + REPOSITORY_OWNER + "/" + REPOSITORY_NAME + "/"))
        or (parsed.scheme == "https" and parsed.hostname == "codeload.github.com" and parsed.path.startswith("/" + REPOSITORY_OWNER + "/" + REPOSITORY_NAME + "/"))
    )
    if not allowed or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Untrusted update URL")
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        if response.getcode() != 200:
            raise ValueError("GitHub returned an unexpected HTTP status")
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("GitHub response is too large")
    return data


def fetch_json(url):
    value = json.loads(http_get(url, MAX_API_BYTES).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a GitHub JSON object")
    return value


def version_tuple(version):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ValueError("Only stable semantic-version releases are supported")
    return tuple(int(part) for part in match.groups())


def extract_archive(data, destination):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if not entries or len(entries) > MAX_ARCHIVE_FILES:
            raise ValueError("Unexpected number of archive entries")
        if sum(entry.file_size for entry in entries) > MAX_UNPACKED_BYTES:
            raise ValueError("Unpacked release is too large")
        roots = set()
        for entry in entries:
            name = entry.filename
            if not name or name.startswith(("/", "\\")) or "\\" in name:
                raise ValueError("Unsafe archive path")
            parts = PurePosixPath(name).parts
            if any(part in ("", ".", "..") for part in parts):
                raise ValueError("Unsafe archive path")
            if len(parts) < 1:
                continue
            roots.add(parts[0])
            if len(parts) == 1:
                continue
            relative = PurePosixPath(*parts[1:])
            target = os.path.join(destination, *relative.parts)
            destination_root = os.path.realpath(destination)
            if not os.path.realpath(target).startswith(destination_root + os.sep):
                raise ValueError("Archive path escapes destination")
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("Symbolic links are not allowed in releases")
            if entry.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                raise ValueError("Only regular files are allowed in releases")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            content = archive.read(entry)
            if len(content) != entry.file_size:
                raise ValueError("Truncated archive entry")
            with open(target, "xb") as handle:
                handle.write(content)
        if len(roots) != 1:
            raise ValueError("Release archive must have one root directory")


def validate_release(root, tag):
    manifest_path = os.path.join(root, "kimi.plugin.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("name") != PLUGIN_ID:
        raise ValueError("Unexpected plugin identifier")
    if manifest.get("version") != tag.lstrip("v"):
        raise ValueError("Release tag and plugin version do not match")
    forbidden = FORBIDDEN_MANIFEST_FIELDS.intersection(manifest)
    if forbidden:
        raise ValueError("Release violates the plugin security policy: " + ", ".join(sorted(forbidden)))
    for required in ("statusline.py", "install.py", "uninstall.py", "update.py", "README.md"):
        if not os.path.isfile(os.path.join(root, required)):
            raise ValueError("Release is incomplete")


def atomic_write_json(path, value):
    mode = stat.S_IMODE(os.stat(path).st_mode)
    fd, temporary = tempfile.mkstemp(prefix=".installed-update-", dir=os.path.dirname(path))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def update_registry(path, root, tag, commit):
    with open(path, encoding="utf-8") as handle:
        registry = json.load(handle)
    entries = [entry for entry in registry.get("plugins", []) if entry.get("id") == PLUGIN_ID]
    if len(entries) != 1:
        raise ValueError("Managed plugin registry entry was not found")
    entry = entries[0]
    if os.path.realpath(entry.get("root", "")) != os.path.realpath(root):
        raise ValueError("Managed plugin root does not match the registry")
    entry["source"] = "github"
    entry["originalSource"] = REPOSITORY_URL
    entry["github"] = {
        "owner": REPOSITORY_OWNER,
        "repo": REPOSITORY_NAME,
        "ref": {"kind": "tag", "value": tag},
        "installedSha": commit,
    }
    entry["updatedAt"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    atomic_write_json(path, registry)


def perform_update():
    plugin_root = os.path.dirname(os.path.abspath(__file__))
    managed_dir = os.path.dirname(plugin_root)
    plugins_dir = os.path.dirname(managed_dir)
    if os.path.basename(plugin_root) != PLUGIN_ID or os.path.basename(managed_dir) != "managed" or os.path.basename(plugins_dir) != "plugins":
        raise ValueError("Updates are supported only from the managed plugin installation")
    registry_path = os.path.join(plugins_dir, "installed.json")
    with open(os.path.join(plugin_root, "kimi.plugin.json"), encoding="utf-8") as handle:
        current_manifest = json.load(handle)
    current_version = str(current_manifest.get("version", ""))
    version_tuple(current_version)

    release = fetch_json(API_ROOT + "/releases/latest")
    if release.get("draft") or release.get("prerelease"):
        raise ValueError("Latest release is not stable")
    tag = release.get("tag_name")
    if not isinstance(tag, str):
        raise ValueError("Release tag is missing")
    latest_version = tag.lstrip("v")
    version_tuple(tag)
    commit_data = fetch_json(API_ROOT + "/commits/" + urllib.parse.quote(tag, safe=""))
    commit = commit_data.get("sha")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Release commit is invalid")

    if version_tuple(latest_version) < version_tuple(current_version):
        raise ValueError("Refusing to downgrade the plugin")
    if version_tuple(latest_version) == version_tuple(current_version):
        print("Already using the latest release: " + tag)
        return 0

    archive_url = "https://codeload.github.com/" + REPOSITORY_OWNER + "/" + REPOSITORY_NAME + "/zip/refs/tags/" + urllib.parse.quote(tag, safe="")
    archive_data = http_get(archive_url, MAX_ARCHIVE_BYTES)
    stage = tempfile.mkdtemp(prefix="." + PLUGIN_ID + "-stage-", dir=managed_dir)
    previous = stage + "-previous"
    backup_root = os.path.join(plugins_dir, "backups", PLUGIN_ID, datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + str(os.getpid()))
    try:
        extract_archive(archive_data, stage)
        validate_release(stage, tag)
        os.makedirs(os.path.dirname(backup_root), exist_ok=True)
        shutil.copytree(plugin_root, backup_root)
        shutil.copy2(registry_path, backup_root + "-installed.json")
        os.replace(plugin_root, previous)
        try:
            os.replace(stage, plugin_root)
            update_registry(registry_path, plugin_root, tag, commit)
        except Exception:
            if os.path.exists(plugin_root):
                os.replace(plugin_root, stage)
            if os.path.exists(previous):
                os.replace(previous, plugin_root)
            raise
        shutil.rmtree(previous)
    finally:
        if os.path.exists(stage):
            shutil.rmtree(stage)
        if os.path.exists(previous):
            shutil.rmtree(previous)

    print("Updated " + PLUGIN_ID + " from " + current_version + " to " + latest_version)
    print("Backup: " + backup_root)
    print("Run /reload and /reload-tui in Kimi Code.")
    return 0


def main():
    try:
        return perform_update()
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, zipfile.BadZipFile, urllib.error.URLError) as error:
        print("Update failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
