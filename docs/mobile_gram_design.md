# Mobile Gram Design & State Management Specification

## 문서 개요
* **작성일:** 2026년 8월 11일 (설계)
* **목적:** 
  1. 식재료 용량(g) 입력을 위한 `appState.recognized` 전역 상태 구조 설계 확장 (`servingG` 기본값 100g 설정).
  2. 모바일 환경 최적화를 위한 `<input type="file" capture="environment">` 동작 특징 분석 및 활용 방안 정립.
* **실제 코드 적용 예정일:** 8월 12일

---

## 1. `frontend/js/state.js` 구조 변경 설계

### 1.1 `appState.recognized` 개별 항목 구조 변경

#### [기존 구조]
```javascript
{
    image_id: string | null,
    name: string,
    confidence: number,
    candidates: string[],
    edited: boolean
}