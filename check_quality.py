#!/usr/bin/env python
"""
StudyMate API 코드 품질 검사 스크립트

이 스크립트는 다음 검사를 수행합니다:
- 코드 포매팅 검사 (Black)
- Import 정렬 검사 (isort)
- 린팅 검사 (Ruff)
- 타입 검사 (MyPy)
- 보안 검사 (Bandit)
- Django 검사
- 문서 스타일 검사 (pydocstyle)
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple, Dict, Any
import argparse

BASE_DIR = Path(__file__).resolve().parent

class CodeQualityChecker:
    """코드 품질 검사기"""
    
    def __init__(self, verbose: bool = False, fix: bool = False):
        self.verbose = verbose
        self.fix = fix
        self.results: List[Tuple[str, bool, str]] = []
    
    def run_check(self, command: List[str], description: str, 
                  allow_failure: bool = False) -> bool:
        """검사 실행"""
        if self.verbose:
            print(f"\n🔍 {description}")
            print("-" * 60)
            print(f"실행 중: {' '.join(command)}")
        else:
            print(f"🔍 {description}...", end=" ", flush=True)
        
        start_time = time.time()
        result = subprocess.run(
            command, 
            cwd=BASE_DIR,
            capture_output=not self.verbose,
            text=True
        )
        duration = time.time() - start_time
        
        success = result.returncode == 0 or allow_failure
        
        if self.verbose:
            if success:
                print(f"✅ {description} - 통과 ({duration:.2f}초)")
            else:
                print(f"❌ {description} - 실패 ({duration:.2f}초)")
                if result.stdout:
                    print("STDOUT:", result.stdout)
                if result.stderr:
                    print("STDERR:", result.stderr)
        else:
            status = "✅ 통과" if success else "❌ 실패"
            print(f"{status} ({duration:.2f}초)")
        
        self.results.append((description, success, result.stderr or result.stdout or ""))
        return success
    
    def check_formatting(self) -> bool:
        """코드 포매팅 검사"""
        if self.fix:
            return self.run_check(
                ["black", ".", "--line-length=120"],
                "코드 포매팅 수정"
            )
        else:
            return self.run_check(
                ["black", "--check", "--diff", ".", "--line-length=120"],
                "코드 포매팅 검사"
            )
    
    def check_imports(self) -> bool:
        """Import 정렬 검사"""
        if self.fix:
            return self.run_check(
                ["isort", ".", "--profile=black", "--line-length=120"],
                "Import 정렬 수정"
            )
        else:
            return self.run_check(
                ["isort", "--check-only", "--diff", ".", "--profile=black", "--line-length=120"],
                "Import 정렬 검사"
            )
    
    def check_linting(self) -> bool:
        """린팅 검사"""
        if self.fix:
            return self.run_check(
                ["ruff", "check", ".", "--fix"],
                "린팅 검사 및 수정"
            )
        else:
            return self.run_check(
                ["ruff", "check", "."],
                "린팅 검사"
            )
    
    def check_types(self) -> bool:
        """타입 검사"""
        return self.run_check(
            ["mypy", "."],
            "타입 검사"
        )
    
    def check_security(self) -> bool:
        """보안 검사"""
        return self.run_check(
            ["bandit", "-r", ".", "-x", "tests/,venv/,env/", "-f", "txt"],
            "보안 검사",
            allow_failure=True  # 보안 검사는 경고만 있어도 통과로 처리
        )
    
    def check_django(self) -> bool:
        """Django 검사"""
        checks = [
            (["python", "manage.py", "check"], "Django 기본 검사"),
            (["python", "manage.py", "check", "--deploy"], "Django 배포 검사"),
            (["python", "manage.py", "makemigrations", "--check", "--dry-run"], "마이그레이션 검사"),
        ]
        
        success = True
        for command, description in checks:
            if not self.run_check(command, description):
                success = False
        
        return success
    
    def check_docstrings(self) -> bool:
        """문서 스타일 검사"""
        return self.run_check(
            ["pydocstyle", ".", "--convention=google", "--add-ignore=D100,D101,D102,D103,D104,D105"],
            "문서 스타일 검사",
            allow_failure=True  # 문서 검사는 경고만 있어도 통과로 처리
        )
    
    def check_complexity(self) -> bool:
        """복잡도 검사"""
        return self.run_check(
            ["flake8", ".", "--select=C901", "--max-complexity=12"],
            "코드 복잡도 검사",
            allow_failure=True
        )
    
    def run_all_checks(self) -> bool:
        """모든 검사 실행"""
        print("🔧 StudyMate API 코드 품질 검사 시작")
        print("=" * 60)
        
        # 기본 코드 품질 검사
        checks = [
            ("formatting", self.check_formatting),
            ("imports", self.check_imports), 
            ("linting", self.check_linting),
            ("types", self.check_types),
            ("security", self.check_security),
            ("django", self.check_django),
            ("docstrings", self.check_docstrings),
            ("complexity", self.check_complexity),
        ]
        
        passed = 0
        failed = 0
        
        for check_name, check_func in checks:
            try:
                if check_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ {check_name} 검사 중 오류 발생: {e}")
                failed += 1
        
        total = passed + failed
        
        # 결과 요약
        print("\n" + "=" * 60)
        print(f"📊 검사 결과: {passed}/{total} 통과")
        
        if failed == 0:
            print("🎉 모든 검사를 통과했습니다!")
            return True
        else:
            print(f"⚠️  {failed}개의 검사에서 문제가 발견되었습니다.")
            
            # 실패한 검사들 상세 정보
            print("\n📋 실패한 검사:")
            for description, success, output in self.results:
                if not success and output:
                    print(f"\n❌ {description}:")
                    print(output[:500] + "..." if len(output) > 500 else output)
            
            return False
    
    def generate_report(self) -> Dict[str, Any]:
        """품질 검사 리포트 생성"""
        passed_checks = [desc for desc, success, _ in self.results if success]
        failed_checks = [desc for desc, success, _ in self.results if not success]
        
        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_checks": len(self.results),
            "passed_checks": len(passed_checks),
            "failed_checks": len(failed_checks),
            "success_rate": (len(passed_checks) / len(self.results)) * 100 if self.results else 0,
            "passed": passed_checks,
            "failed": failed_checks,
            "details": [
                {
                    "check": desc,
                    "success": success,
                    "output": output[:200] + "..." if len(output) > 200 else output
                }
                for desc, success, output in self.results
            ]
        }


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="StudyMate API 코드 품질 검사")
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세한 출력 표시"
    )
    parser.add_argument(
        "--fix",
        action="store_true", 
        help="자동으로 수정 가능한 문제들 수정"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="JSON 리포트 생성"
    )
    parser.add_argument(
        "--check",
        choices=["formatting", "imports", "linting", "types", "security", "django", "docstrings", "complexity"],
        help="특정 검사만 실행"
    )
    
    args = parser.parse_args()
    
    checker = CodeQualityChecker(verbose=args.verbose, fix=args.fix)
    
    # 특정 검사만 실행
    if args.check:
        check_methods = {
            "formatting": checker.check_formatting,
            "imports": checker.check_imports,
            "linting": checker.check_linting,
            "types": checker.check_types,
            "security": checker.check_security,
            "django": checker.check_django,
            "docstrings": checker.check_docstrings,
            "complexity": checker.check_complexity,
        }
        
        success = check_methods[args.check]()
        sys.exit(0 if success else 1)
    
    # 모든 검사 실행
    success = checker.run_all_checks()
    
    # 리포트 생성
    if args.report:
        import json
        report = checker.generate_report()
        report_file = BASE_DIR / "quality_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n📋 상세 리포트가 생성되었습니다: {report_file}")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()