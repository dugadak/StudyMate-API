from django.apps import AppConfig


class StudyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'study'
    
    def ready(self):
        """앱이 준비될 때 CQRS 핸들러들을 등록"""
        try:
            # CQRS 핸들러 자동 등록을 위한 import
            from . import cqrs
        except ImportError:
            # CQRS 모듈이 없는 경우 무시
            pass
