-- StudyMate API 데이터베이스 초기화 스크립트

-- 데이터베이스가 존재하지 않으면 생성
SELECT 'CREATE DATABASE studymate'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'studymate')\gexec

-- 확장 프로그램 설치 (성능 및 기능 향상용)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- 인덱스 최적화를 위한 통계 정보 업데이트
ANALYZE;

-- 설정 최적화 (필요시)
-- ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
-- ALTER SYSTEM SET track_activity_query_size = 2048;
-- SELECT pg_reload_conf();