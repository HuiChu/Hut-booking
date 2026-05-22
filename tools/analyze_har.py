"""Analyze a HAR file and print a redacted summary.

Redacted: response bodies, query/form VALUES (only field names kept), cookie values,
header values that look sensitive. Useful for sharing recon results without leaking PII.

Usage:
  uv run python tools/analyze_har.py storage/recon/hike_taiwan_gov_tw.har
  uv run python tools/analyze_har.py <path> --show-values  # if you want values too (don't share)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


SENSITIVE_HEADERS = {"cookie", "set-cookie", "authorization", "x-csrf-token"}


def short(s: str, n: int = 80) -> str:
    s = s.replace("\n", " ").replace("\r", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


def is_aspnet_form_post(entry: dict) -> bool:
    req = entry["request"]
    if req["method"] != "POST":
        return False
    post = req.get("postData", {})
    text = post.get("text", "")
    return "__VIEWSTATE" in text or "__EVENTTARGET" in text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("har", type=Path)
    ap.add_argument("--show-values", action="store_true", help="DO NOT share output; includes PII")
    ap.add_argument("--host-filter", default="hike.taiwan.gov.tw")
    args = ap.parse_args()

    data = json.loads(args.har.read_text(encoding="utf-8"))
    entries = data["log"]["entries"]

    # 1. URL summary
    url_methods: list[tuple[str, str, int, str]] = []
    for e in entries:
        req, resp = e["request"], e["response"]
        url = req["url"]
        host = urlparse(url).netloc
        if args.host_filter and args.host_filter not in host:
            continue
        path = urlparse(url).path + ("?" + urlparse(url).query if urlparse(url).query else "")
        url_methods.append((req["method"], path, resp["status"], host))

    print(f"# HAR analysis: {args.har}")
    print(f"# total entries: {len(entries)} | filtered to {args.host_filter}: {len(url_methods)}")
    print()

    # 2. URL chronology
    print("## Request chronology (host-filtered)")
    print(f"{'method':<6} {'status':<6} path")
    print("-" * 100)
    for method, path, status, _host in url_methods:
        print(f"{method:<6} {status:<6} {short(path, 90)}")
    print()

    # 3. ASP.NET POSTs — extract __EVENTTARGET + payload field names
    print("## ASP.NET form POSTs (have __VIEWSTATE / __EVENTTARGET)")
    print()
    aspnet_posts = [e for e in entries if args.host_filter in urlparse(e["request"]["url"]).netloc and is_aspnet_form_post(e)]
    if not aspnet_posts:
        print("(none found — did the form POSTs actually go through?)")
    for i, e in enumerate(aspnet_posts, 1):
        req, resp = e["request"], e["response"]
        url = urlparse(req["url"])
        post = req.get("postData", {})
        params = post.get("params") or []
        text = post.get("text", "")
        if not params and text:
            # Parse url-encoded body manually
            from urllib.parse import parse_qsl
            params = [{"name": k, "value": v} for k, v in parse_qsl(text, keep_blank_values=True)]

        print(f"### POST #{i}: {url.path}{('?' + url.query) if url.query else ''}")
        print(f"  status: {resp['status']}")
        # __EVENTTARGET value matters; it tells us which button was clicked
        evt = next((p["value"] for p in params if p["name"] == "__EVENTTARGET"), "")
        evtarg = next((p["value"] for p in params if p["name"] == "__EVENTARGUMENT"), "")
        print(f"  __EVENTTARGET   = {evt!r}")
        print(f"  __EVENTARGUMENT = {evtarg!r}")
        print(f"  fields ({len(params)}):")
        for p in params:
            name = p["name"]
            value = p.get("value", "")
            if args.show_values:
                disp = short(value, 60)
            elif name.startswith("__"):
                disp = f"<{len(value)} chars>" if name in ("__VIEWSTATE", "__EVENTVALIDATION") else short(value, 60)
            else:
                disp = f"<{len(value)} chars>" if value else "<empty>"
            print(f"    {name:<50} = {disp}")
        # Look for redirect / next URL in response
        loc = next((h["value"] for h in resp.get("headers", []) if h["name"].lower() == "location"), None)
        if loc:
            print(f"  → redirect Location: {loc}")
        print()

    # 4. GET pages (form pages)
    print("## GET pages with HTML response (likely form pages)")
    print(f"{'status':<6} {'len':<10} path")
    print("-" * 100)
    for e in entries:
        req, resp = e["request"], e["response"]
        if req["method"] != "GET":
            continue
        host = urlparse(req["url"]).netloc
        if args.host_filter not in host:
            continue
        content_type = next((h["value"] for h in resp.get("headers", []) if h["name"].lower() == "content-type"), "")
        if "text/html" not in content_type:
            continue
        size = resp.get("content", {}).get("size", 0)
        path = urlparse(req["url"]).path + ("?" + urlparse(req["url"]).query if urlparse(req["url"]).query else "")
        print(f"{resp['status']:<6} {size:<10} {short(path, 90)}")
    print()

    # 5. Captcha / image requests
    print("## Suspected CAPTCHA / verification requests")
    captcha_keywords = ("captcha", "verify", "code", "validate")
    found = False
    for e in entries:
        req = e["request"]
        url_lower = req["url"].lower()
        if any(kw in url_lower for kw in captcha_keywords):
            print(f"  {req['method']:<6} {req['url']}")
            found = True
    if not found:
        print("  (none found by keyword)")
    print()

    # 6. Cookie names (no values)
    print("## Cookies set (names only)")
    cookie_names: Counter[str] = Counter()
    for e in entries:
        for h in e["response"].get("headers", []):
            if h["name"].lower() == "set-cookie":
                cname = h["value"].split("=", 1)[0]
                cookie_names[cname] += 1
    for name, count in cookie_names.most_common():
        print(f"  {name:<40} (set {count} times)")
    print()

    # 7. Hosts
    print("## All hosts contacted (no filter)")
    hosts = Counter(urlparse(e["request"]["url"]).netloc for e in entries)
    for host, count in hosts.most_common():
        print(f"  {host:<40} {count}")


if __name__ == "__main__":
    main()
