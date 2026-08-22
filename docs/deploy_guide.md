# 배포 가이드 (Render)

8/11에 정리한 배포 플랫폼 후보 중 **Render**를 선택해 배포한다. Render는 GitHub 저장소를 직접 연결해
`Dockerfile` 기반으로 이미지를 빌드 → 배포해주는 방식(Web Service, Docker 환경)을 지원한다.

## 0. 사전 준비

- GitHub 저장소
- 배포 브랜치: `main` (PR 머지 후 배포)
- 루트에 `Dockerfile`, `.dockerignore` 존재 확인
- `model/artifacts/ingredient_model_v2.tflite` 파일이 git에 커밋되어 있어야 함
  (`.keras` 원본은 git에는 남겨두되 `.dockerignore`로 배포 이미지에서는 제외한다. 자세한 내용은
  [7. TFLite 경량화 적용](#7-tflite-경량화-적용-2026-08-22) 참고)

```bash
git ls-files model/artifacts
# ingredient_model_v2.tflite, class_names*.json 등이 보여야 함
```

- 배포에 필요한 API 키 값을 미리 확보해둔다 (Render 시크릿에 등록할 값들, `.env.example` 참고)
  - `GEMINI_API_KEY`
  - `RDA_RECIPE_API_KEY`
  - `FOODSAFETY_RECIPE_API_KEY`
  - `CORS_ORIGINS` (배포 후 실제 프론트엔드 접근 origin으로 설정. 프론트를 같은 서비스에서 정적으로 서빙하므로
    보통 Render가 부여하는 서비스 URL 자신을 넣거나, 별도 프론트 도메인이 있다면 그 값을 넣는다)
  - `MOCK_MODE`

> 이 값들은 절대 코드/커밋/`.env` 파일로 저장소에 올리지 않는다. Render 대시보드의 Environment
> 설정(시크릿)에만 등록한다.

## 1. Render 서비스 생성

저장소가 GitHub organization(`2026-PNU-AI-StudyGroup`) 소속이라, 일반 멤버 계정으로는 Render GitHub
App의 조직 저장소 접근 승인을 받을 수 없다(조직 Owner만 승인 가능). 이 문제를 피하기 위해
**Public Git Repository** 방식으로 연결했다. 저장소가 public이므로 GitHub 계정 연동 없이 git URL만으로
클론·빌드가 가능하다.

1. render 로그인
2. **New +** → **Web Service** 선택
3. Source 선택 화면에서 GitHub/GitLab/Bitbucket이 아닌 **Public Git Repository** 탭 선택 후
   저장소 URL 입력
4. 배포 설정 입력
   - **Name**: `ingredient-project` (원하는 이름)
   - **Region**: Singapore 등 가까운 리전
   - **Branch**: `dev/C` (검증 단계이므로 작업 브랜치를 직접 지정. main 브랜치로 승격은 팀 리뷰 후 별도 진행)
   - **Language**: `Docker` (자동 인식이 안 될 수 있어 직접 선택 필요. 선택 시 Build/Start Command
     입력란이 사라지고 저장소 루트의 `Dockerfile`을 그대로 사용)
   - **Instance Type**: Free (테스트용)
     - 모델 로딩(TensorFlow + SentenceTransformer) 메모리 사용량이 있으므로 Free 플랜에서 OOM이
       발생하면 최소 유료 플랜(예: Starter)으로 올린다.

> **주의(Public Git Repository 방식의 한계)**: GitHub App으로 정식 연동한 게 아니라 git 클론 방식이라
> **push해도 자동 재배포(Auto-Deploy)가 되지 않는다.** 코드를 수정한 뒤에는 Render 대시보드에서
> **Manual Deploy → Deploy latest commit**을 직접 눌러 재배포해야 한다. 이후 조직 관리자에게 Render
> GitHub App 승인을 받으면 정식 GitHub 연동으로 전환해 자동 배포를 활성화할 수 있다.

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

- 현재는 Public Git Repository 방식이라 **자동 재배포가 되지 않는다.** 코드를 수정해 push한 뒤에는
  Render 대시보드에서 **Manual Deploy → Deploy latest commit**을 매번 직접 눌러야 최신 코드가 반영된다.
- 모델을 재학습해 `.keras` 파일을 교체하는 경우도 동일하게, 커밋·push 후 Manual Deploy로 반영한다.
- 이후 main으로 승격하고 조직 관리자에게 Render GitHub App 승인을 받으면, 정식 GitHub 연동 방식으로
  바꿔 push 시 자동 재배포되도록 전환할 수 있다.

## 참고: Free 플랜 유의사항

- Render Free 웹 서비스는 일정 시간 요청이 없으면 슬립되며, 슬립 이후 첫 요청 시 콜드 스타트로
  응답이 수십 초 이상 걸릴 수 있다 (TensorFlow/임베딩 모델 로딩 포함 시 더 오래 걸릴 수 있음).
- 데모/시연 전에는 미리 한 번 접속해 깨워두는 것을 권장한다.

## 6. 실제 배포 시도 결과 (2026-08-21)

위 절차대로 Render Web Service(`ingredient-project`, Free 플랜, Public Git Repository, `dev/C`
브랜치)를 실제로 1회 배포해 다음을 확인했다.

- **정상 확인됨**: 빌드 성공, 프론트엔드 정적 파일 서빙(`/`), 헬스체크(`/api/health` → `{"status":"ok"}`)
- **문제 발생**: 이미지 분류 API(`/api/ingredients/predict`)를 호출하면 TensorFlow 임포트 + `.keras`
  모델 로딩 + 추론 과정에서 메모리 사용량이 Free 플랜 한도(512MB)를 초과해 인스턴스가 강제 재시작됨
  (Render로부터 "exceeded its memory limit" 알림 수신). 이 상태에서 요청은 `502 Bad Gateway`로 실패한다.

**결정: 이미지 분류가 이 프로젝트의 핵심 기능이므로, 해당 기능이 배포 환경에서 불안정하게 동작하는
상태로 배포 링크를 대표 제출물로 사용하지 않기로 함.** 대신,

- Render 서비스는 정지(suspend)해 불필요한 재시작/알림을 막는다.
- 이미지 분류를 포함한 전체 기능은 로컬 실행 화면으로 데모 영상을 촬영해 대체한다.
- Dockerfile, `.dockerignore`, 배포 절차 자체는 그대로 저장소에 남겨, 추후 아래 개선을 적용한 뒤
  재배포를 시도할 수 있도록 한다.

### 향후 재배포 시 검토할 개선 방향

- `.keras` 모델을 TFLite 등 경량 포맷으로 변환해 추론 시 메모리 사용량을 크게 줄인다.
- Render 유료 플랜(예: Standard, RAM 2GB 이상)으로 인스턴스를 올려 TensorFlow 풀 모델을 그대로 구동한다.
- 이미지 분류만 별도의 경량 추론 서버(예: ONNX Runtime, TFLite 런타임)로 분리해 메인 API 서버의
  메모리 부담을 줄인다.

## 7. TFLite 경량화 적용 (2026-08-22)

위 개선 방향 중 첫 번째(TFLite 변환)를 적용했다.

- `model/convert_to_tflite.py`: `ingredient_model_v2.keras` → `ingredient_model_v2.tflite` (float16
  양자화) 변환 스크립트. 로컬에서 1회 실행해 결과물(`model/artifacts/ingredient_model_v2.tflite`,
  약 7.8MB, 원본 대비 약 절반)을 커밋한다.
- `backend/services/image_service.py`: `tf.keras.models.load_model` + `model.predict` 대신
  `ai_edge_litert.interpreter.Interpreter`로 `.tflite` 모델을 로딩·추론하도록 변경.
- `requirements.txt`: `tensorflow` → `ai-edge-litert`로 교체 (배포 이미지에서 무거운 TensorFlow 풀
  패키지를 설치하지 않아 메모리·빌드 시간 모두 절감).
- `Dockerfile`, `.dockerignore`: `.keras` 원본 모델 파일은 이미지에 포함하지 않도록 제외
  (`model/artifacts/*.keras`), 변환 스크립트도 배포 이미지에서 제외.
- 검증: 샘플 이미지(`service_img/t1~t3.png`) 기준 변환 전후 top-1 클래스 100% 일치, 클래스별
  confidence 차이는 0.001 미만으로 정확도 손실 무시할 수준.
- `tests/test_image_service.py`의 `load_model` 반환 시그니처를 `(interpreter, input_index,
  output_index, class_names)`로 갱신.

재배포 시 Render 인스턴스의 실제 메모리 사용량(Metrics 탭)을 확인해 512MB 이내로 들어오는지
재검증이 필요하다.
