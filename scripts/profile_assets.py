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
PALETTES = {
    "dark": {
        "background": "#0d1117", "text": "#eeeffa", "muted": "#a7a4bb",
        "accent": "#b899ff", "mint": "#9cd9c6", "border": "#302b43",
        "levels": ("#201d2b", "#44315f", "#70509c", "#9673cd", "#b899ff"),
    },
    "light": {
        "background": "#ffffff", "text": "#242133", "muted": "#615b72",
        "accent": "#7145ad", "mint": "#327b68", "border": "#e4ddee",
        "levels": ("#eee9f5", "#dccaf4", "#bd9de5", "#9870cd", "#7145ad"),
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
        wrapped = textwrap.wrap(event["text"], width=58) or [""]
        if len(wrapped) > 5:
            raise InvalidAsset("Unexpectedly long public activity title")
        spans = "".join(
            f'<tspan x="26" dy="{0 if index == 0 else 19}">{escape(line)}</tspan>'
            for index, line in enumerate(wrapped)
        )
        row = (
            f'<g class="activity" data-url="{escape(event["url"], quote=True)}">'
            f'<text x="26" y="{y}" font-size="12.5" fill="{palette["text"]}">{spans}</text>'
            f'<text x="26" y="{y + (len(wrapped) - 1) * 19 + 19}" font-size="10.5" fill="{palette["muted"]}">{event["date"]}</text>'
            '</g>'
        )
        rows.append(row)
        y += len(wrapped) * 19 + 35
    if not activities:
        rows.append(
            f'<text x="26" y="{y}" font-size="12" fill="{palette["muted"]}">'
            'No qualifying public events in the last 90 days.</text>'
        )
        y += 32
    box_height = y - top + 4
    group = (
        f'<g id="loop-lab-public-activity">'
        f'<rect x="0.5" y="{top}" width="479" height="{box_height}" rx="16" '
        f'fill="{palette["background"]}" stroke="{palette["border"]}"/>'
        f'<text x="26" y="{top + 30}" font-size="16" font-weight="600" fill="{palette["accent"]}">'
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
      :root {{ background: {palette['background']}; color: {palette['text']}; }}
      .items-wrapper {{ background: {palette['background']}; border-color: {palette['border']}; color: {palette['text']}; }}
      svg {{ color: {palette['text']}; }}
      h1, h2, h3 {{ color: {palette['accent']} !important; }}
      .field svg {{ fill: {palette['accent']}; }}
      .activity .repo, .activity .issue, .activity .commit .sha {{ color: {palette['mint']}; }}
      .activity .details, .activity .timestamp, .activity .code {{ color: {palette['muted']}; }}
      .activity .code {{ background: {palette['border']}; }}
    """
    insertion = (
        '<title id="loop-lab-metrics-title">WizardLoop contribution calendar and recent public activity</title>'
        '<desc id="loop-lab-metrics-description">A full-year isometric contribution calendar, streak statistics, '
        'and up to three recent public GitHub events. Generated from GitHub API data and lowlighter metrics.</desc>'
        f'<style id="loop-lab-palette">{css}</style>'
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
            if re.fullmatch(r"https://github\\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+", url):
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
        "Sources: [GitHub Readme Stats](https://github.com/stats-organization/github-readme-stats-action) "
        "and [lowlighter/metrics](https://github.com/lowlighter/metrics).",
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
        for name in FILES:
            validate_svg((args.directory / name).read_bytes(), name)
        expected = summary_from_assets({name: (args.directory / name).read_bytes() for name in FILES})
        if (args.directory / "summary.md").read_bytes() != expected:
            raise InvalidAsset("summary.md does not match the published SVG data")
        print("All six local SVGs and their text summary passed validation.")


if __name__ == "__main__":
    main()
