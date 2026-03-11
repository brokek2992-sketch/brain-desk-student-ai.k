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
from googleapiclient.http import MediaIoBaseDownload
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

# Add session middleware with proper cookie settings for HTTPS
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production'),
    session_cookie='brain_desk_session',
    max_age=86400 * 7,  # 7 days
    same_site='none',  # Allow cross-domain cookies
    https_only=True  # Use HTTPS cookies
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

# ==================== OAuth Configuration ====================

# Canonical URLs - Using the working emergentagent.com domain
OAUTH_CALLBACK_URL = "https://brain-desk-1.preview.emergentagent.com/api/auth/callback"
FRONTEND_URL = "https://brain-desk-1.preview.emergentagent.com"

# In-memory state storage (use Redis in production)
oauth_states = {}

# ==================== Authentication Routes ====================

@api_router.get("/auth/login")
async def login(request: Request):
    """Initiate Google OAuth flow"""
    try:
        # Generate secure random state
        import secrets
        state = secrets.token_urlsafe(32)
        
        logger.info("=" * 80)
        logger.info("OAUTH LOGIN INITIATED")
        logger.info(f"Generated state: {state}")
        logger.info(f"Callback URL: {OAUTH_CALLBACK_URL}")
        logger.info(f"Client ID: {GOOGLE_CLIENT_ID[:20]}...")
        logger.info("=" * 80)
        
        # Store state with timestamp
        oauth_states[state] = {
            'created_at': datetime.utcnow(),
            'redirect_uri': OAUTH_CALLBACK_URL
        }
        
        # Build authorization URL manually WITHOUT Flow/PKCE
        from urllib.parse import urlencode
        
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
        
        logger.info(f"Authorization URL generated successfully (WITHOUT PKCE)")
        logger.info(f"Redirect URI in URL: {OAUTH_CALLBACK_URL}")
        
        return {"authorization_url": authorization_url}
        
    except Exception as e:
        logger.error(f"ERROR in login endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    iss: str = None,
    hd: str = None
):
    """Handle Google OAuth callback"""
    
    logger.info("=" * 80)
    logger.info("OAUTH CALLBACK RECEIVED")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Query params: code={bool(code)}, state={state[:10] if state else None}..., error={error}")
    logger.info(f"Additional params: iss={iss}, hd={hd}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info("=" * 80)
    
    try:
        # Check for Google error
        if error:
            logger.error(f"Google OAuth error: {error}")
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/login?error=google_error&message={error}"
            )
        
        # Validate required parameters
        if not code:
            logger.error("Missing authorization code")
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/login?error=missing_code"
            )
        
        if not state:
            logger.error("Missing state parameter")
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/login?error=missing_state"
            )
        
        logger.info(f"Received code: {code[:20]}...")
        logger.info(f"Received state: {state}")
        
        # Validate state
        if state not in oauth_states:
            logger.error(f"Invalid state received: {state}")
            logger.error(f"Valid states in memory: {list(oauth_states.keys())}")
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/login?error=invalid_state"
            )
        
        stored_state = oauth_states[state]
        logger.info(f"State validation passed")
        logger.info(f"State created at: {stored_state['created_at']}")
        
        # Clean up used state
        del oauth_states[state]
        
        # Verify credentials
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            logger.error("Google OAuth credentials not configured")
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/login?error=config_error"
            )
        
        logger.info(f"Using Client ID: {GOOGLE_CLIENT_ID[:20]}...")
        logger.info(f"Using redirect_uri: {OAUTH_CALLBACK_URL}")
        
        # Exchange code for tokens (manual approach to avoid PKCE)
        import requests
        
        logger.info("Exchanging authorization code for tokens...")
        
        try:
            # Manual token exchange to avoid PKCE
            token_response = requests.post(
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
                logger.error(f"Token exchange failed with status {token_response.status_code}")
                logger.error(f"Response: {token_response.text}")
                return RedirectResponse(
                    url=f"{FRONTEND_URL}/auth/login?error=token_exchange_failed"
                )
            
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            id_token_str = token_data.get("id_token")
            
            logger.info("✅ Token exchange successful")
            logger.info(f"Access token received: {access_token[:20] if access_token else 'None'}...")
            logger.info(f"Refresh token: {'Yes' if refresh_token else 'No'}")
            
        except Exception as token_error:
            logger.error(f"❌ Token exchange failed: {str(token_error)}", exc_info=True)
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/login?error=token_exchange_failed"
            )
        
        # Verify ID token and get user info
        logger.info("Verifying ID token...")
        
        try:
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
            
            logger.info(f"✅ User verified: {email}")
            logger.info(f"Google ID: {google_id}")
            logger.info(f"Name: {name}")
            
        except Exception as verify_error:
            logger.error(f"❌ ID token verification failed: {str(verify_error)}", exc_info=True)
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/login?error=verification_failed"
            )
        
        # Create or update user in database
        logger.info("Checking database for existing user...")
        
        try:
            existing_user = await db.users.find_one({"google_id": google_id})
            
            if existing_user:
                # Update existing user
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
                logger.info(f"✅ Updated existing user: {user_id}")
            else:
                # Create new user
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
                logger.info(f"✅ Created new user: {user_id}")
        
        except Exception as db_error:
            logger.error(f"❌ Database error: {str(db_error)}", exc_info=True)
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/login?error=database_error"
            )
        
        # Create session
        logger.info("Creating session...")
        
        try:
            request.session['user_id'] = user_id
            request.session['email'] = email
            logger.info(f"✅ Session created successfully")
            logger.info(f"Session data: user_id={user_id}, email={email}")
            
        except Exception as session_error:
            logger.error(f"❌ Session creation failed: {str(session_error)}", exc_info=True)
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/login?error=session_error"
            )
        
        # Success! Redirect to frontend with user_id as query param
        # Frontend will capture this and call /api/auth/me with credentials
        logger.info(f"✅ OAuth flow completed successfully")
        logger.info(f"Redirecting to: {FRONTEND_URL}?user_id={user_id}")
        logger.info("=" * 80)
        
        # Redirect with user_id so frontend can fetch user data
        return RedirectResponse(url=f"{FRONTEND_URL}?auth_success=true&user_id={user_id}")
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ UNEXPECTED ERROR in callback: {str(e)}")
        logger.error("=" * 80, exc_info=True)
        return RedirectResponse(
            url=f"{FRONTEND_URL}/auth/login?error=unexpected_error&message={str(e)}"
        )
        
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

@api_router.get("/auth/user/{user_id}")
async def get_user_by_id(user_id: str):
    """Get user by ID (for post-OAuth frontend auth)"""
    try:
        user = await db.users.find_one({"id": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return User(**user)
    except Exception as e:
        logger.error(f"Error fetching user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
    """Sync courses, assignments, AND materials from Google Classroom"""
    try:
        creds = get_google_credentials(user)
        classroom_service = build('classroom', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
        
        logger.info(f"Starting Classroom sync for user: {user.email}")
        
        # Fetch courses
        results = classroom_service.courses().list(pageSize=100).execute()
        courses = results.get('courses', [])
        
        synced_courses = []
        synced_assignments = []
        synced_notes = 0
        
        for course in courses:
            course_id = course['id']
            course_name = course.get('name', 'Untitled Course')
            
            logger.info(f"Processing course: {course_name}")
            
            course_data = Course(
                user_id=user.id,
                classroom_id=course_id,
                name=course_name,
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
                db_course_id = existing_course['id']
            else:
                await db.courses.insert_one(course_data.dict())
                db_course_id = course_data.id
            
            synced_courses.append(course_data)
            
            # Fetch coursework (assignments) with materials
            try:
                coursework_results = classroom_service.courses().courseWork().list(
                    courseId=course_id
                ).execute()
                coursework_items = coursework_results.get('courseWork', [])
                
                logger.info(f"Found {len(coursework_items)} coursework items in {course_name}")
                
                for item in coursework_items:
                    # Save assignment
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
                        course_id=db_course_id,
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
                    
                    # Process materials/attachments
                    materials = item.get('materials', [])
                    
                    for material in materials:
                        # Check for Drive files
                        if 'driveFile' in material:
                            drive_file = material['driveFile']['driveFile']
                            file_id = drive_file['id']
                            file_title = drive_file.get('title', 'Untitled File')
                            
                            logger.info(f"Processing Drive file: {file_title}")
                            
                            # Download and process PDF
                            if file_title.lower().endswith('.pdf'):
                                try:
                                    # Download PDF content
                                    request = drive_service.files().get_media(fileId=file_id)
                                    file_content = io.BytesIO()
                                    downloader = MediaIoBaseDownload(file_content, request)
                                    
                                    done = False
                                    while not done:
                                        status, done = downloader.next_chunk()
                                    
                                    file_content.seek(0)
                                    
                                    # Extract text from PDF
                                    pdf_text = await extract_text_from_pdf(file_content.read())
                                    
                                    if pdf_text:
                                        # Save as note
                                        note = Note(
                                            user_id=user.id,
                                            course_id=db_course_id,
                                            title=file_title,
                                            content=pdf_text[:10000],  # Limit size
                                            attachments=[{
                                                'type': 'drive_file',
                                                'file_id': file_id,
                                                'title': file_title
                                            }]
                                        )
                                        
                                        # Check if note already exists
                                        existing_note = await db.notes.find_one({
                                            "user_id": user.id,
                                            "course_id": db_course_id,
                                            "title": file_title
                                        })
                                        
                                        if not existing_note:
                                            await db.notes.insert_one(note.dict())
                                            synced_notes += 1
                                            logger.info(f"✅ Saved PDF note: {file_title} ({len(pdf_text)} chars)")
                                
                                except Exception as pdf_error:
                                    logger.error(f"Error processing PDF {file_title}: {str(pdf_error)}")
                        
                        # Check for links
                        elif 'link' in material:
                            link_url = material['link'].get('url', '')
                            link_title = material['link'].get('title', 'Link')
                            
                            # Save link as note
                            note = Note(
                                user_id=user.id,
                                course_id=db_course_id,
                                title=link_title,
                                content=f"Link: {link_url}",
                                attachments=[{
                                    'type': 'link',
                                    'url': link_url,
                                    'title': link_title
                                }]
                            )
                            
                            existing_note = await db.notes.find_one({
                                "user_id": user.id,
                                "course_id": db_course_id,
                                "title": link_title
                            })
                            
                            if not existing_note:
                                await db.notes.insert_one(note.dict())
                                synced_notes += 1
            
            except HttpError as e:
                logger.warning(f"Could not fetch coursework for {course_id}: {str(e)}")
            
            # Fetch course materials
            try:
                materials_results = classroom_service.courses().courseWorkMaterials().list(
                    courseId=course_id
                ).execute()
                materials_items = materials_results.get('courseWorkMaterial', [])
                
                logger.info(f"Found {len(materials_items)} course materials in {course_name}")
                
                for material_item in materials_items:
                    materials = material_item.get('materials', [])
                    
                    for material in materials:
                        if 'driveFile' in material:
                            drive_file = material['driveFile']['driveFile']
                            file_id = drive_file['id']
                            file_title = drive_file.get('title', 'Untitled File')
                            
                            # Download PDF
                            if file_title.lower().endswith('.pdf'):
                                try:
                                    request = drive_service.files().get_media(fileId=file_id)
                                    file_content = io.BytesIO()
                                    downloader = MediaIoBaseDownload(file_content, request)
                                    
                                    done = False
                                    while not done:
                                        status, done = downloader.next_chunk()
                                    
                                    file_content.seek(0)
                                    pdf_text = await extract_text_from_pdf(file_content.read())
                                    
                                    if pdf_text:
                                        note = Note(
                                            user_id=user.id,
                                            course_id=db_course_id,
                                            title=file_title,
                                            content=pdf_text[:10000],
                                            attachments=[{
                                                'type': 'drive_file',
                                                'file_id': file_id,
                                                'title': file_title
                                            }]
                                        )
                                        
                                        existing_note = await db.notes.find_one({
                                            "user_id": user.id,
                                            "course_id": db_course_id,
                                            "title": file_title
                                        })
                                        
                                        if not existing_note:
                                            await db.notes.insert_one(note.dict())
                                            synced_notes += 1
                                            logger.info(f"✅ Saved material: {file_title}")
                                
                                except Exception as e:
                                    logger.error(f"Error processing material {file_title}: {str(e)}")
            
            except HttpError as e:
                logger.warning(f"Could not fetch materials for {course_id}: {str(e)}")
        
        logger.info(f"Sync complete: {len(synced_courses)} courses, {len(synced_assignments)} assignments, {synced_notes} notes")
        
        return {
            "message": "Sync completed",
            "courses_synced": len(synced_courses),
            "assignments_synced": len(synced_assignments),
            "notes_synced": synced_notes
        }
    
    except Exception as e:
        logger.error(f"Error syncing classroom: {str(e)}", exc_info=True)
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
    """Chat with AI tutor using retrieved notes"""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        logger.info(f"Chat request from {user.email}: {request.message[:50]}...")
        
        # Get relevant notes for context
        query = {"user_id": user.id}
        if request.course_id:
            query["course_id"] = request.course_id
            logger.info(f"Filtering notes by course: {request.course_id}")
        
        notes = await db.notes.find(query).to_list(100)
        
        logger.info(f"Retrieved {len(notes)} notes for context")
        
        # Build context from notes with better formatting
        if notes:
            context = "=== STUDENT'S COURSE MATERIALS ===\n\n"
            for note in notes:
                context += f"📄 {note['title']}\n"
                context += f"{note['content'][:2000]}\n"  # Limit each note
                context += "\n" + "="*50 + "\n\n"
            
            context += "\n=== END OF MATERIALS ===\n"
        else:
            context = "No course materials have been synced yet. Please sync your Google Classroom first.\n"
        
        # Create chat with context
        system_message = f"""You are a helpful AI tutor assistant for a student.

IMPORTANT: The student has shared their course materials with you below. When answering questions:
1. ALWAYS search through the provided materials first
2. If the answer is in the materials, cite which document it came from
3. If the answer is NOT in the materials, clearly state that and provide general educational guidance
4. Be specific and reference the actual content from their notes

{context}

Now help the student with their question."""
        
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
        
        logger.info(f"Chat response generated ({len(response)} chars)")
        
        return {
            "session_id": session_id,
            "response": response,
            "notes_used": len(notes)
        }
    
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}", exc_info=True)
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

@api_router.get("/sync/stats")
async def get_sync_stats(user: User = Depends(get_current_user)):
    """Get statistics about synced data"""
    try:
        # Get all courses
        courses = await db.courses.find({"user_id": user.id}).to_list(100)
        
        stats = {
            "total_courses": len(courses),
            "total_notes": 0,
            "total_assignments": 0,
            "courses_detail": []
        }
        
        for course in courses:
            notes_count = await db.notes.count_documents({
                "user_id": user.id,
                "course_id": course['id']
            })
            
            assignments_count = await db.assignments.count_documents({
                "user_id": user.id,
                "course_id": course['id']
            })
            
            # Get sample notes
            sample_notes = await db.notes.find({
                "user_id": user.id,
                "course_id": course['id']
            }).limit(3).to_list(3)
            
            stats["total_notes"] += notes_count
            stats["total_assignments"] += assignments_count
            
            stats["courses_detail"].append({
                "name": course['name'],
                "notes_count": notes_count,
                "assignments_count": assignments_count,
                "sample_notes": [
                    {
                        "title": note['title'],
                        "content_preview": note['content'][:200] + "..."
                    }
                    for note in sample_notes
                ]
            })
        
        return stats
    
    except Exception as e:
        logger.error(f"Error getting sync stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
