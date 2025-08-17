#!/usr/bin/env python
"""
StudyMate API 코드 품질 도구 설정 스크립트

이 스크립트는 다음 작업을 수행합니다:
- 코드 품질 도구 설치
- Pre-commit 훅 설정
- 코드 포매팅 및 린팅 실행
- 타입 검사 실행
"""

import os
import sys
import subprocess
from pathlib import Path

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).resolve().parent

def run_command(command, description=""):
    """명령어 실행"""
    if description:
        print(f"\n{'='*60}")
        print(f"🔧 {description}")
        print(f"{'='*60}")
    
    print(f"실행 중: {' '.join(command)}")
    result = subprocess.run(command, cwd=BASE_DIR)
    
    if result.returncode != 0:
        print(f"❌ 실패: {description}")
        return False
    else:
        print(f"✅ 성공: {description}")
    
    return True

def install_development_tools():
    """개발 도구 설치"""
    tools = [
        "mypy",
        "django-stubs[compatible-mypy]",
        "djangorestframework-stubs[compatible-mypy]", 
        "types-redis",
        "types-requests",
        "ruff",
        "bandit",
        "pre-commit",
        "pydocstyle",
        "pylint",
        "pylint-django",
    ]
    
    for tool in tools:
        command = ["pip", "install", tool]
        if not run_command(command, f"{tool} 설치"):
            return False
    
    return True

def setup_pre_commit():
    """Pre-commit 훅 설정"""
    commands = [
        (["pre-commit", "install"], "Pre-commit 훅 설치"),
        (["pre-commit", "install", "--hook-type", "pre-push"], "Pre-push 훅 설치"),
        (["pre-commit", "autoupdate"], "Pre-commit 훅 업데이트"),
    ]
    
    for command, description in commands:
        if not run_command(command, description):
            return False
    
    return True

def format_code():
    """코드 포매팅"""
    commands = [
        (["black", ".", "--line-length=120"], "Black 코드 포매팅"),
        (["isort", ".", "--profile=black", "--line-length=120"], "Import 정렬"),
    ]
    
    for command, description in commands:
        if not run_command(command, description):
            return False
    
    return True

def lint_code():
    """코드 린팅"""
    commands = [
        (["ruff", "check", ".", "--fix"], "Ruff 린팅"),
        (["flake8", "."], "Flake8 검사"),
        (["bandit", "-r", ".", "-x", "tests/,venv/"], "보안 검사"),
    ]
    
    success = True
    for command, description in commands:
        if not run_command(command, description):
            success = False
    
    return success

def type_check():
    """타입 검사"""
    command = ["mypy", "."]
    return run_command(command, "MyPy 타입 검사")

def django_checks():
    """Django 프로젝트 검사"""
    commands = [
        (["python", "manage.py", "check"], "Django 기본 검사"),
        (["python", "manage.py", "check", "--deploy"], "Django 배포 검사"),
        (["python", "manage.py", "makemigrations", "--check", "--dry-run"], "마이그레이션 검사"),
    ]
    
    success = True
    for command, description in commands:
        if not run_command(command, description):
            success = False
    
    return success

def generate_baseline_files():
    """베이스라인 파일 생성"""
    # 시크릿 검사 베이스라인 생성
    command = ["detect-secrets", "scan", "--baseline", ".secrets.baseline"]
    run_command(command, "시크릿 검사 베이스라인 생성")
    
    # MyPy 캐시 정리
    command = ["mypy", "--install-types", "--non-interactive", "."]
    run_command(command, "MyPy 타입 스텁 설치")

def create_quality_script():
    """코드 품질 검사 스크립트 생성"""
    script_content = '''#!/usr/bin/env python
"""
코드 품질 검사 스크립트
"""

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def run_check(command, description):
    """검사 실행"""
    print(f"\\n🔍 {description}")
    print("-" * 50)
    result = subprocess.run(command, cwd=BASE_DIR)
    
    if result.returncode == 0:
        print(f"✅ {description} - 통과")
        return True
    else:
        print(f"❌ {description} - 실패")
        return False

def main():
    """메인 함수"""
    checks = [
        (["black", "--check", ".", "--line-length=120"], "코드 포매팅 검사"),
        (["isort", "--check-only", ".", "--profile=black"], "Import 정렬 검사"),
        (["ruff", "check", "."], "린팅 검사"),
        (["mypy", "."], "타입 검사"),
        (["bandit", "-r", ".", "-x", "tests/,venv/"], "보안 검사"),
        (["python", "manage.py", "check"], "Django 검사"),
    ]
    
    print("🔧 StudyMate API 코드 품질 검사 시작")
    
    passed = 0
    total = len(checks)
    
    for command, description in checks:
        if run_check(command, description):
            passed += 1
    
    print(f"\\n📊 검사 결과: {passed}/{total} 통과")
    
    if passed == total:
        print("🎉 모든 검사를 통과했습니다!")
        sys.exit(0)
    else:
        print("⚠️  일부 검사에서 문제가 발견되었습니다.")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
    
    script_path = BASE_DIR / "check_quality.py"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    
    # 실행 권한 부여
    os.chmod(script_path, 0o755)
    print(f"✅ 코드 품질 검사 스크립트 생성: {script_path}")

def main():
    """메인 함수"""
    print("🔧 StudyMate API 코드 품질 도구 설정 시작")
    
    # 1. 개발 도구 설치
    if not install_development_tools():
        print("❌ 개발 도구 설치 실패")
        sys.exit(1)
    
    # 2. Pre-commit 설정
    if not setup_pre_commit():
        print("❌ Pre-commit 설정 실패")
        sys.exit(1)
    
    # 3. 베이스라인 파일 생성
    generate_baseline_files()
    
    # 4. 코드 포매팅
    if not format_code():
        print("❌ 코드 포매팅 실패")
        sys.exit(1)
    
    # 5. 코드 품질 검사 스크립트 생성
    create_quality_script()
    
    print("\n🎉 코드 품질 도구 설정 완료!")
    print("\n📋 사용 가능한 명령어:")
    print("- python check_quality.py : 전체 품질 검사")
    print("- pre-commit run --all-files : Pre-commit 훅 실행")
    print("- black . : 코드 포매팅")
    print("- ruff check . : 린팅 검사")
    print("- mypy . : 타입 검사")
    print("- bandit -r . : 보안 검사")

if __name__ == "__main__":
    main()