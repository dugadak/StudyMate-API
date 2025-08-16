from rest_framework import viewsets, generics, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from .models import Subject, StudySettings, StudySummary, StudyProgress
from .serializers import (
    SubjectSerializer, StudySettingsSerializer, 
    StudySummarySerializer, StudyProgressSerializer
)
from .services import StudySummaryService, StudyProgressService


class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]


class StudySettingsViewSet(viewsets.ModelViewSet):
    serializer_class = StudySettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return StudySettings.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class StudySummaryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudySummarySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return StudySummary.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        summary = self.get_object()
        summary.is_read = True
        summary.save()
        
        StudyProgressService.update_progress(
            user=request.user,
            subject=summary.subject,
            action_type='summary_read'
        )
        
        return Response({'message': '읽음 처리되었습니다.'})


class StudyProgressViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudyProgressSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return StudyProgress.objects.filter(user=self.request.user)


class GenerateSummaryView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        subject_id = request.data.get('subject_id')
        
        if not subject_id:
            return Response({
                'error': '과목을 선택해주세요.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            summary_service = StudySummaryService()
            summary = summary_service.generate_summary(request.user, subject_id)
            
            return Response({
                'summary': StudySummarySerializer(summary).data,
                'message': '학습 요약이 생성되었습니다.'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
