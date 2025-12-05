#!/usr/bin/env python3
"""
TikTok 트렌딩 영상 크롤러
- TikTok은 Cloudflare가 없어서 크롤링이 쉬움
- yt-dlp로 트렌딩 페이지에서 영상 추출
"""

import json
import re
import subprocess
import os
from datetime import datetime, timezone

def get_trending_from_ytdlp():
    """yt-dlp로 TikTok 트렌딩 가져오기"""
    videos = []
    
    # TikTok 트렌딩/추천 URL들
    trending_urls = [
        # 트렌딩 페이지 (지역별)
        "https://www.tiktok.com/foryou",  # For You 페이지
        "https://www.tiktok.com/trending",
        # 인기 해시태그
        "https://www.tiktok.com/tag/fyp",
        "https://www.tiktok.com/tag/viral",
        "https://www.tiktok.com/tag/funny",
    ]
    
    # 인기 계정들 (최신 영상)
    popular_accounts = [
        "@bts_official_bighit",
        "@blackpinkofficial", 
        "@twice_tiktok_official",
        "@aikiplanet",
        "@bayashi.tiktok",
        "@jaboratory_0310",
        "@sagawa_fuji",
        "@mrbeast",
        "@charlidamelio",
        "@khloekardashian",
        "@addisonre",
        "@bellapoarch",
        "@zachking",
        "@willsmith",
        "@therock",
    ]
    
    print("[YTDLP] Fetching from popular accounts...")
    
    for account in popular_accounts:
        try:
            # yt-dlp로 계정의 최신 영상 3개 가져오기
            url = f"https://www.tiktok.com/{account}"
            
            result = subprocess.run([
                "yt-dlp",
                "--flat-playlist",
                "--playlist-end", "3",
                "-j",
                url
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            data = json.loads(line)
                            video_url = data.get("url") or data.get("webpage_url")
                            video_id = data.get("id")
                            title = data.get("title", "")
                            
                            if video_url and video_id:
                                videos.append({
                                    "id": video_id,
                                    "url": video_url,
                                    "title": title[:100] if title else "",
                                    "account": account,
                                    "source": "ytdlp_account"
                                })
                                print(f"  {account}: {video_id}")
                        except json.JSONDecodeError:
                            continue
                            
        except subprocess.TimeoutExpired:
            print(f"  {account}: timeout")
        except Exception as e:
            print(f"  {account}: {str(e)[:30]}")
    
    return videos


def get_trending_from_api():
    """TikTok 비공식 API로 트렌딩 가져오기"""
    import urllib.request
    
    videos = []
    
    # 인기 RSS/API 소스들
    sources = [
        # TikTok RSS (비공식)
        "https://proxitok.pabloferreiro.es/api/trending",
        # ProxiTok 인스턴스들
        "https://proxitok.pussthecat.org/trending",
        "https://proxitok.privacy.qvarford.net/trending",
    ]
    
    print("[API] Trying ProxiTok instances...")
    
    for api_url in sources:
        try:
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
            })
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                
                # TikTok 비디오 URL 패턴
                pattern = r'(?:tiktok\.com/@[\w.-]+/video/|video/)(\d+)'
                matches = re.findall(pattern, html)
                
                for video_id in matches[:30]:
                    if video_id not in [v["id"] for v in videos]:
                        videos.append({
                            "id": video_id,
                            "url": f"https://www.tiktok.com/@/video/{video_id}",
                            "title": "",
                            "source": "proxitok"
                        })
                
                if len(matches) > 0:
                    print(f"  {api_url}: found {len(matches)} videos")
                    break
                    
        except Exception as e:
            print(f"  {api_url}: {str(e)[:30]}")
    
    return videos


def get_from_scraper():
    """웹 스크래핑으로 TikTok 영상 가져오기"""
    import urllib.request
    
    videos = []
    
    # TikTok 직접 스크래핑 (headless browser 없이)
    # TikTok 메인 페이지 HTML에서 video ID 추출
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    }
    
    # 인기 태그 페이지들
    tag_urls = [
        ("https://www.tiktok.com/tag/fyp", "fyp"),
        ("https://www.tiktok.com/tag/viral", "viral"),
        ("https://www.tiktok.com/tag/funny", "funny"),
        ("https://www.tiktok.com/tag/kpop", "kpop"),
        ("https://www.tiktok.com/tag/anime", "anime"),
    ]
    
    print("[SCRAPER] Trying TikTok tag pages...")
    
    for url, tag in tag_urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                
                # video ID 패턴들
                patterns = [
                    r'"id"\s*:\s*"(\d{18,20})"',  # JSON 내 ID
                    r'/video/(\d{18,20})',  # URL 패턴
                    r'video-(\d{18,20})',  # 클래스 패턴
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, html)
                    for video_id in matches[:10]:
                        if video_id not in [v["id"] for v in videos] and len(video_id) >= 18:
                            videos.append({
                                "id": video_id,
                                "url": f"https://www.tiktok.com/@/video/{video_id}",
                                "title": "",
                                "tag": tag,
                                "source": "scraper"
                            })
                
                if len(videos) > 0:
                    print(f"  {tag}: found {len(videos)} videos so far")
                    
        except Exception as e:
            print(f"  {tag}: {str(e)[:40]}")
    
    return videos


async def main():
    all_videos = []
    seen_ids = set()
    
    # 1. yt-dlp로 인기 계정에서 가져오기
    ytdlp_videos = get_trending_from_ytdlp()
    for v in ytdlp_videos:
        if v["id"] not in seen_ids:
            seen_ids.add(v["id"])
            all_videos.append(v)
    
    print(f"\n[YTDLP] Got {len(ytdlp_videos)} videos")
    
    # 2. ProxiTok API
    if len(all_videos) < 50:
        api_videos = get_trending_from_api()
        for v in api_videos:
            if v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                all_videos.append(v)
        print(f"[API] Got {len(api_videos)} additional videos")
    
    # 3. 직접 스크래핑 (fallback)
    if len(all_videos) < 30:
        scraper_videos = get_from_scraper()
        for v in scraper_videos:
            if v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                all_videos.append(v)
        print(f"[SCRAPER] Got {len(scraper_videos)} additional videos")
    
    # 결과 저장
    all_videos = all_videos[:100]
    
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(all_videos),
        "platform": "tiktok",
        "sources_used": list(set(v.get("source", "unknown") for v in all_videos)),
        "videos": all_videos,
    }
    
    with open("tiktok.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # URL만 추출
    urls = [v["url"] for v in all_videos]
    with open("tiktok_urls.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(urls))
    
    print(f"\n=== FINAL: {len(all_videos)} TikTok videos ===")
    print(f"Sources: {output['sources_used']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
