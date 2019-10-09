from __future__ import unicode_literals

# imports - standard imports
import os, shutil
from distutils.command.clean import clean as Clean

from setuptools import setup, find_packages
import re, ast

# get version from __version__ variable in frappe/__init__.py
_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

with open('frappe/__init__.py', 'rb') as f:
	version = str(ast.literal_eval(_version_re.search(
		f.read().decode('utf-8')).group(1)))

class CleanCommand(Clean):
	def run(self):
		Clean.run(self)

		basedir = os.path.abspath(os.path.dirname(__file__))

		for relpath in ['build', '.cache', '.coverage', 'dist', 'frappe.egg-info']:
			abspath = os.path.join(basedir, relpath)
			if os.path.exists(abspath):
				if os.path.isfile(abspath):
					os.remove(abspath)
				else:
					shutil.rmtree(abspath)

		for dirpath, dirnames, filenames in os.walk(basedir):
			for filename in filenames:
				_, extension = os.path.splitext(filename)
				if extension in ['.pyc']:
					abspath = os.path.join(dirpath, filename)
					os.remove(abspath)
			for dirname in dirnames:
				if dirname in ['__pycache__']:
					abspath = os.path.join(dirpath,  dirname)
					shutil.rmtree(abspath)

setup(
	name='frappe',
	version=version,
	description='Metadata driven, full-stack web framework',
	author='Frappe Technologies',
	author_email='info@frappe.io',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires,
	dependency_links=[
		'https://github.com/frappe/python-pdfkit.git#egg=pdfkit'
	],
	cmdclass = \
	{
		'clean': CleanCommand
	}
)
