#!/usr/bin/env python
"""
StudyMate API 테스트 실행 스크립트

이 스크립트는 다양한 테스트 시나리오를 실행할 수 있습니다:
- 전체 테스트 실행
- 특정 앱 테스트 실행
- 마커별 테스트 실행
- 성능 테스트 실행
- 커버리지 리포트 생성
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'studymate_api.test_settings')

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).resolve().parent

def run_command(command, description=""):
    """명령어 실행"""
    if description:
        print(f"\n{'='*60}")
        print(f"🧪 {description}")
        print(f"{'='*60}")
    
    print(f"실행 중: {' '.join(command)}")
    result = subprocess.run(command, cwd=BASE_DIR)
    
    if result.returncode != 0:
        print(f"❌ 실패: {description}")
        sys.exit(result.returncode)
    else:
        print(f"✅ 성공: {description}")
    
    return result


def setup_test_environment():
    """테스트 환경 설정"""
    # 테스트 결과 디렉토리 생성
    test_results_dir = BASE_DIR / 'test_results'
    test_results_dir.mkdir(exist_ok=True)
    
    # 로그 디렉토리 생성
    logs_dir = BASE_DIR / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    print("✅ 테스트 환경 설정 완료")


def run_all_tests():
    """전체 테스트 실행"""
    command = [
        'python', '-m', 'pytest',
        'tests/',
        '--tb=short',
        '--durations=10'
    ]
    
    run_command(command, "전체 테스트 실행")


def run_unit_tests():
    """단위 테스트 실행"""
    command = [
        'python', '-m', 'pytest',
        'tests/',
        '-m', 'unit',
        '--tb=short'
    ]
    
    run_command(command, "단위 테스트 실행")


def run_integration_tests():
    """통합 테스트 실행"""
    command = [
        'python', '-m', 'pytest',
        'tests/',
        '-m', 'integration',
        '--tb=short'
    ]
    
    run_command(command, "통합 테스트 실행")


def run_api_tests():
    """API 테스트 실행"""
    command = [
        'python', '-m', 'pytest',
        'tests/',
        '-m', 'api',
        '--tb=short'
    ]
    
    run_command(command, "API 테스트 실행")


def run_performance_tests():
    """성능 테스트 실행"""
    command = [
        'python', '-m', 'pytest',
        'tests/',
        '-m', 'performance',
        '--tb=short',
        '--durations=0'
    ]
    
    run_command(command, "성능 테스트 실행")


def run_app_tests(app_name):
    """특정 앱 테스트 실행"""
    command = [
        'python', '-m', 'pytest',
        f'tests/test_{app_name}.py',
        '--tb=short'
    ]
    
    run_command(command, f"{app_name} 앱 테스트 실행")


def run_coverage_tests():
    """커버리지 포함 테스트 실행"""
    command = [
        'python', '-m', 'pytest',
        'tests/',
        '--cov=.',
        '--cov-report=html:test_results/coverage_html',
        '--cov-report=xml:test_results/coverage.xml',
        '--cov-report=term-missing',
        '--tb=short'
    ]
    
    run_command(command, "커버리지 테스트 실행")


def run_fast_tests():
    """빠른 테스트 실행 (느린 테스트 제외)"""
    command = [
        'python', '-m', 'pytest',
        'tests/',
        '-m', 'not slow',
        '--tb=short'
    ]
    
    run_command(command, "빠른 테스트 실행")


def run_security_tests():
    """보안 테스트 실행"""
    command = [
        'python', '-m', 'pytest',
        'tests/',
        '-m', 'security',
        '--tb=short'
    ]
    
    run_command(command, "보안 테스트 실행")


def generate_test_report():
    """테스트 리포트 생성"""
    print("\n📊 테스트 리포트 생성 중...")
    
    # JUnit XML 리포트
    command = [
        'python', '-m', 'pytest',
        'tests/',
        '--junitxml=test_results/junit.xml',
        '--tb=short'
    ]
    
    run_command(command, "JUnit XML 리포트 생성")
    
    # 커버리지 리포트
    run_coverage_tests()
    
    print("\n📋 생성된 리포트:")
    print("- HTML 커버리지: test_results/coverage_html/index.html")
    print("- XML 커버리지: test_results/coverage.xml")
    print("- JUnit XML: test_results/junit.xml")


def check_test_quality():
    """테스트 품질 검사"""
    print("\n🔍 테스트 품질 검사 중...")
    
    # 테스트 파일 수 체크
    test_files = list(Path('tests').glob('test_*.py'))
    print(f"📁 테스트 파일 수: {len(test_files)}")
    
    # 각 앱별 테스트 존재 여부 체크
    apps = ['accounts', 'study', 'quiz', 'subscription', 'notifications']
    missing_tests = []
    
    for app in apps:
        test_file = Path(f'tests/test_{app}.py')
        if not test_file.exists():
            missing_tests.append(app)
    
    if missing_tests:
        print(f"⚠️  누락된 테스트: {', '.join(missing_tests)}")
    else:
        print("✅ 모든 앱에 테스트가 존재합니다")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='StudyMate API 테스트 실행기')
    
    parser.add_argument(
        '--type',
        choices=['all', 'unit', 'integration', 'api', 'performance', 'fast', 'security'],
        default='all',
        help='실행할 테스트 타입'
    )
    
    parser.add_argument(
        '--app',
        choices=['accounts', 'study', 'quiz', 'subscription', 'notifications'],
        help='특정 앱 테스트 실행'
    )
    
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='커버리지 포함 실행'
    )
    
    parser.add_argument(
        '--report',
        action='store_true',
        help='테스트 리포트 생성'
    )
    
    parser.add_argument(
        '--quality',
        action='store_true',
        help='테스트 품질 검사'
    )
    
    args = parser.parse_args()
    
    # 테스트 환경 설정
    setup_test_environment()
    
    try:
        if args.quality:
            check_test_quality()
        
        if args.report:
            generate_test_report()
        elif args.coverage:
            run_coverage_tests()
        elif args.app:
            run_app_tests(args.app)
        elif args.type == 'unit':
            run_unit_tests()
        elif args.type == 'integration':
            run_integration_tests()
        elif args.type == 'api':
            run_api_tests()
        elif args.type == 'performance':
            run_performance_tests()
        elif args.type == 'fast':
            run_fast_tests()
        elif args.type == 'security':
            run_security_tests()
        else:
            run_all_tests()
        
        print(f"\n🎉 테스트 완료!")
        
    except KeyboardInterrupt:
        print(f"\n⏸️  테스트가 중단되었습니다.")
        sys.exit(1)


if __name__ == '__main__':
    main()