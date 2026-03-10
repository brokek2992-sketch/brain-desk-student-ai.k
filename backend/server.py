from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from emergentintegrations.llm.chat import LlmChat, UserMessage
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
from bson import ObjectId
import json
import io
import base64
from PyPDF2 import PdfReader

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'brain_desk')]

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', 'sk-emergent-4B0C38046991616673')

# SCOPES for Google APIs
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.me.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/calendar'
]

# Create the main app
app = FastAPI()

# Add session middleware with proper cookie settings
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production'),
    session_cookie='brain_desk_session',
    max_age=86400 * 7,  # 7 days
    same_site='none',  # Allow cross-domain cookies
    https_only=False  # Allow HTTP for local development
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# ==================== Models ====================

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    google_id: str
    email: str
    name: str
    picture: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Course(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    classroom_id: str
    name: str
    section: Optional[str] = None
    description: Optional[str] = None
    teacher_name: Optional[str] = None
    enrollment_code: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Assignment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    course_id: str
    classroom_id: str
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    state: str = "PENDING"  # PENDING, COMPLETED
    link: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Note(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    course_id: Optional[str] = None
    title: str
    content: str
    attachments: Optional[List[dict]] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: int

class Quiz(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    course_id: Optional[str] = None
    title: str
    questions: List[QuizQuestion]
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ==================== Request/Response Models ====================

class NoteCreate(BaseModel):
    course_id: Optional[str] = None
    title: str
    content: str
    attachments: Optional[List[dict]] = []

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    course_id: Optional[str] = None

class QuizGenerateRequest(BaseModel):
    course_id: Optional[str] = None
    topic: str
    num_questions: int = 10

# ==================== Helper Functions ====================

async def get_current_user(request: Request):
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return User(**user)

def get_google_credentials(user: User):
    if not user.access_token:
        raise HTTPException(status_code=401, detail="No Google credentials found")
    
    creds = Credentials(
        token=user.access_token,
        refresh_token=user.refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=SCOPES
    )
    return creds

async def extract_text_from_pdf(pdf_content: bytes) -> str:
    """Extract text from PDF bytes"""
    try:
        pdf_file = io.BytesIO(pdf_content)
        pdf_reader = PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Error extracting PDF text: {str(e)}")
        return ""

# ==================== Health Check Route ====================

@api_router.get("/")
async def health_check():
    """Health check endpoint"""
    return {"message": "Hello World", "status": "healthy", "service": "Brain Desk API"}

# ==================== Authentication Routes ====================

@api_router.get("/auth/login")
async def login(request: Request):
    """Initiate Google OAuth flow"""
    # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    # Use the canonical callback URL that matches Google Cloud Console configuration
    redirect_uri = "http://brain-desk-1.cluster-1.preview.emergentcf.cloud/api/auth/callback"
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        },
        scopes=SCOPES
    )
    flow.redirect_uri = redirect_uri
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    request.session['state'] = state
    request.session['redirect_uri'] = redirect_uri  # Store for callback
    return {"authorization_url": authorization_url}

@api_router.get("/auth/callback")
async def auth_callback(request: Request, code: str, state: str):
    """Handle Google OAuth callback"""
    try:
        logger.info(f"OAuth callback received - code: {code[:20]}..., state: {state}")
        
        # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
        # Use the fixed redirect_uri (not from session due to domain mismatch)
        redirect_uri = "http://brain-desk-1.cluster-1.preview.emergentcf.cloud/api/auth/callback"
        
        logger.info(f"Using redirect_uri: {redirect_uri}")
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=SCOPES
        )
        flow.redirect_uri = redirect_uri
        
        logger.info("Fetching token from Google...")
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        logger.info("Token fetched successfully")
        
        # Get user info
        from google.oauth2 import id_token
        from google.auth.transport import requests
        
        logger.info("Verifying ID token...")
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        
        google_id = id_info['sub']
        email = id_info['email']
        name = id_info.get('name', email)
        picture = id_info.get('picture', '')
        
        logger.info(f"User authenticated: {email}")
        
        # Check if user exists
        existing_user = await db.users.find_one({"google_id": google_id})
        
        if existing_user:
            # Update tokens
            await db.users.update_one(
                {"google_id": google_id},
                {"$set": {
                    "access_token": credentials.token,
                    "refresh_token": credentials.refresh_token,
                    "picture": picture
                }}
            )
            user_id = existing_user['id']
            logger.info(f"Updated existing user: {user_id}")
        else:
            # Create new user
            user = User(
                google_id=google_id,
                email=email,
                name=name,
                picture=picture,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token
            )
            await db.users.insert_one(user.dict())
            user_id = user.id
            logger.info(f"Created new user: {user_id}")
        
        # Store user_id in session (create new session for this domain)
        request.session['user_id'] = user_id
        logger.info("Session created successfully")
        
        # Redirect to frontend homepage
        frontend_url = "https://brain-desk-1.preview.emergentagent.com"
        logger.info(f"Redirecting to: {frontend_url}")
        return RedirectResponse(url=frontend_url)
        
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}", exc_info=True)
        # Return error page instead of 403
        return RedirectResponse(
            url=f"https://brain-desk-1.preview.emergentagent.com/auth/login?error={str(e)}"
        )
    
    credentials = flow.credentials
    
    # Get user info
    from google.oauth2 import id_token
    from google.auth.transport import requests
    
    id_info = id_token.verify_oauth2_token(
        credentials.id_token,
        requests.Request(),
        GOOGLE_CLIENT_ID
    )
    
    google_id = id_info['sub']
    email = id_info['email']
    name = id_info.get('name', email)
    picture = id_info.get('picture', '')
    
    # Check if user exists
    existing_user = await db.users.find_one({"google_id": google_id})
    
    if existing_user:
        # Update tokens
        await db.users.update_one(
            {"google_id": google_id},
            {"$set": {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "picture": picture
            }}
        )
        user_id = existing_user['id']
    else:
        # Create new user
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            picture=picture,
            access_token=credentials.token,
            refresh_token=credentials.refresh_token
        )
        await db.users.insert_one(user.dict())
        user_id = user.id
    
    # Store user_id in session
    request.session['user_id'] = user_id
    
    # Redirect to frontend homepage
    frontend_url = "https://brain-desk-1.preview.emergentagent.com"
    return RedirectResponse(url=frontend_url)

@api_router.get("/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    """Get current user"""
    return user

@api_router.post("/auth/logout")
async def logout(request: Request):
    """Logout user"""
    request.session.clear()
    return {"message": "Logged out successfully"}

# ==================== Google Classroom Routes ====================

@api_router.get("/sync/classroom")
async def sync_classroom(user: User = Depends(get_current_user)):
    """Sync courses and assignments from Google Classroom"""
    try:
        creds = get_google_credentials(user)
        service = build('classroom', 'v1', credentials=creds)
        
        # Fetch courses
        results = service.courses().list(pageSize=100).execute()
        courses = results.get('courses', [])
        
        synced_courses = []
        synced_assignments = []
        
        for course in courses:
            course_id = course['id']
            course_data = Course(
                user_id=user.id,
                classroom_id=course_id,
                name=course.get('name', 'Untitled Course'),
                section=course.get('section', ''),
                description=course.get('descriptionHeading', ''),
                teacher_name=course.get('ownerId', ''),
                enrollment_code=course.get('enrollmentCode', '')
            )
            
            # Check if course exists
            existing_course = await db.courses.find_one({
                "user_id": user.id,
                "classroom_id": course_id
            })
            
            if existing_course:
                await db.courses.update_one(
                    {"user_id": user.id, "classroom_id": course_id},
                    {"$set": course_data.dict()}
                )
            else:
                await db.courses.insert_one(course_data.dict())
            
            synced_courses.append(course_data)
            
            # Fetch coursework (assignments)
            try:
                coursework_results = service.courses().courseWork().list(
                    courseId=course_id
                ).execute()
                coursework_items = coursework_results.get('courseWork', [])
                
                for item in coursework_items:
                    due_date = None
                    if 'dueDate' in item:
                        due_date_data = item['dueDate']
                        due_date = datetime(
                            due_date_data.get('year', 2025),
                            due_date_data.get('month', 1),
                            due_date_data.get('day', 1)
                        )
                    
                    assignment_data = Assignment(
                        user_id=user.id,
                        course_id=course_data.id,
                        classroom_id=course_id,
                        title=item.get('title', 'Untitled Assignment'),
                        description=item.get('description', ''),
                        due_date=due_date,
                        state="PENDING",
                        link=item.get('alternateLink', '')
                    )
                    
                    existing_assignment = await db.assignments.find_one({
                        "user_id": user.id,
                        "classroom_id": course_id,
                        "title": assignment_data.title
                    })
                    
                    if not existing_assignment:
                        await db.assignments.insert_one(assignment_data.dict())
                        synced_assignments.append(assignment_data)
            
            except HttpError as e:
                logger.warning(f"Could not fetch coursework for {course_id}: {str(e)}")
        
        return {
            "message": "Sync completed",
            "courses_synced": len(synced_courses),
            "assignments_synced": len(synced_assignments)
        }
    
    except Exception as e:
        logger.error(f"Error syncing classroom: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Courses Routes ====================

@api_router.get("/courses")
async def get_courses(user: User = Depends(get_current_user)):
    """Get all courses for the user"""
    courses = await db.courses.find({"user_id": user.id}).to_list(1000)
    
    # Get counts for each course
    result = []
    for course in courses:
        notes_count = await db.notes.count_documents({
            "user_id": user.id,
            "course_id": course['id']
        })
        assignments_count = await db.assignments.count_documents({
            "user_id": user.id,
            "course_id": course['id'],
            "state": "PENDING"
        })
        
        course_data = Course(**course)
        result.append({
            **course_data.dict(),
            "notes_count": notes_count,
            "assignments_count": assignments_count
        })
    
    return result

@api_router.get("/courses/{course_id}")
async def get_course(course_id: str, user: User = Depends(get_current_user)):
    """Get a specific course"""
    course = await db.courses.find_one({"id": course_id, "user_id": user.id})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return Course(**course)

# ==================== Assignments Routes ====================

@api_router.get("/assignments")
async def get_assignments(user: User = Depends(get_current_user)):
    """Get all assignments for the user"""
    assignments = await db.assignments.find({"user_id": user.id}).sort("due_date", 1).to_list(1000)
    return [Assignment(**a) for a in assignments]

@api_router.get("/assignments/{assignment_id}")
async def get_assignment(assignment_id: str, user: User = Depends(get_current_user)):
    """Get a specific assignment"""
    assignment = await db.assignments.find_one({"id": assignment_id, "user_id": user.id})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return Assignment(**assignment)

@api_router.patch("/assignments/{assignment_id}/complete")
async def complete_assignment(assignment_id: str, user: User = Depends(get_current_user)):
    """Mark assignment as complete"""
    result = await db.assignments.update_one(
        {"id": assignment_id, "user_id": user.id},
        {"$set": {"state": "COMPLETED"}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"message": "Assignment marked as complete"}

# ==================== Notes Routes ====================

@api_router.get("/notes")
async def get_notes(course_id: Optional[str] = None, user: User = Depends(get_current_user)):
    """Get all notes for the user"""
    query = {"user_id": user.id}
    if course_id:
        query["course_id"] = course_id
    
    notes = await db.notes.find(query).sort("updated_at", -1).to_list(1000)
    return [Note(**n) for n in notes]

@api_router.post("/notes")
async def create_note(note_data: NoteCreate, user: User = Depends(get_current_user)):
    """Create a new note"""
    note = Note(
        user_id=user.id,
        course_id=note_data.course_id,
        title=note_data.title,
        content=note_data.content,
        attachments=note_data.attachments or []
    )
    await db.notes.insert_one(note.dict())
    return note

@api_router.get("/notes/{note_id}")
async def get_note(note_id: str, user: User = Depends(get_current_user)):
    """Get a specific note"""
    note = await db.notes.find_one({"id": note_id, "user_id": user.id})
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return Note(**note)

@api_router.put("/notes/{note_id}")
async def update_note(note_id: str, note_data: NoteCreate, user: User = Depends(get_current_user)):
    """Update a note"""
    result = await db.notes.update_one(
        {"id": note_id, "user_id": user.id},
        {"$set": {
            "title": note_data.title,
            "content": note_data.content,
            "attachments": note_data.attachments or [],
            "updated_at": datetime.utcnow()
        }}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note updated successfully"}

@api_router.delete("/notes/{note_id}")
async def delete_note(note_id: str, user: User = Depends(get_current_user)):
    """Delete a note"""
    result = await db.notes.delete_one({"id": note_id, "user_id": user.id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note deleted successfully"}

# ==================== AI Chat Routes ====================

@api_router.post("/chat")
async def chat(request: ChatRequest, user: User = Depends(get_current_user)):
    """Chat with AI tutor"""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        # Get relevant notes for context
        query = {"user_id": user.id}
        if request.course_id:
            query["course_id"] = request.course_id
        
        notes = await db.notes.find(query).to_list(100)
        
        # Build context from notes
        context = "Here are the student's notes:\n\n"
        for note in notes:
            context += f"Title: {note['title']}\n{note['content']}\n\n"
        
        # Create chat with context
        system_message = f"""You are a helpful AI tutor assistant for students. You help them understand concepts, generate quizzes, and study better.
        
{context}

Use the above notes to answer questions accurately. If the information isn't in the notes, provide general educational help."""
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=system_message
        )
        chat.with_model("openai", "gpt-4o")
        
        user_message = UserMessage(text=request.message)
        response = await chat.send_message(user_message)
        
        # Save chat messages
        user_msg = ChatMessage(
            user_id=user.id,
            session_id=session_id,
            role="user",
            content=request.message
        )
        assistant_msg = ChatMessage(
            user_id=user.id,
            session_id=session_id,
            role="assistant",
            content=response
        )
        
        await db.chat_messages.insert_one(user_msg.dict())
        await db.chat_messages.insert_one(assistant_msg.dict())
        
        return {
            "session_id": session_id,
            "response": response
        }
    
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str, user: User = Depends(get_current_user)):
    """Get chat history for a session"""
    messages = await db.chat_messages.find({
        "user_id": user.id,
        "session_id": session_id
    }).sort("timestamp", 1).to_list(1000)
    
    return [ChatMessage(**m) for m in messages]

@api_router.get("/chat/sessions")
async def get_chat_sessions(user: User = Depends(get_current_user)):
    """Get all chat sessions"""
    pipeline = [
        {"$match": {"user_id": user.id}},
        {"$group": {
            "_id": "$session_id",
            "last_message": {"$last": "$content"},
            "last_timestamp": {"$last": "$timestamp"}
        }},
        {"$sort": {"last_timestamp": -1}}
    ]
    
    sessions = await db.chat_messages.aggregate(pipeline).to_list(100)
    return sessions

# ==================== Quiz Routes ====================

@api_router.post("/quiz/generate")
async def generate_quiz(request: QuizGenerateRequest, user: User = Depends(get_current_user)):
    """Generate a quiz from notes"""
    try:
        # Get notes
        query = {"user_id": user.id}
        if request.course_id:
            query["course_id"] = request.course_id
        
        notes = await db.notes.find(query).to_list(100)
        
        if not notes:
            raise HTTPException(status_code=400, detail="No notes found to generate quiz from")
        
        # Build context
        context = ""
        for note in notes:
            context += f"{note['title']}\n{note['content']}\n\n"
        
        # Generate quiz using AI
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message=f"You are a quiz generator. Generate {request.num_questions} multiple choice questions based on the following content. Return ONLY a JSON array of objects with 'question', 'options' (array of 4 strings), and 'correct_answer' (0-3 index). No additional text."
        )
        chat.with_model("openai", "gpt-4o")
        
        prompt = f"Generate {request.num_questions} MCQs on the topic: {request.topic}\n\nContent:\n{context[:4000]}"
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse response
        import re
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            questions_data = json.loads(json_match.group())
            questions = [QuizQuestion(**q) for q in questions_data]
        else:
            raise HTTPException(status_code=500, detail="Failed to generate quiz")
        
        # Save quiz
        quiz = Quiz(
            user_id=user.id,
            course_id=request.course_id,
            title=f"Quiz: {request.topic}",
            questions=questions
        )
        await db.quizzes.insert_one(quiz.dict())
        
        return quiz
    
    except Exception as e:
        logger.error(f"Error generating quiz: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/quiz/{quiz_id}")
async def get_quiz(quiz_id: str, user: User = Depends(get_current_user)):
    """Get a quiz"""
    quiz = await db.quizzes.find_one({"id": quiz_id, "user_id": user.id})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return Quiz(**quiz)

# ==================== Dashboard Routes ====================

@api_router.get("/dashboard")
async def get_dashboard(user: User = Depends(get_current_user)):
    """Get dashboard data"""
    # Get today's assignments
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    
    today_assignments = await db.assignments.find({
        "user_id": user.id,
        "due_date": {"$gte": today, "$lt": tomorrow},
        "state": "PENDING"
    }).to_list(100)
    
    # Get upcoming assignments (next 7 days)
    next_week = today + timedelta(days=7)
    upcoming_assignments = await db.assignments.find({
        "user_id": user.id,
        "due_date": {"$gte": tomorrow, "$lt": next_week},
        "state": "PENDING"
    }).sort("due_date", 1).to_list(100)
    
    # Get recent notes
    recent_notes = await db.notes.find({
        "user_id": user.id
    }).sort("updated_at", -1).limit(5).to_list(5)
    
    # Get courses count
    courses_count = await db.courses.count_documents({"user_id": user.id})
    
    return {
        "today_assignments": [Assignment(**a) for a in today_assignments],
        "upcoming_assignments": [Assignment(**a) for a in upcoming_assignments],
        "recent_notes": [Note(**n) for n in recent_notes],
        "courses_count": courses_count
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
