from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from rest_framework.response import Response
from collections import OrderedDict


class SubscriptionPagination(PageNumberPagination):
    """Standard pagination for Subscription app"""
    
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


class SubscriptionSmallPagination(PageNumberPagination):
    """Smaller pagination for subscription summaries"""
    
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'page'


class PaymentPagination(PageNumberPagination):
    """Pagination for payment history"""
    
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """Enhanced payment pagination with financial summary"""
        # Calculate totals for current page
        page_total = 0
        successful_total = 0
        refunded_total = 0
        
        for item in data:
            if isinstance(item, dict):
                amount = item.get('amount', 0)
                status = item.get('status', '')
                refund_amount = item.get('refund_amount', 0)
                
                page_total += amount
                if status == 'succeeded':
                    successful_total += amount
                refunded_total += refund_amount
        
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
                ('page_total', page_total),
                ('successful_total', successful_total),
                ('refunded_total', refunded_total),
                ('net_total', successful_total - refunded_total),
            ])),
            ('results', data)
        ]))


class DiscountPagination(PageNumberPagination):
    """Pagination for discounts"""
    
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'page'


class UsageCreditPagination(PageNumberPagination):
    """Pagination for usage credits"""
    
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """Enhanced credit pagination with usage summary"""
        # Calculate credit totals for current page
        total_credits = 0
        used_credits = 0
        remaining_credits = 0
        unlimited_count = 0
        
        for item in data:
            if isinstance(item, dict):
                if item.get('is_unlimited', False):
                    unlimited_count += 1
                else:
                    total_credits += item.get('total_credits', 0) + item.get('bonus_credits', 0)
                    used_credits += item.get('used_credits', 0)
                    remaining_credits += item.get('remaining_credits', 0)
        
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
                ('total_credits', total_credits),
                ('used_credits', used_credits),
                ('remaining_credits', remaining_credits),
                ('unlimited_count', unlimited_count),
                ('usage_percentage', (used_credits / total_credits * 100) if total_credits > 0 else 0),
            ])),
            ('results', data)
        ]))


class AnalyticsPagination(LimitOffsetPagination):
    """Pagination for analytics data"""
    
    default_limit = 50
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 200
    
    def get_paginated_response(self, data):
        """Analytics pagination with metadata"""
        return Response(OrderedDict([
            ('pagination', OrderedDict([
                ('links', OrderedDict([
                    ('next', self.get_next_link()),
                    ('previous', self.get_previous_link())
                ])),
                ('count', self.count),
                ('limit', self.limit),
                ('offset', self.offset),
            ])),
            ('results', data)
        ]))


class DashboardPagination(PageNumberPagination):
    """Pagination for dashboard views"""
    
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 25
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """Simplified pagination for dashboard"""
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))