#!/usr/bin/env python3
"""Validate and publish a complete, self-contained set of profile SVGs.

No network calls, credentials, or third-party Python dependencies.
The repository is changed only after every staged SVG passes validation.
"""
from __future__ import annotations

import argparse
from html import escape
import json
import os
from pathlib import Path
import re
import tempfile
import textwrap
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
FILES = (
    "stats-dark.svg", "stats-light.svg",
    "top-langs-dark.svg", "top-langs-light.svg",
    "metrics-dark.svg", "metrics-light.svg",
)
FONT_STACK = "Arial, Helvetica, sans-serif"
PALETTES = {
    "dark": {
        "background": "#1b1033", "text": "#f4edff", "muted": "#b8a3d5",
        "accent": "#c9a3ff", "icon": "#b49aff", "border": "#493064",
        "gradient_start": "#281343", "gradient_end": "#130a24",
        "levels": ("#2a1b40", "#5c328c", "#8b4bce", "#b177ee", "#d8b4ff"),
    },
    "light": {
        "background": "#f5efff", "text": "#2f174b", "muted": "#70598d",
        "accent": "#713cc0", "icon": "#8952ce", "border": "#d7c3ef",
        "gradient_start": "#f9f4ff", "gradient_end": "#eee0ff",
        "levels": ("#e5d7f5", "#c9a4ed", "#a476db", "#8451bf", "#64309e"),
    },
}
GITHUB_CALENDAR_COLORS = (
    ("#ebedf0", "#161b22"),
    ("#9be9a8", "#0e4429", "#ffee4a", "#0a3069"),
    ("#40c463", "#006d32", "#ffc501", "#0969da"),
    ("#30a14e", "#26a641", "#fe9600", "#54aeff"),
    ("#216e39", "#39d353", "#03001c", "#b6e3ff"),
)


class InvalidAsset(ValueError):
    """A missing, incomplete, erroneous, or externally dependent SVG."""


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def visible_text(element: ET.Element) -> str:
    if local_name(element.tag) in {"style", "script", "defs"}:
        return ""
    parts = [element.text or ""]
    for child in element:
        parts.extend((visible_text(child), child.tail or ""))
    return " ".join(" ".join(parts).split())


def validate_svg(content: bytes, filename: str) -> ET.Element:
    if not content or len(content) > 2_000_000:
        raise InvalidAsset(f"{filename}: empty or unexpectedly large file")
    text = content.decode("utf-8")
    if re.search(r"<!DOCTYPE|<!ENTITY", text, re.I):
        raise InvalidAsset(f"{filename}: XML entities are not allowed")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        raise InvalidAsset(f"{filename}: malformed SVG") from error
    if root.tag != f"{{{SVG_NS}}}svg":
        raise InvalidAsset(f"{filename}: document root is not an SVG")
    for name, maximum in (("width", 2048), ("height", 4096)):
        value = root.get(name, "")
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?(?:px)?", value):
            raise InvalidAsset(f"{filename}: missing numeric {name}")
        if not 20 <= float(value.removesuffix("px")) <= maximum:
            raise InvalidAsset(f"{filename}: invalid rendered {name}")
    for element in root.iter():
        tag = local_name(element.tag)
        if tag in {"script", "iframe", "object", "embed"}:
            raise InvalidAsset(f"{filename}: executable element")
        if {"error", "warning"} & set(element.get("class", "").split()):
            raise InvalidAsset(f"{filename}: renderer reported an error or warning")
        for key, value in element.attrib.items():
            attr = local_name(key).lower()
            if attr.startswith("on"):
                raise InvalidAsset(f"{filename}: executable event handler")
            if tag in {"image", "img", "use"} and attr in {"src", "href"}:
                if not value.startswith(("#", "data:image/")):
                    raise InvalidAsset(f"{filename}: externally loaded image")
        if tag == "style":
            css = element.text or ""
            if re.search(r"@import", css, re.I):
                raise InvalidAsset(f"{filename}: external stylesheet")
            for target in re.findall(r"url\(\s*['\"]?([^)'\"]+)", css, re.I):
                if not target.startswith(("#", "data:")):
                    raise InvalidAsset(f"{filename}: external CSS resource")
    labels = visible_text(root).lower()
    if filename.startswith("stats"):
        if "github stats" not in labels:
            raise InvalidAsset(f"{filename}: missing statistics title")
        fields = {node.get("data-testid"): visible_text(node) for node in root.iter()}
        for field in ("stars", "commits", "prs", "issues", "contribs"):
            if not re.fullmatch(r"[0-9][0-9,.]*(?:[kmb])?", fields.get(field, ""), re.I):
                raise InvalidAsset(f"{filename}: missing or invalid {field} count")
    elif filename.startswith("top-langs"):
        if "top languages" not in labels:
            raise InvalidAsset(f"{filename}: missing languages title")
        languages = [
            visible_text(node) for node in root.iter()
            if node.get("data-testid") == "lang-name"
        ]
        if not languages or not all(re.search(r"\d+(?:\.\d+)?%", item) for item in languages):
            raise InvalidAsset(f"{filename}: missing measured language percentages")
    elif filename.startswith("metrics"):
        if "contributions calendar" not in labels or (filename != "metrics-raw.svg" and "recent activity" not in labels):
            raise InvalidAsset(f"{filename}: missing calendar or activity section")
        if "best streak" not in labels or "average per day" not in labels:
            raise InvalidAsset(f"{filename}: missing calendar statistics")
        faces = [
            node for node in root.iter()
            if local_name(node.tag) == "path" and node.get("filter", "").startswith("url(#brightness")
        ]
        if len(faces) < 100:
            raise InvalidAsset(f"{filename}: incomplete isometric calendar")
    else:
        raise InvalidAsset(f"Unexpected asset: {filename}")
    return root




def set_svg_attribute(tag: str, name: str, value: str) -> str:
    """Change one quoted SVG attribute without reserializing numeric geometry."""
    attribute = re.compile(r"\b" + re.escape(name) + r"\s*=\s*([\"']).*?\1", re.S)
    rendered = f'{name}="{escape(value, quote=True)}"'
    if attribute.search(tag):
        return attribute.sub(lambda _: rendered, tag, count=1)
    position = -2 if tag.endswith('/>') else -1
    return tag[:position] + " " + rendered + tag[position:]


def explicit_sans(text: str) -> str:
    # Presentation attributes also cover standalone renderers that ignore CSS
    # font shorthands; the final stylesheet covers browsers' CSS cascade.
    return re.sub(
        r"<(?:text|tspan)\b[^>]*>",
        lambda match: set_svg_attribute(match.group(), "font-family", FONT_STACK),
        text,
    )


def style_card(content: bytes, filename: str) -> bytes:
    """Theme an upstream card, preserving every value and chart coordinate."""
    root = validate_svg(content, filename)
    if not filename.startswith(("stats-", "top-langs-")):
        raise InvalidAsset(f"{filename}: expected a stats or language card")
    theme = "dark" if filename.endswith("-dark.svg") else "light"
    palette = PALETTES[theme]
    text = content.decode("utf-8").strip()
    # Reapplying the design is byte-for-byte stable.
    text = re.sub(r'<defs id="amethyst-card-background">.*?</defs>', '', text, flags=re.S)
    text = re.sub(r'<style id="amethyst-card-type">.*?</style>', '', text, flags=re.S)
    width = float(root.get("width", "").removesuffix("px"))
    height = max(195, float(root.get("height", "").removesuffix("px")))
    def root_attributes(match: re.Match) -> str:
        tag = set_svg_attribute(match.group(), "height", f"{height:g}")
        tag = set_svg_attribute(tag, "viewBox", f"0 0 {width:g} {height:g}")
        return set_svg_attribute(tag, "font-family", FONT_STACK)
    text = re.sub(r"<svg\b[^>]*>", root_attributes, text, count=1)
    def background(match: re.Match) -> str:
        tag = set_svg_attribute(match.group(), "fill", "url(#amethyst-card-gradient)")
        tag = set_svg_attribute(tag, "stroke", palette["border"])
        return set_svg_attribute(tag, "rx", "18")
    text, count = re.subn(r'<rect\b[^>]*data-testid=["\']card-bg["\'][^>]*/?>', background, text, count=1)
    if count != 1:
        raise InvalidAsset(f"{filename}: missing upstream card background")
    text = explicit_sans(text)
    defs = (
        '<defs id="amethyst-card-background">'
        '<linearGradient id="amethyst-card-gradient" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{palette["gradient_start"]}"/>'
        f'<stop offset="100%" stop-color="{palette["gradient_end"]}"/>'
        '</linearGradient></defs>'
    )
    css = (
        '<style id="amethyst-card-type">'
        f'text,tspan{{font-family:{FONT_STACK} !important;}}'
        f'.header{{font-size:18px; font-weight:700; fill:{palette["accent"]};}}'
        f'.stat{{font-size:14px; fill:{palette["text"]};}}'
        f'.lang-name{{font-size:14px; fill:{palette["text"]};}}'
        f'.icon{{fill:{palette["icon"]};}}'
        '</style>'
    )
    text = text.rsplit('</svg>', 1)[0] + defs + css + '</svg>\n'
    result = text.encode('utf-8')
    validate_svg(result, filename)
    return result


def append_activity(text: str, theme: str, activities: list[dict]) -> str:
    """Append a native-SVG feed; no brittle upstream activity payload assumptions."""
    if not isinstance(activities, list) or len(activities) > 3:
        raise InvalidAsset("Activity snapshot must contain zero to three public events")
    root = ET.fromstring(text)
    old_height = float(root.get("height", "").removesuffix("px"))
    palette = PALETTES[theme]
    top = old_height + 4
    y = top + 60
    rows = []
    for event in activities:
        if not isinstance(event, dict) or not all(isinstance(event.get(k), str) for k in ("date", "text", "url")):
            raise InvalidAsset("Malformed public activity record")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", event["date"]):
            raise InvalidAsset("Invalid public activity date")
        if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+", event["url"]):
            raise InvalidAsset("Invalid public activity link")
        wrapped = textwrap.wrap(event["text"], width=40) or [""]
        if len(wrapped) > 5:
            raise InvalidAsset("Unexpectedly long public activity title")
        spans = "".join(
            f'<tspan x="26" dy="{0 if index == 0 else 24}">{escape(line)}</tspan>'
            for index, line in enumerate(wrapped)
        )
        row = (
            f'<g class="activity" data-url="{escape(event["url"], quote=True)}">'
            f'<text x="26" y="{y}" font-size="18" fill="{palette["text"]}">{spans}</text>'
            f'<text x="26" y="{y + (len(wrapped) - 1) * 24 + 23}" font-size="14" fill="{palette["muted"]}">{event["date"]}</text>'
            '</g>'
        )
        rows.append(row)
        y += len(wrapped) * 24 + 40
    if not activities:
        rows.append(
            f'<text x="26" y="{y}" font-size="14" fill="{palette["muted"]}">'
            'No qualifying public events in the last 90 days.</text>'
        )
        y += 32
    box_height = y - top + 4
    group = (
        f'<g id="loop-lab-public-activity">'
        f'<rect x="0.5" y="{top}" width="479" height="{box_height}" rx="18" '
        f'fill="url(#amethyst-metrics-gradient)" stroke="{palette["border"]}"/>'
        f'<text x="26" y="{top + 30}" font-size="18" font-weight="700" fill="{palette["accent"]}">'
        'Recent activity</text>'
        + "".join(rows) + '</g>'
    )
    height = int(top + box_height + 1)
    text = re.sub(
        r"<svg\b([^>]*)>",
        lambda match: "<svg" + re.sub(r'height="[^"]*"', f'height="{height}"', match.group(1), count=1) + ">",
        text, count=1,
    )
    return text.rsplit("</svg>", 1)[0] + group + "</svg>"


def theme_metrics(raw: bytes, theme: str, activities: list[dict] | None = None) -> bytes:
    validate_svg(raw, "metrics-raw.svg")
    palette = PALETTES[theme]
    text = raw.decode("utf-8").strip()
    color_map = {
        original: palette["levels"][level]
        for level, colors in enumerate(GITHUB_CALENDAR_COLORS)
        for original in colors
    }
    # Only calendar face fills are recolored; counts and geometry are untouched.
    def recolor(match: re.Match) -> str:
        prefix, color, suffix = match.groups()
        return prefix + color_map.get(color.lower(), color) + suffix
    text = re.sub(r'(fill=["\'])(#[0-9a-fA-F]{6})(["\'])', recolor, text)
    css = f"""
      :root {{ background: transparent !important; color: {palette['text']}; }}
      .items-wrapper {{ font-size: 16px; background: {palette['background']}; background: linear-gradient(135deg, {palette['gradient_start']}, {palette['gradient_end']}); border-color: {palette['border']}; color: {palette['text']}; }}
      svg {{ color: {palette['text']}; }}
      svg, text, tspan, .items-wrapper, .items-wrapper * {{ font-family: {FONT_STACK} !important; }}
      h1, h2, h3 {{ color: {palette['accent']} !important; }}
      h2 {{ font-size: 18px; font-weight: 700; }}
      h3 {{ font-size: 14px; }}
      .field svg {{ fill: {palette['icon']}; }}
      .activity .repo, .activity .issue, .activity .commit .sha {{ color: {palette['icon']}; }}
      .activity .details, .activity .timestamp, .activity .code {{ color: {palette['muted']}; }}
      .activity .code {{ background: {palette['border']}; }}
    """
    insertion = (
        '<title id="loop-lab-metrics-title">WizardLoop contribution calendar and recent public activity</title>'
        '<desc id="loop-lab-metrics-description">A full-year isometric contribution calendar, streak statistics, '
        'and up to three recent public GitHub events. Generated from GitHub API data and lowlighter metrics.</desc>'
        f'<style id="loop-lab-palette">{css}</style>'
        '<defs><linearGradient id="amethyst-metrics-gradient" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{palette["gradient_start"]}"/>'
        f'<stop offset="100%" stop-color="{palette["gradient_end"]}"/>'
        '</linearGradient></defs>'
    )
    text = re.sub(
        r"<svg\b([^>]*)>",
        lambda match: '<svg' + match.group(1)
        + ' role="img" aria-labelledby="loop-lab-metrics-title loop-lab-metrics-description">',
        text, count=1,
    )
    # Place the palette after the generator's styles so it takes precedence.
    point = text.index("<foreignObject")
    text = text[:point] + insertion + text[point:]
    if activities is not None:
        text = append_activity(text, theme, activities)
    text = explicit_sans(text)
    return (text + "\n").encode("utf-8")


def prepare_metrics(raw_path: Path, stage: Path, activity_path: Path) -> None:
    raw = raw_path.read_bytes()
    activities = json.loads(activity_path.read_text(encoding='utf-8'))
    candidates = {
        f"metrics-{theme}.svg": theme_metrics(raw, theme, activities)
        for theme in PALETTES
    }
    for name, content in candidates.items():
        validate_svg(content, name)
    stage.mkdir(parents=True, exist_ok=True)
    for name, content in candidates.items():
        (stage / name).write_bytes(content)



def markdown_text(value: str) -> str:
    """Keep public event text inert inside a Markdown list item."""
    return re.sub(r"([\\\x60*_{}\[\]<>#|])", r"\\\1", value)


def summary_from_assets(candidates: dict[str, bytes]) -> bytes:
    """Derive an accessible text companion from the exact published SVG data."""
    stats = validate_svg(candidates["stats-dark.svg"], "stats-dark.svg")
    languages = validate_svg(candidates["top-langs-dark.svg"], "top-langs-dark.svg")
    metrics = validate_svg(candidates["metrics-dark.svg"], "metrics-dark.svg")
    lines = [
        "# GitHub activity, in text", "",
        "This text is generated from the same validated GitHub data as the profile cards.",
        "Figures update with the cards; an unsuccessful refresh keeps the previous complete set.", "",
        "## GitHub stats", "",
    ]
    parents = {child: parent for parent in stats.iter() for child in parent}
    fields = ("stars", "commits", "prs", "issues", "contribs")
    fallback_labels = {
        "stars": "Total stars earned", "commits": "Commits",
        "prs": "Pull requests", "issues": "Issues",
        "contribs": "Repositories contributed to",
    }
    for field in fields:
        node = next(node for node in stats.iter() if node.get("data-testid") == field)
        siblings = [
            visible_text(sibling).rstrip(": ")
            for sibling in parents.get(node, ())
            if local_name(sibling.tag) == "text" and sibling is not node
        ]
        label = siblings[0] if siblings else fallback_labels[field]
        lines.append(f"- {markdown_text(label)}: **{markdown_text(visible_text(node))}**")
    lines.extend(["", "## Top languages", ""])
    for node in languages.iter():
        if node.get("data-testid") == "lang-name":
            lines.append(f"- {markdown_text(visible_text(node))}")
    lines.extend([
        "",
        "Language percentages describe analyzed repository content, not proficiency or coding time.",
        "", "## Contribution calendar", "",
        "The isometric view covers the last year of GitHub contributions. These totals may include "
        "private contribution aggregates visible to the existing metrics token; private project names are not shown.",
        "",
    ])
    wanted = ("Current streak", "Best streak", "Highest in a day at", "Average per day at")
    facts = []
    for node in metrics.iter():
        if "field" not in node.get("class", "").split():
            continue
        value = visible_text(node)
        if value.startswith(wanted):
            facts.append(value)
    if not facts:
        # The validator permits plain SVG text as well as lowlighter's XHTML.
        for node in metrics.iter():
            if local_name(node.tag) == "text":
                value = visible_text(node)
                if "Best streak" in value:
                    facts.append(value)
    lines.extend("- " + markdown_text(value) for value in facts)
    lines.extend([
        "",
        "GitHub contribution counts can include commits, issues, pull requests, and reviews.",
        "", "## Recent public activity", "",
    ])
    events = [
        node for node in metrics.iter()
        if local_name(node.tag) in {"section", "g"} and "activity" in node.get("class", "").split()
    ]
    if events:
        for event in events:
            label = markdown_text(visible_text(event))
            url = event.get("data-url", "")
            if re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+", url):
                lines.append(f"- [{label}]({url})")
            else:
                lines.append("- " + label)
    else:
        lines.append("No qualifying recent public activity was returned.")
    lines.extend([
        "",
        "The activity feed includes at most three public events from the past 90 days.",
        "Profile-repository updates and common automation bots are excluded.",
        "",
        "",
    ])
    return "\n".join(lines).encode("utf-8")


def publish(stage: Path, destination: Path) -> list[str]:
    # Read and validate the entire batch before touching any published file.
    candidates: dict[str, bytes] = {}
    for name in FILES:
        source = stage / name
        if not source.is_file() or source.is_symlink():
            raise InvalidAsset(f"{name}: missing regular staged file")
        content = source.read_bytes()
        if name.startswith(("stats-", "top-langs-")):
            content = style_card(content, name)
        validate_svg(content, name)
        candidates[name] = content
    candidates['summary.md'] = summary_from_assets(candidates)
    previous = {
        name: (destination / name).read_bytes() if (destination / name).is_file() else None
        for name in candidates
    }
    changed = [name for name in candidates if candidates[name] != previous[name]]
    if not changed:
        return []
    destination.mkdir(parents=True, exist_ok=True)
    # Temporary files are on the destination filesystem for atomic os.replace.
    with tempfile.TemporaryDirectory(prefix=".profile-publish-", dir=destination.parent) as temp:
        temp_path = Path(temp)
        for name in changed:
            (temp_path / name).write_bytes(candidates[name])
        installed: list[str] = []
        try:
            for name in changed:
                os.replace(temp_path / name, destination / name)
                installed.append(name)
        except OSError:
            for name in reversed(installed):
                target = destination / name
                if previous[name] is None:
                    target.unlink(missing_ok=True)
                else:
                    target.write_bytes(previous[name])
            raise
    return changed



def check_directory(directory: Path) -> None:
    """Validate checked-out outputs, accepting platform newline conversion."""
    assets = {name: (directory / name).read_bytes() for name in FILES}
    for name, content in assets.items():
        validate_svg(content, name)
    expected = summary_from_assets(assets).decode("utf-8")
    # Git may check text files out as CRLF on Windows. read_text normalizes EOLs
    # without relaxing the requirement that the actual summary data must match.
    if (directory / "summary.md").read_text(encoding="utf-8") != expected:
        raise InvalidAsset("summary.md does not match the published SVG data")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare-metrics")
    prepare.add_argument("--raw", required=True, type=Path)
    prepare.add_argument("--stage", required=True, type=Path)
    prepare.add_argument("--activity", required=True, type=Path)
    update = sub.add_parser("publish")
    update.add_argument("--stage", required=True, type=Path)
    update.add_argument("--destination", required=True, type=Path)
    check = sub.add_parser("check")
    check.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "prepare-metrics":
        prepare_metrics(args.raw, args.stage, args.activity)
        print("Prepared dark and light metrics from one GitHub snapshot.")
    elif args.command == "publish":
        changed = publish(args.stage, args.destination)
        print("Updated: " + ", ".join(changed) if changed else "No SVG content changed.")
    else:
        check_directory(args.directory)
        print("All six local SVGs and their text summary passed validation.")


if __name__ == "__main__":
    main()
