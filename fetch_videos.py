#!/usr/bin/env python3
"""
twidouga.net 우회 - 다중 프록시/Tor 전략
"""

import json
import re
import asyncio
import time
import subprocess
import os
from datetime import datetime, timezone

# === 패턴들 ===
VIDEO_PATTERN = re.compile(r'https://video\.twimg\.com/[^"\'<>\s]+\.mp4[^"\'<>\s]*')
TWEET_PATTERN = re.compile(r'(?:twitter\.com|x\.com)/\w+/status/(\d+)')


def extract_videos(html: str, source: str) -> list:
    videos = []
    seen_ids = set()
    
    for match in VIDEO_PATTERN.finditer(html):
        url = match.group(0)
        vid = hash(url) % 10000000000
        if vid not in seen_ids:
            seen_ids.add(vid)
            videos.append({"id": str(vid), "video_url": url, "tweet_url": url, "source": source})
    
    for match in TWEET_PATTERN.finditer(html):
        tid = match.group(1)
        if tid not in seen_ids:
            seen_ids.add(tid)
            videos.append({"id": tid, "video_url": None, "tweet_url": f"https://twitter.com/i/status/{tid}", "source": source})
    
    return videos


# === 방법 1: Tor 네트워크 사용 ===
async def try_tor_request(url: str) -> str:
    """Tor SOCKS5 프록시를 통한 요청"""
    try:
        import requests
        
        print(f"[TOR] Trying {url}...")
        
        # Tor 설치 및 시작
        subprocess.run(["apt-get", "update", "-qq"], capture_output=True)
        subprocess.run(["apt-get", "install", "-y", "-qq", "tor"], capture_output=True)
        subprocess.run(["service", "tor", "start"], capture_output=True)
        time.sleep(5)
        
        proxies = {
            'http': 'socks5h://127.0.0.1:9050',
            'https': 'socks5h://127.0.0.1:9050'
        }
        
        response = requests.get(url, proxies=proxies, timeout=60, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        })
        
        if response.status_code == 200:
            print(f"[TOR] Success! Got {len(response.text)} bytes")
            return response.text
        else:
            print(f"[TOR] Status {response.status_code}")
            
    except Exception as e:
        print(f"[TOR] Error: {e}")
    
    return ""


# === 방법 2: 무료 프록시 서비스들 ===
FREE_PROXIES = [
    # scrape.do 무료 API
    "https://api.scrape.do/?token=free&url=",
    # scrapingbee 무료 (100 크레딧)
    # ProxyScrape
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
]

async def try_proxy_service(url: str) -> str:
    """무료 프록시 서비스 사용"""
    try:
        import urllib.request
        import urllib.parse
        
        # 방법 1: scrape.do (무료 API)
        encoded_url = urllib.parse.quote(url, safe='')
        api_url = f"https://api.scrape.do/?url={encoded_url}"
        
        print(f"[PROXY] Trying scrape.do...")
        
        req = urllib.request.Request(api_url, headers={
            "User-Agent": "Mozilla/5.0"
        })
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            if "twimg.com" in html or "twitter.com" in html:
                print(f"[PROXY] scrape.do success!")
                return html
                
    except Exception as e:
        print(f"[PROXY] Error: {e}")
    
    return ""


# === 방법 3: Cloudflare Workers 프록시 ===
async def try_cf_worker_proxy(url: str) -> str:
    """Cloudflare Workers를 프록시로 사용 (별도 설정 필요)"""
    # 이 방법은 사용자가 직접 CF Worker를 배포해야 함
    return ""


# === 방법 4: curl_cffi with rotating user agents ===
def try_curl_rotating(url: str) -> str:
    """curl_cffi with rotating impersonation"""
    try:
        from curl_cffi import requests as cffi_requests
        
        print(f"[CURL_ROTATE] Trying {url}...")
        
        # 다양한 브라우저 fingerprint 시도
        browsers = ["chrome110", "chrome116", "chrome120", "edge101", "safari15_3"]
        
        for browser in browsers:
            try:
                session = cffi_requests.Session(impersonate=browser)
                
                # 먼저 메인 페이지
                resp1 = session.get("https://twidouga.net/", timeout=30)
                time.sleep(3)
                
                # 실제 페이지
                response = session.get(url, timeout=60)
                
                if response.status_code == 200:
                    if "twimg.com" in response.text or "twitter.com" in response.text:
                        print(f"[CURL_ROTATE] Success with {browser}!")
                        return response.text
                else:
                    print(f"[CURL_ROTATE] {browser}: {response.status_code}")
                    
            except Exception as e:
                print(f"[CURL_ROTATE] {browser} failed: {str(e)[:40]}")
                
    except Exception as e:
        print(f"[CURL_ROTATE] Error: {e}")
    
    return ""


# === 방법 5: Playwright with VPN-like proxy ===
async def try_playwright_with_proxy(url: str) -> str:
    """Playwright with free proxy"""
    try:
        from playwright.async_api import async_playwright
        
        # 무료 프록시 목록 (작동하는 것 찾기)
        proxies = [
            # 일본 프록시 (twidouga.net이 일본 사이트)
            {"server": "http://jp.proxy.freeproxy.io:8080"},
            {"server": "http://103.155.217.1:41317"},
        ]
        
        print(f"[PLAYWRIGHT_PROXY] Trying {url}...")
        
        async with async_playwright() as p:
            for proxy_config in proxies:
                try:
                    browser = await p.chromium.launch(
                        headless=True,
                        proxy=proxy_config,
                        args=['--no-sandbox']
                    )
                    
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                    )
                    
                    page = await context.new_page()
                    
                    await page.goto(url, timeout=60000)
                    await page.wait_for_timeout(5000)
                    
                    html = await page.content()
                    await browser.close()
                    
                    if "twimg.com" in html or "twitter.com" in html:
                        print(f"[PLAYWRIGHT_PROXY] Success with proxy!")
                        return html
                        
                except Exception as e:
                    print(f"[PLAYWRIGHT_PROXY] Proxy failed: {str(e)[:40]}")
                    
    except Exception as e:
        print(f"[PLAYWRIGHT_PROXY] Error: {e}")
    
    return ""


# === GitHub 캐시 (fallback) ===
async def fetch_github_cache() -> list:
    """GitHub에 있는 기존 캐시 사용"""
    try:
        import urllib.request
        
        url = "https://raw.githubusercontent.com/PineAppleHollyday1/twitter-realtime-100-twidouga.net-/main/realtime_t.php"
        
        print("[GITHUB_CACHE] Fetching cached data...")
        
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            videos = extract_videos(html, "github_cache")
            print(f"[GITHUB_CACHE] Found {len(videos)} cached videos")
            return videos
            
    except Exception as e:
        print(f"[GITHUB_CACHE] Error: {e}")
    
    return []


async def main():
    urls = [
        ("https://twidouga.net/realtime_t.php", "twidouga_jp"),
        ("https://twidouga.net/ko/realtime_t.php", "twidouga_kr"),
    ]
    
    all_videos = []
    seen_ids = set()
    
    for url, source in urls:
        html = ""
        
        # 방법 1: Tor
        html = await try_tor_request(url)
        if html and ("twimg.com" in html or "twitter.com" in html):
            videos = extract_videos(html, source + "_tor")
            print(f"[SUCCESS] Tor found {len(videos)} videos!")
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            continue
        
        # 방법 2: 프록시 서비스
        html = await try_proxy_service(url)
        if html and ("twimg.com" in html or "twitter.com" in html):
            videos = extract_videos(html, source + "_proxy")
            print(f"[SUCCESS] Proxy found {len(videos)} videos!")
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            continue
        
        # 방법 3: curl rotating
        html = try_curl_rotating(url)
        if html and ("twimg.com" in html or "twitter.com" in html):
            videos = extract_videos(html, source + "_curl")
            print(f"[SUCCESS] curl found {len(videos)} videos!")
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            continue
        
        # 방법 4: Playwright with proxy
        html = await try_playwright_with_proxy(url)
        if html and ("twimg.com" in html or "twitter.com" in html):
            videos = extract_videos(html, source + "_playwright_proxy")
            print(f"[SUCCESS] Playwright proxy found {len(videos)} videos!")
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
    
    # 실패 시 GitHub 캐시 사용
    if len(all_videos) == 0:
        print("\n[FALLBACK] All methods failed, using GitHub cache...")
        all_videos = await fetch_github_cache()
    
    # 결과 저장
    all_videos.sort(key=lambda x: x["video_url"] is None)
    all_videos = all_videos[:100]
    
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
    
    print(f"\n=== FINAL: {len(all_videos)} videos ===")
    print(f"Sources: {output['sources_used']}")


if __name__ == "__main__":
    asyncio.run(main())
