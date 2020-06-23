from __future__ import unicode_literals

# imports - standard imports
from distutils.command.clean import clean as Clean
from pathlib import Path
from setuptools import setup


class CleanCommand(Clean):
	def run(self):
		Clean.run(self)

		def rm_tree(path):
			path = Path(path)
			for file in path.glob('*'):
				if file.is_file():
					file.unlink()
				else:
					rm_tree(file)
			if path.is_dir():
				path.rmdir()

		for relpath in ('build', '.cache', '.coverage', 'dist', 'frappe.egg-info'):
			rm_tree(relpath)

		for path in Path('.').rglob('*.py[co]'):
			path.unlink()

		for path in Path('.').rglob('__pycache__'):
			path.rmdir()


setup(cmdclass={'clean': CleanCommand})
