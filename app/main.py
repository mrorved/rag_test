from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import json
import datetime
from app.config import settings
from app.rag_engine import rag_engine

app = FastAPI(
    title="CVGaudio AI Assistant API",
    description="RAG-консультант по звуковому оборудованию CVGaudio для cvg-rus.ru",
    version="1.0.0"
)

# Разрешаем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Модели данных ---

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str = Field(..., description="Текст вопроса пользователя")
    history: Optional[List[ChatMessage]] = Field(default=[], description="История предыдущих сообщений")
    session_id: Optional[str] = Field(default=None, description="ID сессии пользователя")

class ChatResponse(BaseModel):
    response: str
    sources: List[Dict[str, str]]
    tokens: Dict[str, int] = Field(default_factory=lambda: {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0})
    session_id: str

class LeadRequest(BaseModel):
    name: str = Field(..., description="Имя контактного лица")
    phone: str = Field(..., description="Телефон")
    email: Optional[str] = Field(default="", description="Email")
    comment: Optional[str] = Field(default="", description="Комментарий или ТЗ")
    chat_history: Optional[List[Dict[str, Any]]] = Field(default=[], description="История диалога с ассистентом")

class LoginRequest(BaseModel):
    username: str
    password: str

# --- Авторизация ---

def check_auth(request: Request):
    """Проверка прав доступа к API (cookie, Bearer token или заголовок X-Auth-Token)"""
    if not settings.AUTH_ENABLED:
        return True
    
    # 1. Проверка Cookie
    token = request.cookies.get("cvg_auth_token")
    if token == settings.AUTH_SECRET_TOKEN:
        return True
        
    # 2. Проверка заголовка Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == settings.AUTH_SECRET_TOKEN:
            return True
            
    # 3. Проверка заголовка X-Auth-Token
    if request.headers.get("X-Auth-Token") == settings.AUTH_SECRET_TOKEN:
        return True
        
    raise HTTPException(status_code=401, detail="Требуется авторизация для использования AI-консультанта")

# --- Эндпоинты аутентификации ---

@app.post("/api/auth/login")
def login(creds: LoginRequest, response: Response):
    if creds.username == settings.AUTH_USERNAME and creds.password == settings.AUTH_PASSWORD:
        response.set_cookie(
            key="cvg_auth_token",
            value=settings.AUTH_SECRET_TOKEN,
            httponly=False,
            max_age=60 * 60 * 24 * 7, # 7 дней
            samesite="lax"
        )
        return {
            "status": "success",
            "token": settings.AUTH_SECRET_TOKEN,
            "username": creds.username
        }
    raise HTTPException(status_code=401, detail="Неверный логин или пароль")

@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("cvg_auth_token")
    return {"status": "success", "message": "Вы вышли из системы"}

@app.get("/api/auth/status")
def auth_status(request: Request):
    if not settings.AUTH_ENABLED:
        return {"authenticated": True, "auth_enabled": False}
    token = request.cookies.get("cvg_auth_token") or request.headers.get("X-Auth-Token")
    if token == settings.AUTH_SECRET_TOKEN:
        return {"authenticated": True, "auth_enabled": True, "username": settings.AUTH_USERNAME}
    return {"authenticated": False, "auth_enabled": True}

# --- Основные эндпоинты ---

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "provider": settings.resolved_provider,
        "model": settings.active_model,
        "auth_enabled": settings.AUTH_ENABLED,
        "has_api_key": bool(settings.active_api_key and "your_" not in settings.active_api_key),
        "knowledge_items_count": len(rag_engine.knowledge_base)
    }

SESSIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sessions.json")

def load_sessions() -> List[Dict[str, Any]]:
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_session_turn(session_id: str, user_msg: str, bot_reply: str, sources: List[Dict[str, str]], tokens: Dict[str, int]):
    os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
    sessions = load_sessions()
    now_iso = datetime.datetime.now().isoformat()
    
    session = None
    for s in sessions:
        if s.get("session_id") == session_id:
            session = s
            break
            
    if not session:
        session = {
            "session_id": session_id,
            "created_at": now_iso,
            "updated_at": now_iso,
            "total_tokens": 0,
            "messages_count": 0,
            "messages": []
        }
        sessions.append(session)
        
    session["updated_at"] = now_iso
    session["total_tokens"] = session.get("total_tokens", 0) + tokens.get("total_tokens", 0)
    
    session["messages"].append({
        "role": "user",
        "content": user_msg,
        "timestamp": now_iso
    })
    session["messages"].append({
        "role": "assistant",
        "content": bot_reply,
        "timestamp": now_iso,
        "tokens": tokens,
        "sources": sources
    })
    session["messages_count"] = len(session["messages"])
    
    if len(sessions) > 500:
        sessions = sessions[-500:]
        
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Error saving sessions]: {e}")

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest, authenticated: bool = Depends(check_auth)):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")

    session_id = request.session_id or f"sess_{int(datetime.datetime.now().timestamp())}_{os.urandom(3).hex()}"
    history_dicts = [{"role": m.role, "content": m.content} for m in request.history]
    reply, sources, tokens = rag_engine.generate_response(request.message, history=history_dicts)
    save_session_turn(session_id, request.message, reply, sources, tokens)
    return ChatResponse(response=reply, sources=sources, tokens=tokens, session_id=session_id)

@app.get("/api/sessions")
def get_sessions(authenticated: bool = Depends(check_auth)):
    """Просмотр всех сессий и диалогов пользователей с расходом токенов"""
    sessions = load_sessions()
    sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return sessions

@app.delete("/api/sessions")
def clear_sessions(authenticated: bool = Depends(check_auth)):
    """Очистка сессий (для администратора)"""
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
        except Exception:
            pass
    return {"status": "success", "message": "История сессий очищена"}

@app.post("/api/lead")
def lead_endpoint(lead: LeadRequest, authenticated: bool = Depends(check_auth)):
    leads_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "leads.json")
    os.makedirs(os.path.dirname(leads_file), exist_ok=True)
    
    leads = []
    if os.path.exists(leads_file):
        try:
            with open(leads_file, "r", encoding="utf-8") as f:
                leads = json.load(f)
        except Exception:
            leads = []

    lead_entry = {
        "created_at": datetime.datetime.now().isoformat(),
        "name": lead.name,
        "phone": lead.phone,
        "email": lead.email,
        "comment": lead.comment,
        "chat_history": lead.chat_history
    }
    leads.append(lead_entry)

    with open(leads_file, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)

    print(f"[Lead] Получена новая заявка от {lead.name} ({lead.phone})")
    return {"status": "success", "message": "Заявка успешно принята"}

@app.get("/api/leads")
def get_leads(authenticated: bool = Depends(check_auth)):
    """Просмотр поступивших заявок инженеру"""
    leads_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "leads.json")
    if os.path.exists(leads_file):
        try:
            with open(leads_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

# Статические файлы для виджета и демонстрационной страницы
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def index():
    return RedirectResponse(url="/static/demo.html")
