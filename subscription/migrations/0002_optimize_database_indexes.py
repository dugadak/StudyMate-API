# Generated database optimization migration for subscription app

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscription', '0001_initial'),
    ]

    operations = [
        # SubscriptionPlan model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_plan_type_active_idx ON subscription_subscriptionplan (plan_type, is_active);",
            reverse_sql="DROP INDEX IF EXISTS subscription_plan_type_active_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_plan_price_idx ON subscription_subscriptionplan (price);",
            reverse_sql="DROP INDEX IF EXISTS subscription_plan_price_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_plan_popular_idx ON subscription_subscriptionplan (is_popular, is_active);",
            reverse_sql="DROP INDEX IF EXISTS subscription_plan_popular_idx;"
        ),
        
        # UserSubscription model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_usersubscription_user_status_idx ON subscription_usersubscription (user_id, status);",
            reverse_sql="DROP INDEX IF EXISTS subscription_usersubscription_user_status_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_usersubscription_expires_idx ON subscription_usersubscription (expires_at);",
            reverse_sql="DROP INDEX IF EXISTS subscription_usersubscription_expires_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_usersubscription_started_idx ON subscription_usersubscription (started_at);",
            reverse_sql="DROP INDEX IF EXISTS subscription_usersubscription_started_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_usersubscription_trial_ends_idx ON subscription_usersubscription (trial_ends_at);",
            reverse_sql="DROP INDEX IF EXISTS subscription_usersubscription_trial_ends_idx;"
        ),
        
        # UsageCredit model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_usagecredit_user_type_idx ON subscription_usagecredit (user_id, credit_type);",
            reverse_sql="DROP INDEX IF EXISTS subscription_usagecredit_user_type_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_usagecredit_expires_idx ON subscription_usagecredit (expires_at);",
            reverse_sql="DROP INDEX IF EXISTS subscription_usagecredit_expires_at_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_usagecredit_unlimited_idx ON subscription_usagecredit (is_unlimited);",
            reverse_sql="DROP INDEX IF EXISTS subscription_usagecredit_unlimited_idx;"
        ),
        
        # Payment model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_payment_user_created_idx ON subscription_payment (user_id, created_at);",
            reverse_sql="DROP INDEX IF EXISTS subscription_payment_user_created_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_payment_status_idx ON subscription_payment (status);",
            reverse_sql="DROP INDEX IF EXISTS subscription_payment_status_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_payment_amount_idx ON subscription_payment (amount);",
            reverse_sql="DROP INDEX IF EXISTS subscription_payment_amount_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_payment_completed_idx ON subscription_payment (completed_at);",
            reverse_sql="DROP INDEX IF EXISTS subscription_payment_completed_idx;"
        ),
        
        # Discount model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_discount_code_idx ON subscription_discount (code);",
            reverse_sql="DROP INDEX IF EXISTS subscription_discount_code_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_discount_valid_period_idx ON subscription_discount (valid_from, valid_until);",
            reverse_sql="DROP INDEX IF EXISTS subscription_discount_valid_period_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_discount_active_idx ON subscription_discount (is_active);",
            reverse_sql="DROP INDEX IF EXISTS subscription_discount_active_idx;"
        ),
        
        # DiscountUsage model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_discountusage_user_discount_idx ON subscription_discountusage (user_id, discount_id);",
            reverse_sql="DROP INDEX IF EXISTS subscription_discountusage_user_discount_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS subscription_discountusage_used_at_idx ON subscription_discountusage (used_at);",
            reverse_sql="DROP INDEX IF EXISTS subscription_discountusage_used_at_idx;"
        ),
        
        # Composite indexes for complex subscription queries
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS subscription_usersubscription_user_status_expires_idx 
            ON subscription_usersubscription (user_id, status, expires_at);
            """,
            reverse_sql="DROP INDEX IF EXISTS subscription_usersubscription_user_status_expires_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS subscription_usersubscription_plan_status_idx 
            ON subscription_usersubscription (plan_id, status);
            """,
            reverse_sql="DROP INDEX IF EXISTS subscription_usersubscription_plan_status_idx;"
        ),
        
        # Performance indexes for active subscriptions
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS subscription_usersubscription_active_idx 
            ON subscription_usersubscription (user_id, expires_at) 
            WHERE status IN ('active', 'trialing');
            """,
            reverse_sql="DROP INDEX IF EXISTS subscription_usersubscription_active_idx;"
        ),
        
        # Index for expiring subscriptions
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS subscription_usersubscription_expiring_idx 
            ON subscription_usersubscription (expires_at) 
            WHERE status = 'active' AND expires_at <= NOW() + INTERVAL '7 days';
            """,
            reverse_sql="DROP INDEX IF EXISTS subscription_usersubscription_expiring_idx;"
        ),
        
        # Revenue analytics indexes
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS subscription_payment_revenue_idx 
            ON subscription_payment (completed_at, amount) 
            WHERE status = 'succeeded';
            """,
            reverse_sql="DROP INDEX IF EXISTS subscription_payment_revenue_idx;"
        ),
        
        # Usage credit optimization
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS subscription_usagecredit_active_idx 
            ON subscription_usagecredit (user_id, credit_type, used_credits, total_credits) 
            WHERE (expires_at IS NULL OR expires_at > NOW());
            """,
            reverse_sql="DROP INDEX IF EXISTS subscription_usagecredit_active_idx;"
        ),
    ]