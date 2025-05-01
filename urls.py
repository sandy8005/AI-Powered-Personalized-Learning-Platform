from django.urls import path, re_path
from django.views.generic.base import RedirectView
from rest_framework.urlpatterns import format_suffix_patterns
from . import views
from .views import (
    UserListCreateAPIView,
    UserDetailAPIView,
    register_user,
    login_user,
    logout_user,
    CoursePlanCreateAPIView,
    CoursePlanListAPIView,
    CourseTopicCreateAPIView,
    CourseAssignmentCreateAPIView,
    CourseProjectCreateAPIView
)

urlpatterns = [
    # Web UI routes
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('register/', register_user, name='register'),
    path('login/', login_user, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logout/', logout_user, name='logout'),
    path('course-plans/<int:course_plan_id>/', views.course_plan_detail_view, name='course-plan-detail'),
    path('create-course-plan/', views.create_course_plan_view, name='create-course-plan-form'),
   
    path('chatbot/', views.chatbot_view, name='chatbot'),
    
    # API routes - Use consistent naming and remove redundant patterns
    path('api/users/', UserListCreateAPIView.as_view(), name='user-list-create'),
    path('api/users/<int:pk>/', UserDetailAPIView.as_view(), name='user-detail'),
    
    # Course-related API routes
    path('api/course-plans/', CoursePlanCreateAPIView.as_view(), name='create-course-plan'),
    path('api/course-plans/list/', CoursePlanListAPIView.as_view(), name='list-course-plans'),
    path('api/course-topics/', CourseTopicCreateAPIView.as_view(), name='create-course-topic'),
    path('api/course-assignments/', CourseAssignmentCreateAPIView.as_view(), name='create-course-assignment'),
    path('api/course-projects/', CourseProjectCreateAPIView.as_view(), name='create-course-project'),
    
    # Additional route to handle the duplicate "api" in the path from FastAPI service
    path('api/api/course-plans/', CoursePlanCreateAPIView.as_view(), name='api-api-create-course-plan'),
    path('api/api/course-topics/', CourseTopicCreateAPIView.as_view(), name='api-api-create-course-topic'),
    path('api/api/course-assignments/', CourseAssignmentCreateAPIView.as_view(), name='api-api-create-course-assignment'),
    path('api/api/course-projects/', CourseProjectCreateAPIView.as_view(), name='api-api-create-course-project'),
    # Add this to your urlpatterns list
    path('course-plans/<int:course_plan_id>/delete/', views.delete_course_plan, name='delete-course-plan'),
]

# Add support for multiple formats
urlpatterns = format_suffix_patterns(urlpatterns)