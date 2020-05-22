# sample ./setup.py file
from setuptools import setup


from setuptools.extension import Extension

ext_packages = [Extension("pytest_valgrind.valgrind",
                          ["pytest_valgrind/valgrind.c"]),]

setup(
    name="pytest-valgrind",
    version="0.1.0",
    url="https://github.com/fridex/pytest-valgrind",
    packages=["pytest_valgrind"],
    author="Sebastian Berg",
    author_email="sebastian@sipsolutions.net",
    maintainer="Fridolin Pokorny",
    maintainer_email="fridex.devel@gmail.com",
    # The following makes a plugin available to pytest:
    entry_points={"pytest11": ["valgrind = pytest_valgrind.plugin"]},
    # Custom PyPI classifier for pytest plugins
    classifiers=["Framework :: Pytest",
                 "License :: OSI Approved :: MIT License"],
    install_requires=["pytest>=2.9.0"],  # I have no clue if this is true.
    # Make the extension module for valgrind interaction,
    # would be good to port to python instead of cthon for compatibility.
    ext_modules=ext_packages,
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
)
