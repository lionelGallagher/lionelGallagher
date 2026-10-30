"""Refresh the profile's calendar-based experience and last-good statistics cards.

The start is the earliest verified public commit authored by the profile owner.
Search may extend that history, but a missing search result never erases it.
Uses only Python's standard library; no personal access token is required.
"""

import calendar
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = timezone(timedelta(hours=8))


def elapsed(start: date, today: date) -> tuple[int, int, int]:
    """Completed calendar years/months and remaining days, with month-end clamping."""
    if today < start:
        raise ValueError("The first commit cannot be in the future")
    months = (today.year - start.year) * 12 + today.month - start.month

    def anniversary(count):
        year, month = divmod(start.year * 12 + start.month - 1 + count, 12)
        month += 1
        return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))

    if anniversary(months) > today:
        months -= 1
    years, remaining_months = divmod(months, 12)
    return years, remaining_months, (today - anniversary(months)).days


def commit_time(record):
    return datetime.fromisoformat(record["date"].replace("Z", "+00:00"))


def select_first_commit(items, known, owner):
    candidates = [known]
    for item in items:
        if (item.get("author") or {}).get("login", "").lower() != owner.lower():
            continue
        candidates.append({"date": item["commit"]["author"]["date"],
                           "sha": item["sha"], "url": item["html_url"]})
    return min(candidates, key=commit_time)


def fetch(url, authenticated=False):
    headers = {"User-Agent": "lionel-profile-refresh", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if authenticated and token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        return response.read(2_000_000)


def save_svg(path, payload):
    """Validate before replacing a previously working image."""
    root = ET.fromstring(payload)
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("Response is not an SVG image")
    visible = " ".join(root.itertext()).lower()
    for error in ("something went wrong", "could not fetch", "rate limit", "maximum retries",
                  "user not found", "deployment_paused", "deployment_disabled"):
        if error in visible:
            raise ValueError("Upstream returned an error card: " + error)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def render_experience(first_commit, today, compact=False):
    start = commit_time(first_commit).astimezone(SHANGHAI).date()
    years, months, days = elapsed(start, today)
    total = (today - start).days
    description = escape(f"工作经验按首次公开提交起累计：{years} 年 {months} 个月 {days} 天。"
                         f"起点 {start}，更新 {today}，上海时间。")
    if compact:
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="252" viewBox="0 0 640 252" role="img" aria-labelledby="title desc">
  <title id="title">精神时光屋 / 工作经验 · {years} 年 {months} 个月 {days} 天</title>
  <desc id="desc">{description}</desc>
  <rect x="1" y="1" width="638" height="250" rx="6" fill="#071015" stroke="#31513e"/>
  <path d="M2 2H13V28H2Z M2 36H8V62H2Z M2 70H13V96H2Z" fill="#ffb34a"/>
  <g font-family="Consolas, 'Microsoft YaHei', monospace">
    <text x="30" y="40" font-size="18" fill="#ffb34a" letter-spacing="2">CAPSULE / 精神时光屋</text>
    <text x="30" y="106" font-size="42" font-weight="700" fill="#e8f1ff">{years} 年 <tspan fill="#ffb34a">{months}</tspan> 个月 <tspan fill="#89e8a2">{days}</tspan> 天</text>
    <text x="30" y="145" font-size="18" fill="#91a3bc">地球修炼时间 · 首次提交至今</text>
    <path d="M30 166H610" stroke="#31513e"/>
    <text x="30" y="199" font-size="17" fill="#91a3bc">SINCE <tspan fill="#e8f1ff">{start}</tspan> <tspan fill="#ffb34a">/ DAY {total:06d}</tspan></text>
    <text x="30" y="229" font-size="15" fill="#91a3bc">AS OF {today} · UTC+08:00</text>
  </g>
</svg>
'''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="164" viewBox="0 0 1280 164" role="img" aria-labelledby="title desc">
  <title id="title">精神时光屋 / 工作经验 · {years} 年 {months} 个月 {days} 天</title>
  <desc id="desc">{description}</desc>
  <rect x="1" y="1" width="1278" height="162" rx="6" fill="#071015" stroke="#31513e"/>
  <path d="M2 2H13V28H2Z M2 36H8V62H2Z M2 70H13V96H2Z" fill="#ffb34a"/>
  <g font-family="Consolas, 'SFMono-Regular', monospace">
    <text x="38" y="39" font-size="13" fill="#ffb34a" letter-spacing="2">CAPSULE / 精神时光屋</text>
    <text x="38" y="101" font-size="43" font-weight="700" fill="#e8f1ff">{years} 年 <tspan fill="#ffb34a">{months}</tspan> 个月 <tspan fill="#89e8a2">{days}</tspan> 天</text>
    <text x="40" y="136" font-size="13" fill="#91a3bc">地球修炼时间 · 首次提交至今</text>
    <path d="M760 32V132" stroke="#31513e"/>
    <text x="798" y="46" font-size="13" fill="#91a3bc">TRAINING START <tspan fill="#e8f1ff">{start}</tspan></text>
    <text x="798" y="84" font-size="25" fill="#ffb34a" letter-spacing="2">DAY {total:06d} / KEEP TRAINING</text>
    <text x="798" y="124" font-size="12" fill="#91a3bc">AS OF {today} · UTC+08:00 · DAILY REFRESH</text>
  </g>
</svg>
'''


def main():
    config_path = ROOT / "data/profile.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    owner = config["owner"]
    query = urllib.parse.urlencode({"q": "author:" + owner, "sort": "author-date",
                                    "order": "asc", "per_page": 10})
    try:
        result = json.loads(fetch("https://api.github.com/search/commits?" + query, authenticated=True))
        config["first_commit"] = select_first_commit(result["items"], config["first_commit"], owner)
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as error:
        print(f"::warning::Commit search unavailable; retaining verified first commit ({type(error).__name__})")

    today = datetime.now(SHANGHAI).date()
    image_dir = ROOT / "images"
    image_dir.mkdir(exist_ok=True)
    save_svg(image_dir / "experience.svg", render_experience(config["first_commit"], today).encode())
    save_svg(image_dir / "experience-mobile.svg", render_experience(config["first_commit"], today, compact=True).encode())
    print("Experience refreshed:", config["first_commit"]["date"], "->", today)

    common = {"username": owner, "bg_color": "071015", "title_color": "ffb34a",
              "text_color": "d3e4d4", "icon_color": "89e8a2", "border_color": "31513e",
              "locale": "cn", "border_radius": "6", "disable_animations": "true"}
    cards = [
        ("github-stats.svg", "/api", {"custom_title": "战斗力探测报告", "show_icons": "true", "hide_rank": "true", "include_all_commits": "true", "card_width": "520"}),
        ("top-langs.svg", "/api/top-langs/", {"custom_title": "技能能量分布", "langs_count": "6", "layout": "compact", "card_width": "420"}),
    ]
    for filename, endpoint, options in cards:
        path = image_dir / filename
        url = "https://github-stats-extended.vercel.app" + endpoint + "?" + urllib.parse.urlencode(common | options)
        try:
            svg = fetch(url).decode("utf-8")
            svg = "\n".join(line.rstrip() for line in svg.strip().splitlines()) + "\n"
            save_svg(path, svg.encode("utf-8"))
            print("Statistics cached:", filename)
        except Exception as error:
            if not path.exists():
                raise RuntimeError("No valid initial statistics card: " + filename) from error
            print(f"::warning::{filename} upstream unavailable; retaining last valid image ({type(error).__name__})")


if __name__ == "__main__":
    main()
