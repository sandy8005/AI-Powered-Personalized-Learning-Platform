from openai import OpenAI
from decouple import config
import traceback
import time

# Debug API key configuration - will show if key is present, not the actual key
api_key = config('OPENAI_API_KEY', default=None)
print(f"DEBUG: OpenAI API Key configured: {'YES' if api_key else 'NO'}")

# Initialize the client properly
client = OpenAI(api_key=api_key)

def get_openai_response(message, user_context=None):
    """
    Get a response from OpenAI's API with enhanced context-aware prompting
    
    Args:
        message (str): The user's message
        user_context (dict, optional): Additional context about the user and their learning progress
        
    Returns:
        str: The AI assistant's response
    """
    start_time = time.time()
    print(f"DEBUG: Starting OpenAI API call for message: '{message[:30]}...'")
    
    try:
        # Build the system message with relevant context
        system_message = "You are a helpful and knowledgeable AI tutor for an online learning platform. "
        
        # Add context about current topic if available
        if user_context and user_context.get('current_topic'):
            topic = user_context['current_topic']
            system_message += f"The user is currently learning about '{topic.main_topic}: {topic.sub_topic}'. "
            
            # Add explanation context if available
            if hasattr(topic, 'explanation') and topic.explanation:
                system_message += f"Here's the explanation for this topic: {topic.explanation} "
        
        # Add context about course plan if available
        if user_context and user_context.get('course_plan'):
            course = user_context['course_plan']
            system_message += f"They are following the course '{course.course_plan_name}'. "
            
            # Add more detailed course information
            if hasattr(course, 'learning_goal') and course.learning_goal:
                system_message += f"Their learning goal is: {course.learning_goal}. "
                
            # Add information about other topics in the course
            if hasattr(course, 'topics'):
                topics = course.topics.all()
                if topics.exists():
                    system_message += "The course includes these topics: "
                    for topic in topics[:5]:  # Limit to 5 to avoid token limit
                        system_message += f"'{topic.main_topic}: {topic.sub_topic}', "
                    system_message = system_message.rstrip(", ") + ". "
        
        # Add progress information if available
        if user_context and user_context.get('progress') is not None:
            progress = user_context['progress']
            system_message += f"They have completed {progress:.1f}% of their current course. "
        
        # Add critical instructions for response quality
        system_message += """
VERY IMPORTANT INSTRUCTIONS:
1. ALWAYS respond directly to the user's specific question. Do not just say you'll help with their course.
2. Provide informative, educational content in your response. Don't just acknowledge the topic.
3. If the user asks about a topic, explain the concept clearly and provide examples.
4. Keep responses concise (3-5 sentences) but substantive and focused on educational content.
5. If you don't know the answer to a specific question, suggest resources or ask a clarifying question.
6. Focus on being a helpful teacher, not just an assistant.
"""
        
        print(f"DEBUG: Sending system message of length {len(system_message)}")
        
        # Create the chat completion with a higher token limit for more detailed responses
        print("DEBUG: Calling OpenAI API...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # You can use "gpt-4" for more advanced responses if available
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": message}
            ],
            max_tokens=350,  # Increased from 150 to allow more detailed responses
            temperature=0.7   # Moderate creativity
        )
        
        elapsed_time = time.time() - start_time
        print(f"DEBUG: OpenAI API call successful! Took {elapsed_time:.2f} seconds")
        print(f"DEBUG: Response length: {len(response.choices[0].message.content)} characters")
        
        # Extract and return the response content
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"ERROR: OpenAI API call failed: {str(e)}")
        print(f"ERROR: Full traceback: {traceback.format_exc()}")
        
        # Provide a helpful fallback response
        if user_context and user_context.get('current_topic'):
            topic = user_context['current_topic']
            return f"I'm having trouble connecting to my knowledge base right now. In the meantime, could you tell me what specific aspect of '{topic.sub_topic}' you'd like to learn more about?"
        
        return "I'm having trouble connecting to my knowledge base right now. Could you please ask a specific question about your course material instead?"


def test_api_connection():
    """
    Test function to verify OpenAI API connectivity
    Run this directly to check if the API is working
    """
    try:
        print("Testing OpenAI API connection...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello world"}
            ],
            max_tokens=10
        )
        print(f"API TEST SUCCESSFUL! Response: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"API TEST FAILED: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return False

# Automatically run the test if this file is executed directly
if __name__ == "__main__":
    test_api_connection()