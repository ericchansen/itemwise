"""Tests for AI context and smart suggestions."""

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
