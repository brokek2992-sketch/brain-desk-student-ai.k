export interface User {
  id: string;
  google_id: string;
  email: string;
  name: string;
  picture?: string;
  created_at: string;
}

export interface Course {
  id: string;
  user_id: string;
  classroom_id: string;
  name: string;
  section?: string;
  description?: string;
  teacher_name?: string;
  enrollment_code?: string;
  created_at: string;
  notes_count?: number;
  assignments_count?: number;
}

export interface Assignment {
  id: string;
  user_id: string;
  course_id: string;
  classroom_id: string;
  title: string;
  description?: string;
  due_date?: string;
  state: 'PENDING' | 'COMPLETED';
  link?: string;
  created_at: string;
}

export interface Note {
  id: string;
  user_id: string;
  course_id?: string;
  title: string;
  content: string;
  attachments?: any[];
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  user_id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface QuizQuestion {
  question: string;
  options: string[];
  correct_answer: number;
}

export interface Quiz {
  id: string;
  user_id: string;
  course_id?: string;
  title: string;
  questions: QuizQuestion[];
  created_at: string;
}

export interface DashboardData {
  today_assignments: Assignment[];
  upcoming_assignments: Assignment[];
  recent_notes: Note[];
  courses_count: number;
}