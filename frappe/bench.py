import json
import os
from pathlib import Path
from typing import Any, Final

from frappe.config import ConfigHandler


class BenchNotScopedError(NotImplementedError):
	pass


class BenchSiteNotLoadedError(ValueError):
	pass


class PathLike:
	def __fspath__(self):
		return str(self.path)


class Serializable:
	def __json__(self):
		return {k: v for k, v in self.__dict__.items()}


class Benched(PathLike, Serializable):
	def __init__(self, path: str | None = None, parent_path: Path | None = None):
		path = (
			path
			or os.environ.get(f"FRAPPE_{self.__class__.__name__.upper()}_PATH")
			or (parent_path.joinpath(self.__class__.__name__.lower()) if parent_path else None)
			# only for Bench class ...
			or (
				# TODO: legacy, remove
				os.environ.get("FRAPPE_BENCH_ROOT") if isinstance(self, Bench) else None
			)
			or (
				# TODO: unsave relative reference, remove
				Path(__file__).resolve().parents[3]  # bench folder in standard layout
				if isinstance(self, Bench)
				else None
			)
			or (Path("~/frappe-bench").expanduser() if isinstance(self, Bench) else None)
		)

		if path is None:
			raise ValueError(f"Unable to determine path for {self.__class__.__name__}")

		self.path = Path(path)


class Frapped:
	python_path: Path

	def __bool__(self):
		return self._is_frapped()

	def _is_frapped(self):
		return self.python_path.is_dir() and self.python_path.joinpath(".frappe").exists()


class Apps(Benched):
	def __init__(self, path: str | None = None, parent_path: str | None = None):
		super().__init__(path, parent_path)
		self._apps = None

	def __str__(self):
		return (
			repr(self)
			+ ("\n * Apps Path: " + str(self.path))
			+ ("\n * Loaded Apps:\n\t" + ("\n\t".join([str(app) for app in self.apps]) or "n/a"))
		)

	class App(Frapped, PathLike, Serializable):
		def __init__(self, name: str, path: str):
			self.name = name
			self.path = Path(path)
			self.python_path = self.path.joinpath(self.name)
			self._modules = None

		def __str__(self):
			return self.name

		class Module(Frapped, PathLike, Serializable):
			def __init__(self, name: str, path: str):
				self.name = name
				self.path = Path(path)
				self.python_path = self.path

		@property
		def modules(self) -> dict[str, Module]:
			if self._modules is None:
				self._modules = {
					d: module
					for d in self.python_path.iterdir()
					if (module := self.Module(d, self.python_path)) and module
				}
			return self._modules

		def __iter__(self):
			return iter(self.modules.values())

		def __len__(self):
			return len(self.modules)

		def __getitem__(self, key):
			return self.modules[key]

	@property
	def apps(self) -> dict[str, App]:
		if self._apps is None:
			self._apps = {
				d: app for d in self.path.iterdir() if d.is_dir() and (app := self.App(d, self.path)) and app
			}
		return self._apps

	def __iter__(self):
		return iter(self.apps.values())

	def __len__(self):
		return len(self.apps)

	def __getitem__(self, key):
		return self.apps[key]


class Logs(Benched):
	def __init__(self, path: str | None = None, parent_path: Path | None = None):
		super().__init__(path, parent_path)

	def get_log_file(self, log_type: str):
		return self.path.joinpath(f"{log_type}.log")


class Run(Benched):
	def __init__(self, path: str | None = None, parent_path: Path | None = None):
		super().__init__(
			path
			# config is the legacy naming of this folder; a misnomer
			or (parent_path.joinpath("config") if parent_path else None),
			parent_path,
		)


class Sites(Benched, ConfigHandler):
	ALL_SITES: Final = "__all-sites__"

	def __init__(self, path: str | None = None, parent_path: Path | None = None, bench: "Bench" = None):
		Benched.__init__(self, path, parent_path)
		ConfigHandler.__init__(self, self.path.joinpath("common_site_config.json"))
		self.__sites = None
		self.bench = bench
		# security: self.site_name attribute scopes access
		self.site_name = os.environ.get("FRAPPE_SITE") or self.config.get("default_site")
		self._iterator = None

	def __str__(self):
		return (
			repr(self)
			+ ("\n * Sites Path: " + str(self.path))
			+ ("\n * Scoped Site: " + (self.site_name or "n/a"))
			+ ("\n * Loaded Sites:\n\t" + ("\n\t".join([str(site) for site in self]) or "n/a"))
		)

	class Site(ConfigHandler, PathLike, Serializable):
		def __init__(self, name: str, path: str, bench: "super.Bench"):
			self.name = name
			self.path = Path(path)
			self.bench: "Bench" = bench
			self._combined_config = None
			ConfigHandler.__init__(self, self.path.joinpath("site_config.json"))

		def __str__(self):
			return self.name

		def __fspath__(self):
			return str(self.path)

		def __json__(self):
			excluded = (
				"bench",  # prevent circular deps
				"_ConfigHandler__config",  # holds file contents
				"_config_stale",  # never stale after accessored
			)
			naming = {"_combined_config": "config"}
			return {naming.get(k, k): v for k, v in self.__dict__.items() if k not in excluded}

		@property
		def config(self) -> dict[str, Any]:
			if self._combined_config is None or self._config_stale:
				site_config = super().config.copy()
				config = self.bench.sites.config.copy()
				config.update(site_config)
				self._combined_config = config
			return self._combined_config

	def add_site(self, site_name: str):
		site_path = self.path.joinpath(site_name)
		os.makedirs(site_path, exist_ok=True)
		for dir_path in [
			site_path.joinpath("public", "files"),
			site_path.joinpath("private", "backups"),
			site_path.joinpath("private", "files"),
			site_path.joinpath("locks"),
			site_path.joinpath("logs"),
		]:
			os.makedirs(dir_path, exist_ok=True)
		self.__sites[site_name] = self.Site(site_name, site_path)

	def remove_site(self, site_name: str):
		if site_name in self.__sites:
			del self.__sites[site_name]
			# site_path = self.path.joinpath(site_name)
			# Note: This doesn't actually delete the site directory, just removes it from the sites dict
			# Actual deletion should be handled separately with proper safeguards

	def scope(self, site_name: str | None = None) -> Site:
		if site_name is None:
			return self.site

		self.__sites = None
		self.site_name = site_name

		if self.site_name != self.ALL_SITES:
			return self.site

	@property
	def site(self) -> Site:
		# security: self.site_name attribute scopes access
		if not self.site_name or self.site_name == self.ALL_SITES:
			raise BenchNotScopedError("Sites was not scoped to a single site, yet.")
		return self[self.site_name]

	@property
	def _sites(self) -> dict[str, Site]:
		if self.__sites is None:
			self.__sites = {}

			def _process(path: Path):
				if path.is_dir() and path.joinpath("site_config.json").exists():
					self.__sites[path.name] = self.Site(path.name, path, self.bench)

			# security: self.site_name attribute scopes access
			if self.site_name and self.site_name != self.ALL_SITES:
				_process(self.path.joinpath(self.site_name))
			elif self.site_name == self.ALL_SITES:
				for site_path in self.path.iterdir():
					_process(site_path)
		return self.__sites

	def __iter__(self):
		# security: self.site_name attribute scopes access
		if self.site_name == self.ALL_SITES:
			return iter(self._sites.values())
		elif self.site_name:
			return iter([self[self.site_name]])
		raise BenchNotScopedError("Sites was not scoped, yet.")

	def __len__(self):
		return len(self._sites)

	def __getitem__(self, key):
		try:
			return self._sites[key]
		except KeyError:
			raise BenchSiteNotLoadedError(f"Site '{key}' was not loaded")


class Bench(Benched):
	def __init__(self, path: str | None = None):
		super().__init__(path)
		self.apps = Apps(parent_path=self.path)
		self.logs = Logs(parent_path=self.path)
		self.run = Run(parent_path=self.path)
		self.sites = Sites(parent_path=self.path, bench=self)

	def scope(self, site_name: str):
		return self.sites.scope(site_name)

	def __str__(self):
		return (
			repr(self)
			+ ("\n * Bench Path: " + str(self.path))
			+ ("\n\n" + str(self.apps))
			+ ("\n\n" + str(self.sites))
		)
