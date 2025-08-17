# Generated database optimization migration for notifications app

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        # NotificationTemplate model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_template_type_active_idx ON notifications_notificationtemplate (template_type, is_active);",
            reverse_sql="DROP INDEX IF EXISTS notifications_template_type_active_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_template_priority_idx ON notifications_notificationtemplate (priority, is_active);",
            reverse_sql="DROP INDEX IF EXISTS notifications_template_priority_idx;"
        ),
        
        # NotificationSchedule model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_schedule_user_active_idx ON notifications_notificationschedule (user_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS notifications_schedule_user_active_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_schedule_next_scheduled_idx ON notifications_notificationschedule (next_scheduled_at);",
            reverse_sql="DROP INDEX IF EXISTS notifications_schedule_next_scheduled_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_schedule_status_idx ON notifications_notificationschedule (status, is_active);",
            reverse_sql="DROP INDEX IF EXISTS notifications_schedule_status_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_schedule_template_idx ON notifications_notificationschedule (template_id);",
            reverse_sql="DROP INDEX IF EXISTS notifications_schedule_template_idx;"
        ),
        
        # Notification model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_notification_user_status_idx ON notifications_notification (user_id, status);",
            reverse_sql="DROP INDEX IF EXISTS notifications_notification_user_status_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_notification_scheduled_idx ON notifications_notification (scheduled_at);",
            reverse_sql="DROP INDEX IF EXISTS notifications_notification_scheduled_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_notification_type_channel_idx ON notifications_notification (notification_type, channel);",
            reverse_sql="DROP INDEX IF EXISTS notifications_notification_type_channel_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_notification_priority_scheduled_idx ON notifications_notification (priority, scheduled_at);",
            reverse_sql="DROP INDEX IF EXISTS notifications_notification_priority_scheduled_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_notification_sent_at_idx ON notifications_notification (sent_at);",
            reverse_sql="DROP INDEX IF EXISTS notifications_notification_sent_at_idx;"
        ),
        
        # DeviceToken model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_devicetoken_user_active_idx ON notifications_devicetoken (user_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS notifications_devicetoken_user_active_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_devicetoken_platform_active_idx ON notifications_devicetoken (platform, is_active);",
            reverse_sql="DROP INDEX IF EXISTS notifications_devicetoken_platform_active_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_devicetoken_primary_idx ON notifications_devicetoken (is_primary, is_active);",
            reverse_sql="DROP INDEX IF EXISTS notifications_devicetoken_primary_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_devicetoken_failure_count_idx ON notifications_devicetoken (failure_count);",
            reverse_sql="DROP INDEX IF EXISTS notifications_devicetoken_failure_count_idx;"
        ),
        
        # NotificationBatch model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_batch_status_idx ON notifications_notificationbatch (status);",
            reverse_sql="DROP INDEX IF EXISTS notifications_batch_status_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_batch_scheduled_idx ON notifications_notificationbatch (scheduled_at);",
            reverse_sql="DROP INDEX IF EXISTS notifications_batch_scheduled_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS notifications_batch_created_by_idx ON notifications_notificationbatch (created_by_id, created_at);",
            reverse_sql="DROP INDEX IF EXISTS notifications_batch_created_by_idx;"
        ),
        
        # Composite indexes for complex notification queries
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS notifications_notification_user_status_scheduled_idx 
            ON notifications_notification (user_id, status, scheduled_at);
            """,
            reverse_sql="DROP INDEX IF EXISTS notifications_notification_user_status_scheduled_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS notifications_schedule_user_status_next_idx 
            ON notifications_notificationschedule (user_id, status, next_scheduled_at);
            """,
            reverse_sql="DROP INDEX IF EXISTS notifications_schedule_user_status_next_idx;"
        ),
        
        # Performance indexes for pending notifications
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS notifications_notification_pending_idx 
            ON notifications_notification (scheduled_at, priority) 
            WHERE status IN ('pending', 'scheduled');
            """,
            reverse_sql="DROP INDEX IF EXISTS notifications_notification_pending_idx;"
        ),
        
        # Index for due schedules
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS notifications_schedule_due_idx 
            ON notifications_notificationschedule (next_scheduled_at) 
            WHERE is_active = true AND status = 'active' AND next_scheduled_at <= NOW();
            """,
            reverse_sql="DROP INDEX IF EXISTS notifications_schedule_due_idx;"
        ),
        
        # Index for unread notifications
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS notifications_notification_unread_idx 
            ON notifications_notification (user_id, created_at DESC) 
            WHERE status = 'sent';
            """,
            reverse_sql="DROP INDEX IF EXISTS notifications_notification_unread_idx;"
        ),
        
        # Index for failed notifications that can be retried
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS notifications_notification_retry_idx 
            ON notifications_notification (retry_count, max_retries, scheduled_at) 
            WHERE status = 'failed' AND (expired_at IS NULL OR expired_at > NOW());
            """,
            reverse_sql="DROP INDEX IF EXISTS notifications_notification_retry_idx;"
        ),
        
        # Analytics and reporting indexes
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS notifications_notification_analytics_idx 
            ON notifications_notification (notification_type, status, created_at);
            """,
            reverse_sql="DROP INDEX IF EXISTS notifications_notification_analytics_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS notifications_schedule_subject_user_idx 
            ON notifications_notificationschedule (subject_id, user_id) 
            WHERE subject_id IS NOT NULL;
            """,
            reverse_sql="DROP INDEX IF EXISTS notifications_schedule_subject_user_idx;"
        ),
        
        # Batch processing optimization
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS notifications_batch_processing_idx 
            ON notifications_notificationbatch (status, scheduled_at) 
            WHERE status IN ('pending', 'processing');
            """,
            reverse_sql="DROP INDEX IF EXISTS notifications_batch_processing_idx;"
        ),
    ]