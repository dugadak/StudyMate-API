"""
Gunicorn 설정 파일

프로덕션 환경에서의 최적화된 Gunicorn 설정입니다.
"""

import multiprocessing
import os

# 서버 소켓
bind = "0.0.0.0:8000"
backlog = 2048

# 워커 프로세스
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
worker_connections = 1000
timeout = 60
keepalive = 5
max_requests = 1000
max_requests_jitter = 100

# 로깅
loglevel = os.environ.get('LOG_LEVEL', 'info')
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s '
    '"%(f)s" "%(a)s" %(D)s'
)
accesslog = "-"
errorlog = "-"

# 프로세스 이름
proc_name = "studymate-api"

# 보안
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# 성능 튜닝
preload_app = True
enable_stdio_inheritance = True

# 프로세스 관리
pidfile = "/tmp/gunicorn.pid"
user = "studymate"
group = "studymate"
tmp_upload_dir = None

# 개발 환경 설정
if os.environ.get('ENVIRONMENT') == 'development':
    reload = True
    workers = 1
    loglevel = 'debug'

# 워커 메모리 관리
def when_ready(server):
    """서버가 준비되었을 때 실행"""
    server.log.info("StudyMate API 서버가 준비되었습니다.")

def worker_int(worker):
    """워커가 중단될 때 실행"""
    worker.log.info(f"워커 {worker.pid}가 중단되었습니다.")

def pre_fork(server, worker):
    """워커가 포크되기 전 실행"""
    server.log.info(f"워커 {worker.pid}를 시작합니다.")

def post_fork(server, worker):
    """워커가 포크된 후 실행"""
    server.log.info(f"워커 {worker.pid}가 시작되었습니다.")

def pre_exec(server):
    """서버 재시작 전 실행"""
    server.log.info("서버를 재시작합니다.")

def worker_abort(worker):
    """워커가 비정상 종료될 때 실행"""
    worker.log.info(f"워커 {worker.pid}가 비정상 종료되었습니다.")

# 환경별 추가 설정
environment = os.environ.get('ENVIRONMENT', 'production')

if environment == 'production':
    # 프로덕션 환경 최적화
    worker_tmp_dir = "/dev/shm"  # 메모리 기반 임시 디렉토리
    
elif environment == 'staging':
    # 스테이징 환경 설정
    workers = max(2, multiprocessing.cpu_count())
    
elif environment == 'development':
    # 개발 환경 설정
    workers = 1
    reload = True
    timeout = 120