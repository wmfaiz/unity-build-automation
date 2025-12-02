import datetime
import json
import os
import tempfile
import shlex
import signal
import threading
import re
import time
import qrcode
from copy import deepcopy
from pathlib import Path
from zoneinfo import ZoneInfo
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt import App
from datetime import datetime as _dt, timedelta as _td
from slack_sdk.errors import SlackApiError
from team_kpi import get_team_kpi, render_team_kpi

SLACK_BOT_TOKEN = ""
SIGNING_SECRET = ""
SERVO_CHANNEL = ""
DREAM_TEAM_KPI_CHANNEL = ""
DREAM_TEAM_CHANNEL = ""
SERVO_AUTOMATION_TEST_CHANNEL = ""
DREAM_TEAM_DR_CHANNEL = ""
DREAM_TEAM_CLIENT = ""
SLACK_SOCKET_TOKEN = ""
BOT_ID = ""

MARKER = "[SERVO-KPI]"
TRACKER_PATH = str((Path(__file__).parent / "performance_tracker.json").resolve())
TRIGGER_HOUR = 21
VALID_ENVS = {"dev", "qa", "staging", "production", "all", "info"}

LOCAL_TZ = ZoneInfo("Asia/Kuala_Lumpur")

app = App(token=SLACK_BOT_TOKEN, signing_secret=SIGNING_SECRET)

qr_links = {
    "DEVELOP_ENV": "https://play.google.com/apps/internaltest/4701158443482208291",
    "QA_ENV": "https://play.google.com/apps/internaltest/4701620813803337968",
    "STAGING_ENV": "https://play.google.com/apps/internaltest/4700827826336852918",
    "PRODUCTION_ENV": "https://play.google.com/apps/internaltest/4701437123017158629",
}

env_map = {
    "DEVELOP_ENV": "Develop",
    "QA_ENV": "QA",
    "STAGING_ENV": "Staging",
    "PRODUCTION_ENV": "Production",
}

valid_sign_off_map = {
    "dev": "Develop",
    "qa": "QA",
    "stag": "Staging",
    "prod": "Production",
}

def upload_file_via_client(client, channel_id, file_path, title="Uploaded file"):
    try:
        client.files_upload_v2(
            channel=channel_id,
            file=file_path,
            title=title,
            initial_comment="Scan to download"
        )
    except Exception as e:
        client.chat_postMessage(
            channel=channel_id,
            text=f":warning: Failed to upload {title} QR: {e}"
        )

def link_to_qr(env_name):
    url = qr_links[env_name]
    output_dir = "QR"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{env_name}_qr.png")
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_file)
    return output_file

def build_release_message_and_send(env_name, version, android_build_id, ios_build_id, logs=None):
    env_label = env_map[env_name.upper()]
    if env_label != "Develop":
        message = (
            "<!here>\n"
            f"New *{env_label}* build for Android and iOS is ready!\n"
            f"*Please wait 10–15 minutes before download.*\n\n"
            f"Android *{env_label} — v{version} ({android_build_id - 1})*\n"
            f"iOS *{env_label} — v{version} ({ios_build_id})*\n"
        )
        app.client.chat_postMessage(channel=SERVO_CHANNEL, text=message)
    else:
        message = (
            f"New *{env_label}* build for Android and iOS is ready!\n"
            f"*Please wait 10–15 minutes before download.*\n\n"
            f"Android *{env_label} — v{version} ({android_build_id - 1})*\n"
            f"iOS *{env_label} — v{version} ({ios_build_id})*\n"
        )
        app.client.chat_postMessage(channel=SERVO_CHANNEL, text=message)
    
    qr_path = link_to_qr(env_name)        
    if qr_path:
        upload_file_via_client(app.client, SERVO_CHANNEL, qr_path, title=f"{env_label}_QR")
    if logs:
        build_log(logs)

def build_log(logs):
    logs = logs.strip()
    try:
        if len(logs) < 39000:
            app.client.chat_postMessage(channel=SERVO_CHANNEL, text=f"```\n{logs}\n```")
        else:
            preview = logs[:500] + "\n...\n(full log uploaded as file)"
            response = app.client.chat_postMessage(channel=SERVO_CHANNEL, text=f"```\n{preview}\n```")
            build_message_ts = response["ts"]
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as tmpfile:
                tmpfile.write(logs)
                tmp_path = tmpfile.name
            app.client.files_upload_v2(channel=SERVO_CHANNEL, file=tmp_path, filename="build_log.txt", title="Build Log", thread_ts=build_message_ts)
            os.remove(tmp_path)
    except SlackApiError as e:
        print(f"[Slack Upload Error] {e.response['error']}")
    except Exception as e:
        print(f"[Slack Upload Failed] {e}")

def build_status_update(env_name, version, message_body):
    env_label = env_map[env_name.upper()]
    message = (
        f"*{env_label} v{version}* {message_body}"
    )
    app.client.chat_postMessage(channel=SERVO_CHANNEL, text=message)

def _run_build_async(env_name, version, note, branch, channel, user):
    client = app.client
    try:
        client.chat_postMessage(
            channel=channel,
            text=f":hourglass_flowing_sand: <@{user}>, your *{env_name}* build is starting…"
        )
        import main
        if env_name == "info":
            main.info()
        elif env_name == "all":
            main.all_environment(branch)(version, note)
        else:
            builders = {
                "dev": main.dev,
                "qa": main.qa,
                "staging": main.staging,
                "production": main.production,
            }
            try:
                builder_factory = builders[env_name]
            except KeyError:
                client.chat_postMessage(channel=channel, text=f":x: Unknown environment `{env_name}`.")
                return
            builder = builder_factory(branch)
            builder(version, note)
        client.chat_postMessage(channel=channel, text=f"<@{user}> *{env_name}* build finished.")
    except Exception as e:
        client.chat_postMessage(channel=channel, text=f"<@{user}> *{env_name}* build failed: `{e}`")

@app.message(r"^!SERVO\s+")
def handle_servo(ack, message, say, client):
    ack()
    text = message.get("text", "").strip()
    channel = message["channel"]
    user = message["user"]
    if channel == SERVO_CHANNEL:
        try:
            parts = shlex.split(text)
        except ValueError:
            return client.chat_postEphemeral(channel=channel, user=user, text="Parse error. Make sure your quotes are balanced.")
        if len(parts) < 2 or parts[0].upper() != "!SERVO":
            return None
        env_name = parts[1].lower()
        if env_name not in VALID_ENVS:
            return client.chat_postEphemeral(channel=channel, user=user, text=f"<@{user}> invalid environment `{env_name}`; must be one of {', '.join(sorted(VALID_ENVS))}.")
        flags = {}
        i = 2
        while i < len(parts):
            if parts[i].startswith("--"):
                key = parts[i][2:]
                val = parts[i+1] if i+1 < len(parts) and not parts[i+1].startswith("--") else None
                flags[key] = val
                i += 2 if val is not None else 1
            else:
                i += 1
        version = flags.get("version")
        note = flags.get("note")
        branch  = flags.get("branch")
        if env_name not in {"info", "all"} and (not version or not note):
            return client.chat_postEphemeral(channel=channel, user=user, text="Both --version and --note are required.\nExample: `!SERVO dev --version 1.2.3 --note \"QA smoke: login + shop\"`")
        if version and not re.match(r"^\d+\.\d+\.\d+$", version):
            return client.chat_postEphemeral(channel=channel, user=user, text=f"<@{user}> invalid version: `{version}`. Use X.Y.Z (e.g., 1.2.3).")
        say(f":arrow_forward: <@{user}> queued *{env_name}* v{version or 'N/A'}…")
        threading.Thread(target=_run_build_async, args=(env_name, version, note, branch, channel, user), daemon=True).start()
        return None
    elif channel == DREAM_TEAM_KPI_CHANNEL:
        command = text[len("!SERVO "):].strip().lower()
        if command == "report":
            threading.Thread(target=_do_kpi_job, daemon=True).start()
        return None
    elif channel == DREAM_TEAM_CLIENT:
        try:
            parts = shlex.split(text)
        except ValueError:
            return client.chat_postEphemeral(channel=channel, user=user, text="Parse error. Make sure your quotes are balanced.")
        if len(parts) < 2 or parts[0].upper() != "!SERVO":
            return None
        env_name = parts[2].lower()
        flags = {}
        i = 3
        saw_version = False
        if i < len(parts) and not parts[i].startswith("--") and parts[i].lower() not in ("version", "at"):
            flags["version"] = parts[i]
            saw_version = True
            i += 1
        while i < len(parts):
            tok = parts[i]
            if tok.startswith("--"):
                key = tok[2:]
                val = parts[i+1] if i+1 < len(parts) and not parts[i+1].startswith("--") else None
                flags[key] = val
                i += 2 if val else 1
            elif tok in ("version", "at") and i+1 < len(parts):
                flags[tok] = parts[i+1]
                i += 2
            elif tok == "at" and i+1 < len(parts):
                flags["at"] = parts[i+1]
                i += 2
            else:
                i += 1
        what_time = flags.get("at")
        version = flags.get("version")
        build_sign_off(env_name, version, what_time)
        return None
    return None

@app.event("message")
def ignore_non_user_messages(event, say):
    subtype = event.get("subtype")
    if subtype in {"channel_join", "channel_leave", "bot_message", "message_changed"}:
        return
    if subtype is None:
        text = event.get("text", "")
        if not text.strip().startswith("!SERVO"):
            return

#----------------------------------------
# Game KPI - START
def _within_trigger_window(now_local: datetime.datetime) -> bool:
    target = now_local.replace(hour=TRIGGER_HOUR, minute=0, second=0, microsecond=0)
    delta = abs((now_local - target).total_seconds()) / 60.0
    return delta <= 59

def _do_kpi_job():
    from ch_kpi import get_kpi
    try:
        now_local = datetime.datetime.now(LOCAL_TZ)
        if not _within_trigger_window(now_local):
            return
        if _slack_has_message_recent(app.client, DREAM_TEAM_KPI_CHANNEL, "[production]", bot_id=BOT_ID, lookback_hours=20):
            return
        kpi_text = get_kpi()
        app.client.chat_postMessage(channel=DREAM_TEAM_KPI_CHANNEL, text=f"{kpi_text}")
    except Exception as e:
        app.client.chat_postMessage(channel=DREAM_TEAM_KPI_CHANNEL, text=f":warning: Daily KPI job failed: {e}")


def _cron_job_for_game_kpi():
    def schedule_daily(hour=21, minute=0):
        while True:
            now = datetime.datetime.now(LOCAL_TZ)
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            delay = (target - now).total_seconds()
            print(f"[KPI Scheduler] Sleeping {delay/3600:.2f} hours until {target}")
            time.sleep(delay)
            _do_kpi_job()
    threading.Thread(target=schedule_daily, daemon=True).start()
# Game KPI - END
#----------------------------------------
# Team KPI - START

def _slot_bounds(now=None, interval_hours=4, tz=LOCAL_TZ):
    now = now or datetime.datetime.now(tz)
    floored_hour = (now.hour // interval_hours) * interval_hours
    start = now.replace(hour=floored_hour, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(hours=interval_hours)
    return start, end

def _slot_key(channel_id: str, marker: str, slot_start: datetime.datetime):
    return f"{channel_id}:{marker}:{slot_start.astimezone(datetime.timezone.utc).isoformat()}"

def _load_sent_index(path=".periodic_sent.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_sent_index(index, path=".periodic_sent.json"):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    os.replace(tmp, path)

def _mark_sent_local(channel_id, marker, slot_start, index_path=".periodic_sent.json"):
    idx = _load_sent_index(index_path)
    idx[_slot_key(channel_id, marker, slot_start)] = True
    _save_sent_index(idx, index_path)

def _is_marked_sent_local(channel_id, marker, slot_start, index_path=".periodic_sent.json"):
    idx = _load_sent_index(index_path)
    return idx.get(_slot_key(channel_id, marker, slot_start), False)

def _slack_has_message_recent(web_client, channel_id, marker, bot_id=None, lookback_hours=4):
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    oldest_ts = (now_utc - datetime.timedelta(hours=lookback_hours)).timestamp()
    latest_ts = now_utc.timestamp()
    cursor = None
    while True:
        resp = web_client.conversations_history(
            channel=channel_id,
            oldest=str(oldest_ts),
            latest=str(latest_ts),
            limit=200,
            inclusive=True,
            cursor=cursor
        )
        for m in resp.get("messages", []):
            text = (m.get("text") or "")
            if marker in text and (bot_id is None or m.get("bot_id") == bot_id):
                return True
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return False

def _slack_has_message_in_slot(web_client, channel_id, slot_start, slot_end, marker, bot_id) -> bool:
    oldest = slot_start.astimezone(datetime.timezone.utc).timestamp()
    latest = slot_end.astimezone(datetime.timezone.utc).timestamp()
    cursor = None
    while True:
        resp = web_client.conversations_history(
            channel=channel_id,
            oldest=str(oldest),
            latest=str(latest),
            limit=200,
            inclusive=True,
            cursor=cursor
        )
        for m in resp.get("messages", []):
            text = (m.get("text") or "")
            if marker in text and (bot_id is None or m.get("bot_id") == bot_id):
                return True
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return False

@app.action("show_buckets")
def on_show_buckets(ack, body, client, logger):
    ack()
    try:
        action = body["actions"][0]
        buckets = json.loads(action.get("value") or "{}")
        lines = [f"{k}: {v}" for k, v in (buckets or {}).items()]
        text = "```\n" + "\n".join(lines) + "\n```" if lines else "_No bucket data available_"
        client.chat_postEphemeral(channel=body["channel"]["id"], user=body["user"]["id"], text=text)
    except Exception as e:
        logger.exception(f"[show_buckets] failed: {e}")

def _bucket_labels(interval_hours=4):
    return [f"{h:02d}-{min(h+interval_hours,24):02d}" for h in range(0, 24, interval_hours)]

def _today_key(tz=LOCAL_TZ):
    return _dt.now(tz).strftime("%Y-%m-%d")

def _load_tracker(path=TRACKER_PATH):
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

def _materialize_buckets(raw: dict | None, interval_hours=4):
    labels = _bucket_labels(interval_hours)
    raw = raw or {}
    return {lbl: raw.get(lbl, "NOT ACTIVE") for lbl in labels}

def _pfid_from_sid(sid: str) -> str | None:
    parts = sid.split("-", 2)
    return parts[1] if len(parts) >= 3 else None

def read_buckets_from_tracker(pfid: str | None, *, path=TRACKER_PATH, tz=LOCAL_TZ, interval_hours=4):
    if not pfid or pfid == "MIA":
        return _materialize_buckets(None, interval_hours)
    data = _load_tracker(path)
    if data.get("__date") != _today_key(tz):
        return _materialize_buckets(None, interval_hours)
    return _materialize_buckets(data.get(pfid), interval_hours)

@app.action("toggle_buckets")
def on_toggle_buckets(ack, body, client, logger):
    ack()
    try:
        action = body["actions"][0]
        payload = json.loads(action["value"])
        sid = payload.get("sid", "")
        pfid = payload.get("pfid") or _pfid_from_sid(sid)
        buckets_map = read_buckets_from_tracker(pfid, path=TRACKER_PATH, tz=LOCAL_TZ, interval_hours=4)
        lines = [f"{k}: {v}" for k, v in buckets_map.items()]
        details_text = "```\n" + "\n".join(lines) + "\n```" if lines else "_No bucket data available_"
        channel_id = body["channel"]["id"]
        ts = body["message"]["ts"]
        blocks = body["message"]["blocks"]
        row_id = f"row-{sid}"
        det_id = f"detail-{sid}"
        idx = next((i for i, b in enumerate(blocks) if b.get("block_id") == row_id), None)
        if idx is None:
            return
        expanded = (idx + 1 < len(blocks)) and (blocks[idx + 1].get("block_id") == det_id)
        row = dict(blocks[idx])
        if "accessory" in row and "text" in row["accessory"]:
            row["accessory"]["text"]["text"] = "Details ▸" if expanded else "Hide ◂"
        if expanded:
            blocks = blocks[:idx] + [row] + blocks[idx + 2:]
        else:
            detail_block = {
                "type": "section",
                "block_id": det_id,
                "text": {"type": "mrkdwn", "text": details_text}
            }
            blocks = blocks[:idx] + [row, detail_block] + blocks[idx + 1:]
        client.chat_update(channel=channel_id, ts=ts, blocks=blocks, text="Team KPI (updated)")
    except Exception as e:
        logger.exception(f"[toggle_buckets] failed: {e}")

def render_team_kpi_blocks(entries):
    rows = []
    for idx, e in enumerate(entries):
        sid = f"{e['slack_id']}-{e.get('pfid','MIA')}-{idx}"
        rows.append({
            "type": "section",
            "block_id": f"row-{sid}",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{e['name']}\n"
                    f"Last Login: {e['last_login']}\n"
                    f"*ACTIVENESS* ({e['yes_pct']}%)"
                )
            },
            "accessory": {
                "type": "button",
                "action_id": "toggle_buckets",
                "text": {"type": "plain_text", "text": "Details ▸", "emoji": True},
                "value": json.dumps({"sid": sid, "pfid": e["pfid"]})
            }
        })
    return rows

def _today_str():
    return _dt.now(LOCAL_TZ).strftime("%Y-%m-%d")

def find_today_root_ts(client, channel, marker="Team KPI Snapshot @"):
    date_str = _today_str()
    cursor = None
    while True:
        resp = client.conversations_history(channel=channel, limit=200, cursor=cursor)
        for m in resp.get("messages", []):
            if m.get("thread_ts") and m["thread_ts"] != m["ts"]:
                continue
            text = m.get("text", "")
            if marker in text and date_str in text:
                return m["ts"]
            for b in m.get("blocks", []):
                if b.get("type") == "header":
                    ht = b.get("text", {}).get("text", "") or ""
                    if marker in ht and date_str in ht:
                        return m["ts"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return None

def create_today_root(client, channel, marker="Team KPI Snapshot @"):
    now = _dt.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")
    header_blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{marker} {now}", "emoji": True}},
        {"type": "divider"},
    ]
    resp = client.chat_postMessage(channel=channel, text=f"{marker} {now}", blocks=header_blocks)
    return resp["ts"]



TEAM_KPI_CACHE = {"ts": None, "data": None}
TEAM_KPI_LOCK = threading.Lock()

def _snapshot_banner_blocks_at(ts, tz=LOCAL_TZ):
    if not isinstance(ts, datetime.datetime):
        try:
            ts = datetime.datetime.fromtimestamp(float(ts), tz=tz)
        except Exception:
            ts = _dt.now(tz)
    return [
        {"type": "divider"},
        {
            "type": "header",
            "text": {"type": "plain_text",
                     "text": f"Snapshot @ {ts:%Y-%m-%d %H:%M} (+08)",
                     "emoji": True}
        }
    ]

def _sleep_until_next_bucket(interval_hours=4):
    ih = max(1/60, min(float(interval_hours or 4.0), 24.0))
    now = _dt.now(LOCAL_TZ)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    bucket = _td(hours=ih)
    elapsed = now - day0
    rem = (bucket - (elapsed % bucket)) % bucket
    time.sleep(max(1, rem.total_seconds()))

def _fmt_ts(ts, tz=LOCAL_TZ):
    import datetime as _datetime
    if isinstance(ts, _datetime.datetime):
        return ts.strftime("%Y-%m-%d %H:%M")
    try:
        return _datetime.datetime.fromtimestamp(float(ts), tz=tz).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)

def record_team_kpi(record_login_func, interval_hours=4):
    def loop():
        while True:
            _sleep_until_next_bucket(interval_hours)
            try:
                data = record_login_func()
                with TEAM_KPI_LOCK:
                    ts_local = TEAM_KPI_CACHE.get("ts")
                    TEAM_KPI_CACHE["ts"] = ts_local
                    TEAM_KPI_CACHE["data"] = data
            except Exception as e:
                print(f"[LOGIN JOB ERROR] {e}")
    threading.Thread(target=loop, daemon=True).start()

def _sleep_until_next_trigger(trigger_hours=(10, 22)):
    now = _dt.now(LOCAL_TZ)
    hours = sorted(trigger_hours)
    today = now.replace(minute=0, second=0, microsecond=0)
    slots = [today.replace(hour=h) for h in hours]
    if now.hour in trigger_hours:
        return
    next_slot = next((t for t in slots if t > now), None)
    if not next_slot:
        next_slot = slots[0] + _td(days=1)
    time.sleep(max(1, (next_slot - now).total_seconds()))

def post_team_kpi_from_cache(channel_id, marker, web_client):
    with TEAM_KPI_LOCK:
        data = TEAM_KPI_CACHE["data"]
        ts   = TEAM_KPI_CACHE["ts"]
    if not data:
        data = get_team_kpi()
        ts   = _dt.now(LOCAL_TZ)
    blocks = _sanitize_blocks_for_slack(render_team_kpi_blocks(data))
    blocks = _snapshot_banner_blocks_at(ts) + blocks
    root_ts = find_today_root_ts(web_client, channel_id, "Team KPI Snapshot @")
    if not root_ts:
        root_ts = create_today_root(web_client, channel_id, "Team KPI Snapshot @")
    web_client.chat_postMessage(channel=channel_id, thread_ts=root_ts, text=marker, blocks=blocks)

def trigger_slack_team_kpi(job_func, *, job_args=None, channel_id=None,
                           marker="Team KPI Snapshot @", web_client=None,
                           trigger_hours=(10, 22), lookback_hours=12):
    job_args = job_args or []
    sent_today = set()
    def loop():
        nonlocal sent_today
        while True:
            _sleep_until_next_trigger(trigger_hours)
            now_hour = _dt.now(LOCAL_TZ).hour
            if now_hour in sent_today:
                continue
            already_sent = False
            if web_client and channel_id:
                try:
                    already_sent = _slack_has_message_recent(
                        web_client,
                        channel_id,
                        marker=marker,
                        bot_id=BOT_ID,
                        lookback_hours=lookback_hours
                    )
                except Exception as e:
                    print(f"[PERIODIC GUARD] Slack check failed: {e}")
                    already_sent = True
            if not already_sent:
                try:
                    job_func(*job_args)
                    sent_today.add(now_hour)
                except Exception as e:
                    print(f"[PERIODIC JOB ERROR] {e}")
            if now_hour == 0:
                sent_today.clear()
    threading.Thread(target=loop, daemon=True).start()
    
def _split_header_and_rows(blocks):
    if not blocks:
        return [], []
    header = []
    rows = blocks[:]
    if blocks[0].get("type") == "header":
        header = [blocks[0]]
        rows = blocks[1:]
    if rows and rows[-1].get("type") == "divider":
        header.append(rows[-1])
        rows = rows[:-1]
    return header, rows

def _chunk(blocks, max_blocks=45):
    buf = []
    for b in blocks:
        if len(buf) >= max_blocks:
            yield buf
            buf = []
        buf.append(b)
    if buf:
        yield buf

def _sanitize_blocks_for_slack(blocks):
    if not isinstance(blocks, list):
        return [{
            "type": "section",
            "text": {"type": "mrkdwn", "text": str(blocks)}
        }]
    b2 = deepcopy(blocks)
    for b in b2:
        acc = b.get("accessory")
        if isinstance(acc, dict) and acc.get("type") == "button":
            t = acc.get("text")
            if not isinstance(t, dict) or t.get("type") != "plain_text":
                label = t if isinstance(t, str) else "Details ▸"
                acc["text"] = {"type": "plain_text", "text": label, "emoji": True}
    return b2

def _thread_has_replies(client, channel, root_ts) -> bool:
    r = client.conversations_replies(channel=channel, ts=root_ts, limit=2)
    return len(r.get("messages", [])) > 1

def _snapshot_banner_blocks():
    now = _dt.now(LOCAL_TZ)
    return [
        {"type": "divider"},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Snapshot @ {now:%Y-%m-%d %H:%M} (+08)",
                "emoji": True
            }
        }
    ]

# Team KPI - END
#----------------------------------
# Sign off flow - START
STATE = {"notes": {}, "confirmed": set(), "signer": {} }
TEAM_ID = [
    "U044QQ0D68M",  # Hiro-san
    "UKC6RHSER",    # Amir
    "U07TH9APDMM",  # Fatin
    "UK707R508",    # Naim
    "U03QV7379CL",  # Tariq
    "U03HRP4VA2W",  # Shahrul
    "U071D1ZCAF9",  # Alwi
    "U080E6RBK2N",  # Imran
    "U08NUEV5NAG",  # Faiz
]

STATE.setdefault("notes", {})
STATE.setdefault("confirmed", set())
STATE.setdefault("signer", {})
STATE.setdefault("row_ts", {})
STATE.setdefault("posted_rows", set())
STATE.setdefault("last_signoff_ts", 0)
STATE.setdefault("locked_at", {})

def _require_defined(name, value):
    if value in (None, "", []):
        raise RuntimeError(f"[signoff] Missing required config: {name}")

def _safe_chat_postMessage(client, **kwargs):
    while True:
        try:
            resp = client.chat_postMessage(**kwargs)
            return resp
        except SlackApiError as e:
            err = getattr(e, "response", None)
            code = getattr(err, "status_code", None)
            if code == 429:
                retry_after = int(err.headers.get("Retry-After", "1") or "1")
                print(f"[signoff] Rate limited. Retrying in {retry_after}s …")
                time.sleep(retry_after)
                continue
            msg = err.data.get("error") if err and hasattr(err, "data") else str(e)
            raise RuntimeError(f"[signoff] chat_postMessage failed: {msg}") from e

def _safe_chat_update(client, **kwargs):
    while True:
        try:
            return client.chat_update(**kwargs)
        except SlackApiError as e:
            err = getattr(e, "response", None)
            code = getattr(err, "status_code", None)
            if code == 429:
                retry_after = int(err.headers.get("Retry-After", "1") or "1")
                print(f"[signoff] Rate limited (update). Retrying in {retry_after}s …")
                time.sleep(retry_after)
                continue
            msg = err.data.get("error") if err and hasattr(err, "data") else str(e)
            raise RuntimeError(f"[signoff] chat_update failed: {msg}") from e

def _note_line(uid: str) -> str:
    status = "✅ *Sign Off*" if uid in STATE["confirmed"] else "_Not Sign Off_"
    note = (STATE["notes"].get(uid) or "").strip() or "_No note_"
    signer = STATE["signer"].get(uid)
    signer_text = f" _(signed by <@{signer}> )_" if signer else ""
    return f"{status} · {note}{signer_text}"

def _has_note(uid: str) -> bool:
    note = (STATE["notes"].get(uid) or "").strip()
    return bool(note) and note != "_No note_"

def _lock_user_row(blocks, uid: str):
    for i, b in enumerate(list(blocks)):
        if b.get("block_id") == f"actions-{uid}":
            del blocks[i]
            break
    for b in blocks:
        if b.get("block_id") == f"ctx-{uid}":
            t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            b["elements"][0]["text"] = _note_line(uid) + f"\n:lock: *Locked* {t}"
            break
    return blocks

def _post_signoff_row(client, channel_id, root_ts, uid):
    key = f"{channel_id}:{root_ts}:{uid}"
    if key in STATE["posted_rows"]:
        print(f"[SKIP DUP] already posted row for {key}")
        return
    STATE["posted_rows"].add(key)

    section = {
        "type": "section",
        "block_id": f"row-{uid}",
        "text": {"type": "mrkdwn", "text": f"<@{uid}>"}
    }
    opt = {"text": {"type": "plain_text", "text": "Sign off"}, "value": f"confirmed-{uid}"}
    actions = {
        "type": "actions",
        "block_id": f"actions-{uid}",
        "elements": [{
            "type": "checkboxes",
            "action_id": f"confirm-{uid}",
            "options": [opt],
            **({"initial_options": [opt]} if uid in STATE["confirmed"] else {})
        }]
    }
    context = {
        "type": "context",
        "block_id": f"ctx-{uid}",
        "elements": [{"type": "mrkdwn", "text": _note_line(uid)}]
    }

    resp = _safe_chat_postMessage(
        client,
        channel=channel_id,
        thread_ts=root_ts,
        text=f"Sign off — <@{uid}>",
        blocks=[section, actions, context],
        unfurl_links=False,
        unfurl_media=False
    )
    STATE["row_ts"][uid] = resp["ts"]

def build_sign_off(env_name, version, what_time, *, force: bool = False, min_interval_sec: int = 5):
    _require_defined("DREAM_TEAM_CLIENT", DREAM_TEAM_CLIENT)
    _require_defined("TEAM_ID", TEAM_ID)
    now = time.time()
    last = STATE.get("last_signoff_ts", 0)
    if not force and (now - last) < min_interval_sec:
        print(f"[SKIP] build_sign_off called twice within {min_interval_sec}s")
        return
    env_label = valid_sign_off_map.get(env_name, env_name)
    STATE["env_label"] = env_label
    STATE["version"] = version
    STATE["what_time"] = what_time

    blocks = _build_all_blocks(env_label, version, what_time)

    parent = _safe_chat_postMessage(
        app.client,
        channel=DREAM_TEAM_CLIENT,
        text=f"{env_label} build reminder",
        blocks=blocks,
    )
    STATE["root"] = {"channel": parent["channel"], "ts": parent["ts"]}

def _get_thread_msg_by_ts(client, channel: str, thread_ts: str, target_ts: str):
    resp = client.conversations_replies(channel=channel, ts=thread_ts, limit=200)
    for m in resp.get("messages", []):
        if m.get("ts") == target_ts:
            return m
    raise RuntimeError(
        f"[signoff] Could not find row message in thread: channel={channel}, "
        f"thread_ts={thread_ts}, target_ts={target_ts}"
    )

def _row_blocks(uid: str, *, checked: bool = False):
    section = {
        "type": "section",
        "block_id": f"row-{uid}",
        "text": {"type": "mrkdwn", "text": f"<@{uid}>"}
    }
    opt = {"text": {"type": "plain_text", "text": "Sign off"}, "value": f"confirmed-{uid}"}
    check = {
        "type": "checkboxes",
        "action_id": f"confirm-{uid}",
        "options": [opt]
    }
    if checked or (uid in STATE["confirmed"]):
        check["initial_options"] = [opt]
    actions = {"type": "actions", "block_id": f"actions-{uid}", "elements": [check]}
    context = {
        "type": "context",
        "block_id": f"ctx-{uid}",
        "elements": [{"type": "mrkdwn", "text": _note_line(uid)}]
    }
    return [section, actions, context]

def _locked_blocks(uid: str):
    section = {
        "type": "section",
        "block_id": f"row-{uid}",
        "text": {"type": "mrkdwn", "text": f"<@{uid}>"}
    }
    t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    ctx_text = _note_line(uid) + f"\n:lock: *Locked* {t}"
    context = {
        "type": "context",
        "block_id": f"ctx-{uid}",
        "elements": [{"type": "mrkdwn", "text": ctx_text}]
    }
    return [section, context]

def _build_all_blocks(env_label, version, what_time):
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text":
                f"<!here>\nReminder: *{env_label}* build at {what_time}\n"
                f"*For client side* please do the following.\n\n"
                f":white_check_mark: Pull latest update\n"
                f":white_check_mark: Push your work\n"
                f":white_check_mark: Switch to the {version} branch\n"
                f":white_check_mark: Test and confirm your fixes/updates on {version} branch\n\n"
                f"*For the rest of the team* please review and confirm this build is ready to proceed.\n\n"
                f"Click *Sign off* when you finish, Thank you!.\n"
                f"*FOR LAST MINUTE PUSHES PLEASE INFORM <@U08NUEV5NAG>*"
                     }
        },
        {"type": "divider"}
    ]
    for uid in TEAM_ID:
        section = {
            "type": "section",
            "block_id": f"row-{uid}",
            "text": {"type": "mrkdwn", "text": f"<@{uid}>"}
        }
        opt = {"text": {"type": "plain_text", "text": "Sign off"}, "value": f"confirmed-{uid}"}
        if uid in STATE["confirmed"]:
            t = STATE["locked_at"][uid]
            ctx_text = _note_line(uid) + f"\n:lock: *Locked* {t}"
            context = {
                "type": "context",
                "block_id": f"ctx-{uid}",
                "elements": [{"type": "mrkdwn", "text": ctx_text}]
            }
            blocks.extend([section, context])
        else:
            actions = {
                "type": "actions",
                "block_id": f"actions-{uid}",
                "elements": [{
                    "type": "checkboxes",
                    "action_id": f"confirm-{uid}",
                    "options": [opt]
                }]
            }
            context = {
                "type": "context",
                "block_id": f"ctx-{uid}",
                "elements": [{"type": "mrkdwn", "text": _note_line(uid)}]
            }
            blocks.extend([section, actions, context])
    return blocks

@app.action(re.compile(r"^confirm-(.+)$"))
def handle_confirm(ack, body, action, client, logger):
    ack()
    uid = action["action_id"].split("confirm-")[1]
    actor = body["user"]["id"]
    ch = body["container"]["channel_id"]
    root = STATE.get("root") or {}
    root_ts = root.get("ts")
    if not root_ts:
        return
    checked = any(o.get("value") == f"confirmed-{uid}" for o in action.get("selected_options", []))
    if not checked:
        STATE["confirmed"].discard(uid)
        STATE["signer"].pop(uid, None)
    elif _has_note(uid):
        STATE["confirmed"].add(uid)
        STATE["signer"][uid] = actor
        STATE["locked_at"][uid] = STATE["locked_at"].get(uid) or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    else:
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "submit-note",
                "private_metadata": json.dumps({"uid": uid, "channel": ch, "ts": root_ts, "actor": actor}),
                "title": {"type": "plain_text", "text": "Add note"},
                "submit": {"type": "plain_text", "text": "Save"},
                "notify_on_close": True,
                "blocks": [{
                    "type": "input", "block_id": "note",
                    "element": {"type": "plain_text_input", "action_id": "note_text", "multiline": True,
                                "initial_value": STATE["notes"].get(uid, "")},
                    "label": {"type": "plain_text", "text": "Your note"}
                }]
            }
        )
        return
    env_label = STATE.get("env_label")
    version   = STATE.get("version")
    what_time = STATE.get("what_time")
    blocks = _build_all_blocks(env_label, version, what_time)
    _safe_chat_update(client, channel=ch, ts=root_ts, blocks=blocks)

@app.view_closed("submit-note")
def on_note_modal_closed(ack, body, client, logger):
    ack()
    meta = json.loads(body.get("view", {}).get("private_metadata", "{}") or "{}")
    uid, ch, root_ts = meta.get("uid"), meta.get("channel"), meta.get("ts")
    if not (uid and ch and root_ts):
        logger.info("Missing metadata on close; nothing to revert.")
        return
    STATE["confirmed"].discard(uid)
    STATE["signer"].pop(uid, None)
    if STATE["notes"].get(uid) in ("", "_Awaiting note…_", "_No note_", None):
        STATE["notes"].pop(uid, None)
    env_label = STATE.get("env_label")
    version   = STATE.get("version")
    what_time = STATE.get("what_time")
    blocks = _build_all_blocks(env_label, version, what_time)
    _safe_chat_update(client, channel=ch, ts=root_ts, blocks=blocks)

@app.view("submit-note")
def handle_note_submit(ack, body, view, client):
    meta = json.loads(view.get("private_metadata","{}"))
    uid = meta.get("uid")
    ch = meta.get("channel")
    root_ts = meta.get("ts")
    actor = meta.get("actor")
    raw = view["state"]["values"]["note"]["note_text"]["value"]
    note = (raw or "").strip()
    if not note:
        return ack(response_action="errors", errors={"note": "Please add a note to sign off."})
    ack()
    STATE["notes"][uid] = note
    STATE["confirmed"].add(uid)
    STATE["signer"][uid] = actor
    STATE["locked_at"][uid] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if actor:
        STATE["signer"][uid] = actor
    env_label = STATE.get("env_label")
    version   = STATE.get("version")
    what_time = STATE.get("what_time")
    blocks = _build_all_blocks(env_label, version, what_time)
    _safe_chat_update(client, channel=ch, ts=root_ts, blocks=blocks, text=f"{env_label} build reminder")
# Sign off flow - END
#----------------------------------

def post_team_kpi_threaded():
    entries = get_team_kpi()
    rows = _sanitize_blocks_for_slack(render_team_kpi_blocks(entries))
    root_ts = find_today_root_ts(app.client, DREAM_TEAM_DR_CHANNEL, "Team KPI Snapshot @")
    if not root_ts:
        root_ts = create_today_root(app.client, DREAM_TEAM_DR_CHANNEL, "Team KPI Snapshot @")
    if _thread_has_replies(app.client, DREAM_TEAM_DR_CHANNEL, root_ts):
        rows = _snapshot_banner_blocks() + rows
    app.client.chat_postMessage(
        channel=DREAM_TEAM_DR_CHANNEL,
        thread_ts=root_ts,
        text="Team KPI",
        blocks=rows
    )

def crenium():
    _cron_job_for_game_kpi()
    record_team_kpi(record_login_func=get_team_kpi, interval_hours=4)
    trigger_slack_team_kpi(
        lambda: post_team_kpi_from_cache(DREAM_TEAM_DR_CHANNEL, MARKER, app.client),
        job_args=[],
        channel_id=DREAM_TEAM_DR_CHANNEL,
        web_client=app.client,
        trigger_hours=(18,),
        lookback_hours=25,
    )
    handler = SocketModeHandler(app, SLACK_SOCKET_TOKEN)
    orig_signal = signal.signal
    signal.signal = lambda *args, **kwargs: None
    try:
        handler.start()
    finally:
        signal.signal = orig_signal

if __name__ == "__main__":
    crenium()
