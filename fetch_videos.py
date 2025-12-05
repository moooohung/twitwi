#!/usr/bin/env python3
"""
twidouga.net에서 실시간 트위터 동영상 URL을 수집하여 videos.json에 저장
GitHub Actions에서 15분마다 실행됨 (일본 서버에서 실행되므로 SNI 차단 없음)
"""

import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# 크롤링할 페이지들
URLS = [
    "https://twidouga.net/realtime_t.php",      # 일본 실시간
    "https://twidouga.net/ko/realtime_t.php",   # 한국 실시간
    "https://twidouga.net/ranking_t.php",       # 일본 랭킹 (24시간)
]

# video.twimg.com URL 패턴
VIDEO_PATTERN = re.compile(
    r'https://video\.twimg\.com/(?:ext_tw_video|amplify_video)/(\d+)/(?:pu/)?vid/(?:avc1/)?\d+x\d+/[^"\'<>\s]+\.mp4\?tag=\d+'
)

# 트윗 URL 패턴
TWEET_PATTERN = re.compile(
    r'https://(?:twitter\.com|x\.com)/[^/]+/status/(\d+)'
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,ko;q=0.7",
}


def fetch_page(url: str) -> str:
    """페이지 HTML 가져오기"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
        return response.text
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return ""


def extract_videos(html: str) -> list[dict]:
    """HTML에서 동영상 정보 추출"""
    videos = []
    seen_ids = set()
    
    soup = BeautifulSoup(html, 'html.parser')
    
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
            })
    
    # 트윗 URL에서 ID 추출 (video_url이 없는 경우 대비)
    for match in TWEET_PATTERN.finditer(html):
        tweet_id = match.group(1)
        if tweet_id not in seen_ids:
            seen_ids.add(tweet_id)
            videos.append({
                "id": tweet_id,
                "video_url": None,  # yt-dlp로 변환 필요
                "tweet_url": f"https://twitter.com/i/status/{tweet_id}",
            })
    
    return videos


def main():
    all_videos = []
    seen_ids = set()
    
    for url in URLS:
        print(f"[INFO] Fetching {url}...")
        html = fetch_page(url)
        
        if html:
            videos = extract_videos(html)
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            print(f"[INFO] Found {len(videos)} videos from {url}")
    
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
    main()
