#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI/UX Pro Max Design System Generator

Combines multi-domain BM25 search (product, style, color, landing, typography)
with the reasoning rules in ui-reasoning.csv to produce a complete design system,
formatted as an ASCII box or Markdown, optionally persisted to disk as
design-system/MASTER.md (+ design-system/pages/<page>.md).
"""

import json
import re
import textwrap
import unicodedata
from datetime import date
from pathlib import Path

from core import DATA_DIR, _load_csv, search

REASONING_FILE = "ui-reasoning.csv"
BOX_WIDTH = 90

# Results per domain for the multi-domain search
SEARCH_CONFIG = {
    "product": {"max_results": 1},
    "style": {"max_results": 3},
    "color": {"max_results": 2},
    "landing": {"max_results": 2},
    "typography": {"max_results": 3},
}

# Fallback rule when no reasoning row matches the detected category
DEFAULT_RULE = {
    "UI_Category": "General",
    "Recommended_Pattern": "Hero + Features + CTA",
    "Style_Priority": "Minimalism + Flat Design",
    "Color_Mood": "Professional + Accent contrast",
    "Typography_Mood": "Modern + Professional",
    "Key_Effects": "Subtle hover (200-250ms) + Smooth transitions",
    "Decision_Rules": "{}",
    "Anti_Patterns": "Excessive animation + Low contrast text",
    "Severity": "MEDIUM",
}

# Words in "if_xxx" rule conditions that are too generic to require in the query
_CONDITION_STOPWORDS = {"focused", "available", "needed", "ready", "heavy", "field", "metric", "has"}

PRE_DELIVERY_CHECKLIST = [
    "No emojis as icons (use SVG: Heroicons/Lucide)",
    "cursor-pointer on all clickable elements",
    "Hover states with smooth transitions (150-300ms)",
    "Light mode: text contrast 4.5:1 minimum",
    "Focus states visible for keyboard navigation",
    "prefers-reduced-motion respected",
    "Responsive: 375px, 768px, 1024px, 1440px",
]


# ============ HELPERS ============
def _split_plus(text):
    """Split 'A + B + C' style fields into a clean list."""
    return [p.strip() for p in str(text or "").split("+") if p.strip()]


def _words(text):
    return set(re.findall(r"[a-z0-9]+", str(text).lower()))


def _slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return slug or "page"


def _parse_rules(raw):
    """Parse Decision_Rules JSON, keeping duplicate keys (e.g. repeated must_have)."""
    try:
        return json.loads(raw or "{}", object_pairs_hook=list)
    except ValueError:
        return []


def _first(result):
    rows = result.get("results") or []
    return rows[0] if rows else {}


# ============ GENERATOR ============
class DesignSystemGenerator:
    """Builds a design system from multi-domain search plus reasoning rules."""

    def __init__(self):
        path = DATA_DIR / REASONING_FILE
        self.reasoning_data = _load_csv(path) if path.exists() else []

    def _multi_domain_search(self, query, rule):
        """Run the per-domain searches, enriching queries with the rule's moods."""
        style_query = "{} {}".format(query, rule.get("Style_Priority", ""))
        typo_query = "{} {}".format(query, rule.get("Typography_Mood", ""))
        landing_query = "{} {}".format(rule.get("Recommended_Pattern", ""), query)
        return {
            "style": search(style_query, "style", SEARCH_CONFIG["style"]["max_results"]),
            "color": search(query, "color", SEARCH_CONFIG["color"]["max_results"]),
            "landing": search(landing_query, "landing", SEARCH_CONFIG["landing"]["max_results"]),
            "typography": search(typo_query, "typography", SEARCH_CONFIG["typography"]["max_results"]),
        }

    def _find_reasoning_rule(self, category, query):
        """Match a product category (and query) to a row in ui-reasoning.csv.

        category may be None when the product search found nothing.
        """
        if not self.reasoning_data:
            return dict(DEFAULT_RULE)
        cat = (category or "").lower().strip()

        if cat:
            # 1. Exact category match
            for row in self.reasoning_data:
                if row.get("UI_Category", "").lower() == cat:
                    return row
            # 2. Substring match either way
            for row in self.reasoning_data:
                ui_cat = row.get("UI_Category", "").lower()
                if ui_cat and (ui_cat in cat or cat in ui_cat):
                    return row
        # 3. Best word overlap with category + query
        target = _words(cat) | _words(query)
        best, best_score = None, 0
        for row in self.reasoning_data:
            score = len(_words(row.get("UI_Category", "")) & target)
            if score > best_score:
                best, best_score = row, score
        return best or dict(DEFAULT_RULE)

    def _select_best_match(self, results, priority_keywords, name_col):
        """Pick the result whose name/keywords best match the priority keywords."""
        if not results:
            return {}
        priorities = [p.lower() for p in priority_keywords]
        best, best_score = results[0], -1
        for rank, row in enumerate(results):
            name = str(row.get(name_col, "")).strip().lower()
            haystack = " ".join(str(v) for v in row.values()).lower()
            score = 0
            for p in priorities:
                if p and name and (p in name or name in p):  # "" is a substring of everything
                    score += 10
                score += len(_words(p) & _words(haystack))
            score -= rank * 0.1  # keep BM25 order as tie-breaker
            if score > best_score:
                best, best_score = row, score
        return best

    def _apply_decision_rules(self, raw_rules, query):
        """Return (triggered, must_have, all) decision rules for the query."""
        query_words = _words(query)
        triggered, must_have, all_rules = [], [], []
        for key, value in _parse_rules(raw_rules):
            all_rules.append((key, value))
            if key == "must_have":
                must_have.append(value)
            elif key.startswith("if_"):
                words = [w for w in key[3:].split("_") if w not in _CONDITION_STOPWORDS]
                if words and all(w in query_words for w in words):
                    triggered.append((key, value))
        return triggered, must_have, all_rules

    def generate(self, query, project_name=None):
        """Generate the design system dict for a query."""
        product = _first(search(query, "product", SEARCH_CONFIG["product"]["max_results"]))
        rule = self._find_reasoning_rule(product.get("Product Type"), query)
        category = product.get("Product Type") or rule.get("UI_Category", "General")
        results = self._multi_domain_search(query, rule)

        style_priority = _split_plus(rule.get("Style_Priority"))
        style = self._select_best_match(results["style"].get("results", []), style_priority, "Style Category")
        # If the best style doesn't match any priority, look the top priority up directly
        if style_priority and not any(p.lower() in str(style.get("Style Category", "")).lower()
                                      for p in style_priority):
            direct = _first(search(style_priority[0], "style", 1))
            if style_priority[0].lower() in str(direct.get("Style Category", "")).lower():
                style = direct

        color = _first(search(category, "color", 1)) or _first(results["color"])
        landing = self._select_best_match(results["landing"].get("results", []),
                                          [rule.get("Recommended_Pattern", "")], "Pattern Name")
        typography = self._select_best_match(results["typography"].get("results", []),
                                             _split_plus(rule.get("Typography_Mood")), "Font Pairing Name")

        triggered, must_have, all_rules = self._apply_decision_rules(rule.get("Decision_Rules"), query)

        return {
            "project_name": project_name or query.upper(),
            "query": query,
            "category": category,
            "rule_category": rule.get("UI_Category", "General"),
            "severity": rule.get("Severity", "MEDIUM"),
            "pattern": {
                "name": rule.get("Recommended_Pattern") or landing.get("Pattern Name", ""),
                "landing_match": landing.get("Pattern Name", ""),
                "sections": landing.get("Section Order", ""),
                "cta_placement": landing.get("Primary CTA Placement", ""),
                "color_strategy": landing.get("Color Strategy", ""),
                "conversion": landing.get("Conversion Optimization", ""),
            },
            "style": {
                "name": style.get("Style Category", rule.get("Style_Priority", "")),
                "priority": rule.get("Style_Priority", ""),
                "type": style.get("Type", ""),
                "keywords": style.get("Keywords", ""),
                "effects": style.get("Effects & Animation", ""),
                "best_for": style.get("Best For", ""),
                "performance": style.get("Performance", ""),
                "accessibility": style.get("Accessibility", ""),
                "complexity": style.get("Complexity", ""),
            },
            "colors": {
                "mood": rule.get("Color_Mood", ""),
                "primary": color.get("Primary (Hex)", ""),
                "secondary": color.get("Secondary (Hex)", ""),
                "cta": color.get("CTA (Hex)", ""),
                "background": color.get("Background (Hex)", ""),
                "text": color.get("Text (Hex)", ""),
                "border": color.get("Border (Hex)", ""),
                "notes": color.get("Notes", ""),
            },
            "typography": {
                "name": typography.get("Font Pairing Name", ""),
                "heading": typography.get("Heading Font", ""),
                "body": typography.get("Body Font", ""),
                "mood": typography.get("Mood/Style Keywords", rule.get("Typography_Mood", "")),
                "best_for": typography.get("Best For", ""),
                "google_fonts_url": typography.get("Google Fonts URL", ""),
                "css_import": typography.get("CSS Import", ""),
                "tailwind_config": typography.get("Tailwind Config", ""),
            },
            "dashboard_style": product.get("Dashboard Style (if applicable)", ""),
            "key_effects": _split_plus(rule.get("Key_Effects")),
            "anti_patterns": _split_plus(rule.get("Anti_Patterns")),
            "decision_rules": all_rules,
            "triggered_rules": triggered,
            "must_have": must_have,
        }


# ============ ASCII FORMAT ============
def _display_width(text):
    """Terminal column width (wide CJK/emoji count as 2)."""
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def _box_line(text=""):
    inner = BOX_WIDTH - 4
    pad = max(0, inner - _display_width(text))
    return "| " + text + " " * pad + " |"


def _box_wrap(text, indent=0):
    inner = BOX_WIDTH - 4
    prefix = " " * indent
    lines = textwrap.wrap(str(text), width=inner - indent, break_long_words=True,
                          break_on_hyphens=False) or [""]
    return [_box_line(prefix + line) for line in lines]


def _box_field(label, value, indent=5):
    if not value:
        return []
    return _box_wrap("{}: {}".format(label, value), indent)


def format_ascii_box(ds):
    """Render the design system as an ASCII box for terminals."""
    border = "+" + "-" * (BOX_WIDTH - 2) + "+"
    out = [border]
    out += _box_wrap("TARGET: {} - RECOMMENDED DESIGN SYSTEM".format(ds["project_name"]), 1)
    out += _box_wrap("Category: {} | Rules: {} ({})".format(
        ds["category"], ds["rule_category"], ds["severity"]), 1)
    out.append(border)

    p = ds["pattern"]
    out.append(_box_line())
    out += _box_wrap("PATTERN: {}".format(p["name"]), 1)
    out += _box_field("Conversion", p["conversion"])
    out += _box_field("CTA", p["cta_placement"])
    if p["sections"]:
        out += _box_wrap("Sections:", 5)
        for sec in re.split(r",\s*(?=\d+\.)", p["sections"]):
            out += _box_wrap(sec.strip(), 7)

    s = ds["style"]
    out.append(_box_line())
    out += _box_wrap("STYLE: {}".format(s["name"]), 1)
    out += _box_field("Keywords", s["keywords"])
    out += _box_field("Best For", s["best_for"])
    if s["performance"] or s["accessibility"]:
        out += _box_wrap("Performance: {} | Accessibility: {}".format(s["performance"], s["accessibility"]), 5)

    c = ds["colors"]
    out.append(_box_line())
    out += _box_wrap("COLORS: {}".format(c["mood"]), 1)
    for label, key in (("Primary", "primary"), ("Secondary", "secondary"), ("CTA", "cta"),
                       ("Background", "background"), ("Text", "text"), ("Border", "border")):
        if c[key]:
            out += _box_wrap("{:<11} {}".format(label + ":", c[key]), 5)
    out += _box_field("Notes", c["notes"])

    t = ds["typography"]
    out.append(_box_line())
    out += _box_wrap("TYPOGRAPHY: {} / {}".format(t["heading"], t["body"]), 1)
    out += _box_field("Pairing", t["name"])
    out += _box_field("Mood", t["mood"])
    out += _box_field("Best For", t["best_for"])
    out += _box_field("Google Fonts", t["google_fonts_url"])

    out.append(_box_line())
    out += _box_wrap("KEY EFFECTS:", 1)
    for effect in ds["key_effects"]:
        out += _box_wrap("- " + effect, 5)
    if s["effects"]:
        out += _box_field("Style effects", s["effects"])

    out.append(_box_line())
    out += _box_wrap("AVOID (Anti-patterns):", 1)
    for anti in ds["anti_patterns"]:
        out += _box_wrap("- " + anti, 5)

    if ds["triggered_rules"] or ds["must_have"]:
        out.append(_box_line())
        out += _box_wrap("DECISION RULES:", 1)
        for key, value in ds["triggered_rules"]:
            out += _box_wrap("{} -> {}".format(key, value), 5)
        for value in ds["must_have"]:
            out += _box_wrap("must have: {}".format(value), 5)

    out.append(_box_line())
    out += _box_wrap("PRE-DELIVERY CHECKLIST:", 1)
    for item in PRE_DELIVERY_CHECKLIST:
        out += _box_wrap("[ ] " + item, 5)
    out.append(_box_line())
    out.append(border)
    return "\n".join(out)


# ============ MARKDOWN FORMAT ============
def format_markdown(ds):
    """Render the design system as Markdown."""
    p, s, c, t = ds["pattern"], ds["style"], ds["colors"], ds["typography"]
    md = [
        "## Design System: {}".format(ds["project_name"]),
        "",
        "**Category:** {} | **Reasoning rule:** {} | **Severity:** {}".format(
            ds["category"], ds["rule_category"], ds["severity"]),
        "",
        "### Pattern",
        "- **Name:** {}".format(p["name"]),
    ]
    if p["landing_match"] and p["landing_match"] != p["name"]:
        md.append("- **Closest landing pattern:** {}".format(p["landing_match"]))
    for label, key in (("Conversion", "conversion"), ("CTA Placement", "cta_placement"),
                       ("Color Strategy", "color_strategy"), ("Sections", "sections")):
        if p[key]:
            md.append("- **{}:** {}".format(label, p[key]))

    md += ["", "### Style", "- **Name:** {}".format(s["name"]),
           "- **Priority (rules):** {}".format(s["priority"])]
    for label, key in (("Type", "type"), ("Keywords", "keywords"), ("Best For", "best_for"),
                       ("Performance", "performance"), ("Accessibility", "accessibility"),
                       ("Complexity", "complexity")):
        if s[key]:
            md.append("- **{}:** {}".format(label, s[key]))

    md += ["", "### Colors", "", "**Mood:** {}".format(c["mood"]), "",
           "| Role | Hex |", "|------|-----|"]
    for label, key in (("Primary", "primary"), ("Secondary", "secondary"), ("CTA", "cta"),
                       ("Background", "background"), ("Text", "text"), ("Border", "border")):
        md.append("| {} | {} |".format(label, c[key] or "-"))
    if c["notes"]:
        md += ["", "*Notes: {}*".format(c["notes"])]

    md += ["", "### Typography",
           "- **Heading:** {}".format(t["heading"]),
           "- **Body:** {}".format(t["body"])]
    for label, key in (("Pairing", "name"), ("Mood", "mood"), ("Best For", "best_for"),
                       ("Google Fonts", "google_fonts_url")):
        if t[key]:
            md.append("- **{}:** {}".format(label, t[key]))
    if t["css_import"]:
        md += ["", "```css", t["css_import"], "```"]

    md += ["", "### Key Effects"]
    md += ["- {}".format(e) for e in ds["key_effects"]]
    if s["effects"]:
        md.append("- Style effects: {}".format(s["effects"]))

    md += ["", "### Avoid (Anti-patterns)"]
    md += ["- {}".format(a) for a in ds["anti_patterns"]]

    if ds["decision_rules"]:
        triggered = set(k for k, _ in ds["triggered_rules"])
        md += ["", "### Decision Rules"]
        for key, value in ds["decision_rules"]:
            mark = " **(applies)**" if key in triggered or key == "must_have" else ""
            md.append("- `{}` -> {}{}".format(key, value, mark))

    md += ["", "### Pre-Delivery Checklist"]
    md += ["- [ ] {}".format(item) for item in PRE_DELIVERY_CHECKLIST]
    return "\n".join(md)


# ============ PERSISTENCE ============
def format_master_md(ds):
    """MASTER.md: global source of truth for the project."""
    c, t = ds["colors"], ds["typography"]
    lines = [
        "# {} - Design System (MASTER)".format(ds["project_name"]),
        "",
        "> Global Source of Truth. When building a page, first check `design-system/pages/<page>.md`;",
        "> if it exists its rules override this file, otherwise use these rules exclusively.",
        "",
        "- **Generated:** {}".format(date.today().isoformat()),
        "- **Query:** `{}`".format(ds["query"]),
        "",
        format_markdown(ds),
        "",
        "### CSS Variables",
        "",
        "```css",
        ":root {",
    ]
    for key in ("primary", "secondary", "cta", "background", "text", "border"):
        if c[key]:
            lines.append("  --color-{}: {};".format(key, c[key]))
    if t["heading"]:
        lines.append("  --font-heading: '{}', sans-serif;".format(t["heading"]))
    if t["body"]:
        lines.append("  --font-body: '{}', sans-serif;".format(t["body"]))
    lines += ["}", "```"]
    if t["tailwind_config"]:
        lines += ["", "### Tailwind Fonts", "", "```js", t["tailwind_config"], "```"]
    return "\n".join(lines) + "\n"


def format_page_md(ds, page):
    """pages/<page>.md: page-specific overrides on top of MASTER.md."""
    landing = _first(search(page, "landing", 1))
    ux = search(page, "ux", 3).get("results", [])
    is_dashboard = bool(_words(page) & {"dashboard", "admin", "analytics", "report", "reports", "metrics"})

    lines = [
        "# {} Page - Overrides".format(page.title()),
        "",
        "> Project: {}. Inherits everything from `../MASTER.md`;".format(ds["project_name"]),
        "> rules in this file take priority for the {} page.".format(page),
        "",
        "- **Generated:** {}".format(date.today().isoformat()),
        "",
        "## Layout",
    ]
    if landing:
        lines += [
            "- **Suggested pattern:** {}".format(landing.get("Pattern Name", "")),
            "- **Sections:** {}".format(landing.get("Section Order", "")),
            "- **CTA Placement:** {}".format(landing.get("Primary CTA Placement", "")),
        ]
    else:
        lines.append("- Follow the MASTER pattern: {}".format(ds["pattern"]["name"]))
    if is_dashboard:
        if ds.get("dashboard_style"):
            lines.append("- **Dashboard style:** {}".format(ds["dashboard_style"]))
        charts = search("{} {}".format(page, ds["query"]), "chart", 2).get("results", [])
        for row in charts:
            lines.append("- **Chart ({}):** {} ({})".format(
                row.get("Data Type", ""), row.get("Best Chart Type", ""), row.get("Library Recommendation", "")))

    lines += ["", "## UX Guidelines"]
    if ux:
        for row in ux:
            lines.append("- **{} ({}):** Do: {} | Don't: {}".format(
                row.get("Issue", ""), row.get("Severity", ""), row.get("Do", ""), row.get("Don't", "")))
    else:
        lines.append("- No page-specific UX guidelines found; apply MASTER rules.")

    lines += ["", "## Overrides", "",
              "Add deviations from MASTER.md for this page here (colors, spacing, components).", ""]
    return "\n".join(lines)


def persist_design_system(ds, page=None, output_dir=None):
    """Write design-system/MASTER.md (+ pages/<page>.md) under output_dir (default: cwd)."""
    base = Path(output_dir) if output_dir else Path.cwd()
    root = base / "design-system"
    pages_dir = root / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    master = root / "MASTER.md"
    master.write_text(format_master_md(ds), encoding="utf-8")
    written = {"master": str(master), "pages_dir": str(pages_dir)}

    if page:
        page_file = pages_dir / "{}.md".format(_slugify(page))
        page_file.write_text(format_page_md(ds, page), encoding="utf-8")
        written["page"] = str(page_file)
    return written


# ============ ENTRY POINT ============
def generate_design_system(query, project_name=None, output_format="ascii",
                           persist=False, page=None, output_dir=None):
    """Generate, format and optionally persist a design system. Returns the formatted text."""
    ds = DesignSystemGenerator().generate(query, project_name)
    text = format_markdown(ds) if output_format == "markdown" else format_ascii_box(ds)

    if persist:
        written = persist_design_system(ds, page=page, output_dir=output_dir)
        notes = ["", "Design system saved:", "  - {}".format(written["master"])]
        if "page" in written:
            notes.append("  - {}".format(written["page"]))
        else:
            notes.append("  - {} (page overrides folder)".format(written["pages_dir"]))
        text += "\n" + "\n".join(notes)
    return text
