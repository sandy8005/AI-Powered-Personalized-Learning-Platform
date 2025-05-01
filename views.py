from datetime import timedelta
from django.shortcuts import render, redirect
from rest_framework import status, generics
from rest_framework.response import Response
from .models import User, CoursePlan, CourseTopic, CourseProject
from .serializers import UserSerializer, CoursePlanSerializer, CourseTopicSerializer, CourseProjectSerializer
from .forms import RegistrationForm
import re
from .models import CourseMapper  # Add this import
from .chatbot_utils import process_user_message, find_course_in_message
import traceback
from .models import User, CoursePlan, CourseTopic, CourseProject, ChatContext, LearningProgress, TopicCompletion
from django.contrib import messages
from django.contrib.auth import logout
import requests 
from django.http import JsonResponse
from rest_framework.decorators import api_view
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import CoursePlan, CourseTopic, CourseAssignment, CourseProject, User
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import OrderingFilter
from .models import CoursePlan
from .serializers import CoursePlanSerializer
from .chatbot_utils import process_user_message


@csrf_exempt

def register_user(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Directly create user using Django ORM
                user = User.objects.create(
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],  # Note: In production, use set_password()
                    full_name=form.cleaned_data['full_name'],
                    dob=form.cleaned_data['dob']
                )
                
                # Optional: Add a success message
                messages.success(request, 'Registration successful! Please log in.')
                
                return redirect('login')
            
            except IntegrityError:
                # Handle email already exists scenario
                return render(request, 'register.html', {
                    'form': form, 
                    'error': 'An account with this email already exists.'
                })
            except Exception as e:
                # Log the error and show a generic error message
                print(f"Registration error: {str(e)}")
                return render(request, 'register.html', {
                    'form': form, 
                    'error': 'An unexpected error occurred. Please try again.'
                })
    else:
        form = RegistrationForm()

    return render(request, 'register.html', {'form': form})

def contains_whole_word(text, word):
    return re.search(r'\b' + re.escape(word) + r'\b', text) is not None
# API Views for User CRUD
class UserListCreateAPIView(generics.ListCreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'user_id'


# # Course Plan Views
# class CoursePlanListCreateView(generics.ListCreateAPIView):
#     queryset = CoursePlan.objects.all()
#     serializer_class = CoursePlanSerializer

#     def perform_create(self, serializer):
#         serializer.save()

#     def create(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#         if serializer.is_valid():
#             self.perform_create(serializer)
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class CoursePlanCreateView(generics.CreateAPIView):
#     queryset = CoursePlan.objects.all()
#     serializer_class = CoursePlanSerializer


# # Course Topic Views
# class CourseTopicCreateView(generics.CreateAPIView):
#     queryset = CourseTopic.objects.all()
#     serializer_class = CourseTopicSerializer


# # Course Project Views
# class CourseProjectCreateView(generics.CreateAPIView):
#     queryset = CourseProject.objects.all()
#     serializer_class = CourseProjectSerializer


# Login, Logout Views
def login_user(request):
    error = None
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user = User.objects.get(email=email)
            if user.password == password:
                request.session['user_id'] = user.user_id
                print(request.session.get('user_id'))
                return redirect('dashboard')  # Redirect to dashboard after login
            else:
                error = "Invalid credentials. Please try again."
        except User.DoesNotExist:
            error = "User does not exist. Please register first."

    return render(request, 'login.html', {'error': error})

def logout_user(request):
    if 'user_id' in request.session:
        print(f"Logging out user: {request.session.get('user_id')}")  # Debugging line to check user_id before clearing
        del request.session['user_id']  # Clear the session
    else:
        print("No user session to log out.")  # If there's no user logged in
    return redirect('login')  # Redirect to the login page


# Chatbot History View
# Enhanced chatbot view
# In views.py, improved context handling
# views.py - Updated chatbot_view function

@csrf_exempt
def chatbot_view(request):
    if 'user_id' not in request.session:
        return redirect('login')
    
    user_id = request.session.get('user_id')
    chat_history_key = f'chat_history_{user_id}'
    active_course_key = f'active_course_{user_id}'
    
    if request.method == 'POST':
        user_message = request.POST.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({'status': 'error', 'message': 'Message cannot be empty'}, status=400)
        
        # Check for chat history clear command
        if user_message.lower() in ['clear my chat history', 'clear chat history', 'clear history']:
            # Clear chat history from session
            request.session[chat_history_key] = []
            request.session.modified = True
            return JsonResponse({
                'status': 'success',
                'message': 'Chat history cleared. How can I help you with your courses today?',
                'chat_history': []
            })
        
        try:
            # Get current user
            user = User.objects.get(pk=user_id)
            
            # Get active course from session or default to user's first course
            active_course_id = request.session.get(active_course_key)
            context_info = {}
            
            if active_course_id:
                try:
                    # Get the active course and learning progress
                    active_course = CoursePlan.objects.get(id=active_course_id, user_id=user_id)
                    progress = LearningProgress.objects.filter(
                        user_id=user_id,
                        course_plan=active_course
                    ).first()
                    
                    context_info = {
                        'user_id': user_id,
                        'current_topic': progress.current_topic if progress and hasattr(progress, 'current_topic') else None,
                        'course_plan': active_course
                    }
                except CoursePlan.DoesNotExist:
                    # Course no longer exists, clear from session
                    if active_course_key in request.session:
                        del request.session[active_course_key]
            
            # If no context yet, provide just the user_id
            if not context_info:
                context_info = {'user_id': user_id}
            
            # Process the message with improved context
            reply = process_user_message(
                message=user_message,
                user_id=user_id,
                context=context_info
            )
            
            # Check if course was switched in the message
            # This logic detects a course mention in the message and updates the session
            mentioned_course = find_course_in_message(user_message, user_id)
            if mentioned_course:
                request.session[active_course_key] = mentioned_course.id
                request.session.modified = True
            
            # Update chat history
            chat_history = request.session.get(chat_history_key, [])
            chat_history.append({'sender': 'You', 'text': user_message})
            chat_history.append({'sender': 'AI', 'text': reply})
            request.session[chat_history_key] = chat_history[-20:]  # Keep only the last 20 messages
            request.session.modified = True
            
            return JsonResponse({
                'status': 'success', 
                'message': reply,
                'chat_history': chat_history
            })
            
        except User.DoesNotExist:
            return JsonResponse({
                'status': 'error', 
                'message': 'User not found. Please log in again.'
            }, status=401)
        
        except Exception as e:
            print(f"Error in chatbot view: {str(e)}")
            import traceback
            print(traceback.format_exc())
            
            return JsonResponse({
                'status': 'error', 
                'message': 'An unexpected error occurred. Please try again.'
            }, status=500)
    
    # For GET requests, render the chat interface
    # Get the user's course plans
    user_course_plans = CoursePlan.objects.filter(user_id=user_id)
    
    # Get current active course from session
    active_course_id = request.session.get(active_course_key)
    active_course = None
    
    if active_course_id:
        try:
            active_course = CoursePlan.objects.get(id=active_course_id, user_id=user_id)
        except CoursePlan.DoesNotExist:
            # Course no longer exists, remove from session
            if active_course_key in request.session:
                del request.session[active_course_key]
    
    # If no active course in session, default to first course
    if not active_course and user_course_plans.exists():
        active_course = user_course_plans.first()
        request.session[active_course_key] = active_course.id
        request.session.modified = True
    
    context = {
        'chat_history': request.session.get(chat_history_key, []),
        'user_course_plans': user_course_plans,
        'active_course': active_course
    }
    
    return render(request, 'chatbot.html', context)
# def course_plan_list_view(request):
#     course_plans = CoursePlan.objects.all()

#     if request.method == 'POST':
#         course_plan_name = request.POST.get('course_plan_name')
#         learning_goal = request.POST.get('learning_goal')
#         course_type = request.POST.get('course_type', 'course')
#         user_id = request.POST.get('user')

#         CoursePlan.objects.create(
#             course_plan_name=course_plan_name,
#             learning_goal=learning_goal,
#             course_type=course_type,
#             user_id=user_id
#         )
#         return redirect('course_plan_list')

#     return render(request, 'course_plan_list.html', {'course_plans': course_plans})

class CoursePlanCreateAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            user = get_object_or_404(User, pk=data['user_id'])
            course_plan = CoursePlan.objects.create(
                course_plan_name=data['course_plan_name'],
                learning_goal=data['learning_goal'],
                course_type=data['course_type'],
                user=user,
                number_of_weeks=data.get('number_of_weeks'),
                created_at=data.get('created_at', timezone.now())
            )
            return Response({'course_plan_id': course_plan.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CourseTopicCreateAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            course_plan = get_object_or_404(CoursePlan, pk=data['course_plan_id'])
            topic = CourseTopic.objects.create(
                main_topic=data['main_topic'],
                sub_topic=data['sub_topic'],
                explanation=data.get('explanation'),
                course_plan=course_plan,
                week=data.get('week')
            )
            return Response({'topic_id': topic.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CourseAssignmentCreateAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            course_plan = get_object_or_404(CoursePlan, pk=data['course_plan_id'])
            assignment = CourseAssignment.objects.create(
                assignment=data['assignment'],
                course_plan=course_plan,
                week=data['week']
            )
            return Response({'assignment_id': assignment.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CourseProjectCreateAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            course_plan = get_object_or_404(CoursePlan, pk=data['course_plan_id'])
            project = CourseProject.objects.create(
                project=data['project'],
                course_plan=course_plan
            )
            return Response({'project_id': project.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# In views.py, modify your CoursePlanCreateAPIView class to handle GET requests as well

class CoursePlanCreateAPIView(APIView):
    def post(self, request):
        # Your existing POST method code remains unchanged
        try:
            data = request.data
            user = get_object_or_404(User, pk=data['user_id'])
            course_plan = CoursePlan.objects.create(
                course_plan_name=data['course_plan_name'],
                learning_goal=data['learning_goal'],
                course_type=data['course_type'],
                user=user,
                number_of_weeks=data.get('number_of_weeks'),
                created_at=data.get('created_at', timezone.now())
            )
            return Response({'course_plan_id': course_plan.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    # Add this method to handle GET requests
    def get(self, request):
        # Get user_id from query parameters or use None
        user_id = request.query_params.get('user_id')
        
        # Initialize queryset with all course plans
        queryset = CoursePlan.objects.all()
        
        # Filter by user_id if provided
        if user_id:
            queryset = queryset.filter(user_id=user_id)
            
        # Serialize the data
        serializer = CoursePlanSerializer(queryset, many=True)
        
        # Return the serialized data
        return Response(serializer.data)

# Update the dashboard_view to show course plans
def dashboard_view(request):
    if 'user_id' not in request.session:
        return redirect('login')
    
    user_id = request.session.get('user_id')
    chat_history_key = f'chat_history_{user_id}'
    chat_history = request.session.get(chat_history_key, [])
    
    # Get course plans for the current user
    try:
        user_course_plans = CoursePlan.objects.filter(user_id=user_id)
    except Exception as e:
        print(f"Error fetching course plans: {str(e)}")
        user_course_plans = []
    
    context = {
        'user_id': user_id,
        'chat_history': chat_history,
        'course_plans': user_course_plans
    }
    
    return render(request, "dashboard.html", context)
# Home view function
def home(request):
    return render(request, 'home.html') 

def about(request):
    return render(request, 'about.html')

def course_plan_detail_view(request, course_plan_id):
    """View to display details of a specific course plan"""
    
    # Redirect to login if user is not authenticated
    if 'user_id' not in request.session:
        return redirect('login')
    
    try:
        # Get the course plan with the given ID
        course_plan = CoursePlan.objects.get(id=course_plan_id)
        
        # Check if the course plan belongs to the current user
        if course_plan.user.user_id != request.session.get('user_id'):
            messages.error(request, "You don't have permission to view this course plan.")
            return redirect('dashboard')
        
        # Get the topics for this course plan
        topics = course_plan.topics.all()  # This uses the related_name='topics' from your model
        
        # Get the assignments for this course plan
        assignments = course_plan.assignments.all()  # This uses the related_name='assignments' from your model
        
        # Parse the assignment JSON data
        import json
        assignments_parsed = []
        for assignment in assignments:
            try:
                assignment_data = json.loads(assignment.assignment)
                assignments_parsed.append({
                    'week': assignment.week,
                    'description': assignment_data.get('Assignment Description', ''),
                    'tasks': assignment_data.get('Tasks', [])
                })
            except json.JSONDecodeError:
                # Handle case where assignment data isn't valid JSON
                pass
        
        # Render the template with the course plan, topics, and assignments
        return render(request, 'course_plan_detail.html', {
            'course_plan': course_plan, 
            'topics': topics,
            'assignments': assignments,
            'assignments_parsed': assignments_parsed
        })
    
    except CoursePlan.DoesNotExist:
        messages.error(request, "Course plan not found.")
        return redirect('dashboard')

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class CoursePlanListAPIView(generics.ListAPIView):
    queryset = CoursePlan.objects.all()
    serializer_class = CoursePlanSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [OrderingFilter]
    ordering_fields = ['created_at', 'course_plan_name', 'number_of_weeks']
    ordering = ['-created_at']  # Default ordering newest first
    
    def get_queryset(self):
        queryset = CoursePlan.objects.all()
        
        # Filter by user_id
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by course_type
        course_type = self.request.query_params.get('course_type')
        if course_type:
            queryset = queryset.filter(course_type=course_type)
            
        # Filter by name (partial match)
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(course_plan_name__icontains=name)
            
        # Filter by creation date range
        created_after = self.request.query_params.get('created_after')
        if created_after:
            queryset = queryset.filter(created_at__gte=created_after)
            
        created_before = self.request.query_params.get('created_before')
        if created_before:
            queryset = queryset.filter(created_at__lte=created_before)
        
        return queryset
    
    # Add this function to your myapp/views.py file
def create_course_plan_view(request):
    """View to display the course plan form and handle submissions"""
    
    # Redirect to login if user is not authenticated
    if 'user_id' not in request.session:
        return redirect('login')
    
    if request.method == 'POST':
        # Get form data
        course_data = {
            'course_plan_name': request.POST.get('course_plan_name'),
            'learning_goal': request.POST.get('learning_goal'),
            'course_type': request.POST.get('course_type'),
            'user_id': request.session.get('user_id'),
            'start_date': request.POST.get('start_date'),
            'end_date': request.POST.get('end_date')
        }
        
        try:
            # Call FastAPI service to generate course plan
            api_response = requests.post('http://localhost:8001/api/course-plans/', json=course_data)
            
            if api_response.status_code == 200:
                # Get the newly created course plan ID
                try:
                    course_plan_id = api_response.json().get('course_plan_id')
                    if course_plan_id:
                        # Get the course plan object
                        new_course = CoursePlan.objects.get(id=course_plan_id)
                        
                        # Create learning progress for this course
                        create_learning_progress(request.session.get('user_id'), new_course)
                        
                        messages.success(request, "Course plan created successfully! Your learning progress has been initialized.")
                    else:
                        messages.success(request, "Course plan created successfully! Please wait while content is generated.")
                except Exception as e:
                    print(f"Error setting up learning progress: {str(e)}")
                    messages.success(request, "Course plan created successfully! Please wait while content is generated.")
                
                return redirect('dashboard')  # Redirect to dashboard after successful creation
            else:
                error_detail = api_response.json().get('detail', 'Unknown error occurred')
                return render(request, 'course_plan_form.html', {'error': error_detail})
                
        except requests.RequestException as e:
            return render(request, 'course_plan_form.html', {'error': f"Service error: {str(e)}"})
    
    # GET request - just render the form
    return render(request, 'course_plan_form.html')

# Add this function to your views.py
def create_learning_progress(user_id, course_plan):
    """Create a learning progress record for a newly created course"""
    # Get the first topic to set as current
    first_topic = course_plan.topics.all().order_by('id').first()
    
    if first_topic:
        # Create the learning progress record
        LearningProgress.objects.create(
            user_id=user_id,
            course_plan=course_plan,
            current_topic=first_topic,
            progress_percentage=0
        )
        return True
    return False

# Add this function to your views.py
def create_learning_progress(user_id, course_plan):
    """Create a learning progress record for a newly created course"""
    # Get the first topic to set as current
    first_topic = course_plan.topics.all().order_by('id').first()
    
    if first_topic:
        # Create the learning progress record
        LearningProgress.objects.create(
            user_id=user_id,
            course_plan=course_plan,
            current_topic=first_topic,
            progress_percentage=0
        )
        return True
    return False

def delete_course_plan(request, course_plan_id):
    try:
        course_plan = CoursePlan.objects.get(id=course_plan_id)
        
        # Safely handle CourseMapper deletion
        from .models import CourseMapper
        try:
            CourseMapper.objects.filter(course_plan=course_plan).delete()
        except Exception as mapper_error:
            print(f"Error handling CourseMapper: {mapper_error}")
        
        # Delete related objects
        LearningProgress.objects.filter(course_plan=course_plan).delete()
        course_plan.topics.all().delete()
        course_plan.assignments.all().delete()
        course_plan.projects.all().delete()
        
        course_plan.delete()
        
        messages.success(request, f"Course '{course_plan.course_plan_name}' has been deleted successfully.")
        return redirect('dashboard')
    
    except Exception as e:
        print(f"Unexpected error deleting course plan: {e}")
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('dashboard')