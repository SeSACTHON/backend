"""Image generator test fixtures.

Mocks external dependencies (google.genai, openai) for isolated unit testing.

Note: These mocks must be applied before importing the modules under test.
"""

import sys
from unittest.mock import MagicMock

# Mock google.genai module
mock_genai = MagicMock()
mock_genai.Client = MagicMock()
mock_genai_types = MagicMock()

mock_part = MagicMock()
mock_part.from_text = MagicMock(return_value=MagicMock())
mock_part.from_bytes = MagicMock(return_value=MagicMock())
mock_genai_types.Part = mock_part
mock_genai_types.Content = MagicMock()
mock_genai_types.GenerateContentConfig = MagicMock()

sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = mock_genai
sys.modules["google.genai.types"] = mock_genai_types

# Mock openai module
mock_openai = MagicMock()
mock_async_openai = MagicMock()
mock_openai.AsyncOpenAI = mock_async_openai
sys.modules["openai"] = mock_openai

# Note: httpx is installed, no need to mock

# Also mock the parent __init__.py imports to avoid loading actual clients
# This is needed because chat_worker.infrastructure.llm.__init__.py imports clients
mock_llm_init = MagicMock()
sys.modules["chat_worker.infrastructure.llm.clients"] = mock_llm_init
sys.modules["chat_worker.infrastructure.llm.clients.gemini_client"] = MagicMock()
sys.modules["chat_worker.infrastructure.llm.clients.openai_client"] = MagicMock()
sys.modules["chat_worker.infrastructure.llm.evaluators"] = MagicMock()
sys.modules["chat_worker.infrastructure.llm.policies"] = MagicMock()
