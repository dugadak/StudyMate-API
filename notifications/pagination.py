from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from collections import OrderedDict


class NotificationPagination(PageNumberPagination):
    """Standard pagination for Notification app"""
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """Enhanced paginated response with additional metadata"""
        return Response(OrderedDict([
            ('pagination', OrderedDict([
                ('links', OrderedDict([
                    ('next', self.get_next_link()),
                    ('previous', self.get_previous_link())
                ])),
                ('count', self.page.paginator.count),
                ('page_size', self.get_page_size(self.request)),
                ('current_page', self.page.number),
                ('total_pages', self.page.paginator.num_pages),
                ('has_next', self.page.has_next()),
                ('has_previous', self.page.has_previous()),
                ('start_index', self.page.start_index()),
                ('end_index', self.page.end_index()),
            ])),
            ('results', data)
        ]))


class SmallNotificationPagination(PageNumberPagination):
    """Smaller pagination for notification summaries"""
    
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'page'


class BatchPagination(PageNumberPagination):
    """Pagination for notification batches"""
    
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """Enhanced batch pagination with processing summary"""
        # Calculate batch summaries for current page
        total_notifications = 0
        sent_notifications = 0
        failed_notifications = 0
        processing_batches = 0
        
        for item in data:
            if isinstance(item, dict):
                total_notifications += item.get('total_count', 0)
                sent_notifications += item.get('sent_count', 0)
                failed_notifications += item.get('failed_count', 0)
                
                if item.get('status') == 'processing':
                    processing_batches += 1
        
        return Response(OrderedDict([
            ('pagination', OrderedDict([
                ('links', OrderedDict([
                    ('next', self.get_next_link()),
                    ('previous', self.get_previous_link())
                ])),
                ('count', self.page.paginator.count),
                ('page_size', self.get_page_size(self.request)),
                ('current_page', self.page.number),
                ('total_pages', self.page.paginator.num_pages),
                ('has_next', self.page.has_next()),
                ('has_previous', self.page.has_previous()),
            ])),
            ('page_summary', OrderedDict([
                ('total_notifications', total_notifications),
                ('sent_notifications', sent_notifications),
                ('failed_notifications', failed_notifications),
                ('processing_batches', processing_batches),
                ('success_rate', (sent_notifications / total_notifications * 100) if total_notifications > 0 else 0),
            ])),
            ('results', data)
        ]))


class TemplatePagination(PageNumberPagination):
    """Pagination for notification templates"""
    
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'page'


class SchedulePagination(PageNumberPagination):
    """Pagination for notification schedules"""
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """Enhanced schedule pagination with status summary"""
        # Calculate schedule summaries for current page
        active_schedules = 0
        paused_schedules = 0
        due_schedules = 0
        
        for item in data:
            if isinstance(item, dict):
                status = item.get('status', '')
                if status == 'active':
                    active_schedules += 1
                elif status == 'paused':
                    paused_schedules += 1
                
                # Check if due (simplified check)
                if item.get('is_due', False):
                    due_schedules += 1
        
        return Response(OrderedDict([
            ('pagination', OrderedDict([
                ('links', OrderedDict([
                    ('next', self.get_next_link()),
                    ('previous', self.get_previous_link())
                ])),
                ('count', self.page.paginator.count),
                ('page_size', self.get_page_size(self.request)),
                ('current_page', self.page.number),
                ('total_pages', self.page.paginator.num_pages),
                ('has_next', self.page.has_next()),
                ('has_previous', self.page.has_previous()),
            ])),
            ('page_summary', OrderedDict([
                ('active_schedules', active_schedules),
                ('paused_schedules', paused_schedules),
                ('due_schedules', due_schedules),
            ])),
            ('results', data)
        ]))


class DevicePagination(PageNumberPagination):
    """Pagination for device tokens"""
    
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """Enhanced device pagination with health summary"""
        # Calculate device health summaries for current page
        active_devices = 0
        healthy_devices = 0
        primary_devices = 0
        platform_counts = {}
        
        for item in data:
            if isinstance(item, dict):
                if item.get('is_active', False):
                    active_devices += 1
                
                if item.get('is_healthy', True):
                    healthy_devices += 1
                
                if item.get('is_primary', False):
                    primary_devices += 1
                
                platform = item.get('platform', 'unknown')
                platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        return Response(OrderedDict([
            ('pagination', OrderedDict([
                ('links', OrderedDict([
                    ('next', self.get_next_link()),
                    ('previous', self.get_previous_link())
                ])),
                ('count', self.page.paginator.count),
                ('page_size', self.get_page_size(self.request)),
                ('current_page', self.page.number),
                ('total_pages', self.page.paginator.num_pages),
                ('has_next', self.page.has_next()),
                ('has_previous', self.page.has_previous()),
            ])),
            ('page_summary', OrderedDict([
                ('active_devices', active_devices),
                ('healthy_devices', healthy_devices),
                ('primary_devices', primary_devices),
                ('platform_distribution', platform_counts),
            ])),
            ('results', data)
        ]))