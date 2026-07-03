# 📺 Stock Briefing Video Pipeline

주식 브리핑 자동 영상 생성 파이프라인

## 구성
- KO / EN / JA 3개 언어 자동 영상 생성
- ElevenLabs 목소리 클론 더빙
- Google Drive 자동 저장

## 대시보드 (GitHub Pages)

`docs/index.html`은 워크플로우 실행과 결과 영상 다운로드를 한 페이지에서 처리하는 정적 대시보드입니다.

GitHub Pages 활성화는 코드로 자동화할 수 없으므로, 저장소 관리자가 아래 절차를 수동으로 한 번 수행해야 합니다.

1. 저장소 **Settings > Pages** 로 이동
2. **Build and deployment > Source** 를 `Deploy from a branch` 로 설정
3. **Branch** 를 `main` (또는 배포할 기본 브랜치), 폴더를 `/docs` 로 선택 후 저장
4. 저장 후 `https://kunil-choi.github.io/stock-briefing-video/` 에서 대시보드에 접근 가능

대시보드는 `repo`, `workflow` 권한이 포함된 GitHub Personal Access Token을 입력받아 브라우저에서 직접 GitHub API를 호출합니다. 토큰은 브라우저 `localStorage`에만 저장되며 서버로 전송되지 않습니다.
