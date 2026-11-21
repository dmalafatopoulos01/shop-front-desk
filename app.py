"""Gradio UI for the Maple Street Auto front-desk agent (made-up shop, fake data)."""
import os
import uuid

import chromadb
import gradio as gr

from agent import MAX_USER_MESSAGES, build_agent, ask
from ingest import CHROMA_DIR, COLLECTION, ingest
from ratelimit import client_ip, limiter_from_env, retry_message

EXAMPLES = [
    "Do you do brake work?",
    "What's open Friday?",
    "Book an oil change for Sam Lee, 555-010-2222, on 2026-11-27 at 08:00",
]

_agent = None
limiter = limiter_from_env()  # per-IP: 10/min and 60/hour by default (RATE_LIMIT_PER_MINUTE/HOUR)


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


def _new_thread_id() -> str:
    return uuid.uuid4().hex


def respond(message: str, history: list, thread_id: str):
    used = sum(1 for m in history if m["role"] == "user")
    if used >= MAX_USER_MESSAGES:
        return "You've reached the message limit for this chat. Please call the shop at 555-0142."
    try:
        return ask(_get_agent(), message, thread_id)
    except Exception:
        return "Sorry, something went wrong on our end. Please try again or call the shop at 555-0142."


def chat(message: str, history: list, thread_id: str, request: gr.Request = None):
    """Append one visitor turn to the chat. Returns (textbox value, updated history)."""
    message = (message or "").strip()
    if not message:
        return "", history

    allowed, retry_after = limiter.check(client_ip(request))
    if not allowed:
        # No model call. Only a notice is added (the visitor's message is not, so it doesn't
        # use up their chat cap), and their text stays in the box so they can resend it.
        return message, history + [{"role": "assistant", "content": retry_message(retry_after)}]

    reply = respond(message, history, thread_id)
    return "", history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]


def _example_handler(text: str):
    def handler(history: list, thread_id: str, request: gr.Request = None):
        return chat(text, history, thread_id, request)

    return handler


# Built from Blocks rather than gr.ChatInterface on purpose: ChatInterface always adds
# Retry/Undo buttons, which would replay or rewind a turn while a booking is waiting for
# the visitor's "yes" and desync the agent's saved state. Each chat has its own thread id,
# and the Clear button starts a fresh one so a cleared screen never leaves a hidden
# confirmation pending on the server.
with gr.Blocks(title="Maple Street Auto: Front Desk") as demo:
    gr.Markdown("# Maple Street Auto: Front Desk")
    gr.Markdown(
        "Ask about hours, services, typical prices and warranty, check open times, "
        "or book an appointment. Demo only: Maple Street Auto and its schedule are made up. "
        f"Chats are limited to {MAX_USER_MESSAGES} messages."
    )
    thread = gr.State(_new_thread_id)
    chatbot = gr.Chatbot(height=460, buttons=["copy_all"], show_label=False)
    box = gr.Textbox(placeholder="Type a message...", show_label=False, autofocus=True)
    with gr.Row():
        for example in EXAMPLES:
            gr.Button(example, size="sm").click(
                _example_handler(example), [chatbot, thread], [box, chatbot]
            )
    box.submit(chat, [box, chatbot, thread], [box, chatbot])
    chatbot.clear(_new_thread_id, None, [thread])

if __name__ == "__main__":
    port = os.environ.get("PORT")  # set by hosts like Render; unset locally
    if port:
        demo.launch(server_name="0.0.0.0", server_port=int(port))
    else:
        demo.launch()
