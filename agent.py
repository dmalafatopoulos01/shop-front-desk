"""Maple Street Auto front-desk agent (LangGraph). Run `python agent.py` for a terminal chat."""
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_ibm import ChatWatsonx
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from tools import TOOLS

load_dotenv()

MAX_USER_MESSAGES = 20  # cap per visitor/session

SYSTEM_PROMPT = """You are the front-desk assistant for Maple Street Auto, a made-up auto repair shop.
- Answer shop questions (hours, services, prices, warranty, location) ONLY from the search_shop_docs tool. Always call it before answering. If the docs don't say, say you don't know and suggest calling the shop.
- Never diagnose a car problem. Never give a firm price: give the typical range from the docs and say the final price follows an inspection.
- If a question is unrelated to the shop, politely say you can only help with Maple Street Auto questions.
- Keep answers short and friendly."""


def build_agent():
    llm = ChatWatsonx(
        model_id=os.environ.get("WATSONX_MODEL_ID", "ibm/granite-4-h-small"),
        url=os.environ["WATSONX_URL"],
        apikey=os.environ["WATSONX_APIKEY"],
        project_id=os.environ["WATSONX_PROJECT_ID"],
        params={"temperature": 0, "max_new_tokens": 400},
    )
    return create_react_agent(llm, TOOLS, prompt=SYSTEM_PROMPT, checkpointer=MemorySaver())


def ask(agent, text: str, thread_id: str = "cli") -> str:
    result = agent.invoke(
        {"messages": [HumanMessage(content=text)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].content


def main():
    agent = build_agent()
    print("Maple Street Auto front desk. Type 'quit' to exit.")
    for _ in range(MAX_USER_MESSAGES):
        try:
            text = input("\nYou: ").strip()
        except EOFError:
            return
        if text.lower() in {"quit", "exit"}:
            return
        if text:
            print(f"Agent: {ask(agent, text)}")
    print("\nMessage limit reached. Please call the shop at 555-0142.")


if __name__ == "__main__":
    main()
