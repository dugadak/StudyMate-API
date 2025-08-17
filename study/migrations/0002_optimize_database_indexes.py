# Generated database optimization migration for study app

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('study', '0001_initial'),
    ]

    operations = [
        # Subject model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS study_subject_user_name_idx ON study_subject (user_id, name);",
            reverse_sql="DROP INDEX IF EXISTS study_subject_user_name_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS study_subject_user_active_idx ON study_subject (user_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS study_subject_user_active_idx;"
        ),
        
        # StudySession model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS study_studysession_user_created_idx ON study_studysession (user_id, created_at);",
            reverse_sql="DROP INDEX IF EXISTS study_studysession_user_created_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS study_studysession_subject_created_idx ON study_studysession (subject_id, created_at);",
            reverse_sql="DROP INDEX IF EXISTS study_studysession_subject_created_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS study_studysession_duration_idx ON study_studysession (duration);",
            reverse_sql="DROP INDEX IF EXISTS study_studysession_duration_idx;"
        ),
        
        # Summary model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS study_summary_user_created_idx ON study_summary (user_id, created_at);",
            reverse_sql="DROP INDEX IF EXISTS study_summary_user_created_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS study_summary_subject_created_idx ON study_summary (subject_id, created_at);",
            reverse_sql="DROP INDEX IF EXISTS study_summary_subject_created_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS study_summary_session_idx ON study_summary (session_id);",
            reverse_sql="DROP INDEX IF EXISTS study_summary_session_idx;"
        ),
        
        # StudyProgress model indexes
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS study_studyprogress_user_subject_idx 
            ON study_studyprogress (user_id, subject_id);
            """,
            reverse_sql="DROP INDEX IF EXISTS study_studyprogress_user_subject_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS study_studyprogress_updated_idx 
            ON study_studyprogress (last_updated);
            """,
            reverse_sql="DROP INDEX IF EXISTS study_studyprogress_updated_idx;"
        ),
        
        # StudyGoal model indexes
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS study_studygoal_user_active_idx 
            ON study_studygoal (user_id, is_active);
            """,
            reverse_sql="DROP INDEX IF EXISTS study_studygoal_user_active_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS study_studygoal_deadline_idx 
            ON study_studygoal (target_date);
            """,
            reverse_sql="DROP INDEX IF EXISTS study_studygoal_deadline_idx;"
        ),
        
        # StudyStreak model indexes
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS study_studystreak_user_current_idx 
            ON study_studystreak (user_id, is_current);
            """,
            reverse_sql="DROP INDEX IF EXISTS study_studystreak_user_current_idx;"
        ),
        
        # StudyAnalytics model indexes
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS study_studyanalytics_user_date_idx 
            ON study_studyanalytics (user_id, date);
            """,
            reverse_sql="DROP INDEX IF EXISTS study_studyanalytics_user_date_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS study_studyanalytics_subject_date_idx 
            ON study_studyanalytics (subject_id, date);
            """,
            reverse_sql="DROP INDEX IF EXISTS study_studyanalytics_subject_date_idx;"
        ),
        
        # Composite indexes for common query patterns
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS study_studysession_user_subject_date_idx 
            ON study_studysession (user_id, subject_id, created_at);
            """,
            reverse_sql="DROP INDEX IF EXISTS study_studysession_user_subject_date_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS study_summary_user_subject_date_idx 
            ON study_summary (user_id, subject_id, created_at);
            """,
            reverse_sql="DROP INDEX IF EXISTS study_summary_user_subject_date_idx;"
        ),
        
        # Performance optimization for recent sessions
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS study_studysession_recent_idx 
            ON study_studysession (created_at DESC) 
            WHERE created_at >= NOW() - INTERVAL '30 days';
            """,
            reverse_sql="DROP INDEX IF EXISTS study_studysession_recent_idx;"
        ),
    ]