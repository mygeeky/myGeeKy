"""myGeeKy must print on a console that cannot draw emoji.

Windows consoles still default to a legacy code page in many locales, and myGeeKy's help and output are
full of emoji. `mygeeky --help` -- the first command anybody runs -- died with UnicodeEncodeError on a
single emoji in a docstring, before printing anything useful. Found by running the real command.
"""
from __future__ import annotations

import io

from mygeeky import cli


class LegacyConsole(io.TextIOWrapper):
    """A stdout like a cp1252 Windows console: it raises on anything outside its code page."""

    def __init__(self):
        super().__init__(io.BytesIO(), encoding="cp1252", errors="strict", newline="")
        self.reconfigured = None

    def reconfigure(self, **kw):           # record what the fix asks for, then really apply it
        self.reconfigured = kw
        super().reconfigure(**kw)


def test_a_legacy_console_is_made_printable(monkeypatch):
    out, err = LegacyConsole(), LegacyConsole()
    monkeypatch.setattr(cli.sys, "stdout", out)
    monkeypatch.setattr(cli.sys, "stderr", err)
    cli._printable()
    assert out.reconfigured == {"errors": "replace"}, out.reconfigured
    assert err.reconfigured == {"errors": "replace"}
    out.write("thanks \U0001f64f")          # the exact character that used to end the program
    out.flush()
    assert "?" in out.buffer.getvalue().decode("cp1252")
    assert out.encoding.lower() == "cp1252", "the console's own encoding must be kept, or output mojibakes"


def test_a_utf8_console_is_left_alone(monkeypatch):
    class Utf8(LegacyConsole):
        def __init__(self):
            io.TextIOWrapper.__init__(self, io.BytesIO(), encoding="utf-8", newline="")
            self.reconfigured = None

    out = Utf8()
    monkeypatch.setattr(cli.sys, "stdout", out)
    monkeypatch.setattr(cli.sys, "stderr", out)
    cli._printable()
    assert out.reconfigured is None, "a console that can already draw emoji was changed anyway"


def test_something_that_is_not_a_console_at_all_is_survived(monkeypatch):
    class Odd:
        encoding = "cp1252"

        def reconfigure(self, **kw):
            raise AttributeError("not a real stream")

    monkeypatch.setattr(cli.sys, "stdout", Odd())
    monkeypatch.setattr(cli.sys, "stderr", None)
    cli._printable()                        # must not raise: piped, captured or embedded output


def test_the_help_text_really_does_contain_emoji():
    """If this ever stops being true the guard is still right, but the reason for it is worth keeping."""
    from click.testing import CliRunner
    said = CliRunner().invoke(cli.main, ["--help"]).output
    assert said, "no help text at all"
    assert any(ord(ch) > 0xFFFF for ch in said), "no astral characters in the help any more"
