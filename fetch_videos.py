#!/usr/bin/env python3
"""
모든 가능한 소스에서 트위터/바이럴 동영상 URL 수집
다중 fallback 전략
"""

import json
import re
import asyncio
import subprocess
from datetime import datetime, timezone
from playwright.async_api import async_playwright
import urllib.request
import ssl

# === 소스 1: twidouga.net (Stealth) ===
TWIDOUGA_URLS = [
    ("https://twidouga.net/realtime_t.php", "twidouga_jp"),
    ("https://twidouga.net/ko/realtime_t.php", "twidouga_kr"),
]

# === 소스 2: 대안 트렌딩 사이트들 ===
ALT_SOURCES = [
    # twittrend.jp - 일본 트위터 트렌드
    ("https://twittrend.jp/", "twittrend_jp"),
    # getdaytrends - 글로벌 트렌드
    ("https://getdaytrends.com/south-korea/", "daytrends_kr"),
    # trends24 - 실시간 트렌드
    ("https://trends24.in/south-korea/", "trends24_kr"),
]

# === 소스 3: Nitter 미러들 (살아있는 것 찾기) ===
NITTER_MIRRORS = [
    "https://nitter.net",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.unixfox.eu",
    "https://nitter.fdn.fr",
    "https://nitter.it",
    "https://nitter.namazso.eu",
    "https://nitter.nixnet.services",
]

# 패턴들
VIDEO_PATTERN = re.compile(
    r'https://video\.twimg\.com/(?:ext_tw_video|amplify_video)/(\d+)/(?:pu/)?vid/(?:avc1/)?\d+x\d+/[^"\'<>\s]+\.mp4(?:\?tag=\d+)?'
)
TWEET_PATTERN = re.compile(r'(?:twitter\.com|x\.com)/[^/]+/status/(\d+)')
NITTER_TWEET_PATTERN = re.compile(r'href="(/[^/]+/status/(\d+))"')
# YouTube Shorts 패턴 (fallback용)
SHORTS_PATTERN = re.compile(r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})')


async def try_curl_direct(url: str) -> str:
    """curl로 직접 시도 (Playwright 우회)"""
    try:
        result = subprocess.run(
            ["curl", "-sL", "-A", 
             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
             "--max-time", "30",
             url],
            capture_output=True, text=True, timeout=35
        )
        if result.returncode == 0:
            return result.stdout
    except Exception as e:
        print(f"[CURL] Failed: {e}")
    return ""


async def try_python_request(url: str) -> str:
    """Python urllib로 시도"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        })
        
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[URLLIB] Failed {url}: {e}")
    return ""


async def fetch_twidouga_stealth(browser, url: str, source: str) -> list:
    """Stealth 모드로 twidouga.net"""
    videos = []
    seen_ids = set()
    
    try:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            }
        )
        
        page = await context.new_page()
        await page.add_init_script("""
            delete navigator.__proto__.webdriver;
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja'] });
            window.chrome = { runtime: {} };
        """)
        
        print(f"[STEALTH] Trying {url}...")
        response = await page.goto(url, wait_until="networkidle", timeout=45000)
        
        if response and response.status == 200:
            await page.wait_for_timeout(5000)
            html = await page.content()
            
            for match in VIDEO_PATTERN.finditer(html):
                vid = match.group(1)
                if vid not in seen_ids:
                    seen_ids.add(vid)
                    videos.append({"id": vid, "video_url": match.group(0), 
                                   "tweet_url": f"https://twitter.com/i/status/{vid}", "source": source})
            
            for match in TWEET_PATTERN.finditer(html):
                tid = match.group(1)
                if tid not in seen_ids:
                    seen_ids.add(tid)
                    videos.append({"id": tid, "video_url": None,
                                   "tweet_url": f"https://twitter.com/i/status/{tid}", "source": source})
        
        await context.close()
        print(f"[STEALTH] Found {len(videos)} from {source}")
        
    except Exception as e:
        print(f"[STEALTH ERROR] {url}: {e}")
    
    return videos


async def fetch_nitter_alive(browser) -> list:
    """살아있는 Nitter 미러 찾아서 크롤링"""
    videos = []
    seen_ids = set()
    
    for mirror in NITTER_MIRRORS:
        try:
            # 검색 페이지 (인기 동영상)
            url = f"{mirror}/search?f=videos&q=filter%3Avideos+lang%3Ako"
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            print(f"[NITTER] Trying {mirror}...")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            
            if response and response.status == 200:
                html = await page.content()
                
                for match in NITTER_TWEET_PATTERN.finditer(html):
                    tid = match.group(2)
                    if tid not in seen_ids:
                        seen_ids.add(tid)
                        videos.append({"id": tid, "video_url": None,
                                       "tweet_url": f"https://twitter.com/i/status/{tid}", 
                                       "source": f"nitter_{mirror.split('//')[1].split('.')[0]}"})
                
                print(f"[NITTER] Found {len(videos)} from {mirror}")
                await context.close()
                
                if len(videos) >= 20:
                    return videos
            else:
                await context.close()
                
        except Exception as e:
            print(f"[NITTER ERROR] {mirror}: {str(e)[:50]}")
    
    return videos


async def fetch_alt_sources(browser) -> list:
    """대안 트렌딩 사이트들"""
    videos = []
    seen_ids = set()
    
    for url, source in ALT_SOURCES:
        try:
            # 먼저 curl 시도
            html = await try_curl_direct(url)
            
            if not html or len(html) < 1000:
                # Playwright로 시도
                context = await browser.new_context()
                page = await context.new_page()
                print(f"[ALT] Playwright trying {url}...")
                response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if response and response.status == 200:
                    html = await page.content()
                await context.close()
            
            if html:
                print(f"[ALT] Got {len(html)} bytes from {source}")
                
                # 트윗 URL 추출
                for match in TWEET_PATTERN.finditer(html):
                    tid = match.group(1)
                    if tid not in seen_ids:
                        seen_ids.add(tid)
                        videos.append({"id": tid, "video_url": None,
                                       "tweet_url": f"https://twitter.com/i/status/{tid}", "source": source})
                
                # video.twimg.com URL 추출
                for match in VIDEO_PATTERN.finditer(html):
                    vid = match.group(1)
                    if vid not in seen_ids:
                        seen_ids.add(vid)
                        videos.append({"id": vid, "video_url": match.group(0),
                                       "tweet_url": f"https://twitter.com/i/status/{vid}", "source": source})
            
            if len(videos) >= 30:
                break
                
        except Exception as e:
            print(f"[ALT ERROR] {url}: {str(e)[:50]}")
    
    print(f"[ALT] Total found: {len(videos)}")
    return videos


async def fetch_youtube_trending_shorts() -> list:
    """YouTube 한국 인기 Shorts (fallback)"""
    videos = []
    
    try:
        # yt-dlp로 한국 인기 Shorts
        result = subprocess.run(
            ["yt-dlp", "--flat-playlist", "-j", 
             "https://www.youtube.com/feed/shorts"],
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    try:
                        data = json.loads(line)
                        vid = data.get("id", "")
                        if vid:
                            videos.append({
                                "id": vid,
                                "video_url": f"https://www.youtube.com/shorts/{vid}",
                                "tweet_url": f"https://www.youtube.com/shorts/{vid}",
                                "source": "youtube_shorts"
                            })
                    except:
                        pass
        
        print(f"[YTSHORTS] Found {len(videos)}")
        
    except Exception as e:
        print(f"[YTSHORTS ERROR] {e}")
    
    return videos[:30]


async def fetch_reddit_viral() -> list:
    """Reddit 바이럴 영상 (완전 fallback)"""
    videos = []
    
    try:
        # Reddit JSON API (no auth needed)
        html = await try_python_request("https://www.reddit.com/r/TikTokCringe/hot.json?limit=50")
        
        if html:
            data = json.loads(html)
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                url = post.get("url", "")
                vid = post.get("id", "")
                
                if "v.redd.it" in url or post.get("is_video"):
                    videos.append({
                        "id": vid,
                        "video_url": url,
                        "tweet_url": f"https://reddit.com{post.get('permalink', '')}",
                        "source": "reddit_viral"
                    })
        
        print(f"[REDDIT] Found {len(videos)}")
        
    except Exception as e:
        print(f"[REDDIT ERROR] {e}")
    
    return videos[:20]


async def main():
    all_videos = []
    seen_ids = set()
    
    def add_videos(new_videos):
        for v in new_videos:
            if v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                all_videos.append(v)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1920,1080",
            ]
        )
        
        # 1. twidouga.net (Stealth)
        print("\n=== Phase 1: twidouga.net ===")
        for url, source in TWIDOUGA_URLS:
            videos = await fetch_twidouga_stealth(browser, url, source)
            add_videos(videos)
            if len(all_videos) >= 50:
                break
        
        # 2. Nitter 미러들
        if len(all_videos) < 20:
            print("\n=== Phase 2: Nitter Mirrors ===")
            videos = await fetch_nitter_alive(browser)
            add_videos(videos)
        
        # 3. 대안 트렌딩 사이트들
        if len(all_videos) < 20:
            print("\n=== Phase 3: Alt Sources ===")
            videos = await fetch_alt_sources(browser)
            add_videos(videos)
        
        await browser.close()
    
    # 4. YouTube Shorts (fallback)
    if len(all_videos) < 10:
        print("\n=== Phase 4: YouTube Shorts ===")
        videos = await fetch_youtube_trending_shorts()
        add_videos(videos)
    
    # 5. Reddit (최후의 수단)
    if len(all_videos) < 5:
        print("\n=== Phase 5: Reddit Viral ===")
        videos = await fetch_reddit_viral()
        add_videos(videos)
    
    # 정렬 (video_url 있는 것 우선)
    all_videos.sort(key=lambda x: (x["video_url"] is None, x["source"] != "twidouga_jp", x["id"]), reverse=True)
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
    
    print(f"\n=== RESULT: {len(all_videos)} videos saved ===")
    print(f"Sources: {output['sources_used']}")


if __name__ == "__main__":
    asyncio.run(main())
