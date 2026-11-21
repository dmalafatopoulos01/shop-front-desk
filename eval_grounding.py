"""Live check that the agent doesn't invent services. Calls the real model (needs .env).

Run:  python eval_grounding.py [runs_per_prompt]

Heuristic, not proof: it looks for service names that are NOT in docs/services.md and for
"yes, we do that" answers to services we don't offer. It can miss paraphrased inventions,
so a pass means "no known failure seen", not "never invents".
"""
import re
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

from agent import ask, build_agent

# Services the shop does NOT offer (not in docs/services.md). Mentioning one as an offering is a failure.
INVENTED = [
    "transmission", "alignment", "engine diagnostic", "engine repair", "engine rebuild", "exhaust",
    "muffler", "suspension", "detailing", "windshield", "body work", "bodywork", "paint",
    "radiator", "coolant", "timing belt", "clutch", "differential", "tune-up", "tune up",
    "smog", "emissions", "car wash", "towing",
]

# Open-ended prompts: the answer may list services, so none of INVENTED may appear.
LIST_PROMPTS = [
    "What services do you offer?",
    "yes",
    "tell me about the shop",
    "What do you do?",
    "Give me a summary of everything you can help with",
    "hi",
]

# Services we don't offer: the answer must decline, not affirm.
NEGATIVE_PROBES = [
    "Do you do transmission repair?",
    "Do you do wheel alignments?",
    "Can you fix my exhaust?",
]
DECLINE = re.compile(
    r"\b(not|don['’]t|do not|doesn['’]t|can['’]t|cannot|unable|isn['’]t|aren['’]t|only)\b"
    r"|not listed|call the shop|555.0142",
    re.I,
)

RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 3


def run_once(prompt: str) -> str:
    return ask(build_agent(), prompt, uuid.uuid4().hex)


def check_list(answer: str) -> list[str]:
    low = answer.lower()
    return [w for w in INVENTED if w in low]


def check_negative(answer: str) -> list[str]:
    return [] if DECLINE.search(answer) else ["did not decline"]


def main():
    jobs = [(p, "list") for p in LIST_PROMPTS for _ in range(RUNS)] + [(p, "neg") for p in NEGATIVE_PROBES for _ in range(RUNS)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        answers = list(pool.map(lambda j: run_once(j[0]), jobs))

    failures = 0
    for (prompt, kind), answer in zip(jobs, answers):
        problems = check_list(answer) if kind == "list" else check_negative(answer)
        if problems:
            failures += 1
            print(f"FAIL [{prompt!r}] {problems}\n  -> {answer[:300]!r}\n")
    total = len(jobs)
    print(f"{total - failures}/{total} answers clean ({failures} with a problem)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
