Valgrind testing helper for pytest
==================================

This is much of a hack, but it can help you test a C extension module with
valgrind. In particular if you are interested in checking for memory leaks.

When might I want to use this?:
  * You have a non-trivial C-extention and should really check it with valgrind.
  * You have a non-trivial C-extention module that does memory allocations
    and might leak memory.
  * You are interested in more then reference count leaks (other tools should
    be better), or hope valgrind can give you some information on the leak.

Why not just run the test in valgrind?:
  * Memory leak checking on valgrind is normally done only at exit. This
    will run a leak check after every test allowing you to narrow down where
    a leak occurs without additional effort.
  * This reports which test fails valgrind and the exact error associated
    with it. So it may be a bit more convenient

Why should I not use this?:
  * It is a a hack with you passing in the valgrind log file to pytest
    (if you want a helpful error summary).
  * It runs the memory check very often (currently cannot be disabled)
    and thus is even slower then a typical valgrind run.


How to use the plugin
---------------------

To use this module, you need to first install it using `pip install .` or
`pip install . --user`. It currently only supports Python 3 and requires
a C compiler as well as typical valgrind installation (`valgrind/valgrind.h`).

To then use it, use a normal pytest invocation giving the `--valgrind` option,
however, you also need to run everything in valgrind itself.

The easiest way to do this is (requires python 3.6 I believe). There
is an example test run in the example folder (which fails the valgrind tests),
as noted in the tests you can run it using:

```
PYTHONMALLOC=malloc valgrind --show-leak-kinds=definite --log-file=/tmp/valgrind-output \
    python -m pytest -vv --valgrind --valgrind-log=/tmp/valgrind-output
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


Reported failures and marking tests
-----------------------------------

This plugin ignores all normal exceptions and replaces them with *KNOWNFAIL*
right now. It will report failures only for errors/leaks reported by valgrind.

You can mark tests with `pytest.mark.valgrind_known_leak(reason="?!")`
or `pytest.mark.valgrind_known_error(reason="Oooops")` (or both).


Notes, Caveats, and Solutions
-----------------------------

Please check the valgrind documentation if you wish to modify your output.
Valgrind starts hiding duplicate errors, so if is highlighted as an error
but there is no error in the valgrind output, it might be that the error
is a repetition of a previous one and thus hidden.

Furter notes:

  * If valgrind has bad interaction causing errors during test gathering
    this may hang pytest. In that case, you may use
    `--continue-on-collection-errors` as a quick workaround.
  * Testing leaks this often slows down testing even more compared to a
    simple run with valgrind.
  * It does not seem too elegant, since a valgrind output file is passed
    to the pytest as an argument.
  * If you do not have useful function names in your output maybe you did
    not build a debug build?
  * Valgrind has lots of options, please check them!
  * No, I did not check this on different systems/compilers. So if it
    breaks, you may have to modify the code or setup.py.
  * By default checks for leaks once before the first test and once after
    every test. This means:
       - Leaks occuring before any test is run are not reported!
       - Leaks should not really occur between tests, but if they do they
         are reported for the next test.
  * If your program has caches (e.g. numpy has a small array cache) this might
    cause leaks to behave non-deterministic, or the object that is being leaked
    not correspond to the actual leaked object (since the allocation occured
    originally for another object).
  * The tool runs the garbage collector before every leak check.
    This is done only once though (gc runs may need longer to
    settle, could be fixed to iterate until no change occurs).
  * I do not know pytest plugins well (and the documentation is not super
    easy at the time), so a lot of how the pytest things are done can and
    should probably be much done better.
    

I do not like this or have a better version!
--------------------------------------------

Sure, feel free to create pull requests, if you have something better I will
be happy to remove/rename this.
