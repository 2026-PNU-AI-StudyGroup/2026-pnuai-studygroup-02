// [UPLOAD] 근영 담당. 이미지 선택, 확장자 검증, 개별 삭제 및 미리보기/결과카드 렌더링

/**
 * [UI] 근영 담당. 인식된 식재료 카드 목록(#result-cards)을 렌더링한다.
 * 각 카드에 그람 수 입력창(스테퍼 -10g/+10g 및 숫자 입력, 기본 100g)이 제공된다.
 * @param {Array} recognizedItems - appState.recognized 배열
 * @param {HTMLElement} container - id='result-cards' 요소
 */
function renderResultCards(recognizedItems, container) {
    if (!container) return;

    container.innerHTML = '';

    if (!recognizedItems || recognizedItems.length === 0) {
        container.innerHTML = '<p class="placeholder-text">인식된 식재료가 여기에 태그로 표시됩니다.</p>';
        return;
    }

    recognizedItems.forEach((item, index) => {
        const card = document.createElement('div');
        card.className = 'result-card';
        card.dataset.index = index;

        // 삭제 버튼: image_id가 있으면 removeIngredient()로 정리, 수동 추가 항목은 직접 제거
        const deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'result-card-delete-btn';
        deleteBtn.textContent = '삭제';
        deleteBtn.addEventListener('click', () => {
            if (item.image_id) {
                removeIngredient(item.image_id);
            } else {
                appState.recognized = appState.recognized.filter((recognized) => recognized !== item);
                appState.nutrition = null;
                appState.recipes = null;
                if (typeof canAnalyze === 'function') canAnalyze();
            }
            renderResultCards(appState.recognized, container);
        });

        if (!item.name) {
            // 인식 실패 항목 처리
            const errorText = document.createElement('p');
            errorText.className = 'result-card-error';
            errorText.textContent = `⚠️ 인식 실패: ${item.error || '이미지를 분류하지 못했습니다.'}`;

            card.appendChild(errorText);
            card.appendChild(deleteBtn);
            container.appendChild(card);
            return;
        }

        // 식재료 이름 표시
        const nameText = document.createElement('span');
        nameText.textContent = item.name;
        nameText.className = 'result-card-name';

        // 신뢰도 표시
        const confidenceText = document.createElement('span');
        confidenceText.className = 'result-card-confidence';
        confidenceText.textContent = typeof item.confidence === 'number'
            ? `신뢰도 ${Math.round(item.confidence * 100)}%`
            : '';

        // 용량(g) 입력 래퍼 생성
        const gramWrapper = document.createElement('div');
        gramWrapper.className = 'gram-input-wrapper';

        const currentGram = item.servingG || 100;

        gramWrapper.innerHTML = `
            <div class="gram-stepper-group">
                <button type="button" class="btn-gram-step btn-minus-10" data-index="${index}">-10g</button>
                <input 
                    type="number" 
                    class="gram-number-input" 
                    data-index="${index}"
                    value="${currentGram}" 
                    min="1" 
                    max="2000" 
                    step="1"
                    inputmode="numeric"
                />
                <span class="gram-unit">g</span>
                <button type="button" class="btn-gram-step btn-plus-10" data-index="${index}">+10g</button>
            </div>
        `;

        card.appendChild(nameText);
        card.appendChild(confidenceText);
        card.appendChild(gramWrapper);
        card.appendChild(deleteBtn);
        container.appendChild(card);
    });

    attachGramInputEvents(container);
}

/**
 * [UI] 근영 담당. result-cards 내 그람 수 입력창 및 스테퍼 버튼 이벤트 제어
 * @param {HTMLElement} container - id='result-cards' 요소
 */
function attachGramInputEvents(container) {
    if (!container) return;

    // 1. 숫자 직접 입력 시 이벤트
    container.querySelectorAll('.gram-number-input').forEach(input => {
        input.addEventListener('change', (e) => {
            const idx = Number(e.target.dataset.index);
            const targetItem = appState.recognized[idx];
            if (!targetItem) return;

            const newGrams = parseInt(e.target.value, 10);
            const success = updateServingG(targetItem.image_id, newGrams, idx);

            if (success) {
                e.target.value = targetItem.servingG;
            } else {
                e.target.value = targetItem.servingG || 100;
            }
        });
    });

    // 2. -10g 스테퍼 버튼 이벤트
    container.querySelectorAll('.btn-minus-10').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = Number(e.target.dataset.index);
            const targetItem = appState.recognized[idx];
            if (!targetItem) return;

            const nextGrams = (targetItem.servingG || 100) - 10;
            const success = updateServingG(targetItem.image_id, nextGrams, idx);

            if (success) {
                const inputEl = container.querySelector(`.gram-number-input[data-index="${idx}"]`);
                if (inputEl) inputEl.value = targetItem.servingG;
            }
        });
    });

    // 3. +10g 스테퍼 버튼 이벤트
    container.querySelectorAll('.btn-plus-10').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = Number(e.target.dataset.index);
            const targetItem = appState.recognized[idx];
            if (!targetItem) return;

            const nextGrams = (targetItem.servingG || 100) + 10;
            const success = updateServingG(targetItem.image_id, nextGrams, idx);

            if (success) {
                const inputEl = container.querySelector(`.gram-number-input[data-index="${idx}"]`);
                if (inputEl) inputEl.value = targetItem.servingG;
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('file-input');
    const dropzone = document.getElementById('dropzone');
    const previewList = document.getElementById('preview-list');
    const recognizeBtn = document.getElementById('recognize-btn');
    const resultCardsContainer = document.getElementById('result-cards');

    // 모바일 환경을 고려해 capture 속성 동적 지원 (카메라 direct 연동)
    if (fileInput) {
        fileInput.setAttribute('accept', 'image/*');
        fileInput.setAttribute('capture', 'environment'); // 스마트폰 후면 카메라 자동 호출
    }

    const allowedExtensions = ['jpg', 'jpeg', 'png'];

    function renderPreviews() {
        previewList.innerHTML = '';

        if (appState.images.length === 0) {
            previewList.innerHTML = `<p class="placeholder-text">선택한 이미지 미리보기가 여기에 표시됩니다.</p>`;
            return;
        }

        appState.images.forEach((image) => {
            const previewItem = document.createElement('div');
            previewItem.className = 'preview-item';

            previewItem.innerHTML = `
                <img src="${image.previewUrl}" alt="preview" class="preview-thumb">
                <span class="preview-filename">${image.file.name}</span>
                <button type="button" data-image-id="${image.image_id}" class="delete-btn">삭제</button>
            `;

            const deleteBtn = previewItem.querySelector('.delete-btn');
            deleteBtn.addEventListener('click', () => {
                removeIngredient(image.image_id);
                renderPreviews();
            });

            previewList.appendChild(previewItem);
        });
    }

    function handleFiles(fileList) {
        Array.from(fileList).forEach(file => {
            const ext = file.name.split('.').pop().toLowerCase();

            if (!allowedExtensions.includes(ext)) {
                alert(`지원하지 않는 파일 형식입니다 (${file.name}). jpg, jpeg, png 파일만 업로드 가능합니다.`);
                return;
            }

            addImage(file);
        });

        renderPreviews();
    }

    if (fileInput) {
        fileInput.addEventListener('change', (event) => {
            handleFiles(event.target.files);
            fileInput.value = '';
        });
    }

    if (dropzone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, (event) => {
                event.preventDefault();
                dropzone.classList.add('dropzone-active');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (event) => {
                event.preventDefault();
                dropzone.classList.remove('dropzone-active');
            });
        });

        dropzone.addEventListener('drop', (event) => {
            const droppedFiles = event.dataTransfer ? event.dataTransfer.files : [];
            if (droppedFiles && droppedFiles.length > 0) {
                handleFiles(droppedFiles);
            }
        });
    }

    if (recognizeBtn) {
        recognizeBtn.addEventListener('click', async () => {
            if (appState.images.length === 0) {
                alert('업로드된 이미지가 없습니다. 이미지를 먼저 선택해주세요.');
                return;
            }

            try {
                recognizeBtn.disabled = true;
                recognizeBtn.textContent = '인식 중...';

                const files = appState.images.map(image => image.file);
                const response = await predictIngredients(files);
                const results = response.results || [];

                appState.recognized = appState.images.map((image, index) => {
                    const result = results[index] || {};
                    return {
                        image_id: image.image_id,
                        name: result.name,
                        confidence: result.confidence,
                        candidates: result.candidates || [],
                        edited: false,
                        servingG: 100
                    };
                });

                if (typeof canAnalyze === 'function') {
                    canAnalyze();
                }

                if (typeof renderResultCards === 'function') {
                    renderResultCards(appState.recognized, resultCardsContainer);
                }

            } catch (error) {
                console.error('인식 실패:', error);
                if (typeof app !== 'undefined' && typeof app.showCommonError === 'function') {
                    app.showCommonError(error.message || '식재료 인식 처리 중 오류가 발생했습니다.');
                }
            } finally {
                recognizeBtn.disabled = false;
                recognizeBtn.textContent = '식재료 인식하기';
            }
        });
    }
});