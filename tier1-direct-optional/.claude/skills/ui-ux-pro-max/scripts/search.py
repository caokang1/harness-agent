#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI/UX Pro Max Search - BM25 search CLI for UI/UX style guides

Usage:
  python3 search.py "<query>" --design-system [-p "Project Name"] [-f ascii|markdown] [--persist] [--page name]
  python3 search.py "<query>" --domain <domain> [-n N]
  python3 search.py "<query>" --stack <stack>

Domains: product, style, typography, color, landing, chart, ux, react, web, prompt, icons
Stacks:  html-tailwind (default), react, nextjs, vue, nuxtjs, nuxt-ui, svelte, swiftui,
         react-native, flutter, shadcn, jetpack-compose
"""

import argparse
import json
import sys

from core import AVAILABLE_STACKS, CSV_CONFIG, MAX_RESULTS, search, search_stack
from design_system import generate_design_system


def _setup_utf8_output():
    """Avoid UnicodeEncodeError on Windows consoles (emoji/CJK in the CSV data)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def format_output(result):
    """Format a domain/stack search result as Markdown for AI consumption."""
    if "error" in result:
        return "Error: {}".format(result["error"])

    out = []
    if result.get("stack"):
        out.append("## UI Pro Max Stack Guidelines")
        out.append("**Stack:** {} | **Query:** {}".format(result["stack"], result["query"]))
    else:
        out.append("## UI Pro Max Search Results")
        out.append("**Domain:** {} | **Query:** {}".format(result["domain"], result["query"]))
    out.append("**Source:** {} | **Found:** {} results\n".format(result["file"], result["count"]))

    if not result["results"]:
        out.append("No matches. Try different or broader keywords.")

    for i, row in enumerate(result["results"], 1):
        out.append("### Result {}".format(i))
        for key, value in row.items():
            value_str = str(value)
            if len(value_str) > 300:
                value_str = value_str[:300] + "..."
            out.append("- **{}:** {}".format(key, value_str))
        out.append("")
    return "\n".join(out)


def _choice(kind, available):
    """argparse type that rejects unknown values with the list of valid ones."""
    def check(value):
        value = value.strip().lower()
        if value not in available:
            raise argparse.ArgumentTypeError(
                "unknown {} '{}'. Available: {}".format(kind, value, ", ".join(available)))
        return value
    return check


def build_parser():
    parser = argparse.ArgumentParser(
        description="UI/UX Pro Max search: design systems, domain search and stack guidelines.")
    parser.add_argument("query", help="Search query, e.g. \"beauty spa wellness service\"")
    parser.add_argument("--domain", "-d", type=_choice("domain", list(CSV_CONFIG)),
                        help="Search domain (auto-detected if omitted): " + ", ".join(CSV_CONFIG))
    parser.add_argument("--stack", "-s", type=_choice("stack", AVAILABLE_STACKS),
                        help="Stack guidelines: " + ", ".join(AVAILABLE_STACKS))
    parser.add_argument("--max-results", "-n", type=int, default=MAX_RESULTS,
                        help="Max results (default: {})".format(MAX_RESULTS))
    parser.add_argument("--json", action="store_true", help="Output raw JSON (domain/stack search)")
    parser.add_argument("--design-system", "-ds", action="store_true",
                        help="Generate a complete design system recommendation")
    parser.add_argument("--project-name", "-p", default=None, help="Project name for the design system")
    parser.add_argument("--format", "-f", choices=["ascii", "markdown"], default="ascii",
                        help="Design system output format (default: ascii)")
    parser.add_argument("--persist", action="store_true",
                        help="Save design-system/MASTER.md (relative to the current directory)")
    parser.add_argument("--page", default=None,
                        help="With --persist: also create design-system/pages/<page>.md")
    parser.add_argument("--output-dir", "-o", default=None,
                        help="With --persist: base directory instead of the current directory")
    return parser


def main(argv=None):
    _setup_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.query.strip():
        parser.error("query must not be empty")
    if args.max_results < 1:
        parser.error("--max-results must be >= 1")
    if args.design_system and (args.domain or args.stack):
        parser.error("--design-system cannot be combined with --domain or --stack")
    if args.domain and args.stack:
        parser.error("use either --domain or --stack, not both")
    if (args.persist or args.page) and not args.design_system:
        parser.error("--persist/--page require --design-system")
    if args.page and not args.persist:
        parser.error("--page requires --persist")

    if args.design_system:
        print(generate_design_system(args.query, args.project_name, args.format,
                                     persist=args.persist, page=args.page, output_dir=args.output_dir))
        return 0

    if args.stack:
        result = search_stack(args.query, args.stack, args.max_results)
    else:
        result = search(args.query, args.domain, args.max_results)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_output(result))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    sys.exit(main())
