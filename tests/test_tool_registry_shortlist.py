from chat.tool_registry import select_tool_descriptions_for_prompt, tool_descriptions_for_prompt


def _names(tools):
    return {tool["name"] for tool in tools}


def test_full_tool_registry_contains_expanded_catalog():
    names = _names(tool_descriptions_for_prompt())

    assert "get_total_revenue" in names
    assert "get_order_status_breakdown" in names
    assert "get_shipment_status_breakdown" in names
    assert "get_payment_method_breakdown" in names
    assert "get_order_timeline" in names


def test_revenue_question_gets_compact_relevant_tool_subset():
    tools = select_tool_descriptions_for_prompt("what is revenue impact for rto orders?")
    names = _names(tools)

    assert len(tools) <= 8
    assert "get_total_revenue" in names
    assert "get_revenue_for_order_ids" in names
    assert "get_rto_orders" in names


def test_payment_question_gets_payment_tools_without_full_catalog():
    tools = select_tool_descriptions_for_prompt("show cod and upi payment breakdown")
    names = _names(tools)

    assert len(tools) <= 8
    assert "get_payment_method_breakdown" in names
    assert "get_orders_by_payment_method" in names
    assert "get_shipment_status_breakdown" not in names


def test_shipment_id_question_gets_lookup_tool():
    tools = select_tool_descriptions_for_prompt("SHIP-778 what is the shipment date")
    names = _names(tools)

    assert len(tools) <= 8
    assert "get_shipment_by_id" in names


def test_order_shipment_question_prioritizes_shipments_for_order_tool():
    tools = select_tool_descriptions_for_prompt(
        "shipment id linked to order id ORD-101 and also tell me courier name"
    )
    names = [tool["name"] for tool in tools]

    assert len(tools) <= 8
    assert "get_shipments_for_order" in names
    assert names.index("get_shipments_for_order") == 0
