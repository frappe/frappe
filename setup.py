from setuptools import setup, find_packages
from frappe.__version__ import __version__
import os


with open("requirements.txt", "r") as f:
	install_requires = f.readlines()

setup(
    name='frappe',
    version=__version__,
    description='Metadata driven, full-stack web framework',
    author='Web Notes Technologies',
    author_email='info@frappe.io',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
        entry_points= {
                'console_scripts':[
                        'frappe = frappe.cli:main'
                        ]
                }
)
