import re
import random
from django.utils import timezone
from django.db.models import Q
from .models import ChatContext, CourseTopic, TopicCompletion, CoursePlan, LearningProgress

def find_course_in_message(message, user_id):
    """
    Find if the user is mentioning a specific course in their message.
    Returns the course plan object if found, None otherwise.
    """
    message_lower = message.lower()
    
    # Get all course plans for this user
    user_courses = CoursePlan.objects.filter(user_id=user_id)
    
    if not user_courses:
        return None
    
    # Try to find an exact match first (course name appears in the message)
    for course in user_courses:
        # Create simplification of course name for better matching
        course_name_simple = course.course_plan_name.lower()
        
        # Check for exact course name in message
        if course_name_simple in message_lower:
            return course
    
    # If no exact match, look for partial matches with threshold
    for course in user_courses:
        course_words = set(course.course_plan_name.lower().split())
        message_words = set(message_lower.split())
        
        # Check for matching words threshold (at least 2 words or 50% of course name words)
        matching_words = course_words.intersection(message_words)
        threshold = max(2, len(course_words) // 2)
        
        if len(matching_words) >= threshold:
            return course
    
    return None

def get_or_create_learning_progress(user_id, course_plan):
    """
    Get or create a learning progress record for a user and course.
    """
    try:
        # Try to get existing progress
        progress = LearningProgress.objects.filter(
            user_id=user_id,
            course_plan=course_plan
        ).first()
        
        if not progress:
            # Create new progress record
            first_topic = course_plan.topics.all().order_by('id').first()
            progress = LearningProgress.objects.create(
                user_id=user_id,
                course_plan=course_plan,
                current_topic=first_topic,
                progress_percentage=0
            )
        
        return progress
    except Exception as e:
        print(f"Error getting/creating learning progress: {e}")
        return None

def list_available_courses(user_id):
    """Generate a response listing all available courses for the user"""
    courses = CoursePlan.objects.filter(user_id=user_id)
    
    if not courses:
        return "You don't have any courses yet. Would you like to create a new course plan?"
    
    response = "Here are your available courses:\n\n"
    for idx, course in enumerate(courses, 1):
        response += f"{idx}. {course.course_plan_name}\n"
    
    response += "\nYou can ask me about any of these courses. For example, try saying 'Let's talk about [course name]' or 'Help me with [course name]'."
    
    return response

def find_relevant_topic(message, all_topics):
    """Find the most relevant topic for a user message using text similarity"""
    message_lower = message.lower()
    best_match = None
    highest_score = 0
    
    for topic in all_topics:
        # Create a combined text of main topic and subtopic
        topic_text = f"{topic.main_topic} {topic.sub_topic}".lower()
        
        # Calculate a simple relevance score
        score = 0
        
        # Check for exact matches first (weighted higher)
        if topic.sub_topic.lower() in message_lower:
            score += 10
        if topic.main_topic.lower() in message_lower:
            score += 5
            
        # Check for individual words in the message matching topic words
        message_words = set(message_lower.split())
        topic_words = set(topic_text.split())
        
        # Count matching words
        matching_words = message_words.intersection(topic_words)
        score += len(matching_words) * 2
        
        # If we found a better match, update
        if score > highest_score:
            highest_score = score
            best_match = topic
    
    # Only return if we have a reasonable match
    if highest_score > 3:
        print(f"DEBUG: Found topic match: {best_match.sub_topic} with score {highest_score}")
        return best_match
    
    return None

def contains_whole_word(text, word):
    """Check if a word appears as a whole word in a text string."""
    return re.search(r'\b' + re.escape(word) + r'\b', text) is not None

# chatbot_utils.py - Updated function

def process_user_message(message, user_id=None, last_message=None, context=None):
    """
    Process user messages with improved context awareness and pattern matching.
    
    Args:
        message (str): The user's message
        user_id (int, optional): The user's ID for context retrieval
        last_message (str, optional): The last message from the chatbot
        context (dict, optional): Additional context information
        
    Returns:
        str: The chatbot's response
    """
    print(f"DEBUG: Message received: {message}")
    print(f"DEBUG: Context keys: {context.keys() if context else None}")
    message_lower = message.lower()

    # Handle command for clearing chat history
    if "clear my chat history" in message_lower or "clear chat history" in message_lower:
        # Note: The actual clearing happens in the view, this just responds
        return "I've cleared our chat history. What would you like to talk about now?"
    
    # Check if the message is asking about creating a new course
    create_course_phrases = ["create a new course", "create course", "new course plan", "create a course plan"]
    if any(phrase in message_lower for phrase in create_course_phrases):
        return """
To create a new course plan:
1. Go to the 'Create Course Plan' page from your dashboard
2. Fill in the course name, learning goal, and course type
3. Choose the number of weeks for your course
4. Click 'Create Course' to generate your personalized learning plan

Would you like me to help you design a curriculum for a specific subject?
        """
    
    # Check if the message is asking about available courses
    course_inquiry_phrases = [
        "what courses", "which courses", "show courses", "list courses", 
        "my courses", "available courses", "switch course", "change course"
    ]
    
    for phrase in course_inquiry_phrases:
        if phrase in message_lower:
            return list_available_courses(user_id)
    
    # Enhanced logic for detecting course switching requests
    # First, check if it's a request for an existing course
    mentioned_course = find_course_in_message(message, user_id)
    
    # If the user mentioned a course that exists, handle the switch
    if mentioned_course:
        # User mentioned a specific course, create or get progress
        progress = get_or_create_learning_progress(user_id, mentioned_course)
        
        # Update the context with the new course
        if context:
            context['course_plan'] = mentioned_course
            context['current_topic'] = progress.current_topic if progress and hasattr(progress, 'current_topic') else None
        
        # Generate a response confirming the course switch AND answering their question
        # (we'll rely on OpenAI for the actual response content)
        return handle_course_specific_question(message, mentioned_course, progress, context)
    
    # Handle requests for courses that don't exist yet
    if "let's talk about" in message_lower or "switch to" in message_lower:
        # Extract the course name
        course_name = None
        if "let's talk about" in message_lower:
            course_name = message_lower.split("let's talk about")[1].strip()
        elif "switch to" in message_lower:
            course_name = message_lower.split("switch to")[1].strip()
        
        if course_name:
            return f"""
I don't see a course called '{course_name}' in your enrolled courses. 
Would you like to create a new course plan for {course_name}? 
You can do this by going to 'Create Course Plan' from your dashboard.
            """
    
    # If no context is provided or no course plan in context, get user's courses
    if not context or not context.get('course_plan'):
        # Try to find any learning progress for this user
        user_progress = LearningProgress.objects.filter(user_id=user_id).first()
        
        if user_progress:
            # Update context with the first found course
            if context:
                context['course_plan'] = user_progress.course_plan
                context['current_topic'] = user_progress.current_topic
            else:
                context = {
                    'course_plan': user_progress.course_plan,
                    'current_topic': user_progress.current_topic,
                    'user_id': user_id
                }
        else:
            # No progress found
            if context is None:
                context = {'user_id': user_id}
    
    # If still no course plan after trying to get progress, give a generic response
    if not context or not context.get('course_plan'):
        # Generic responses for users without a course plan
        greetings = ["hi", "hello", "hey", "greetings", "howdy"]
        if any(contains_whole_word(message_lower, greet) for greet in greetings):
            return "Hello! It looks like you haven't created a course plan yet. Would you like to create one and start your learning journey?"

        # Default response for users without a course plan
        return "Welcome to the Learning Platform! To get started, please create a course plan. This will help us personalize your learning experience."

    # Get course plan and topic from context for OpenAI
    course_plan = context.get('course_plan')
    current_topic = context.get('current_topic')
    
    # Handle the question with current context
    return handle_course_specific_question(message, course_plan, current_topic, context)

def handle_course_specific_question(message, course_plan, current_topic_or_progress, context):
    """
    Helper function to generate responses for course-specific questions
    
    Args:
        message (str): The user's message
        course_plan: The current course plan
        current_topic_or_progress: Either the current topic or learning progress object
        context (dict): Additional context information
        
    Returns:
        str: The chatbot's response
    """
    # Extract current topic from progress if needed
    current_topic = None
    if hasattr(current_topic_or_progress, 'current_topic'):
        # This is a progress object
        current_topic = current_topic_or_progress.current_topic
    else:
        # This is already a topic object
        current_topic = current_topic_or_progress
    
    # Check for specific question types
    message_lower = message.lower()
    
    # Progress questions
    if "progress" in message_lower or "how far" in message_lower or "completed" in message_lower:
        # In a real implementation, calculate actual progress
        progress_percent = 0
        try:
            # Try to get progress percentage if available
            from .models import LearningProgress
            progress = LearningProgress.objects.filter(
                user_id=context.get('user_id'),
                course_plan=course_plan
            ).first()
            if progress:
                progress_percent = progress.progress_percentage
                
            completed_topics = 0
            total_topics = course_plan.topics.count()
            if hasattr(progress, 'completed_topics'):
                completed_topics = progress.completed_topics.count()
                
            return f"You've completed {progress_percent:.1f}% of the '{course_plan.course_plan_name}' course. You've finished {completed_topics} out of {total_topics} topics."
        except Exception as e:
            print(f"Error getting progress: {str(e)}")
            return f"You're currently studying the topic '{current_topic.main_topic}: {current_topic.sub_topic}' in the '{course_plan.course_plan_name}' course. Keep going!"
    
    # Try using OpenAI for natural language understanding
    try:
        from .openai_utils import get_openai_response
        
        # Prepare additional context for OpenAI
        openai_context = {
            'current_topic': current_topic,
            'course_plan': course_plan,
            'progress': 0,  # Default placeholder value
            'learning_goal': course_plan.learning_goal if course_plan else '',
            'user_message': message  # Add the user's message
        }
        
        return get_openai_response(message, openai_context)
    
    except Exception as e:
        print(f"Error calling OpenAI API: {str(e)}")
        
        # Better fallback if OpenAI fails
        if current_topic:
            return f"I'm here to help you learn about {current_topic.sub_topic} in your '{course_plan.course_plan_name}' course. What specific aspect would you like to know more about?"
        else:
            return f"I'm here to help you with your '{course_plan.course_plan_name}' course. What would you like to learn today?"