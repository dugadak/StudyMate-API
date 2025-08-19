"""
Django management command for analyzing database performance
Usage: python manage.py analyze_database_performance
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models
from django.apps import apps
from django.conf import settings
import time
from typing import Dict, List, Any


class Command(BaseCommand):
    help = "Analyze database performance and provide optimization recommendations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--app",
            type=str,
            help="Analyze specific app only",
        )
        parser.add_argument(
            "--model",
            type=str,
            help="Analyze specific model only",
        )
        parser.add_argument(
            "--slow-queries",
            action="store_true",
            help="Analyze slow queries",
        )
        parser.add_argument(
            "--table-sizes",
            action="store_true",
            help="Show table sizes",
        )
        parser.add_argument(
            "--index-usage",
            action="store_true",
            help="Analyze index usage",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== Database Performance Analysis ===\n"))

        if options["app"]:
            self.analyze_app(options["app"])
        elif options["model"]:
            self.analyze_model(options["model"])
        else:
            self.analyze_all()

        if options["slow_queries"]:
            self.analyze_slow_queries()

        if options["table_sizes"]:
            self.analyze_table_sizes()

        if options["index_usage"]:
            self.analyze_index_usage()

        self.stdout.write(self.style.SUCCESS("\n=== Analysis Complete ==="))

    def analyze_all(self):
        """Analyze all StudyMate apps"""
        target_apps = ["accounts", "study", "quiz", "subscription", "notifications"]

        for app_name in target_apps:
            try:
                self.analyze_app(app_name)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error analyzing {app_name}: {str(e)}"))

    def analyze_app(self, app_name: str):
        """Analyze specific app"""
        self.stdout.write(self.style.HTTP_INFO(f"\n📊 Analyzing {app_name} app"))

        try:
            app_config = apps.get_app_config(app_name)
            models_list = app_config.get_models()

            for model in models_list:
                self.analyze_model_performance(model)

        except LookupError:
            raise CommandError(f'App "{app_name}" not found')

    def analyze_model(self, model_name: str):
        """Analyze specific model"""
        try:
            app_label, model_name_part = model_name.split(".")
            model = apps.get_model(app_label, model_name_part)
            self.analyze_model_performance(model)
        except (ValueError, LookupError):
            raise CommandError(f'Model "{model_name}" not found')

    def analyze_model_performance(self, model):
        """Analyze individual model performance"""
        model_name = f"{model._meta.app_label}.{model._meta.model_name}"
        table_name = model._meta.db_table

        self.stdout.write(f"  🔍 {model_name}")

        # Get basic statistics
        try:
            count = model.objects.count()
            self.stdout.write(f"    Records: {count:,}")

            # Analyze query performance
            self.analyze_query_performance(model, table_name)

            # Check for potential issues
            self.check_model_issues(model)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    Error: {str(e)}"))

    def analyze_query_performance(self, model, table_name: str):
        """Analyze query performance for model"""
        # Test common query patterns
        queries_to_test = []

        # Basic queries
        if hasattr(model, "user"):
            queries_to_test.append(("User filter", lambda: list(model.objects.filter(user_id=1)[:10])))

        if hasattr(model, "created_at"):
            queries_to_test.append(("Date ordering", lambda: list(model.objects.order_by("-created_at")[:10])))

        if hasattr(model, "is_active"):
            queries_to_test.append(("Active filter", lambda: list(model.objects.filter(is_active=True)[:10])))

        # Run performance tests
        for query_name, query_func in queries_to_test:
            try:
                start_time = time.time()
                query_func()
                end_time = time.time()
                duration = (end_time - start_time) * 1000  # Convert to milliseconds

                if duration > 100:  # Slow query threshold
                    self.stdout.write(self.style.WARNING(f"    ⚠️  {query_name}: {duration:.2f}ms (SLOW)"))
                elif duration > 50:
                    self.stdout.write(self.style.HTTP_INFO(f"    🔶 {query_name}: {duration:.2f}ms"))
                else:
                    self.stdout.write(f"    ✅ {query_name}: {duration:.2f}ms")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    ❌ {query_name}: Error - {str(e)}"))

    def check_model_issues(self, model):
        """Check for common model issues"""
        issues = []

        # Check for missing indexes on foreign keys
        for field in model._meta.get_fields():
            if isinstance(field, models.ForeignKey):
                if not getattr(field, "db_index", False):
                    issues.append(f"Missing index on FK: {field.name}")

        # Check for large text fields without proper indexing
        for field in model._meta.get_fields():
            if isinstance(field, models.TextField):
                issues.append(f"Large text field: {field.name} - consider search indexing")

        # Check for datetime fields commonly used in filtering
        datetime_fields = []
        for field in model._meta.get_fields():
            if isinstance(field, (models.DateTimeField, models.DateField)):
                if field.name in ["created_at", "updated_at", "expires_at", "scheduled_at"]:
                    if not getattr(field, "db_index", False):
                        datetime_fields.append(field.name)

        if datetime_fields:
            issues.append(f'DateTime fields need indexing: {", ".join(datetime_fields)}')

        # Display issues
        if issues:
            self.stdout.write("    Issues found:")
            for issue in issues:
                self.stdout.write(self.style.WARNING(f"      ⚠️  {issue}"))

    def analyze_slow_queries(self):
        """Analyze slow queries (database specific)"""
        self.stdout.write(self.style.HTTP_INFO("\n🐌 Slow Query Analysis"))

        try:
            with connection.cursor() as cursor:
                # For SQLite, we can't easily get slow query logs
                # For production, you'd want to implement database-specific queries
                if "sqlite" in connection.settings_dict["ENGINE"]:
                    self.stdout.write("    SQLite doesn't provide slow query logs")
                    self.stdout.write("    Consider using PostgreSQL or MySQL for production")
                else:
                    # PostgreSQL example
                    cursor.execute(
                        """
                        SELECT query, mean_time, calls
                        FROM pg_stat_statements
                        ORDER BY mean_time DESC
                        LIMIT 10;
                    """
                    )
                    results = cursor.fetchall()

                    for query, mean_time, calls in results:
                        self.stdout.write(f"    {mean_time:.2f}ms avg ({calls} calls): {query[:100]}...")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    Error analyzing slow queries: {str(e)}"))

    def analyze_table_sizes(self):
        """Analyze table sizes"""
        self.stdout.write(self.style.HTTP_INFO("\n📏 Table Size Analysis"))

        try:
            with connection.cursor() as cursor:
                if "sqlite" in connection.settings_dict["ENGINE"]:
                    # SQLite specific query
                    cursor.execute(
                        """
                        SELECT name, 
                               COUNT(*) as row_count
                        FROM sqlite_master 
                        WHERE type='table' AND name NOT LIKE 'sqlite_%'
                        ORDER BY name;
                    """
                    )

                    tables = cursor.fetchall()
                    for table_name, _ in tables:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                        count = cursor.fetchone()[0]
                        self.stdout.write(f"    {table_name}: {count:,} rows")

                else:
                    # PostgreSQL specific query
                    cursor.execute(
                        """
                        SELECT schemaname, tablename,
                               pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                               pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                        FROM pg_tables 
                        WHERE schemaname = 'public'
                        ORDER BY size_bytes DESC;
                    """
                    )

                    results = cursor.fetchall()
                    for schema, table, size, size_bytes in results:
                        self.stdout.write(f"    {table}: {size}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    Error analyzing table sizes: {str(e)}"))

    def analyze_index_usage(self):
        """Analyze index usage"""
        self.stdout.write(self.style.HTTP_INFO("\n📇 Index Usage Analysis"))

        try:
            with connection.cursor() as cursor:
                if "sqlite" in connection.settings_dict["ENGINE"]:
                    # SQLite index information
                    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index';")
                    indexes = cursor.fetchall()

                    self.stdout.write(f"    Total indexes: {len(indexes)}")
                    for name, sql in indexes[:10]:  # Show first 10
                        if sql:  # Skip automatic indexes
                            self.stdout.write(f"    {name}: {sql}")

                else:
                    # PostgreSQL index usage
                    cursor.execute(
                        """
                        SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
                        FROM pg_stat_user_indexes
                        ORDER BY idx_tup_read DESC
                        LIMIT 20;
                    """
                    )

                    results = cursor.fetchall()
                    for schema, table, index, reads, fetches in results:
                        self.stdout.write(f"    {index} on {table}: {reads:,} reads, {fetches:,} fetches")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    Error analyzing index usage: {str(e)}"))

    def generate_recommendations(self):
        """Generate optimization recommendations"""
        recommendations = [
            "1. Add indexes to frequently queried foreign key fields",
            "2. Add composite indexes for complex query patterns",
            "3. Consider partitioning large tables by date",
            "4. Implement proper database connection pooling",
            "5. Use select_related() and prefetch_related() for ORM queries",
            "6. Consider read replicas for heavy read workloads",
            "7. Implement query result caching for frequently accessed data",
            "8. Monitor slow query logs regularly",
            "9. Consider denormalization for frequently joined tables",
            "10. Use database-specific optimization features",
        ]

        self.stdout.write(self.style.HTTP_INFO("\n💡 Optimization Recommendations"))

        for recommendation in recommendations:
            self.stdout.write(f"    {recommendation}")
