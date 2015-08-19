from setuptools import setup, find_packages

version = "7.0.0"

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
    install_requires=install_requires
)
