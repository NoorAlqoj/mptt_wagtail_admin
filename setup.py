from setuptools import setup


# The text of the README file
README = open('README.rst').read()

# This call to setup() does all the work
setup(
    name="mptt_wagtail5",
    version="1.0.0",
    description="A Django app to integrate mptt to wagtail admin.",
    long_description=README,
    url="https://github.com/NoorAlqoj/mptt-wagtail-admin",
    author="Noor Alqoj",
    author_email="noor.alqoj@gmail.com",
    license="MIT",
    packages=["mptt_wagtail"],
    include_package_data=True,
    install_requires=[],
)
