#!/usr/bin/env python3
"""
TikTok 추천/트렌딩 영상 크롤러
- ProxiTok 트렌딩 페이지에서 랜덤 영상 수집
- yt-dlp로 트렌딩 해시태그 영상 수집
- 특정 계정이 아닌 무작위 트렌딩 영상만
"""

import json
import re
import subprocess
import os
from datetime import datetime, timezone
import urllib.request
import random


def get_trending_from_proxitok():
    """ProxiTok 트렌딩 페이지에서 영상 가져오기"""
    videos = []
    
    # ProxiTok 인스턴스들 (TikTok 프라이버시 프론트엔드)
    instances = [
        "https://proxitok.pabloferreiro.es",
        "https://proxitok.pussthecat.org",
        "https://tok.habedieeh.re",
        "https://proxitok.lunar.icu",
        "https://tik.hostux.net",
        "https://proxitok.privacy.qvarford.net",
        "https://tok.artemislena.eu",
    ]
    
    print("[PROXITOK] Scanning trending pages...")
    
    for instance in instances:
        try:
            # 트렌딩 페이지
            url = f"{instance}/trending"
            
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
                "Accept": "text/html,application/xhtml+xml",
            })
            
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                
                # 비디오 ID 패턴들
                # ProxiTok URL: /@username/video/1234567890
                patterns = [
                    r'/@([^/]+)/video/(\d{18,20})',  # /@user/video/id
                    r'/video/(\d{18,20})',  # /video/id
                    r'"id"\s*:\s*"(\d{18,20})"',  # JSON id
                ]
                
                found_videos = set()
                
                for pattern in patterns:
                    matches = re.findall(pattern, html)
                    for match in matches:
                        if isinstance(match, tuple):
                            # /@username/video/id 패턴
                            username, video_id = match
                            if video_id not in found_videos and len(video_id) >= 18:
                                found_videos.add(video_id)
                                videos.append({
                                    "id": video_id,
                                    "url": f"https://www.tiktok.com/@{username}/video/{video_id}",
                                    "title": "",
                                    "source": f"proxitok_trending",
                                    "username": username
                                })
                        else:
                            # video/id만 있는 패턴
                            video_id = match
                            if video_id not in found_videos and len(video_id) >= 18:
                                found_videos.add(video_id)
                                videos.append({
                                    "id": video_id,
                                    "url": f"https://www.tiktok.com/@a/video/{video_id}",
                                    "title": "",
                                    "source": "proxitok_trending"
                                })
                
                if len(found_videos) > 0:
                    print(f"  {instance}: found {len(found_videos)} trending videos")
                    break  # 하나만 성공하면 충분
                    
        except Exception as e:
            print(f"  {instance}: {str(e)[:40]}")
    
    print(f"[PROXITOK] Total: {len(videos)} trending videos")
    return videos


def get_trending_hashtags():
    """yt-dlp로 트렌딩 해시태그 영상 가져오기"""
    videos = []
    
    # 글로벌 인기 해시태그들 (지속적으로 인기 있는 것들)
    trending_tags = [
        "fyp",
        "foryou", 
        "viral",
        "trending",
        "funny",
        "comedy",
        "dance",
        "music",
        "cute",
        "satisfying",
        "challenge",
        "meme",
        "anime",
        "kpop",
        "food",
    ]
    
    # 랜덤으로 3개 태그 선택
    selected_tags = random.sample(trending_tags, min(5, len(trending_tags)))
    
    print(f"[YTDLP] Fetching from trending hashtags: {selected_tags}")
    
    for tag in selected_tags:
        try:
            url = f"https://www.tiktok.com/tag/{tag}"
            
            result = subprocess.run([
                "yt-dlp",
                "--flat-playlist",
                "--playlist-end", "10",  # 각 태그에서 10개씩
                "-j",
                "--no-warnings",
                url
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            data = json.loads(line)
                            video_url = data.get("url") or data.get("webpage_url")
                            video_id = data.get("id")
                            title = data.get("title", "")
                            uploader = data.get("uploader", "")
                            
                            if video_url and video_id:
                                # 중복 체크
                                if video_id not in [v["id"] for v in videos]:
                                    videos.append({
                                        "id": video_id,
                                        "url": video_url,
                                        "title": title[:100] if title else "",
                                        "username": uploader,
                                        "tag": tag,
                                        "source": f"ytdlp_tag_{tag}"
                                    })
                        except json.JSONDecodeError:
                            continue
                            
                print(f"  #{tag}: found {len([v for v in videos if v.get('tag') == tag])} videos")
                            
        except subprocess.TimeoutExpired:
            print(f"  #{tag}: timeout")
        except Exception as e:
            print(f"  #{tag}: {str(e)[:30]}")
    
    print(f"[YTDLP] Total from hashtags: {len(videos)} videos")
    return videos


def get_discover_page():
    """TikTok Discover 페이지에서 영상 가져오기"""
    videos = []
    
    try:
        # yt-dlp로 Discover 페이지 가져오기
        result = subprocess.run([
            "yt-dlp",
            "--flat-playlist",
            "--playlist-end", "30",
            "-j",
            "--no-warnings",
            "https://www.tiktok.com/explore"
        ], capture_output=True, text=True, timeout=90)
        
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        data = json.loads(line)
                        video_url = data.get("url") or data.get("webpage_url")
                        video_id = data.get("id")
                        title = data.get("title", "")
                        uploader = data.get("uploader", "")
                        
                        if video_url and video_id:
                            videos.append({
                                "id": video_id,
                                "url": video_url,
                                "title": title[:100] if title else "",
                                "username": uploader,
                                "source": "ytdlp_explore"
                            })
                    except json.JSONDecodeError:
                        continue
                        
            print(f"[DISCOVER] Found {len(videos)} videos from explore page")
                        
    except subprocess.TimeoutExpired:
        print("[DISCOVER] Timeout")
    except Exception as e:
        print(f"[DISCOVER] Error: {str(e)[:40]}")
    
    return videos


async def main():
    all_videos = []
    seen_ids = set()
    
    # 1. ProxiTok 트렌딩 (가장 쉬움)
    proxitok_videos = get_trending_from_proxitok()
    for v in proxitok_videos:
        if v["id"] not in seen_ids:
            seen_ids.add(v["id"])
            all_videos.append(v)
    
    # 2. yt-dlp로 트렌딩 해시태그
    if len(all_videos) < 50:
        hashtag_videos = get_trending_hashtags()
        for v in hashtag_videos:
            if v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                all_videos.append(v)
    
    # 3. Discover/Explore 페이지
    if len(all_videos) < 30:
        discover_videos = get_discover_page()
        for v in discover_videos:
            if v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                all_videos.append(v)
    
    # 결과 셔플 (랜덤화)
    random.shuffle(all_videos)
    all_videos = all_videos[:100]
    
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(all_videos),
        "platform": "tiktok",
        "type": "trending_random",  # 추천탭 무작위
        "sources_used": list(set(v.get("source", "unknown") for v in all_videos)),
        "videos": all_videos,
    }
    
    with open("tiktok.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # URL만 추출
    urls = [v["url"] for v in all_videos]
    with open("tiktok_urls.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(urls))
    
    print(f"\n=== FINAL: {len(all_videos)} TikTok trending videos ===")
    print(f"Sources: {output['sources_used']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
