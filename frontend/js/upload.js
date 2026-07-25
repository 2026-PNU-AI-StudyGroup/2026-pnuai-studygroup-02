// [UPLOAD] 근영 담당. 이미지 선택, 확장자 검증, 개별 삭제 및 미리보기 렌더링

document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('file-input');
    const previewList = document.getElementById('preview-list');
    const recognizeBtn = document.getElementById('recognize-btn');
    const resultCardsContainer = document.getElementById('result-cards');

    // 지원 확장자 정의 (jpg, jpeg, png)
    const allowedExtensions = ['jpg', 'jpeg', 'png'];

    // appState에 이미지 배열이 없다면 초기화
    if (!window.appState) window.appState = {};
    if (!appState.images) appState.images = [];

    /**
     * 현재 상태의 이미지 목록을 읽어와 미리보기 UI 영역을 다시 그리는 렌더링 함수
     * appState.images는 state.js의 addImage()가 만든 { image_id, file, previewUrl } 구조를 따른다.
     */
    function renderPreviews() {
        // 기존 렌더링 내용 초기화
        previewList.innerHTML = '';

        if (appState.images.length === 0) {
            previewList.innerHTML = `<p class="placeholder-text text-gray-400 text-sm">선택한 이미지 미리보기가 여기에 표시됩니다.</p>`;
            return;
        }

        // 이미지 배열을 순회하며 미리보기 카드 생성 (addImage()가 이미 만들어 둔 previewUrl 재사용)
        appState.images.forEach((image) => {
            const previewItem = document.createElement('div');
            previewItem.className = 'relative border rounded-lg p-2 flex items-center justify-between bg-white shadow-sm';

            previewItem.innerHTML = `
                <div class="flex items-center gap-2">
                    <img src="${image.previewUrl}" alt="preview" class="w-12 h-12 object-cover rounded">
                    <span class="text-xs truncate max-w-[120px]">${image.file.name}</span>
                </div>
                <button type="button" data-image-id="${image.image_id}" class="delete-btn text-red-500 hover:text-red-700 text-xs px-2 py-1">
                    삭제
                </button>
            `;

            // 개별 삭제 버튼 이벤트: removeIngredient()가 images/recognized/nutrition/recipes를 함께 정리한다.
            const deleteBtn = previewItem.querySelector('.delete-btn');
            deleteBtn.addEventListener('click', () => {
                removeIngredient(image.image_id);
                renderPreviews(); // UI 갱신
            });

            previewList.appendChild(previewItem);
        });
    }

    // 파일 선택 이벤트 처리
    if (fileInput) {
        fileInput.addEventListener('change', (event) => {
            const files = Array.from(event.target.files);

            files.forEach(file => {
                const ext = file.name.split('.').pop().toLowerCase();

                // 확장자 검증
                if (!allowedExtensions.includes(ext)) {
                    alert(`지원하지 않는 파일 형식입니다 (${file.name}). jpg, jpeg, png 파일만 업로드 가능합니다.`);
                    return;
                }

                // state.js의 addImage()로 상태에 추가 (image_id, previewUrl을 함께 생성)
                addImage(file);
            });

            // 입력값 초기화 (같은 파일 다시 선택 가능하도록)
            fileInput.value = '';
            renderPreviews();
        });
    }

    // 식재료 인식하기 버튼 클릭 이벤트 (API 연동)
    if (recognizeBtn) {
        recognizeBtn.addEventListener('click', async () => {
            if (appState.images.length === 0) {
                alert('업로드된 이미지가 없습니다. 이미지를 먼저 선택해주세요.');
                return;
            }

            try {
                recognizeBtn.disabled = true;
                recognizeBtn.textContent = '인식 중...';

                // api.js에 정의된 predictIngredients 호출 (File 객체 배열만 전달)
                const files = appState.images.map(image => image.file);
                const response = await predictIngredients(files);
                const results = response.results || [];

                // 백엔드는 파일명 기준 image_id를 반환하므로, 프론트에서 생성한 image_id로
                // 요청/응답 순서를 맞춰 매핑한다(image_service.predict_batch가 입력 순서를 그대로 유지함).
                appState.recognized = appState.images.map((image, index) => {
                    const result = results[index] || {};
                    return {
                        image_id: image.image_id,
                        name: result.name,
                        confidence: result.confidence,
                        candidates: result.candidates || [],
                        edited: false
                    };
                });

                // 인식 결과가 반영됐으므로 분석 가능 여부(analyze-btn 활성화)를 다시 계산한다.
                if (typeof canAnalyze === 'function') {
                    canAnalyze();
                }

                // 결과 카드 렌더링 함수 호출
                if (typeof renderResultCards === 'function') {
                    renderResultCards(appState.recognized, resultCardsContainer);
                }

            } catch (error) {
                console.error('인식 실패:', error);
                alert(`오류 발생: ${error.message}`);
            } finally {
                recognizeBtn.disabled = false;
                recognizeBtn.textContent = '식재료 인식하기';
            }
        });
    }
});