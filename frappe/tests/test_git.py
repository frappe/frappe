import tempfile
import unittest
from pathlib import Path

from frappe.tests.classes.unit_test_case import UnitTestCase
from frappe.utils import git


class TestGitWrapper(UnitTestCase):
	def test_repo_init_and_commit(self):
		with tempfile.TemporaryDirectory() as td:
			repo = git.Repo.init(td, initial_branch="main")
			self.assertEqual(repo.active_branch.name, "main")

			# Create files on disk
			readme = Path(td) / "README.md"
			readme.write_text("# Hello World")

			gitignore = Path(td) / ".gitignore"
			gitignore.write_text("*.tmp\nignored_dir/\n")

			tmp_file = Path(td) / "test.tmp"
			tmp_file.write_text("should be ignored")

			ignored_subdir = Path(td) / "ignored_dir"
			ignored_subdir.mkdir()
			(ignored_subdir / "file.txt").write_text("ignored")

			# Test ignored paths
			self.assertTrue(repo._is_path_ignored("test.tmp"))
			self.assertTrue(repo._is_path_ignored("ignored_dir/file.txt"))
			self.assertFalse(repo._is_path_ignored("README.md"))
			self.assertEqual(repo.ignored(["test.tmp", "README.md"]), ["test.tmp"])

			# Stage and commit
			repo.git.add(A=True)
			commit = repo.index.commit("Initial commit")

			self.assertEqual(commit.summary, "Initial commit")
			self.assertEqual(repo.head.commit.hexsha, commit.hexsha)
			self.assertEqual(repo.head.object.hexsha, commit.hexsha)

			# Verify iter_commits
			commits = list(repo.iter_commits())
			self.assertEqual(len(commits), 1)
			self.assertEqual(commits[0].hexsha, commit.hexsha)

			# Verify branches and heads list
			self.assertIn("main", [h.name for h in repo.heads])
			self.assertEqual(repo.heads["main"].name, "main")

	def test_repo_search_parent_directories(self):
		with tempfile.TemporaryDirectory() as td:
			git.Repo.init(td, initial_branch="develop")
			nested_dir = Path(td) / "a" / "b" / "c"
			nested_dir.mkdir(parents=True)

			found_repo = git.Repo(nested_dir, search_parent_directories=True)
			self.assertEqual(Path(found_repo.working_dir).resolve(), Path(td).resolve())

	def test_invalid_repo_errors(self):
		with tempfile.TemporaryDirectory() as td:
			with self.assertRaises(git.exc.InvalidGitRepositoryError):
				git.Repo(td)

		with self.assertRaises(git.exc.NoSuchPathError):
			git.Repo("/non/existent/path/xyz_123")
