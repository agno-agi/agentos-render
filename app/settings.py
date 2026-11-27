"""
App Settings
============

Shared runtime objects for the platform.
"""

from os import getenv

from agno.models.openai import OpenAIResponses


def default_model() -> OpenAIResponses:
    """Fresh model instance per agent — avoids shared-state footguns."""
    return OpenAIResponses(id="gpt-6.1-sol")


def super_agent_model() -> OpenAIResponses:
    """Model for Super Agent and Company work."""
    # Test build only: the test stack can name another model for Super Agent.
    return OpenAIResponses(id=getenv("SUPER_AGENT_MODEL") or "gpt-6.1-terra")
