---
name: 💬 Comment - 주석 추가/변경
about: 필요한 주석 추가 및 변경
title: 'comment: '
labels: 'comment, documentation, backend'
assignees: ''
---

## 💬 주석 추가/변경 내용

<!-- 어떤 주석을 추가/변경하는지 설명해주세요. -->


## 🎯 대상 코드

```python
# 파일 경로
services/waste/app/services.py

# 대상 함수/클래스
def process_waste_image():
    ...
```

## 📝 추가할 주석 유형

- [ ] Docstring (함수/클래스 설명)
- [ ] 인라인 주석 (복잡한 로직 설명)
- [ ] TODO 주석
- [ ] FIXME 주석
- [ ] NOTE 주석
- [ ] 타입 힌트 추가

## 🏁 할 일

- [ ] Docstring 작성 (Google Style)
- [ ] 복잡한 로직 주석 추가
- [ ] TODO/FIXME 정리
- [ ] 타입 힌트 추가

## 📚 Docstring 예시

```python
def process_waste_image(job_id: str) -> dict:
    """쓰레기 이미지 처리 파이프라인
    
    Args:
        job_id: 작업 ID
    
    Returns:
        dict: 처리 결과
        {
            "waste_type": str,
            "confidence": float,
            "feedback": str
        }
    
    Raises:
        ValueError: job_id가 유효하지 않을 경우
        APIError: AI API 호출 실패 시
    """
    pass
```

## 📚 참고사항

<!-- Google Style Docstring 가이드 -->
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)

