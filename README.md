Valgrind testing helper for pytest
==================================

This is much of a hack, but it can help you test a C extension module with
valgrind. In particular if you are interested in checking for memory leaks.

The main reason for using this is to find out which test causes a leak, since
valgrind by default does not run leak checks intermittently. This causes
leak checks to be run after every test.

To use this module, you need to first install it using `pip install .` or
`pip install . --user`. It currently only supports Python 3 and requires
a C compiler as well as typical valgrind installation (`valgrind/valgrind.h`).

To then use it, use a normal pytest invocation giving the `--valgrind` option,
however, you also need to run everything in valgrind itself.

The easiest way to do this is (requires python 3.6 I believe):

```
PYTHONMALLOC=malloc valgrind --show-leak-kinds=definite --log-file=<some file> python -m pytest -v
--valgrind
```
Note that the `PYTHONMALLOC=malloc` command is crucial (and only works on newer
python versions). Alternatively, a python debug build with the `--valgrind`
option can be used. If neither is used, the output will be useless due to
false positives by python (suppression could be added, but are less reliable).

Note that you should provide a log file in this invocation. Any normal failures
will be skipped. For example in numpy, typically the floating point errors
fail to report, which causes test failures.

Any valgrind error or memory leak occuring *during* the test will lead to the
test being recorded as *FAILURE*. You will have to search the valgrind log
file for the specific error.

Notes
-----

Please check the valgrind documentation if you wish to modify your output.
Valgrind starts hiding duplicate errors, so if is highlighted as an error
but there is no error in the valgrind output, it is likely that the error
is a repetition of a previous one and thus hidden.

Furter notes:

  * At this time, this is practically untested.
  * It does not seem too elegant, if you know a nice way to fetch the
    valgrind output to include it into the pytest report, please tell
    me.
  * If you do not have useful function names in your output you did
    not build a debug build.
  * Valgrind has lots of options, please check them!
  * No, I did not check this on different systems/compilers. So if it
    breaks, you may have to modify the code or setup.py.
  * If valgrind has bad interaction causing errors during test gathering
    this may hang pytest. In that case, you may use
    `--continue-on-collection-errors` as a quick workaround.

Future Additions
================

Some things that would be easy to add very quickly probably:
  * I am not quite sure what happens to skipped tests, but
    a marker to skip only on valgrind may be good. Currently
    `pytest_valgrind.valgrind.running_on_valgrind()` is exposed
    and allows to check whether the tests are run inside valgrind.
