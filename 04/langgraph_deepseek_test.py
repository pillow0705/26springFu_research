"""Minimal LangGraph + DeepSeek connectivity test.

Run with:
    DEEPSEEK_API_KEY='sk-...' .venv/bin/python langgraph_deepseek_test.py
"""

import os
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph


class TestState(TypedDict):
    prompt: str
    answer: str


model = ChatOpenAI(
    model="deepseek-flash",
    base_url="https://api.deepseek.com",
    api_key=os.environ["DEEPSEEK_API_KEY"],
    temperature=0,
)


def ask_deepseek(state: TestState) -> dict[str, str]:
    response = model.invoke(state["prompt"])
    return {"answer": str(response.content)}


graph = StateGraph(TestState)
graph.add_node("ask_deepseek", ask_deepseek)
graph.add_edge(START, "ask_deepseek")
graph.add_edge("ask_deepseek", END)
app = graph.compile()


if __name__ == "__main__":
    result = app.invoke({"prompt": "Reply with exactly: LangGraph works."})
    print(result["answer"])
