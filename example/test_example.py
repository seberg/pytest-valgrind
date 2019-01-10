"""
This is a minimal example of tests which fail in pytest and can be used to
check that it is working correctly.

Run this example with:

```shell
PYTHONMALLOC=malloc valgrind --show-leak-kinds=definite --log-file=/tmp/valgrind-output \
    python -m pytest -vv --valgrind --valgrind-log=/tmp/valgrind-output
```

You can find a sample output (hopefully not completely outdated) next to this
file.
"""

import pytest
from pytest_valgrind.valgrind import create_leak, access_invalid


def test_all_good():
    # This test just passes, yay!
    pass


def test_fails_but_valgrind_good():
    assert 0


def test_valgrind_error():
    # Test accesses invalid/uninitialized data on the C level
    access_invalid()


def test_valgrind_leak():
    # Test leaks a bit of memory on the C level
    create_leak()


def test_valgrind_error_and_leak():
    # Test both access invalid/unitialized data and creates a leak
    access_invalid()
    create_leak()


@pytest.mark.valgrind_known_leak(reason="Leaks intentionally")
def test_valgrind_leak_ignored():
    create_leak()


@pytest.mark.valgrind_known_error(reason="Errors intentionally")
def test_valgrind_error_ignored():
    access_invalid()


@pytest.mark.valgrind_known_leak(reason="Leaks intentionally")
def test_valgrind_leak_ignored_but_errors_as_well():
    create_leak()
    access_invalid()
