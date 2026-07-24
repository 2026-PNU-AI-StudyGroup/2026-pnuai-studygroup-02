# 레시피 LLM 서비스 인수인계 문서

<!-- [HANDOVER] 시은 작성, 24일 필수 완성 -->

## 1. 서비스 개요

사용자가 보유한 재료와 부족 영양소를 입력하면 LLM이 레시피를 생성하는 FastAPI 서비스입니다.

LLM 호출, JSON 파싱 또는 Pydantic 검증에 실패하면
`backend/mock/recipe_mock.json`의 고정 응답을 반환합니다.

주요 API는 다음과 같습니다.

```text
POST /api/recipes/recommend
```

현재 구현은 Google Gemini SDK를 사용합니다.
초기 명세에는 Anthropic Claude가 기재되어 있으므로,
LLM 제공자를 변경할 때는 서비스 코드와 환경변수 이름을 함께 수정해야 합니다.

## 2. 서비스 실행 방법

### 2.1 패키지 설치

프로젝트 최상위 폴더에서 실행합니다.

```powershell
python -m pip install -r requirements.txt
```

### 2.2 환경변수 설정

`.env.example`을 복사해 `.env` 파일을 만듭니다.

```powershell
Copy-Item .env.example .env
```

현재 Gemini 구현을 실행할 때는 다음처럼 설정합니다.

```env
GEMINI_API_KEY=실제_API_키
MOCK_MODE=false
CORS_ORIGINS=http://localhost:8000
```

`.env`에는 실제 API 키가 들어 있으므로 GitHub에 올리지 않습니다.

### 2.3 서버 실행

```powershell
python -m uvicorn backend.main:app --reload
```

정상 실행 시 다음 메시지가 출력됩니다.

```text
Application startup complete.
```

API 문서 주소:

```text
http://127.0.0.1:8000/docs
```

## 3. MOCK_MODE 전환 방법

### 실제 LLM 사용

```env
MOCK_MODE=false
```

이 상태에서는 Gemini API를 호출합니다.

### 고정 Mock 응답 사용

```env
MOCK_MODE=true
```

이 상태에서는 실제 LLM을 호출하지 않고
`backend/mock/recipe_mock.json`을 반환합니다.

환경변수를 변경한 뒤 서버를 다시 시작해야 합니다.

Mock 모드 확인 포인트:

- 응답 상태 코드가 `200`
- `recipe_id`가 `mock-`으로 시작
- 모든 레시피의 `sources`가 `[]`
- 실제 LLM 호출 실패 로그가 없음
- 터미널에 `MOCK_MODE=true` 안내 로그가 표시됨

## 4. 테스트 실행 방법

레시피 테스트만 실행:

```powershell
python -m pytest tests/test_recipes.py -v
```

현재 정상 결과:

```text
3 passed
```

전체 테스트 실행:

```powershell
python -m pytest -v
```

## 5. 테스트 입력 5세트와 기대 결과

### 테스트 1: 보유 재료 우선 모드

```json
{
  "ingredients": ["감자", "당근", "양배추"],
  "deficient_nutrients": [],
  "mode": "owned_first"
}
```

기대 결과:

- HTTP 상태 코드 `200`
- `recipe_mode`가 `owned_first`
- 레시피가 3개 이상
- `owned_ingredients`에는 입력한 재료만 포함
- `steps`가 빈 배열이 아님
- `sources`가 `[]`

### 테스트 2: 단백질 보충 모드

```json
{
  "ingredients": ["감자", "양배추"],
  "deficient_nutrients": ["단백질"],
  "mode": "nutrition_supplement"
}
```

기대 결과:

- HTTP 상태 코드 `200`
- `recipe_mode`가 `nutrition_supplement`
- 두부, 달걀, 콩 등의 단백질 보완 재료가
  `additional_ingredients`에 포함
- `sources`가 `[]`

### 테스트 3: 철분 보충 모드

```json
{
  "ingredients": ["감자", "당근"],
  "deficient_nutrients": ["철분"],
  "mode": "nutrition_supplement"
}
```

기대 결과:

- 철분 보완 재료가 `additional_ingredients`에 포함
- 입력하지 않은 재료가 `owned_ingredients`에 들어가지 않음
- `steps`가 빈 배열이 아님

### 테스트 4: 중복과 공백이 있는 입력

```json
{
  "ingredients": [" 감자 ", "감자", " 당근"],
  "deficient_nutrients": [],
  "mode": "owned_first"
}
```

기대 결과:

- 중복된 감자가 하나로 정리됨
- 문자열 앞뒤 공백이 제거됨
- HTTP 상태 코드 `200`
- 감자와 당근 기준으로 레시피 생성

### 테스트 5: 부족 영양소 누락

```json
{
  "ingredients": ["감자", "양배추"],
  "deficient_nutrients": [],
  "mode": "nutrition_supplement"
}
```

기대 결과:

- HTTP 상태 코드 `422`
- 부족 영양소 입력이 필요하다는 오류 메시지
- 오류 코드가 `INVALID_RECIPE_REQUEST`

## 6. 예상 오류와 해결 방법

### `GEMINI_API_KEY가 설정되지 않았습니다`

원인:

- `.env` 파일이 없음
- API 키 이름이 잘못됨
- 환경변수를 저장한 뒤 서버를 재시작하지 않음

해결:

```powershell
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(bool(os.getenv('GEMINI_API_KEY')))"
```

`True`가 출력되어야 합니다.

API 키가 없을 때는 다음처럼 실행할 수 있습니다.

```env
MOCK_MODE=true
```

### `503 UNAVAILABLE`

원인:

- Gemini 서버의 일시적인 과부하

해결:

- 잠시 후 재시도
- 서비스의 재시도 로그 확인
- 최종 Mock fallback 응답 확인

### `404 NOT_FOUND`

원인:

- 현재 계정에서 지원되지 않는 모델명 사용

해결:

- `backend/services/llm_recipe_service.py`의 `MODEL_NAME` 확인
- 계정에서 사용할 수 있는 모델로 변경

### `422 Unprocessable Entity`

원인:

- `ingredients`가 비어 있음
- 잘못된 `mode`
- `nutrition_supplement`인데 `deficient_nutrients`가 비어 있음

해결:

- 요청 JSON의 필드명과 값을 확인

### Mock JSON 검증 실패

원인:

- 필수 필드 누락
- `steps`가 빈 배열
- `recipe_mode` 값 오류
- `sources` 타입 오류

검증 명령:

```powershell
python -c "import json; from backend.schemas.recipe import RecipeResponse; data=json.load(open('backend/mock/recipe_mock.json', encoding='utf-8')); print(RecipeResponse.model_validate(data))"
```

## 7. 수정해도 되는 파일

다음 파일은 기능 개선이나 오류 수정 시 변경할 수 있습니다.

```text
backend/services/llm_recipe_service.py
backend/routers/recipes.py
backend/mock/recipe_mock.json
tests/test_recipes.py
docs/recipe_handover.md
.env.example
```

다음 파일은 프론트엔드와 API 계약에 영향을 주므로 팀과 협의 후 수정합니다.

```text
backend/schemas/recipe.py
```

## 8. 절대 임의로 변경하면 안 되는 응답 필드

### `recipe_mode`

허용 값:

```text
owned_first
nutrition_supplement
```

정상 예:

```json
{
  "recipe_mode": "owned_first"
}
```

필드 이름이나 허용 문자열을 임의로 바꾸지 않습니다.

### `sources`

항상 배열 타입이어야 하며 현재는 빈 배열입니다.

정상:

```json
{
  "sources": []
}
```

잘못된 예:

```json
{
  "sources": null
}
```

```json
{
  "sources": ""
}
```

```json
{
  "sources": "Gemini"
}
```

## 9. API 요청 예시

```http
POST /api/recipes/recommend
Content-Type: application/json
```

```json
{
  "ingredients": ["감자", "당근", "양배추"],
  "deficient_nutrients": [],
  "mode": "owned_first"
}
```

## 10. API 응답 예시

```json
{
  "recipe_mode": "owned_first",
  "recipes": [
    {
      "recipe_id": "recipe-001",
      "title": "감자 당근 볶음",
      "owned_ingredients": ["감자", "당근"],
      "additional_ingredients": [],
      "steps": [
        "감자와 당근을 깨끗하게 씻는다.",
        "재료를 먹기 좋은 크기로 썬다.",
        "팬에 식용유를 두르고 볶는다."
      ],
      "sources": []
    }
  ]
}
```

## 11. 인수인계 전 최종 확인

- [ ] 서버 실행 성공
- [ ] `/docs` 접속 성공
- [ ] `owned_first` 테스트 성공
- [ ] `nutrition_supplement` 테스트 성공
- [ ] LLM 실패 fallback 테스트 성공
- [ ] `MOCK_MODE=true` 동작 확인
- [ ] `.env`가 Git에 포함되지 않음
- [ ] `.env.example`이 Git에 포함됨
- [ ] `recipe_mode` 필드 유지
- [ ] `sources`가 항상 배열
- [ ] 전체 pytest 통과