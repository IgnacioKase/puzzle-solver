"""Exercise the real hook in temporary Git repos, with an offline Ruff stand-in."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT


class PreCommitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        # A controlled PATH makes the tests independent of installed uv/ruff.
        for name in ("bash", "git"):
            (self.bin / name).symlink_to(shutil.which(name))
        self.env = {
            **os.environ,
            "PATH": str(self.bin),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
        }
        self.env.pop("SKIP_RUFF", None)
        self.git("init", "-q")
        self.git("config", "user.name", "Hook Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.hooksPath", ".githooks")
        (self.root / ".githooks").mkdir()
        shutil.copy2(ROOT / ".githooks/pre-commit", self.root / ".githooks/pre-commit")
        (self.root / "original.py").write_text("x=1\n")
        self.git("add", "original.py")
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "Initial")

    def git(self, *args):
        return subprocess.run(
            [shutil.which("git"), *args],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    def fake_ruff(self):
        # Shell builtins only; assert the hook dispatches and stages correctly.
        fake = self.bin / "ruff"
        fake.write_text("""#!/usr/bin/env bash
if [[ "$1" == "--version" ]]; then echo 'ruff 0.16.8'; exit 0; fi
printf '%s\\n' "$*" >> ruff-calls
if [[ "$1" == "format" ]]; then
    while [[ "$1" != "--" ]]; do shift; done
    shift
    for f in "$@"; do printf 'x = 1\\n' > "$f"; done
fi
if [[ "$1" == "check" && -n "${FAIL_LINT:-}" ]]; then exit 1; fi
""")
        fake.chmod(0o755)

    def hook(self):
        return subprocess.run(
            [str(self.root / ".githooks/pre-commit")],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_documentation_only_commit_needs_no_ruff(self):
        (self.root / "README.md").write_text("Docs only\n")
        self.git("add", "README.md")
        result = self.hook()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_python_commit_fails_without_formatter(self):
        (self.root / "new.py").write_text("x=1\n")
        self.git("add", "new.py")
        self.assertNotEqual(self.hook().returncode, 0)

    def test_renamed_python_file_is_formatted(self):
        self.fake_ruff()
        self.git("mv", "original.py", "renamed.py")
        result = self.hook()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git("show", ":renamed.py"), "x = 1\n")

    def test_wrong_ruff_version_blocks_before_formatting(self):
        self.fake_ruff()
        executable = self.bin / "ruff"
        executable.write_text(executable.read_text().replace("ruff 0.16.8", "ruff 0.0.1"))
        (self.root / "new.py").write_text("x=1\n")
        self.git("add", "new.py")
        result = self.hook()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("match CI", result.stdout)
        self.assertFalse((self.root / "ruff-calls").exists())

    def test_spaces_in_filename_and_unstaged_files_preserved(self):
        self.fake_ruff()
        (self.root / "a file.py").write_text("x=1\n")
        self.git("add", "a file.py")
        (self.root / "original.py").write_text("pending=2\n")
        result = self.hook()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git("show", ":a file.py"), "x = 1\n")
        self.assertEqual(self.git("show", ":original.py"), "x=1\n")
        self.assertEqual((self.root / "original.py").read_text(), "pending=2\n")

    def test_partially_staged_file_blocks_without_modification(self):
        self.fake_ruff()
        path = self.root / "original.py"
        path.write_text("x=2\n")
        self.git("add", "original.py")
        path.write_text("x=3\n")
        result = self.hook()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unstaged", result.stdout)
        self.assertEqual(path.read_text(), "x=3\n")
        self.assertEqual(self.git("show", ":original.py"), "x=2\n")
        self.assertFalse((self.root / "ruff-calls").exists())

    def test_unfixable_lint_blocks_commit(self):
        self.fake_ruff()
        self.env["FAIL_LINT"] = "1"
        (self.root / "new.py").write_text("x=1\n")
        self.git("add", "new.py")
        self.assertNotEqual(self.hook().returncode, 0)

    def test_explicit_skip(self):
        self.env["SKIP_RUFF"] = "1"
        (self.root / "new.py").write_text("x=1\n")
        self.git("add", "new.py")
        self.assertEqual(self.hook().returncode, 0)
