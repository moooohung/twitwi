#!/usr/bin/env python3
"""
twidouga.net 우회 - FlareSolverr + Nitter + GitHub 캐시
"""

import json
import re
import asyncio
import time
import os
from datetime import datetime, timezone

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


async def try_flaresolverr(url: str) -> str:
    """FlareSolverr 서비스 호출 (이미 Docker로 실행 중)"""
    try:
        import urllib.request
        
        print(f"[FLARESOLVERR] Requesting {url}...")
        
        payload = json.dumps({
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 60000
        }).encode('utf-8')
        
        req = urllib.request.Request(
            "http://localhost:8191/v1",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if result.get("status") == "ok":
                html = result.get("solution", {}).get("response", "")
                print(f"[FLARESOLVERR] Success! Got {len(html)} bytes")
                
                # 결과가 유효한지 확인
                if "twimg.com" in html or "twitter.com" in html or "x.com" in html:
                    return html
                else:
                    print(f"[FLARESOLVERR] Got response but no twitter content")
                    print(f"[FLARESOLVERR] First 500 chars: {html[:500]}")
            else:
                print(f"[FLARESOLVERR] Failed: {result.get('message', 'Unknown error')}")
                
    except Exception as e:
        print(f"[FLARESOLVERR] Error: {e}")
    
    return ""


async def try_nitter_instances() -> list:
    """Nitter 인스턴스에서 일본어 비디오 트윗 가져오기"""
    import urllib.request
    
    videos = []
    
    nitter_instances = [
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
        "https://nitter.1d4.us",
        "https://xcancel.com",
        "https://nitter.lucabased.xyz",
    ]
    
    print(f"[NITTER] Scanning {len(nitter_instances)} instances...")
    
    for instance in nitter_instances:
        try:
            # 일본어 비디오 검색
            search_url = f"{instance}/search?f=videos&q=lang%3Aja"
            
            req = urllib.request.Request(search_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html",
                "Accept-Language": "ja,en;q=0.9"
            })
            
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                
                # Nitter URL 형식: /username/status/id
                tweet_matches = re.findall(r'href="(/[^/]+/status/\d+)"', html)
                
                for match in tweet_matches[:30]:
                    tweet_id = match.split('/')[-1]
                    if tweet_id not in [v["id"] for v in videos]:
                        # username 추출
                        username = match.split('/')[1]
                        videos.append({
                            "id": tweet_id,
                            "video_url": None,
                            "tweet_url": f"https://twitter.com/{username}/status/{tweet_id}",
                            "source": f"nitter_{instance.split('//')[1].split('/')[0]}"
                        })
                
                if len(tweet_matches) > 0:
                    print(f"[NITTER] {instance}: found {len(tweet_matches)} tweets (total: {len(videos)})")
                    break  # 하나만 성공하면 충분
                    
        except Exception as e:
            print(f"[NITTER] {instance} failed: {str(e)[:40]}")
            continue
    
    print(f"[NITTER] Total: {len(videos)} videos")
    return videos


async def fetch_github_sources() -> list:
    """GitHub에 있는 캐시 데이터"""
    import urllib.request
    
    videos = []
    
    github_sources = [
        ("https://raw.githubusercontent.com/PineAppleHollyday1/twitter-realtime-100-twidouga.net-/main/realtime_t.php", "github_pineapple"),
    ]
    
    print(f"[GITHUB] Fetching from {len(github_sources)} sources...")
    
    for url, source in github_sources:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                found = extract_videos(html, source)
                print(f"[GITHUB] {source}: {len(found)} videos")
                videos.extend(found)
        except Exception as e:
            print(f"[GITHUB] {source} failed: {str(e)[:30]}")
    
    return videos


async def main():
    all_videos = []
    seen_ids = set()
    
    target_urls = [
        ("https://twidouga.net/realtime_t.php", "twidouga_jp"),
        ("https://twidouga.net/ko/realtime_t.php", "twidouga_kr"),
    ]
    
    # === 1. FlareSolverr 시도 ===
    for url, source in target_urls:
        html = await try_flaresolverr(url)
        if html:
            vids = extract_videos(html, f"{source}_flaresolverr")
            for v in vids:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            if len(vids) > 0:
                print(f"[SUCCESS] FlareSolverr got {len(vids)} videos from {source}!")
                break
    
    # === 2. Nitter 인스턴스 시도 ===
    if len(all_videos) == 0:
        nitter_videos = await try_nitter_instances()
        for v in nitter_videos:
            if v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                all_videos.append(v)
        if len(nitter_videos) > 0:
            print(f"[SUCCESS] Nitter got {len(nitter_videos)} videos!")
    
    # === 3. GitHub 캐시 (항상 추가) ===
    github_videos = await fetch_github_sources()
    for v in github_videos:
        if v["id"] not in seen_ids:
            seen_ids.add(v["id"])
            all_videos.append(v)
    
    # === 결과 저장 ===
    all_videos.sort(key=lambda x: (x["video_url"] is None, x["source"]))
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
