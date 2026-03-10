# 🧠 Brain Desk - AI-Powered Study Companion

A cross-platform mobile app for students to manage notes, assignments, and studying with AI assistance.

## ✨ Features

### 📚 Google Classroom Integration
- Automatic sync of courses and assignments
- Real-time assignment tracking with due dates
- Course organization with notes

### 🤖 AI Tutor
- Chat with GPT-4 powered AI assistant
- Ask questions about your notes
- Get explanations in simple terms
- Generate quizzes and MCQs
- Summarize chapters and concepts

### 📝 Note Management
- Create and organize notes by course
- Attach files and PDFs
- Search through your notes
- AI-powered note summaries

### ✅ Assignment Tracking
- View all assignments from Google Classroom
- Filter by status (Pending/Completed)
- Color-coded due date indicators
- Mark assignments as complete

### 📊 Dashboard
- Overview of today's tasks
- Upcoming assignments
- Recent notes
- Quick actions

## 🚀 Tech Stack

**Frontend:**
- Expo (React Native)
- TypeScript
- Expo Router (file-based routing)
- Zustand (state management)
- Axios (HTTP client)
- React Native components

**Backend:**
- FastAPI (Python)
- MongoDB (database)
- Google OAuth 2.0
- Google Classroom API
- Google Drive API
- Google Calendar API
- OpenAI GPT-4 (via Emergent LLM Key)

## 🔧 Setup Instructions

### 1. Google Cloud Setup

**Already Completed:**
- Google OAuth Client ID: `954627207327-6dplmlbf9kq25p8sm4mkobgptd3bsmag.apps.googleusercontent.com`
- Google Client Secret: `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`

**Important:** Make sure these URLs are added to your Google Cloud Console OAuth credentials:

**Authorized JavaScript Origins:**
```
https://brain-desk-1.preview.emergentagent.com
```

**Authorized Redirect URIs:**
```
https://brain-desk-1.preview.emergentagent.com/api/auth/callback
```

### 2. Running the App

The app is already running at:
- **Web Preview:** https://brain-desk-1.preview.emergentagent.com
- **Backend API:** https://brain-desk-1.preview.emergentagent.com/api

## 📱 App Structure

```
/app
├── backend/
│   ├── server.py          # FastAPI backend with all endpoints
│   ├── requirements.txt   # Python dependencies
│   └── .env              # Backend environment variables
│
├── frontend/
│   ├── app/
│   │   ├── (tabs)/       # Main tab navigation
│   │   │   ├── home.tsx          # Dashboard
│   │   │   ├── courses.tsx       # Courses list
│   │   │   ├── assignments.tsx   # Assignments tracker
│   │   │   ├── tutor.tsx         # AI Tutor chat
│   │   │   └── profile.tsx       # User profile
│   │   │
│   │   ├── auth/
│   │   │   └── login.tsx         # Login screen
│   │   │
│   │   ├── index.tsx              # Entry point
│   │   └── _layout.tsx            # Root layout
│   │
│   ├── src/
│   │   ├── components/    # Reusable components
│   │   ├── store/         # Zustand state management
│   │   ├── types/         # TypeScript types
│   │   └── utils/         # Utilities & API client
│   │
│   └── package.json
```

## 🎨 Design Theme

**Colors:**
- Primary: Deep Indigo/Purple gradient (#6C5CE7)
- Secondary: Teal/Electric Blue (#00CEC9)
- Background: Soft off-white (#F8F9FA)
- Text: Dark gray/black for readability

**UI Features:**
- Smooth animations and transitions
- Gradient cards
- Rounded corners with shadows
- Micro-interactions on button taps
- Modern, student-friendly design

## 📝 Usage

1. **Login:** Click "Continue with Google" to authenticate
2. **Sync:** Use the sync button to fetch your Google Classroom data
3. **Dashboard:** View today's assignments and recent notes
4. **Courses:** Browse your courses and their assignments
5. **Assignments:** Track and manage your assignments
6. **AI Tutor:** Chat with the AI to study and understand concepts
7. **Profile:** Manage your account and settings

## 🎓 For Students

Brain Desk helps you:
- 📖 Organize all your study materials in one place
- 🎯 Never miss an assignment deadline
- 🤖 Get instant help from AI tutor
- 📝 Create and manage notes efficiently
- 📊 Track your academic progress
- ⚡ Study smarter, not harder

---

Built with ❤️ for students
