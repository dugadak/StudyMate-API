# Generated database optimization migration for quiz app

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quiz', '0001_initial'),
    ]

    operations = [
        # Quiz model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_quiz_user_created_idx ON quiz_quiz (user_id, created_at);",
            reverse_sql="DROP INDEX IF EXISTS quiz_quiz_user_created_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_quiz_subject_created_idx ON quiz_quiz (subject_id, created_at);",
            reverse_sql="DROP INDEX IF EXISTS quiz_quiz_subject_created_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_quiz_difficulty_idx ON quiz_quiz (difficulty);",
            reverse_sql="DROP INDEX IF EXISTS quiz_quiz_difficulty_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_quiz_is_public_idx ON quiz_quiz (is_public);",
            reverse_sql="DROP INDEX IF EXISTS quiz_quiz_is_public_idx;"
        ),
        
        # Question model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_question_quiz_order_idx ON quiz_question (quiz_id, order);",
            reverse_sql="DROP INDEX IF EXISTS quiz_question_quiz_order_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_question_type_idx ON quiz_question (question_type);",
            reverse_sql="DROP INDEX IF EXISTS quiz_question_type_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_question_difficulty_idx ON quiz_question (difficulty);",
            reverse_sql="DROP INDEX IF EXISTS quiz_question_difficulty_idx;"
        ),
        
        # QuizAttempt model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_quizattempt_user_started_idx ON quiz_quizattempt (user_id, started_at);",
            reverse_sql="DROP INDEX IF EXISTS quiz_quizattempt_user_started_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_quizattempt_quiz_started_idx ON quiz_quizattempt (quiz_id, started_at);",
            reverse_sql="DROP INDEX IF EXISTS quiz_quizattempt_quiz_started_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_quizattempt_completed_idx ON quiz_quizattempt (completed_at);",
            reverse_sql="DROP INDEX IF EXISTS quiz_quizattempt_completed_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_quizattempt_score_idx ON quiz_quizattempt (score);",
            reverse_sql="DROP INDEX IF EXISTS quiz_quizattempt_score_idx;"
        ),
        
        # Answer model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_answer_attempt_question_idx ON quiz_answer (attempt_id, question_id);",
            reverse_sql="DROP INDEX IF EXISTS quiz_answer_attempt_question_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_answer_is_correct_idx ON quiz_answer (is_correct);",
            reverse_sql="DROP INDEX IF EXISTS quiz_answer_is_correct_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS quiz_answer_answered_at_idx ON quiz_answer (answered_at);",
            reverse_sql="DROP INDEX IF EXISTS quiz_answer_answered_at_idx;"
        ),
        
        # QuizProgress model indexes
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS quiz_quizprogress_user_quiz_idx 
            ON quiz_quizprogress (user_id, quiz_id);
            """,
            reverse_sql="DROP INDEX IF EXISTS quiz_quizprogress_user_quiz_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS quiz_quizprogress_updated_idx 
            ON quiz_quizprogress (last_updated);
            """,
            reverse_sql="DROP INDEX IF EXISTS quiz_quizprogress_updated_idx;"
        ),
        
        # QuizAnalytics model indexes
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS quiz_quizanalytics_user_date_idx 
            ON quiz_quizanalytics (user_id, date);
            """,
            reverse_sql="DROP INDEX IF EXISTS quiz_quizanalytics_user_date_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS quiz_quizanalytics_quiz_date_idx 
            ON quiz_quizanalytics (quiz_id, date);
            """,
            reverse_sql="DROP INDEX IF EXISTS quiz_quizanalytics_quiz_date_idx;"
        ),
        
        # Composite indexes for complex queries
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS quiz_quizattempt_user_quiz_completed_idx 
            ON quiz_quizattempt (user_id, quiz_id, completed_at);
            """,
            reverse_sql="DROP INDEX IF EXISTS quiz_quizattempt_user_quiz_completed_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS quiz_quiz_user_subject_public_idx 
            ON quiz_quiz (user_id, subject_id, is_public);
            """,
            reverse_sql="DROP INDEX IF EXISTS quiz_quiz_user_subject_public_idx;"
        ),
        
        # Performance indexes for leaderboards and rankings
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS quiz_quizattempt_quiz_score_desc_idx 
            ON quiz_quizattempt (quiz_id, score DESC) 
            WHERE completed_at IS NOT NULL;
            """,
            reverse_sql="DROP INDEX IF EXISTS quiz_quizattempt_quiz_score_desc_idx;"
        ),
        
        # Index for recent quiz activity
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS quiz_quizattempt_recent_idx 
            ON quiz_quizattempt (started_at DESC) 
            WHERE started_at >= NOW() - INTERVAL '30 days';
            """,
            reverse_sql="DROP INDEX IF EXISTS quiz_quizattempt_recent_idx;"
        ),
        
        # QuizReview model indexes
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS quiz_quizreview_user_quiz_idx 
            ON quiz_quizreview (user_id, quiz_id);
            """,
            reverse_sql="DROP INDEX IF EXISTS quiz_quizreview_user_quiz_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS quiz_quizreview_rating_idx 
            ON quiz_quizreview (rating);
            """,
            reverse_sql="DROP INDEX IF EXISTS quiz_quizreview_rating_idx;"
        ),
    ]