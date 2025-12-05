#!/usr/bin/env python3
"""
트위터 동영상 URL을 수집하여 videos.json에 저장
Playwright + Cloudflare bypass 시도
"""

import json
import re
import asyncio
import subprocess
import sys
from datetime import datetime, timezone
from playwright.async_api import async_playwright

# twidouga.net 페이지들
TWIDOUGA_URLS = [
    ("https://twidouga.net/realtime_t.php", "jp_realtime"),
    ("https://twidouga.net/ko/realtime_t.php", "kr_realtime"),
]

# video.twimg.com URL 패턴
VIDEO_PATTERN = re.compile(
    r'https://video\.twimg\.com/(?:ext_tw_video|amplify_video)/(\d+)/(?:pu/)?vid/(?:avc1/)?\d+x\d+/[^"\'<>\s]+\.mp4(?:\?tag=\d+)?'
)

# 트윗 URL 패턴
TWEET_PATTERN = re.compile(
    r'https://(?:twitter\.com|x\.com)/[^/]+/status/(\d+)'
)


async def fetch_with_stealth(browser, url: str, source: str) -> list:
    """Stealth 모드로 twidouga.net 가져오기"""
    videos = []
    seen_ids = set()
    
    try:
        # 더 실제 브라우저 같은 설정
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            geolocation={"latitude": 35.6762, "longitude": 139.6503},
            permissions=["geolocation"],
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            }
        )
        
        page = await context.new_page()
        
        # WebDriver 속성 숨기기
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ja-JP', 'ja', 'en-US', 'en']
            });
            window.chrome = { runtime: {} };
        """)
        
        print(f"[INFO] Fetching {url} with stealth...")
        
        # 먼저 메인 페이지 방문 (쿠키 획득)
        try:
            await page.goto("https://twidouga.net/", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[WARN] Main page failed: {e}")
        
        # Cloudflare 챌린지 대기
        await page.wait_for_timeout(5000)
        
        # 실제 페이지로 이동
        response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        if response:
            print(f"[INFO] Response status: {response.status}")
        
        # 긴 대기 (Cloudflare JS 실행 시간)
        await page.wait_for_timeout(10000)
        
        # 스크롤
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 300)")
            await page.wait_for_timeout(1000)
        
        # HTML 가져오기
        html = await page.content()
        print(f"[DEBUG] HTML length: {len(html)}")
        
        # Cloudflare 챌린지 페이지인지 확인
        if "Just a moment" in html or "Checking your browser" in html:
            print("[WARN] Still on Cloudflare challenge page")
            # 스크린샷 저장
            await page.screenshot(path="cloudflare_challenge.png")
        else:
            print("[INFO] Passed Cloudflare check")
        
        # video.twimg.com URL 추출
        for match in VIDEO_PATTERN.finditer(html):
            video_url = match.group(0)
            video_id = match.group(1)
            if video_id not in seen_ids:
                seen_ids.add(video_id)
                videos.append({
                    "id": video_id,
                    "video_url": video_url,
                    "tweet_url": f"https://twitter.com/i/status/{video_id}",
                    "source": source,
                })
        
        # 트윗 URL 추출
        for match in TWEET_PATTERN.finditer(html):
            tweet_id = match.group(1)
            if tweet_id not in seen_ids:
                seen_ids.add(tweet_id)
                videos.append({
                    "id": tweet_id,
                    "video_url": None,
                    "tweet_url": f"https://twitter.com/i/status/{tweet_id}",
                    "source": source,
                })
        
        print(f"[INFO] Found {len(videos)} videos from {source}")
        await context.close()
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
    
    return videos


# yt-dlp로 Twitter/X 트렌딩 직접 가져오기 (backup)
def fetch_from_ytdlp_search() -> list:
    """yt-dlp로 Twitter 인기 영상 검색 시도"""
    videos = []
    try:
        # 한국어 트위터 영상 검색
        result = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--print", "url", 
             "ytsearch10:트위터 인기 영상 2024"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    videos.append({
                        "id": line.strip(),
                        "video_url": None,
                        "tweet_url": line.strip(),
                        "source": "ytdlp_search",
                    })
    except Exception as e:
        print(f"[WARN] yt-dlp search failed: {e}")
    
    return videos


async def main():
    all_videos = []
    seen_ids = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        
        # twidouga.net 시도 (stealth mode)
        for url, source in TWIDOUGA_URLS:
            videos = await fetch_with_stealth(browser, url, source)
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            
            if len(all_videos) >= 50:
                break
        
        await browser.close()
    
    # 결과가 없으면 로그만 남기기
    if len(all_videos) == 0:
        print("[WARN] No videos found from any source")
    
    # video_url이 있는 것 우선 정렬
    all_videos.sort(key=lambda x: (x["video_url"] is None, x["id"]), reverse=True)
    
    # 상위 100개만 유지
    all_videos = all_videos[:100]
    
    # JSON 저장
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(all_videos),
        "videos": all_videos,
    }
    
    with open("videos.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"[INFO] Saved {len(all_videos)} videos to videos.json")
    
    # URL 목록 저장
    video_urls = [v["video_url"] or v["tweet_url"] for v in all_videos]
    with open("urls.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(video_urls))
    
    print(f"[INFO] Saved {len(video_urls)} URLs to urls.txt")


if __name__ == "__main__":
    asyncio.run(main())
