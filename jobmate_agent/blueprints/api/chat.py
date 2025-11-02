from flask import request, Response, stream_with_context, jsonify, g
import os
import logging
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from datetime import datetime

from . import api_bp
from jobmate_agent.extensions import db, bcrypt
from jobmate_agent.models import User, Chat, ChatMessage
from jobmate_agent.jwt_auth import require_jwt

# Configure OpenAI (DeepSeek)
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)


def _build_messages_for_api(chat_id: int) -> list[dict]:
    """Build messages for LLM API, including ALL system messages with context."""
    chat_msgs = (
        ChatMessage.query.filter_by(chat_id=chat_id)
        .order_by(ChatMessage.timestamp)
        .all()
    )
    messages_for_api: list[dict] = []
    
    # Include ALL messages, especially system messages with context
    for msg in chat_msgs:
        content = msg.content or ""
        messages_for_api.append({"role": msg.role, "content": content})
    
    return messages_for_api


def _ensure_user_from_profile() -> User | None:
    prof = getattr(g, "user_profile", None)
    if prof is None:
        return None
    # Try to match existing User by email; fallback to creating a placeholder
    email = getattr(prof, "email", None)
    name = getattr(prof, "name", None)
    user: User | None = None
    if email:
        user = User.query.filter_by(email=email).first()
    if user is None:
        username = (name or (email.split("@")[0] if email else f"user-{prof.id}"))
        # create a placeholder password
        pw = bcrypt.generate_password_hash(os.urandom(8)).decode("utf-8")
        user = User(username=username, email=email or f"auth0:{prof.id}", password_hash=pw)
        db.session.add(user)
        db.session.commit()
    return user


@api_bp.route("/chat/stream", methods=["POST"])
@require_jwt(hydrate=True)
def chat_stream():
    """Stream chat responses from LLM with full context from system messages."""
    try:
        data = request.get_json(silent=True) or {}
        message = str(data.get("message") or "").strip()
        chat_id = data.get("chat_id")
        if not message:
            return jsonify({"error": "message_required"}), 400

        user_profile_id = getattr(g, "user_sub", None)
        if not user_profile_id:
            return jsonify({"error": "unauthorized"}), 401

        # Get the chat and verify ownership
        chat = Chat.query.get(chat_id)
        if not chat:
            return jsonify({"error": "chat_not_found"}), 404
        if chat.user_id and chat.user_id != user_profile_id:
            return jsonify({"error": "chat_not_owned"}), 403

        # Save user message
        user_msg = ChatMessage(role="user", content=message, chat_id=chat_id)
        db.session.add(user_msg)
        db.session.commit()

        # Build messages for API (includes system messages with context)
        messages = _build_messages_for_api(chat_id)
        print(f"[CHAT_STREAM] Sending {len(messages)} messages to LLM (chat_id={chat_id})")
        
        # Get model from chat settings
        model = chat.model or "deepseek-chat"
        print(f"[CHAT_STREAM] Using model: {model}")

        # Determine API endpoint based on model
        if model.startswith("gpt-"):
            # OpenAI models
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY_BETA")
            base_url = "https://api.openai.com/v1"
        else:
            # DeepSeek models (default)
            api_key = os.getenv("DEEPSEEK_API_KEY")
            base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

        if not api_key:
            print(f"[CHAT_STREAM] ERROR: No API key found for model {model}")
            return jsonify({"error": "api_key_missing"}), 500

        # Stream response from LLM
        def generate():
            try:
                from openai import OpenAI
                client_instance = OpenAI(api_key=api_key, base_url=base_url)
                
                stream = client_instance.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    temperature=0.7,
                )
                
                full_response = ""
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield f"data: {content}\n\n"
                
                # Save assistant response to database
                assistant_msg = ChatMessage(
                    role="assistant",
                    content=full_response,
                    chat_id=chat_id
                )
                db.session.add(assistant_msg)
                db.session.commit()
                print(f"[CHAT_STREAM] Saved assistant response ({len(full_response)} chars)")
                
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                print(f"[CHAT_STREAM] ERROR during streaming: {e}")
                import traceback
                traceback.print_exc()
                yield f"data: Error: {str(e)}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )

    except Exception as e:
        print(f"[CHAT_STREAM] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "unexpected_error", "detail": str(e)}), 500


@api_bp.route("/chats", methods=["GET"])
@require_jwt(hydrate=True)
def list_chats():
    try:
        # Get user profile ID (Auth0 string ID) directly from g
        user_profile_id = getattr(g, "user_sub", None)
        print(f"[LIST_CHATS] user_profile_id from g.user_sub: {user_profile_id}")
        
        if not user_profile_id:
            print("[LIST_CHATS] ERROR: No user_profile_id found")
            return jsonify({"error": "unauthorized"}), 401
        
        print(f"[LIST_CHATS] Querying chats for user_id: {user_profile_id}")
        chats = (
            Chat.query.filter_by(user_id=user_profile_id).order_by(Chat.timestamp.desc()).all()
        )
        print(f"[LIST_CHATS] Found {len(chats)} chats")
        print(f"[LIST_CHATS] Found {len(chats)} chats")
        items = [
            {
                "id": c.id,
                "title": c.title or "New Chat",
                "timestamp": c.timestamp.isoformat() if c.timestamp else None,
                "model": c.model or "deepseek-chat",
            }
            for c in chats
        ]
        print(f"[LIST_CHATS] Returning {len(items)} chat items")
        return jsonify({"chats": items})
    except Exception as e:
        print(f"[LIST_CHATS] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "unexpected_error", "detail": str(e)}), 500


@api_bp.route("/chat/create", methods=["POST"])
@require_jwt(hydrate=True)
def create_chat():
    try:
        data = request.get_json(silent=True) or {}
        selected_model = str(data.get("model") or "deepseek-chat")
        job_id = data.get("job_id")
        try:
            job_id = int(job_id) if job_id is not None else None
        except Exception:
            job_id = None

        allowed_models = [
            "deepseek-chat",
            "deepseek-reasoner",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-3.5-turbo",
        ]
        if selected_model not in allowed_models:
            selected_model = "deepseek-chat"

        # Get user profile ID (Auth0 string ID) directly from g
        user_profile_id = getattr(g, "user_sub", None)
        profile = getattr(g, "user_profile", None)
        
        if not user_profile_id or not profile:
            return jsonify({"error": "unauthorized"}), 401

        new_chat = Chat(title="New Chat", user_id=user_profile_id, model=selected_model, timestamp=datetime.utcnow())
        db.session.add(new_chat)
        db.session.commit()

        # Build context info to return to client
        context_info = {
            "has_context": False,
            "user": None,
            "job": None,
            "gap": None,
            "snippets_count": 0,
            "snippets": [],
            "message": None,
        }

        # If job_id provided, attempt to ensure and seed preloaded context
        if job_id:
            try:
                from jobmate_agent.models import PreloadedContext, JobListing
                from jobmate_agent.services.context_builder import ensure_preloaded_contexts

                if profile:
                    context_info["user"] = {
                        "id": profile.id,
                        "name": getattr(profile, "name", None),
                        "email": getattr(profile, "email", None),
                    }

                # populate job summary if available
                try:
                    jl = JobListing.query.get(job_id)
                    if jl:
                        context_info["job"] = {"id": jl.id, "title": jl.title, "company": jl.company, "description": jl.description}
                except Exception:
                    pass

                # Ensure preloaded contexts exist — build on-demand if missing
                ensure_preloaded_contexts(user_profile_id, job_id)
                snippets = (
                    PreloadedContext.query.filter_by(user_id=user_profile_id, job_listing_id=job_id)
                    .order_by(PreloadedContext.created_at)
                    .all()
                )

                if snippets:
                    context_info["has_context"] = True
                    context_info["snippets_count"] = len(snippets)
                    context_info["snippets"] = [{"doc_type": s.doc_type, "content": (s.content or '')[:2000]} for s in snippets]
                    for s in snippets:
                        sys_msg = ChatMessage(role="system", content=s.content or "", chat_id=new_chat.id)
                        db.session.add(sys_msg)
                else:
                    context_info["has_context"] = False

                # Gap snippet and assistant message
                gap_snip = (
                    PreloadedContext.query.filter_by(user_id=user_profile_id, job_listing_id=job_id, doc_type="gap").first()
                )
                if gap_snip and gap_snip.content and "No gap report" not in gap_snip.content:
                    assistant_text = (
                        f"I found a skill gap report for this job. Summary: {gap_snip.content}\n\n"
                        "If you'd like, I can walk through the top missing skills and suggest learning steps or help tailor your application."
                    )
                    context_info["gap"] = {"content": (gap_snip.content or '')[:2000]}
                else:
                    assistant_text = (
                        "I couldn't find an existing skill gap report for this job. "
                        "Press the 'Analyse' button in the job details to generate one — I can then provide tailored recommendations and an action plan."
                    )
                    context_info["message"] = "No gap analysis available. Press Analyse to generate one."

                assistant_msg = ChatMessage(role="assistant", content=assistant_text, chat_id=new_chat.id)
                db.session.add(assistant_msg)
                db.session.commit()
            except Exception:
                db.session.rollback()
                # non-fatal; proceed without preloaded content
                app_logger = logging.getLogger(__name__)
                app_logger.exception("Failed to seed preloaded context into chat")

        return jsonify({"chat": {"id": new_chat.id, "title": new_chat.title, "timestamp": new_chat.timestamp.isoformat() if new_chat.timestamp else None, "model": new_chat.model}, "context": context_info}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "unexpected_error", "detail": str(e)}), 500


@api_bp.route("/chat/<int:chat_id>", methods=["DELETE"])
@require_jwt(hydrate=True)
def delete_chat(chat_id: int):
    try:
        user_profile_id = getattr(g, "user_sub", None)
        if not user_profile_id:
            return jsonify({"error": "unauthorized"}), 401
        
        chat = Chat.query.get(chat_id)
        if not chat:
            return jsonify({"error": "chat_not_found"}), 404
        if chat.user_id and chat.user_id != user_profile_id:
            return jsonify({"error": "chat_not_owned"}), 403
        # delete messages then chat
        ChatMessage.query.filter_by(chat_id=chat.id).delete()
        db.session.delete(chat)
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "unexpected_error", "detail": str(e)}), 500


@api_bp.route("/chat/<int:chat_id>/messages", methods=["GET"])
@require_jwt(hydrate=True)
def get_chat_messages(chat_id: int):
    try:
        user_profile_id = getattr(g, "user_sub", None)
        if not user_profile_id:
            return jsonify({"error": "unauthorized"}), 401
        
        chat = Chat.query.get(chat_id)
        if not chat:
            return jsonify({"error": "chat_not_found"}), 404
        if chat.user_id and chat.user_id != user_profile_id:
            return jsonify({"error": "chat_not_owned"}), 403
        msgs = (
            ChatMessage.query.filter_by(chat_id=chat.id).order_by(ChatMessage.timestamp).all()
        )
        items = [{"id": m.id, "role": m.role, "content": m.content or ""} for m in msgs]
        return jsonify({"messages": items, "chat": {
            "id": chat.id,
            "title": chat.title,
            "timestamp": chat.timestamp.isoformat() if chat.timestamp else None,
            "model": chat.model,
        }})
    except Exception as e:
        return jsonify({"error": "unexpected_error", "detail": str(e)}), 500
@api_bp.route("/preload-context", methods=["POST"])
@require_jwt(hydrate=True)
def preload_context():
    """Trigger background preload of user+job context (stores DB snippets and tries Chroma upsert).

    Request JSON: { "job_id": number }
    Response: { ok: true }
    """
    try:
        data = request.get_json(silent=True) or {}
        job_id = data.get("job_id")
        user_id = g.user_sub
        if not user_id:
            return jsonify({"error": "unauthorized"}), 401

        # Run async preloader
        from jobmate_agent.services.preloader import preload_context_async

        preload_context_async(user_id, job_id)
        return jsonify({"ok": True}), 202
    except Exception as e:
        return jsonify({"error": "failed_to_start_preload", "detail": str(e)}), 500


@api_bp.route("/preload-status", methods=["GET"])
@require_jwt(hydrate=True)
def preload_status():
    """Return whether preloaded snippets exist for user+job. Query params: job_id"""
    try:
        job_id = request.args.get("job_id")
        try:
            job_id = int(job_id) if job_id is not None else None
        except Exception:
            job_id = None
        user_id = g.user_sub
        if not user_id:
            return jsonify({"error": "unauthorized"}), 401

        from jobmate_agent.models import PreloadedContext

        snippets = PreloadedContext.query.filter_by(user_id=user_id, job_listing_id=job_id).all()
        exists = len(snippets) > 0
        return jsonify({"exists": exists, "count": len(snippets)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500