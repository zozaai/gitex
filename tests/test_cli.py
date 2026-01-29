import shutil
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner
from git import Repo

# Import the main entry point
from gitex.main import cli


class TestGitExCLI(unittest.TestCase):
    def setUp(self):
        """
        Set up a temporary directory before each test.
        This serves as our 'sample asset directory'.
        """
        self.test_dir = tempfile.mkdtemp()
        self.runner = CliRunner(mix_stderr=False)

    def tearDown(self):
        """Clean up the temporary directory after each test."""
        shutil.rmtree(self.test_dir)

    def test_non_git_repo_skips(self):
        """
        Test that running gitex on a normal directory (not a git repo)
        skips execution and prints a warning.
        """
        p = Path(self.test_dir) / "test_file.txt"
        p.write_text("content inside non-git dir", encoding="utf-8")

        result = self.runner.invoke(cli, [self.test_dir])

        self.assertEqual(result.exit_code, 0)

        # Click >= 8.3: use stderr/stdout explicitly
        self.assertIn("Skipping", result.stderr)
        self.assertIn("not a valid Git repository", result.stderr)

        # Should NOT output the file content to stdout
        self.assertNotIn("content inside non-git dir", result.stdout)

    def test_non_git_repo_force(self):
        """
        Test that using the --force flag allows gitex to run
        on a non-git directory.
        """
        p = Path(self.test_dir) / "forced_file.txt"
        p.write_text("forced content", encoding="utf-8")

        result = self.runner.invoke(cli, [self.test_dir, "--force"])

        self.assertEqual(result.exit_code, 0)

        # Warning should not appear in stderr
        self.assertNotIn("Skipping", result.stderr)

        # Should see the file content in stdout
        self.assertIn("forced_file.txt", result.stdout)
        self.assertIn("forced content", result.stdout)

    def test_ignore_gitignore_does_not_affect_repo_check(self):
        """
        Test that --ignore-gitignore flag alone does not bypass the
        repo safety check (unless --force is also used).
        """
        p = Path(self.test_dir) / "ignored.txt"
        p.write_text("secret", encoding="utf-8")

        # Run with -g but NO --force
        result = self.runner.invoke(cli, [self.test_dir, "-g"])

        # It should still skip because it's not a git repo
        self.assertIn("Skipping", result.stderr)
        self.assertNotIn("secret", result.stdout)

    def test_valid_git_repo(self):
        """
        Test that gitex runs automatically on a valid git repository.
        """
        Repo.init(self.test_dir)

        p = Path(self.test_dir) / "repo_file.py"
        p.write_text("print('hello git')\n", encoding="utf-8")

        result = self.runner.invoke(cli, [self.test_dir])

        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("Skipping", result.stderr)

        self.assertIn("repo_file.py", result.stdout)

        # Verify fenced code blocks
        self.assertIn("```python", result.stdout)
        self.assertIn("print('hello git')", result.stdout)
        self.assertIn("```", result.stdout)

    def test_help_short_flag(self):
        result = self.runner.invoke(cli, ["-h"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Usage:", result.output)

if __name__ == "__main__":
    unittest.main()
