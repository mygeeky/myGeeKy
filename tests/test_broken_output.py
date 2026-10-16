"""Nothing reading myGeeKy's output is normal, not a crash.

`mygeeky interests | head` closes the pipe as soon as head has its lines, and the panel stops reading
when the view that asked for a command is closed. POSIX reports that write as BrokenPipeError, which
reads as what it is. Windows reports it as a plain OSError with errno 22, "Invalid argument", which
does not -- so it was written up as a crash report and shown to the person as "myGeeKy hit a problem:
Invalid argument". That is issue #6: three reports, none of them a fault.

The subprocess test below is the original reproduction, kept as a test: it closes the read end and
then writes, which is the only way to get the real errno rather than a hand-made one.
"""
from __future__ import annotations

import errno
import io
import os
import subprocess
import sys
from pathlib import Path

from mygeeky import cli


# --------------------------------------------------------------------------- what counts as "gone"
def _raised_in(name, exc):
    """Give `exc` a traceback whose innermost frame is a function called `name`."""
    def echo():
        raise exc

    def write():
        raise exc

    def unrelated():
        raise exc

    try:
        {"echo": echo, "write": write, "unrelated": unrelated}[name]()
    except type(exc) as caught:
        return caught
    raise AssertionError("did not raise")


def test_a_broken_pipe_is_not_a_crash():
    assert cli._output_is_gone(_raised_in("write", BrokenPipeError(errno.EPIPE, "Broken pipe")))


def test_windows_errno_22_from_an_output_call_is_not_a_crash():
    """The actual shape of issue #6: OSError 22 out of click.echo's file.flush()."""
    exc = _raised_in("echo", OSError(errno.EINVAL, "Invalid argument"))
    assert cli._output_is_gone(exc)


def test_errno_22_from_somewhere_else_is_still_a_crash():
    """EINVAL is far too broad to wave through on its own -- a real one must still be reported."""
    exc = _raised_in("unrelated", OSError(errno.EINVAL, "Invalid argument"))
    assert not cli._output_is_gone(exc)


def test_an_unrelated_oserror_is_still_a_crash():
    exc = _raised_in("echo", OSError(errno.ENOENT, "No such file or directory"))
    assert not cli._output_is_gone(exc)


def test_giving_up_on_output_survives_streams_with_no_file_descriptor(monkeypatch):
    """Under pytest (and in the panel) stdout is a captured object, not a real descriptor."""
    monkeypatch.setattr(cli.sys, "stdout", io.StringIO())
    monkeypatch.setattr(cli.sys, "stderr", None)
    cli._give_up_on_output()            # must not raise


# --------------------------------------------------------------------------- the real thing
CHILD = r"""
import pathlib, sys, time
sys.argv = ["mygeeky", "--help"]
from mygeeky import config
config.LOG_DIR = pathlib.Path(__LOG_DIR__)          # never the real one, even if this regresses
from mygeeky import cli
if __NO_GUARD__:
    cli._output_is_gone = lambda exc: False         # how it behaved before this was fixed
time.sleep(1.0)                                     # let the parent's close land first
cli.entry()
"""


def _run_with_no_reader(log_dir, without_the_guard=False):
    """Start `mygeeky --help`, take the read end away, and report how it ended."""
    child = (CHILD.replace("__LOG_DIR__", repr(str(log_dir)))
                  .replace("__NO_GUARD__", repr(without_the_guard)))
    proc = subprocess.Popen([sys.executable, "-c", child],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=str(Path(cli.__file__).parents[2]))
    proc.stdout.close()                 # the reader goes away, exactly like `| head`
    said = proc.stderr.read().decode("utf-8", "replace")
    proc.stderr.close()
    proc.wait(timeout=120)
    return proc.returncode, said, sorted(log_dir.glob("error-*.txt"))


def test_a_reader_that_goes_away_exits_quietly_and_files_no_report(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    code, said, reports = _run_with_no_reader(log_dir)

    assert not reports, f"a report was filed for output going nowhere: {reports[0].read_text()[:400]}"
    assert code == 0, f"exit {code}, not a quiet 0. stderr: {said[:400]}"
    assert "hit a problem" not in said, said[:400]
    assert "Exception ignored" not in said, f"the interpreter's own exit-time flush still shows: {said[:400]}"


def test_without_the_guard_the_same_run_is_issue_6(tmp_path):
    """Proof that the test above is testing the guard, and a record of what the person saw.

    With the guard removed, this exact run is the bug as reported: a crash report on disk and
    "myGeeKy hit a problem: Invalid argument" (on Windows; "Broken pipe" elsewhere)."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    code, said, reports = _run_with_no_reader(log_dir, without_the_guard=True)

    # 120, not the SystemExit(1): the interpreter's own exit-time flush of the dead stream fails
    # on top of everything else and has the last word on the exit code.
    assert code in (1, 120), f"expected the old failure, got exit {code}: {said[:400]}"
    assert reports, "no report filed, so this test no longer demonstrates the old behaviour"
    assert "hit a problem" in said, f"the person was not shown the bogus failure: {said[:400]}"
    filed = reports[0].read_text(encoding="utf-8", errors="replace")
    assert "Invalid argument" in filed or "Broken pipe" in filed, filed[:400]
