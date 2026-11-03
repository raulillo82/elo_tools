'''
Tests the deploy script with real git repositories and fake podman, systemctl
and curl. Run with: python3 -m unittest
'''
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "web" / "deploy" / "elo-deploy.sh"
FAKE = '#!/bin/bash\necho "$(basename "$0") $*" >> "$CALLS"\n'


def git(folder, *args):
    subprocess.run(["git", "-C", str(folder), "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", *args], check=True, capture_output=True)


class ContainerfileTest(unittest.TestCase):
    def test_base_image_is_fixed_by_digest(self):
        text = (SCRIPT.parents[1] / "Containerfile").read_text()
        self.assertRegex(text, r"(?m)^FROM \S+:\S+@sha256:[0-9a-f]{64}$")


class Sandbox:
    SCRIPT = SCRIPT

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.origin = self.root / "origin"
        self.repo = self.root / "repo"
        self.bin = self.root / "bin"
        self.calls = self.root / "calls"
        self.state = self.root / "state"
        (self.root / "units").mkdir()
        self.bin.mkdir()
        (self.origin / "web" / "deploy").mkdir(parents=True)
        git(self.origin, "init", "-q", "-b", "main")
        self.commit("web/app.py", "one")
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.repo)], check=True)
        (self.root / "production").mkdir()
        (self.root / "data").mkdir()
        for name in ("podman", "systemctl"):
            self.fake(name, FAKE)
        self.health(200)
        self.run_deploy()
        self.calls.write_text("")

    def fake(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def health(self, code):
        self.fake("curl", f"#!/bin/bash\necho -n {code}\n")

    def commit(self, name, text):
        (self.origin / name).write_text(text)
        git(self.origin, "add", "-A")
        git(self.origin, "commit", "-qm", text)

    def run_deploy(self):
        env = {**os.environ, "REPO": str(self.repo), "STATE": str(self.state),
               "UNITS": str(self.root / "units"), "CALLS": str(self.calls),
               "PATH": f"{self.bin}:{os.environ['PATH']}", "HEALTH_TRIES": "2", "HEALTH_WAIT": "0"}
        return subprocess.run(["bash", str(self.SCRIPT)], env={**env, **self.extra()},
                              capture_output=True, text=True)

    def extra(self):
        return {}

    def called(self):
        return self.calls.read_text() if self.calls.exists() else ""

    def head(self):
        return subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()

    def deployed(self):
        return (self.state / "deployed").read_text().strip()


class DeployTest(Sandbox, unittest.TestCase):
    def test_nothing_to_do(self):
        self.assertEqual(self.run_deploy().returncode, 0)
        self.assertEqual(self.called(), "")

    def test_new_commit_is_deployed(self):
        self.commit("web/app.py", "two")
        self.assertEqual(self.run_deploy().returncode, 0)
        self.assertIn("podman build", self.called())
        self.assertIn("systemctl --user restart elo-web.service", self.called())
        self.assertEqual(self.deployed(), self.head())
        self.assertIn("podman image prune", self.called())

    def test_changes_outside_the_image_dont_restart(self):
        self.commit("README.md", "docs")
        self.assertEqual(self.run_deploy().returncode, 0)
        self.assertNotIn("restart", self.called())
        self.assertEqual(self.deployed(), self.head())

    def test_failed_version_goes_back(self):
        old = self.deployed()
        self.commit("web/app.py", "broken")
        self.health(500)
        self.assertEqual(self.run_deploy().returncode, 1)
        self.assertIn("podman tag localhost/elo-web:previous localhost/elo-web:latest", self.called())
        self.assertEqual(self.deployed(), old)

    def test_failed_build_doesnt_restart(self):
        self.commit("web/app.py", "broken")
        self.fake("podman", FAKE + '[ "$1" = build ] && exit 1\nexit 0\n')
        self.assertEqual(self.run_deploy().returncode, 1)
        self.assertEqual(self.called().count("restart elo-web.service"), 1)

    def test_failed_commit_stops_retrying(self):
        self.commit("web/app.py", "broken")
        self.health(500)
        for _ in range(3):
            self.assertEqual(self.run_deploy().returncode, 1)
        self.calls.write_text("")
        self.assertEqual(self.run_deploy().returncode, 0)
        self.assertEqual(self.called(), "")

    def test_a_newer_commit_is_tried_after_a_failure(self):
        self.commit("web/app.py", "broken")
        self.health(500)
        self.run_deploy()
        self.commit("web/app.py", "fixed")
        self.health(200)
        self.assertEqual(self.run_deploy().returncode, 0)
        self.assertEqual(self.deployed(), self.head())
        self.assertFalse((self.state / "failed").exists())


class StagingDeployTest(Sandbox, unittest.TestCase):
    SCRIPT = SCRIPT.with_name("elo-staging-deploy.sh")

    def extra(self):
        return {"DATA": str(self.root / "data"), "PRODUCTION_DATA": str(self.root / "production")}

    def branch(self, name, *commits):
        git(self.origin, "switch", "-qc", name)
        for text in commits:
            self.commit("web/app.py", text)
        git(self.origin, "switch", "-q", "main")

    def test_without_the_branch_it_follows_main(self):
        self.commit("web/app.py", "two")
        self.assertEqual(self.run_deploy().returncode, 0)
        self.assertIn("podman build", self.called())
        self.assertEqual(self.deployed(), self.head())
        self.assertIn("elo-staging.service", self.called())

    def test_the_branch_wins_and_is_left_when_deleted(self):
        self.branch("staging", "feature")
        self.run_deploy()
        self.assertEqual(self.deployed(), self.origin_head("staging"))
        self.assertEqual(self.head(), self.origin_head("staging"))
        git(self.origin, "branch", "-qD", "staging")
        self.run_deploy()
        self.assertEqual(self.deployed(), self.origin_head("main"))

    def test_the_branch_can_move_to_something_unrelated(self):
        self.branch("staging", "first")
        self.run_deploy()
        git(self.origin, "branch", "-qD", "staging")
        self.branch("staging", "second")
        self.assertEqual(self.run_deploy().returncode, 0)
        self.assertEqual(self.deployed(), self.origin_head("staging"))

    def test_a_branch_cant_install_units(self):
        (self.origin / "web" / "deploy" / "evil.service").write_text("[Service]")
        self.branch("staging", "evil")
        self.run_deploy()
        self.assertEqual(list((self.root / "units").iterdir()), [])
        self.assertNotIn("daemon-reload", self.called())

    def test_failed_version_goes_back(self):
        self.commit("web/app.py", "broken")
        self.fake("podman", FAKE + 'exit 0\n')
        self.health(500)
        self.assertEqual(self.run_deploy().returncode, 1)
        self.assertIn("podman tag localhost/elo-web-staging:previous", self.called())

    def test_lists_are_copied_but_never_the_accounts(self):
        production = self.root / "production"
        (production / "players-2027-01.sqlite").write_text("list")
        (production / "rosters.json").write_text("{}")
        (production / "accounts.db").write_text("secrets")
        self.assertEqual(self.run_deploy().returncode, 0)
        names = sorted(path.name for path in (self.root / "data").iterdir())
        self.assertEqual(names, ["players-2027-01.sqlite", "rosters.json"])
        self.assertIn("restart elo-staging.service", self.called())
        self.calls.write_text("")
        self.run_deploy()
        self.assertEqual(self.called(), "")

    def origin_head(self, name):
        return subprocess.run(["git", "-C", str(self.origin), "rev-parse", name],
                              capture_output=True, text=True, check=True).stdout.strip()


if __name__ == "__main__":
    unittest.main()
