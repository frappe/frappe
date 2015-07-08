from setuptools import setup, find_packages

version = "5.0.34"

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
