import os
# NOTE: google.generativeai is deprecated; using google.genai instead
import sqlite3
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from supabase import create_client, Client
from google import genai as genai_client
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
import bcrypt
import uuid

load_dotenv()

app = FastAPI()

# Password Hashing Helpers (enforcing bcrypt's 72-byte limit)
def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed_password: str) -> bool:
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configure Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
IS_SUPABASE = bool(SUPABASE_URL and "supabase.co" in SUPABASE_URL and SUPABASE_KEY)
supabase: Client = None
if IS_SUPABASE:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")
        IS_SUPABASE = False

# Configure Gemini AI
# google.genai client is configured per-call via the Client object

# --- Database Fallback Setup ---
# If Supabase credentials are not set, we fall back to local SQLite so you can test immediately.
# On Vercel, the root filesystem is read-only, so write to /tmp
DATABASE = '/tmp/database.db' if os.environ.get("VERCEL") else os.path.join(BASE_DIR, 'database.db')

def init_db():
    if IS_SUPABASE:
        return
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
            ''')
            # --- Data Collection Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_email TEXT NOT NULL,
                    message   TEXT NOT NULL,
                    reply     TEXT NOT NULL,
                    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
                )
            ''')
            conn.commit()
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")

init_db()

# --- Database Helper Functions ---
def get_db_user(email):
    if IS_SUPABASE:
        res = supabase.table("users").select("*").eq("email", email).execute()
        return res.data[0] if res.data else None
    else:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "email": row[1], "password_hash": row[2]}
            return None

def create_db_user(email, hashed_pw):
    if IS_SUPABASE:
        supabase.table("users").insert({"email": email, "password_hash": hashed_pw}).execute()
    else:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, hashed_pw))
            conn.commit()

def get_all_users():
    if IS_SUPABASE:
        res = supabase.table("users").select("*").execute()
        return res.data
    else:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, password_hash FROM users")
            return [{"id": row[0], "email": row[1], "password_hash": row[2]} for row in cursor.fetchall()]

def save_chat_message(user_email: str, message: str, reply: str):
    """Persist a chat exchange to the chat_messages table."""
    if IS_SUPABASE:
        supabase.table("chat_messages").insert({
            "user_email": user_email,
            "message": message,
            "reply": reply
        }).execute()
    else:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_messages (user_email, message, reply) VALUES (?, ?, ?)",
                (user_email, message, reply)
            )
            conn.commit()

# --- API Endpoints ---
class AuthModel(BaseModel):
    email: str
    password: str

class ChatModel(BaseModel):
    message: str
    area: Optional[str] = "General Programming"

STUDY_SYSTEM_PROMPT = """You are CodeMentor AI, an expert, patient, and encouraging programming tutor and computer science study assistant.
Your mission is to help students, self-taught programmers, and developers understand programming languages and software engineering deeply.
You specialize in languages including Python, Java, HTML/CSS/JavaScript, C++, SQL, TypeScript, and core concepts such as Data Structures, Algorithms, Object-Oriented Programming (OOP), System Design, and Debugging.

Guidelines for your teaching:
1. Clear & Intuitive Explanations: Break complex ideas down into bite-sized concepts. Use analogies when teaching abstract principles.
2. Clean, Well-Commented Code: Always provide modern, idiomatic code examples using proper markdown language tags (```python, ```java, ```html, ```css, ```javascript, ```sql, ```cpp). Add inline comments explaining non-trivial lines.
3. Multi-Area Knowledge: Adapt your answers to the selected study focus (e.g. Python backend, Web Development, Java OOP, Algorithms, Database SQL, or Code Debugging).
4. Debugging & Error Analysis: When debugging, pinpoint the bug line, explain the root cause, show the corrected snippet, and explain how to avoid it in the future.
5. Interactive Study & Quizzing: Conclude conceptual explanations with 1 or 2 quick challenge questions, quiz prompts, or next-step coding exercises to solidify learning.
6. Friendly & Inspiring Tone: Be concise, structured, supportive, and developer-friendly.
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    template_path = os.path.join(BASE_DIR, "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.post("/api/register")
async def register(data: AuthModel):
    try:
        # Check if user already exists
        if get_db_user(data.email):
            return JSONResponse(content={"error": "Email already registered"}, status_code=400)
            
        # Hash the password manually (auto-truncated to 72 bytes)
        hashed_password = hash_password(data.password)
        
        # Save to database (Supabase or SQLite)
        create_db_user(data.email, hashed_password)
        
        return JSONResponse(content={"message": "Registration successful! Please login."}, status_code=201)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

@app.post("/api/login")
async def login(data: AuthModel):
    try:
        user = get_db_user(data.email)
        
        if not user or not verify_password(data.password, user["password_hash"]):
            return JSONResponse(content={"error": "Invalid email or password"}, status_code=401)
            
        # For a custom auth flow, we'd issue a JWT. 
        # For simplicity in this SPA, we will just use a mock token with the email.
        # In a real production app, use PyJWT to sign a token here.
        mock_token = f"custom_token_{data.email}"
        
        return {
            "message": "Login successful", 
            "access_token": mock_token,
            "user": data.email
        }
    except Exception as e:
        return JSONResponse(content={"error": "Login error occurred"}, status_code=500)

@app.get("/api/admin/users")
async def admin_users():
    """Endpoint to return all users and their hashed passwords to show on the page."""
    try:
        users = get_all_users()
        return {"users": users}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/my-hash")
async def my_hash(authorization: Optional[str] = Header(None)):
    """Return the hashed password of the currently logged-in user."""
    if not authorization or not authorization.startswith("Bearer custom_token_"):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    email = authorization.split("custom_token_")[1]
    user = get_db_user(email)
    if not user:
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    return {"password_hash": user["password_hash"]}

@app.post("/api/chat")
async def chat(data: ChatModel, authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer custom_token_"):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    
    # Extract email from our mock token to verify they are logged in
    email = authorization.split("custom_token_")[1]
    
    if not get_db_user(email):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)

    try:
        if os.environ.get("GEMINI_API_KEY", "dummy_key") == "dummy_key":
            ai_response = "I am a simulated AI programming tutor. Please set GEMINI_API_KEY in your .env file to use the live AI."
        else:
            model = genai_client.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
            
            system_instruction = STUDY_SYSTEM_PROMPT
            if data.area and data.area != "General Programming":
                system_instruction += f"\n\nStudent's Current Focus Area: {data.area}. Tailor your terminology, examples, and recommendations specifically to this domain when relevant."

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7
            )
            response = model.models.generate_content(
                model=gemini_model,
                contents=data.message,
                config=config
            )
            ai_response = response.text

        # --- Data Collection: save every exchange ---
        save_chat_message(email, data.message, ai_response)
            
        return {"reply": ai_response}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
