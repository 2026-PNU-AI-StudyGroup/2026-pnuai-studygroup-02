# 배포 가이드 (Render)

8/11에 정리한 배포 플랫폼 후보 중 **Render**를 선택해 배포한다. Render는 GitHub 저장소를 직접 연결해
`Dockerfile` 기반으로 이미지를 빌드 → 배포해주는 방식(Web Service, Docker 환경)을 지원한다.

## 0. 사전 준비

- GitHub 저장소: `2026-PNU-AI-StudyGroup/2026-pnuai-studygroup-02` (이미 연결되어 있음)
- 배포 브랜치: `main` (PR 머지 후 배포)
- 루트에 `Dockerfile`, `.dockerignore` 존재 확인
- `model/artifacts/*.keras` 모델 파일이 git에 커밋되어 있어야 함
  (`.gitignore`에서 `model/artifacts/*.keras` 제외 규칙을 제거했으므로, 아래처럼 커밋되어 있는지 확인)

```bash
git ls-files model/artifacts
# ingredient_model.keras, ingredient_model_v2.keras, class_names*.json 등이 보여야 함
```

- 배포에 필요한 API 키 값을 미리 확보해둔다 (Render 시크릿에 등록할 값들, `.env.example` 참고)
  - `GEMINI_API_KEY`
  - `RDA_RECIPE_API_KEY`
  - `FOODSAFETY_RECIPE_API_KEY`
  - `CORS_ORIGINS` (배포 후 실제 프론트엔드 접근 origin으로 설정. 프론트를 같은 서비스에서 정적으로 서빙하므로
    보통 Render가 부여하는 서비스 URL 자신을 넣거나, 별도 프론트 도메인이 있다면 그 값을 넣는다)
  - `MOCK_MODE` (기본 `false`)

> 이 값들은 절대 코드/커밋/`.env` 파일로 저장소에 올리지 않는다. Render 대시보드의 Environment
> 설정(시크릿)에만 등록한다.

## 1. Render 서비스 생성

1. https://dashboard.render.com 접속 후 로그인 (GitHub 계정 연동)
2. **New +** → **Web Service** 선택
3. **Build and deploy from a Git repository** 선택 후 해당 GitHub 저장소 연결
   - 최초 연결 시 Render GitHub App 권한 승인 필요 (저장소 접근 허용)
4. 배포 설정 입력
   - **Name**: `ingredient-project` (원하는 이름)
   - **Region**: Singapore 등 가까운 리전
   - **Branch**: `main`
   - **Root Directory**: 비워둠 (저장소 루트에 Dockerfile 위치)
   - **Runtime**: `Docker` (Render가 루트의 `Dockerfile`을 자동 인식)
   - **Instance Type**: Free (테스트용) 또는 최소 유료 플랜
     - 모델 로딩(TensorFlow + SentenceTransformer) 메모리 사용량이 있으므로 Free 플랜에서 OOM이
       발생하면 최소 유료 플랜(예: Starter)으로 올린다.

## 2. 환경 변수(시크릿) 등록

Render 서비스 생성 화면(또는 생성 후 **Environment** 탭)에서 **Environment Variables**에 다음을 등록한다.
값은 Render가 암호화 저장하며 저장소에는 노출되지 않는다.

| Key | Value | 비고 |
|---|---|---|
| `GEMINI_API_KEY` | (실제 키) | Secret |
| `RDA_RECIPE_API_KEY` | (실제 키) | Secret |
| `FOODSAFETY_RECIPE_API_KEY` | (실제 키) | Secret |
| `CORS_ORIGINS` | `https://<서비스-slug>.onrender.com` | 배포 후 실제 URL로 갱신 |
| `MOCK_MODE` | `false` | LLM 정상 호출 |

`PORT`는 Render가 자동으로 주입하므로 별도로 설정하지 않는다 (`Dockerfile`의 CMD가
`${PORT:-8000}`을 사용해 이를 그대로 반영한다).

## 3. 첫 배포 실행

1. **Create Web Service** 클릭 → Render가 `Dockerfile` 기반으로 빌드 시작
   - `pip install -r requirements.txt` (tensorflow 포함) + SentenceTransformer 모델 사전 다운로드 때문에
     첫 빌드는 5~15분 정도 소요될 수 있다.
2. 빌드 로그에서 에러 없이 `Build successful` 및 `Deploy live` 상태가 되는지 확인
3. 상단에 표시되는 서비스 URL(`https://<서비스-slug>.onrender.com`)로 접속

## 4. 배포 검증

1. 브라우저에서 서비스 URL 접속 → `frontend/index.html`이 정상 렌더링되는지 확인 (정적 파일 서빙 확인)
2. 헬스체크 확인
   ```bash
   curl https://<서비스-slug>.onrender.com/api/health
   # {"status":"ok"}
   ```
3. 이미지 분류, 레시피 추천 등 실제 API를 한 번씩 호출해 모델/RAG 로딩과 외부 API 키 연동이
   정상 동작하는지 확인
4. 문제 발생 시 Render 대시보드의 **Logs** 탭에서 스택트레이스 확인 후 조치

## 5. 이후 배포(재배포)

- `main` 브랜치에 새 커밋이 푸시되면 Render가 자동으로 재빌드·재배포한다 (Auto-Deploy 기본 켜짐).
- 모델을 재학습해 `.keras` 파일을 교체하는 경우, 새 파일을 커밋 → `main` 푸시 → Render 자동 재배포로 반영된다.
- 수동 재배포가 필요하면 대시보드에서 **Manual Deploy → Deploy latest commit** 사용.

## 참고: Free 플랜 유의사항

- Render Free 웹 서비스는 일정 시간 요청이 없으면 슬립되며, 슬립 이후 첫 요청 시 콜드 스타트로
  응답이 수십 초 이상 걸릴 수 있다 (TensorFlow/임베딩 모델 로딩 포함 시 더 오래 걸릴 수 있음).
- 데모/시연 전에는 미리 한 번 접속해 깨워두는 것을 권장한다.
