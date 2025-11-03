---
name: 📝 Rename - 파일/폴더명 수정
about: 파일 혹은 폴더명을 수정하거나 옮기는 작업만 수행한 경우
title: 'rename: '
labels: 'rename, refactor, backend'
assignees: ''
---

## 📝 Rename 내용

<!-- 어떤 파일/폴더를 변경하는지 설명해주세요. -->


## 🎯 변경 대상

### AS-IS (현재)
```
services/waste/app/waste_service.py
```

### TO-BE (변경 후)
```
services/waste/app/services.py
```

## 💡 변경 이유

- [ ] 네이밍 컨벤션 준수
- [ ] 의미 명확화
- [ ] 중복 제거
- [ ] 구조 재구성
- [ ] 기타: 

## 🔍 영향 범위 체크

- [ ] Import 경로 변경 필요
- [ ] 테스트 파일 경로 업데이트
- [ ] 문서 링크 업데이트
- [ ] CI/CD 경로 변경
- [ ] Helm Chart 경로 변경

## 🏁 할 일

- [ ] 파일/폴더 이름 변경
- [ ] Import 경로 모두 수정
- [ ] 테스트 실행 확인
- [ ] 문서 링크 확인

## ⚠️ 주의사항

<!-- Git에서 파일명 변경 추적을 위해 -->
```bash
git mv old_name.py new_name.py
# 또는
git add -A  # 변경 사항 추적
```

## 📚 참고사항

<!-- 추가 정보 -->

