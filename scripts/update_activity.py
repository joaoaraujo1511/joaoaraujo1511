"""Publish aggregate activity and languages from PUBLIC, owned, non-fork projects.

Only this module contacts GitHub. No private repository nodes, titles or code are
requested. API responses and credentials are never written to logs or files.
"""
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import html
import json
import math
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

OWNER = "joaoaraujo1511"
START = date(2025, 9, 1)
ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("totalCommitContributions", "totalPullRequestContributions", "totalPullRequestReviewContributions")


def request(query, variables=None):
    token = os.environ.get("METRICS_READ_TOKEN", "")
    if not token:
        raise ValueError("Add the METRICS_READ_TOKEN Actions secret with only read:user scope.")
    req = urllib.request.Request("https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": "Bearer " + token, "User-Agent": "profile-activity-updater", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as response:
        scopes = {s.strip() for s in response.headers.get("X-OAuth-Scopes", "").split(",") if s.strip()}
        if scopes != {"read:user"}:
            raise ValueError("Use a classic token with ONLY read:user; broader permissions are rejected.")
        payload = json.load(response)
    if payload.get("errors") or not payload.get("data"):
        raise ValueError("GitHub could not return complete metrics; keeping the previous images.")
    return payload["data"]


def months_between(start, end):
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield f"{year:04}-{month:02}"
        month += 1
        if month == 13:
            year, month = year + 1, 1


def aggregate_daily(days, today):
    expected = (today - START).days + 1
    if len(days) != expected or min(days) != START.isoformat() or max(days) != today.isoformat():
        raise ValueError("Incomplete contribution history; keeping the previous images.")
    monthly = dict.fromkeys(months_between(START, today), 0)
    for day, count in days.items():
        date.fromisoformat(day)
        if not isinstance(count, int) or count < 0:
            raise ValueError("Invalid contribution count.")
        monthly[day[:7]] += count
    return monthly


def collect(now):
    # UTC boundaries match GitHub's contribution calendar. Local date is display-only.
    today = now.date()
    identity = request('query { viewer { login createdAt } }')["viewer"]
    if identity["login"].lower() != OWNER:
        raise ValueError("The token must belong to the profile owner.")
    totals = dict.fromkeys(FIELDS, 0)
    daily = {}
    for year in range(int(identity["createdAt"][:4]), today.year + 1):
        end = min(now, datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
        query = '''query($from:DateTime!,$to:DateTime!) { viewer {
          contributionsCollection(from:$from,to:$to) {
            totalCommitContributions totalPullRequestContributions totalPullRequestReviewContributions
            contributionCalendar { weeks { contributionDays { date contributionCount } } }
          }
        }}'''
        row = request(query, {"from": f"{year}-01-01T00:00:00Z", "to": end.isoformat()})["viewer"]["contributionsCollection"]
        for field in FIELDS:
            totals[field] += row[field]
        for week in row["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                stamp = day["date"]
                if START.isoformat() <= stamp <= today.isoformat() and stamp[:4] == str(year):
                    if stamp in daily:
                        raise ValueError("Duplicate contribution day.")
                    daily[stamp] = day["contributionCount"]
    # Prevent replacing the approved full-history card with an accidentally
    # public-only response. A legitimate GitHub history rewrite needs review.
    if any(totals[field] < floor for field, floor in zip(FIELDS, (930, 125, 6))):
        raise ValueError("Totals are below the verified baseline; check private contribution visibility before publishing.")
    monthly = aggregate_daily(daily, today)
    languages, colors, projects = Counter(), {}, 0
    cursor = None
    while True:
        public = request('''query($cursor:String) { viewer {
          repositories(first:100,after:$cursor,privacy:PUBLIC,isFork:false,ownerAffiliations:OWNER) {
            pageInfo { hasNextPage endCursor }
            nodes { name isPrivate languages(first:100) {
              pageInfo { hasNextPage } edges { size node { name color } }
            } }
          }
        }}''', {"cursor": cursor})["viewer"]["repositories"]
        for repo in public["nodes"]:
            if repo["isPrivate"]:
                raise ValueError("Unexpected private repository; refusing to process languages.")
            if repo["name"].lower() == OWNER:
                continue
            if repo["languages"]["pageInfo"]["hasNextPage"]:
                raise ValueError("Language response was truncated.")
            projects += 1
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                languages[name] += edge["size"]
                color = edge["node"]["color"] or "#9198a1"
                if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                    raise ValueError("Invalid language color.")
                colors[name] = color
        if not public["pageInfo"]["hasNextPage"]:
            break
        cursor = public["pageInfo"]["endCursor"]
    return {"totals": totals, "monthly": monthly, "languages": dict(languages.most_common()),
            "colors": colors, "projects": projects, "date": today.isoformat(),
            "updated": now.astimezone(ZoneInfo("Europe/Lisbon")).date().isoformat()}


def description(data):
    counts = [data["totals"][f] for f in FIELDS]
    return (f"GitHub activity: {counts[0]} lifetime commit contributions, {counts[1]} pull requests opened, "
            f"and {counts[2]} reviews. Public project languages and monthly contribution totals from "
            f"September 2025 to {data['date']}. Activity includes anonymous private totals. Updated {data['updated']}.")


def render(data, theme):
    bg, fg, muted, border, accent = (("#0d1117", "#f0f6fc", "#9198a1", "#30363d", "#b8c6d4")
        if theme == "dark" else ("#ffffff", "#1f2328", "#59636e", "#d1d9e0", "#596f83"))
    languages = list(data["languages"].items())
    top = max(263, 140 + math.ceil(len(languages) / 2) * 41)
    months = list(data["monthly"].items())
    chunks = [months[i:i + 18] for i in range(0, len(months), 18)]
    footer = top + 269 * len(chunks)
    height = footer + 34
    p = [f'<rect x=".5" y=".5" width="831" height="{height-1}" rx="10" fill="{bg}" stroke="{border}"/>']
    def text(x, y, value, size=12, color=fg, weight=400, anchor="start"):
        p.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{html.escape(str(value))}</text>')
    text(24, 38, "Activity", 16, weight=600)
    text(24, 61, "Lifetime contributions", 11, muted)
    p.append(f'<path d="M344 24V{top-19}" stroke="{border}"/>')
    icons = ['<circle cx="8" cy="8" r="3"/><path d="M0 8h5m6 0h5"/>',
        '<circle cx="4" cy="3" r="2"/><circle cx="4" cy="13" r="2"/><circle cx="13" cy="13" r="2"/><path d="M4 5v6m6-8h1a2 2 0 0 1 2 2v6"/>',
        '<path d="M2 2h12v10H8l-4 3v-3H2Z"/><path d="m5 6 2 2 4-4"/>']
    for i, (field, label, icon) in enumerate(zip(FIELDS, ("Commit contributions", "Pull requests opened", "Pull request reviews"), icons)):
        y = 101 + i * 57
        value = f'{data["totals"][field]:,}'
        p.append(f'<g transform="translate(26 {y-12})" fill="none" stroke="{muted}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">{icon}</g>')
        text(58, y+2, value, min(23, 105 / max(4, len(value))), weight=600)
        text(151, y, label, 12, muted)
    text(372, 38, "Languages in public projects", 16, weight=600)
    text(372, 61, f'Share of code bytes · {data["projects"]} public projects', 11, muted)
    total = sum(v for _, v in languages)
    p.append('<defs><clipPath id="language-bar"><rect x="372" y="82" width="432" height="10" rx="5"/></clipPath></defs><g clip-path="url(#language-bar)">')
    x = 372
    for name, value in languages:
        width = value / total * 432
        p.append(f'<rect x="{x}" y="82" width="{width}" height="10" fill="{data["colors"][name]}"/>')
        x += width
    p.append('</g>')
    for i, (name, value) in enumerate(languages):
        x, y = 372 + i % 2 * 226, 124 + i // 2 * 41
        p.append(f'<circle cx="{x+4}" cy="{y-4}" r="4" fill="{data["colors"][name]}"/>')
        text(x+16, y, name, min(12, 140 / max(1, len(name)) * 1.7))
        text(x+202, y, f'{value / total * 100:.2f}%', 11, muted, anchor="end")
    if not total:
        text(372, 124, "No public language data yet", color=muted)
    text(372, top-22, "Language share reflects repository contents.", 10, muted)
    ceiling = max(50, math.ceil(max(data["monthly"].values(), default=0) / 50) * 50)
    for index, chunk in enumerate(chunks):
        y0 = top + index * 269
        p.append(f'<path d="M24 {y0}H808" stroke="{border}"/>')
        text(24, y0+39, "Monthly contributions", 15, weight=600)
        ending = date.fromisoformat(data["date"]) if index == len(chunks)-1 else date.fromisoformat(chunk[-1][0]+"-01")
        label = date.fromisoformat(chunk[0][0]+"-01").strftime("%b %Y") + " – " + ending.strftime("%d %b %Y" if index == len(chunks)-1 else "%b %Y")
        text(808, y0+39, label.upper(), 10, muted, anchor="end")
        baseline, pitch = y0+207, 756 / len(chunk)
        for fraction in (0, .5, 1):
            y = baseline - fraction * 136
            p.append(f'<path d="M52 {y}H808" stroke="{border}" stroke-dasharray="3 5"/>')
            text(42, y+4, round(fraction*ceiling), 10, muted, anchor="end")
        year_positions = {}
        for i, (month, value) in enumerate(chunk):
            center, barheight = 52 + (i+.5)*pitch, value / ceiling * 136
            width = min(31, pitch*.6)
            p.append(f'<rect x="{center-width/2}" y="{baseline-barheight}" width="{width}" height="{barheight}" rx="3" fill="{accent}" opacity="{1 if value == max(data["monthly"].values()) else .65}"/>')
            text(center, baseline-10-barheight, value, 11, weight=600, anchor="middle")
            text(center, baseline+21, date.fromisoformat(month+"-01").strftime("%b"), 10, muted, anchor="middle")
            year_positions.setdefault(month[:4], []).append(center)
        for year, centers in year_positions.items():
            text(sum(centers)/len(centers), baseline+45, year, 10, muted, anchor="middle")
    p.append(f'<path d="M24 {footer}H808" stroke="{border}"/>')
    text(24, footer+20, "Activity includes anonymous private totals", 11, muted)
    text(808, footer+20, "Updated " + date.fromisoformat(data["updated"]).strftime("%d %b %Y"), 11, muted, anchor="end")
    alt = html.escape(description(data), quote=True)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="832" height="{height}" viewBox="0 0 832 {height}" role="img" aria-label="{alt}"><title>{alt}</title><g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif">' + ''.join(p) + '</g></svg>'
    ET.fromstring(svg)
    return svg


def publish(data, root=ROOT):
    assets = {theme: render(data, theme) for theme in ("dark", "light")}
    # Hash in the URL prevents stale GitHub image caches; only these two files remain.
    digest = hashlib.sha256(''.join(assets.values()).encode()).hexdigest()[:12]
    alt = html.escape(description(data), quote=True)
    picture = f'''## Activity

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/activity-auto-{digest}-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/activity-auto-{digest}-light.svg">
  <img src="assets/activity-auto-{digest}-light.svg" alt="{alt}" width="832">
</picture>

'''
    readme = root / "README.md"
    previous = readme.read_text(encoding="utf-8")
    updated, matches = re.subn(r'## Activity\s.*?(?=### Reach me)', lambda _: picture, previous, flags=re.S)
    if matches != 1:
        raise ValueError("Expected one Activity section; refusing to change the README.")
    (root / "assets").mkdir(exist_ok=True)
    for theme, content in assets.items():
        (root / "assets" / f"activity-auto-{digest}-{theme}.svg").write_text(content, encoding="utf-8")
    readme.write_text(updated, encoding="utf-8")
    for old in (root / "assets").glob("activity-auto-*.svg"):
        if re.fullmatch(r"activity-auto-[a-f0-9]{12}-(dark|light)\.svg", old.name) and digest not in old.name:
            old.unlink()


if __name__ == "__main__":
    try:
        publish(collect(datetime.now(timezone.utc)))
        print("Updated activity totals, public languages and monthly contributions.")
    except Exception as error:
        # Never print raw server responses or request objects, which may contain secrets.
        print("Activity update failed (" + type(error).__name__ + "). Previous published assets remain unchanged.", file=sys.stderr)
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        sys.exit(1)
