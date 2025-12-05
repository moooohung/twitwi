#!/usr/bin/env python3
"""
Twitter 비디오 크롤러 - 다중 소스 전략
1. FlareSolverr + twidouga.net (실패 시 스킵)
2. Nitter 인스턴스 스캔
3. Twitter API v2 (Bearer Token 필요)
4. 유명 일본 계정 직접 크롤링
5. GitHub 캐시 fallback
"""

import json
import re
import asyncio
import os
from datetime import datetime, timezone
import urllib.request
import urllib.parse

VIDEO_PATTERN = re.compile(r'https://video\.twimg\.com/[^"\'<>\s]+\.mp4[^"\'<>\s]*')
TWEET_PATTERN = re.compile(r'(?:twitter\.com|x\.com)/(\w+)/status/(\d+)')


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
        username, tid = match.groups()
        if tid not in seen_ids:
            seen_ids.add(tid)
            videos.append({"id": tid, "video_url": None, "tweet_url": f"https://twitter.com/{username}/status/{tid}", "source": source})
    
    return videos


async def try_flaresolverr(url: str) -> str:
    """FlareSolverr (Cloudflare 우회)"""
    try:
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
                
                # 실제 컨텐츠인지 확인 (에러 페이지 제외)
                if "twimg.com" in html or ("twitter.com" in html and "ERR_" not in html):
                    print(f"[FLARESOLVERR] Success with real content!")
                    return html
                    
                # Cloudflare 챌린지 페이지인지 확인
                if "Just a moment" in html or "Checking your browser" in html:
                    print(f"[FLARESOLVERR] Cloudflare challenge detected, retrying...")
                    return ""
                    
                print(f"[FLARESOLVERR] Got error page or empty content")
                
    except Exception as e:
        print(f"[FLARESOLVERR] Error: {e}")
    
    return ""


async def try_nitter_search() -> list:
    """Nitter 검색 - 더 많은 인스턴스"""
    videos = []
    
    # 더 많은 Nitter 미러들
    instances = [
        "https://nitter.privacydev.net",
        "https://nitter.poast.org", 
        "https://xcancel.com",
        "https://nitter.cz",
        "https://nitter.esmailelbob.xyz",
        "https://nitter.dasakamern.de",
        "https://nitter.woodland.cafe",
        "https://nitter.moomoo.me",
    ]
    
    print(f"[NITTER] Trying {len(instances)} instances...")
    
    for instance in instances:
        try:
            # 비디오 검색 (일본어)
            url = f"{instance}/search?f=videos&q=lang%3Aja"
            
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                "Accept": "text/html",
            })
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                
                # /username/status/id 패턴
                matches = re.findall(r'href="(/([^/]+)/status/(\d+))"', html)
                
                for full, username, tweet_id in matches[:30]:
                    if tweet_id not in [v["id"] for v in videos]:
                        videos.append({
                            "id": tweet_id,
                            "video_url": None,
                            "tweet_url": f"https://twitter.com/{username}/status/{tweet_id}",
                            "source": f"nitter_{instance.split('//')[1].split('.')[0]}"
                        })
                
                if len(matches) > 0:
                    print(f"[NITTER] {instance}: found {len(matches)} tweets")
                    break
                    
        except Exception as e:
            print(f"[NITTER] {instance}: {str(e)[:30]}")
    
    print(f"[NITTER] Total: {len(videos)}")
    return videos


async def try_twitter_api() -> list:
    """Twitter API v2 (Bearer Token 필요)"""
    videos = []
    
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN", "")
    if not bearer_token:
        print("[TWITTER_API] No bearer token, skipping")
        return videos
    
    try:
        print("[TWITTER_API] Fetching trending topics...")
        
        # 일본 WOEID: 23424856
        url = "https://api.twitter.com/1.1/trends/place.json?id=23424856"
        
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {bearer_token}"
        })
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            trends = data[0].get("trends", [])[:10]
            
            for trend in trends:
                # 트렌드 검색으로 비디오 찾기
                query = urllib.parse.quote(f"{trend['name']} filter:videos")
                search_url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=10&expansions=attachments.media_keys&media.fields=url,variants"
                
                # ... (API 호출 구현)
                
    except Exception as e:
        print(f"[TWITTER_API] Error: {e}")
    
    return videos


async def try_famous_accounts() -> list:
    """유명 일본 비디오 계정들 크롤링"""
    videos = []
    
    # 일본에서 인기 있는 비디오 공유 계정들
    accounts = [
        "video_japan",
        "bazvideo",
        "gifmagazine",
    ]
    
    # Nitter를 통해 접근
    for account in accounts:
        try:
            instances = ["https://xcancel.com", "https://nitter.privacydev.net"]
            for instance in instances:
                try:
                    url = f"{instance}/{account}/media"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        html = resp.read().decode('utf-8', errors='ignore')
                        
                        matches = re.findall(r'/status/(\d+)', html)
                        for tid in matches[:10]:
                            if tid not in [v["id"] for v in videos]:
                                videos.append({
                                    "id": tid,
                                    "video_url": None,
                                    "tweet_url": f"https://twitter.com/{account}/status/{tid}",
                                    "source": f"account_{account}"
                                })
                        
                        if len(matches) > 0:
                            print(f"[ACCOUNTS] {account}: {len(matches)} videos")
                            break
                            
                except:
                    continue
                    
        except Exception as e:
            print(f"[ACCOUNTS] {account}: {str(e)[:30]}")
    
    return videos


async def fetch_github_cache() -> list:
    """GitHub 캐시"""
    videos = []
    
    sources = [
        ("https://raw.githubusercontent.com/PineAppleHollyday1/twitter-realtime-100-twidouga.net-/main/realtime_t.php", "github_pineapple"),
    ]
    
    for url, source in sources:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                videos.extend(extract_videos(html, source))
                print(f"[GITHUB] {source}: {len(videos)} videos")
        except Exception as e:
            print(f"[GITHUB] {source}: {str(e)[:30]}")
    
    return videos


async def main():
    all_videos = []
    seen_ids = set()
    
    # === 1. FlareSolverr ===
    for url in ["https://twidouga.net/realtime_t.php"]:
        html = await try_flaresolverr(url)
        if html:
            vids = extract_videos(html, "twidouga_flaresolverr")
            for v in vids:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            if vids:
                break
    
    # === 2. Nitter ===
    if len(all_videos) == 0:
        nitter_vids = await try_nitter_search()
        for v in nitter_vids:
            if v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                all_videos.append(v)
    
    # === 3. 유명 계정 ===
    if len(all_videos) < 20:
        account_vids = await try_famous_accounts()
        for v in account_vids:
            if v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                all_videos.append(v)
    
    # === 4. GitHub 캐시 (항상) ===
    github_vids = await fetch_github_cache()
    for v in github_vids:
        if v["id"] not in seen_ids:
            seen_ids.add(v["id"])
            all_videos.append(v)
    
    # === 저장 ===
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
    
    urls = [v["video_url"] or v["tweet_url"] for v in all_videos]
    with open("urls.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(urls))
    
    print(f"\n=== FINAL: {len(all_videos)} videos ===")
    print(f"Sources: {output['sources_used']}")


if __name__ == "__main__":
    asyncio.run(main())
