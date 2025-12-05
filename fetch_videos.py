#!/usr/bin/env python3
"""
twidouga.net Cloudflare 우회 - 다중 전략
1. cloudscraper - Cloudflare JS Challenge 자동 해결
2. curl_cffi - Chrome TLS fingerprint 모방
3. DrissionPage - Stealth Chromium
"""

import json
import re
import asyncio
from datetime import datetime, timezone

# === 방법 1: cloudscraper ===
def try_cloudscraper(url: str) -> str:
    """cloudscraper로 Cloudflare JS Challenge 우회"""
    try:
        import cloudscraper
        
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True,
            },
            delay=10,  # JS challenge 대기 시간
        )
        
        print(f"[CLOUDSCRAPER] Trying {url}...")
        response = scraper.get(url, timeout=60)
        
        if response.status_code == 200:
            print(f"[CLOUDSCRAPER] Success! Got {len(response.text)} bytes")
            return response.text
        else:
            print(f"[CLOUDSCRAPER] Status {response.status_code}")
            
    except Exception as e:
        print(f"[CLOUDSCRAPER] Error: {e}")
    
    return ""


# === 방법 2: curl_cffi (Chrome impersonate) ===
def try_curl_cffi(url: str) -> str:
    """curl_cffi로 Chrome TLS fingerprint 모방"""
    try:
        from curl_cffi import requests as cffi_requests
        
        print(f"[CURL_CFFI] Trying {url}...")
        response = cffi_requests.get(
            url,
            impersonate="chrome120",
            timeout=60,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ja-JP,ja;q=0.9",
            }
        )
        
        if response.status_code == 200:
            print(f"[CURL_CFFI] Success! Got {len(response.text)} bytes")
            return response.text
        else:
            print(f"[CURL_CFFI] Status {response.status_code}")
            
    except Exception as e:
        print(f"[CURL_CFFI] Error: {e}")
    
    return ""


# === 방법 3: DrissionPage (Stealth Chromium) ===
def try_drissionpage(url: str) -> str:
    """DrissionPage로 Stealth Chromium 브라우저 사용"""
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
        
        print(f"[DRISSIONPAGE] Trying {url}...")
        
        options = ChromiumOptions()
        options.headless()
        options.set_argument('--no-sandbox')
        options.set_argument('--disable-dev-shm-usage')
        options.set_argument('--disable-blink-features=AutomationControlled')
        
        page = ChromiumPage(options)
        page.get(url)
        
        # Cloudflare 챌린지 대기
        import time
        time.sleep(10)
        
        html = page.html
        page.quit()
        
        if html and len(html) > 1000:
            print(f"[DRISSIONPAGE] Success! Got {len(html)} bytes")
            return html
            
    except Exception as e:
        print(f"[DRISSIONPAGE] Error: {e}")
    
    return ""


# === 방법 4: Playwright with stealth ===
async def try_playwright_stealth(url: str) -> str:
    """Playwright + playwright-stealth로 우회"""
    try:
        from playwright.async_api import async_playwright
        from playwright_stealth import stealth_async
        
        print(f"[PLAYWRIGHT_STEALTH] Trying {url}...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
            )
            
            page = await context.new_page()
            
            # Stealth 적용
            await stealth_async(page)
            
            # 먼저 메인 페이지로 쿠키 획득
            await page.goto("https://twidouga.net/", wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(8000)
            
            # 실제 페이지로 이동
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(5000)
            
            html = await page.content()
            await browser.close()
            
            if html and "twimg.com" in html.lower():
                print(f"[PLAYWRIGHT_STEALTH] Success! Got {len(html)} bytes with video URLs!")
                return html
            elif html and len(html) > 5000:
                print(f"[PLAYWRIGHT_STEALTH] Got HTML but no videos. Checking...")
                if "Just a moment" in html or "Checking your browser" in html:
                    print("[PLAYWRIGHT_STEALTH] Still on Cloudflare challenge page")
                else:
                    print(f"[PLAYWRIGHT_STEALTH] Got content: {len(html)} bytes")
                    return html
                    
    except Exception as e:
        print(f"[PLAYWRIGHT_STEALTH] Error: {e}")
    
    return ""


# === 패턴들 ===
VIDEO_PATTERN = re.compile(r'https://video\.twimg\.com/[^"\'<>\s]+\.mp4[^"\'<>\s]*')
TWEET_PATTERN = re.compile(r'(?:twitter\.com|x\.com)/\w+/status/(\d+)')


def extract_videos(html: str, source: str) -> list:
    """HTML에서 동영상 URL 추출"""
    videos = []
    seen_ids = set()
    
    # video.twimg.com 직접 URL
    for match in VIDEO_PATTERN.finditer(html):
        url = match.group(0)
        vid = hash(url) % 10000000000
        if vid not in seen_ids:
            seen_ids.add(vid)
            videos.append({
                "id": str(vid),
                "video_url": url,
                "tweet_url": url,
                "source": source
            })
    
    # 트윗 URL
    for match in TWEET_PATTERN.finditer(html):
        tid = match.group(1)
        if tid not in seen_ids:
            seen_ids.add(tid)
            videos.append({
                "id": tid,
                "video_url": None,
                "tweet_url": f"https://twitter.com/i/status/{tid}",
                "source": source
            })
    
    return videos


async def main():
    urls = [
        ("https://twidouga.net/realtime_t.php", "twidouga_jp"),
        ("https://twidouga.net/ko/realtime_t.php", "twidouga_kr"),
    ]
    
    all_videos = []
    seen_ids = set()
    
    for url, source in urls:
        html = ""
        
        # 방법 1: cloudscraper
        html = try_cloudscraper(url)
        if html and ("twimg.com" in html or "twitter.com" in html):
            videos = extract_videos(html, source + "_cloudscraper")
            print(f"[RESULT] cloudscraper found {len(videos)} videos")
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            if len(all_videos) >= 30:
                break
            continue
        
        # 방법 2: curl_cffi
        html = try_curl_cffi(url)
        if html and ("twimg.com" in html or "twitter.com" in html):
            videos = extract_videos(html, source + "_curl_cffi")
            print(f"[RESULT] curl_cffi found {len(videos)} videos")
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            if len(all_videos) >= 30:
                break
            continue
        
        # 방법 3: DrissionPage
        html = try_drissionpage(url)
        if html and ("twimg.com" in html or "twitter.com" in html):
            videos = extract_videos(html, source + "_drissionpage")
            print(f"[RESULT] DrissionPage found {len(videos)} videos")
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            if len(all_videos) >= 30:
                break
            continue
        
        # 방법 4: Playwright stealth
        html = await try_playwright_stealth(url)
        if html and ("twimg.com" in html or "twitter.com" in html):
            videos = extract_videos(html, source + "_playwright_stealth")
            print(f"[RESULT] Playwright stealth found {len(videos)} videos")
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
    
    # 결과 정렬
    all_videos.sort(key=lambda x: x["video_url"] is None)
    all_videos = all_videos[:100]
    
    # 저장
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(all_videos),
        "sources_used": list(set(v["source"] for v in all_videos)),
        "videos": all_videos,
    }
    
    with open("videos.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    video_urls = [v["video_url"] or v["tweet_url"] for v in all_videos]
    with open("urls.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(video_urls))
    
    print(f"\n=== FINAL RESULT: {len(all_videos)} videos ===")
    print(f"Sources: {output['sources_used']}")


if __name__ == "__main__":
    asyncio.run(main())
