from setuptools import setup, find_packages

version = "5.0.0-alpha"

with open("requirements.txt", "r") as f:
	install_requires = f.readlines()

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
        entry_points= {
                'console_scripts':[
                        'frappe = frappe.cli:main'
                        ]
                }
)
