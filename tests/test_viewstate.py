from hut_bot.grabber.viewstate import parse_all_hidden_inputs, parse_viewstate

ASPNET_FORM = """
<html><body>
<form id="aspnetForm">
  <input type="hidden" name="__VIEWSTATE" value="VIEWSTATE_VALUE_BASE64==" />
  <input type="hidden" name="__VIEWSTATEGENERATOR" value="ABCD1234" />
  <input type="hidden" name="__EVENTVALIDATION" value="EVENTVAL_VALUE_BASE64==" />
  <input type="hidden" name="__EVENTTARGET" value="" />
  <input type="hidden" name="__EVENTARGUMENT" value="" />
  <input type="hidden" name="someOtherHidden" value="hello" />
  <input type="text" name="visibleInput" value="not hidden" />
</form>
</body></html>
"""


def test_parse_viewstate_extracts_three_critical_fields() -> None:
    bundle = parse_viewstate(ASPNET_FORM)
    assert bundle.viewstate == "VIEWSTATE_VALUE_BASE64=="
    assert bundle.viewstate_generator == "ABCD1234"
    assert bundle.event_validation == "EVENTVAL_VALUE_BASE64=="
    assert bundle.viewstate_encrypted == ""


def test_parse_viewstate_as_payload_has_all_keys() -> None:
    bundle = parse_viewstate(ASPNET_FORM)
    payload = bundle.as_payload()
    assert payload["__VIEWSTATE"] == "VIEWSTATE_VALUE_BASE64=="
    assert payload["__VIEWSTATEGENERATOR"] == "ABCD1234"
    assert payload["__EVENTVALIDATION"] == "EVENTVAL_VALUE_BASE64=="
    assert "__VIEWSTATEENCRYPTED" not in payload


def test_parse_viewstate_returns_empty_strings_when_missing() -> None:
    bundle = parse_viewstate("<html><body><form></form></body></html>")
    assert bundle.viewstate == ""
    assert bundle.event_validation == ""


def test_parse_all_hidden_inputs_includes_only_hidden() -> None:
    hidden = parse_all_hidden_inputs(ASPNET_FORM)
    assert "__VIEWSTATE" in hidden
    assert "__EVENTTARGET" in hidden
    assert "someOtherHidden" in hidden
    assert hidden["someOtherHidden"] == "hello"
    assert "visibleInput" not in hidden
