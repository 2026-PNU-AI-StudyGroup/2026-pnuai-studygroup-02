// [UPLOAD] 근영 담당. 이미지 선택, 확장자 검증, 개별 삭제 및 미리보기 렌더링

document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('file-input');
    const previewList = document.getElementById('preview-list');
    const recognizeBtn = document.getElementById('recognize-btn');

    // 지원 확장자 정의 (jpg, jpeg, png)
    const allowedExtensions = ['jpg', 'jpeg', 'png'];

    /**
     * 현재 상태의 이미지 목록을 읽어와 미리보기 UI 영역을 다시 그리는 렌더링 함수
     */
    function renderPreviews() {
        // 기존 렌더링 내용 초기화
        previewList.innerHTML = '';

        if (appState.images.length === 0) {
            previewList.innerHTML = `<p class="placeholder-text">선택한 이미지 미리보기가 여기에 표시됩니다.</p>`;
            return;
        }

        // 이미지 각각을 카드 요소로 동적 렌더링
        appState.images.forEach(img => {
            const previewCard = document.createElement('div');
            previewCard.className = 'preview-card';
            previewCard.style.position = 'relative';
            previewCard.style.display = 'inline-block';
            previewCard.style.margin = '10px';
            previewCard.style.width = '120px';
            previewCard.style.height = '120px';
            previewCard.style.border = '1px solid #dee2e6';
            previewCard.style.borderRadius = '8px';
            previewCard.style.overflow = 'hidden';

            // 이미지 태그
            const imageEl = document.createElement('img');
            imageEl.src = img.previewUrl;
            imageEl.style.width = '100%';
            imageEl.style.height = '100%';
            imageEl.style.objectFit = 'cover';

            // 개별 삭제 버튼
            const deleteBtn = document.createElement('button');
            deleteBtn.textContent = '×';
            deleteBtn.style.position = 'absolute';
            deleteBtn.style.top = '5px';
            deleteBtn.style.right = '5px';
            deleteBtn.style.background = 'rgba(0,0,0,0.6)';
            deleteBtn.style.color = '#fff';
            deleteBtn.style.border = 'none';
            deleteBtn.style.borderRadius = '50%';
            deleteBtn.style.width = '24px';
            deleteBtn.style.height = '24px';
            deleteBtn.style.cursor = 'pointer';
            deleteBtn.style.fontSize = '14px';
            deleteBtn.style.lineHeight = '1';
            deleteBtn.style.display = 'flex';
            deleteBtn.style.alignItems = 'center';
            deleteBtn.style.justifyContent = 'center';

            // 삭제 버튼 이벤트 연결
            deleteBtn.addEventListener('click', () => {
                removeImage(img.image_id); // 상태에서 제거
                renderPreviews();        // UI 다시 그리기
            });

            previewCard.appendChild(imageEl);
            previewCard.appendChild(deleteBtn);
            previewList.appendChild(previewCard);
        });
    }

    // 파일 입력(input[type="file"]) 체인지 이벤트 리스너
    fileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);

        files.forEach(file => {
            // 파일명에서 확장자 추출 및 소문자 변환
            const fileExtension = file.name.split('.').pop().toLowerCase();

            if (allowedExtensions.includes(fileExtension)) {
                // 검증을 통과한 경우 전역 상태에 이미지 추가
                addImage(file);
            } else {
                // 지원하지 않는 포맷은 얼럿으로 표시하고 건너뜀
                alert(`[오류] "${file.name}"은(는) 지원하지 않는 파일 형식입니다. (jpg, jpeg, png 파일만 업로드 가능)`);
            }
        });

        // 업로드 입력값 초기화 (동일한 파일을 다시 연속으로 올릴 수 있도록 처리)
        fileInput.value = '';

        // 미리보기 화면 갱신
        renderPreviews();
    });

    // 인식하기 버튼 클릭 시 이벤트 리스너 (아직 API 연동이 없으므로 알림만 처리)
    recognizeBtn.addEventListener('click', () => {
        if (appState.images.length === 0) {
            alert('인식할 이미지를 먼저 업로드해 주세요.');
            return;
        }
        alert('다음 주(7/22 이후) 백엔드 AI 모델 API와 연동될 예정입니다.');
    });
});