"""AI Limits Monitor, T3 edition: data side (settings and the per-vendor usage readers).

The usage readers are the same as in the desktop edition (github.com/P3anutSweet/ai-limits-monitor), without its
desktop window. Claude and Codex numbers come from the internal endpoints the apps use for their own usage screens
(unofficial: they may change or break at any time), read with the logins Claude Code (~/.claude/.credentials.json)
and Codex (~/.codex/auth.json) keep fresh. Tokens are only read, never written, logged, printed or served.

Settings: ai_limits_t3_settings.json next to this file (or the file named by AI_LIMITS_T3_SETTINGS), each key
overridable by an AI_LIMITS_T3_<KEY> environment variable; see README.md.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
CLAUDE_CRED = os.path.join(HOME, ".claude", ".credentials.json")
CODEX_AUTH = os.path.join(HOME, ".codex", "auth.json")
GROK_AUTH = os.path.join(HOME, ".grok", "auth.json")
T3_AG_CACHE = os.path.join(HOME, ".t3", "caches", "antigravity.json")   # T3 keeps Antigravity's own usage windows here
T3_AG_PROVIDERS = os.path.join(HOME, ".t3", "userdata", "providers", "antigravity")
GEMINI_DIR = os.path.join(HOME, ".gemini")
DSH_CRED = os.path.join(HOME, ".dsh", ".credentials.yaml")             # big fat fish (DeepSeek) Harness account grant
HERE = os.path.dirname(os.path.abspath(__file__))
_LOCAL = os.environ.get("LOCALAPPDATA") or os.path.join(HOME, "AppData", "Local")

# ---------- settings: ai_limits_t3_settings.json next to the script, then AI_LIMITS_T3_<KEY> environment overrides ----------
ALL_SERVICES = ["Claude", "Codex", "Gemini", "DeepSeek", "Grok", "Kimi", "Qwen", "Doubao", "GLM", "MiniMax"]
DEFAULTS = {
    "port": 47823,                   # the page is served at http://localhost:<port> (this PC only)
    "source": "auto",                # "auto": the desktop edition's latest.json when fresh, else read usage itself;
                                     # "file": only latest.json; "self": always read usage itself
    "latest_json": os.path.join(_LOCAL, "ai-limits-monitor", "latest.json"),   # written by the desktop edition
    "max_age_minutes": 15,           # "auto" uses latest.json only when it is younger than this
    "data_dir": os.path.join(_LOCAL, "ai-limits-monitor-t3"),
    "avatar_dir": os.path.join(HERE, "avatars"),
    "services": ["Claude", "Codex", "Gemini", "DeepSeek", "Grok"],   # any of ALL_SERVICES, in page order
    "time_zone": "local",            # "local", or a fixed UTC offset in hours (e.g. 8)
    "time_zone_label": "",           # shown after times, e.g. "UTC"
    "refresh_minutes": 5,
    "kimi_credentials": "",          # Kimi Code login file; "" = %KIMI_CODE_HOME%\credentials\kimi-code.json
    "gemini_badge": "",              # plan pill on the Gemini card, e.g. "AI Pro"
    "gemini_notes": [],              # extra info lines on the Gemini card (your own labels, never checked)
    "demo": False,                   # sample data, nothing read from any account (also: --demo)
}
SETTINGS_FILE = os.environ.get("AI_LIMITS_T3_SETTINGS") or os.path.join(HERE, "ai_limits_t3_settings.json")


def _env_value(default, raw):
    if isinstance(default, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, list):
        items = [x.strip() for x in raw.split(",") if x.strip()]
        return [float(x) for x in items] if default and isinstance(default[0], (int, float)) else items
    if isinstance(default, (int, float)):
        return float(raw)
    return raw


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            s.update({k: v for k, v in json.load(f).items() if not k.startswith("_")})   # "_about" = comment
    except FileNotFoundError:
        pass
    except Exception as e:
        sys.stderr.write(f"ai_limits_t3_settings.json ignored: {type(e).__name__}\n")
    for k in DEFAULTS:
        raw = os.environ.get("AI_LIMITS_T3_" + k.upper())
        if raw:
            try:
                s[k] = _env_value(DEFAULTS[k], raw)
            except ValueError:
                pass
    if "--demo" in sys.argv:
        s["demo"] = True
    for k in ("data_dir", "avatar_dir", "latest_json"):   # empty = default
        s[k] = s[k] or DEFAULTS[k]
    for k in ("data_dir", "avatar_dir", "kimi_credentials", "latest_json"):
        s[k] = os.path.normpath(os.path.expandvars(os.path.expanduser(s[k]))) if s[k] else s[k]
    s["port"] = int(s["port"])
    return s


S = load_settings()
DEMO = bool(S["demo"])
READ_ONLY = DEMO                    # demo runs write nothing
TZ = None if str(S["time_zone"]).lower() == "local" else dt.timezone(dt.timedelta(hours=float(S["time_zone"])))
TZ_SUFFIX = (" " + S["time_zone_label"]) if S["time_zone_label"] else ""
LOG_DIR = S["data_dir"]


# ---------- data ----------
def http_json(url, headers, timeout=20):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_iso(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def fetch_claude():
    out = {"name": "Claude", "plan": "", "meters": [], "notes": [], "error": None}
    try:
        cred = json.load(open(CLAUDE_CRED, encoding="utf-8"))["claudeAiOauth"]
    except Exception:
        out["error"] = "No Claude login found"
        return out
    tier = (cred.get("rateLimitTier") or "").replace("default_claude_", "").replace("_", " ")
    out["plan"] = (tier or cred.get("subscriptionType") or "").title().replace("Max 5X", "Max 5x").replace("Max 20X", "Max 20x")
    if cred.get("expiresAt") and cred["expiresAt"] / 1000 < time.time():
        out["error"] = "Login token expired: open Claude Code once to refresh"
        return out
    try:
        d = http_json("https://api.anthropic.com/api/oauth/usage", {
            "Authorization": "Bearer " + cred["accessToken"],
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "ai-limits-monitor/1",
        })
    except urllib.error.HTTPError as e:
        out["error"] = f"Claude usage API: HTTP {e.code}"
        return out
    except Exception as e:
        out["error"] = f"Claude usage API: {type(e).__name__}"
        return out

    limits = d.get("limits") or []
    if limits:
        for lim in limits:
            kind = lim.get("kind")
            scope = lim.get("scope") or {}
            model = ((scope.get("model") or {}).get("display_name")) or ""
            surface = scope.get("surface") or ""
            if kind == "session":
                label, window = "5-hour", 5 * 3600
            elif kind == "weekly_all":
                label, window = "Weekly · all models", 7 * 86400
            elif kind == "weekly_scoped":
                label, window = "Weekly · " + (model or str(surface) or "scoped"), 7 * 86400
            else:
                label, window = kind.replace("_", " ").capitalize(), None
            out["meters"].append({
                "key": "claude:" + kind + ":" + (model or str(surface)),
                "label": label, "pct": float(lim.get("percent") or 0),
                "resets_at": parse_iso(lim.get("resets_at")), "window": window,
                "active": bool(lim.get("is_active")),
            })
    else:  # older response shape
        for k, label, window in (("five_hour", "5-hour", 5 * 3600), ("seven_day", "Weekly · all models", 7 * 86400),
                                 ("seven_day_opus", "Weekly · Opus", 7 * 86400)):
            v = d.get(k)
            if v:
                out["meters"].append({"key": "claude:" + k, "label": label, "pct": float(v.get("utilization") or 0),
                                      "resets_at": parse_iso(v.get("resets_at")), "window": window, "active": False})

    ex = d.get("extra_usage") or {}
    if ex.get("is_enabled") and ex.get("monthly_limit"):
        div = 10 ** int(ex.get("decimal_places") or 2)
        used, cap = (ex.get("used_credits") or 0) / div, ex["monthly_limit"] / div
        out["meters"].append({"key": "claude:extra", "label": "Extra usage · month",
                              "pct": float(ex.get("utilization") or 0), "resets_at": None, "window": None,
                              "detail": f"${used:,.2f} of ${cap:,.0f}", "active": False})
    return out


def fetch_codex():
    out = {"name": "Codex", "plan": "", "meters": [], "notes": [], "error": None}
    try:
        auth = json.load(open(CODEX_AUTH, encoding="utf-8"))
        tok = auth.get("tokens") or {}
    except Exception:
        out["error"] = "No Codex login found"
        return out
    try:
        d = http_json("https://chatgpt.com/backend-api/wham/usage", {
            "Authorization": "Bearer " + tok.get("access_token", ""),
            "ChatGPT-Account-Id": tok.get("account_id", ""),
            "User-Agent": "codex_cli_rs",
        })
    except urllib.error.HTTPError as e:
        out["error"] = f"Codex usage API: HTTP {e.code}" + (" (open Codex once to refresh login)" if e.code in (401, 403) else "")
        return out
    except Exception as e:
        out["error"] = f"Codex usage API: {type(e).__name__}"
        return out

    plan = (d.get("plan_type") or "").lower()
    out["plan"] = {"prolite": "Pro Lite", "pro": "Pro", "plus": "Plus", "team": "Team", "business": "Business"}.get(plan, plan.title())

    def window_label(sec):
        if not sec:
            return "Limit"
        if sec <= 6 * 3600:
            return f"{round(sec / 3600)}-hour"
        if sec >= 6 * 86400:
            return "Weekly"
        return f"{round(sec / 86400)}-day"

    def add_rl(rl, prefix, keybase):
        for wkey in ("primary_window", "secondary_window"):
            w = (rl or {}).get(wkey)
            if not w:
                continue
            sec = w.get("limit_window_seconds")
            label = window_label(sec) + ((" · " + prefix) if prefix else "")
            out["meters"].append({"key": f"codex:{keybase}:{sec}", "label": label,
                                  "pct": float(w.get("used_percent") or 0),
                                  "resets_at": w.get("reset_at"), "window": sec, "active": False})

    rl = d.get("rate_limit") or {}
    add_rl(rl, "", "main")
    if not rl.get("secondary_window") and not any(m["window"] and m["window"] <= 6 * 3600 for m in out["meters"]):
        pass  # "No 5-hour limit" note removed (2026-11-09)
    for extra in d.get("additional_rate_limits") or []:
        name = extra.get("limit_name") or extra.get("metered_feature") or extra.get("limit_id") or "model"
        add_rl(extra.get("rate_limit") or extra, str(name), str(name))
    cr = d.get("code_review_rate_limit")
    if cr:
        add_rl(cr, "code review", "review")

    for model, mu in (d.get("model_usage") or {}).items():
        ok = mu.get("available", True)
        when = mu.get("available_at")
        txt = f"{model}: available" if ok else f"{model}: blocked" + (f" until {fmt_time(when)}" if when else "")
        out["notes"].append(("ok" if ok else "bad", txt))
    if rl.get("limit_reached"):
        out["notes"].append(("bad", "Limit reached"))
    return out


def fetch_grok():
    """Grok has no readable plan usage from the shell (grok usage needs its daemon route), so the
    section only shows whether the CLI is signed in: blue dot = signed in, rose = not (2026-11-10)."""
    out = {"name": "Grok", "plan": "", "meters": [], "notes": [], "error": None, "signed_in": False}
    try:
        auth = json.load(open(GROK_AUTH, encoding="utf-8"))
        out["signed_in"] = any(isinstance(v, dict) and v.get("key") for v in (auth or {}).values())
    except Exception:
        pass
    out["notes"].append(("ok", "signed in") if out["signed_in"] else ("bad", "not signed in"))
    return out


# ---- free-account status cards (2026-11-10: sign-in status like Grok, status only, in case
# one day they offer free credits): Kimi, Qwen, Doubao, GLM, MiniMax. Free sign-in only, no plan, no top-up.
# A card shows signed in / not signed in and, only when the vendor itself reports it, a free balance / trial
# quota line (marked FREE). Nothing is estimated or invented.
NPM_BIN = os.path.join(os.environ.get("APPDATA", os.path.join(HOME, "AppData", "Roaming")), "npm")
KIMI_SEEN = os.path.join(LOG_DIR, "kimi_usage_seen.json")
KIMI_CRED = S["kimi_credentials"] or os.path.join(os.environ.get("KIMI_CODE_HOME") or os.path.join(HOME, ".kimi-code"),
                                                  "credentials", "kimi-code.json")


def run_cli(name, args, timeout=25):
    """Run a vendor CLI (npm shim) without a console window; returns (exit code, stdout) or (None, '')."""
    try:
        p = subprocess.run([os.path.join(NPM_BIN, name + ".cmd")] + list(args), capture_output=True, timeout=timeout,
                           creationflags=0x08000000, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except Exception:
        return None, ""


def cli_json(name, args, timeout=25):
    rc, txt = run_cli(name, args, timeout)
    try:
        return rc, json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
    except Exception:
        return rc, None


def status_card(name, signed, lines=None, cap=None, error=None):
    """Status-only card (like Grok). lines = [(kind, text)], kind ok / bad / info / free (a real free-credit line)."""
    out = {"name": name, "plan": "", "meters": [], "notes": [], "error": error, "signed_in": bool(signed),
           "status_lines": list(lines or []), "cap": cap}
    out["notes"].append(("ok", "signed in") if signed else ("bad", "not signed in"))
    return out


_KIMI = {"t": 0.0, "res": None}


def fetch_kimi():
    """Kimi Code (OAuth device login; login file set by kimi_credentials / KIMI_CODE_HOME). Signed in = the login file has a
    refresh token. Free quota source: GET api.kimi.com/coding/v1/usages with the access token, only while that token is
    still valid (the monitor never refreshes or rewrites it). An empty reply = the free account has no plan quota."""
    try:
        d = json.load(open(KIMI_CRED, encoding="utf-8"))
    except Exception:
        d = None
    signed = bool(d and d.get("refresh_token"))
    if not signed:
        return status_card("Kimi", False, [("info", "free sign-in: kimi login")], "free sign-in missing")
    lines, cap = [], "free account"
    try:
        if time.time() < (d.get("expires_at") or 0) - 30 and time.time() - _KIMI["t"] > 600:
            _KIMI["res"] = http_json("https://api.kimi.com/coding/v1/usages",
                                     {"Authorization": "Bearer " + d["access_token"], "User-Agent": "ai-limits-monitor/2"})
            _KIMI["t"] = time.time()
            try:   # remember the last real reading (no token in it) for the times the 15-minute token is idle
                if READ_ONLY:
                    raise RuntimeError("demo / snapshot runs write nothing")
                os.makedirs(LOG_DIR, exist_ok=True)
                json.dump({"checked": dt.date.today().isoformat(), "keys": list(_KIMI["res"])[:6]},
                          open(KIMI_SEEN, "w", encoding="utf-8"))
            except Exception:
                pass
    except Exception:
        pass
    res = _KIMI["res"]
    if res is None:
        try:
            seen = json.load(open(KIMI_SEEN, encoding="utf-8"))
        except Exception:
            seen = None
        if seen is None:
            lines.append(("info", "usage not checked yet (sign-in token idle)"))
        elif seen.get("keys"):
            lines.append(("free", f"usage data was reported by Kimi on {seen['checked']}: open Kimi Code"))
        else:
            lines.append(("info", f"no plan quota reported (checked {seen['checked']})"))
    elif res:
        keys = ", ".join(list(res)[:4])
        lines.append(("free", f"usage data reported by Kimi ({keys}): open Kimi Code to read it"))
        cap = "Kimi reports usage data"
    else:
        lines.append(("info", "no plan quota reported  ·  free account"))
    return status_card("Kimi", True, lines, cap)


SIGNIN_STATUS = os.path.join(LOG_DIR, "signin_status.json")


def fetch_qwen():
    """Qwen 千问 = the consumer app https://www.qianwen.com/ signed in inside a browser (the QwenCloud CLI needs a
    separate Alibaba Cloud account and is not used). Browsers keep their cookie store locked and encrypted, so there
    is no live check: the sign-in is recorded by hand in <data_dir>\\signin_status.json
    ({"qwen": {"signed_in": true, "verified": "YYYY-MM-DD", "free_quota": ""}}), and the card says when.
    The account page lists no quota or credits (checked 2026-11-10); if that changes the line goes in 'free_quota'."""
    try:
        s = json.load(open(SIGNIN_STATUS, encoding="utf-8")).get("qwen") or {}
    except Exception:
        s = {}
    if not s.get("signed_in"):
        return status_card("Qwen", False, [("info", "free sign-in: open qianwen.com in Chrome")], "free sign-in missing")
    lines = []
    if s.get("free_quota"):
        lines.append(("free", str(s["free_quota"])))
    lines.append(("info", f"qianwen.com app in Chrome  ·  verified {s.get('verified', '?')}"))
    lines.append(("info", "no quota shown" if not s.get("free_quota") else "quota as shown on the site"))
    return status_card("Qwen", True, lines, "qianwen.com app · free" + (" · quota shown" if s.get("free_quota") else ""))


_ARK = {"t": 0.0, "lines": None, "cap": None}


def fetch_doubao():
    """Doubao / Volcengine Ark (arkcli volc-sso browser login, account = individual Douyin sign-in). Signed in =
    `arkcli auth status`. Free quota = `arkcli usage balance --type free-quota` (the per-model free inference quota
    Volcengine itself reports); plan = `--type plan` (empty = no subscription). Checked every 30 min."""
    rc, st = cli_json("arkcli", ["auth", "status"])
    if st is None:
        return status_card("Doubao", False, [], "sign-in check failed", "arkcli not answering")
    if not st.get("logged_in"):
        return status_card("Doubao", False, [("info", "free sign-in: arkcli auth login volc-sso")], "free sign-in missing")
    if _ARK["lines"] is None or time.time() - _ARK["t"] > 1800:
        lines, cap = [], "free account"
        _, fq = cli_json("arkcli", ["usage", "balance", "--type", "free-quota", "--modality", "LLM", "--page-size", "50"], 50)
        items = (fq or {}).get("items") if isinstance(fq, dict) else None
        if items:
            rem = [int((i.get("free_usage") or {}).get("remaining") or 0) for i in items]
            tot = [int((i.get("free_usage") or {}).get("total") or 0) for i in items]
            if sum(rem) > 0:
                n = len(items)
                per = f"{max(rem) // 1000}k" if len(set(rem)) == 1 else f"{sum(rem) // 1000}k total"
                used = sum(tot) - sum(rem)
                lines.append(("free", f"{n} models × {per} tokens" + ("" if used else ", none used")))
                st_all = {i.get("state") for i in items}
                if st_all == {"Unavailable"}:
                    lines.append(("info", "listed Unavailable until the service is opened"))
                cap = f"free quota: {n} models × {per} tokens"
        elif fq is None:
            lines.append(("info", "free quota: not readable"))
        else:
            lines.append(("info", "no free quota reported"))
        _, pl = cli_json("arkcli", ["usage", "balance", "--type", "plan"], 40)
        if isinstance(pl, dict) and pl.get("items") == []:
            lines.append(("info", "no Agent / Coding Plan"))
        elif isinstance(pl, dict) and pl.get("items"):
            lines.append(("info", "a plan is active: check the Ark console"))
        _ARK.update(t=time.time(), lines=lines, cap=cap)
    return status_card("Doubao", True, _ARK["lines"], _ARK["cap"])


_GLM = {"t": 0.0, "res": None}


def fetch_glm():
    """GLM 智谱 via Z.ai: a free account's API key (ZAI_API_KEY user environment variable, key only ever sent in the
    request header). Signed in = the key is accepted by a token-free model listing (checked every 30 min).
    Z.ai has no balance / quota endpoint for free keys, so none is shown; glm-4.7-flash is the free model
    Z.ai's price list marks free (that is a standing free tier, not a granted credit)."""
    key = user_env("ZAI_API_KEY")
    if not key:
        return status_card("GLM", False, [("info", "free account key: z.ai API keys")], "free key missing")
    if _GLM["res"] is None or time.time() - _GLM["t"] > 1800:
        try:
            http_json("https://api.z.ai/api/paas/v4/models", {"Authorization": "Bearer " + key, "User-Agent": "ai-limits-monitor/2"})
            res = ("ok", None)
        except urllib.error.HTTPError as e:
            res = ("rejected", e.code)
        except Exception:
            res = ("net", None)
        _GLM.update(t=time.time(), res=res)
    kind, code = _GLM["res"]
    if kind == "ok":
        return status_card("GLM", True, [("info", "glm-4.7-flash is Z.ai's free model"),
                                          ("info", "no balance or quota reported for free keys")], "Z.ai free key")
    if kind == "rejected":
        return status_card("GLM", False, [("bad", f"key rejected (HTTP {code})")], "key rejected")
    return status_card("GLM", True, [("info", "key set  ·  check failed (network)")], "Z.ai key set")


_MM = {"t": 0.0, "lines": None, "cap": None}


def fetch_minimax():
    """MiniMax (mmx CLI, OAuth browser login to platform.minimax.io; no key, no plan). Signed in = `mmx auth status`
    finds credentials. Quota = `mmx quota show` (Token Plan counters, every 30 min): all totals 0 means no plan /
    no quota; any non-zero total is flagged FREE so a trial grant would be noticed (it is the vendor's own number)."""
    rc, st = cli_json("mmx", ["auth", "status", "--non-interactive"])
    if not isinstance(st, dict) or st.get("error") or not st.get("method"):
        return status_card("MiniMax", False, [("info", "free sign-in: mmx auth login")], "free sign-in missing")
    if _MM["lines"] is None or time.time() - _MM["t"] > 1800:
        lines, cap = [], "free account"
        _, q = cli_json("mmx", ["quota", "show", "--non-interactive"], 40)
        rows = (q or {}).get("model_remains") if isinstance(q, dict) else None
        if rows is None:
            lines.append(("info", "quota: not readable"))
        else:
            got = [r for r in rows if (r.get("current_interval_total_count") or 0) > 0 or (r.get("current_weekly_total_count") or 0) > 0]
            if got:
                txt = "  ·  ".join(f"{r.get('model_name')} {r.get('current_interval_total_count') or 0}/5h, "
                                   f"{r.get('current_weekly_total_count') or 0}/wk" for r in got)
                lines.append(("free", "quota reported: " + txt))
                cap = "MiniMax reports quota"
            else:
                lines.append(("info", "no plan quota reported  ·  free account"))
        _MM.update(t=time.time(), lines=lines, cap=cap)
    return status_card("MiniMax", True, _MM["lines"], _MM["cap"])


def fetch_gemini():
    """Gemini via Antigravity (2026-11-10). Antigravity reports its own usage windows (the numbers of its /usage
    command); T3 Code stores the latest reading in ~/.t3/caches/antigravity.json, read here (no token touched).
    Windows as Antigravity reports them (e.g. Gemini 5-hour + weekly, shared Claude & GPT windows). Sign-in = the cache
    says authenticated, or ~/.gemini/oauth_creds.json exists. GEMINI_API_KEY, if set, is checked with a token-free
    models listing (connected / rejected); the API reports neither usage nor billing tier, so none is shown.
    The plan pill and any extra lines come only from the settings (gemini_badge, gemini_notes), never from a check."""
    out = {"name": "Gemini", "plan": "", "meters": [], "notes": [], "error": None}
    try:
        d = json.load(open(T3_AG_CACHE, encoding="utf-8"))
    except Exception:
        d = None
    signed = bool(d and (d.get("auth") or {}).get("status") == "authenticated")
    if not signed and os.path.isfile(os.path.join(GEMINI_DIR, "oauth_creds.json")):
        signed = True
    out["signed"] = signed
    out["notes"].append(("ok", "Antigravity signed in") if signed else ("bad", "Antigravity not signed in"))
    ul = (d or {}).get("usageLimits") or {}
    checked = parse_iso(ul.get("checkedAt"))
    gone = 0
    for w in ul.get("windows") or []:
        pct = w.get("usedPercent")
        if pct is None:
            continue
        wid = w.get("id") or ""
        mins = w.get("windowDurationMins")
        resets = parse_iso(w.get("resetsAt"))
        if resets and resets < time.time():
            gone += 1        # that window reset after the reading: its new value is unknown
            continue
        kind = "session" if w.get("kind") == "session" else "weekly_all"
        span = "5-hour" if mins == 300 else ("Weekly" if mins == 10080 else (w.get("label") or "").split("·")[-1].strip())
        who = (w.get("label") or "").split("·")[0].replace("(shared)", "").strip()
        who = "" if who == "Gemini" else who.replace("Gemini 4 ", "").replace("Gemini ", "")
        short = {"Claude & GPT": "C&G "}.get(who, who + " " if who else "")
        out["meters"].append({"key": f"gemini:{kind}:{wid}", "label": f"{who} · {span}" if who else span,
                              "order": (0 if not who else 2 if "Claude" in who else 1, 0 if kind == "session" else 1),
                              "short": short + span.replace("5-hour", "5h").replace("Weekly", "Week"),
                              "minor": bool(who),   # compact view skips these while unused
                              "pct": float(pct), "resets_at": resets, "window": mins * 60 if mins else None,
                              "active": False})
    out["meters"].sort(key=lambda m: m.pop("order"))
    idle = [m for m in out["meters"] if m["minor"] and m["pct"] <= 0]
    if idle:   # unused secondary windows: one quiet line instead of empty bars (still real 0 % readings)
        out["meters"] = [m for m in out["meters"] if m not in idle]
        groups = {}
        for m in idle:
            who, _, span = m["short"].rpartition(" ")
            groups.setdefault(who.replace("C&G", "Claude & GPT"), []).append(span.replace("Week", "wk"))
        out["notes"].append(("info", "unused: " + "  ·  ".join(f"{k} {', '.join(v)}" for k, v in groups.items())))
    if not ul:
        out["notes"].append(("info", "Antigravity quota: unknown (no reading yet)"))
    elif checked and time.time() - checked > 1800:
        out["notes"].append(("info", f"Antigravity reading from {fmt_time(checked)}{TZ_SUFFIX}"))
    if gone:
        out["notes"].append(("info", "a window reset since the last reading: unknown"))
    if S["gemini_badge"]:
        out["badge"] = S["gemini_badge"]    # plan pill, from the settings (e.g. "AI Pro")
    out["notes"].append(gemini_key_note())
    for line in S["gemini_notes"] or []:
        out["notes"].append(("info", str(line)))
    return out


_GKEY = {"t": 0.0, "note": None}


def gemini_key_note():
    """State of the Gemini API key (GEMINI_API_KEY user env). Checked with a token-free models listing at most
    every 30 min; the key goes only in the request header, never in a URL, log or the panel. The API reports
    no usage or rate-limit numbers (no headers, no endpoint), so none are shown."""
    key = user_env("GEMINI_API_KEY")
    if not key:
        return ("bad", "API key not connected")
    if _GKEY["note"] and time.time() - _GKEY["t"] < 1800:
        return _GKEY["note"]
    try:
        http_json("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1", {"x-goog-api-key": key})
        note = ("ok", "API key connected · usage not reported")
    except urllib.error.HTTPError as e:
        note = ("bad", f"API key rejected (HTTP {e.code})")
    except Exception:
        note = ("info", "API key set · check failed (network)")
    _GKEY.update(t=time.time(), note=note)
    return note


def user_env(name):
    """A user environment variable, from the registry if the process env predates it; the value stays in memory."""
    v = os.environ.get(name)
    if v:
        return v
    try:
        import winreg as _wr
        with _wr.OpenKey(_wr.HKEY_CURRENT_USER, "Environment") as k:
            return _wr.QueryValueEx(k, name)[0]
    except Exception:
        return None


def _money(v):
    try:
        return float(v)
    except Exception:
        return None


# ---- big fat fish: 蓝色大肥鱼 = DeepSeek (the community's name for its blue whale-maid girl, who loves white rice) ----
def fetch_big_fat_fish():
    """Big fat fish (DeepSeek) account balance (2026-11-10), read the way DeepSeek Harness reads it: the Platform account grant
    from ~/.dsh/.credentials.yaml goes in the x-dsh-auth-token header to platform.deepseek.com
    /api/v0/users/get_user_summary. normal_wallets = topped-up credit, bonus_wallets = granted credit.
    The grant is only read, never written, logged or printed. No reading -> error text, never a made-up 0."""
    out = {"name": "DeepSeek", "plan": "", "meters": [], "notes": [], "error": None}
    try:
        import re as _re
        txt = open(DSH_CRED, encoding="utf-8").read()
        tok = _re.search(r"deepseek-account-platform/default:.*?token:\s*(\S+)", txt, _re.S).group(1)
    except Exception:
        out["error"] = "DeepSeek Harness not signed in"
        return out
    try:
        d = http_json("https://platform.deepseek.com/api/v0/users/get_user_summary",
                      {"x-dsh-auth-token": tok, "Accept": "application/json", "User-Agent": "ai-limits-monitor/2"})
    except urllib.error.HTTPError as e:
        out["error"] = f"DeepSeek balance: HTTP {e.code}"
        return out
    except Exception as e:
        out["error"] = f"DeepSeek balance: {type(e).__name__}"
        return out
    if d.get("code") == 40003:
        out["error"] = "DeepSeek sign-in expired: open DeepSeek Harness"
        return out
    biz = ((d.get("data") or {}).get("biz_data")) or {}
    if d.get("code") != 0 or not isinstance(biz, dict) or "normal_wallets" not in biz:
        out["error"] = "DeepSeek balance: unknown reply"
        return out

    def total(rows):
        t = {}
        for r in rows or []:
            v = _money(r.get("balance"))
            if v is not None:
                c = r.get("currency") or "?"
                t[c] = t.get(c, 0.0) + v
        return t
    topped, granted = total(biz.get("normal_wallets")), total(biz.get("bonus_wallets"))
    spent = {r.get("currency") or "?": _money(r.get("amount")) for r in biz.get("total_costs") or []}
    cur = next(iter(topped or granted or {"CNY": 0}), "CNY")
    sym = {"CNY": "¥", "USD": "$"}.get(cur, cur + " ")
    tp, gr = topped.get(cur, 0.0), granted.get(cur, 0.0)
    bal = tp + gr
    out["balance"] = {"currency": cur, "total": round(bal, 2), "topped_up": round(tp, 2), "granted": round(gr, 2),
                      "spent_total": round(spent.get(cur) or 0, 2)}
    out["pills"] = [(f"{sym}{bal:,.2f}", "bad" if bal <= 0 else "ok")]
    # rice bowls, not coins: the big fat fish's balance is her bowl of rice (2026-11-10)
    out["notes"].append(("rice_bad" if bal <= 0 else "rice_ok", f"Balance {sym}{bal:,.2f}" + ("  ·  API calls fail" if bal <= 0 else "")))
    out["notes"].append(("info", f"topped-up {sym}{tp:,.2f}  ·  granted {sym}{gr:,.2f}"
                         + (f"  ·  spent {sym}{spent[cur]:,.2f}" if spent.get(cur) else "")))
    return out


AVATAR_KEY = {"Claude": "claude", "Codex": "codex_gpt", "Grok": "grok", "Gemini": "gemini", "DeepSeek": "deepseek",
              "GLM": "glm", "Kimi": "kimi", "Qwen": "qwen", "Wenxin": "wenxin", "Doubao": "doubao", "MiniMax": "minimax"}
DISPLAY_NAME = {"Codex": "GPT · Codex", "Qwen": "Qwen 千问", "Wenxin": "文心一言", "Doubao": "Doubao 豆包", "GLM": "GLM 智谱"}   # CJK strings are drawn in Microsoft YaHei UI


def fmt_time(ts):
    """Clock time in the configured zone (time_zone setting: local, or a fixed UTC offset)."""
    if not ts:
        return ""
    t = dt.datetime.fromtimestamp(ts, TZ)
    now = dt.datetime.now(TZ)
    if t.date() == now.date():
        return t.strftime("%H:%M")
    return t.strftime("%a %H:%M")


def fmt_left(ts):
    if not ts:
        return ""
    s = int(ts - time.time())
    if s <= 0:
        return "resetting"
    d, r = divmod(s, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


FETCHERS = {"Claude": fetch_claude, "Codex": fetch_codex, "Gemini": fetch_gemini,
            "DeepSeek": fetch_big_fat_fish, "Grok": fetch_grok,                     # big fat fish = DeepSeek
            "Kimi": fetch_kimi, "Qwen": fetch_qwen, "Doubao": fetch_doubao,         # free-account status cards
            "GLM": fetch_glm, "MiniMax": fetch_minimax}


# ---------- demo: sample data only (screenshots, trying the look); nothing is read from any account ----------
def demo_results():
    now = time.time()
    H, D = 3600, 86400
    m = lambda key, label, pct, left, window, **kw: dict(key=key, label=label, pct=float(pct), window=window,
                                                         resets_at=(now + left) if left else None, active=False, **kw)
    return {
        "Claude": {"name": "Claude", "plan": "Sample", "notes": [], "error": None, "meters": [
            m("claude:session:", "5-hour", 34, 2 * H + 10 * 60, 5 * H),
            m("claude:weekly_all:", "Weekly · all models", 58, 3 * D + 5 * H, 7 * D),
            m("claude:weekly_scoped:Opus", "Weekly · Opus", 41, 3 * D + 5 * H, 7 * D),
            m("claude:extra", "Extra usage · month", 12, None, None, detail="$6.00 of $50")]},
        "Codex": {"name": "Codex", "plan": "Sample", "error": None,
                  "meters": [m("codex:main:604800", "Weekly", 27, 4 * D + 2 * H, 7 * D)],
                  "notes": [("ok", "frontier model: available")]},
        "Gemini": {"name": "Gemini", "plan": "", "error": None, "badge": "Pro", "meters": [
            dict(m("gemini:session:gemini-5h", "5-hour", 12, 3 * H + 40 * 60, 5 * H), short="5h", minor=False),
            dict(m("gemini:weekly_all:gemini-weekly", "Weekly", 9, 5 * D, 7 * D), short="Week", minor=False)],
            "notes": [("ok", "Antigravity signed in"), ("ok", "API key connected · usage not reported")]},
        "DeepSeek": {"name": "DeepSeek", "plan": "", "meters": [], "error": None,
                     "pills": [("¥12.50", "ok")],
                     "notes": [("rice_ok", "Balance ¥12.50"), ("info", "topped-up ¥10.00  ·  granted ¥2.50")]},
        "Grok": dict(status_card("Grok", True), status_lines=[]),
        "Kimi": status_card("Kimi", True, [("info", "no plan quota reported  ·  free account")], "free account"),
        "Qwen": status_card("Qwen", False, [("info", "free sign-in: open qianwen.com")], "free sign-in missing"),
        "Doubao": status_card("Doubao", True, [("free", "18 models × 500k tokens, none used")], "free quota"),
        "GLM": status_card("GLM", True, [("info", "no balance or quota reported for free keys")], "free key"),
        "MiniMax": status_card("MiniMax", True, [("info", "no plan quota reported  ·  free account")], "free account"),
    }


def _demo_fetcher(name):
    f = lambda: demo_results()[name]
    f.__name__ = "fetch_" + name.lower()
    return f


ALL_FETCHERS = tuple((_demo_fetcher(n) if DEMO else FETCHERS[n]) for n in S["services"] if n in FETCHERS)
