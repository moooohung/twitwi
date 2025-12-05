#!/usr/bin/env python3
"""
twidouga.net Cloudflare 우회 - 강화된 전략
1. nodriver (undetected-chromedriver async)
2. cloudscraper with JS interpreter
3. FlareSolverr proxy
4. 순수 Playwright + 수동 stealth
"""

import json
import re
import asyncio
import time
from datetime import datetime, timezone

# === 패턴들 ===
VIDEO_PATTERN = re.compile(r'https://video\.twimg\.com/[^"\'<>\s]+\.mp4[^"\'<>\s]*')
TWEET_PATTERN = re.compile(r'(?:twitter\.com|x\.com)/\w+/status/(\d+)')


def extract_videos(html: str, source: str) -> list:
    """HTML에서 동영상 URL 추출"""
    videos = []
    seen_ids = set()
    
    for match in VIDEO_PATTERN.finditer(html):
        url = match.group(0)
        vid = hash(url) % 10000000000
        if vid not in seen_ids:
            seen_ids.add(vid)
            videos.append({
                "id": str(vid),
                "video_url": url,
                "tweet_url": url,
                "source": source
            })
    
    for match in TWEET_PATTERN.finditer(html):
        tid = match.group(1)
        if tid not in seen_ids:
            seen_ids.add(tid)
            videos.append({
                "id": tid,
                "video_url": None,
                "tweet_url": f"https://twitter.com/i/status/{tid}",
                "source": source
            })
    
    return videos


# === 방법 1: nodriver (가장 강력한 undetected 브라우저) ===
async def try_nodriver(url: str) -> str:
    """nodriver - undetected-chromedriver의 async 버전"""
    try:
        import nodriver as uc
        
        print(f"[NODRIVER] Trying {url}...")
        
        browser = await uc.start(
            headless=True,
            browser_args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        
        page = await browser.get(url)
        
        # Cloudflare 챌린지 통과 대기 (최대 30초)
        for i in range(15):
            await asyncio.sleep(2)
            content = await page.get_content()
            
            if "twimg.com" in content or "twitter.com" in content:
                print(f"[NODRIVER] Success after {(i+1)*2}s! Found video URLs!")
                await browser.stop()
                return content
            
            if "Just a moment" not in content and "Checking your browser" not in content:
                if len(content) > 5000:
                    print(f"[NODRIVER] Got page content after {(i+1)*2}s")
                    await browser.stop()
                    return content
        
        await browser.stop()
        print("[NODRIVER] Timeout waiting for Cloudflare")
        
    except Exception as e:
        print(f"[NODRIVER] Error: {e}")
    
    return ""


# === 방법 2: cloudscraper with JavaScript interpreter ===
def try_cloudscraper_js(url: str) -> str:
    """cloudscraper with JS engine"""
    try:
        import cloudscraper
        
        print(f"[CLOUDSCRAPER_JS] Trying {url}...")
        
        # 다양한 설정 시도
        for interpreter in ['nodejs', 'native', 'js2py']:
            try:
                scraper = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'linux',
                        'desktop': True,
                    },
                    interpreter=interpreter,
                    delay=15,
                )
                
                response = scraper.get(url, timeout=90)
                
                if response.status_code == 200:
                    text = response.text
                    if "twimg.com" in text or "twitter.com" in text:
                        print(f"[CLOUDSCRAPER_JS] Success with {interpreter}!")
                        return text
                    
            except Exception as e:
                print(f"[CLOUDSCRAPER_JS] {interpreter} failed: {str(e)[:50]}")
                
    except Exception as e:
        print(f"[CLOUDSCRAPER_JS] Error: {e}")
    
    return ""


# === 방법 3: Playwright + 수동 stealth 설정 ===
async def try_playwright_manual_stealth(url: str) -> str:
    """Playwright with manual stealth configuration"""
    try:
        from playwright.async_api import async_playwright
        
        print(f"[PLAYWRIGHT_STEALTH] Trying {url}...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox', 
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate", 
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                }
            )
            
            page = await context.new_page()
            
            # 강력한 stealth 스크립트
            await page.add_init_script("""
                // navigator.webdriver 숨기기
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                // Chrome 객체
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // permissions 수정
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
                );
                
                // plugins 배열
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                // languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ja-JP', 'ja', 'en-US', 'en'],
                });
                
                // 자동화 관련 속성 숨기기
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            """)
            
            # 먼저 메인 페이지 방문
            try:
                await page.goto("https://twidouga.net/", timeout=30000)
                await page.wait_for_timeout(5000)
            except:
                pass
            
            # Cloudflare 챌린지 대기
            for i in range(20):
                await page.wait_for_timeout(2000)
                content = await page.content()
                
                if "Just a moment" not in content and len(content) > 3000:
                    break
            
            # 실제 페이지로 이동
            await page.goto(url, timeout=60000)
            
            # 로딩 대기
            for i in range(15):
                await page.wait_for_timeout(2000)
                content = await page.content()
                
                if "twimg.com" in content or "twitter.com" in content:
                    print(f"[PLAYWRIGHT_STEALTH] Found videos after {(i+1)*2}s!")
                    await browser.close()
                    return content
                
                if "Just a moment" not in content and "Checking" not in content:
                    if len(content) > 5000:
                        print(f"[PLAYWRIGHT_STEALTH] Got content: {len(content)} bytes")
                        await browser.close()
                        return content
            
            # 스크린샷 저장 (디버깅용)
            await page.screenshot(path="cloudflare_debug.png")
            final_content = await page.content()
            await browser.close()
            
            print(f"[PLAYWRIGHT_STEALTH] Final content length: {len(final_content)}")
            if "Just a moment" in final_content:
                print("[PLAYWRIGHT_STEALTH] Still stuck on Cloudflare challenge")
            
            return final_content
            
    except Exception as e:
        print(f"[PLAYWRIGHT_STEALTH] Error: {e}")
    
    return ""


# === 방법 4: curl_cffi with session ===
def try_curl_cffi_session(url: str) -> str:
    """curl_cffi with persistent session"""
    try:
        from curl_cffi import requests as cffi_requests
        
        print(f"[CURL_CFFI_SESSION] Trying {url}...")
        
        session = cffi_requests.Session(impersonate="chrome120")
        
        # 먼저 메인 페이지로 쿠키 획득
        try:
            resp1 = session.get("https://twidouga.net/", timeout=30)
            print(f"[CURL_CFFI_SESSION] Main page: {resp1.status_code}")
            time.sleep(5)
        except:
            pass
        
        # 실제 요청
        response = session.get(url, timeout=60)
        
        if response.status_code == 200:
            if "twimg.com" in response.text or "twitter.com" in response.text:
                print(f"[CURL_CFFI_SESSION] Success!")
                return response.text
        else:
            print(f"[CURL_CFFI_SESSION] Status {response.status_code}")
            
    except Exception as e:
        print(f"[CURL_CFFI_SESSION] Error: {e}")
    
    return ""


async def main():
    urls = [
        ("https://twidouga.net/realtime_t.php", "twidouga_jp"),
        ("https://twidouga.net/ko/realtime_t.php", "twidouga_kr"),
    ]
    
    all_videos = []
    seen_ids = set()
    
    for url, source in urls:
        html = ""
        
        # 방법 1: nodriver (가장 강력)
        html = await try_nodriver(url)
        if html and ("twimg.com" in html or "twitter.com" in html):
            videos = extract_videos(html, source + "_nodriver")
            print(f"[SUCCESS] nodriver found {len(videos)} videos!")
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            continue
        
        # 방법 2: cloudscraper with JS
        html = try_cloudscraper_js(url)
        if html and ("twimg.com" in html or "twitter.com" in html):
            videos = extract_videos(html, source + "_cloudscraper")
            print(f"[SUCCESS] cloudscraper found {len(videos)} videos!")
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            continue
        
        # 방법 3: Playwright manual stealth
        html = await try_playwright_manual_stealth(url)
        if html and ("twimg.com" in html or "twitter.com" in html):
            videos = extract_videos(html, source + "_playwright")
            print(f"[SUCCESS] Playwright found {len(videos)} videos!")
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
            continue
        
        # 방법 4: curl_cffi session
        html = try_curl_cffi_session(url)
        if html and ("twimg.com" in html or "twitter.com" in html):
            videos = extract_videos(html, source + "_curl_cffi")
            print(f"[SUCCESS] curl_cffi found {len(videos)} videos!")
            for v in videos:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    all_videos.append(v)
    
    # 결과 저장
    all_videos.sort(key=lambda x: x["video_url"] is None)
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
