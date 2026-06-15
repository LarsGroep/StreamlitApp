"""
Verify Beatport label IDs by checking the v4 releases API.
Uses an anon token from a known-good label page (Drumcode id=2027).
For each label, checks:
  - Does the v4 API return any releases at all?
  - What's the release count?
  - Does the label name in releases match what we expect?
"""

import asyncio
import json
from pathlib import Path

_LABELS_FILE = Path(__file__).parent / "input" / "framework_labels.json"
_API = "https://api.beatport.com/v4"

# Expected Beatport presence (True = should have many releases)
SHOULD_HAVE_RELEASES = {
    "Solid Grooves Records", "PIV Records", "Hot Creations", "Cuttin Headz",
    "Eastenderz", "CircoLoco Records", "Afterlife", "Diynamic Music",
    "Innervisions", "Kompakt", "Drumcode", "Tronic", "Soma Records",
    "Toolroom", "Fabric Records",
}


async def main():
    from playwright.async_api import async_playwright

    with open(_LABELS_FILE, encoding="utf-8") as f:
        labels = json.load(f)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Load Drumcode page (known correct ID=2027) to get token
        print("Loading Drumcode page to get anon token...")
        await page.goto(
            "https://www.beatport.com/label/drumcode/2027/releases",
            wait_until="domcontentloaded",
            timeout=25000,
        )
        await asyncio.sleep(5)

        token = None
        nd = await page.evaluate(
            "() => window.__NEXT_DATA__ ? JSON.parse(JSON.stringify(window.__NEXT_DATA__)) : null"
        )
        if nd:
            pp = (nd.get("props") or {}).get("pageProps") or {}
            token = (pp.get("anonSession") or {}).get("access_token")
            drumcode_name = pp.get("label", {}).get("name", "")
            print(f"Page label name: {drumcode_name!r}")
            print(f"Token: {'found' if token else 'NOT FOUND'}")

        if not token:
            print("ERROR: No token")
            await browser.close()
            return

        results = {}
        print(f"\n{'Label':<35} {'ID':<8} {'Count':<8} {'Status'}")
        print("-" * 70)

        for label in labels:
            name = label["name"]
            label_id = label["id"]

            url = f"{_API}/catalog/releases/?page=1&per_page=5&order_by=-release_date,id&label_id={label_id}"
            try:
                resp = await context.request.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status == 200:
                    data = await resp.json()
                    count = data.get("count", 0)
                    releases = data.get("results", [])

                    # Get sample release label name to verify
                    sample_label_names = set()
                    for r in releases:
                        for l in r.get("labels") or []:
                            if l.get("name"):
                                sample_label_names.add(l["name"])
                        if r.get("label"):
                            sample_label_names.add(r["label"].get("name", ""))

                    should_have = name in SHOULD_HAVE_RELEASES
                    if count == 0 and should_have:
                        status = "WRONG ID (0 releases)"
                    elif count == 0:
                        status = "0 releases (may be correct)"
                    elif count < 10 and should_have:
                        status = f"SUSPICIOUS ({count} releases)"
                    else:
                        status = f"OK ({count} releases)"

                    print(f"{name:<35} {label_id:<8} {count:<8} {status}")
                    if sample_label_names:
                        print(f"  {'Sample label names:'} {', '.join(list(sample_label_names)[:3])}")

                    results[name] = {"id": label_id, "count": count, "status": status}
                elif resp.status == 401:
                    print(f"{name:<35} {label_id:<8} {'401':<8} Token expired!")
                    # Refresh token from current page
                    nd2 = await page.evaluate(
                        "() => window.__NEXT_DATA__ ? JSON.parse(JSON.stringify(window.__NEXT_DATA__)) : null"
                    )
                    if nd2:
                        token = ((nd2.get("props") or {}).get("pageProps") or {}).get("anonSession", {}).get("access_token", token)
                    results[name] = {"id": label_id, "count": 0, "status": "401"}
                else:
                    print(f"{name:<35} {label_id:<8} {'err':<8} Status {resp.status}")
                    results[name] = {"id": label_id, "count": 0, "status": f"HTTP {resp.status}"}
            except Exception as e:
                print(f"{name:<35} {label_id:<8} {'err':<8} {e}")
                results[name] = {"id": label_id, "count": 0, "status": f"error: {e}"}

            await asyncio.sleep(0.3)

        # Summary
        print("\n\n=== LABELS NEEDING ID CORRECTION ===")
        for name, r in results.items():
            if "WRONG" in r["status"] or "SUSPICIOUS" in r["status"] or r["status"].startswith("HTTP") or "401" in r["status"]:
                print(f"  {name}: id={r['id']} - {r['status']}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
