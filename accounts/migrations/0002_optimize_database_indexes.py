# Generated database optimization migration for accounts app

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        # Add composite index for email + is_active (login queries)
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_user_email_active_idx ON accounts_user (email, is_active);",
            reverse_sql="DROP INDEX IF EXISTS accounts_user_email_active_idx;"
        ),
        
        # Add index for last_login (analytics queries)
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_user_last_login_idx ON accounts_user (last_login);",
            reverse_sql="DROP INDEX IF EXISTS accounts_user_last_login_idx;"
        ),
        
        # Add index for date_joined (user registration analytics)
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_user_date_joined_idx ON accounts_user (date_joined);",
            reverse_sql="DROP INDEX IF EXISTS accounts_user_date_joined_idx;"
        ),
        
        # Add index for is_active + date_joined (active user analysis)
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_user_active_joined_idx ON accounts_user (is_active, date_joined);",
            reverse_sql="DROP INDEX IF EXISTS accounts_user_active_joined_idx;"
        ),
        
        # LoginHistory model indexes if it exists
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS accounts_loginhistory_user_timestamp_idx 
            ON accounts_loginhistory (user_id, timestamp);
            """,
            reverse_sql="DROP INDEX IF EXISTS accounts_loginhistory_user_timestamp_idx;"
        ),
        
        # EmailVerificationToken model indexes if it exists
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS accounts_emailverificationtoken_expires_idx 
            ON accounts_emailverificationtoken (expires_at);
            """,
            reverse_sql="DROP INDEX IF EXISTS accounts_emailverificationtoken_expires_idx;"
        ),
        
        # PasswordResetToken model indexes if it exists
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS accounts_passwordresettoken_expires_idx 
            ON accounts_passwordresettoken (expires_at);
            """,
            reverse_sql="DROP INDEX IF EXISTS accounts_passwordresettoken_expires_idx;"
        ),
        
        # Add partial index for active users only (space efficient)
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS accounts_user_active_users_idx 
            ON accounts_user (email, last_login) WHERE is_active = true;
            """,
            reverse_sql="DROP INDEX IF EXISTS accounts_user_active_users_idx;"
        ),
    ]