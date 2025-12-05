#!/usr/bin/env python3
"""
twidouga.net에서 실시간 트위터 동영상 URL을 수집하여 videos.json에 저장
Playwright (headless Chrome)를 사용하여 Cloudflare 우회
"""

import json
import re
import asyncio
from datetime import datetime, timezone
from playwright.async_api import async_playwright

# 크롤링할 페이지들
URLS = [
    ("https://twidouga.net/realtime_t.php", "jp_realtime"),
    ("https://twidouga.net/ko/realtime_t.php", "kr_realtime"),
    ("https://twidouga.net/ranking_t.php", "jp_ranking"),
]

# video.twimg.com URL 패턴
VIDEO_PATTERN = re.compile(
    r'https://video\.twimg\.com/(?:ext_tw_video|amplify_video)/(\d+)/(?:pu/)?vid/(?:avc1/)?\d+x\d+/[^"\'<>\s]+\.mp4(?:\?tag=\d+)?'
)

# 트윗 URL 패턴
TWEET_PATTERN = re.compile(
    r'https://(?:twitter\.com|x\.com)/[^/]+/status/(\d+)'
)


async def fetch_page(browser, url: str, source: str) -> list:
    """Playwright로 페이지 가져오기"""
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
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # 페이지 로딩 대기
        await page.wait_for_timeout(3000)
        
        # HTML 가져오기
        html = await page.content()
        
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
        
        # 트윗 URL에서 ID 추출 (video_url이 없는 경우 대비)
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
        
        for url, source in URLS:
            videos = await fetch_page(browser, url, source)
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            
            # 충분히 모았으면 중단
            if len(all_videos) >= 80:
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
