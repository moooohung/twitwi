# Twitter Trending Videos Auto-Fetcher

twidouga.net에서 실시간 트위터 동영상 URL을 15분마다 자동 수집합니다.

## 사용법

### KRBroadcasting 모드에서 사용

`videos.json` 또는 `urls.txt`의 Raw URL을 사용:

```
https://raw.githubusercontent.com/YOUR_USERNAME/twitter-trending-videos/main/videos.json
https://raw.githubusercontent.com/YOUR_USERNAME/twitter-trending-videos/main/urls.txt
```

### 파일 형식

**videos.json:**
```json
{
  "updated_at": "2025-01-01T12:00:00+00:00",
  "count": 50,
  "videos": [
    {
      "id": "1234567890",
      "video_url": "https://video.twimg.com/ext_tw_video/1234567890/pu/vid/avc1/720x1280/xxx.mp4?tag=12",
      "tweet_url": "https://twitter.com/i/status/1234567890"
    }
  ]
}
```

**urls.txt:**
```
https://video.twimg.com/ext_tw_video/...
https://twitter.com/i/status/...
```

## GitHub Actions

15분마다 자동 실행:
- `twidouga.net/realtime_t.php` (일본 실시간)
- `twidouga.net/ko/realtime_t.php` (한국 실시간)  
- `twidouga.net/ranking_t.php` (24시간 랭킹)

## 설정

1. 이 레포지토리를 Fork
2. Settings → Actions → General → "Read and write permissions" 활성화
3. Actions 탭에서 워크플로우 활성화

## 라이선스

MIT
