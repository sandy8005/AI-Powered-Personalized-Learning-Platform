import openai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from datetime import datetime
import json
import re
import httpx
from fastapi.middleware.cors import CORSMiddleware


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "FastAPI server is running"}

@app.get("/test")
async def test():
    return {"message": "Test endpoint is working"}

class CoursePlan(BaseModel):
    course_plan_name: str
    learning_goal: str
    course_type: str  
    user_id: int
    start_date: str
    end_date: str

def generate_course_content(course_name: str, learning_goal: str, number_of_weeks: int):
    try:
        prompt = f"""
        Generate a course plan for:
        Goal: {learning_goal}
        Course: {course_name}
        Duration: {number_of_weeks} weeks
        Format (example):
        {{
            "Week 1": {{
                "Topic 1": ["Subtopic A", "Subtopic B"],
                "Topic 2": ["Subtopic C"]
            }},
            "Week 2": {{
                "Topic 3": ["Subtopic D"]
            }}
        }}
        """
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a course generator"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return parse_course_plan(response['choices'][0]['message']['content'].strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating course content: {str(e)}")

def parse_course_plan(course_structure: str) -> dict:
    try:
        match = re.search(r"\{.*\}", course_structure, re.DOTALL)
        return json.loads(match.group(0).strip()) if match else {}
    except json.JSONDecodeError:
        return {}


async def post_to_api(url: str, data: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data)
        try:
            return response.json()
        except Exception:
            print(f"Failed to parse JSON from {url}")
            print("Raw Response Text:", response.text)
            return {"error": "Invalid JSON response", "status_code": response.status_code}

async def generate_assignments_for_plan(structured_plan: dict) -> dict:
    for _ in range(5):
        try:
            prompt = f"""
Using the following course plan JSON, generate weekly assignments in a valid JSON format.
Each assignment should include:
  - "Assignment Description": a brief summary of what the assignment is about,
  - "Tasks": a list of one or more tasks that the student must complete.
Make sure to output only the JSON without any extra explanation.
Example output format:
{{
    "Week 1": {{
        "Assignment Description": "Solve practical exercises on basic concepts.",
        "Tasks": ["Task 1", "Task 2"]
    }},
    "Week 2": {{
        "Assignment Description": "Implement a small project using Python libraries.",
        "Tasks": ["Task 1", "Task 2"]
    }}
}}
Course plan:
{json.dumps(structured_plan, indent=2)}
"""
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an assignment generator"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            match = re.search(r"\{.*\}", response['choices'][0]['message']['content'].strip(), re.DOTALL)
            if match:
                return json.loads(match.group(0).strip())
            else:
                continue
        except Exception:
            continue
    return {}

async def generate_project(course_name: str, course_plan: dict) -> str:
    try:
        all_topics = [f"{mt}: {st}" for topics in course_plan.values() for mt, sts in topics.items() for st in sts]
        prompt = f"Create a practical project for '{course_name}' using these topics: {all_topics}"
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a project generator"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating project: {str(e)}")

async def generate_subtopic_explanation(main_topic: str, sub_topic: str):
    try:
        prompt = f"Explain the subtopic '{sub_topic}' under '{main_topic}' clearly."
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an educational content generator"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating explanation for {sub_topic}: {str(e)}")


def convert_week_to_int(week_label: str) -> int:
    digits = ''.join(filter(str.isdigit, week_label))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

@app.post("/api/course-plans/")
async def create_course_plan(course: CoursePlan):
    print(f"Endpoint hit: /api/course-plans/ with data: {course.dict()}")
    try:
        print("Step 1: Input received", course.dict())
        number_of_weeks = (datetime.strptime(course.end_date, "%Y-%m-%d") - datetime.strptime(course.start_date, "%Y-%m-%d")).days // 7
        print("Step 2: number_of_weeks =", number_of_weeks)

        course_data = {
            "course_plan_name": course.course_plan_name,
            "learning_goal": course.learning_goal,
            "course_type": course.course_type,
            "user_id": course.user_id,
            "number_of_weeks": number_of_weeks
        }

        print(" Step 3: Posting course plan")
    
        course_plan_response = await post_to_api("http://localhost:8000/api/api/course-plans/", course_data)
        print("Response from Django (course plan):", course_plan_response)

        course_plan_id = course_plan_response.get("course_plan_id")
        if not course_plan_id:
            raise HTTPException(status_code=500, detail="course_plan_id not returned")

        structured_course_content = generate_course_content(course.course_plan_name, course.learning_goal, number_of_weeks)
        print("Step 4: structured_course_content generated")
        print("Structured Course Content:", structured_course_content)

        
        if course.course_type == 'course':
            for week_label, topics in structured_course_content.items():
                week_int = convert_week_to_int(week_label)
                for main_topic, subtopics in topics.items():
                    for sub_topic in subtopics:
                        topic_data = {
                            "main_topic": main_topic,
                            "sub_topic": sub_topic,
                            "explanation": await generate_subtopic_explanation(main_topic, sub_topic),
                            "course_plan_id": course_plan_id,
                            "week": week_int
                        }
                        print("Posting topic:", topic_data)
                        resp = await post_to_api("http://localhost:8000/api/api/course-topics/", topic_data)
                        print("Topic post response:", resp)

        # Branch for "course_assignment" (assignments and topics)
        elif course.course_type == 'course_assignment':
            print("Generating assignments (course_assignment)...")
            assignments = await generate_assignments_for_plan(structured_course_content)
            print("Assignments generated (course_assignment):", assignments)
            for week_label, assignment in assignments.items():
                week_int = convert_week_to_int(week_label)
                assignment_data = {
                    "assignment": json.dumps(assignment),
                    "course_plan_id": course_plan_id,
                    "week": week_int
                }
                print("Posting assignment (course_assignment):", assignment_data)
                resp = await post_to_api("http://localhost:8000/api/api/course-assignments/", assignment_data)
                print("Assignment post response (course_assignment):", resp)

            print("Posting topics (course_assignment)...")
            for week_label, topics in structured_course_content.items():
                week_int = convert_week_to_int(week_label)
                for main_topic, subtopics in topics.items():
                    for sub_topic in subtopics:
                        topic_data = {
                            "main_topic": main_topic,
                            "sub_topic": sub_topic,
                            "explanation": await generate_subtopic_explanation(main_topic, sub_topic),
                            "course_plan_id": course_plan_id,
                            "week": week_int
                        }
                        print("Posting topic (course_assignment):", topic_data)
                        resp = await post_to_api("http://localhost:8000/api/api/course-topics/", topic_data)
                        print(" Topic post response (course_assignment):", resp)

        # Branch for "course_assignment_project" (assignments, topics, and project)
        elif course.course_type == 'course_assignment_project':
            print("Generating assignments (course_assignment_project)...")
            assignments = await generate_assignments_for_plan(structured_course_content)
            print("Assignments generated (course_assignment_project):", assignments)
            for week_label, assignment in assignments.items():
                week_int = convert_week_to_int(week_label)
                assignment_data = {
                    "assignment": json.dumps(assignment),
                    "course_plan_id": course_plan_id,
                    "week": week_int
                }
                print("Posting assignment (course_assignment_project):", assignment_data)
                resp = await post_to_api("http://localhost:8000/api/api/course-assignments/", assignment_data)
                print("Assignment post response (course_assignment_project):", resp)

            print("Posting topics (course_assignment_project)...")
            for week_label, topics in structured_course_content.items():
                week_int = convert_week_to_int(week_label)
                for main_topic, subtopics in topics.items():
                    for sub_topic in subtopics:
                        topic_data = {
                            "main_topic": main_topic,
                            "sub_topic": sub_topic,
                            "explanation": await generate_subtopic_explanation(main_topic, sub_topic),
                            "course_plan_id": course_plan_id,
                            "week": week_int
                        }
                        print("Posting topic (course_assignment_project):", topic_data)
                        resp = await post_to_api("http://localhost:8000/api/api/course-topics/", topic_data)
                        print("Topic post response (course_assignment_project):", resp)

            print("Generating and posting project (course_assignment_project)...")
            project_description = await generate_project(course.course_plan_name, structured_course_content)
            project_data = {
                "project": project_description,
                "course_plan_id": course_plan_id
            }
            print("Posting project (course_assignment_project):", project_data)
            resp = await post_to_api("http://localhost:8000/api/api/course-projects/", project_data)
            print("Project post response (course_assignment_project):", resp)

        return {"message": "Course plan created successfully", "course_plan_id": course_plan_id}

    except Exception as e:
        print("Error in create_course_plan:", str(e))
        raise HTTPException(status_code=500, detail=f"Error creating course plan: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)