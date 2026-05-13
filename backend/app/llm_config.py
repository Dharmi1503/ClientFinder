"""
llm_config.py
=============
Configuration for the 3-tier LLM fallback chain.
"""

TIER1_NAME = "local_ollama"
TIER2_NAME = "anthropic_claude_haiku"
TIER3_NAME = "rule_based"

TIER1_TIMEOUT_SECONDS = 60
TIER2_TIMEOUT_SECONDS = 10

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"

ANTHROPIC_MODEL = "claude-3-haiku-20240307"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
