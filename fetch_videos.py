#!/usr/bin/env python3
"""
트위터 동영상 URL을 수집하여 videos.json에 저장
Playwright (headless Chrome)를 사용
- Primary: twidouga.net
- Fallback: Nitter 미러들
"""

import json
import re
import asyncio
from datetime import datetime, timezone
from playwright.async_api import async_playwright

# twidouga.net 페이지들
TWIDOUGA_URLS = [
    ("https://twidouga.net/realtime_t.php", "jp_realtime"),
    ("https://twidouga.net/ko/realtime_t.php", "kr_realtime"),
    ("https://twidouga.net/ranking_t.php", "jp_ranking"),
]

# Nitter 미러 (fallback)
NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.woodland.cafe",
]

# video.twimg.com URL 패턴
VIDEO_PATTERN = re.compile(
    r'https://video\.twimg\.com/(?:ext_tw_video|amplify_video)/(\d+)/(?:pu/)?vid/(?:avc1/)?\d+x\d+/[^"\'<>\s]+\.mp4(?:\?tag=\d+)?'
)

# 트윗 URL 패턴 (twidouga.net 용)
TWEET_PATTERN = re.compile(
    r'https://(?:twitter\.com|x\.com)/[^/]+/status/(\d+)'
)

# Nitter 트윗 패턴
NITTER_TWEET_PATTERN = re.compile(
    r'href="(/[^/]+/status/\d+)"'
)


async def fetch_twidouga(browser, url: str, source: str) -> list:
    """twidouga.net에서 페이지 가져오기"""
    videos = []
    seen_ids = set()
    
    try:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="ja-JP",
        )
        page = await context.new_page()
        
        print(f"[INFO] Fetching {url}...")
        response = await page.goto(url, wait_until="networkidle", timeout=60000)
        
        if response:
            print(f"[INFO] Response status: {response.status}")
        
        # 페이지 로딩 대기 (JavaScript 렌더링)
        await page.wait_for_timeout(5000)
        
        # 스크롤 다운 (동적 로딩을 위해)
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 500)")
            await page.wait_for_timeout(500)
        
        # HTML 가져오기
        html = await page.content()
        print(f"[DEBUG] HTML length: {len(html)}")
        
        # 디버깅: 일부 HTML 출력
        if "video" in html.lower() or "twimg" in html.lower():
            print("[DEBUG] Found 'video' or 'twimg' in HTML")
        else:
            print("[DEBUG] No 'video' or 'twimg' found in HTML")
            # HTML 첫 5000자 출력
            print(f"[DEBUG] HTML preview: {html[:5000]}")
        
        # video.twimg.com 직접 URL 추출
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
        
        # 트윗 URL에서 ID 추출
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


async def fetch_nitter(browser, base_url: str) -> list:
    """Nitter 미러에서 트렌딩 가져오기"""
    videos = []
    seen_ids = set()
    
    try:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        
        # Nitter 검색: 인기 동영상
        url = f"{base_url}/search?f=videos&q=lang%3Ako&src=typed_query"
        print(f"[INFO] Trying Nitter: {url}")
        
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        if response and response.status == 200:
            html = await page.content()
            print(f"[INFO] Nitter response OK, HTML length: {len(html)}")
            
            # Nitter 트윗 링크 추출
            for match in NITTER_TWEET_PATTERN.finditer(html):
                path = match.group(1)  # /username/status/12345
                if "/status/" in path:
                    tweet_id = path.split("/status/")[-1]
                    if tweet_id.isdigit() and tweet_id not in seen_ids:
                        seen_ids.add(tweet_id)
                        videos.append({
                            "id": tweet_id,
                            "video_url": None,
                            "tweet_url": f"https://twitter.com/i/status/{tweet_id}",
                            "source": f"nitter_{base_url.split('//')[1].split('.')[0]}",
                        })
            
            print(f"[INFO] Found {len(videos)} from Nitter {base_url}")
        else:
            print(f"[WARN] Nitter returned status: {response.status if response else 'None'}")
        
        await context.close()
        
    except Exception as e:
        print(f"[ERROR] Nitter {base_url} failed: {e}")
    
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
                "--disable-gpu",
            ]
        )
        
        # 1. twidouga.net 시도
        for url, source in TWIDOUGA_URLS:
            videos = await fetch_twidouga(browser, url, source)
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            
            if len(all_videos) >= 50:
                break
        
        # 2. twidouga.net이 실패하면 Nitter fallback
        if len(all_videos) < 10:
            print("[INFO] Twidouga failed, trying Nitter mirrors...")
            for mirror in NITTER_MIRRORS:
                videos = await fetch_nitter(browser, mirror)
                for v in videos:
                    if v["id"] not in seen_ids:
                        seen_ids.add(v["id"])
                        all_videos.append(v)
                
                if len(all_videos) >= 30:
                    break
        
        await browser.close()
    
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
    
    # 간단한 URL 목록도 저장 (TwitterProvider용)
    video_urls = [v["video_url"] or v["tweet_url"] for v in all_videos]
    with open("urls.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(video_urls))
    
    print(f"[INFO] Saved {len(video_urls)} URLs to urls.txt")


if __name__ == "__main__":
    asyncio.run(main())
