#!/usr/bin/env python3
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

KIMI_HOME = os.path.abspath(os.path.expanduser(os.environ.get("KIMI_CODE_HOME", "~/.kimi-code")))
CONFIG_FILE = os.path.join(KIMI_HOME, "config.toml")
CREDENTIALS_DIR = os.path.join(KIMI_HOME, "credentials")
CACHE_FILE = os.path.join(KIMI_HOME, "quota-statusline-cache.json")
LOCK_FILE = os.path.join(KIMI_HOME, "quota-statusline-refresh.lock")
DEFAULT_BASE_URL = "https://api.kimi.com/coding/v1"
ALLOWED_HOSTS = {"api.kimi.com", "api.kimi.ai"}
CACHE_TTL_SECONDS = 60
STALE_AFTER_SECONDS = 600
LOCK_TTL_SECONDS = 120
REQUEST_TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 1_000_000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.URLError("Redirects are disabled")


def read_json(path, max_bytes=MAX_RESPONSE_BYTES):
    with open(path, "rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("JSON file is too large")
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def toml_value(raw):
    value = raw.strip()
    if value.startswith('"'):
        return json.loads(value)
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    return value


def resolve_official_endpoint():
    credential_name = "kimi-code"
    base_url = DEFAULT_BASE_URL
    section = ""
    try:
        with open(CONFIG_FILE, encoding="utf-8", errors="strict") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].strip()
                    continue
                if "=" not in line:
                    continue
                key, _, raw_value = line.partition("=")
                key = key.strip()
                try:
                    value = toml_value(raw_value)
                except (ValueError, json.JSONDecodeError):
                    continue
                if not isinstance(value, str):
                    continue
                if section == 'providers."managed:kimi-code"' and key == "base_url":
                    base_url = value
                elif section == 'providers."managed:kimi-code".oauth' and key == "key":
                    credential_name = value.rsplit("/", 1)[-1]
    except FileNotFoundError:
        pass

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", credential_name):
        raise ValueError("Unsafe credential name")
    if credential_name in {".", ".."}:
        raise ValueError("Unsafe credential name")

    parsed = urllib.parse.urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path.rstrip("/") != "/coding/v1"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Untrusted Kimi endpoint")

    credential_path = os.path.join(CREDENTIALS_DIR, credential_name + ".json")
    return credential_path, "https://" + parsed.hostname + "/coding/v1/usages"


def finite_number(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a quota number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Quota number is not finite")
    return number


def parse_window(detail, ratio=False):
    if not isinstance(detail, dict):
        raise ValueError("Invalid quota window")
    if ratio:
        used_ratio = finite_number(detail.get("used_ratio"))
        if used_ratio < 0:
            raise ValueError("Negative quota usage")
    else:
        used = finite_number(detail.get("used", 0))
        limit = finite_number(detail.get("limit"))
        if used < 0 or limit <= 0:
            raise ValueError("Invalid quota usage")
        used_ratio = used / limit
    reset_at = detail.get("reset_time" if ratio else "resetTime", "")
    if not isinstance(reset_at, str) or len(reset_at) > 64:
        reset_at = ""
    return {
        "remaining_ratio": max(0.0, 1.0 - used_ratio),
        "reset_at": reset_at,
    }


def parse_quota_response(response):
    windows = {}
    usages = response.get("usages")
    if isinstance(usages, dict):
        for name, key in (("5h", "limit_5h"), ("7d", "limit_7d"), ("month", "limit_month_total")):
            try:
                windows[name] = parse_window(usages.get(key), ratio=True)
            except (TypeError, ValueError, OverflowError):
                pass

    limits = response.get("limits")
    if "5h" not in windows and isinstance(limits, list):
        for item in limits:
            if not isinstance(item, dict):
                continue
            window = item.get("window")
            if (
                isinstance(window, dict)
                and window.get("duration") == 300
                and window.get("timeUnit") == "TIME_UNIT_MINUTE"
            ):
                try:
                    windows["5h"] = parse_window(item.get("detail"))
                except (TypeError, ValueError, OverflowError):
                    pass
                break

    if "7d" not in windows:
        try:
            windows["7d"] = parse_window(response.get("usage"))
        except (TypeError, ValueError, OverflowError):
            pass

    return {"fetched_at": time.time(), "windows": windows} if windows else None


def fetch_official_quota():
    try:
        credential_path, url = resolve_official_endpoint()
        credentials = read_json(credential_path)
        token = credentials.get("access_token")
        expires_at = finite_number(credentials.get("expires_at", 0))
        if (
            not isinstance(token, str)
            or not token
            or len(token) > 8192
            or any(ord(char) < 33 or ord(char) == 127 for char in token)
            or expires_at < time.time() + 10
        ):
            return None

        request = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json",
                "User-Agent": "kimi-quota-statusline-secure/1.0.0",
            },
        )
        opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.getcode() != 200:
                return None
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            return None
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        return parse_quota_response(payload)
    except (OSError, ValueError, TypeError, OverflowError, urllib.error.URLError, json.JSONDecodeError):
        return None


def load_cache():
    try:
        return read_json(CACHE_FILE, max_bytes=65536)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def atomic_write_json(path, value):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".quota-statusline-", dir=directory)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def create_refresh_lock():
    try:
        fd = os.open(LOCK_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        return True
    except FileExistsError:
        try:
            if time.time() - os.stat(LOCK_FILE).st_mtime > LOCK_TTL_SECONDS:
                os.unlink(LOCK_FILE)
        except OSError:
            pass
        return False
    except OSError:
        return False


def detached_kwargs():
    if os.name == "nt":
        return {"creationflags": 0x00000008 | 0x00000200}
    return {"start_new_session": True}


def maybe_refresh(cache):
    checked_at = cache.get("checked_at", 0)
    try:
        checked_at = finite_number(checked_at)
    except (TypeError, ValueError, OverflowError):
        checked_at = 0
    now = time.time()
    if cache and 0 <= now - checked_at <= CACHE_TTL_SECONDS:
        return
    if not create_refresh_lock():
        return
    try:
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--refresh"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **detached_kwargs()
        )
    except OSError:
        try:
            os.unlink(LOCK_FILE)
        except OSError:
            pass


def refresh_cache():
    try:
        official = fetch_official_quota()
        previous = load_cache()
        if official is None:
            official = {
                "fetched_at": previous.get("fetched_at", 0),
                "windows": previous.get("windows", {}) if isinstance(previous.get("windows"), dict) else {},
            }
        atomic_write_json(
            CACHE_FILE,
            {
                "version": 1,
                "checked_at": time.time(),
                "fetched_at": official.get("fetched_at", 0),
                "windows": official.get("windows", {}),
            },
        )
    finally:
        try:
            os.unlink(LOCK_FILE)
        except OSError:
            pass


def reset_hint(value):
    if not isinstance(value, str) or not value:
        return ""
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        seconds = int(timestamp - time.time())
        if seconds <= 0:
            return ""
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes = seconds // 60
        if days:
            return str(days) + "d" + str(hours) + "h"
        if hours:
            return str(hours) + "h" + (str(minutes) + "m" if minutes else "")
        return str(minutes) + "m"
    except (ValueError, OverflowError, OSError):
        return ""


def render(cache):
    windows = cache.get("windows")
    if not isinstance(windows, dict) or not windows:
        return "Kimi quota: unavailable" if cache else "Kimi quota: loading"
    try:
        fetched_at = finite_number(cache.get("fetched_at", 0))
    except (TypeError, ValueError, OverflowError):
        fetched_at = 0
    stale = time.time() - fetched_at > STALE_AFTER_SECONDS
    parts = []
    for name, label in (("5h", "5h"), ("7d", "7d"), ("month", "month")):
        window = windows.get(name)
        if not isinstance(window, dict):
            continue
        try:
            remaining = finite_number(window.get("remaining_ratio"))
        except (TypeError, ValueError, OverflowError):
            continue
        if remaining < 0:
            continue
        percentage = round(100 * min(1.0, remaining))
        text = label + " " + ("~" if stale else "") + str(percentage) + "%"
        hint = reset_hint(window.get("reset_at"))
        if hint:
            text += " " + hint
        parts.append(text)
    return " · ".join(parts) if parts else "Kimi quota: unavailable"


def main():
    if hasattr(sys.stdin, "buffer"):
        sys.stdin.buffer.read(MAX_RESPONSE_BYTES)
    else:
        sys.stdin.read(MAX_RESPONSE_BYTES)
    cache = load_cache()
    maybe_refresh(cache)
    print(render(cache))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--refresh":
        refresh_cache()
    else:
        main()
