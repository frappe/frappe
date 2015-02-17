from setuptools import setup, find_packages
import os

version = "4.12.1"

with open("requirements.txt", "r") as f:
	install_requires = f.readlines()

setup(
    name='frappe',
    version=version,
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
