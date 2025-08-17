"""
Django management command for log analysis and error monitoring

Usage: python manage.py analyze_logs [options]
"""

import os
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from typing import Dict, List, Any, Optional


class Command(BaseCommand):
    help = 'Analyze application logs and generate reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--log-file',
            type=str,
            help='Specific log file to analyze',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Number of days to analyze (default: 1)',
        )
        parser.add_argument(
            '--log-type',
            type=str,
            choices=['errors', 'performance', 'security', 'business_metrics', 'all'],
            default='all',
            help='Type of logs to analyze',
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['summary', 'detailed', 'json'],
            default='summary',
            help='Output format',
        )
        parser.add_argument(
            '--top',
            type=int,
            default=10,
            help='Number of top items to show in reports',
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export report to file',
        )

    def handle(self, *args, **options):
        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        
        if not os.path.exists(log_dir):
            raise CommandError(f"Log directory does not exist: {log_dir}")
        
        analyzer = LogAnalyzer(log_dir, options)
        report = analyzer.analyze()
        
        # Output report
        if options['format'] == 'json':
            output = json.dumps(report, indent=2, default=str)
        elif options['format'] == 'detailed':
            output = self.format_detailed_report(report)
        else:
            output = self.format_summary_report(report)
        
        # Export or print
        if options['export']:
            with open(options['export'], 'w') as f:
                f.write(output)
            self.stdout.write(
                self.style.SUCCESS(f"Report exported to {options['export']}")
            )
        else:
            self.stdout.write(output)

    def format_summary_report(self, report: Dict[str, Any]) -> str:
        """Format summary report"""
        lines = []
        lines.append("=" * 60)
        lines.append("STUDYMATE LOG ANALYSIS SUMMARY")
        lines.append("=" * 60)
        lines.append(f"Analysis Period: {report['period']['start']} to {report['period']['end']}")
        lines.append(f"Total Log Entries: {report['summary']['total_entries']:,}")
        lines.append("")
        
        # Error Analysis
        if 'errors' in report:
            lines.append("🚨 ERROR ANALYSIS")
            lines.append("-" * 20)
            lines.append(f"Total Errors: {report['errors']['total_count']:,}")
            lines.append(f"Unique Error Types: {len(report['errors']['by_type'])}")
            lines.append("")
            
            lines.append("Top Error Types:")
            for error_type, count in report['errors']['top_errors'][:5]:
                lines.append(f"  {error_type}: {count:,}")
            lines.append("")
        
        # Performance Analysis
        if 'performance' in report:
            lines.append("⚡ PERFORMANCE ANALYSIS")
            lines.append("-" * 25)
            lines.append(f"Total Requests: {report['performance']['total_requests']:,}")
            lines.append(f"Average Response Time: {report['performance']['avg_response_time']:.2f}ms")
            lines.append(f"Slow Requests (>1s): {report['performance']['slow_requests']:,}")
            lines.append("")
            
            lines.append("Slowest Endpoints:")
            for endpoint, avg_time in report['performance']['slowest_endpoints'][:5]:
                lines.append(f"  {endpoint}: {avg_time:.2f}ms")
            lines.append("")
        
        # Security Analysis
        if 'security' in report:
            lines.append("🔒 SECURITY ANALYSIS")
            lines.append("-" * 20)
            lines.append(f"Security Events: {report['security']['total_events']:,}")
            lines.append(f"Suspicious IPs: {len(report['security']['suspicious_ips'])}")
            lines.append("")
        
        # Business Metrics
        if 'business_metrics' in report:
            lines.append("📊 BUSINESS METRICS")
            lines.append("-" * 20)
            for metric, value in report['business_metrics']['key_metrics'].items():
                lines.append(f"  {metric}: {value:,}")
            lines.append("")
        
        return "\n".join(lines)

    def format_detailed_report(self, report: Dict[str, Any]) -> str:
        """Format detailed report"""
        lines = []
        lines.append("=" * 80)
        lines.append("STUDYMATE DETAILED LOG ANALYSIS")
        lines.append("=" * 80)
        lines.append(f"Analysis Period: {report['period']['start']} to {report['period']['end']}")
        lines.append(f"Total Log Entries Analyzed: {report['summary']['total_entries']:,}")
        lines.append("")
        
        # Detailed error analysis
        if 'errors' in report:
            lines.append("🚨 DETAILED ERROR ANALYSIS")
            lines.append("=" * 40)
            lines.append(f"Total Errors: {report['errors']['total_count']:,}")
            lines.append(f"Error Rate: {report['errors']['error_rate']:.2f}%")
            lines.append("")
            
            lines.append("Error Distribution by Type:")
            for error_type, count in report['errors']['by_type'].items():
                percentage = (count / report['errors']['total_count']) * 100
                lines.append(f"  {error_type}: {count:,} ({percentage:.1f}%)")
            lines.append("")
            
            lines.append("Error Timeline (hourly):")
            for hour, count in sorted(report['errors']['hourly_distribution'].items()):
                lines.append(f"  {hour}:00 - {count:,} errors")
            lines.append("")
        
        # Detailed performance analysis
        if 'performance' in report:
            lines.append("⚡ DETAILED PERFORMANCE ANALYSIS")
            lines.append("=" * 45)
            lines.append(f"Total Requests: {report['performance']['total_requests']:,}")
            lines.append(f"Average Response Time: {report['performance']['avg_response_time']:.2f}ms")
            lines.append(f"95th Percentile: {report['performance']['p95_response_time']:.2f}ms")
            lines.append(f"99th Percentile: {report['performance']['p99_response_time']:.2f}ms")
            lines.append("")
            
            lines.append("Response Time Distribution:")
            for range_name, count in report['performance']['response_time_distribution'].items():
                percentage = (count / report['performance']['total_requests']) * 100
                lines.append(f"  {range_name}: {count:,} ({percentage:.1f}%)")
            lines.append("")
        
        return "\n".join(lines)


class LogAnalyzer:
    """Log file analyzer"""
    
    def __init__(self, log_dir: str, options: Dict[str, Any]):
        self.log_dir = log_dir
        self.options = options
        self.days = options.get('days', 1)
        self.log_type = options.get('log_type', 'all')
        self.top_count = options.get('top', 10)
        
        # Calculate date range
        self.end_date = timezone.now()
        self.start_date = self.end_date - timedelta(days=self.days)
    
    def analyze(self) -> Dict[str, Any]:
        """Perform log analysis"""
        report = {
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'days': self.days
            },
            'summary': {
                'total_entries': 0,
                'files_analyzed': []
            }
        }
        
        # Analyze different log types
        if self.log_type in ['errors', 'all']:
            report['errors'] = self.analyze_errors()
        
        if self.log_type in ['performance', 'all']:
            report['performance'] = self.analyze_performance()
        
        if self.log_type in ['security', 'all']:
            report['security'] = self.analyze_security()
        
        if self.log_type in ['business_metrics', 'all']:
            report['business_metrics'] = self.analyze_business_metrics()
        
        return report
    
    def analyze_errors(self) -> Dict[str, Any]:
        """Analyze error logs"""
        error_file = os.path.join(self.log_dir, 'errors.log')
        
        if not os.path.exists(error_file):
            return {'error': 'Error log file not found'}
        
        errors_by_type = Counter()
        errors_by_hour = defaultdict(int)
        total_errors = 0
        error_details = []
        
        with open(error_file, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    entry_time = datetime.fromisoformat(log_entry['timestamp'].replace('Z', '+00:00'))
                    
                    if self.start_date <= entry_time <= self.end_date:
                        total_errors += 1
                        
                        # Extract error type
                        error_type = log_entry.get('logger', 'unknown')
                        errors_by_type[error_type] += 1
                        
                        # Group by hour
                        hour_key = entry_time.strftime('%Y-%m-%d %H')
                        errors_by_hour[hour_key] += 1
                        
                        # Store error details
                        error_details.append({
                            'timestamp': log_entry['timestamp'],
                            'type': error_type,
                            'message': log_entry.get('message', ''),
                            'module': log_entry.get('module', ''),
                            'function': log_entry.get('function', ''),
                        })
                
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return {
            'total_count': total_errors,
            'error_rate': 0.0,  # Would calculate based on total requests
            'by_type': dict(errors_by_type),
            'top_errors': errors_by_type.most_common(self.top_count),
            'hourly_distribution': dict(errors_by_hour),
            'recent_errors': error_details[-self.top_count:] if error_details else []
        }
    
    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze performance logs"""
        perf_file = os.path.join(self.log_dir, 'performance.log')
        
        if not os.path.exists(perf_file):
            return {'error': 'Performance log file not found'}
        
        response_times = []
        requests_by_endpoint = defaultdict(list)
        slow_requests = 0
        total_requests = 0
        
        with open(perf_file, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    entry_time = datetime.fromisoformat(log_entry['timestamp'].replace('Z', '+00:00'))
                    
                    if self.start_date <= entry_time <= self.end_date:
                        duration = log_entry.get('duration_ms', 0)
                        endpoint = log_entry.get('request_path', 'unknown')
                        
                        total_requests += 1
                        response_times.append(duration)
                        requests_by_endpoint[endpoint].append(duration)
                        
                        if duration > 1000:  # Slow request threshold
                            slow_requests += 1
                
                except (json.JSONDecodeError, KeyError):
                    continue
        
        # Calculate statistics
        if response_times:
            response_times.sort()
            avg_response_time = sum(response_times) / len(response_times)
            p95_index = int(len(response_times) * 0.95)
            p99_index = int(len(response_times) * 0.99)
            p95_response_time = response_times[p95_index] if p95_index < len(response_times) else 0
            p99_response_time = response_times[p99_index] if p99_index < len(response_times) else 0
        else:
            avg_response_time = p95_response_time = p99_response_time = 0
        
        # Calculate slowest endpoints
        slowest_endpoints = []
        for endpoint, times in requests_by_endpoint.items():
            if times:
                avg_time = sum(times) / len(times)
                slowest_endpoints.append((endpoint, avg_time))
        slowest_endpoints.sort(key=lambda x: x[1], reverse=True)
        
        # Response time distribution
        response_time_distribution = {
            '< 100ms': len([t for t in response_times if t < 100]),
            '100-500ms': len([t for t in response_times if 100 <= t < 500]),
            '500ms-1s': len([t for t in response_times if 500 <= t < 1000]),
            '1-5s': len([t for t in response_times if 1000 <= t < 5000]),
            '> 5s': len([t for t in response_times if t >= 5000]),
        }
        
        return {
            'total_requests': total_requests,
            'avg_response_time': avg_response_time,
            'p95_response_time': p95_response_time,
            'p99_response_time': p99_response_time,
            'slow_requests': slow_requests,
            'slowest_endpoints': slowest_endpoints[:self.top_count],
            'response_time_distribution': response_time_distribution
        }
    
    def analyze_security(self) -> Dict[str, Any]:
        """Analyze security logs"""
        security_file = os.path.join(self.log_dir, 'security.log')
        
        if not os.path.exists(security_file):
            return {'error': 'Security log file not found'}
        
        events_by_type = Counter()
        suspicious_ips = set()
        total_events = 0
        
        with open(security_file, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    entry_time = datetime.fromisoformat(log_entry['timestamp'].replace('Z', '+00:00'))
                    
                    if self.start_date <= entry_time <= self.end_date:
                        total_events += 1
                        
                        event_type = log_entry.get('event', 'unknown')
                        events_by_type[event_type] += 1
                        
                        ip_address = log_entry.get('ip_address')
                        if ip_address and event_type in ['suspicious_request_content', 'potential_attack_detected']:
                            suspicious_ips.add(ip_address)
                
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return {
            'total_events': total_events,
            'events_by_type': dict(events_by_type),
            'top_events': events_by_type.most_common(self.top_count),
            'suspicious_ips': list(suspicious_ips),
            'suspicious_ip_count': len(suspicious_ips)
        }
    
    def analyze_business_metrics(self) -> Dict[str, Any]:
        """Analyze business metrics logs"""
        metrics_file = os.path.join(self.log_dir, 'business_metrics.log')
        
        if not os.path.exists(metrics_file):
            return {'error': 'Business metrics log file not found'}
        
        metrics_by_type = defaultdict(list)
        total_metrics = 0
        
        with open(metrics_file, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    entry_time = datetime.fromisoformat(log_entry['timestamp'].replace('Z', '+00:00'))
                    
                    if self.start_date <= entry_time <= self.end_date:
                        total_metrics += 1
                        
                        metric_name = log_entry.get('metric', 'unknown')
                        metric_value = log_entry.get('value', 0)
                        
                        metrics_by_type[metric_name].append(metric_value)
                
                except (json.JSONDecodeError, KeyError):
                    continue
        
        # Calculate aggregated metrics
        key_metrics = {}
        for metric_name, values in metrics_by_type.items():
            if values:
                key_metrics[metric_name] = {
                    'total': sum(values),
                    'average': sum(values) / len(values),
                    'count': len(values)
                }
        
        return {
            'total_metric_entries': total_metrics,
            'metrics_tracked': len(metrics_by_type),
            'key_metrics': {k: v['total'] for k, v in key_metrics.items()},
            'detailed_metrics': key_metrics
        }