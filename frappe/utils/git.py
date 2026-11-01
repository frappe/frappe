"""A high-compatibility GitPython drop-in wrapper powered entirely by rusty_git.sync

Zero subprocess calls: all Git operations run in-process using Rust (gix + git2)
and pure Python directory/ignore management.
"""

import fnmatch
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import rusty_git


class InvalidGitRepositoryError(rusty_git.GitRepositoryError):
	"""Raised when a directory does not appear to be a valid git repository."""
	pass


class NoSuchPathError(Exception):
	"""Raised when a specified repository path does not exist."""
	pass


class GitCommandError(Exception):
	"""Raised when a git command or operation fails."""
	def __init__(self, command, status=1, stderr=None, stdout=None):
		self.command = command
		self.status = status
		self.stderr = stderr
		self.stdout = stdout
		super().__init__(f"Operation '{command}' failed with status {status}: {stderr}")


class _ExcModule:
	InvalidGitRepositoryError = InvalidGitRepositoryError
	NoSuchPathError = NoSuchPathError
	GitCommandError = GitCommandError


exc = _ExcModule()


@dataclass
class Author:
	name: str
	email: str

	def __str__(self):
		return f"{self.name} <{self.email}>"


class Commit:
	def __init__(self, repo_path: str, data: dict):
		self._repo_path = repo_path
		self.hexsha = data["sha"]
		self.message = data.get("message", "")
		self.summary = self.message.split("\n", 1)[0]
		self.author = Author(name=data.get("author_name", ""), email=data.get("author_email", ""))
		self.committer = Author(name=data.get("committer_name", ""), email=data.get("committer_email", ""))
		epoch = data.get("timestamp_epoch", 0)
		self.committed_date = epoch
		self.committed_datetime = datetime.fromtimestamp(epoch)
		self._parent_shas = data.get("parent_shas", [])

	@property
	def parents(self) -> tuple["Commit", ...]:
		return tuple(
			Commit(self._repo_path, rusty_git.sync.get_commit(self._repo_path, sha))
			for sha in self._parent_shas
		)

	def __str__(self):
		return self.hexsha

	def __repr__(self):
		return f"<Commit '{self.hexsha[:7]}'>"


class Head:
	def __init__(self, repo_path: str, name: str):
		self.repo_path = repo_path
		self.name = name

	@property
	def commit(self) -> Commit:
		raw = rusty_git.sync.get_commit(self.repo_path, self.name)
		return Commit(self.repo_path, raw)

	@property
	def object(self) -> Commit:
		"""GitPython compatibility alias (head.object -> commit)."""
		return self.commit

	def __str__(self):
		return self.name

	def __repr__(self):
		return f"<Head 'refs/heads/{self.name}'>"


class IterableList(list):
	"""GitPython-style list that allows lookup by name or attribute: repo.heads['main'] or repo.heads.main"""

	def __getitem__(self, item):
		if isinstance(item, str):
			for entry in self:
				if entry.name == item:
					return entry
			raise IndexError(f"No head named {item}")
		return super().__getitem__(item)

	def __getattr__(self, name):
		try:
			return self[name]
		except IndexError:
			raise AttributeError(f"No head named {name}")


class GitCommand:
	"""In-process command adapter replacing git CLI invocations."""

	def __init__(self, repo: "Repo"):
		self.repo = repo

	def add(self, *paths, **kwargs):
		"""Mark working tree files for next index commit."""
		if kwargs.get("A") or kwargs.get("all") or "." in paths:
			self.repo.index.stage_all()
		else:
			for path in paths:
				self.repo.index.stage(path)


class IndexFile:
	"""In-process staging index tracking changes to commit."""

	def __init__(self, repo: "Repo"):
		self.repo = repo
		self._staged_files: dict[str, bytes] | None = None

	def stage_all(self):
		"""Stage all files from working tree, respecting .gitignore."""
		root = Path(self.repo.working_dir)
		staged = {}
		for p in root.rglob("*"):
			if ".git" in p.parts:
				continue
			if p.is_file():
				rel = str(p.relative_to(root))
				if not self.repo._is_path_ignored(rel):
					staged[rel] = p.read_bytes()
		self._staged_files = staged

	def stage(self, path: str | Path):
		if self._staged_files is None:
			self._staged_files = {}
		p = Path(path)
		root = Path(self.repo.working_dir)
		full_path = p if p.is_absolute() else (root / p)
		if full_path.is_file():
			rel = str(full_path.relative_to(root))
			if not self.repo._is_path_ignored(rel):
				self._staged_files[rel] = full_path.read_bytes()

	def commit(self, message: str, **kwargs) -> Commit:
		"""Create a commit using rusty_git in-process with zero subprocesses."""
		if self._staged_files is None:
			self.stage_all()

		branch = self.repo.active_branch.name
		res = rusty_git.sync.create_commit(
			self.repo.working_dir,
			branch=branch,
			files=self._staged_files,
			message=message,
			**kwargs,
		)
		self._staged_files = None
		raw = rusty_git.sync.get_commit(self.repo.working_dir, res["commit_sha"])
		return Commit(self.repo.working_dir, raw)


class Repo:
	def __init__(self, path: str | Path, search_parent_directories: bool = False):
		target_path = Path(path).resolve()
		if not target_path.exists():
			raise NoSuchPathError(f"Path does not exist: {path}")

		if search_parent_directories:
			curr = target_path
			found = None
			while True:
				if (curr / ".git").exists() or (curr / "HEAD").exists():
					found = curr
					break
				if curr.parent == curr:
					break
				curr = curr.parent
			if found is None:
				raise InvalidGitRepositoryError(f"{path} does not appear to be a git repository")
			target_path = found

		self.working_dir = str(target_path)

		# Verify repository by reading HEAD or branches via rusty_git
		try:
			_ = rusty_git.sync.get_commit(self.working_dir, "HEAD")
		except rusty_git.GitRepositoryError as e:
			raise InvalidGitRepositoryError(str(e)) from e
		except Exception:
			# For freshly initialized repos before any commit exists
			if not ((target_path / ".git").exists() or (target_path / "HEAD").exists()):
				raise InvalidGitRepositoryError(f"{path} does not appear to be a git repository")

		self._git = None
		self._index = None
		self._cached_gitignore = None

	@classmethod
	def init(
		cls,
		path: str | Path | None = None,
		initial_branch: str | None = None,
		mkdir: bool = True,
		**kwargs,
	) -> "Repo":
		"""Initialize a working-tree Git repository in-process with zero subprocesses."""
		repo_path = Path(path or os.getcwd()).resolve()
		if mkdir and not repo_path.exists():
			repo_path.mkdir(parents=True, exist_ok=True)

		git_dir = repo_path / ".git"
		git_dir.mkdir(parents=True, exist_ok=True)

		# Use rusty_git to initialize the git object store and directory structure
		rusty_git.sync.init_bare_repository(str(git_dir))

		# Configure repository as non-bare (working-tree repo)
		config_file = git_dir / "config"
		if config_file.exists():
			config_content = config_file.read_text()
			config_file.write_text(config_content.replace("bare = true", "bare = false"))

		# Set initial branch ref
		branch = initial_branch or "main"
		(git_dir / "HEAD").write_text(f"ref: refs/heads/{branch}\n")

		return cls(repo_path)

	@property
	def git(self) -> GitCommand:
		if self._git is None:
			self._git = GitCommand(self)
		return self._git

	@property
	def index(self) -> IndexFile:
		if self._index is None:
			self._index = IndexFile(self)
		return self._index

	@property
	def heads(self) -> IterableList:
		branches = rusty_git.sync.list_branches(self.working_dir)
		return IterableList([Head(self.working_dir, b) for b in branches])

	@property
	def branches(self) -> IterableList:
		return self.heads

	@property
	def active_branch(self) -> Head:
		head_path = Path(self.working_dir) / "HEAD"
		if not head_path.exists():
			head_path = Path(self.working_dir) / ".git" / "HEAD"

		if head_path.exists():
			content = head_path.read_text().strip()
			if content.startswith("ref: refs/heads/"):
				return Head(self.working_dir, content.removeprefix("ref: refs/heads/"))
		return Head(self.working_dir, "main")

	@property
	def head(self) -> Head:
		return Head(self.working_dir, "HEAD")

	def commit(self, rev: str = "HEAD") -> Commit:
		raw = rusty_git.sync.get_commit(self.working_dir, rev)
		return Commit(self.working_dir, raw)

	def iter_commits(self, rev: str = "HEAD", max_count: int | None = None) -> Iterator[Commit]:
		"""Walk commit history by parent pointers."""
		curr = self.commit(rev)
		count = 0
		while curr:
			yield curr
			count += 1
			if max_count and count >= max_count:
				break
			parents = curr.parents
			if not parents:
				break
			curr = parents[0]

	def diff(self, base: str, head: str):
		return rusty_git.sync.compare_refs(self.working_dir, base, head)

	def create_commit(self, branch: str, files: dict, message: str, **kwargs):
		"""In-memory atomic commit without disk staging."""
		return rusty_git.sync.create_commit(
			self.working_dir,
			branch=branch,
			files=files,
			message=message,
			**kwargs,
		)

	def _load_gitignore_patterns(self) -> list[str]:
		gitignore = Path(self.working_dir) / ".gitignore"
		if not gitignore.exists():
			return []
		patterns = []
		for line in gitignore.read_text().splitlines():
			line = line.strip()
			if not line or line.startswith("#"):
				continue
			patterns.append(line)
		return patterns

	def _is_path_ignored(self, path: str | Path) -> bool:
		"""Evaluate path against repository .gitignore rules."""
		if self._cached_gitignore is None:
			self._cached_gitignore = self._load_gitignore_patterns()

		target = Path(path)
		repo = Path(self.working_dir)
		if target.is_absolute():
			try:
				rel = target.relative_to(repo)
			except ValueError:
				rel = target
		else:
			rel = target

		rel_str = str(rel)
		parts = rel.parts
		ignored = False

		for line in self._cached_gitignore:
			negated = line.startswith("!")
			pattern = line[1:].strip() if negated else line
			pattern = pattern.rstrip("/")

			if "/" in pattern:
				match = fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(rel_str, f"*/{pattern}")
			else:
				match = any(fnmatch.fnmatch(part, pattern) for part in parts)

			if match:
				ignored = not negated

		return ignored

	def ignored(self, *paths) -> list[str]:
		"""In-process gitignore checker matching git check-ignore behavior."""
		flat_paths = []
		for p in paths:
			if isinstance(p, (list, tuple, set)):
				flat_paths.extend(str(item) for item in p)
			else:
				flat_paths.append(str(p))

		return [p for p in flat_paths if self._is_path_ignored(p)]
