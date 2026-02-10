"""Tests for Azure OpenAI client module."""

import json
from typing import Any
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

import itemwise.ai_client as ai_client_module
from itemwise.ai_client import generate_display_name


class TestGenerateDisplayName:
    """Tests for generate_display_name function."""

    def test_basic_lowercase_name(self) -> None:
        assert generate_display_name("chicken breast") == "Chicken Breast"

    def test_already_capitalized(self) -> None:
        assert generate_display_name("Garage") == "Garage"

    def test_single_word(self) -> None:
        assert generate_display_name("freezer") == "Freezer"

    def test_empty_string(self) -> None:
        assert generate_display_name("") == ""

    def test_whitespace_only(self) -> None:
        assert generate_display_name("   ") == ""

    def test_possessive_name(self) -> None:
        result = generate_display_name("tims pocket")
        assert result == "Tim's Pocket"

    def test_non_possessive_word_ending_in_ss(self) -> None:
        result = generate_display_name("glass cabinet")
        assert result == "Glass Cabinet"

    def test_multiple_words(self) -> None:
        assert generate_display_name("big red barn") == "Big Red Barn"

    def test_mixed_case_input(self) -> None:
        assert generate_display_name("UPPER case MIX") == "Upper Case Mix"

    def test_name_with_numbers(self) -> None:
        result = generate_display_name("room 101")
        assert result == "Room 101"

    def test_possessive_at_end_not_applied(self) -> None:
        # Last word shouldn't get possessive treatment (no following word)
        result = generate_display_name("bobs")
        assert result == "Bobs"

    def test_short_s_word_not_possessive(self) -> None:
        # Two-letter words ending in 's' shouldn't be treated as possessive
        result = generate_display_name("is good")
        assert result == "Is Good"


class TestGetClient:
    """Tests for get_client function."""

    def setup_method(self) -> None:
        """Reset the cached client before each test."""
        ai_client_module._client = None

    def teardown_method(self) -> None:
        """Reset the cached client after each test."""
        ai_client_module._client = None

    def test_raises_when_no_endpoint(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
                ai_client_module.get_client()

    def test_returns_client_when_endpoint_configured(self) -> None:
        mock_credential = MagicMock()
        mock_token_provider = MagicMock()
        mock_azure_openai = MagicMock()

        with (
            patch.dict("os.environ", {"AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com"}),
            patch("itemwise.ai_client.DefaultAzureCredential", return_value=mock_credential),
            patch("itemwise.ai_client.get_bearer_token_provider", return_value=mock_token_provider),
            patch("itemwise.ai_client.AzureOpenAI", return_value=mock_azure_openai),
        ):
            client = ai_client_module.get_client()
            assert client is mock_azure_openai

    def test_caches_client_on_repeated_calls(self) -> None:
        mock_credential = MagicMock()
        mock_token_provider = MagicMock()
        mock_azure_openai = MagicMock()

        with (
            patch.dict("os.environ", {"AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com"}),
            patch("itemwise.ai_client.DefaultAzureCredential", return_value=mock_credential),
            patch("itemwise.ai_client.get_bearer_token_provider", return_value=mock_token_provider),
            patch("itemwise.ai_client.AzureOpenAI", return_value=mock_azure_openai) as mock_cls,
        ):
            client1 = ai_client_module.get_client()
            client2 = ai_client_module.get_client()
            assert client1 is client2
            mock_cls.assert_called_once()

    def test_passes_correct_params_to_azure_openai(self) -> None:
        mock_credential = MagicMock()
        mock_token_provider = MagicMock()

        with (
            patch.dict("os.environ", {"AZURE_OPENAI_ENDPOINT": "https://myendpoint.openai.azure.com"}),
            patch("itemwise.ai_client.DefaultAzureCredential", return_value=mock_credential),
            patch("itemwise.ai_client.get_bearer_token_provider", return_value=mock_token_provider),
            patch("itemwise.ai_client.AzureOpenAI") as mock_cls,
        ):
            ai_client_module.get_client()
            mock_cls.assert_called_once_with(
                azure_endpoint="https://myendpoint.openai.azure.com",
                azure_ad_token_provider=mock_token_provider,
                api_version="2024-10-21",
            )


class TestProcessChatWithTools:
    """Tests for process_chat_with_tools function."""

    def setup_method(self) -> None:
        ai_client_module._client = None

    def teardown_method(self) -> None:
        ai_client_module._client = None

    def _make_mock_response(self, content: str = "Hello!", tool_calls: Any = None) -> MagicMock:
        """Helper to create a mock chat completion response."""
        message = MagicMock()
        message.content = content
        message.tool_calls = tool_calls
        choice = MagicMock()
        choice.message = message
        response = MagicMock()
        response.choices = [choice]
        return response

    def _make_tool_call(self, name: str, arguments: dict[str, Any], call_id: str = "call_1") -> MagicMock:
        """Helper to create a mock tool call."""
        tool_call = MagicMock()
        tool_call.id = call_id
        tool_call.function.name = name
        tool_call.function.arguments = json.dumps(arguments)
        return tool_call

    async def test_returns_response_when_no_tool_calls(self) -> None:
        mock_client = MagicMock()
        mock_response = self._make_mock_response(content="I can help with that!")
        mock_client.chat.completions.create.return_value = mock_response

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            result = await ai_client_module.process_chat_with_tools(
                "What's in my inventory?",
                {},
            )
            assert result == "I can help with that!"

    async def test_returns_fallback_when_content_is_none(self) -> None:
        mock_client = MagicMock()
        mock_response = self._make_mock_response(content=None, tool_calls=None)
        # content is None triggers the fallback
        mock_response.choices[0].message.content = None
        mock_client.chat.completions.create.return_value = mock_response

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            result = await ai_client_module.process_chat_with_tools("hello", {})
            assert result == "I'm not sure how to help with that."

    async def test_handles_tool_calls(self) -> None:
        mock_client = MagicMock()
        tool_call = self._make_tool_call("search_items", {"query": "chicken"})

        # First response has tool calls
        first_response = self._make_mock_response(tool_calls=[tool_call])
        # Second response is the final answer
        final_response = self._make_mock_response(content="Found 2 chicken items.")

        mock_client.chat.completions.create.side_effect = [first_response, final_response]

        mock_handler = AsyncMock(return_value={"results": [{"name": "chicken"}]})
        tool_handlers = {"search_items": mock_handler}

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            result = await ai_client_module.process_chat_with_tools(
                "Do I have chicken?",
                tool_handlers,
            )
            assert result == "Found 2 chicken items."
            mock_handler.assert_called_once_with(query="chicken")

    async def test_handles_unknown_tool(self) -> None:
        mock_client = MagicMock()
        tool_call = self._make_tool_call("unknown_tool", {"arg": "val"})

        first_response = self._make_mock_response(tool_calls=[tool_call])
        final_response = self._make_mock_response(content="Sorry, I couldn't do that.")

        mock_client.chat.completions.create.side_effect = [first_response, final_response]

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            result = await ai_client_module.process_chat_with_tools(
                "Do something weird",
                {},
            )
            assert result == "Sorry, I couldn't do that."

    async def test_handles_tool_handler_error(self) -> None:
        mock_client = MagicMock()
        tool_call = self._make_tool_call("add_item", {"name": "test", "quantity": 1, "category": "misc", "location": "Garage"})

        first_response = self._make_mock_response(tool_calls=[tool_call])
        final_response = self._make_mock_response(content="There was an error adding the item.")

        mock_client.chat.completions.create.side_effect = [first_response, final_response]

        mock_handler = AsyncMock(side_effect=Exception("DB connection failed"))
        tool_handlers = {"add_item": mock_handler}

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            result = await ai_client_module.process_chat_with_tools(
                "Add test item to garage",
                tool_handlers,
            )
            assert result == "There was an error adding the item."

    async def test_multiple_tool_calls(self) -> None:
        mock_client = MagicMock()
        call1 = self._make_tool_call("search_items", {"query": "chicken"}, call_id="call_1")
        call2 = self._make_tool_call("search_items", {"query": "beef"}, call_id="call_2")

        first_response = self._make_mock_response(tool_calls=[call1, call2])
        final_response = self._make_mock_response(content="Found chicken and beef.")

        mock_client.chat.completions.create.side_effect = [first_response, final_response]

        mock_handler = AsyncMock(return_value={"results": []})
        tool_handlers = {"search_items": mock_handler}

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            result = await ai_client_module.process_chat_with_tools(
                "Do I have chicken or beef?",
                tool_handlers,
            )
            assert result == "Found chicken and beef."
            assert mock_handler.call_count == 2

    async def test_final_response_none_content(self) -> None:
        mock_client = MagicMock()
        tool_call = self._make_tool_call("list_items", {})

        first_response = self._make_mock_response(tool_calls=[tool_call])
        final_response = self._make_mock_response(content=None)
        final_response.choices[0].message.content = None

        mock_client.chat.completions.create.side_effect = [first_response, final_response]

        mock_handler = AsyncMock(return_value={"items": []})
        tool_handlers = {"list_items": mock_handler}

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            result = await ai_client_module.process_chat_with_tools("List all", tool_handlers)
            assert result == "Done."
