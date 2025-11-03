---
name: 🗑️ Remove - 파일 삭제
about: 파일을 삭제하는 작업만 수행한 경우
title: 'remove: '
labels: 'remove, cleanup, backend'
assignees: ''
---

## 🗑️ 삭제 대상

<!-- 어떤 파일을 삭제하는지 설명해주세요. -->


## 🎯 삭제 파일 목록

```
services/waste/app/old_service.py
services/waste/app/deprecated.py
...
```

## 💡 삭제 이유

- [ ] 사용하지 않는 코드
- [ ] Deprecated 코드
- [ ] 중복 코드
- [ ] 임시 파일
- [ ] 테스트용 코드
- [ ] 기타: 

## ⚠️ 영향 범위 확인

- [ ] Import하는 곳 없음 확인
- [ ] 테스트 코드 의존성 없음
- [ ] 문서에서 참조 없음
- [ ] CI/CD에서 사용 안 함

## 🏁 할 일

- [ ] 파일 삭제
- [ ] Import 참조 제거
- [ ] 테스트 실행 (에러 없는지)
- [ ] Lint 검사 통과

## 📚 참고사항

<!-- 추가 정보 -->

---

**⚠️ 삭제 전 반드시 grep으로 참조 확인!**
```bash
grep -r "filename" services/
```

