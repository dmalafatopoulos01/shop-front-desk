"""Maple Street Auto front-desk agent (LangGraph). Run `python agent.py` for a terminal chat."""
import os
from datetime import date

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_ibm import ChatWatsonx
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command

from tools import TOOLS

load_dotenv()

MAX_USER_MESSAGES = 20  # cap per visitor/session

SYSTEM_PROMPT = """You are the front-desk assistant for Maple Street Auto, a made-up auto repair shop.
- Answer shop questions (hours, services, prices, warranty, location) ONLY from the search_shop_docs tool. Always call it before answering a shop question.
- Grounding rules. State only facts that appear in the tool results; never use general knowledge about what auto shops usually do. When listing services, list only the services named in the results, in their own words, and never add "and more", "etc.", or any service that is not named. If asked whether we do something that the results do not name, do NOT say yes: say it isn't listed so you can't confirm it, and suggest calling the shop at 555-0142. If the docs don't say, say you don't know and suggest calling the shop.
- If the visitor's message is not a question or request (for example just "yes", "ok", "hi" or "thanks"), do not call tools or summarize the shop: reply briefly and ask what they'd like help with.
- Never diagnose a car problem. Never give a firm price: give the typical range from the docs and say the final price follows an inspection.
- For availability questions ("what's open Friday?"), call get_open_slots with the weekday name or ISO date and list exactly the times it returns. Never invent times.
- To book: collect the customer's name, phone number, service, and an open date and time (check with get_open_slots first). Ask for anything missing; never invent details. Then call book_appointment. The system asks the customer to confirm and re-checks the slot itself; after the tool returns, relay its result honestly. If the tool says the slot is unavailable, tell the customer and ask which other time they want; never choose a different date or time for them. Never say something is booked unless the tool said "Booked".
- Today's date is {today}.
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
    return create_react_agent(llm, TOOLS, prompt=SYSTEM_PROMPT.format(today=date.today().strftime("%A %Y-%m-%d")), checkpointer=MemorySaver())


def ask(agent, text: str, thread_id: str = "cli") -> str:
    """One visitor turn. If a booking is waiting for confirmation, `text` is the answer to it."""
    config = {"configurable": {"thread_id": thread_id}}
    pending = any(t.interrupts for t in agent.get_state(config).tasks)
    inp = Command(resume=text) if pending else {"messages": [HumanMessage(content=text)]}
    result = agent.invoke(inp, config=config)
    if result.get("__interrupt__"):  # booking readback: show it, wait for yes/no
        return result["__interrupt__"][0].value
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
