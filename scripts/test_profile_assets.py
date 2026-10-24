"""Failure-retention tests. Synthetic fixtures here are never profile output."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from profile_assets import FILES, InvalidAsset, publish, theme_metrics, validate_svg, summary_from_assets, check_directory, style_card, FONT_STACK


def fixture(name, count="12"):
    if name.startswith("stats"):
        content = "<text>GitHub stats</text>" + "".join(
            f'<text data-testid="{field}">{count}</text>'
            for field in ("stars", "commits", "prs", "issues", "contribs")
        )
    elif name.startswith("top-langs"):
        content = '<text>Top languages</text><text data-testid="lang-name">Python 100%</text>'
    else:
        content = (
            "<text>Contributions calendar. Best streak 4. Average per day 1.</text>"
            "<text>Recent activity</text>"
            '<path fill="#9be9a8" filter="url(#brightness1)" d="M0,0 1,1"/>' * 101
        )
        content = '<foreignObject width="480" height="480">' + content + "</foreignObject>"
    card = name.startswith(("stats-", "top-langs-"))
    width = 445 if card else 480
    height = (195 if name.startswith("stats-") else 165) if card else 480
    if card:
        content = '<rect data-testid="card-bg" x="0.5" y="0.5" width="444" height="99%" fill="#fff"/>' + content
    result = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        + content + "</svg>"
    ).encode()
    return style_card(result, name) if card else result


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.stage = root / "stage"
        self.destination = root / "profile"
        self.stage.mkdir()
        self.destination.mkdir()
        for name in FILES:
            (self.stage / name).write_bytes(fixture(name, "13"))
            (self.destination / name).write_bytes(fixture(name, "12"))
        (self.destination / "summary.md").write_bytes(summary_from_assets(self.snapshot()))
        self.before = self.snapshot()

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.destination.iterdir()}

    def test_complete_batch_publishes_only_changed_files(self):
        changed = publish(self.stage, self.destination)
        self.assertEqual(changed, ["stats-dark.svg", "stats-light.svg", "summary.md"])
        self.assertEqual(
            self.snapshot(),
            {**{name: (self.stage / name).read_bytes() for name in FILES},
             "summary.md": summary_from_assets({name: (self.stage / name).read_bytes() for name in FILES})},
        )

    def test_no_change_preserves_file_timestamps(self):
        publish(self.stage, self.destination)
        before = {p.name: p.stat().st_mtime_ns for p in self.destination.iterdir()}
        self.assertEqual(publish(self.stage, self.destination), [])
        self.assertEqual(before, {p.name: p.stat().st_mtime_ns for p in self.destination.iterdir()})

    def test_missing_last_file_preserves_every_previous_asset(self):
        (self.stage / FILES[-1]).unlink()
        with self.assertRaises(InvalidAsset):
            publish(self.stage, self.destination)
        self.assertEqual(self.snapshot(), self.before)

    def test_malformed_last_file_preserves_every_previous_asset(self):
        (self.stage / FILES[-1]).write_text("<svg>truncated")
        with self.assertRaises(InvalidAsset):
            publish(self.stage, self.destination)
        self.assertEqual(self.snapshot(), self.before)

    def test_error_card_preserves_every_previous_asset(self):
        error_card = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="445" height="195">'
            "<text>Something went wrong! API rate limit exceeded.</text></svg>"
        )
        (self.stage / "stats-light.svg").write_text(error_card)
        with self.assertRaises(InvalidAsset):
            publish(self.stage, self.destination)
        self.assertEqual(self.snapshot(), self.before)

    def test_failed_install_rolls_back_first_replaced_file(self):
        import os
        replace = os.replace
        calls = []
        def fail_second(source, destination):
            calls.append(destination)
            if len(calls) == 2:
                raise OSError("simulated interrupted file replacement")
            return replace(source, destination)
        with mock.patch("profile_assets.os.replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                publish(self.stage, self.destination)
        self.assertEqual(self.snapshot(), self.before)


    def test_check_directory_accepts_windows_crlf_checkout(self):
        publish(self.stage, self.destination)
        summary = self.destination / "summary.md"
        summary.write_bytes(summary.read_bytes().replace(b"\n", b"\r\n"))
        check_directory(self.destination)

    def test_check_directory_rejects_changed_data_even_with_crlf(self):
        publish(self.stage, self.destination)
        summary = self.destination / "summary.md"
        summary.write_bytes(summary.read_bytes().replace(b"**13**", b"**999**").replace(b"\n", b"\r\n"))
        with self.assertRaises(InvalidAsset):
            check_directory(self.destination)


class ValidationTests(unittest.TestCase):
    def test_metrics_error_is_rejected_even_with_other_valid_sections(self):
        content = fixture("metrics-dark.svg").replace(
            b"</foreignObject>", b'<div class="field error">API error</div></foreignObject>'
        )
        with self.assertRaises(InvalidAsset):
            validate_svg(content, "metrics-dark.svg")

    def test_external_image_is_rejected(self):
        content = fixture("stats-dark.svg").replace(
            b"</svg>", b'<image href="https://example.com/tracker.svg"/></svg>'
        )
        with self.assertRaises(InvalidAsset):
            validate_svg(content, "stats-dark.svg")

    def test_unmeasured_renderer_canvas_is_rejected(self):
        content = fixture("metrics-dark.svg").replace(b'height="480"', b'height="99999"', 1)
        with self.assertRaises(InvalidAsset):
            validate_svg(content, "metrics-dark.svg")

    def test_metric_themes_preserve_data_and_add_accessible_description(self):
        raw = fixture("metrics-dark.svg")
        dark = theme_metrics(raw, "dark")
        light = theme_metrics(raw, "light")
        validate_svg(dark, "metrics-dark.svg")
        validate_svg(light, "metrics-light.svg")
        self.assertIn(b"#5c328c", dark)
        self.assertIn(b"#c9a4ed", light)
        self.assertIn(b"Best streak 4. Average per day 1.", dark)
        self.assertIn(b"Best streak 4. Average per day 1.", light)
        self.assertIn(b"aria-labelledby", dark)
        self.assertNotEqual(dark, light)
        self.assertIn(b"background: transparent !important", dark)
        self.assertIn(b"background: transparent !important", light)


    def test_summary_has_real_card_values_and_no_style_content(self):
        data = {name: fixture(name, "37") for name in FILES}
        summary = summary_from_assets(data).decode()
        self.assertIn("**37**", summary)
        self.assertIn("Python 100%", summary)
        self.assertIn("Best streak 4", summary)
        self.assertNotIn("<svg", summary)
        self.assertNotIn("brightness1", summary)

    def test_summary_escapes_untrusted_activity_markdown(self):
        data = {name: fixture(name) for name in FILES}
        data["metrics-dark.svg"] = data["metrics-dark.svg"].replace(
            b"</foreignObject>",
            b'<section class="activity">Pushed [link](https://example.com) &lt;img&gt;</section></foreignObject>'
        )
        summary = summary_from_assets(data).decode()
        self.assertIn(r"\[link\]", summary)
        self.assertIn(r"\&lt;img\&gt;".replace("&lt;", "<").replace("&gt;", ">"), summary)



    def test_native_activity_accepts_reduced_public_records_and_preserves_calendar(self):
        raw = fixture("metrics-dark.svg").replace(b"<text>Recent activity</text>", b"")
        records = [{"date": "2026-10-23", "text": "Opened pull request #8 in WizardLoop/example", "url": "https://github.com/WizardLoop/example/pull/8"}]
        result = theme_metrics(raw, "dark", records)
        validate_svg(result, "metrics-dark.svg")
        self.assertIn(b"Opened pull request #8", result)
        self.assertIn(b"Recent activity", result)
        self.assertIn(b"Best streak 4", result)
        self.assertGreater(int(__import__("xml.etree.ElementTree", fromlist=["fromstring"]).fromstring(result).get("height")), 480)

    def test_malformed_public_activity_cannot_be_published(self):
        raw = fixture("metrics-dark.svg")
        records = [{"date": "2026-10-23", "text": "event", "url": "javascript:alert(1)"}]
        with self.assertRaises(InvalidAsset):
            theme_metrics(raw, "dark", records)



    def test_summary_links_public_activity_to_github(self):
        records = [{"date": "2026-10-23", "text": "Opened pull request #8 in WizardLoop/example", "url": "https://github.com/WizardLoop/example/pull/8"}]
        data = {name: fixture(name) for name in FILES}
        data["metrics-dark.svg"] = theme_metrics(fixture("metrics-dark.svg"), "dark", records)
        summary = summary_from_assets(data).decode()
        self.assertIn("](https://github.com/WizardLoop/example/pull/8)", summary)
        self.assertIn(r"Opened pull request \#8", summary)



    def test_activity_uses_mobile_readable_type_and_bounded_line_lengths(self):
        records = [{"date": "2026-10-23", "text": "Published a release (v3.1.1) in WizardLoop/very-long-public-repository-name", "url": "https://github.com/WizardLoop/very-long-public-repository-name/releases"}]
        result = theme_metrics(fixture("metrics-dark.svg"), "dark", records)
        root = __import__("xml.etree.ElementTree", fromlist=["fromstring"]).fromstring(result)
        activity = next(node for node in root.iter() if node.get("class") == "activity")
        text_nodes = list(activity)
        self.assertEqual(text_nodes[0].get("font-size"), "18")
        self.assertEqual(text_nodes[1].get("font-size"), "14")
        self.assertTrue(all(len(span.text or "") <= 40 for span in text_nodes[0]))
        self.assertGreater(len(list(text_nodes[0])), 1)



class CardStylingTests(unittest.TestCase):
    def test_repeated_styling_does_not_create_daily_commit_churn(self):
        for name in FILES[:4]:
            once = fixture(name)
            self.assertEqual(style_card(once, name), once)

    def test_stats_and_languages_share_height_without_changing_data(self):
        import xml.etree.ElementTree as ET
        stats = ET.fromstring(fixture("stats-dark.svg", "241"))
        languages = ET.fromstring(fixture("top-langs-dark.svg"))
        self.assertEqual(stats.get("height"), "195")
        self.assertEqual(languages.get("height"), "195")
        self.assertEqual(stats.get("viewBox"), languages.get("viewBox"))
        counts = [node.text for node in stats.iter() if node.get("data-testid") in ("stars", "commits", "prs", "issues", "contribs")]
        self.assertEqual(counts, ["241"] * 5)
        self.assertIn("Python 100%", " ".join(languages.itertext()))

    def test_standalone_svg_text_has_explicit_sans_serif_fallback(self):
        import xml.etree.ElementTree as ET
        for name in FILES:
            content = fixture(name)
            if name.startswith("metrics-"):
                content = theme_metrics(content, "dark")
            root = ET.fromstring(content)
            text = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] in {"text", "tspan"}]
            self.assertTrue(text)
            self.assertTrue(all(node.get("font-family") == FONT_STACK for node in text))
            self.assertIn(b"font-family:Arial, Helvetica, sans-serif !important", content.replace(b"font-family: Arial", b"font-family:Arial"))

    def test_error_response_is_rejected_before_styling(self):
        error = b'<svg xmlns="http://www.w3.org/2000/svg" width="445" height="195"><text>Something went wrong</text></svg>'
        with self.assertRaises(InvalidAsset):
            style_card(error, "stats-dark.svg")


if __name__ == "__main__":
    unittest.main()
