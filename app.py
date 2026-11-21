"""Gradio UI for the Maple Street Auto front-desk agent (made-up shop, fake data)."""
import os
import uuid

import chromadb
import gradio as gr

from agent import MAX_USER_MESSAGES, build_agent, ask
from ingest import CHROMA_DIR, COLLECTION, ingest

EXAMPLES = [
    "Do you do brake work?",
    "What's open Friday?",
    "Book an oil change for Sam Lee, 555-010-2222, on 2026-11-27 at 08:00",
]

_agent = None


def _ensure_index():
    """The Chroma index isn't in git; build it on first start (e.g. on a fresh Space)."""
    try:
        chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection(COLLECTION)
    except Exception:
        ingest()


def _get_agent():
    global _agent
    if _agent is None:
        _ensure_index()
        _agent = build_agent()
    return _agent


def respond(message: str, history: list, request: gr.Request):
    used = sum(1 for m in history if m["role"] == "user")
    if used >= MAX_USER_MESSAGES:
        return "You've reached the message limit for this chat. Please call the shop at 555-0142."
    thread_id = getattr(request, "session_hash", None) or str(uuid.uuid4())
    try:
        return ask(_get_agent(), message, thread_id)
    except Exception:
        return "Sorry, something went wrong on our end. Please try again or call the shop at 555-0142."


demo = gr.ChatInterface(
    respond,
    title="Maple Street Auto: Front Desk",
    description=(
        "Ask about hours, services, typical prices and warranty, check open times, "
        "or book an appointment. Demo only: Maple Street Auto and its schedule are made up. "
        f"Chats are limited to {MAX_USER_MESSAGES} messages."
    ),
    examples=EXAMPLES,
    cache_examples=False,
)

if __name__ == "__main__":
    port = os.environ.get("PORT")  # set by hosts like Render; unset locally
    if port:
        demo.launch(server_name="0.0.0.0", server_port=int(port))
    else:
        demo.launch()
