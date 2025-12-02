import glob
import json
import os
import random
import re
import shutil
import textwrap
import time
import zipfile
from functools import lru_cache
from urllib.parse import urlencode
from googleapiclient.discovery import build
from google.oauth2 import service_account
import certifi
import jwt, datetime as dt, requests, gzip, io, csv, subprocess
import requests
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Tuple, Iterable, List
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from dateutil.tz import UTC
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession, Request
from pymongo import MongoClient
from requests.adapters import HTTPAdapter
from requests.exceptions import SSLError, Timeout, ConnectionError as ReqConnErr
from urllib3 import Retry

script_dir = os.path.dirname(os.path.abspath(__file__))

ADIMPRESSION = ""
CASHPURCHASE = ""
INGAMEPURCHASE = ""
LOGIN = ""
API_TOKEN = ""
APP_TOKEN = ""
UNITY_ADS_API_KEY = ""
UNITY_ADS_ORG_ID = ""
APPLE_ADS_ID = ""
ANDROID_ADS_ID = ""
BUCKET = ""
ASC_ISSUER_ID = ""
ASC_KEY_ID = ""
ASC_VENDOR = ""
PLAYFAB_ENDPOINT = ""
PLAYFAB_SECRET = ""

MONGO_URI = "mongodb://192.168.130.101:27017"
DB_NAME = f"PRD_telemetry_db"

ADJUST_SESSION = requests.Session()
_adjust_retries = Retry(
    total=8,
    connect=5,
    read=5,
    backoff_factor=0.7,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
)
ADJUST_SESSION.mount("https://", HTTPAdapter(max_retries=_adjust_retries))
ADJUST_SESSION.mount("http://", HTTPAdapter(max_retries=_adjust_retries))

SPREADSHEET_ID = "1KPZbG6IWXTsg1ku3g234Sg619qxcgQ7mB6bz4_nSS24"
SHEETS_JSON = os.path.join(script_dir, "cryptic", "dreamteam-ch-dev-excel-access-d8b9aebb3269.json")

headers = {
    'Authorization': f'Bearer {API_TOKEN}',
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def safe_div(num, denom):
    try:
        return round(num / denom, 2)
    except (ZeroDivisionError, TypeError):
        return 0.0

def percent(val):
    return f"{round(val * 100, 2)}%" if val is not None else "N/A"

def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0

def fetch_retention_rates():
    base = (datetime.now(ZoneInfo("UTC")) - timedelta(days=1))
    start_date = (base - timedelta(days=60)).strftime("%Y-%m-%d")
    yesterday  = base.strftime("%Y-%m-%d")
    if yesterday < start_date:
        yesterday = start_date
    url = (
        f"https://automate.adjust.com/reports-service/report?"
        f"app_token__in={APP_TOKEN}"
        f"&dimensions=day"
        f"&metrics=installs,revenue,"
        f"retention_rate_d1,retention_rate_d3,retention_rate_d7,"
        f"retention_rate_d14,retention_rate_d30"
        f"&date_period={start_date}:{yesterday}"
        f"&cohort_maturity=immature"
        f"&attribution_source=first"
        f"&attribution_type=all"
        f"&country__in=all"
        f"&tracker__in=all"
        f"&full_data=true"
        f"&readable_names=false"
        f"&format_dates=false"
        f"&sandbox=false"
    )
    response = ADJUST_SESSION.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    rows = response.json().get("rows", [])
    parsed = []
    total_installs = 0
    yesterday_installs = 0
    for row in rows:
        date = row.get("day", "")
        installs = int(row.get("installs", 0))
        total_installs += installs
        if date == yesterday:
            yesterday_installs = installs
        parsed.append({
            "date": date,
            "installs": installs,
            "revenue": safe_float(row.get("revenue")),
            "retention_rate_d1": safe_float(row.get("retention_rate_d1")),
            "retention_rate_d3": safe_float(row.get("retention_rate_d3")),
            "retention_rate_d7": safe_float(row.get("retention_rate_d7")),
            "retention_rate_d14": safe_float(row.get("retention_rate_d14")),
            "retention_rate_d30": safe_float(row.get("retention_rate_d30")),
        })
    return parsed, total_installs, yesterday_installs

def latest_retention(rows, field, *, min_days_old=0, ref_day=None):
    if ref_day:
        base = datetime.fromisoformat(ref_day).date()
    else:
        dates = [datetime.strptime(r["date"], "%Y-%m-%d").date() for r in rows if r.get("date")]
        base = max(dates) if dates else None
    if base is None:
        return 0.0
    candidates = []
    for r in rows:
        if not r.get("date"):
            continue
        d = datetime.strptime(r["date"], "%Y-%m-%d").date()
        if (base - d).days >= min_days_old:
            v = r.get(field)
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = None
            if v is not None and v > 0:
                candidates.append((d, v))
    if not candidates:
        return 0.0
    newest_date, value = max(candidates, key=lambda t: t[0])
    return round(value * 100.0, 2)

def fetch_daus(target_date=None):
    ref_day = _as_utc_date(target_date)
    start_date, end_date = _month_to_yesterday_for(ref_day)
    url = (
        f"https://automate.adjust.com/reports-service/report?"
        f"app_token__in={APP_TOKEN}"
        f"&dimensions=day"
        f"&metrics=daus"
        f"&date_period={start_date:%Y-%m-%d}:{end_date:%Y-%m-%d}"
    )
    response = ADJUST_SESSION.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    rows = response.json().get("rows", [])
    parsed = [{"date": r.get("day"), "dau": round(float(r.get("daus", 0)))} for r in rows]
    total = sum(row["dau"] for row in parsed)
    average_dau = round(total / len(parsed), 4) if parsed else 0.0
    daily_dau = next((row["dau"] for row in parsed if row["date"] == f"{end_date:%Y-%m-%d}"), 0)
    return parsed, average_dau, daily_dau

def fetch_mau():
    today = datetime.now(ZoneInfo("UTC"))
    start_date = today.replace(day=1).strftime("%Y-%m-%d")
    end_of_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    end_date = end_of_month.strftime("%Y-%m-%d")
    url = (
        "https://automate.adjust.com/reports-service/report?"
        f"app_token__in={APP_TOKEN}"
        f"&metrics=daus"
        f"&dimensions=day"
        f"&date_period={start_date}:{end_date}"
        f"&attribution_source=first"
        f"&attribution_type=all"
        f"&country__in=all"
        f"&tracker__in=all"
        f"&readable_names=false"
        f"&format_dates=false"
        f"&sandbox=false"
    )
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    rows = response.json().get("rows", [])
    daily_daus = []
    unique_total = 0.0
    for row in rows:
        dau = float(row.get("daus", 0))
        daily_daus.append({
            "date": row.get("day"),
            "dau": round(dau)
        })
        unique_total += dau
    return daily_daus, round(unique_total)

def fetch_month_mau(target_date=None):
    ref_day = _as_utc_date(target_date)
    start_date, end_date = _month_to_yesterday_for(ref_day)
    url = (
        f"https://automate.adjust.com/reports-service/report?"
        f"app_token__in={APP_TOKEN}"
        f"&metrics=maus"
        f"&dimensions=month"
        f"&date_period={start_date:%Y-%m-%d}:{end_date:%Y-%m-%d}"
        f"&attribution_source=first"
        f"&attribution_type=all"
        f"&country__in=all"
        f"&tracker__in=all"
        f"&timezone=UTC"
        f"&readable_names=false"
        f"&format_dates=false"
        f"&full_data=true"
        f"&cohort_maturity=immature"
        f"&sandbox=false"
    )
    response = ADJUST_SESSION.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    rows = response.json().get("rows", [])
    if not rows:
        return "0"
    row = next((r for r in rows if r.get("month") == f"{start_date:%Y-%m}"), rows[-1])
    maus = int(float(row.get("maus", 0)))
    return f"{maus:,}"

def fetch_event_users(target_date=None):
    ref_day = _as_utc_date(target_date)
    start_date, end_date = _month_to_yesterday_for(ref_day)
    url = (
        f"https://automate.adjust.com/reports-service/events?"
        f"app_token__in={APP_TOKEN}"
        f"&event_token__in={CASHPURCHASE},{INGAMEPURCHASE},{ADIMPRESSION},{LOGIN}"
        f"&kpi=event_users"
        f"&grouping=date,event_token"
        f"&start_date={start_date:%Y-%m-%d}"
        f"&end_date={end_date:%Y-%m-%d}"
    )
    response = ADJUST_SESSION.get(url, headers=headers, timeout=20)
    if response.status_code != 200:
        return 0.0
    try:
        rows = response.json()
        if not isinstance(rows, list):
            return 0.0
        event_counts = {CASHPURCHASE: 0.0, INGAMEPURCHASE: 0.0, ADIMPRESSION: 0.0}
        for row in rows:
            token = row.get("event_token")
            count = float(row.get("event_users", 0))
            if token in event_counts:
                event_counts[token] += count
        return event_counts[CASHPURCHASE]
    except Exception as e:
        print("JSON parsing error:", e)
        return 0.0

def as_int(x):
    if isinstance(x, str):
        x = x.replace(",", "")
    try:
        return int(round(float(x)))
    except Exception:
        return 0

def _fmt_ret(x): return f"{x:.2f}%" if x is not None else "N/A"

def compute_average_retention(rows):
    if not rows:
        return {}
    keys = [
        "retention_rate_d1",
        "retention_rate_d3",
        "retention_rate_d7",
        "retention_rate_d14",
        "retention_rate_d30",
    ]
    sums = {k: 0.0 for k in keys}
    counts = {k: 0 for k in keys}
    for row in rows:
        for k in keys:
            val = row.get(k)
            if isinstance(val, (int, float)) and val > 0:
                sums[k] += val
                counts[k] += 1
    averages = {}
    for k in keys:
        if counts[k] > 0:
            averages[k] = round((sums[k] / counts[k]) * 100, 2)
        else:
            averages[k] = 0.0
    return averages

def format_kpi_report(data, adjust_daily_dau, 
                      retention_rows, total_month_revenue, 
                      total_daily_revenue, ads_revenue_month,
                      ads_revenue_yesterday, adjust_yesterday_installs, adjust_month_mau, adjust=False, raw_data=False,
                      target_date: str | None = None):
    if target_date:
        (playfab_retention_rows, playfab_total_installs,
         playfab_yesterday_installs, playfab_dau, playfab_mau,
         playfab_y_installs, playfab_mtd_installs) = pf_fetch_retention_rates_ref_day(ref_day=target_date)
    else:      
        (playfab_retention_rows, playfab_total_installs,
        playfab_yesterday_installs, playfab_dau, playfab_mau,
        playfab_y_installs, playfab_mtd_installs) = pf_fetch_retention_rates(ref_day=target_date)

    totals = data.get("totals", {})
    rows = data.get("rows", [])

    adjust_revenue = int(totals.get("revenue", sum(r["revenue"] for r in rows)))
    adjust_installs_total = int(totals.get("installs", sum(r["installs"] for r in rows)))

    if target_date:
        ref_day = datetime.fromisoformat(target_date).date()
    else:
        ref_day = (datetime.now(ZoneInfo("UTC"))).date()

    date_end = ref_day.strftime("%Y-%m-%d")
    daily_row = next((row for row in rows if row.get("date") == date_end), {})

    if total_month_revenue:
        adjust_arppu_total = safe_div(adjust_revenue, adjust_month_mau)
        playfab_arppu_total = safe_div(total_month_revenue, playfab_mau)
    else:
        adjust_arppu_total = 0
        playfab_arppu_total = 0

    if total_daily_revenue:
        adjust_daily_arppu_total = safe_div(adjust_revenue, adjust_daily_dau)
        playfab_daily_arppu_total = safe_div(total_daily_revenue, playfab_dau)
    else:
        adjust_daily_arppu_total = 0
        playfab_daily_arppu_total = 0
    
    day1_playfab  = exact_retention_for_day_playfab(playfab_retention_rows,  1, ref_day)
    day3_playfab  = exact_retention_for_day_playfab(playfab_retention_rows,  3, ref_day)
    day7_playfab  = exact_retention_for_day_playfab(playfab_retention_rows,  7, ref_day)
    day14_playfab = exact_retention_for_day_playfab(playfab_retention_rows, 14, ref_day)
    day30_playfab = exact_retention_for_day_playfab(playfab_retention_rows, 30, ref_day)

    avg_ret = compute_average_retention(rows)
    day1_avg_playfab = avg_ret.get("retention_rate_d1")
    day3_avg_playfab = avg_ret.get("retention_rate_d3")
    day7_avg_playfab = avg_ret.get("retention_rate_d7")
    day14_avg_playfab = avg_ret.get("retention_rate_d14")
    day30_avg_playfab = avg_ret.get("retention_rate_d30")

    adj_ref = _as_utc_date(ref_day) + timedelta(days=1)
    day1_ret  = exact_retention_for_day_adjust_manual(retention_rows,  1, adj_ref)
    day3_ret  = exact_retention_for_day_adjust_manual(retention_rows,  3, adj_ref)
    day7_ret  = exact_retention_for_day_adjust_manual(retention_rows,  7, adj_ref)
    day14_ret = exact_retention_for_day_adjust_manual(retention_rows, 14, adj_ref)
    day30_ret = exact_retention_for_day_adjust_manual(retention_rows, 30, adj_ref)

    date_str = ref_day.strftime("%B %d (%a)")
    month_str = ref_day.strftime("%B")

    playfab_retentions = [day1_playfab, day3_playfab, day7_playfab, day14_playfab, day30_playfab]
    adjust_retentions  = [day1_ret, day3_ret, day7_ret, day14_ret, day30_ret]

    iap_month = float(total_month_revenue or 0.0)
    iap_day   = float(total_daily_revenue or 0.0)
    print("IAP Month:", iap_month)
    print("IAP Day:", iap_day)
    if iap_month:
        adjust_arppu_total = safe_div(
            max(0.0, float(adjust_revenue or 0) - float(ads_revenue_month or 0)),
            adjust_month_mau
        )
        playfab_arppu_total = safe_div(iap_month, playfab_mau)
    else:
        adjust_arppu_total = 0
        playfab_arppu_total = 0
    if iap_day:
        adjust_daily_arppu_total = safe_div(
            max(0.0, float(daily_row.get("revenue", 0)) - float(ads_revenue_yesterday or 0)),
            adjust_daily_dau
        )
        playfab_daily_arppu_total = safe_div(iap_day, playfab_dau)
    else:
        adjust_daily_arppu_total = 0
        playfab_daily_arppu_total = 0
    est_payrate_month_adjust = estimate_paying_rate_with_arppu_list(
        dau=float(str(adjust_month_mau).replace(",", "") or 0),
        new_downloads=float(adjust_installs_total or 0),
        retentions=adjust_retentions,
        iap_revenue=max(0.0, float(adjust_revenue or 0) - float(ads_revenue_month or 0)),
        arppu=adjust_arppu_total
    )
    est_payrate_day_adjust = estimate_paying_rate_with_arppu_list(
        dau=float(str(adjust_daily_dau).replace(",", "") or 0),
        new_downloads=float(adjust_yesterday_installs or 0),
        retentions=adjust_retentions,
        iap_revenue=max(0.0, float(daily_row.get("revenue", 0)) - float(ads_revenue_yesterday or 0)),
        arppu=adjust_daily_arppu_total
    )
    paying_user_month, paying_user_yesterday = paying_user()
    pf_mau = as_int(playfab_mau)
    daily_revenu = int(total_daily_revenue)
    ads_d_revenu = int(ads_revenue_yesterday)
    useThis_dau = as_int(playfab_dau)
    real_payrate_month_playfab = round((paying_user_month / pf_mau) * 100.0, 2)
    real_arppu_month_playfab = safe_div(iap_month, paying_user_month) if iap_month else 0.0
    real_payrate_day_playfab = (paying_user_yesterday / useThis_dau) * 100.0
    real_arppu_day_playfab = safe_div(iap_day, paying_user_yesterday) if iap_day else 0.0
    if raw_data:
        return (total_month_revenue, ads_revenue_month, pf_mau, playfab_mtd_installs, 
                playfab_arppu_total, real_payrate_month_playfab, daily_revenu, ads_d_revenu, useThis_dau, 
                playfab_y_installs, playfab_daily_arppu_total, real_payrate_day_playfab,
                day1_playfab, day3_playfab, day7_playfab, day14_playfab, day30_playfab)
    if adjust:
        msg = textwrap.dedent(f"""\
            [production] {date_str} Aggregated Data
    
            ▼ Monthly Aggregation (up to previous day)
            ────────────────────────────
            {month_str} {"Revenue": <13}: ¥{int(total_month_revenue):,}
            {month_str} {"Ads Revenue": <13}: ¥{int(ads_revenue_month):,}
            {month_str} {"MAU": <13}: {as_int(playfab_mau):,.2f} ({as_int(adjust_month_mau):,.2f})
            {month_str} {"New Downloads": <13}: {playfab_mtd_installs:,} ({adjust_installs_total:,})
            {month_str} {"Paying Users": <13}: {paying_user_month:,}
            {month_str} {"ARPPU": <13}: ¥{real_arppu_month_playfab:,.2f} (¥{adjust_arppu_total:,.2f} est)
            {month_str} {"Paying Rate": <13}: {real_payrate_month_playfab:.2f}% ({est_payrate_month_adjust:.2f}% est)
            ────────────────────────────
    
            ▼ Daily Aggregation (for previous day only)
            ────────────────────────────
            {"Revenue": <13}: ¥{int(total_daily_revenue):,}
            {"Ads Revenue": <13}: ¥{int(ads_revenue_yesterday):,}
            {"DAU": <13}: {as_int(playfab_dau):,.2f} ({as_int(adjust_daily_dau):,.2f})
            {"New Downloads": <13}: {playfab_y_installs:,} ({adjust_yesterday_installs:,})
            {"Paying Users": <13}: {paying_user_yesterday:,}
            {"ARPPU": <13}: ¥{real_arppu_day_playfab:,.2f} (¥{adjust_daily_arppu_total:,.2f} est)
            {"Paying Rate": <13}: {real_payrate_day_playfab:.2f}% ({est_payrate_day_adjust:.2f}% est)
            ────────────────────────────
    
            ▼ Retention Rate
            ────────────────────────────
            {"Day":<5} | {"Daily":>6}  | {"Average":>7}
            ────────────────────────────
            {"1":<5} | {day1_playfab:>6}% | {day1_avg_playfab:>7}%
            {"3":<5} | {day3_playfab:>6}% | {day3_avg_playfab:>7}%
            {"7":<5} | {day7_playfab:>6}% | {day7_avg_playfab:>7}%
            {"14":<5} | {day14_playfab:>6}% | {day14_avg_playfab:>7}%
            {"30":<5} | {day30_playfab:>6}% | {day30_avg_playfab:>7}%
            ────────────────────────────
        """)
    else:
        msg = textwrap.dedent(f"""\
            [production] {date_str} Aggregated Data
            
            ▼ Monthly Aggregation (up to previous day)
            ────────────────────────────
            {month_str} {"Revenue": <13}: ¥{int(total_month_revenue):,}
            {month_str} {"Ads Revenue": <13}: ¥{int(ads_revenue_month):,}
            {month_str} {"MAU": <13}: {as_int(playfab_mau):,.2f}
            {month_str} {"New Downloads": <13}: {playfab_mtd_installs:,}
            {month_str} {"Paying Users": <13}: {paying_user_month:,}
            {month_str} {"ARPPU": <13}: ¥{real_arppu_month_playfab:,.2f}
            {month_str} {"Paying Rate": <13}: {real_payrate_month_playfab:.2f}%
            ────────────────────────────
    
            ▼ Daily Aggregation (for previous day only)
            ────────────────────────────
            {"Revenue": <13}: ¥{int(total_daily_revenue):,}
            {"Ads Revenue": <13}: ¥{int(ads_revenue_yesterday):,}
            {"DAU": <13}: {as_int(playfab_dau):,.2f}
            {"New Downloads": <13}: {playfab_y_installs:,}
            {"Paying Users": <13}: {paying_user_yesterday:,}
            {"ARPPU": <13}: ¥{real_arppu_day_playfab:,.2f}
            {"Paying Rate": <13}: {real_payrate_day_playfab:.2f}%
            ────────────────────────────
    
            ▼ Retention Rate
            ────────────────────────────
            {"Day":<5} | {"Daily":>6}  | {"Average":>7}
            ────────────────────────────
            {"1":<5} | {day1_playfab:>6}% | {day1_avg_playfab:>7}%
            {"3":<5} | {day3_playfab:>6}% | {day3_avg_playfab:>7}%
            {"7":<5} | {day7_playfab:>6}% | {day7_avg_playfab:>7}%
            {"14":<5} | {day14_playfab:>6}% | {day14_avg_playfab:>7}%
            {"30":<5} | {day30_playfab:>6}% | {day30_avg_playfab:>7}%
            ────────────────────────────
        """)

    print(msg)
    return msg

# ----- Generals -----

_FX_SESSION = requests.Session()
_FX_SESSION.headers.update({"Accept": "application/json",
                            "User-Agent": "kpi-bot/1.0 (+okakichi)"})
_FX_SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
    total=6, connect=4, read=4, backoff_factor=0.7,
    status_forcelist=[408, 429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False
)))

def _fx_cache_path():
    p = os.path.join(script_dir, ".fx_cache.json")
    if os.access(os.path.dirname(p), os.W_OK):
        return p
    return "/tmp/.fx_cache.json"

def _fx_cache_load():
    try:
        with open(_fx_cache_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _fx_cache_save(ccy_pair: str, date_iso: str, rate: "Decimal|float|str"):
    try:
        data = _fx_cache_load()
        data.setdefault(ccy_pair, {})[date_iso] = str(rate)
        with open(_fx_cache_path(), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

def _fx_cached_get(ccy_pair: str, date_iso: str) -> "Decimal|None":
    data = _fx_cache_load()
    try:
        val = data.get(ccy_pair, {}).get(date_iso)
        return _q(val) if val is not None else None
    except Exception:
        return None

def _banking_days_back(start_date: datetime.date, max_days=5):
    cur = start_date
    yielded = 0
    while yielded < max_days:
        if cur.weekday() < 5:
            yield cur
            yielded += 1
        cur = cur - timedelta(days=1)

def _get_json_with_retries(url, timeout=15):
    timeouts = (timeout, timeout)
    r = _FX_SESSION.get(url, timeout=timeouts)
    r.raise_for_status()
    return r.json()

def _to_cents(d) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _get_usd_to_jpy(date_iso: str | None = None) -> Decimal:
    def providers(d: str | None):
        if d:
            return [
                (f"https://api.frankfurter.app/{d}?from=USD&to=JPY", lambda j: j["rates"]["JPY"]),
                (f"https://api.exchangerate.host/{d}?base=USD&symbols=JPY", lambda j: j["rates"]["JPY"]),
                (f"https://open.er-api.com/v6/latest/USD", lambda j: j["rates"]["JPY"]),
            ]
        else:
            return [
                ("https://api.frankfurter.app/latest?from=USD&to=JPY", lambda j: j["rates"]["JPY"]),
                ("https://api.exchangerate.host/latest?base=USD&symbols=JPY", lambda j: j["rates"]["JPY"]),
                ("https://open.er-api.com/v6/latest/USD", lambda j: j["rates"]["JPY"]),
            ]

    errs = []
    if date_iso:
        cached = _fx_cached_get("USDJPY", date_iso)
        if cached and cached > 0:
            return cached
    base_date = (datetime.now(ZoneInfo("UTC"))).date() if not date_iso else datetime.fromisoformat(date_iso).date()
    attempt_dates = [date_iso] if date_iso else [None]
    attempt_dates += [d.isoformat() for d in _banking_days_back(base_date, max_days=5)]
    for di in attempt_dates:
        for url, pick in providers(di):
            try:
                if not date_iso:
                    time.sleep(random.uniform(0, 0.4))
                j = _get_json_with_retries(url, timeout=15)
                rate = _q(pick(j))
                if rate > 0:
                    store_key = (di or base_date.isoformat())
                    _fx_cache_save("USDJPY", store_key, rate)
                    return rate
            except Exception as e:
                body = ""
                try:
                    body = f" | body: {j if isinstance(j, str) else ''}"
                except Exception:
                    pass
                errs.append(f"{url} → {e}{body}")
    cache = _fx_cache_load().get("USDJPY", {})
    if cache:
        try:
            best_date = max(cache.keys())
            return _q(cache[best_date])
        except Exception:
            pass

    raise RuntimeError("USD→JPY fetch failed. " + " ; ".join(errs))

@lru_cache(maxsize=64)
def _fetch_usd_rates_for_date(date=None) -> dict[str, Decimal]:
    date = (date or datetime.now(ZoneInfo("UTC")).date().isoformat())
    cached_all = _fx_cache_load().get(f"USDALL_{date}")
    if isinstance(cached_all, dict) and cached_all:
        return {k: _q(v) for k, v in cached_all.items()}
    providers = [
        (f"https://api.frankfurter.app/{date}?from=USD", lambda j: j["rates"]),
        (f"https://api.exchangerate.host/{date}?base=USD", lambda j: j["rates"]),
        ("https://open.er-api.com/v6/latest/USD", lambda j: j["rates"]),
    ]
    errs = []
    for url, pick in providers:
        try:
            j = _get_json_with_retries(url, timeout=15)
            data = pick(j) or {}
            out = {k.upper(): _q(v) for k, v in data.items() if v}
            if out:
                try:
                    data_cache = _fx_cache_load()
                    data_cache[f"USDALL_{date}"] = {k: str(v) for k, v in out.items()}
                    with open(_fx_cache_path(), "w", encoding="utf-8") as f:
                        json.dump(data_cache, f)
                except Exception:
                    pass
                return out
        except Exception as e:
            snippet = ""
            try:
                snippet = f" | body: {str(j)[:160]}"
            except Exception:
                pass
            errs.append(f"{url} → {e}{snippet}")
    for d in _banking_days_back(datetime.fromisoformat(date), max_days=5):
        try:
            return _fetch_usd_rates_for_date(d.isoformat())
        except Exception:
            continue
    raise RuntimeError("FX fetch failed. " + " ; ".join(errs))

def _to_yen(usd: Decimal, usd_to_jpy: Decimal) -> Decimal:
    return (usd * usd_to_jpy).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _q(x: float | str | Decimal) -> Decimal:
    return Decimal(str(x))

@lru_cache(maxsize=64)
def _fetch_usd_rates_for_date(date=None) -> dict[str, Decimal]:
    providers = [
        (f"https://api.frankfurter.app/{date}?from=USD", lambda j: j["rates"]),
        (f"https://api.exchangerate.host/{date}?base=USD", lambda j: j["rates"]),
        ("https://open.er-api.com/v6/latest/USD", lambda j: j["rates"]),
    ]
    errs = []
    for url, pick in providers:
        try:
            r = requests.get(url, timeout=15, headers={"Accept": "application/json"})
            r.raise_for_status()
            data = pick(r.json())
            out = {k.upper(): _q(v) for k, v in (data or {}).items() if v}
            if out:
                return out
        except Exception as e:
            body = ""
            try: body = f" | body: {r.text[:160]}"
            except: pass
            errs.append(f"{url} → {e}{body}")
    raise RuntimeError("FX fetch failed. " + " ; ".join(errs))

def _jpy_multiplier_for(date, ccy) -> Decimal | None:
    ccy = (ccy or "").upper().strip()
    if not ccy or ccy == "UNKNOWN":
        ccy = "USD"
    if ccy == "JPY":
        return Decimal("1")
    rates = _fetch_usd_rates_for_date(date)
    usd_jpy = rates.get("JPY")
    usd_ccy = rates.get(ccy)
    if not usd_jpy or not usd_ccy or usd_ccy == 0:
        return None
    return usd_jpy / usd_ccy

def _round_jpy(x: Decimal) -> float:
    return float(x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

# ----- Google Play Console Record -----
GCS_API = "https://storage.googleapis.com/storage/v1"
GCS_DOWNLOAD = "https://storage.googleapis.com"
PREFIX = "sales/"

def authed_session() -> AuthorizedSession:
    credential = os.path.join(script_dir, "cryptic", "dreamteam-ch-dev-8ab8ad353128.json")
    SCOPES = [
        "https://www.googleapis.com/auth/devstorage.read_only",
        "https://www.googleapis.com/auth/devstorage.read_write",
        "https://www.googleapis.com/auth/devstorage.full_control",
        "https://www.googleapis.com/auth/androidpublisher"
    ]
    creds = service_account.Credentials.from_service_account_file(credential, scopes=SCOPES)
    creds.refresh(Request())
    assert creds.token, "No OAuth access token; check JSON key & scopes"
    return AuthorizedSession(creds)

def month_to_yesterday() -> Tuple[dt.date, dt.date]:
    today = dt.datetime.now(dt.UTC).date()
    start = today.replace(day=1)
    end = today - dt.timedelta(days=1)
    if end < start: end = start
    return start, end

def daterange(start: dt.date, end: dt.date) -> Iterable[dt.date]:
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)

def list_objects(sess, bucket, prefix) -> List[dict]:
    url = f"{GCS_API}/b/{bucket}/o"
    params, items = {"prefix": prefix}, []
    while True:
        r = sess.get(url, params=params, timeout=60)
        if r.status_code != 200:
            r.raise_for_status()
        data = r.json()
        items += data.get("items", [])
        tok = data.get("nextPageToken")
        if not tok: break
        params["pageToken"] = tok
    return items

def download_bytes(sess, bucket, object_name) -> bytes:
    r = sess.get(f"{GCS_DOWNLOAD}/{bucket}/{object_name}", timeout=120)
    if r.status_code != 200:
        r.raise_for_status()
    return r.content

def save_zip_csv_filtered(zip_bytes, out_csv_path, product_id=None) -> None:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(csv_name, "r") as f_in:
            text = io.TextIOWrapper(f_in, encoding="utf-8", newline="")
            reader = csv.DictReader(text)

            headers = reader.fieldnames or []
            headers_lower = {h.lower(): h for h in headers}

            prod_col = None
            for candidate in ("product id", "productid", "product_id"):
                if candidate in headers_lower:
                    prod_col = headers_lower[candidate]
                    break
            if prod_col is None and product_id:
                print(
                    "[WARN] No Product ID column found in Google sales CSV. "
                    "Falling back to unfiltered export (all rows)."
                )
                product_id = None
            with open(out_csv_path, "w", newline="", encoding="utf-8") as f_out:
                writer = csv.DictWriter(f_out, fieldnames=headers)
                writer.writeheader()

                if not product_id or not prod_col:
                    for row in reader:
                        writer.writerow(row)
                else:
                    for row in reader:
                        if row.get(prod_col) == product_id:
                            writer.writerow(row)

def download_sales_csvs_month_to_yesterday(sess, bucket, out_dir=".", product_id="jp.okakichi.heroes") -> List[str]:
    start, end = month_to_yesterday()
    objs = list_objects(sess, bucket, PREFIX)
    names = {o["name"] for o in objs if o["name"].lower().endswith(".zip")}
    daily = [f"{PREFIX}salesreport_{d.strftime('%Y%m%d')}.zip" for d in daterange(start, end)]
    targets = [n for n in daily if n in names]
    if not targets:
        months = {start.strftime("%Y%m"), end.strftime("%Y%m")}
        targets = [f"{PREFIX}salesreport_{m}.zip" for m in months if f"{PREFIX}salesreport_{m}.zip" in names]
    if not targets:
        raise RuntimeError("No matching sales reports found. Check bucket name, permissions, or whether sales reports are enabled.")
    saved = []
    for obj in targets:
        csv_path = os.path.join(out_dir, os.path.basename(obj).replace(".zip", ".csv"))
        zip_bytes = download_bytes(sess, bucket, obj)
        save_zip_csv_filtered(zip_bytes, csv_path, product_id=product_id)
        saved.append(csv_path)
    return saved

def _detect_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";"]).delimiter
    except Exception:
        return max([",", "\t", ";"], key=sample.count)

def _to_decimal(s: str) -> Decimal:
    if s is None:
        return Decimal("0")
    s = str(s).strip()
    if not s:
        return Decimal("0")
    s = s.replace(",", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")

def download_sales_csvs_month_to_day(sess, bucket, ref_day, out_dir=".", product_id="jp.okakichi.heroes"):
    start, end = _month_to_yesterday_for(ref_day)
    objs = list_objects(sess, bucket, PREFIX)
    names = {o["name"] for o in objs if o["name"].lower().endswith(".zip")}
    daily = [f"{PREFIX}salesreport_{d.strftime('%Y%m%d')}.zip" for d in daterange(start, end)]
    targets = [n for n in daily if n in names]
    if not targets:
        months = {start.strftime("%Y%m"), end.strftime("%Y%m")}
        targets = [f"{PREFIX}salesreport_{m}.zip" for m in months if f"{PREFIX}salesreport_{m}.zip" in names]
    if not targets:
        raise RuntimeError("No matching sales reports found for the requested period.")
    saved = []
    for obj in targets:
        csv_path = os.path.join(out_dir, os.path.basename(obj).replace(".zip", ".csv"))
        zip_bytes = download_bytes(sess, bucket, obj)
        save_zip_csv_filtered(zip_bytes, csv_path, product_id=product_id)
        saved.append(csv_path)
    return saved

def get_google_revenue(directory=".", yesterday_only=False, target_date=None):
    matches = glob.glob(os.path.join(directory, "salesreport*.csv"))
    if not matches:
        raise FileNotFoundError("No salesreport CSV file found.")
    matches = sorted(matches)
    yesterday_str = (datetime.now(ZoneInfo("UTC")) - timedelta(days=1)).strftime("%Y-%m-%d")
    jpy_total = Decimal("0")
    for csv_path in matches:
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(8192)
            delim = _detect_delimiter(sample)
            f.seek(0)
            reader = csv.DictReader(f, delimiter=delim)
            header_map = {h.strip().lower(): h for h in (reader.fieldnames or [])}
            cur_col = header_map.get("currency of sale")
            amt_col = header_map.get("charged amount")
            date_col = (
                    header_map.get("transaction date")
                    or header_map.get("order charged date")
                    or header_map.get("date")
            )
            if not cur_col or not amt_col:
                continue
            for row in reader:
                cur = (row.get(cur_col) or "").strip()
                if cur != "JPY":
                    continue
                row_date = None
                if date_col and row.get(date_col):
                    row_date = row[date_col].strip().split(" ")[0]
                if yesterday_only:
                    if row_date != yesterday_str:
                        continue
                if target_date:
                    if row_date != target_date:
                        continue
                try:
                    amt = Decimal(
                        (row.get(amt_col) or "0").replace(",", "").strip() or "0"
                    )
                except Exception:
                    amt = Decimal("0")
                jpy_total += amt
    return float(_to_cents(jpy_total))

def get_google_revenue_json(target_date=None) -> dict:
    sess = authed_session()
    download_sales_csvs_month_to_yesterday(sess, BUCKET)
    month_jpy = get_google_revenue(yesterday_only=False, target_date=target_date)
    yday_jpy  = get_google_revenue(yesterday_only=True, target_date=target_date)
    for p in glob.glob(os.path.join(".", "salesreport*.csv")):
        try:
            os.remove(p)
        except OSError:
            pass
    return {"month_revenue": float(month_jpy), "yesterday_revenue": float(yday_jpy)}

# ----- Unity Ads -----
def unity_ads_headers(key: str):
    return {
        "Authorization": f"Basic {key}",
        "Accept": "application/json",
    }

def _sum_ads_revenue(org_id, api_key, start_utc, end_utc) -> float:
    params = {"fields": "revenue_sum", "groupBy": "game", "scale": "all",
              "start": start_utc.replace(tzinfo=dt.timezone.utc).isoformat().replace("+00:00", "Z"),
              "end": end_utc.replace(tzinfo=dt.timezone.utc).isoformat().replace("+00:00", "Z"),
              "gameIds": ",".join([APPLE_ADS_ID, ANDROID_ADS_ID])}
    url = f"https://monetization.api.unity.com/stats/v1/operate/organizations/{org_id}"
    r = requests.get(url, params=params, headers=unity_ads_headers(api_key), timeout=60)
    if r.status_code == 401:
        params_fallback = dict(params)
        params_fallback["apikey"] = api_key
        r = requests.get(url, params=params_fallback, headers={"Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    rows = r.json() or []
    return sum(float(row.get("revenue_sum") or 0) for row in rows)

def get_unity_ads_revenue(target_date=None):
    ref = _as_utc_date(target_date)
    mtd_start_utc = dt.datetime(ref.year, ref.month, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
    mtd_end_utc = dt.datetime(ref.year, ref.month, ref.day, 23, 59, 59, tzinfo=dt.timezone.utc)
    y_start_utc = dt.datetime(ref.year, ref.month, ref.day, 0, 0, 0, tzinfo=dt.timezone.utc)
    y_end_utc = dt.datetime(ref.year, ref.month, ref.day, 23, 59, 59, tzinfo=dt.timezone.utc)
    mtd_usd = Decimal(str(_sum_ads_revenue(UNITY_ADS_ORG_ID, UNITY_ADS_API_KEY, mtd_start_utc, mtd_end_utc)))
    y_usd = Decimal(str(_sum_ads_revenue(UNITY_ADS_ORG_ID, UNITY_ADS_API_KEY, y_start_utc,  y_end_utc)))
    usd_to_jpy = _get_usd_to_jpy(ref.isoformat())
    mtd_jpy = _to_yen(mtd_usd, usd_to_jpy)
    y_jpy = _to_yen(y_usd, usd_to_jpy)
    return {
        "month_revenue": float(mtd_jpy),
        "yesterday_revenue": float(y_jpy),
    }

# ----- Apple Revenue -----
ASC_P8_PATH   = os.path.join(script_dir, "cryptic", "AuthKey_S35VA88J4U.p8")
SKUS = {"jp.okakichi.heroes"}
APPLE_IDS = {"6566179200"}
_session = requests.Session()
_retries = Retry(
    total=8,
    connect=5,
    read=5,
    backoff_factor=0.8,
    status_forcelist=[408, 429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    respect_retry_after_header=True,
    raise_on_status=False,
)
_adapter = HTTPAdapter(max_retries=_retries, pool_maxsize=2, pool_block=True)
_session.mount("https://", _adapter)

def _proceeds_decimal(r: dict) -> Decimal:
    raw = (r.get("Developer Proceeds") or "0").replace(",", "")
    try:
        return Decimal(str(raw))
    except Exception:
        return Decimal("0")

def _get_currency(r: dict) -> str:
    for k in ("Proceeds Currency", "Currency of Proceeds", "Currency"):
        v = r.get(k)
        if v:
            return v.strip()
    return "UNKNOWN"

def _is_my_game(r: dict) -> bool:
    app_id = (r.get("Apple Identifier") or "").strip()
    parent = (r.get("Parent Identifier") or "").strip()
    sku = (r.get("SKU") or "").strip()
    match_id = (not APPLE_IDS) or (app_id in APPLE_IDS) or (parent in APPLE_IDS)
    match_sku_exact = (not SKUS) or (sku in SKUS)
    match_sku_pref = (not SKUS) or any(sku.startswith(p) for p in SKUS)
    return match_id or match_sku_exact or match_sku_pref

def asc_jwt():
    now = dt.datetime.now(dt.UTC)
    with open(ASC_P8_PATH, "rb") as f:
        key = f.read()
    exp = int(now.timestamp()) + 10 * 60
    return jwt.encode(
        {"iss": ASC_ISSUER_ID, "exp": exp, "aud": "appstoreconnect-v1"},
        key,
        algorithm="ES256",
        headers={"kid": ASC_KEY_ID},
    )

def _fetch_sales_report(report_date_iso: str, *, version: str | None = None, frequency: str = "DAILY") -> bytes:
    url = "https://api.appstoreconnect.apple.com/v1/salesReports"
    params = {
        "filter[reportType]": "SALES",
        "filter[reportSubType]": "SUMMARY",
        "filter[frequency]": frequency,
        "filter[reportDate]": report_date_iso,
        "filter[vendorNumber]": ASC_VENDOR,
    }
    if version:
        params["filter[version]"] = version
    token = asc_jwt()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/a-gzip",
        "Connection": "close",
        "User-Agent": "build-helper/1.0 (+okakichi)",
    }
    try:
        r = _session.get(
            url,
            headers=headers,
            params=params,
            timeout=(30, 300),
            verify=certifi.where(),
        )
        if r.status_code == 404:
            raise requests.HTTPError("Report not found (likely not generated yet).", response=r)
        r.raise_for_status()
        return r.content
    except (SSLError, Timeout, ReqConnErr):
        auth_header = f"Authorization: Bearer {token}"
        cmd = [
            "curl", "-g", "-sS", "-L", "--http1.1",
            "--retry", "5", "--retry-delay", "1", "--retry-all-errors",
            "--max-time", "310",
            "-H", auth_header,
            "-H", "Accept: application/a-gzip",
            f"{url}?{urlencode(list(params.items()))}",
        ]
        res = subprocess.run(cmd, check=True, capture_output=True)
        return res.stdout

def download_sales_summary_gz(report_date_iso: str) -> bytes:
    if hasattr(report_date_iso, "isoformat"):
        report_date_iso = report_date_iso.isoformat()
    target = min(dt.date.fromisoformat(str(report_date_iso).split("T", 1)[0]),
                 latest_asc_daily_date())
    try:
        return _fetch_sales_report(target.isoformat(), frequency="DAILY")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            d = target
            for _ in range(3):
                d -= dt.timedelta(days=1)
                try:
                    return _fetch_sales_report(d.isoformat(), frequency="DAILY")
                except requests.HTTPError as e2:
                    if not (e2.response is not None and e2.response.status_code == 404):
                        raise
        raise

def download_sales_summary_with_date(report_date_iso: str) -> tuple[list[dict] | None, dt.date | None]:
    if hasattr(report_date_iso, "isoformat"):
        report_date_iso = report_date_iso.isoformat()
    requested = dt.date.fromisoformat(str(report_date_iso).split("T", 1)[0])
    target = min(requested, latest_asc_daily_date())
    d = target
    for _ in range(4):
        try:
            gz = _fetch_sales_report(d.isoformat(), frequency="DAILY")
            rows = parse_summary_rows(gz)
            return rows, d
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                d -= dt.timedelta(days=1)
                continue
            raise
    return None, None
    
def parse_summary_rows(gz_bytes: bytes) -> list[dict]:
    with gzip.GzipFile(fileobj=io.BytesIO(gz_bytes)) as gz:
        text = gz.read().decode("utf-8", errors="replace")
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))

def latest_asc_daily_date() -> dt.date:
    la_today = dt.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    return la_today - dt.timedelta(days=1)

def get_apple_revenue(target_date=None, *, roll_to_latest_available=False):
    ref = _as_utc_date(target_date)
    eff_ref = min(ref, latest_asc_daily_date())
    start = eff_ref.replace(day=1)
    mtd_by_ccy: dict[str, Decimal] = {}
    yday_by_ccy: dict[str, Decimal] = {}
    counted_dates: set[dt.date] = set()
    latest_used_date: dt.date | None = None
    cur = start
    while cur <= eff_ref:
        rows, used_date = download_sales_summary_with_date(cur.isoformat())
        if not rows or not used_date:
            cur += dt.timedelta(days=1)
            continue
        if (latest_used_date is None) or (used_date > latest_used_date):
            latest_used_date = used_date
        add_mtd = used_date not in counted_dates
        for r in rows:
            if not _is_my_game(r):
                continue
            val = _proceeds_decimal(r)
            if val == 0:
                continue
            ccy = (_get_currency(r) or "UNKNOWN").upper()
            if add_mtd:
                mtd_by_ccy[ccy] = mtd_by_ccy.get(ccy, Decimal("0")) + val
            if used_date == eff_ref:
                yday_by_ccy[ccy] = yday_by_ccy.get(ccy, Decimal("0")) + val
        if add_mtd:
            counted_dates.add(used_date)
        cur += dt.timedelta(days=1)
    if roll_to_latest_available and not yday_by_ccy and latest_used_date:
        rows, _ = download_sales_summary_with_date(latest_used_date.isoformat())
        if rows:
            for r in rows[:5]:
                print({
                    "SKU": r.get("SKU"),
                    "Apple Identifier": r.get("Apple Identifier"),
                    "Product Type Identifier": r.get("Product Type Identifier"),
                    "Units": r.get("Units"),
                    "Proceeds Currency": r.get("Proceeds Currency") or r.get("Currency"),
                    "Developer Proceeds": r.get("Developer Proceeds"),
                })
            for r in rows:
                if not _is_my_game(r):
                    continue
                val = _proceeds_decimal(r)
                if val == 0:
                    continue
                ccy = (_get_currency(r) or "UNKNOWN").upper()
                yday_by_ccy[ccy] = yday_by_ccy.get(ccy, Decimal("0")) + val
    print("Apple Month Revenue:", float(sum(mtd_by_ccy.values(), Decimal("0"))))
    print("Apple Daily Revenue:", float(sum(yday_by_ccy.values(), Decimal("0"))))
    return {
        "month_revenue": float(sum(mtd_by_ccy.values(), Decimal("0"))),
        "yesterday_revenue": float(sum(yday_by_ccy.values(), Decimal("0"))),
        "month_by_currency": mtd_by_ccy,
        "yesterday_by_currency": yday_by_ccy,
        "effective_ref_date": eff_ref.isoformat(),
        "actual_latest_file_date": (latest_used_date.isoformat() if latest_used_date else None),
        "rolled_to_latest_available": bool(roll_to_latest_available and not yday_by_ccy),
    }
# ----- PlayFab Data -----
def _session_with_retries(total=5, backoff=0.6):
    retry = Retry(
        total=total,
        read=total,
        connect=total,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s

def _kul_month_to_yesterday():
    today = dt.datetime.now(dt.UTC)
    start = today.replace(day=1)
    end = today - timedelta(days=1)
    if end < start:
        end = start
    return start, end

def _daterange(start_date, end_date):
    cur = start_date
    while cur <= end_date:
        yield cur
        cur += timedelta(days=1)

def _norm(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (s or '').lower())

def _find_col(fieldnames, *candidates):
    normmap = {_norm(f): f for f in fieldnames}
    for c in candidates:
        col = normmap.get(_norm(c))
        if col:
            return col
    return None

def _month_to_yesterday_utc():
    today = datetime.now(UTC).date()
    start = today.replace(day=1)
    end = today - timedelta(days=1)
    if end < start:
        end = start
    return start, end

def _get_data_report_download_url(report_name, y, m, d, report_version=1, *, max_wait_attempts=3):
    url = f"{PLAYFAB_ENDPOINT}/Admin/GetDataReport"
    headers = {"X-SecretKey": PLAYFAB_SECRET, "Content-Type": "application/json"}
    payload = {
        "ReportName": report_name,
        "Year": int(y),
        "Month": int(m),
        "Day": int(d),
        "ReportVersion": int(report_version),
    }
    s = _session_with_retries()
    for attempt in range(1, max_wait_attempts + 1):
        r = s.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code != 200:
            snippet = r.text[:300].replace("\n", " ")
            if r.status_code == 400 and ("ReportNotProcessed" in snippet or '"errorCode":1603' in snippet):
                if attempt < max_wait_attempts:
                    continue
            raise RuntimeError(f"GetDataReport {y}-{m:02d}-{d:02d} failed: {r.status_code} {snippet}")
        data = (r.json() or {}).get("data") or {}
        dl = data.get("DownloadUrl")
        if dl:
            return dl
        mins = data.get("MinutesUntilReportReady")
        if attempt < max_wait_attempts:
            continue
        raise RuntimeError(f"GetDataReport {y}-{m:02d}-{d:02d} not ready after {max_wait_attempts} tries")

def _download_to(path, url):
    s = _session_with_retries()
    resp = s.get(url, timeout=180)
    resp.raise_for_status()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(resp.content)

def download_reports_month_to_yesterday(report_name="DailyTotalsReport", report_version=1, ref_day=None):
    out_dir = os.path.join(script_dir, "report")
    start, end = _month_to_yesterday_for(ref_day)
    saved = []
    for day in _daterange(start, end):
        y, m, d = day.year, day.month, day.day
        out_path = os.path.join(out_dir, f"{report_name}_{y}{m:02d}{d:02d}.csv")  
        if os.path.isfile(out_path):
            saved.append(out_path)
            continue
        try:
            dl = _get_data_report_download_url(report_name, y, m, d, report_version=report_version)
            _download_to(out_path, dl)
            saved.append(out_path)
        except Exception as e:
            continue
    return saved

def _read_mtd_mau(csv_path: str) -> int:
    with open(csv_path, newline="", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.DictReader(f)
        row = next(reader)
        def is_mtd_mau(k: str) -> bool:
            s = k.strip().lower()
            return ("month" in s and "to" in s and "date" in s and "mau" in s)
        for k, v in row.items():
            if is_mtd_mau(k):
                return int(str(v).replace(",", "")) if v else 0
    raise KeyError("MTD MAU column not found")

def get_current_month_mau_from_reports(report_dir="report", report_name="DailyTotalsReport"):
    files = glob.glob(os.path.join(report_dir, f"{report_name}_*.csv"))
    if not files:
        return 0
    files.sort(key=lambda p: int(os.path.basename(p).split("_")[-1].split(".")[0]))
    latest = files[-1]
    mau = _read_mtd_mau(latest)
    return mau

def _read_metrics(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.DictReader(f)
        row = next(reader)
        dau_col  = _find_col(reader.fieldnames, "Unique Logins")
        inst_col = _find_col(reader.fieldnames, "New Users")
        mau_col  = _find_col(reader.fieldnames, "Month to Date Mau")
        def to_int(x):
            s = (x or "").replace(",", "").strip()
            return int(float(s)) if s else 0
        return {
            "dau":      to_int(row[dau_col])  if dau_col  else 0,
            "installs": to_int(row[inst_col]) if inst_col else 0,
            "mtd_mau":  to_int(row[mau_col])  if mau_col  else 0,
        }

def _list_files(report_name="DailyTotalsReport"):
    report_dir = os.path.join(script_dir, "report")
    files = glob.glob(os.path.join(report_dir, f"{report_name}_*.csv"))
    files.sort(key=lambda p: int(os.path.basename(p).split("_")[-1].split(".")[0]))
    return files

def _date_from_filename(path):
    ds = os.path.splitext(os.path.basename(path))[0].split("_")[-1]
    return datetime.strptime(ds, "%Y%m%d").date()

def get_yesterday_metrics(report_name="DailyTotalsReport", ref_day=None):
    report_dir = os.path.join(script_dir, "report")
    target = _as_utc_date(ref_day)
    files = _list_files(report_name)
    if not files:
        return None, None
    by_date = { _date_from_filename(p): p for p in files }
    if target in by_date:
        day = target
    else:
        prior = [d for d in by_date if d <= target]
        day = max(prior) if prior else max(by_date)
    path = by_date[day]
    return day, _read_metrics(path)

def get_mtd_installs_until_latest(report_name="DailyTotalsReport", ref_day=None):
    files = _list_files(report_name)
    if not files:
        return None, 0
    ref = _as_utc_date(ref_day)
    candidates = [d for d in (_date_from_filename(p) for p in files) if d <= ref]
    if not candidates:
        return None, 0
    latest_date = max(candidates)
    year, month = latest_date.year, latest_date.month
    mtd_sum, last_date = 0, None
    for p in files:
        d = _date_from_filename(p)
        if d.year == year and d.month == month and d <= latest_date:
            mtd_sum += _read_metrics(p)["installs"]
            last_date = d
    return last_date, mtd_sum

def download_retention_reports_month_to_yesterday(report_name="ThirtyDayNewUserRetentionReport", ref_day=None):
    out_dir = os.path.join(script_dir, "report")
    os.makedirs(out_dir, exist_ok=True)
    base = _as_utc_date(ref_day)
    candidates = [base + timedelta(days=1), base, base - timedelta(days=1), base - timedelta(days=2)]
    for cur in candidates:
        y, m, d = cur.year, cur.month, cur.day
        out_path = os.path.join(out_dir, f"{report_name}_{y}{m:02d}{d:02d}.csv")
        if os.path.isfile(out_path):
            return out_path
        try:
            url = _get_data_report_download_url(report_name, y, m, d)
            _download_to(out_path, url)
            return out_path
        except RuntimeError as e:
            if "ReportNotProcessed" in str(e) or "not ready" in str(e):
                continue
            raise
    raise RuntimeError("No PlayFab retention report is ready for the last 2 days or next day.")

def _parse_cohort_date(s: str):
    s = (s or "").strip()
    if "T" in s:
        s = s.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Bad cohort date: {s}")

def _to_float(x):
    s = (x or "").replace("%","").replace(",","").strip()
    return float(s) if s else 0.0

def _to_int(x):
    s = (x or "").replace(",","").strip()
    return int(float(s)) if s else 0

def _as_utc_date(d=None):
    if d is None:
        return (datetime.now(ZoneInfo("UTC")) - timedelta(days=1)).date()
    if isinstance(d, str):
        return datetime.fromisoformat(d).date()
    return d

def _month_to_yesterday_for(ref_day):
    ref = _as_utc_date(ref_day)
    start = ref.replace(day=1)
    end = ref
    if end < start:
        end = start
    return start, end

def read_pf_new_user_retention_month_to_yesterday(csv_path, ref_day=None, lookback_days=60):
    ref = _as_utc_date(ref_day)
    start = ref - timedelta(days=lookback_days)
    end = ref
    out = {}
    with open(csv_path, newline="", encoding="utf-8-sig", errors="ignore") as f:
        r = csv.DictReader(f)
        for row in r:
            cohort = _parse_cohort_date(row.get("Cohort"))
            if not (start <= cohort <= end):
                continue
            days = _to_int(row.get("Days Later"))
            size = _to_int(row.get("Cohort Size"))
            pct = _to_float(row.get("Percent Retained"))
            key = cohort.isoformat()
            if cohort not in out:
                out[cohort] = {
                    "cohort_date": key,
                    "users": size,
                    "d1": 0.0,
                    "d3": 0.0,
                    "d7": 0.0,
                    "d14": 0.0,
                    "d30": 0.0
                }
            if size:
                out[cohort]["users"] = size
            if days == 1:
                out[cohort]["d1"] = pct
            elif days == 3:
                out[cohort]["d3"] = pct
            elif days == 7:
                out[cohort]["d7"] = pct
            elif days == 14:
                out[cohort]["d14"] = pct
            elif days == 30:
                out[cohort]["d30"] = pct
    return [out[k] for k in sorted(out)]

def pf_fetch_retention_rates(ref_day=None):
    download_reports_month_to_yesterday(report_name="DailyTotalsReport", ref_day=ref_day)
    csv_path = download_retention_reports_month_to_yesterday(report_name="ThirtyDayNewUserRetentionReport", ref_day=ref_day)
    cohorts = read_pf_new_user_retention_month_to_yesterday(csv_path, ref_day=ref_day, lookback_days=60)
    rows = []
    total_installs = 0
    yday_str = _as_utc_date(ref_day).strftime("%Y-%m-%d")
    for c in cohorts:
        date = c["cohort_date"]
        installs = int(c.get("users", 0))
        r1 = float(c.get("d1", 0.0)) / 100.0
        r3 = float(c.get("d3", 0.0)) / 100.0
        r7 = float(c.get("d7", 0.0)) / 100.0
        r14 = float(c.get("d14", 0.0)) / 100.0
        r30 = float(c.get("d30", 0.0)) / 100.0
        total_installs += installs
        rows.append({
            "date": date,
            "installs": installs,
            "revenue": 0.0,
            "retention_rate_d1": r1,
            "retention_rate_d3": r3,
            "retention_rate_d7": r7,
            "retention_rate_d14": r14,
            "retention_rate_d30": r30,
        })
    y_date, y_metrics = get_yesterday_metrics(ref_day=ref_day)
    dau = (y_metrics or {}).get('dau', 0)
    y_installs = (y_metrics or {}).get('installs', 0)
    m_date, mtd_installs = get_mtd_installs_until_latest(ref_day=ref_day)
    mau = get_current_month_mau_from_reports()
    return rows, total_installs, (
        next((int(c.get("users",0)) for c in cohorts if c["cohort_date"]==yday_str), 0)
    ), dau, mau, y_installs, (mtd_installs or 0)

def download_retention_reports_window(report_name="ThirtyDayNewUserRetentionReport", ref_day=None, days_before=1, days_after=0):
    out_dir = os.path.join(script_dir, "report")
    os.makedirs(out_dir, exist_ok=True)
    base = _as_utc_date(ref_day)
    today = datetime.now(ZoneInfo("UTC")).date()
    paths = []
    for delta in range(-days_before, days_after + 1):
        cur = base + timedelta(days=delta)
        if cur >= today:
            continue
        y, m, d = cur.year, cur.month, cur.day
        out_path = os.path.join(out_dir, f"{report_name}_{y}{m:02d}{d:02d}.csv")
        if os.path.isfile(out_path):
            paths.append(out_path)
            continue
        try:
            url = _get_data_report_download_url(report_name, y, m, d)
            _download_to(out_path, url)
            paths.append(out_path)
        except RuntimeError as e:
            if "ReportNotProcessed" in str(e) or "not ready" in str(e):
                continue
            raise
    if not paths:
        raise RuntimeError("No PlayFab retention reports in ±window around ref_day.")
    return paths

def _merge_pf_retention_rows(csv_paths, ref_day=None, lookback_days=60):
    by_cohort = {}
    for p in csv_paths:
        rows = read_pf_new_user_retention_month_to_yesterday(p, ref_day=ref_day, lookback_days=lookback_days)
        for r in rows:
            key = r["cohort_date"]
            if key not in by_cohort:
                by_cohort[key] = r.copy()
            else:
                if r["users"] > by_cohort[key]["users"]:
                    by_cohort[key]["users"] = r["users"]
                for k in ("d1", "d3", "d7", "d14"):
                    if by_cohort[key][k] == 0.0 and r[k] > 0.0:
                        by_cohort[key][k] = r[k]
                by_cohort[key]["d30"] = max(by_cohort[key]["d30"], r["d30"])
    return [by_cohort[k] for k in sorted(by_cohort)]

def exact_retention_for_day_playfab(rows, day_n, ref_day):
    cohort_date = (_as_utc_date(ref_day) - timedelta(days=day_n)).strftime("%Y-%m-%d")
    row = next((r for r in rows if r.get("date") == cohort_date), None)
    if not row:
        return None
    v = row.get(f"retention_rate_d{day_n}")
    try:
        return round(float(v) * 100.0, 2)
    except (TypeError, ValueError):
        return None

def exact_retention_for_day_adjust(rows, day_n, ref_day):
    cohort_date = (_as_utc_date(ref_day) - timedelta(days=day_n)).strftime("%Y-%m-%d")
    row = next((r for r in rows if r.get("date") == cohort_date), None)
    if not row:
        return 0.0
    v = row.get(f"retention_rate_d{day_n}")
    try:
        return round(float(v) * 100.0, 2)
    except (TypeError, ValueError):
        return 0.0

def exact_retention_for_day_adjust_manual(rows, day_n, ref_day):
    cohort_date = (_as_utc_date(ref_day) - timedelta(days=day_n)).strftime("%Y-%m-%d")
    row = next((r for r in rows if r.get("date") == cohort_date), None)
    if not row:
        return 0.0
    v = row.get(f"retention_rate_d{day_n}")
    try:
        return round(float(v) * 100.0, 2)
    except (TypeError, ValueError):
        return 0.0

def pf_fetch_retention_rates_ref_day(ref_day=None):
    download_reports_month_to_yesterday(report_name="DailyTotalsReport", ref_day=ref_day)
    paths = download_retention_reports_window(report_name="ThirtyDayNewUserRetentionReport",
                                              ref_day=ref_day, days_before=1, days_after=0)
    cohorts = _merge_pf_retention_rows(paths, ref_day=ref_day, lookback_days=60)
    rows = []
    total_installs = 0
    yday_str = _as_utc_date(ref_day).strftime("%Y-%m-%d")
    for c in cohorts:
        date = c["cohort_date"]
        installs = int(c.get("users", 0))
        r1 = float(c.get("d1", 0.0)) / 100.0
        r3 = float(c.get("d3", 0.0)) / 100.0
        r7 = float(c.get("d7", 0.0)) / 100.0
        r14 = float(c.get("d14", 0.0)) / 100.0
        r30 = float(c.get("d30", 0.0)) / 100.0
        total_installs += installs
        rows.append({
            "date": date,
            "installs": installs,
            "revenue": 0.0,
            "retention_rate_d1": r1,
            "retention_rate_d3": r3,
            "retention_rate_d7": r7,
            "retention_rate_d14": r14,
            "retention_rate_d30": r30,
        })
    y_date, y_metrics = get_yesterday_metrics(ref_day=ref_day)
    dau = (y_metrics or {}).get('dau', 0)
    y_installs = (y_metrics or {}).get('installs', 0)
    m_date, mtd_installs = get_mtd_installs_until_latest(ref_day=ref_day)
    mau = get_current_month_mau_from_reports()
    return rows, total_installs, (
        next((int(c.get("users",0)) for c in cohorts if c["cohort_date"]==yday_str), 0)
    ), dau, mau, y_installs, (mtd_installs or 0)

def fetch_retention_rates_range(start_date_iso, end_date_iso, cohort_maturity="immature"):
    url = (
        f"https://automate.adjust.com/reports-service/report?"
        f"app_token__in={APP_TOKEN}"
        f"&dimensions=day"
        f"&metrics=installs,revenue,"
        f"retention_rate_d1,retention_rate_d3,retention_rate_d7,"
        f"retention_rate_d14,retention_rate_d30"
        f"&date_period={start_date_iso}:{end_date_iso}"
        f"&cohort_maturity={cohort_maturity}"
        f"&attribution_source=first"
        f"&attribution_type=all"
        f"&country__in=all"
        f"&tracker__in=all"
        f"&full_data=true"
        f"&readable_names=false"
        f"&format_dates=false"
        f"&sandbox=false"
    )
    response = ADJUST_SESSION.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    rows = response.json().get("rows", []) or []
    parsed = []
    for row in rows:
        parsed.append({
            "date": row.get("day", ""),
            "installs": int(row.get("installs", 0)),
            "revenue": safe_float(row.get("revenue")),
            "retention_rate_d1":  safe_float(row.get("retention_rate_d1")),
            "retention_rate_d3":  safe_float(row.get("retention_rate_d3")),
            "retention_rate_d7":  safe_float(row.get("retention_rate_d7")),
            "retention_rate_d14": safe_float(row.get("retention_rate_d14")),
            "retention_rate_d30": safe_float(row.get("retention_rate_d30")),
        })
    return parsed

def estimate_paying_rate_with_arppu_list(dau, new_downloads, retentions, iap_revenue, arppu=None, *,
    base_small_dau_rate=5.0,
    base_large_dau_rate=10.0,
    large_dau_threshold=1000,
    retention_benchmarks=(30.0, 15.0, 7.0, 3.0, 1.5),
    retention_weights=None,
    quality_min=0.5, quality_max=1.5,
    maturity_alpha=0.5, maturity_min=0.7, maturity_max=1.1,
    assumed_purchase_size=600.0,
    arppu_floor=200.0, arppu_cap=5000.0,
    revenue_weight_cap=0.7,
    revenue_per_user_norm=10.0) -> float:
    if not dau or dau <= 0:
        return 0.0
    if not iap_revenue or iap_revenue <= 0:
        return 0.0
    base_rate = base_large_dau_rate if dau >= large_dau_threshold else base_small_dau_rate
    if retention_weights is None:
        n = len(retentions)
        retention_weights = [0.5] + [0.5/(n-1)]*(n-1) if n>1 else [1.0]
    total_w = sum(retention_weights)
    if total_w <= 0: retention_weights = [1.0/len(retentions)]*len(retentions)
    else: retention_weights = [w/total_w for w in retention_weights]
    ratios = []
    for r, b in zip(retentions, retention_benchmarks):
        if b > 0:
            ratios.append((r or 0.0) / b)
    quality = sum(w*ratios[i] for i, w in enumerate(retention_weights) if i < len(ratios))
    quality = max(quality_min, min(quality_max, quality))
    new_share = max(0.0, min(1.0, (new_downloads or 0.0) / dau))
    maturity = 1.0 - maturity_alpha * new_share
    maturity = max(maturity_min, min(maturity_max, maturity))
    prior_rate = base_rate * quality * maturity
    eff_arppu = arppu if (arppu and arppu > 0) else assumed_purchase_size
    eff_arppu = max(arppu_floor, min(arppu_cap, eff_arppu))
    est_payers = (iap_revenue or 0.0) / eff_arppu
    rev_rate = max(0.0, min(100.0, (est_payers / dau) * 100.0))
    rev_per_user = (iap_revenue or 0.0) / max(1.0, dau)
    w_rev = max(0.0, min(revenue_weight_cap, rev_per_user / revenue_per_user_norm))
    w_prior = 1.0 - w_rev
    return round(max(0.0, min(100.0, w_prior*prior_rate + w_rev*rev_rate)), 2)

def to_float(x, default=0.0):
    if x is None: return float(default)
    if isinstance(x, (int, float)): return float(x)
    s = str(x).strip().replace(",", "")
    if s.endswith("%"): s = s[:-1]
    try:
        return float(s)
    except Exception:
        return float(default)

def split_revenue_for_kpi(google_store_value, apple_store_value, *,
    google_value_is_gross=True,
    apple_value_is_proceeds=True,
    google_fee_pct=0.30,
    apple_fee_pct=0.30
):
    g_raw = to_float(google_store_value)
    a_raw = to_float(apple_store_value)
    g_gross = g_raw if google_value_is_gross else g_raw / max(1e-9, (1 - google_fee_pct))
    a_proceeds = a_raw if apple_value_is_proceeds else a_raw * (1 - apple_fee_pct)
    g_net_est = (1 - google_fee_pct) * g_gross
    a_net_est = a_proceeds
    return {
        "google_gross": f"¥{int(g_gross):,.2f}",
        "google_net_est": f"¥{int(g_net_est):,.2f}",
        "apple_gross_proxy": f"¥{int(a_proceeds / max(1e-9, (1 - apple_fee_pct)) if apple_value_is_proceeds else a_raw):,.2f}",
        "apple_net_est": f"¥{int(a_net_est):,.2f}",
        "total_gross_proxy": f"¥{int(g_gross + (a_proceeds / max(1e-9, (1 - apple_fee_pct)) if apple_value_is_proceeds else a_raw)):,.2f}",
        "total_net_est": f"¥{int(g_net_est + a_net_est):,.2f}",
    }

def paying_user_info():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    summary_col = db["telemetry_summary"]
    raw_col = db["telemetry_raw"]
    total_docs = summary_col.count_documents({})
    print(f"telemetry_summary total docs: {total_docs}")
    docs_with_cash = summary_col.count_documents(
        {"purchase_events.Cash.Count": {"$gt": 0}}
    )
    print(f"docs with purchase_events.Cash.Count > 0: {docs_with_cash}")
    sample = summary_col.find_one(
        {"purchase_events.Cash.Count": {"$gt": 0}},
        {"_id": 1, "purchase_events.Cash.EventId": 1},
    )
    if sample:
        print("\nSample cash summary doc:")
        print(sample)
        first_event_id = sample["purchase_events"]["Cash"]["EventId"][0]
        print(f"First Cash EventId from summary: {first_event_id}")
        raw_count_by__id = raw_col.count_documents({"_id": first_event_id})
        print(f"telemetry_raw documents with _id == eventId  : {raw_count_by__id}")
    else:
        print("No Cash docs in summary, aborting.")
        return
    pipeline = [
        {"$match": {"purchase_events.Cash.Count": {"$gt": 0}}},
        {
            "$project": {
                "playerId": "$_id",
                "cashEventIds": "$purchase_events.Cash.EventId",
            }
        },
        {"$unwind": "$cashEventIds"},
        {
            "$lookup": {
                "from": "telemetry_raw",
                "localField": "cashEventIds",
                "foreignField": "_id",
                "as": "purchaseDoc",
            }
        },
        {"$unwind": "$purchaseDoc"},
    ]
    print("\nRunning aggregation (join only)...")
    cursor = summary_col.aggregate(pipeline)
    players: dict[str, list[dict]] = {}
    for doc in cursor:
        player_id = doc["playerId"]
        event = doc["purchaseDoc"]
        payload = (event.get("Payload") or {})
        tdata = (payload.get("TelemetryData") or {})
        status = tdata.get("Status")
        env = tdata.get("Environment")
        revenue = tdata.get("Revenue")
        shop_id = tdata.get("ShopId", tdata.get("shopId"))
        ts = event.get("Timestamp")
        event_id = event.get("_id") or event.get("Id")

        players.setdefault(player_id, []).append(
            {
                "timestamp": ts,
                "revenue": revenue,
                "status": status,
                "environment": env,
                "shopId": shop_id,
                "eventId": event_id,
            }
        )
    print(f"\nPlayers with Cash purchases found (from summary): {len(players)}")
    if not players:
        print("Still no players – then the Cash bucket in summary is empty / mis-filled.")
        return
    for player_id, purchases in sorted(players.items()):
        print(f"\nPlayer: {player_id}")
        for p in purchases:
            revenue = p.get("revenue")
            currency = amount = None
            if isinstance(revenue, str) and " " in revenue:
                parts = revenue.split(" ", 1)
                currency = parts[0]
                try:
                    amount = float(parts[1])
                except ValueError:
                    amount = parts[1]

            print(
                f"  {p['timestamp']}  "
                f"{currency or ''} {amount if amount is not None else ''}  "
                f"(raw='{revenue}', "
                f"Status={p.get('status')}, Env={p.get('environment')})  "
                f"ShopId={p.get('shopId')}  "
                f"EventId={p.get('eventId')}"
            )

def get_paying_users_between(start_dt, end_dt):
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    summary_col = db["telemetry_summary"]
    if isinstance(start_dt, datetime):
        start_epoch = int(start_dt.timestamp())
    else:
        start_epoch = int(start_dt)
    if isinstance(end_dt, datetime):
        end_epoch = int(end_dt.timestamp())
    else:
        end_epoch = int(end_dt)
    pipeline = [
        {"$match": {"purchase_events.Cash.Count": {"$gt": 0}}},
        {
            "$project": {
                "playerId": "$_id",
                "cashEventIds": "$purchase_events.Cash.EventId",
            }
        },
        {"$unwind": "$cashEventIds"},
        {
            "$lookup": {
                "from": "telemetry_raw",
                "localField": "cashEventIds",
                "foreignField": "_id",
                "as": "purchaseDoc",
            }
        },
        {"$unwind": "$purchaseDoc"},
        {
            "$match": {
                "purchaseDoc.Timestamp": {
                    "$gte": start_epoch,
                    "$lt": end_epoch,
                }
            }
        },
        {"$group": {"_id": "$playerId"}},
        {"$count": "paying_users"},
    ]
    result = list(summary_col.aggregate(pipeline))
    count = result[0]["paying_users"] if result else 0
    return count

def paying_user():
    now_local = datetime.now()
    start_of_today_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_yesterday_local = start_of_today_local - timedelta(days=1)
    start_of_month_local = start_of_today_local.replace(day=1)
    start_of_today_utc = start_of_today_local.astimezone(timezone.utc)
    start_of_yesterday_utc = start_of_yesterday_local.astimezone(timezone.utc)
    start_of_month_utc = start_of_month_local.astimezone(timezone.utc)
    yesterday_count = get_paying_users_between(start_of_yesterday_utc, start_of_today_utc)
    this_month_count = get_paying_users_between(start_of_month_utc, start_of_today_utc)
    print(yesterday_count)
    print(this_month_count)
    return this_month_count, yesterday_count

def format_ts_to_date(ts):
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d")
    if isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(ts, timezone.utc)
        return dt.strftime("%Y-%m-%d")
    if isinstance(ts, str):
        return ts[:10]
    return str(ts)

def get_kpi_for_date(date_iso, raw_data=False):
    REPORT_DIR = os.path.join(script_dir, "report")
    if os.path.isdir(REPORT_DIR):
        shutil.rmtree(REPORT_DIR)
    ref_day = datetime.fromisoformat(date_iso).date()
    month_start = ref_day.replace(day=1)
    end_date = ref_day
    rows_month = fetch_retention_rates_range(f"{month_start:%Y-%m-%d}", f"{end_date:%Y-%m-%d}")
    yesterday_installs = next((int(r["installs"]) for r in rows_month if r.get("date") == date_iso), 0)
    lookback_start = ref_day - timedelta(days=60)
    rows_ext = fetch_retention_rates_range(
        f"{lookback_start:%Y-%m-%d}",
        f"{(end_date + timedelta(days=1)):%Y-%m-%d}",
        cohort_maturity="mature"
    )
    retention_rows = rows_ext
    try:
        sess = authed_session()
        download_sales_csvs_month_to_day(sess, BUCKET, ref_day=ref_day)
        google_revenue_month = get_google_revenue(yesterday_only=False, target_date=None)
        google_revenue_yesterday = get_google_revenue(yesterday_only=False, target_date=f"{ref_day:%Y-%m-%d}")
        print("Google Monthly Revenue:", google_revenue_month)
        print("Google Daily Revenue:", google_revenue_yesterday)
    finally:
        for p in glob.glob(os.path.join(".", "salesreport*.csv")):
            try:
                os.remove(p)
            except OSError:
                pass
    ads_rev = get_unity_ads_revenue(target_date=date_iso)
    ads_month_revenue = ads_rev["month_revenue"]
    ads_yesterday_revenue = ads_rev["yesterday_revenue"]
    a_rev = get_apple_revenue(target_date=date_iso)
    apple_revenue_month = a_rev["month_revenue"]
    apple_revenue_yesterday = a_rev["yesterday_revenue"]

    rev_month = split_revenue_for_kpi(
        google_store_value=google_revenue_month,
        apple_store_value=apple_revenue_month,
        google_value_is_gross=True,
        apple_value_is_proceeds=True,
        google_fee_pct=0.30,
        apple_fee_pct=0.30
    )

    rev_yesterday = split_revenue_for_kpi(
        google_store_value=google_revenue_yesterday,
        apple_store_value=apple_revenue_yesterday,
        google_value_is_gross=True,
        apple_value_is_proceeds=True,
        google_fee_pct=0.30,
        apple_fee_pct=0.30
    )

    month_gross_total = rev_month["total_gross_proxy"]
    month_net_est_total = rev_month["total_net_est"]
    yesteday_gross_total = rev_yesterday["total_gross_proxy"]
    yesteday_net_est_total = rev_yesterday["total_net_est"]

    total_month_revenue = google_revenue_month + apple_revenue_month
    total_day_revenue   = google_revenue_yesterday + apple_revenue_yesterday
    event_users_total = fetch_event_users(target_date=date_iso)
    _, average_dau, daily_dau = fetch_daus(target_date=date_iso)
    adjust_maus = fetch_month_mau(target_date=date_iso)
    report_data = {
        "totals": {
            "revenue": total_month_revenue,
            "yesterday_revenue": total_day_revenue,
            "installs": sum(r["installs"] for r in rows_month),
            "daus": average_dau,
            "sessions": 0,
            "month_gross": month_gross_total,
            "month_net_est": month_net_est_total,
            "yesterday_gross": yesteday_gross_total,
            "yesterday_net_est": yesteday_net_est_total
        },
        "rows": rows_month,
    }
    
    if raw_data:
        return format_kpi_report(report_data, daily_dau, retention_rows, total_month_revenue, total_day_revenue,
                                 ads_month_revenue, ads_yesterday_revenue, yesterday_installs, adjust_maus, 
                                 adjust=False, raw_data=True, target_date=date_iso)
    else:
        return format_kpi_report(report_data, daily_dau, retention_rows, total_month_revenue, total_day_revenue, 
                                 ads_month_revenue, ads_yesterday_revenue, yesterday_installs, adjust_maus, 
                                 adjust=False, raw_data=False, target_date=date_iso)

def sheets_service():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(SHEETS_JSON,scopes=scopes)
    return build("sheets", "v4", credentials=creds)

def append_kpi_text_to_sheet(date_iso):
    raw = get_kpi_for_date(date_iso, raw_data=True)
    (
        total_month_revenue, ads_revenue_month, pf_mau, playfab_mtd_installs,
        playfab_arppu_total, est_payrate_month_playfab, daily_revenu, ads_d_revenu, useThis_dau,
        playfab_y_installs, playfab_daily_arppu_total, est_payrate_day_playfab,
        day1_playfab, day3_playfab, day7_playfab, day14_playfab, day30_playfab
    ) = raw
    avg_retention = (day1_playfab + day3_playfab + day7_playfab + day14_playfab + day30_playfab) / 5.0
    service = sheets_service()
    sheet = service.spreadsheets()
    resp = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Sheet1!A:A",
    ).execute()
    rows = resp.get("values", [])
    target_row = None
    for idx, row in enumerate(rows, start=1):
        if row and row[0] == date_iso:
            target_row = idx
            break
    if target_row is None:
        target_row = len(rows) + 1
    row_values = [
        date_iso,
        total_month_revenue, ads_revenue_month, pf_mau, playfab_mtd_installs,
        playfab_arppu_total, est_payrate_month_playfab, daily_revenu, ads_d_revenu, useThis_dau,
        playfab_y_installs, playfab_daily_arppu_total, est_payrate_day_playfab,
        day1_playfab, day3_playfab, day7_playfab, day14_playfab, day30_playfab,
        avg_retention,
    ]
    body = {"values": [row_values]}
    result = sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"Sheet1!A{target_row}:S{target_row}",
        valueInputOption="RAW",
        body=body,
    ).execute()
    print(f"Updated Sheet1 row {target_row} for {date_iso}")
    return result

def get_kpi():
    gap_day = (datetime.now(timezone.utc).date() - timedelta(days=1)).strftime("%Y-%m-%d")
    append_kpi_text_to_sheet(gap_day)
    return get_kpi_for_date(gap_day, raw_data=False)

# if __name__ == "__main__":
#    gap_day = (datetime.now(timezone.utc).date() - timedelta(days=1)).strftime("%Y-%m-%d")
#    print(get_kpi_for_date(gap_day, raw_data=False))

#    start_date = datetime(datetime.today().year, 9, 1)
#    end_date = datetime.today() - timedelta(days=1)
#    current_date = start_date
#    while current_date <= end_date:
#       print(current_date.strftime("%Y-%m-%d"))
#       print(get_kpi_for_date(current_date.strftime("%Y-%m-%d"), True))
#       current_date += timedelta(days=1)

   # target_date = "2025-12-01"
   # append_kpi_text_to_sheet(target_date)
   # get_kpi_for_date(target_date, raw_data=False)

#   paying_user_info()