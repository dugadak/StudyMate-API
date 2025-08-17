"""
Database Optimization Script for StudyMate API

This script analyzes the current database models and provides
recommendations for performance optimization including:
- Index analysis and recommendations
- Query optimization suggestions
- Database schema improvements
- Performance monitoring queries
"""

import os
import django
from django.db import models, connection
from django.apps import apps
from django.core.management import execute_from_command_line
import sys

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'studymate_api.settings')
django.setup()


class DatabaseOptimizer:
    """Database optimization analyzer and recommendations"""
    
    def __init__(self):
        self.models = []
        self.optimization_recommendations = []
        self.index_recommendations = []
        
    def analyze_models(self):
        """Analyze all models for optimization opportunities"""
        print("=== Database Model Analysis ===\n")
        
        for app_config in apps.get_app_configs():
            if app_config.name in ['accounts', 'study', 'quiz', 'subscription', 'notifications']:
                print(f"Analyzing {app_config.name} app models:")
                
                for model in app_config.get_models():
                    self.analyze_model(model)
                print()
    
    def analyze_model(self, model):
        """Analyze individual model for optimization"""
        model_name = f"{model._meta.app_label}.{model._meta.model_name}"
        print(f"  📊 {model_name}")
        
        # Analyze fields
        foreign_keys = []
        many_to_many = []
        indexed_fields = []
        text_fields = []
        datetime_fields = []
        
        for field in model._meta.get_fields():
            if isinstance(field, models.ForeignKey):
                foreign_keys.append(field.name)
            elif isinstance(field, models.ManyToManyField):
                many_to_many.append(field.name)
            elif isinstance(field, (models.TextField, models.CharField)) and hasattr(field, 'max_length'):
                text_fields.append(field.name)
            elif isinstance(field, (models.DateTimeField, models.DateField)):
                datetime_fields.append(field.name)
            
            # Check for existing indexes
            if hasattr(field, 'db_index') and field.db_index:
                indexed_fields.append(field.name)
        
        # Generate recommendations
        self.generate_recommendations(model, foreign_keys, datetime_fields, text_fields)
        
        print(f"    - Foreign Keys: {len(foreign_keys)}")
        print(f"    - DateTime Fields: {len(datetime_fields)}")
        print(f"    - Indexed Fields: {len(indexed_fields)}")
        
    def generate_recommendations(self, model, foreign_keys, datetime_fields, text_fields):
        """Generate optimization recommendations for model"""
        model_name = f"{model._meta.app_label}.{model._meta.model_name}"
        
        # Check for missing indexes on foreign keys
        for fk in foreign_keys:
            self.index_recommendations.append({
                'model': model_name,
                'field': fk,
                'type': 'foreign_key_index',
                'priority': 'high',
                'reason': 'Foreign key without index can cause slow JOINs'
            })
        
        # Check for datetime fields that might need indexes
        for dt_field in datetime_fields:
            if dt_field in ['created_at', 'updated_at', 'expires_at', 'scheduled_at']:
                self.index_recommendations.append({
                    'model': model_name,
                    'field': dt_field,
                    'type': 'datetime_index',
                    'priority': 'medium',
                    'reason': f'DateTime field {dt_field} often used in filtering/ordering'
                })
        
        # Check for composite indexes needed
        if model_name == 'accounts.user':
            self.index_recommendations.append({
                'model': model_name,
                'fields': ['email', 'is_active'],
                'type': 'composite_index',
                'priority': 'high',
                'reason': 'Login queries often filter by email and check is_active'
            })
        
        elif model_name == 'study.studysession':
            self.index_recommendations.append({
                'model': model_name,
                'fields': ['user', 'created_at'],
                'type': 'composite_index',
                'priority': 'high',
                'reason': 'User study history queries need user + date filtering'
            })
        
        elif model_name == 'quiz.quizattempt':
            self.index_recommendations.append({
                'model': model_name,
                'fields': ['user', 'completed_at'],
                'type': 'composite_index',
                'priority': 'high',
                'reason': 'Quiz progress tracking needs user + completion time'
            })
        
        elif model_name == 'subscription.usersubscription':
            self.index_recommendations.append({
                'model': model_name,
                'fields': ['user', 'status', 'expires_at'],
                'type': 'composite_index',
                'priority': 'high',
                'reason': 'Subscription status checks need user + status + expiry'
            })
        
        elif model_name == 'notifications.notification':
            self.index_recommendations.append({
                'model': model_name,
                'fields': ['user', 'status', 'scheduled_at'],
                'type': 'composite_index',
                'priority': 'high',
                'reason': 'Notification queries need user + status + schedule filtering'
            })
    
    def print_recommendations(self):
        """Print all optimization recommendations"""
        print("\n=== Database Optimization Recommendations ===\n")
        
        # Group by priority
        high_priority = [r for r in self.index_recommendations if r.get('priority') == 'high']
        medium_priority = [r for r in self.index_recommendations if r.get('priority') == 'medium']
        
        print("🔴 HIGH PRIORITY OPTIMIZATIONS:")
        for rec in high_priority:
            if 'fields' in rec:
                print(f"  - {rec['model']}: Composite index on {rec['fields']}")
            else:
                print(f"  - {rec['model']}.{rec['field']}: {rec['type']}")
            print(f"    Reason: {rec['reason']}\n")
        
        print("🟡 MEDIUM PRIORITY OPTIMIZATIONS:")
        for rec in medium_priority:
            if 'fields' in rec:
                print(f"  - {rec['model']}: Composite index on {rec['fields']}")
            else:
                print(f"  - {rec['model']}.{rec['field']}: {rec['type']}")
            print(f"    Reason: {rec['reason']}\n")
    
    def generate_migration_commands(self):
        """Generate Django migration commands for optimizations"""
        print("=== Django Migration Commands ===\n")
        
        print("# Run these commands to create optimization migrations:\n")
        
        apps_to_migrate = set()
        for rec in self.index_recommendations:
            app_name = rec['model'].split('.')[0]
            apps_to_migrate.add(app_name)
        
        for app in apps_to_migrate:
            print(f"python manage.py makemigrations {app} --name optimize_database_indexes")
        
        print("\n# After creating migrations, run:")
        print("python manage.py migrate")
    
    def generate_performance_queries(self):
        """Generate SQL queries for performance monitoring"""
        print("\n=== Performance Monitoring Queries ===\n")
        
        queries = [
            {
                'name': 'Slow Query Analysis',
                'sql': """
                -- Enable slow query logging (MySQL)
                SET GLOBAL slow_query_log = 'ON';
                SET GLOBAL long_query_time = 1;
                """
            },
            {
                'name': 'Index Usage Analysis',
                'sql': """
                -- Check unused indexes (PostgreSQL)
                SELECT 
                    schemaname,
                    tablename,
                    attname,
                    n_distinct,
                    correlation
                FROM pg_stats
                WHERE schemaname = 'public'
                ORDER BY n_distinct DESC;
                """
            },
            {
                'name': 'Table Size Analysis',
                'sql': """
                -- Check table sizes (PostgreSQL)
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY size_bytes DESC;
                """
            }
        ]
        
        for query in queries:
            print(f"-- {query['name']}")
            print(query['sql'])
            print()
    
    def run_analysis(self):
        """Run complete database analysis"""
        self.analyze_models()
        self.print_recommendations()
        self.generate_migration_commands()
        self.generate_performance_queries()


if __name__ == "__main__":
    optimizer = DatabaseOptimizer()
    optimizer.run_analysis()