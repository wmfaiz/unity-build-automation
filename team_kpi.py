import json
import os
import requests
from pathlib import Path
from datetime import datetime, timedelta
from datetime import datetime as _dt, timedelta as _td
from zoneinfo import ZoneInfo

BASE = ""
SECRET = ""
LOCAL_TZ = ZoneInfo("Asia/Kuala_Lumpur")
TRACKER_PATH = str((Path(__file__).parent / "performance_tracker.json").resolve())

def get_player_last_login(playfab_id):
    url = f"{BASE}/Server/GetPlayerProfile"
    headers = {"X-SecretKey": SECRET, "Content-Type": "application/json"}
    body = {"PlayFabId": playfab_id, "ProfileConstraints": {"ShowLastLogin": True}}
    r = requests.post(url, headers=headers, json=body, timeout=120)
    r.raise_for_status()
    data = r.json().get("data", {})
    return (data.get("PlayerProfile") or {}).get("LastLogin")

def _bucket_labels(interval_hours=4):
    return [f"{h:02d}-{min(h+interval_hours,24):02d}" for h in range(0, 24, interval_hours)]

def _empty_status_map(interval_hours=4):
    return {label: "NOT ACTIVE" for label in _bucket_labels(interval_hours)}

def _load_tracker(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

def _save_tracker(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

def _today_key(tz: ZoneInfo):
    return datetime.now(tz).strftime("%Y-%m-%d")

def _bucket_for_last_login(last_login_iso: str, tz: ZoneInfo, interval_hours=4):
    try:
        t_loc = _dt.fromisoformat(last_login_iso.replace("Z", "+00:00")).astimezone(tz)
    except Exception:
        return None
    today0 = _dt.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    if not (today0 <= t_loc < today0 + _td(days=1)):
        return None 
    start_h = (t_loc.hour // interval_hours) * interval_hours
    end_h = min(start_h + interval_hours, 24)
    return f"{start_h:02d}-{end_h:02d}"

def update_performance_tracker(playfab_id, last_login_iso: str | None, *, path=TRACKER_PATH, tz: ZoneInfo = LOCAL_TZ, interval_hours=4) -> dict:
    data = _load_tracker(path)
    today = _today_key(tz)
    changed = False
    if data.get("__date") != today:
        fresh = {"__date": today}
        for k, v in data.items():
            if k == "__date":
                continue
            fresh[k] = _empty_status_map(interval_hours)
        data = fresh
        changed = True
    if playfab_id not in data or not isinstance(data.get(playfab_id), dict):
        data[playfab_id] = _empty_status_map(interval_hours)
        changed = True
    if last_login_iso:
        b = _bucket_for_last_login(last_login_iso, tz, interval_hours)
        if b:
            if data[playfab_id].get(b) != "ACTIVE":
                data[playfab_id][b] = "ACTIVE"
                changed = True
        else:
            data[playfab_id] = _empty_status_map(interval_hours)
            changed = True
    if changed:
        _save_tracker(path, data)
    return data[playfab_id]

def login_buckets_today(playfab_id, tz: ZoneInfo = LOCAL_TZ, interval_hours=4):
    last = get_player_last_login(playfab_id)
    today0 = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    labels = []
    buckets = []
    for start_h in range(0, 24, interval_hours):
        end_h = min(start_h + interval_hours, 24)
        start = today0.replace(hour=start_h)
        end = today0 + timedelta(days=1) if end_h == 24 else today0.replace(hour=end_h)
        label = f"{start_h:02d}-{end_h:02d}"
        labels.append(label)
        buckets.append((start, end))
    result = {label: False for label in labels}
    if not last:
        return result, None
    try:
        t_utc = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except Exception:
        return result, last
    t_loc = t_utc.astimezone(tz)
    if not (today0 <= t_loc < today0 + timedelta(days=1)):
        return result, last
    for label, (start, end) in zip(labels, buckets):
        if start <= t_loc < end:
            result[label] = True
            break
    return result, last

def get_team_kpi():
    infos = [{"上永吉 岳宏": ["23269383365E287C", "U044QQ0D68M"]},
             {"Hafiz Muhammad": ["E6883B930C85282", "U05B4212NHW"]},
             {"Firdaus Muhammad": ["9AB21795C142B866", "U071QDZTD6C"]},
             {"Adrian Ng": ["E604A5015E3E2C74", "U01EZ46BF7W"]},
             {"Shahrul Ahmad": ["FFB4DABA2226E626", "U03HRP4VA2W"]},
             {"Shahrul Ahmad": ["ECCF5B70417A555A", "U03HRP4VA2W"]},
             {"Wan Faiz": ["D462D2466B036451", "U08NUEV5NAG"]},
             {"Tivos Chan": ["DE5E7B9BE4EEDBF6", "UJVGYJSSF"]},
             {"Imran Arif": ["BE5E62B0D8BD00F0", "U080E6RBK2N"]},
             {"Nur Liyana": ["F3A85F662D8BDBE6", "U08MSH6S6S2"]},
             {"Amin Faris": ["C631A022316CD0DE", "UHJ8U4Y22"]},
             {"Tariq Sharif": ["EA2022C144C3713A", "U03QV7379CL"]},
             {"Aqilah Fatin": ["D344C0264CD0155B", "U07TH9APDMM"]},
             {"Alwi Mohammad": ["A33568F2E60EF968", "U071D1ZCAF9"]},
             {"Naim Mohd": ["B6D40A750FF850D5", "UK707R508"]},
             {"Qushairi Amir": ["900B21396B9E7B4C", "UKC6RHSER"]},
             {"Thang Eden": ["MIA", "UK0Q63CPL"]},
             {"Wen Hui Chang": ["MIA", "U027ZDM8Q1Z"]},
             {"Ng Ming Hau": ["MIA", "U04U9221YUX"]}]
    output_list = []
    for info in infos:
        for human_name, pair in info.items():
            pfid, slack_id = pair[0], pair[1]
            if pfid == "MIA":
                output_list.append({
                    "name": f"<@{slack_id}>",
                    "slack_id": slack_id,
                    "pfid": "MIA",
                    "last_login": "MIA",
                    "yes_pct": 0.0,
                    "no_pct": 100.0,
                    "buckets": {}
                })
                continue
            results, last = login_buckets_today(pfid, tz=LOCAL_TZ)
            persisted_map = update_performance_tracker(pfid, last, path=TRACKER_PATH, tz=LOCAL_TZ, interval_hours=4)
            try:
                if last:
                    dt_local = datetime.fromisoformat(last.replace("Z", "+00:00")).astimezone(LOCAL_TZ)
                    offset_short = dt_local.strftime("%z")[:3]
                    last_local = f"{dt_local.strftime('%Y-%m-%d %H:%M:%S')} {offset_short}"
                else:
                    last_local = "N/A"
            except Exception:
                last_local = last or "N/A"
            total = len(persisted_map)
            yes_count = sum(1 for v in persisted_map.values() if v == "ACTIVE")
            yes_pct = round((yes_count / total) * 100, 2) if total else 0.0
            no_pct  = round(100 - yes_pct, 2) if total else 0.0
            bucket_dict = {label: ("ACTIVE" if v == "ACTIVE" else "NOT ACTIVE") for label, v in persisted_map.items()}
            output_list.append({
                "name": f"<@{slack_id}>",
                "slack_id": slack_id,
                "pfid": pfid,
                "last_login": last_local,
                "yes_pct": yes_pct,
                "no_pct": no_pct,
                "buckets": bucket_dict
            })
    return output_list

def render_team_kpi(json_or_list):
    entries = json.loads(json_or_list) if isinstance(json_or_list, str) else json_or_list
    lines = []
    for e in entries:
        lines.append(e["name"])
        lines.append(f"Last Login: {e['last_login']}")
        lines.append(f"ACTIVENESS ({e['yes_pct']}%)")
        for label, status in e["buckets"].items():
            lines.append(f"{label}: {status}")
        lines.append("")
    return "\n".join(lines)

# if __name__ == "__main__":
#     data = get_team_kpi()
#     print(render_team_kpi(data))