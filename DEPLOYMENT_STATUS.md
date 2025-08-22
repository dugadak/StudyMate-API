# 📊 StudyMate API 배포 현황

## 🚀 현재 배포 정보

### 서버 정보
- **서버 주소**: http://54.161.77.144/
- **인스턴스 ID**: i-0020665af83b7e371
- **인스턴스 유형**: AWS EC2 (us-east-1)
- **운영체제**: Amazon Linux 2
- **배포 날짜**: 2025-08-22
- **최종 업데이트**: 2025-08-22 (Django 애플리케이션 정상 배포)

### 접속 가능한 엔드포인트
| 엔드포인트 | URL | 상태 | 설명 |
|-----------|-----|------|-----|
| 메인 | http://54.161.77.144/ | ✅ 정상 | API 서버 상태 확인 |
| 헬스체크 | http://54.161.77.144/health | ✅ 정상 | 서버 상태 모니터링 |
| API 정보 | http://54.161.77.144/api/ | ✅ 정상 | API 버전 및 엔드포인트 정보 |
| 직접 접속 | http://54.161.77.144:8000/ | ✅ 정상 | Gunicorn 직접 접속 |

## 🛠 기술 스택

### 서버 구성
- **웹 서버**: Nginx (포트 80)
- **애플리케이션 서버**: Gunicorn (포트 8000, 2 workers)
- **Python 버전**: 3.9.23
- **프레임워크**: Django 5.0 (정상 작동)
- **데이터베이스**: SQLite (개발용)

### AWS 설정
- **보안 그룹**: sg-04cf738aac57f235f
- **인바운드 규칙**:
  - SSH (22): 0.0.0.0/0
  - HTTP (80): 0.0.0.0/0
  - Custom TCP (8000): 0.0.0.0/0

## 📝 배포 방법

### 자동 배포 스크립트 사용
```bash
cd scripts/deploy
./deploy_to_ec2.sh
```

### 수동 배포
```bash
# 1. EC2 서버 접속
ssh -i /path/to/key.pem ec2-user@54.161.77.144

# 2. 코드 업데이트
cd ~/studymate-api
git pull origin main

# 3. 서버 재시작
sudo killall python3 2>/dev/null
nohup python3 scripts/deploy/simple_api_server.py > /tmp/api_server.log 2>&1 &

# 4. 상태 확인
curl localhost:8000/health
```

## 🔍 모니터링

### 서버 상태 확인
```bash
# 로컬에서 확인
curl http://54.161.77.144/health

# 서버 로그 확인 (SSH 접속 후)
tail -f /tmp/api_server.log
```

### 프로세스 확인
```bash
# SSH 접속 후
ps aux | grep python3
sudo netstat -tlnp | grep -E ':80|:8000'
```

## ⚠️ 주의사항

1. **데이터베이스**: 현재 SQLite 사용 중 (프로덕션에서는 PostgreSQL 권장)
2. **SSL/TLS**: HTTPS 미적용 (프로덕션에서는 필수)
3. **도메인**: IP 직접 접속 (도메인 연결 필요)
4. **백업**: 자동 백업 미설정
5. **모델 변경사항**: 모든 필드에 적절한 default 값 설정 완료

## 📅 다음 단계

- [x] Django 애플리케이션 완전 배포 ✅
- [ ] PostgreSQL 데이터베이스 설정
- [ ] HTTPS 인증서 적용 (Let's Encrypt)
- [ ] 도메인 연결
- [ ] CI/CD 파이프라인 구축
- [ ] 모니터링 시스템 구축 (CloudWatch)
- [ ] 자동 백업 설정
- [ ] Redis 캐시 서버 설정
- [ ] 로드 밸런싱 구성

## 🔧 트러블슈팅

### 서버가 응답하지 않는 경우
1. AWS 보안 그룹 확인 (포트 80, 8000 열려있는지)
2. Nginx 상태 확인: `sudo systemctl status nginx`
3. Python 서버 프로세스 확인: `ps aux | grep python3`

### 배포 후 변경사항이 반영되지 않는 경우
1. 서버 재시작: `sudo killall python3 && nohup python3 simple_api_server.py &`
2. Nginx 재시작: `sudo systemctl restart nginx`
3. 브라우저 캐시 삭제

## 📞 문의
문제 발생 시 GitHub Issues에 등록해주세요.