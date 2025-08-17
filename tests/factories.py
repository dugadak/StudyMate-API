"""
Factory Boy를 사용한 테스트 데이터 생성 팩토리

이 모듈은 테스트에서 사용할 모델 인스턴스를 쉽게 생성할 수 있는
팩토리 클래스들을 제공합니다.
"""

import factory
from factory import django, SubFactory, LazyAttribute, Sequence, LazyFunction
from factory.fuzzy import FuzzyChoice, FuzzyDecimal, FuzzyInteger, FuzzyDate, FuzzyDateTime
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
import faker

User = get_user_model()
fake = faker.Faker('ko_KR')


class UserFactory(django.DjangoModelFactory):
    """사용자 팩토리"""
    
    class Meta:
        model = User
        django_get_or_create = ('email',)
    
    email = factory.Sequence(lambda n: f'user{n}@test.com')
    first_name = factory.LazyFunction(fake.first_name)
    last_name = factory.LazyFunction(fake.last_name)
    is_active = True
    is_staff = False
    is_superuser = False
    date_joined = factory.LazyFunction(timezone.now)
    
    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        if not create:
            return
        
        password = extracted or 'testpass123'
        self.set_password(password)
        self.save()


class AdminUserFactory(UserFactory):
    """관리자 사용자 팩토리"""
    
    email = factory.Sequence(lambda n: f'admin{n}@test.com')
    is_staff = True
    is_superuser = True


class UserProfileFactory(django.DjangoModelFactory):
    """사용자 프로필 팩토리"""
    
    class Meta:
        model = 'accounts.UserProfile'
    
    user = SubFactory(UserFactory)
    name = factory.LazyAttribute(lambda obj: f"{obj.user.first_name} {obj.user.last_name}")
    bio = factory.LazyFunction(lambda: fake.text(max_nb_chars=200))
    birth_date = FuzzyDate(
        start_date=datetime(1980, 1, 1).date(),
        end_date=datetime(2005, 12, 31).date()
    )
    phone = factory.LazyFunction(lambda: fake.phone_number())
    preferred_language = FuzzyChoice(['ko', 'en'])
    timezone = 'Asia/Seoul'
    is_verified = True


class SubjectFactory(django.DjangoModelFactory):
    """과목 팩토리"""
    
    class Meta:
        model = 'study.Subject'
    
    name = factory.LazyFunction(lambda: fake.word() + ' 학습')
    description = factory.LazyFunction(lambda: fake.text(max_nb_chars=500))
    category = FuzzyChoice(['programming', 'data_science', 'design', 'business'])
    default_difficulty = FuzzyChoice(['beginner', 'intermediate', 'advanced'])
    icon = factory.LazyFunction(lambda: fake.word())
    color_code = '#4CAF50'
    is_active = True
    requires_premium = False
    tags = factory.LazyFunction(lambda: [fake.word() for _ in range(3)])
    keywords = factory.LazyFunction(lambda: [fake.word() for _ in range(5)])
    total_learners = FuzzyInteger(0, 10000)
    total_summaries = FuzzyInteger(0, 1000)
    average_rating = FuzzyDecimal(1.0, 5.0, precision=1)


class StudySettingsFactory(django.DjangoModelFactory):
    """학습 설정 팩토리"""
    
    class Meta:
        model = 'study.StudySettings'
    
    user = SubFactory(UserFactory)
    subject = SubFactory(SubjectFactory)
    difficulty_level = FuzzyChoice(['beginner', 'intermediate', 'advanced'])
    current_knowledge = factory.LazyFunction(lambda: fake.text(max_nb_chars=200))
    learning_goal = factory.LazyFunction(lambda: fake.text(max_nb_chars=200))
    preferred_depth = FuzzyChoice(['basic', 'intermediate', 'detailed'])
    learning_style = FuzzyChoice(['visual', 'auditory', 'kinesthetic', 'reading'])
    content_type_preference = FuzzyChoice(['summary', 'explanation', 'example'])
    daily_summary_count = FuzzyInteger(1, 5)
    notification_times = factory.LazyFunction(lambda: ['09:00', '18:00'])
    study_days = factory.LazyFunction(lambda: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'])
    preferred_study_duration = FuzzyInteger(15, 120)
    include_examples = True
    include_quizzes = True
    language_preference = 'ko'
    preferred_ai_model = 'gpt-4'


class StudySummaryFactory(django.DjangoModelFactory):
    """학습 요약 팩토리"""
    
    class Meta:
        model = 'study.StudySummary'
    
    user = SubFactory(UserFactory)
    subject = SubFactory(SubjectFactory)
    title = factory.LazyFunction(lambda: fake.sentence(nb_words=6))
    content = factory.LazyFunction(lambda: fake.text(max_nb_chars=2000))
    content_type = FuzzyChoice(['summary', 'explanation', 'example'])
    difficulty_level = FuzzyChoice(['beginner', 'intermediate', 'advanced'])
    ai_model_used = 'gpt-4'
    generation_time = FuzzyDecimal(0.5, 5.0, precision=2)
    token_count = FuzzyInteger(100, 2000)
    is_read = False
    user_rating = None
    is_bookmarked = False
    topics_covered = factory.LazyFunction(lambda: [fake.word() for _ in range(3)])
    tags = factory.LazyFunction(lambda: [fake.word() for _ in range(2)])
    generated_at = factory.LazyFunction(timezone.now)


class StudyProgressFactory(django.DjangoModelFactory):
    """학습 진도 팩토리"""
    
    class Meta:
        model = 'study.StudyProgress'
    
    user = SubFactory(UserFactory)
    subject = SubFactory(SubjectFactory)
    topics_learned = factory.LazyFunction(lambda: [fake.word() for _ in range(5)])
    mastery_levels = factory.LazyFunction(lambda: {fake.word(): fake.random_int(1, 5) for _ in range(3)})
    total_summaries_read = FuzzyInteger(0, 100)
    total_quizzes_completed = FuzzyInteger(0, 50)
    total_study_time = FuzzyInteger(0, 10000)  # 분 단위
    current_streak = FuzzyInteger(0, 30)
    longest_streak = FuzzyInteger(0, 100)
    study_frequency = FuzzyDecimal(0.0, 7.0, precision=1)
    average_rating_given = FuzzyDecimal(1.0, 5.0, precision=1)
    completion_rate = FuzzyDecimal(0.0, 100.0, precision=1)
    weekly_goal = FuzzyInteger(1, 20)
    monthly_goal = FuzzyInteger(5, 100)
    preferred_study_hours = factory.LazyFunction(lambda: [fake.random_int(0, 23) for _ in range(2)])
    study_session_count = FuzzyInteger(0, 500)
    average_session_duration = FuzzyInteger(10, 180)
    badges_earned = factory.LazyFunction(lambda: [fake.word() for _ in range(2)])
    milestones_reached = factory.LazyFunction(lambda: [fake.word() for _ in range(3)])
    last_activity_date = factory.LazyFunction(timezone.now)


class QuizFactory(django.DjangoModelFactory):
    """퀴즈 팩토리"""
    
    class Meta:
        model = 'quiz.Quiz'
    
    subject = SubFactory(SubjectFactory)
    title = factory.LazyFunction(lambda: fake.sentence(nb_words=4))
    description = factory.LazyFunction(lambda: fake.text(max_nb_chars=300))
    difficulty_level = FuzzyChoice(['beginner', 'intermediate', 'advanced'])
    time_limit = FuzzyInteger(300, 3600)  # 5분-1시간
    passing_score = FuzzyInteger(60, 90)
    max_attempts = FuzzyInteger(1, 5)
    is_active = True
    tags = factory.LazyFunction(lambda: [fake.word() for _ in range(2)])
    ai_model_used = 'gpt-4'
    generation_time = FuzzyDecimal(1.0, 10.0, precision=2)


class QuizQuestionFactory(django.DjangoModelFactory):
    """퀴즈 문제 팩토리"""
    
    class Meta:
        model = 'quiz.QuizQuestion'
    
    quiz = SubFactory(QuizFactory)
    question_text = factory.LazyFunction(lambda: fake.sentence(nb_words=10) + '?')
    question_type = FuzzyChoice(['multiple_choice', 'true_false', 'short_answer'])
    options = factory.LazyFunction(lambda: [fake.word() for _ in range(4)])
    correct_answer = factory.LazyAttribute(lambda obj: obj.options[0] if obj.options else fake.word())
    explanation = factory.LazyFunction(lambda: fake.text(max_nb_chars=200))
    points = FuzzyInteger(1, 10)
    order = factory.Sequence(lambda n: n + 1)


class QuizAttemptFactory(django.DjangoModelFactory):
    """퀴즈 응시 팩토리"""
    
    class Meta:
        model = 'quiz.QuizAttempt'
    
    user = SubFactory(UserFactory)
    quiz = SubFactory(QuizFactory)
    score = FuzzyDecimal(0.0, 100.0, precision=1)
    total_questions = FuzzyInteger(5, 50)
    correct_answers = factory.LazyAttribute(lambda obj: int(obj.total_questions * obj.score / 100))
    time_taken = FuzzyInteger(60, 3600)  # 1분-1시간
    is_completed = True
    started_at = factory.LazyFunction(lambda: timezone.now() - timedelta(hours=1))
    completed_at = factory.LazyFunction(timezone.now)


class SubscriptionPlanFactory(django.DjangoModelFactory):
    """구독 플랜 팩토리"""
    
    class Meta:
        model = 'subscription.SubscriptionPlan'
    
    name = factory.LazyFunction(lambda: fake.word() + ' 플랜')
    description = factory.LazyFunction(lambda: fake.text(max_nb_chars=300))
    price = FuzzyDecimal(9.99, 99.99, precision=2)
    billing_period = FuzzyChoice(['monthly', 'yearly'])
    plan_type = FuzzyChoice(['basic', 'premium', 'enterprise'])
    max_ai_requests = FuzzyInteger(100, 10000)
    max_summaries_per_day = FuzzyInteger(10, 100)
    max_quizzes_per_day = FuzzyInteger(5, 50)
    features = factory.LazyFunction(lambda: [fake.word() for _ in range(5)])
    is_active = True
    stripe_price_id = factory.LazyFunction(lambda: f'price_{fake.lexify(text="?" * 24)}')


class UserSubscriptionFactory(django.DjangoModelFactory):
    """사용자 구독 팩토리"""
    
    class Meta:
        model = 'subscription.UserSubscription'
    
    user = SubFactory(UserFactory)
    plan = SubFactory(SubscriptionPlanFactory)
    status = FuzzyChoice(['active', 'inactive', 'trial', 'cancelled'])
    stripe_subscription_id = factory.LazyFunction(lambda: f'sub_{fake.lexify(text="?" * 24)}')
    stripe_customer_id = factory.LazyFunction(lambda: f'cus_{fake.lexify(text="?" * 24)}')
    current_period_start = factory.LazyFunction(timezone.now)
    current_period_end = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
    is_trial = False
    trial_ends_at = None
    cancelled_at = None


class NotificationTemplateFactory(django.DjangoModelFactory):
    """알림 템플릿 팩토리"""
    
    class Meta:
        model = 'notifications.NotificationTemplate'
    
    name = factory.LazyFunction(lambda: fake.word() + '_notification')
    title = factory.LazyFunction(lambda: fake.sentence(nb_words=4))
    message = factory.LazyFunction(lambda: fake.text(max_nb_chars=200))
    notification_type = FuzzyChoice(['email', 'push', 'in_app'])
    is_active = True
    variables = factory.LazyFunction(lambda: ['user_name', 'subject_name'])


class NotificationFactory(django.DjangoModelFactory):
    """알림 팩토리"""
    
    class Meta:
        model = 'notifications.Notification'
    
    user = SubFactory(UserFactory)
    template = SubFactory(NotificationTemplateFactory)
    title = factory.LazyFunction(lambda: fake.sentence(nb_words=4))
    message = factory.LazyFunction(lambda: fake.text(max_nb_chars=200))
    notification_type = FuzzyChoice(['email', 'push', 'in_app'])
    is_read = False
    sent_at = None
    read_at = None
    data = factory.LazyFunction(lambda: {'key': 'value'})


# 편의 함수들
def create_test_user_with_profile(**kwargs):
    """프로필이 있는 테스트 사용자 생성"""
    user = UserFactory(**kwargs)
    profile = UserProfileFactory(user=user)
    return user, profile


def create_test_subject_with_settings(user=None, **kwargs):
    """설정이 있는 테스트 과목 생성"""
    if user is None:
        user = UserFactory()
    
    subject = SubjectFactory(**kwargs)
    settings = StudySettingsFactory(user=user, subject=subject)
    return subject, settings


def create_test_quiz_with_questions(question_count=5, **kwargs):
    """문제가 있는 테스트 퀴즈 생성"""
    quiz = QuizFactory(**kwargs)
    questions = [
        QuizQuestionFactory(quiz=quiz, order=i+1) 
        for i in range(question_count)
    ]
    return quiz, questions


def create_test_subscription(user=None, **kwargs):
    """테스트 구독 생성"""
    if user is None:
        user = UserFactory()
    
    plan = SubscriptionPlanFactory()
    subscription = UserSubscriptionFactory(user=user, plan=plan, **kwargs)
    return subscription


# 내보낼 팩토리들
__all__ = [
    'UserFactory',
    'AdminUserFactory',
    'UserProfileFactory',
    'SubjectFactory',
    'StudySettingsFactory',
    'StudySummaryFactory',
    'StudyProgressFactory',
    'QuizFactory',
    'QuizQuestionFactory',
    'QuizAttemptFactory',
    'SubscriptionPlanFactory',
    'UserSubscriptionFactory',
    'NotificationTemplateFactory',
    'NotificationFactory',
    'create_test_user_with_profile',
    'create_test_subject_with_settings',
    'create_test_quiz_with_questions',
    'create_test_subscription',
]