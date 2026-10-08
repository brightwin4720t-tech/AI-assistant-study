# Aura AI Assistant

A premium Single Page Application (SPA) built with FastAPI, Supabase, and Gemini AI. 

## Features
- **Integrated Frontend**: HTML, CSS, and JS all combined into a single, clean `index.html` file.
- **Premium UI/UX**: Dark mode, glassmorphism design, and responsive layout.
- **Secure Authentication**: User registration, login, and secure password hashing handled seamlessly by Supabase Auth.
- **AI Integration**: Powered by Google's Gemini Pro API.

## Tech Stack
- **Frontend**: Vanilla HTML5, CSS3, and JS (all inside `templates/index.html`).
- **Backend**: Python 3, FastAPI.
- **Database/Auth**: Supabase.

## How to Run

1. **Activate the Virtual Environment**
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. **Install Dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Set up Environment Variables**
   Rename `.env.example` to `.env` and configure your credentials. 
   *(Note: The app has a "mock" mode. If you don't provide real Supabase/Gemini keys, it will still run and demonstrate the UI/mock logins!)*
   ```
   SUPABASE_URL=your_supabase_project_url
   SUPABASE_KEY=your_supabase_anon_key
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

4. **Run the Application**
   ```powershell
   python app.py
   ```

5. **Access the Application**
   Open your browser and navigate to `http://127.0.0.1:8000/`.
