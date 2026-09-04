"""Model provider switch.

MODEL_PROVIDER=fake   -> no API key needed, deterministic stub (local dev / CI)
MODEL_PROVIDER=groq   -> matches your Session 1 labs (ChatGroq, free tier)
MODEL_PROVIDER=bedrock -> matches your Session 2 labs + AgentCore deployment

Keep this the ONLY place that knows which provider is active — every node
imports get_chat_model()/is_fake(), nothing else touches env vars directly.
"""
from __future__ import annotations

import os


def provider() -> str:
    return os.environ.get("MODEL_PROVIDER", "fake").lower()


def is_fake() -> bool:
    return provider() == "fake"


def get_chat_model(temperature: float = 0.0):
    p = provider()

    if p == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=temperature,
            api_key=os.environ["GROQ_API_KEY"],
        )

    if p == "bedrock":
        from langchain_aws import ChatBedrock

        return ChatBedrock(
            model_id=os.environ.get(
                "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"
            ),
            region_name=os.environ.get("AWS_REGION", "ap-southeast-1"),
            model_kwargs={"temperature": temperature},
        )

    raise RuntimeError(
        f"get_chat_model() called with MODEL_PROVIDER={p!r} — 'fake' mode should "
        "never call this; check the caller's is_fake() guard."
    )
