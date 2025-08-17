"""
Django management command for cache management
Usage: python manage.py manage_cache [options]
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.utils import timezone
from studymate_api.cache import (
    smart_cache, cache_warmer, cache_invalidator, CacheMonitor, StudyMateCache
)
import json


class Command(BaseCommand):
    help = 'Manage StudyMate caching system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['info', 'warm', 'clear', 'stats', 'test'],
            default='info',
            help='Action to perform',
        )
        parser.add_argument(
            '--cache-type',
            type=str,
            help='Specific cache type to operate on',
        )
        parser.add_argument(
            '--pattern',
            type=str,
            help='Cache key pattern for bulk operations',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID for user-specific operations',
        )

    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'info':
            self.show_cache_info()
        elif action == 'warm':
            self.warm_caches(options.get('cache_type'))
        elif action == 'clear':
            self.clear_caches(options.get('cache_type'), options.get('pattern'))
        elif action == 'stats':
            self.show_statistics()
        elif action == 'test':
            self.test_cache_performance()

    def show_cache_info(self):
        """Display cache information"""
        self.stdout.write(
            self.style.SUCCESS('=== StudyMate Cache Information ===\n')
        )
        
        # Basic cache info
        cache_info = CacheMonitor.get_cache_info()
        self.stdout.write(f"Backend: {cache_info['backend']}")
        self.stdout.write(f"Timestamp: {cache_info['timestamp']}")
        
        # Cache stats
        stats = cache_info['stats']
        self.stdout.write(f"\nCache Statistics:")
        self.stdout.write(f"  Hits: {stats['hits']}")
        self.stdout.write(f"  Misses: {stats['misses']}")
        self.stdout.write(f"  Total Requests: {stats['total_requests']}")
        self.stdout.write(f"  Hit Rate: {stats['hit_rate']}%")
        
        # Cache size
        size_info = CacheMonitor.get_cache_size_estimate()
        if 'total_keys' in size_info:
            self.stdout.write(f"\nCache Size:")
            self.stdout.write(f"  Total Keys: {size_info['total_keys']}")
            self.stdout.write(f"  Estimated Size: {size_info.get('estimated_size_mb', 'N/A')} MB")

    def warm_caches(self, cache_type: str = None):
        """Warm up caches"""
        self.stdout.write(
            self.style.HTTP_INFO('🔥 Warming up caches...\n')
        )
        
        if cache_type:
            # Warm specific cache type
            try:
                cache_warmer.warm_cache(cache_type)
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Cache warming completed for {cache_type}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Cache warming failed for {cache_type}: {str(e)}")
                )
        else:
            # Warm all caches
            try:
                cache_warmer.warm_all_caches()
                self.stdout.write(
                    self.style.SUCCESS("✅ All cache warming completed")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Cache warming failed: {str(e)}")
                )

    def clear_caches(self, cache_type: str = None, pattern: str = None):
        """Clear caches"""
        self.stdout.write(
            self.style.WARNING('🗑️  Clearing caches...\n')
        )
        
        if cache_type and pattern:
            # Clear specific pattern
            deleted_count = smart_cache.delete_pattern(cache_type, pattern)
            self.stdout.write(
                self.style.SUCCESS(f"✅ Deleted {deleted_count} cache entries for {cache_type}:{pattern}")
            )
        elif cache_type:
            # Clear all entries for cache type
            deleted_count = smart_cache.delete_pattern(cache_type)
            self.stdout.write(
                self.style.SUCCESS(f"✅ Deleted {deleted_count} cache entries for {cache_type}")
            )
        else:
            # Clear entire cache
            try:
                cache.clear()
                self.stdout.write(
                    self.style.SUCCESS("✅ Entire cache cleared")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Cache clearing failed: {str(e)}")
                )

    def show_statistics(self):
        """Show detailed cache statistics"""
        self.stdout.write(
            self.style.SUCCESS('=== Cache Performance Statistics ===\n')
        )
        
        # Overall stats
        stats = smart_cache.get_stats()
        self.stdout.write("📊 Overall Performance:")
        self.stdout.write(f"   Hit Rate: {stats['hit_rate']}%")
        self.stdout.write(f"   Total Requests: {stats['total_requests']}")
        self.stdout.write(f"   Cache Hits: {stats['hits']}")
        self.stdout.write(f"   Cache Misses: {stats['misses']}")
        
        # Cache types and their usage
        cache_types = [
            ('User Profiles', StudyMateCache.USER_PROFILE),
            ('Study Statistics', StudyMateCache.STUDY_STATISTICS),
            ('Quiz Results', StudyMateCache.QUIZ_RESULTS),
            ('Subject Data', StudyMateCache.SUBJECT_DATA),
            ('Subscription Status', StudyMateCache.SUBSCRIPTION_STATUS),
            ('Notification Settings', StudyMateCache.NOTIFICATION_SETTINGS),
        ]
        
        self.stdout.write("\n📋 Cache Types:")
        for name, cache_type in cache_types:
            self.stdout.write(f"   {name}: {cache_type}")

    def test_cache_performance(self):
        """Test cache performance"""
        self.stdout.write(
            self.style.HTTP_INFO('🧪 Testing cache performance...\n')
        )
        
        import time
        
        # Test cache operations
        test_data = {'test': 'data', 'timestamp': timezone.now().isoformat()}
        test_key = 'performance_test'
        
        # Test SET operation
        start_time = time.time()
        smart_cache.set('test', test_key, test_data)
        set_time = (time.time() - start_time) * 1000
        
        # Test GET operation
        start_time = time.time()
        retrieved_data = smart_cache.get('test', test_key)
        get_time = (time.time() - start_time) * 1000
        
        # Test DELETE operation
        start_time = time.time()
        smart_cache.delete('test', test_key)
        delete_time = (time.time() - start_time) * 1000
        
        # Results
        self.stdout.write("⏱️  Performance Results:")
        self.stdout.write(f"   SET operation: {set_time:.2f}ms")
        self.stdout.write(f"   GET operation: {get_time:.2f}ms")
        self.stdout.write(f"   DELETE operation: {delete_time:.2f}ms")
        
        # Verify data integrity
        if retrieved_data == test_data:
            self.stdout.write(
                self.style.SUCCESS("✅ Data integrity test passed")
            )
        else:
            self.stdout.write(
                self.style.ERROR("❌ Data integrity test failed")
            )
        
        # Test bulk operations
        self.stdout.write("\n🔄 Testing bulk operations...")
        
        # Set multiple keys
        start_time = time.time()
        for i in range(100):
            smart_cache.set('bulk_test', f'key_{i}', {'data': i})
        bulk_set_time = (time.time() - start_time) * 1000
        
        # Get multiple keys
        start_time = time.time()
        for i in range(100):
            smart_cache.get('bulk_test', f'key_{i}')
        bulk_get_time = (time.time() - start_time) * 1000
        
        # Clean up
        smart_cache.delete_pattern('bulk_test')
        
        self.stdout.write(f"   Bulk SET (100 items): {bulk_set_time:.2f}ms")
        self.stdout.write(f"   Bulk GET (100 items): {bulk_get_time:.2f}ms")
        self.stdout.write(f"   Average SET time: {bulk_set_time/100:.2f}ms per item")
        self.stdout.write(f"   Average GET time: {bulk_get_time/100:.2f}ms per item")
        
        # Performance recommendations
        self.stdout.write("\n💡 Performance Recommendations:")
        
        if set_time > 10:
            self.stdout.write(
                self.style.WARNING("   ⚠️  SET operations are slow (>10ms)")
            )
        
        if get_time > 5:
            self.stdout.write(
                self.style.WARNING("   ⚠️  GET operations are slow (>5ms)")
            )
        
        if bulk_get_time/100 > 2:
            self.stdout.write(
                self.style.WARNING("   ⚠️  Consider implementing batch operations")
            )
        
        hit_rate = smart_cache.get_stats()['hit_rate']
        if hit_rate < 80:
            self.stdout.write(
                self.style.WARNING(f"   ⚠️  Cache hit rate is low ({hit_rate}%)")
            )
        
        self.stdout.write(
            self.style.SUCCESS("\n✅ Performance testing completed")
        )