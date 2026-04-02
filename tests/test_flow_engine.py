"""tests/test_flow_engine.py — unit tests for FlowEngine (no DB/Redis needed)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock
from app.services.flow_engine import FlowEngine, _resolve, _label

# ── Helpers ───────────────────────────────────────────────────

def make_sess(node="START", lang="mr", ctx=None, fallback_count=0):
    return {"current_node": node, "language": lang, "context": ctx or {}, "fallback_count": fallback_count, "db_id": None}


@pytest.fixture
def engine():
    return FlowEngine()


# ── _resolve ──────────────────────────────────────────────────

def test_resolve_replaces_known_keys():
    assert _resolve("Hello {name}!", {"name": "Rahul"}) == "Hello Rahul!"

def test_resolve_leaves_unknown_keys():
    assert _resolve("{unknown}", {}) == "{unknown}"

def test_resolve_multiple():
    result = _resolve("{a} and {b}", {"a": "X", "b": "Y"})
    assert result == "X and Y"


# ── _label ────────────────────────────────────────────────────

def test_label_string():
    assert _label("hello", "mr") == "hello"

def test_label_dict_mr():
    assert _label({"mr": "नमस्कार", "en": "Hello"}, "mr") == "नमस्कार"

def test_label_dict_en():
    assert _label({"mr": "नमस्कार", "en": "Hello"}, "en") == "Hello"

def test_label_fallback_to_mr():
    assert _label({"mr": "नमस्कार"}, "en") == "नमस्कार"


# ── Language selection ────────────────────────────────────────

def test_language_select_english(engine):
    sess = make_sess("START")
    next_node, payload = engine.process(sess, "lang_en", "Rahul")
    assert next_node == "MAIN_MENU"
    assert sess["language"] == "en"
    assert payload["type"] == "interactive"

def test_language_select_marathi(engine):
    sess = make_sess("START")
    next_node, payload = engine.process(sess, "मराठी", "अभिजीत")
    assert next_node == "MAIN_MENU"
    assert sess["language"] == "mr"

def test_user_name_stored_in_context(engine):
    sess = make_sess("START")
    engine.process(sess, "lang_en", "TestUser")
    assert sess["context"].get("user_name") == "TestUser"


# ── Main menu navigation ──────────────────────────────────────

def test_main_menu_to_schemes(engine):
    sess = make_sess("MAIN_MENU", "en")
    next_node, payload = engine.process(sess, "menu_7", "User")
    assert next_node == "SCHEMES"
    assert payload["type"] == "interactive"

def test_main_menu_to_complaint_channel(engine):
    sess = make_sess("MAIN_MENU", "mr")
    next_node, _ = engine.process(sess, "menu_2")
    assert next_node == "COMPLAINT_CHANNEL"

def test_main_menu_to_emergency(engine):
    sess = make_sess("MAIN_MENU", "en")
    next_node, _ = engine.process(sess, "menu_5")
    assert next_node == "EMERGENCY"


# ── Schemes flow ──────────────────────────────────────────────

def test_scheme_pmay(engine):
    sess = make_sess("SCHEMES", "en")
    next_node, payload = engine.process(sess, "scheme_pmay")
    assert next_node == "SCHEME_PMAY"
    assert "pmaymis.gov.in" in payload.get("interactive", {}).get("body", {}).get("text", "")

def test_scheme_sba(engine):
    sess = make_sess("SCHEMES", "mr")
    next_node, payload = engine.process(sess, "scheme_sba")
    assert next_node == "SCHEME_SBA"
    assert "sbmurban.org" in payload.get("interactive", {}).get("body", {}).get("text", "")


# ── Complaint flow ────────────────────────────────────────────

def test_complaint_channel_whatsapp(engine):
    sess = make_sess("COMPLAINT_CHANNEL", "mr")
    next_node, _ = engine.process(sess, "ch_wa")
    assert next_node == "COMPLAINT_WARD"

def test_complaint_external_channel(engine):
    sess = make_sess("COMPLAINT_CHANNEL", "en")
    next_node, _ = engine.process(sess, "ch_website")
    assert next_node == "COMPLAINT_EXTERNAL"
    assert "url" in sess["context"]

def test_ward_selection_stores_context(engine):
    sess = make_sess("COMPLAINT_WARD", "mr")
    next_node, _ = engine.process(sess, "ward_1")
    assert next_node == "COMPLAINT_TYPE"
    assert sess["context"]["ward"] == "ward_1"
    assert sess["context"]["officer_phone"] == "8975758827"

def test_dept_selection(engine):
    sess = make_sess("COMPLAINT_TYPE", "mr", {"ward": "ward_1", "ward_name": "सावेडी"})
    next_node, _ = engine.process(sess, "dept_enc")
    assert next_node == "COMPLAINT_SUBTYPE"
    assert sess["context"]["department"] == "dept_enc"

def test_subtype_selection_enc(engine):
    sess = make_sess("COMPLAINT_SUBTYPE", "mr", {"ward": "ward_1", "department": "dept_enc"})
    next_node, _ = engine.process(sess, "e1")
    assert next_node == "COMPLAINT_CONFIRM"

def test_free_text_minimum_length(engine):
    sess = make_sess("COMPLAINT_FREETEXT", "mr")
    next_node, _ = engine.process(sess, "ab")   # too short
    assert next_node == "FALLBACK"

def test_free_text_valid(engine):
    sess = make_sess("COMPLAINT_FREETEXT", "en")
    next_node, _ = engine.process(sess, "There is a broken pipe on main road")
    assert next_node == "COMPLAINT_CONFIRM"
    assert sess["context"]["complaint_text"] == "There is a broken pipe on main road"

def test_confirm_yes_goes_to_success(engine):
    sess = make_sess("COMPLAINT_CONFIRM", "en", {"ward": "ward_1", "dept_name": "Water", "complaint_text": "No water"})
    next_node, _ = engine.process(sess, "confirm_yes")
    assert next_node == "COMPLAINT_SUCCESS"

def test_confirm_no_restarts_ward(engine):
    sess = make_sess("COMPLAINT_CONFIRM", "en", {})
    next_node, _ = engine.process(sess, "confirm_no")
    assert next_node == "COMPLAINT_WARD"


# ── Fallback & escalation ─────────────────────────────────────

def test_invalid_input_fallback(engine):
    sess = make_sess("MAIN_MENU", "en", fallback_count=0)
    next_node, _ = engine.process(sess, "garbage_input_xyz")
    assert next_node == "FALLBACK"
    assert sess["fallback_count"] == 1

def test_max_fallback_triggers_escalation(engine):
    sess = make_sess("MAIN_MENU", "en", fallback_count=2)
    next_node, _ = engine.process(sess, "still_invalid")
    assert next_node == "HUMAN_ESCALATION"
    assert sess["fallback_count"] == 0

def test_valid_input_resets_fallback(engine):
    sess = make_sess("MAIN_MENU", "en", fallback_count=2)
    engine.process(sess, "menu_5")   # valid: Emergency
    assert sess["fallback_count"] == 0
