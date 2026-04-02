"""app/services/flow_engine.py — deterministic menu state machine"""
import json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
log = get_logger(__name__)

class FlowLoader:
    _flow: dict | None = None
    @classmethod
    def get(cls) -> dict:
        if cls._flow is None:
            cls._flow = json.loads(Path(settings.flow_file).read_text(encoding="utf-8"))
        return cls._flow

def _resolve(template: str, ctx: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(ctx.get(m.group(1), m.group(0))), template)

def _label(obj: Any, lang: str) -> str:
    if isinstance(obj, str): return obj
    return obj.get(lang) or obj.get("mr") or obj.get("en") or ""

class FlowEngine:
    def __init__(self):
        self.flow = FlowLoader.get()
        self.nodes = self.flow["nodes"]
        self.officer_map = self.flow.get("officer_map", {})

    def process(self, sess: dict, user_input: str, wa_name: str = "") -> tuple[str, dict]:
        lang = sess.get("language", "mr")
        current = sess.get("current_node", "START")
        ctx = sess.get("context", {})

        node = self.nodes.get(current)
        if not node:
            log.error("unknown_node", node=current)
            return self._fallback(sess, lang, ctx)

        # Language selection at START
        if current == "START":
            if user_input in ("lang_en", "English"):
                sess["language"] = lang = "en"
            else:
                sess["language"] = lang = "mr"
            ctx["user_name"] = wa_name
            sess["context"] = ctx
            return "MAIN_MENU", self._render(self.nodes["MAIN_MENU"], lang, ctx, sess)

        # Free text capture
        if node["type"] == "free_text":
            min_len = node.get("validation", {}).get("min_length", 1)
            if len(user_input.strip()) < min_len:
                return self._fallback(sess, lang, ctx)
            ctx["complaint_text"] = user_input.strip()
            sess["context"] = ctx
            next_node = node["next"]
            return next_node, self._render(self.nodes[next_node], lang, ctx, sess)

        # Menu option matching
        option = self._match_option(node, user_input, lang)
        if not option:
            sess["fallback_count"] = sess.get("fallback_count", 0) + 1
            if sess["fallback_count"] >= settings.max_fallback_retries:
                sess["fallback_count"] = 0
                return "HUMAN_ESCALATION", self._render(self.nodes["HUMAN_ESCALATION"], lang, ctx, sess)
            return self._fallback(sess, lang, ctx)

        sess["fallback_count"] = 0
        ctx = self._update_context(option, ctx, node, lang)
        sess["context"] = ctx

        next_node = option.get("next", "MAIN_MENU")
        if next_node == "COMPLAINT_EXTERNAL":
            ctx["url"] = option.get("meta", {}).get("url", "")
            sess["context"] = ctx

        sess["previous_node"] = current
        return next_node, self._render(self.nodes[next_node], lang, ctx, sess)

    def _render(self, node: dict, lang: str, ctx: dict, sess: dict) -> dict:
        messages = node.get("messages", {})
        text = _resolve(_label(messages, lang), ctx)
        ntype = node["type"]

        if ntype == "interactive_buttons":
            return self._buttons_payload(node, text, lang)
        if ntype == "interactive_list":
            return self._list_payload(node, text, lang)
        if ntype == "text_with_buttons":
            return self._buttons_payload(node, text, lang) if node.get("options") else {"type":"text","body":text}
        if ntype == "dynamic_list":
            return self._dynamic_list_payload(node, text, lang, ctx)
        return {"type": "text", "body": text}

    def _buttons_payload(self, node: dict, text: str, lang: str) -> dict:
        buttons = [
            {"type":"reply","reply":{"id":o["id"],"title":_label(o["title"],lang)[:20]}}
            for o in node.get("options",[])[:3]
        ]
        return {"type":"interactive","interactive":{"type":"button","body":{"text":text},"action":{"buttons":buttons}}}

    def _list_payload(self, node: dict, text: str, lang: str) -> dict:
        header = _label(node.get("list_header",{}), lang)
        btn    = _label(node.get("list_button",{}), lang) or "Select"
        rows   = [{"id":o["id"],"title":_label(o["title"],lang)[:24],"description":_label(o.get("description",""),lang)[:72]} for o in node.get("options",[])[:10]]
        return {"type":"interactive","interactive":{"type":"list","header":{"type":"text","text":header},"body":{"text":text},"action":{"button":btn,"sections":[{"title":header,"rows":rows}]}}}

    def _dynamic_list_payload(self, node: dict, text: str, lang: str, ctx: dict) -> dict:
        dept = ctx.get("department","dept_default")
        subtypes = node.get("subtypes",{})
        options = subtypes.get(dept) or subtypes.get("dept_default",[])
        header = _label(node.get("list_header",{}), lang)
        btn    = _label(node.get("list_button",{}), lang) or "Select"
        rows   = [{"id":o["id"],"title":_label(o["title"],lang)[:24],"description":""} for o in options[:10]]
        return {"type":"interactive","interactive":{"type":"list","header":{"type":"text","text":header},"body":{"text":text},"action":{"button":btn,"sections":[{"title":header,"rows":rows}]}}}

    def _match_option(self, node: dict, user_input: str, lang: str) -> dict | None:
        ui = user_input.strip()
        options = node.get("options", [])
        if node["type"] == "dynamic_list":
            options = [o for g in node.get("subtypes",{}).values() for o in g]
        for opt in options:
            title = _label(opt.get("title",""), lang)
            if ui == opt["id"] or ui.lower() == title.lower():
                return opt
            if len(ui) > 5 and (ui in title or title in ui):
                return opt
        return None

    def _update_context(self, option: dict, ctx: dict, node: dict, lang: str) -> dict:
        oid = option["id"]
        title = _label(option.get("title",""), lang)
        if oid.startswith("ward_"):
            ctx["ward"] = oid
            ctx["ward_name"] = title
            officer = self.officer_map.get(oid, {})
            ctx["officer_name"]  = officer.get("name","")
            ctx["officer_phone"] = officer.get("phone","")
        elif oid.startswith("dept_"):
            ctx["department"] = oid
            ctx["dept_name"]  = title
        elif node["id"] == "COMPLAINT_SUBTYPE":
            ctx["complaint_type"] = oid
            ctx["complaint_text"] = title
        elif oid == "confirm_yes":
            ctx["date"] = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
        return ctx

    def _fallback(self, sess: dict, lang: str, ctx: dict) -> tuple[str, dict]:
        return "FALLBACK", self._render(self.nodes["FALLBACK"], lang, ctx, sess)
