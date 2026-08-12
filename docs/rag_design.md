# RAG 기반 레시피 검색 설계

## 1. 목적

기존 레시피 생성 기능은 LLM이 사용자 보유 재료를 기반으로
레시피를 직접 생성하는 방식이다.

향후에는 농촌진흥청 및 식품안전나라의 실제 레시피 데이터를
검색한 뒤 검색 결과를 LLM에 전달하는 RAG 구조로 변경한다.

이를 통해 실제 레시피 데이터를 근거로 답변을 생성하고,
사용자가 추천 결과의 출처를 확인할 수 있도록 한다.


## 2. 현재 Recipe 스키마

현재 `backend/schemas/recipe.py`의 `Recipe` 모델에서
`sources` 필드는 다음과 같이 정의되어 있다.

```python
sources: list[str] = Field(
    default_factory=list,
    description="RAG를 사용하지 않으므로 항상 빈 배열",
)