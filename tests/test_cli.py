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
        self.runner = CliRunner()

    def tearDown(self):
        """Clean up the temporary directory after each test."""
        shutil.rmtree(self.test_dir)

    def test_non_git_repo_skips(self):
        """
        Test that running gitex on a normal directory (not a git repo) 
        skips execution and prints a warning.
        """
        # Create a dummy file to ensure directory isn't empty
        p = Path(self.test_dir) / "test_file.txt"
        p.write_text("content inside non-git dir")
        
        # Run gitex on this directory
        result = self.runner.invoke(cli, [self.test_dir])
        
        # Should exit cleanly (return) but print warning to stderr
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Skipping", result.stderr)
        self.assertIn("not a valid Git repository", result.stderr)
        # Should NOT output the file content
        self.assertNotIn("content inside non-git dir", result.output)

    def test_non_git_repo_force(self):
        """
        Test that using the --force flag allows gitex to run 
        on a non-git directory.
        """
        p = Path(self.test_dir) / "forced_file.txt"
        p.write_text("forced content")
        
        # Run with --force
        result = self.runner.invoke(cli, [self.test_dir, "--force"])
        
        self.assertEqual(result.exit_code, 0)
        # Warning should not appear (or be overridden by success output)
        self.assertNotIn("Skipping", result.stderr)
        # Should see the file content
        self.assertIn("forced_file.txt", result.output)
        self.assertIn("forced content", result.output)

    def test_valid_git_repo(self):
        """
        Test that gitex runs automatically on a valid git repository.
        """
        # Initialize a dummy git repo in the temp dir
        repo = Repo.init(self.test_dir)
        
        # Create a file
        p = Path(self.test_dir) / "repo_file.py"
        p.write_text("print('hello git')")
        
        # Run gitex
        result = self.runner.invoke(cli, [self.test_dir])
        
        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("Skipping", result.stderr)
        self.assertIn("repo_file.py", result.output)
        self.assertIn("print('hello git')", result.output)

    def test_ignore_gitignore_does_not_affect_repo_check(self):
        """
        Test that --ignore-gitignore flag alone does not bypass the 
        repo safety check (unless --force is also used).
        """
        # Non-git dir
        p = Path(self.test_dir) / "ignored.txt"
        p.write_text("secret")
        
        # Run with -g but NO --force
        result = self.runner.invoke(cli, [self.test_dir, "-g"])
        
        # It should still skip because it's not a git repo
        self.assertIn("Skipping", result.stderr)
        self.assertNotIn("secret", result.output)

if __name__ == '__main__':
    unittest.main()