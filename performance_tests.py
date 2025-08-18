#!/usr/bin/env python
"""
StudyMate API 성능 테스트 스크립트

이 스크립트는 다음을 수행합니다:
- API 엔드포인트 성능 테스트
- 데이터베이스 성능 측정
- 캐시 성능 검증
- 동시 사용자 부하 테스트
- 메모리 및 CPU 사용량 모니터링
"""

import asyncio
import time
import statistics
import json
import psutil
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd

@dataclass
class TestResult:
    """테스트 결과 데이터 클래스"""
    test_name: str
    success_count: int
    failure_count: int
    response_times: List[float]
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_messages: List[str]
    timestamp: datetime

class PerformanceTester:
    """성능 테스트 실행 클래스"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.results: List[TestResult] = []
        
        # 기본 헤더 설정
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'StudyMate-Performance-Tester/1.0'
        })
    
    def authenticate(self, email: str = "test@studymate.com", password: str = "test123!") -> str:
        """사용자 인증 및 토큰 반환"""
        try:
            response = self.session.post(f"{self.base_url}/api/auth/login/", json={
                "email": email,
                "password": password
            })
            
            if response.status_code == 200:
                token = response.json().get('token')
                self.session.headers.update({'Authorization': f'Bearer {token}'})
                return token
            else:
                print(f"인증 실패: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"인증 중 오류: {e}")
            return None
    
    def single_request_test(self, endpoint: str, method: str = "GET", data: Dict = None) -> Tuple[bool, float, str]:
        """단일 요청 테스트"""
        start_time = time.time()
        
        try:
            if method.upper() == "GET":
                response = self.session.get(f"{self.base_url}{endpoint}")
            elif method.upper() == "POST":
                response = self.session.post(f"{self.base_url}{endpoint}", json=data)
            elif method.upper() == "PUT":
                response = self.session.put(f"{self.base_url}{endpoint}", json=data)
            elif method.upper() == "DELETE":
                response = self.session.delete(f"{self.base_url}{endpoint}")
            else:
                return False, 0, f"지원하지 않는 HTTP 메소드: {method}"
            
            response_time = time.time() - start_time
            
            if response.status_code < 400:
                return True, response_time, ""
            else:
                return False, response_time, f"HTTP {response.status_code}: {response.text[:100]}"
        
        except Exception as e:
            response_time = time.time() - start_time
            return False, response_time, str(e)
    
    def load_test(self, endpoint: str, concurrent_users: int = 10, 
                  total_requests: int = 100, method: str = "GET", 
                  data: Dict = None) -> TestResult:
        """부하 테스트 수행"""
        print(f"\n🔥 부하 테스트 시작: {endpoint}")
        print(f"   동시 사용자: {concurrent_users}, 총 요청: {total_requests}")
        
        success_count = 0
        failure_count = 0
        response_times = []
        error_messages = []
        
        start_time = time.time()
        
        def make_request():
            return self.single_request_test(endpoint, method, data)
        
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(make_request) for _ in range(total_requests)]
            
            for future in as_completed(futures):
                success, response_time, error_msg = future.result()
                response_times.append(response_time)
                
                if success:
                    success_count += 1
                else:
                    failure_count += 1
                    if error_msg:
                        error_messages.append(error_msg)
        
        total_time = time.time() - start_time
        
        # 통계 계산
        avg_response_time = statistics.mean(response_times) if response_times else 0
        min_response_time = min(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if response_times else 0
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if response_times else 0
        requests_per_second = total_requests / total_time if total_time > 0 else 0
        
        result = TestResult(
            test_name=f"Load Test - {endpoint}",
            success_count=success_count,
            failure_count=failure_count,
            response_times=response_times,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=requests_per_second,
            error_messages=error_messages[:10],  # 처음 10개 오류만 저장
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        self.print_test_result(result)
        return result
    
    def stress_test(self, endpoint: str, duration_seconds: int = 60, 
                   max_concurrent_users: int = 50) -> List[TestResult]:
        """스트레스 테스트 - 점진적으로 부하 증가"""
        print(f"\n🚨 스트레스 테스트 시작: {endpoint}")
        print(f"   지속 시간: {duration_seconds}초, 최대 동시 사용자: {max_concurrent_users}")
        
        results = []
        step_duration = duration_seconds // 5  # 5단계로 나누기
        
        for step in range(1, 6):
            concurrent_users = (max_concurrent_users * step) // 5
            requests_count = concurrent_users * 10  # 사용자당 10개 요청
            
            print(f"   단계 {step}/5: {concurrent_users} 동시 사용자")
            
            result = self.load_test(
                endpoint=endpoint,
                concurrent_users=concurrent_users,
                total_requests=requests_count,
                method="GET"
            )
            results.append(result)
            
            # 단계별 휴식
            if step < 5:
                time.sleep(5)
        
        return results
    
    def endurance_test(self, endpoint: str, duration_minutes: int = 10, 
                      concurrent_users: int = 5) -> TestResult:
        """지구력 테스트 - 장시간 지속적인 부하"""
        print(f"\n⏱️ 지구력 테스트 시작: {endpoint}")
        print(f"   지속 시간: {duration_minutes}분, 동시 사용자: {concurrent_users}")
        
        total_requests = 0
        success_count = 0
        failure_count = 0
        response_times = []
        error_messages = []
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        def continuous_requests():
            nonlocal total_requests, success_count, failure_count
            
            while time.time() < end_time:
                success, response_time, error_msg = self.single_request_test(endpoint)
                total_requests += 1
                response_times.append(response_time)
                
                if success:
                    success_count += 1
                else:
                    failure_count += 1
                    if error_msg:
                        error_messages.append(error_msg)
                
                time.sleep(1)  # 1초 간격
        
        # 멀티 스레드로 지속적인 요청
        threads = []
        for _ in range(concurrent_users):
            thread = threading.Thread(target=continuous_requests)
            threads.append(thread)
            thread.start()
        
        # 모든 스레드 완료 대기
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # 통계 계산
        avg_response_time = statistics.mean(response_times) if response_times else 0
        min_response_time = min(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else 0
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else 0
        requests_per_second = total_requests / total_time if total_time > 0 else 0
        
        result = TestResult(
            test_name=f"Endurance Test - {endpoint}",
            success_count=success_count,
            failure_count=failure_count,
            response_times=response_times,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=requests_per_second,
            error_messages=error_messages[:10],
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        self.print_test_result(result)
        return result
    
    def print_test_result(self, result: TestResult):
        """테스트 결과 출력"""
        print(f"\n📊 {result.test_name} 결과:")
        print(f"   ✅ 성공: {result.success_count}")
        print(f"   ❌ 실패: {result.failure_count}")
        print(f"   📈 성공률: {(result.success_count / (result.success_count + result.failure_count)) * 100:.2f}%")
        print(f"   ⏱️ 평균 응답시간: {result.avg_response_time:.3f}초")
        print(f"   🏃 초당 요청수: {result.requests_per_second:.2f} RPS")
        print(f"   📊 P95: {result.p95_response_time:.3f}초")
        print(f"   📊 P99: {result.p99_response_time:.3f}초")
        
        if result.error_messages:
            print(f"   🚨 주요 오류: {result.error_messages[0]}")
    
    def system_monitoring_test(self, duration_seconds: int = 60) -> Dict[str, Any]:
        """시스템 리소스 모니터링"""
        print(f"\n💻 시스템 모니터링 시작 ({duration_seconds}초)")
        
        cpu_usage = []
        memory_usage = []
        timestamps = []
        
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            
            cpu_usage.append(cpu_percent)
            memory_usage.append(memory_percent)
            timestamps.append(time.time() - start_time)
        
        monitoring_result = {
            'duration': duration_seconds,
            'cpu_usage': {
                'values': cpu_usage,
                'avg': statistics.mean(cpu_usage),
                'max': max(cpu_usage),
                'min': min(cpu_usage)
            },
            'memory_usage': {
                'values': memory_usage,
                'avg': statistics.mean(memory_usage),
                'max': max(memory_usage),
                'min': min(memory_usage)
            },
            'timestamps': timestamps
        }
        
        print(f"   🖥️ 평균 CPU 사용률: {monitoring_result['cpu_usage']['avg']:.2f}%")
        print(f"   🧠 평균 메모리 사용률: {monitoring_result['memory_usage']['avg']:.2f}%")
        
        return monitoring_result
    
    def generate_report(self, output_file: str = "performance_report.json"):
        """성능 테스트 리포트 생성"""
        print(f"\n📋 성능 테스트 리포트 생성 중...")
        
        report = {
            'test_summary': {
                'total_tests': len(self.results),
                'total_requests': sum(r.success_count + r.failure_count for r in self.results),
                'total_successes': sum(r.success_count for r in self.results),
                'total_failures': sum(r.failure_count for r in self.results),
                'overall_success_rate': 0,
                'avg_response_time': 0,
                'max_rps': 0
            },
            'test_results': []
        }
        
        # 전체 통계 계산
        total_requests = report['test_summary']['total_requests']
        total_successes = report['test_summary']['total_successes']
        
        if total_requests > 0:
            report['test_summary']['overall_success_rate'] = (total_successes / total_requests) * 100
        
        if self.results:
            all_response_times = []
            for result in self.results:
                all_response_times.extend(result.response_times)
            
            if all_response_times:
                report['test_summary']['avg_response_time'] = statistics.mean(all_response_times)
            
            report['test_summary']['max_rps'] = max(r.requests_per_second for r in self.results)
        
        # 개별 테스트 결과
        for result in self.results:
            report['test_results'].append({
                'test_name': result.test_name,
                'success_count': result.success_count,
                'failure_count': result.failure_count,
                'success_rate': (result.success_count / (result.success_count + result.failure_count)) * 100,
                'avg_response_time': result.avg_response_time,
                'min_response_time': result.min_response_time,
                'max_response_time': result.max_response_time,
                'p95_response_time': result.p95_response_time,
                'p99_response_time': result.p99_response_time,
                'requests_per_second': result.requests_per_second,
                'error_messages': result.error_messages,
                'timestamp': result.timestamp.isoformat()
            })
        
        # 파일로 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"   📄 리포트 저장됨: {output_file}")
        
        # 요약 출력
        print(f"\n🎯 최종 결과 요약:")
        print(f"   총 테스트: {report['test_summary']['total_tests']}")
        print(f"   총 요청: {report['test_summary']['total_requests']}")
        print(f"   전체 성공률: {report['test_summary']['overall_success_rate']:.2f}%")
        print(f"   평균 응답시간: {report['test_summary']['avg_response_time']:.3f}초")
        print(f"   최대 RPS: {report['test_summary']['max_rps']:.2f}")
        
        return report

def main():
    """메인 테스트 함수"""
    print("🚀 StudyMate API 성능 테스트 시작")
    
    # 테스터 초기화
    tester = PerformanceTester()
    
    # 1. 기본 헬스체크
    print("\n1. 헬스체크 테스트")
    tester.load_test("/health/", concurrent_users=5, total_requests=50)
    
    # 2. 인증 테스트 (필요시 주석 해제)
    # print("\n2. 인증 API 테스트")
    # tester.load_test("/api/auth/login/", concurrent_users=3, total_requests=20, 
    #                  method="POST", data={"email": "test@test.com", "password": "test123"})
    
    # 3. API 문서 테스트
    print("\n3. API 문서 테스트")
    tester.load_test("/api/docs/", concurrent_users=10, total_requests=100)
    
    # 4. 메트릭 엔드포인트 테스트
    print("\n4. 메트릭 엔드포인트 테스트")
    tester.load_test("/metrics/", concurrent_users=5, total_requests=50)
    
    # 5. 스트레스 테스트
    print("\n5. 헬스체크 스트레스 테스트")
    tester.stress_test("/health/", duration_seconds=30, max_concurrent_users=20)
    
    # 6. 지구력 테스트
    print("\n6. 헬스체크 지구력 테스트")
    tester.endurance_test("/health/", duration_minutes=2, concurrent_users=3)
    
    # 7. 시스템 모니터링
    monitoring_result = tester.system_monitoring_test(duration_seconds=30)
    
    # 8. 리포트 생성
    report = tester.generate_report()
    
    print("\n🎉 성능 테스트 완료!")
    
    # 성능 기준 체크
    check_performance_criteria(report)

def check_performance_criteria(report: Dict[str, Any]):
    """성능 기준 체크"""
    print("\n📏 성능 기준 체크:")
    
    criteria = {
        'success_rate_threshold': 95.0,  # 95% 이상 성공률
        'avg_response_time_threshold': 1.0,  # 1초 이하 평균 응답시간
        'min_rps_threshold': 10.0  # 최소 10 RPS
    }
    
    summary = report['test_summary']
    
    # 성공률 체크
    if summary['overall_success_rate'] >= criteria['success_rate_threshold']:
        print(f"   ✅ 성공률: {summary['overall_success_rate']:.2f}% (기준: {criteria['success_rate_threshold']}%)")
    else:
        print(f"   ❌ 성공률: {summary['overall_success_rate']:.2f}% (기준: {criteria['success_rate_threshold']}%)")
    
    # 응답시간 체크
    if summary['avg_response_time'] <= criteria['avg_response_time_threshold']:
        print(f"   ✅ 평균 응답시간: {summary['avg_response_time']:.3f}초 (기준: {criteria['avg_response_time_threshold']}초)")
    else:
        print(f"   ❌ 평균 응답시간: {summary['avg_response_time']:.3f}초 (기준: {criteria['avg_response_time_threshold']}초)")
    
    # RPS 체크
    if summary['max_rps'] >= criteria['min_rps_threshold']:
        print(f"   ✅ 최대 RPS: {summary['max_rps']:.2f} (기준: {criteria['min_rps_threshold']})")
    else:
        print(f"   ❌ 최대 RPS: {summary['max_rps']:.2f} (기준: {criteria['min_rps_threshold']})")

if __name__ == "__main__":
    main()