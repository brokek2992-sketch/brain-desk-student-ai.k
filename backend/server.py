from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import google.generativeai as genai
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
import json
import io
import base64
import zipfile
from PyPDF2 import PdfReader

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'brain_desk')]

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')

# Gemini AI Configuration
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# SCOPES for Google APIs
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.me.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.readonly',
]

# Create the main app
app = FastAPI()

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get('SECRET_KEY', 'brain-desk-secret-key-change-in-prod'),
    session_cookie='brain_desk_session',
    max_age=86400 * 7,
    same_site='none',
    https_only=True
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# ==================== OAuth URLs ====================
BACKEND_URL = os.environ.get('BACKEND_URL', 'https://brain-desk-backend.onrender.com')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://brain-desk-frontend.onrender.com')
OAUTH_CALLBACK_URL = f"{BACKEND_URL}/api/auth/callback"

# In-memory state storage
oauth_states = {}

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
    state: str = "PENDING"
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
    role: str
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

class EmailAttachment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    course_id: Optional[str] = None
    email_id: str
    subject: str
    sender: str
    received_date: datetime
    file_name: str
    file_type: str
    content: str
    category: str
    confidence: float
    source: str = "email"
    attachment_data: Optional[dict] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UniversityUpdate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: str
    sender: str
    received_date: datetime
    summary: str
    category: str
    attachments: List[dict] = []
    email_id: str
    body_text: str
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

async def extract_text_from_docx(docx_bytes: bytes) -> str:
    try:
        import docx
        doc = docx.Document(io.BytesIO(docx_bytes))
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text
    except Exception as e:
        logger.error(f"Error extracting DOCX text: {str(e)}")
        return ""

async def ask_gemini(prompt: str, system_context: str = "") -> str:
    """Send a message to Gemini and get a response"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        full_prompt = f"{system_context}\n\n{prompt}" if system_context else prompt
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini error: {str(e)}")
        return "I'm sorry, I couldn't process that request. Please try again."

# ==================== Health Check ====================

@api_router.get("/")
async def health_check():
    return {"message": "Brain Desk API is running!", "status": "healthy"}

# ==================== Authentication Routes ====================

@api_router.get("/auth/login")
async def login(request: Request):
    try:
        import secrets
        from urllib.parse import urlencode

        state = secrets.token_urlsafe(32)
        oauth_states[state] = {'created_at': datetime.utcnow()}

        auth_params = {
            'client_id': GOOGLE_CLIENT_ID,
            'redirect_uri': OAUTH_CALLBACK_URL,
            'response_type': 'code',
            'scope': ' '.join(SCOPES),
            'state': state,
            'access_type': 'offline',
            'include_granted_scopes': 'true',
            'prompt': 'consent'
        }

        authorization_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(auth_params)}"
        logger.info(f"Login initiated, callback: {OAUTH_CALLBACK_URL}")
        return {"authorization_url": authorization_url}

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None
):
    try:
        if error:
            return RedirectResponse(url=f"{FRONTEND_URL}/auth/login?error={error}")

        if not code or not state:
            return RedirectResponse(url=f"{FRONTEND_URL}/auth/login?error=missing_params")

        if state not in oauth_states:
            return RedirectResponse(url=f"{FRONTEND_URL}/auth/login?error=invalid_state")

        del oauth_states[state]

        import requests as http_requests

        token_response = http_requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": OAUTH_CALLBACK_URL,
                "grant_type": "authorization_code"
            }
        )

        if token_response.status_code != 200:
            logger.error(f"Token exchange failed: {token_response.text}")
            return RedirectResponse(url=f"{FRONTEND_URL}/auth/login?error=token_failed")

        token_data = token_response.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        id_token_str = token_data.get("id_token")

        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        id_info = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )

        google_id = id_info['sub']
        email = id_info['email']
        name = id_info.get('name', email)
        picture = id_info.get('picture', '')

        existing_user = await db.users.find_one({"google_id": google_id})

        if existing_user:
            await db.users.update_one(
                {"google_id": google_id},
                {"$set": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "picture": picture,
                    "name": name
                }}
            )
            user_id = existing_user['id']
        else:
            user = User(
                google_id=google_id,
                email=email,
                name=name,
                picture=picture,
                access_token=access_token,
                refresh_token=refresh_token
            )
            await db.users.insert_one(user.dict())
            user_id = user.id

        request.session['user_id'] = user_id
        logger.info(f"User logged in: {email}")
        return RedirectResponse(url=f"{FRONTEND_URL}?auth_success=true&user_id={user_id}")

    except Exception as e:
        logger.error(f"Callback error: {str(e)}", exc_info=True)
        return RedirectResponse(url=f"{FRONTEND_URL}/auth/login?error=unexpected")


@api_router.get("/auth/user/{user_id}")
async def get_user_by_id(user_id: str):
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return User(**user)


@api_router.get("/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    return user


@api_router.post("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out successfully"}

# ==================== Google Classroom Sync ====================

@api_router.get("/sync/classroom")
async def sync_classroom(user: User = Depends(get_current_user)):
    try:
        creds = get_google_credentials(user)
        classroom_service = build('classroom', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)

        results = classroom_service.courses().list(pageSize=100).execute()
        courses = results.get('courses', [])

        synced_courses = []
        synced_assignments = []
        synced_notes = 0

        for course in courses:
            course_id = course['id']
            course_name = course.get('name', 'Untitled Course')

            course_data = Course(
                user_id=user.id,
                classroom_id=course_id,
                name=course_name,
                section=course.get('section', ''),
                description=course.get('descriptionHeading', ''),
                teacher_name=course.get('ownerId', ''),
                enrollment_code=course.get('enrollmentCode', '')
            )

            existing_course = await db.courses.find_one({
                "user_id": user.id,
                "classroom_id": course_id
            })

            if existing_course:
                await db.courses.update_one(
                    {"user_id": user.id, "classroom_id": course_id},
                    {"$set": course_data.dict()}
                )
                db_course_id = existing_course['id']
            else:
                await db.courses.insert_one(course_data.dict())
                db_course_id = course_data.id

            synced_courses.append(course_data)

            # Fetch coursework
            try:
                coursework_results = classroom_service.courses().courseWork().list(
                    courseId=course_id
                ).execute()
                coursework_items = coursework_results.get('courseWork', [])

                for item in coursework_items:
                    due_date = None
                    if 'dueDate' in item:
                        d = item['dueDate']
                        due_date = datetime(d.get('year', 2025), d.get('month', 1), d.get('day', 1))

                    assignment_data = Assignment(
                        user_id=user.id,
                        course_id=db_course_id,
                        classroom_id=course_id,
                        title=item.get('title', 'Untitled'),
                        description=item.get('description', ''),
                        due_date=due_date,
                        state="PENDING",
                        link=item.get('alternateLink', '')
                    )

                    existing = await db.assignments.find_one({
                        "user_id": user.id,
                        "classroom_id": course_id,
                        "title": assignment_data.title
                    })

                    if not existing:
                        await db.assignments.insert_one(assignment_data.dict())
                        synced_assignments.append(assignment_data)

                    # Process materials
                    for material in item.get('materials', []):
                        if 'driveFile' in material:
                            drive_file = material['driveFile']['driveFile']
                            file_id = drive_file['id']
                            file_title = drive_file.get('title', 'Untitled')

                            if file_title.lower().endswith('.pdf'):
                                try:
                                    req = drive_service.files().get_media(fileId=file_id)
                                    file_content = io.BytesIO()
                                    downloader = MediaIoBaseDownload(file_content, req)
                                    done = False
                                    while not done:
                                        _, done = downloader.next_chunk()
                                    file_content.seek(0)
                                    pdf_text = await extract_text_from_pdf(file_content.read())

                                    if pdf_text:
                                        existing_note = await db.notes.find_one({
                                            "user_id": user.id,
                                            "course_id": db_course_id,
                                            "title": file_title
                                        })
                                        if not existing_note:
                                            note = Note(
                                                user_id=user.id,
                                                course_id=db_course_id,
                                                title=file_title,
                                                content=pdf_text[:10000],
                                                attachments=[{'type': 'drive_file', 'file_id': file_id}]
                                            )
                                            await db.notes.insert_one(note.dict())
                                            synced_notes += 1
                                except Exception as e:
                                    logger.error(f"PDF error: {str(e)}")

            except HttpError as e:
                logger.warning(f"Coursework fetch error: {str(e)}")

        return {
            "message": "Sync completed",
            "courses_synced": len(synced_courses),
            "assignments_synced": len(synced_assignments),
            "notes_synced": synced_notes
        }

    except Exception as e:
        logger.error(f"Classroom sync error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Courses Routes ====================

@api_router.get("/courses")
async def get_courses(user: User = Depends(get_current_user)):
    courses = await db.courses.find({"user_id": user.id}).to_list(1000)
    result = []
    for course in courses:
        notes_count = await db.notes.count_documents({"user_id": user.id, "course_id": course['id']})
        assignments_count = await db.assignments.count_documents({
            "user_id": user.id, "course_id": course['id'], "state": "PENDING"
        })
        result.append({**Course(**course).dict(), "notes_count": notes_count, "assignments_count": assignments_count})
    return result


@api_router.get("/courses/{course_id}")
async def get_course(course_id: str, user: User = Depends(get_current_user)):
    course = await db.courses.find_one({"id": course_id, "user_id": user.id})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return Course(**course)


@api_router.get("/courses/{course_id}/files")
async def get_course_files(course_id: str, user: User = Depends(get_current_user)):
    notes = await db.notes.find({"user_id": user.id, "course_id": course_id}).sort("created_at", -1).to_list(1000)
    email_notes = await db.email_attachments.find({"user_id": user.id, "course_id": course_id}).to_list(1000)

    files = []
    for note in notes:
        files.append({
            "id": note['id'], "title": note['title'], "content": note['content'],
            "created_at": note['created_at'], "source": "classroom",
            "content_preview": note['content'][:200] + "..." if len(note['content']) > 200 else note['content'],
            "content_length": len(note['content']),
            "file_type": "PDF" if note['title'].lower().endswith('.pdf') else "Document"
        })
    for en in email_notes:
        files.append({
            "id": en['id'], "title": en['file_name'], "content": en['content'],
            "created_at": en['received_date'], "source": "email",
            "sender": en.get('sender', ''), "subject": en.get('subject', ''),
            "content_preview": en['content'][:200] + "..." if len(en['content']) > 200 else en['content'],
            "content_length": len(en['content']), "file_type": en.get('file_type', 'Document')
        })

    files.sort(key=lambda x: x['created_at'], reverse=True)
    return {"course_id": course_id, "total_files": len(files), "files": files}


@api_router.get("/courses/{course_id}/download")
async def download_course_files(course_id: str, user: User = Depends(get_current_user)):
    course = await db.courses.find_one({"id": course_id, "user_id": user.id})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    notes = await db.notes.find({"user_id": user.id, "course_id": course_id}).to_list(1000)
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for note in notes:
            filename = note['title'] if note['title'].endswith(('.txt', '.pdf')) else note['title'] + '.txt'
            zf.writestr(filename, note['content'])

    zip_buffer.seek(0)
    course_name = course['name'].replace('/', '-')
    return StreamingResponse(zip_buffer, media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={course_name}_files.zip"})

# ==================== Assignments Routes ====================

@api_router.get("/assignments")
async def get_assignments(user: User = Depends(get_current_user)):
    assignments = await db.assignments.find({"user_id": user.id}).sort("due_date", 1).to_list(1000)
    return [Assignment(**a) for a in assignments]


@api_router.patch("/assignments/{assignment_id}/complete")
async def complete_assignment(assignment_id: str, user: User = Depends(get_current_user)):
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
    query = {"user_id": user.id}
    if course_id:
        query["course_id"] = course_id
    notes = await db.notes.find(query).sort("updated_at", -1).to_list(1000)
    return [Note(**n) for n in notes]


@api_router.post("/notes")
async def create_note(note_data: NoteCreate, user: User = Depends(get_current_user)):
    note = Note(user_id=user.id, course_id=note_data.course_id,
                title=note_data.title, content=note_data.content,
                attachments=note_data.attachments or [])
    await db.notes.insert_one(note.dict())
    return note


@api_router.put("/notes/{note_id}")
async def update_note(note_id: str, note_data: NoteCreate, user: User = Depends(get_current_user)):
    result = await db.notes.update_one(
        {"id": note_id, "user_id": user.id},
        {"$set": {"title": note_data.title, "content": note_data.content,
                  "attachments": note_data.attachments or [], "updated_at": datetime.utcnow()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note updated"}


@api_router.delete("/notes/{note_id}")
async def delete_note(note_id: str, user: User = Depends(get_current_user)):
    result = await db.notes.delete_one({"id": note_id, "user_id": user.id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note deleted"}

# ==================== AI Chat (Gemini) ====================

@api_router.post("/chat")
async def chat(request: ChatRequest, user: User = Depends(get_current_user)):
    try:
        session_id = request.session_id or str(uuid.uuid4())
        courses = await db.courses.find({"user_id": user.id}).to_list(100)

        identified_course_id = request.course_id
        identified_course_name = None

        if not identified_course_id:
            msg_lower = request.message.lower()
            for course in courses:
                if course['name'].lower() in msg_lower:
                    identified_course_id = course['id']
                    identified_course_name = course['name']
                    break
        else:
            for course in courses:
                if course['id'] == identified_course_id:
                    identified_course_name = course['name']
                    break

        query = {"user_id": user.id}
        if identified_course_id:
            query["course_id"] = identified_course_id

        notes = await db.notes.find(query).to_list(50)

        context = ""
        if notes:
            context = f"=== COURSE MATERIALS: {identified_course_name or 'ALL COURSES'} ===\n\n"
            for note in notes:
                context += f"📄 {note['title']}\n{note['content'][:2000]}\n\n{'='*40}\n\n"
        else:
            context = "No course materials synced yet. Please sync your Google Classroom first.\n"

        system_prompt = f"""You are Brain Desk AI, a helpful study assistant for a college student.
        
You have access to the student's course materials below. When answering:
1. Search through the materials first
2. Cite which document your answer comes from
3. If not in materials, say so and give general guidance
4. Be concise and student-friendly

{context}"""

        response = await ask_gemini(request.message, system_prompt)

        user_msg = ChatMessage(user_id=user.id, session_id=session_id, role="user", content=request.message)
        assistant_msg = ChatMessage(user_id=user.id, session_id=session_id, role="assistant", content=response)

        await db.chat_messages.insert_one(user_msg.dict())
        await db.chat_messages.insert_one(assistant_msg.dict())

        return {
            "session_id": session_id,
            "response": response,
            "notes_used": len(notes),
            "course_identified": identified_course_name
        }

    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str, user: User = Depends(get_current_user)):
    messages = await db.chat_messages.find({
        "user_id": user.id, "session_id": session_id
    }).sort("timestamp", 1).to_list(1000)
    return [ChatMessage(**m) for m in messages]

# ==================== Quiz (Gemini) ====================

@api_router.post("/quiz/generate")
async def generate_quiz(request: QuizGenerateRequest, user: User = Depends(get_current_user)):
    try:
        query = {"user_id": user.id}
        if request.course_id:
            query["course_id"] = request.course_id

        notes = await db.notes.find(query).to_list(20)
        if not notes:
            raise HTTPException(status_code=400, detail="No notes found")

        context = "\n\n".join([f"{n['title']}\n{n['content'][:1000]}" for n in notes])

        prompt = f"""Generate {request.num_questions} multiple choice questions on: {request.topic}

Content:
{context[:3000]}

Return ONLY a JSON array. Each object must have:
- "question": string
- "options": array of 4 strings
- "correct_answer": number 0-3

No extra text, just the JSON array."""

        response = await ask_gemini(prompt)

        import re
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if not json_match:
            raise HTTPException(status_code=500, detail="Failed to generate quiz")

        questions_data = json.loads(json_match.group())
        questions = [QuizQuestion(**q) for q in questions_data]

        quiz = Quiz(user_id=user.id, course_id=request.course_id,
                    title=f"Quiz: {request.topic}", questions=questions)
        await db.quizzes.insert_one(quiz.dict())
        return quiz

    except Exception as e:
        logger.error(f"Quiz error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Calendar ====================

@api_router.get("/calendar/events")
async def get_calendar_events(month: int = None, year: int = None, user: User = Depends(get_current_user)):
    if not month or not year:
        now = datetime.utcnow()
        month, year = now.month, now.year

    start_date = datetime(year, month, 1)
    end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    assignments = await db.assignments.find({
        "user_id": user.id,
        "due_date": {"$gte": start_date, "$lt": end_date}
    }).to_list(1000)

    notes = await db.notes.find({
        "user_id": user.id,
        "created_at": {"$gte": start_date, "$lt": end_date}
    }).to_list(1000)

    course_ids = set([a['course_id'] for a in assignments] + [n.get('course_id') for n in notes if n.get('course_id')])
    courses_map = {}
    for cid in course_ids:
        if cid:
            c = await db.courses.find_one({"id": cid, "user_id": user.id})
            if c:
                courses_map[cid] = c['name']

    events_by_date = {}
    for a in assignments:
        if a.get('due_date'):
            key = a['due_date'].strftime('%Y-%m-%d')
            if key not in events_by_date:
                events_by_date[key] = {"assignments": [], "notes": []}
            events_by_date[key]["assignments"].append({
                "id": a['id'], "title": a['title'],
                "course_name": courses_map.get(a['course_id'], 'Unknown'),
                "state": a.get('state', 'PENDING')
            })

    for n in notes:
        key = n['created_at'].strftime('%Y-%m-%d')
        if key not in events_by_date:
            events_by_date[key] = {"assignments": [], "notes": []}
        events_by_date[key]["notes"].append({
            "id": n['id'], "title": n['title'],
            "course_name": courses_map.get(n.get('course_id'), 'Unknown')
        })

    return {"month": month, "year": year, "events_by_date": events_by_date,
            "total_assignments": len(assignments), "total_notes": len(notes)}

# ==================== Dashboard ====================

@api_router.get("/dashboard")
async def get_dashboard(user: User = Depends(get_current_user)):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    next_week = today + timedelta(days=7)

    today_assignments = await db.assignments.find({
        "user_id": user.id,
        "due_date": {"$gte": today, "$lt": tomorrow},
        "state": "PENDING"
    }).to_list(100)

    upcoming = await db.assignments.find({
        "user_id": user.id,
        "due_date": {"$gte": tomorrow, "$lt": next_week},
        "state": "PENDING"
    }).sort("due_date", 1).to_list(100)

    recent_notes = await db.notes.find({"user_id": user.id}).sort("updated_at", -1).limit(5).to_list(5)
    courses_count = await db.courses.count_documents({"user_id": user.id})

    return {
        "today_assignments": [Assignment(**a) for a in today_assignments],
        "upcoming_assignments": [Assignment(**a) for a in upcoming],
        "recent_notes": [Note(**n) for n in recent_notes],
        "courses_count": courses_count
    }


@api_router.get("/sync/stats")
async def get_sync_stats(user: User = Depends(get_current_user)):
    courses = await db.courses.find({"user_id": user.id}).to_list(100)
    stats = {"total_courses": len(courses), "total_notes": 0, "total_assignments": 0, "courses_detail": []}

    for course in courses:
        notes_count = await db.notes.count_documents({"user_id": user.id, "course_id": course['id']})
        assignments_count = await db.assignments.count_documents({"user_id": user.id, "course_id": course['id']})
        stats["total_notes"] += notes_count
        stats["total_assignments"] += assignments_count
        stats["courses_detail"].append({
            "name": course['name'],
            "notes_count": notes_count,
            "assignments_count": assignments_count
        })
    return stats

# ==================== Email Sync ====================

@api_router.get("/sync/email")
async def sync_email(user: User = Depends(get_current_user)):
    try:
        creds = get_google_credentials(user)
        gmail_service = build('gmail', 'v1', credentials=creds)

        courses = await db.courses.find({"user_id": user.id}).to_list(100)
        course_map = {c['name'].lower(): c['id'] for c in courses}

        results = gmail_service.users().messages().list(
            userId='me', q='has:attachment newer_than:30d', maxResults=50
        ).execute()

        messages = results.get('messages', [])
        synced = 0

        for msg_ref in messages:
            try:
                message = gmail_service.users().messages().get(
                    userId='me', id=msg_ref['id'], format='full'
                ).execute()

                headers = message['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
                date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')

                from email.utils import parsedate_to_datetime
                received_date = parsedate_to_datetime(date_str) if date_str else datetime.utcnow()

                academic_keywords = ['assignment', 'lecture', 'class', 'exam', 'submission', 'syllabus', 'notes']
                if not any(kw in subject.lower() for kw in academic_keywords):
                    continue

                parts = message['payload'].get('parts', [])

                def get_attachments(parts):
                    atts = []
                    for part in parts:
                        if part.get('filename'):
                            atts.append(part)
                        if part.get('parts'):
                            atts.extend(get_attachments(part['parts']))
                    return atts

                attachments = get_attachments(parts)

                mapped_course_id = None
                for course_name in course_map:
                    if course_name in subject.lower():
                        mapped_course_id = course_map[course_name]
                        break

                for attachment in attachments[:3]:
                    filename = attachment['filename']
                    if not any(filename.lower().endswith(ext) for ext in ['.pdf', '.docx', '.pptx']):
                        continue

                    att_id = attachment['body'].get('attachmentId')
                    if not att_id:
                        continue

                    existing = await db.email_attachments.find_one({
                        "email_id": msg_ref['id'], "file_name": filename, "user_id": user.id
                    })
                    if existing:
                        continue

                    att_data = gmail_service.users().messages().attachments().get(
                        userId='me', messageId=msg_ref['id'], id=att_id
                    ).execute()

                    file_data = base64.urlsafe_b64decode(att_data['data'])
                    text_content = ""
                    if filename.lower().endswith('.pdf'):
                        text_content = await extract_text_from_pdf(file_data)
                    elif filename.lower().endswith('.docx'):
                        text_content = await extract_text_from_docx(file_data)

                    email_att = EmailAttachment(
                        user_id=user.id, course_id=mapped_course_id,
                        email_id=msg_ref['id'], subject=subject, sender=sender,
                        received_date=received_date, file_name=filename,
                        file_type='PDF' if filename.lower().endswith('.pdf') else 'Document',
                        content=text_content[:10000], category='course_material' if mapped_course_id else 'unsorted',
                        confidence=0.9 if mapped_course_id else 0.0
                    )
                    await db.email_attachments.insert_one(email_att.dict())
                    synced += 1

            except Exception as e:
                logger.error(f"Email processing error: {str(e)}")

        return {"message": "Email sync completed", "attachments_synced": synced}

    except Exception as e:
        logger.error(f"Email sync error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ==================== App Setup ====================

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
