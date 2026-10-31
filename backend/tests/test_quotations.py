import pytest

from commercial_helpers import AS_OF


def template_body(commerce) -> dict:
    body = commerce.draft_body()
    body.pop("plan_id")
    body.pop("lines")
    return {**body, "template_id": commerce.template["id"]}


def test_template_copies_lines_and_quotation_validity(commerce) -> None:
    row = commerce.call("POST", "/subscriptions/from-template", 201, json=template_body(commerce))
    assert row["status"] == "quotation"
    assert row["quotation_date"] == AS_OF
    assert row["quotation_expiry_date"] == "2026-01-29"
    original_lines = row["lines"]
    commerce.call("PATCH", f"/quotation-templates/{commerce.template['id']}",
                  json={"validity_days": 90, "lines": [{"product_id": commerce.product["id"], "quantity": 5}]})
    preserved = commerce.call("GET", f"/subscriptions/{row['id']}")
    assert preserved["lines"] == original_lines
    assert preserved["quotation_expiry_date"] == "2026-01-29"
    commerce.action(row["id"], "confirm", 409, as_of="2026-01-30")


@pytest.mark.parametrize("patch", [{"validity_days": 0}, {"lines": [{"product_id": 1, "quantity": 0}]}, {"plan_id": 9999}])
def test_invalid_templates_are_rejected(commerce, patch: dict) -> None:
    body = {"name": "Invalid", "validity_days": 10, "plan_id": commerce.plan["id"], "lines": commerce.lines(), **patch}
    commerce.call("POST", "/quotation-templates", 422, json=body)


def test_template_line_crud_and_pagination(commerce) -> None:
    template_id = commerce.template["id"]
    line = commerce.call("POST", f"/quotation-templates/{template_id}/lines", 201,
                         json={"product_id": commerce.product["id"], "quantity": 3})
    result = commerce.call("GET", f"/quotation-templates/{template_id}/lines?limit=1&offset=1")
    assert result["total"] == 2
    assert result["items"][0]["id"] == line["id"]
    updated = commerce.call("PATCH", f"/quotation-templates/{template_id}/lines/{line['id']}",
                            json={"quantity": 4, "variant_id": commerce.variant["id"]})
    assert updated["quantity"] == 4
    commerce.call("DELETE", f"/quotation-templates/{template_id}/lines/{line['id']}", 204)
    assert commerce.call("GET", f"/quotation-templates/{template_id}")["lines"] == commerce.template["lines"]


def test_inactive_template_and_insufficient_copied_quantity_are_rejected(commerce) -> None:
    commerce.call("PATCH", f"/quotation-templates/{commerce.template['id']}", json={"lines": []})
    commerce.call("POST", "/subscriptions/from-template", 422, json=template_body(commerce))
    commerce.call("PATCH", f"/quotation-templates/{commerce.template['id']}", json={"active": False})
    commerce.call("POST", "/subscriptions/from-template", 422, json=template_body(commerce))


def test_actions_require_explicit_as_of(commerce) -> None:
    body = commerce.draft_body()
    body.pop("as_of")
    commerce.call("POST", "/subscriptions", 422, json=body)
    row = commerce.subscription()
    commerce.call("POST", f"/subscriptions/{row['id']}/quotation", 422, json={})
