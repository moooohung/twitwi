#!/usr/bin/env python3
"""
모든 가능한 소스에서 트위터/바이럴 동영상 URL 수집
"""

import json
import re
import asyncio
import subprocess
from datetime import datetime, timezone
from playwright.async_api import async_playwright
import urllib.request
import ssl

# 패턴들
VIDEO_PATTERN = re.compile(r'https://video\.twimg\.com/[^"\'<>\s]+\.mp4[^"\'<>\s]*')
TWEET_PATTERN = re.compile(r'(?:twitter\.com|x\.com)/\w+/status/(\d+)')
NITTER_TWEET_PATTERN = re.compile(r'href="(/\w+/status/(\d+))"')

# 살아있는 Nitter 미러들 (2024-2025 기준)
NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.cz",
    "https://nitter.esmailelbob.xyz",
    "https://xcancel.com",
]

async def try_request(url: str, headers: dict = None) -> str:
    """Python urllib로 요청"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if headers:
            default_headers.update(headers)
        
        req = urllib.request.Request(url, headers=default_headers)
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[REQ] Failed {url}: {str(e)[:60]}")
    return ""


async def fetch_xcancel(browser) -> list:
    """xcancel.com (Nitter 대안) 크롤링"""
    videos = []
    seen_ids = set()
    
    # 인기 계정들의 최신 동영상
    accounts = [
        "ViralHog", "NowThis", "ABC", "Reuters", "BBCWorld",
        "caboribbean", "ajaboribbean"  # 인기 동영상 계정들
    ]
    
    for account in accounts[:3]:  # 시간 절약을 위해 3개만
        try:
            url = f"https://xcancel.com/{account}/media"
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            print(f"[XCANCEL] Trying {account}...")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            
            if response and response.status == 200:
                html = await page.content()
                
                for match in NITTER_TWEET_PATTERN.finditer(html):
                    tid = match.group(2)
                    if tid not in seen_ids and tid.isdigit():
                        seen_ids.add(tid)
                        videos.append({
                            "id": tid, 
                            "video_url": None,
                            "tweet_url": f"https://twitter.com/i/status/{tid}",
                            "source": f"xcancel_{account}"
                        })
            
            await context.close()
            
            if len(videos) >= 15:
                break
                
        except Exception as e:
            print(f"[XCANCEL ERROR] {account}: {str(e)[:40]}")
    
    print(f"[XCANCEL] Found {len(videos)}")
    return videos


async def fetch_youtube_shorts_kr() -> list:
    """yt-dlp로 한국 Shorts"""
    videos = []
    
    try:
        # 한국 인기 Shorts 채널들
        channels = [
            "https://www.youtube.com/@SBSNews/shorts",
            "https://www.youtube.com/@KBSNews/shorts",
            "https://www.youtube.com/@1thek/shorts",
        ]
        
        for channel in channels:
            print(f"[YTDLP] Trying {channel}...")
            result = subprocess.run(
                ["yt-dlp", "--flat-playlist", "-j", "--playlist-end", "10", channel],
                capture_output=True, text=True, timeout=45
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        try:
                            data = json.loads(line)
                            vid = data.get("id", "")
                            title = data.get("title", "")
                            if vid:
                                videos.append({
                                    "id": vid,
                                    "video_url": f"https://www.youtube.com/shorts/{vid}",
                                    "tweet_url": f"https://www.youtube.com/shorts/{vid}",
                                    "title": title[:50] if title else "",
                                    "source": "youtube_shorts_kr"
                                })
                        except:
                            pass
            
            if len(videos) >= 20:
                break
        
        print(f"[YTDLP] Found {len(videos)}")
        
    except Exception as e:
        print(f"[YTDLP ERROR] {e}")
    
    return videos


async def fetch_tiktok_trending() -> list:
    """TikTok 트렌딩 (yt-dlp 사용)"""
    videos = []
    
    try:
        print("[TIKTOK] Trying trending...")
        
        # TikTok 인기 태그로 검색
        result = subprocess.run(
            ["yt-dlp", "--flat-playlist", "-j", "--playlist-end", "15",
             "https://www.tiktok.com/tag/viral"],
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    try:
                        data = json.loads(line)
                        vid = data.get("id", "")
                        url = data.get("url", "") or data.get("webpage_url", "")
                        if vid and url:
                            videos.append({
                                "id": vid,
                                "video_url": url,
                                "tweet_url": url,
                                "source": "tiktok_viral"
                            })
                    except:
                        pass
        
        print(f"[TIKTOK] Found {len(videos)}")
        
    except Exception as e:
        print(f"[TIKTOK ERROR] {e}")
    
    return videos


async def fetch_twitter_popular_accounts(browser) -> list:
    """인기 트위터 계정 직접 크롤링 (syndication API)"""
    videos = []
    seen_ids = set()
    
    # Twitter syndication API (공개 트윗용)
    popular_tweets = [
        "1864702143251640000",  # 인기 트윗 ID 예시들
        "1864500000000000000",
    ]
    
    # Twitter oEmbed API 시도
    for tweet_id in popular_tweets[:5]:
        try:
            url = f"https://publish.twitter.com/oembed?url=https://twitter.com/i/status/{tweet_id}"
            html = await try_request(url)
            if html and "html" in html:
                videos.append({
                    "id": tweet_id,
                    "video_url": None,
                    "tweet_url": f"https://twitter.com/i/status/{tweet_id}",
                    "source": "twitter_oembed"
                })
        except:
            pass
    
    return videos


async def fetch_from_github_lists() -> list:
    """GitHub에 저장된 트렌딩 리스트들"""
    videos = []
    
    # 다른 사람들이 만든 트렌딩 리스트 활용
    lists = [
        "https://raw.githubusercontent.com/PineAppleHollyday1/twitter-realtime-100-twidouga.net-/master/realtime_t.php",
    ]
    
    for url in lists:
        try:
            html = await try_request(url)
            if html:
                for match in TWEET_PATTERN.finditer(html):
                    tid = match.group(1)
                    if tid.isdigit():
                        videos.append({
                            "id": tid,
                            "video_url": None,
                            "tweet_url": f"https://twitter.com/i/status/{tid}",
                            "source": "github_list"
                        })
                
                for match in VIDEO_PATTERN.finditer(html):
                    videos.append({
                        "id": hash(match.group(0)) % 10000000000,
                        "video_url": match.group(0),
                        "tweet_url": match.group(0),
                        "source": "github_list_direct"
                    })
                    
        except Exception as e:
            print(f"[GITHUB LIST] {e}")
    
    print(f"[GITHUB LIST] Found {len(videos)}")
    return videos


async def main():
    all_videos = []
    seen_ids = set()
    
    def add_videos(new_videos):
        for v in new_videos:
            vid = str(v["id"])
            if vid not in seen_ids:
                seen_ids.add(vid)
                all_videos.append(v)
    
    # Phase 0: GitHub 리스트 (캐시된 데이터)
    print("\n=== Phase 0: GitHub Lists ===")
    videos = await fetch_from_github_lists()
    add_videos(videos)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        
        # Phase 1: xcancel.com (Nitter 대안)
        if len(all_videos) < 30:
            print("\n=== Phase 1: xcancel.com ===")
            videos = await fetch_xcancel(browser)
            add_videos(videos)
        
        await browser.close()
    
    # Phase 2: YouTube Shorts
    if len(all_videos) < 20:
        print("\n=== Phase 2: YouTube Shorts ===")
        videos = await fetch_youtube_shorts_kr()
        add_videos(videos)
    
    # Phase 3: TikTok
    if len(all_videos) < 15:
        print("\n=== Phase 3: TikTok ===")
        videos = await fetch_tiktok_trending()
        add_videos(videos)
    
    # 정렬
    all_videos.sort(key=lambda x: (
        x["source"] == "github_list_direct",  # video_url 있는 것 우선
        x["source"] == "github_list",
        x["source"].startswith("youtube"),
    ), reverse=True)
    
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
