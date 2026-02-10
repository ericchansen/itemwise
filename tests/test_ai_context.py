"""Tests for AI context and smart suggestions."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import itemwise.ai_client as ai_client_module
from itemwise.ai_client import INVENTORY_TOOLS, _get_system_prompt


class TestInventoryTools:
    """Tests for AI tool definitions."""

    def test_tools_include_get_oldest_items(self):
        tool_names = [t["function"]["name"] for t in INVENTORY_TOOLS]
        assert "get_oldest_items" in tool_names

    def test_remove_item_has_lot_id_param(self):
        remove_tool = next(t for t in INVENTORY_TOOLS if t["function"]["name"] == "remove_item")
        params = remove_tool["function"]["parameters"]["properties"]
        assert "lot_id" in params

    def test_all_required_tools_present(self):
        tool_names = [t["function"]["name"] for t in INVENTORY_TOOLS]
        expected = ["add_item", "remove_item", "search_items", "list_items", "list_locations", "get_oldest_items"]
        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"

    def test_tool_definitions_are_valid(self):
        for tool in INVENTORY_TOOLS:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]


class TestSystemPrompt:
    """Tests for system prompt content."""

    def test_prompt_mentions_recipe_instructions(self):
        prompt = _get_system_prompt()
        assert "recipe" in prompt.lower()

    def test_prompt_mentions_list_items_for_suggestions(self):
        prompt = _get_system_prompt()
        assert "list_items" in prompt

    def test_prompt_mentions_oldest_items(self):
        prompt = _get_system_prompt()
        assert "oldest" in prompt.lower()

    def test_prompt_mentions_lot_tracking(self):
        prompt = _get_system_prompt()
        assert "batch" in prompt.lower() or "lot" in prompt.lower()

    def test_prompt_instructs_not_to_ask_user_to_list(self):
        prompt = _get_system_prompt()
        assert "do not ask" in prompt.lower() or "don't ask" in prompt.lower()


class TestMultiRoundToolCalling:
    """Tests for multi-round (looped) tool calling in process_chat_with_tools."""

    def setup_method(self) -> None:
        ai_client_module._client = None

    def teardown_method(self) -> None:
        ai_client_module._client = None

    def _make_mock_response(
        self, content: str = "Hello!", tool_calls: Any = None
    ) -> MagicMock:
        message = MagicMock()
        message.content = content
        message.tool_calls = tool_calls
        choice = MagicMock()
        choice.message = message
        response = MagicMock()
        response.choices = [choice]
        return response

    def _make_tool_call(
        self, name: str, arguments: dict[str, Any], call_id: str = "call_1"
    ) -> MagicMock:
        tool_call = MagicMock()
        tool_call.id = call_id
        tool_call.function.name = name
        tool_call.function.arguments = json.dumps(arguments)
        return tool_call

    async def test_chained_tool_calls_across_rounds(self) -> None:
        """Model calls search_items in round 1, then remove_item in round 2."""
        mock_client = MagicMock()

        search_call = self._make_tool_call(
            "search_items", {"query": "chicken"}, call_id="call_s"
        )
        remove_call = self._make_tool_call(
            "remove_item", {"item_id": 42}, call_id="call_r"
        )

        round1 = self._make_mock_response(tool_calls=[search_call])
        round2 = self._make_mock_response(tool_calls=[remove_call])
        final = self._make_mock_response(content="Removed chicken from inventory.")

        mock_client.chat.completions.create.side_effect = [round1, round2, final]

        search_handler = AsyncMock(
            return_value={"results": [{"id": 42, "name": "chicken"}]}
        )
        remove_handler = AsyncMock(return_value={"removed": True})

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            result = await ai_client_module.process_chat_with_tools(
                "Remove my chicken",
                {"search_items": search_handler, "remove_item": remove_handler},
            )

        assert result == "Removed chicken from inventory."
        search_handler.assert_called_once_with(query="chicken")
        remove_handler.assert_called_once_with(item_id=42)
        assert mock_client.chat.completions.create.call_count == 3

    async def test_loop_terminates_when_model_returns_text(self) -> None:
        """Loop stops on the first response with no tool_calls."""
        mock_client = MagicMock()

        tool_call = self._make_tool_call(
            "list_items", {}, call_id="call_list"
        )
        round1 = self._make_mock_response(tool_calls=[tool_call])
        final = self._make_mock_response(content="You have 3 items.")

        mock_client.chat.completions.create.side_effect = [round1, final]

        handler = AsyncMock(return_value={"items": ["a", "b", "c"]})

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            result = await ai_client_module.process_chat_with_tools(
                "What do I have?",
                {"list_items": handler},
            )

        assert result == "You have 3 items."
        # Only 2 LLM calls: one with tool_calls, one final text
        assert mock_client.chat.completions.create.call_count == 2

    async def test_safety_limit_max_iterations(self) -> None:
        """After 5 rounds of tool calls, the loop stops and requests a final text response."""
        mock_client = MagicMock()

        # Create 5 rounds that always return a tool call
        tool_responses = []
        for i in range(5):
            tc = self._make_tool_call(
                "list_items", {}, call_id=f"call_{i}"
            )
            tool_responses.append(self._make_mock_response(tool_calls=[tc]))

        # The 6th call is the safety-net final text response (no tools param)
        safety_final = self._make_mock_response(content="Here is your summary.")

        mock_client.chat.completions.create.side_effect = [
            *tool_responses,
            safety_final,
        ]

        handler = AsyncMock(return_value={"items": []})

        with patch("itemwise.ai_client.get_client", return_value=mock_client):
            result = await ai_client_module.process_chat_with_tools(
                "Keep going",
                {"list_items": handler},
            )

        assert result == "Here is your summary."
        # 5 loop iterations + 1 safety-net call = 6 total
        assert mock_client.chat.completions.create.call_count == 6
        assert handler.call_count == 5
