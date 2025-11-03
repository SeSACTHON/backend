---
name: 🚨 Hotfix - 긴급 버그 수정
about: 급하게 치명적인 버그를 고쳐야하는 경우
title: 'hotfix: '
labels: 'hotfix, critical, backend'
assignees: ''
---

## 🚨 긴급 상황

**심각도**: 🔴 Critical

## 🐛 버그 설명

<!-- 어떤 치명적인 버그인지 명확하게 설명해주세요. -->


## 💥 영향 범위

- [ ] 서비스 전체 중단
- [ ] 주요 기능 완전 장애
- [ ] 데이터 손실 위험
- [ ] 보안 취약점
- [ ] 기타 치명적 문제: 

## 🎯 영향받는 서비스

- [ ] auth-service
- [ ] users-service
- [ ] waste-service
- [ ] recycling-service
- [ ] locations-service
- [ ] Database
- [ ] RabbitMQ
- [ ] 전체 시스템

## 🔄 재현 방법

1. 
2. 
3. 

## ✅ 예상 동작

<!-- 정상 동작 설명 -->


## ❌ 실제 동작

<!-- 버그 동작 설명 -->


## 🔧 임시 조치 (Workaround)

<!-- 급한 대로 취한 임시 조치가 있다면 -->


## 📝 로그

```
# 에러 로그 붙여넣기
```

## ⏰ 발생 시각

- 발생 시간: YYYY-MM-DD HH:MM
- 발견 시간: YYYY-MM-DD HH:MM

## 📚 참고사항

<!-- 추가 정보 -->


---

**⚠️ Hotfix는 main 브랜치에서 직접 분기하여 처리합니다.**  
**브랜치명**: `hotfix/{이슈번호}-{설명}`

