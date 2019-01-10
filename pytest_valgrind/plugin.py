import pytest
import gc

from .valgrind import (
    running_valgrind, get_valgrind_num_errs, print_to_valgrind_log,
    do_leak_check)
# Debuggin/testing helpers:
from .valgrind import access_invalid, create_leak

def pytest_addoption(parser):
    group = parser.getgroup('valgrind')
    group.addoption(
        '--valgrind',
        action='store_true',
        dest='valgrind',
        help='''\
Runs valgrind checks after every test and replaces the actual results with
valgrind analysis result.
For this to make sense, it has to run with valgrind. Valgrind options
can be used normally. Please check the readme for some pointers, this
is very much a minimal tool and hopefully more knowledgeable users may
extend it or create better ones.

It currently reports failed tests (without valgrind errors) as skipped.

If you are only interested in errors and not memory leaks, you can just
run your program through valgrind directly with a high level of verbosity.
However, this plugin will check for memory leaks after every tests which can
help you narrow down the failing test.

Unlike running directly, you should ask valgrind to write somewhere else.
The valgrind output will include information about which functions were called.
The pytest output itself will then give you the failed functions and you
can search for them.

This could probably be set up nicer, but it works. It has the advantage,
that finding the broken test (and after that its output) gets much easier.
''')

def pytest_configure(config):
    valgrind = config.getvalue("valgrind")
    if valgrind:
        if not running_valgrind():
            raise RuntimeError(
                "pytest is configured to used valgrind, but was not started "
                "within valgrind!\n"
                "Please run with"
                "`valgrind --show-leak-kinds=definite --log-file=valgrind-output -- your command`. "
                "or a similar invocation.\nThe one above send valgrind information"
                "to an additional log file and adds test information to it, so"
                "you can search for those tests that failed.")

        checker = ValgrindChecker(config)
        config.pluginmanager.register(checker, 'valgrind_checker')


class ValgrindChecker(object):
    def __init__(self, config):
        pass

    @pytest.hookimpl(hookwrapper=True)
    def pytest_pyfunc_call(self, pyfuncitem):
        # TODO: Should replace this with an internal error probably.
        #       something that prints noisily on the normal output.
        print_to_valgrind_log(b"Preparing for next function call "
                              b"(Leaks here occured between function calls)")

        gc.collect()  # force a garbage collection
        before_leaked = do_leak_check()
        before_errors = get_valgrind_num_errs()

        print_to_valgrind_log(
            b"\n**************************************************************")
        print_to_valgrind_log(pyfuncitem.nodeid.encode("utf8"))
        print_to_valgrind_log(
            b"**************************************************************")

        outcome = yield
        # create_leak()
        # access_invalid()

        after_errors = get_valgrind_num_errs()
        gc.collect()  # for a garbage collection
        after_leaked = do_leak_check()

        print_to_valgrind_log(
            b"\n**************************************************************")

        error = after_errors - before_errors > 0
        leak = after_leaked - before_leaked > 0

        if error and leak:
            pytest.fail("[VALGRIND ERROR+LEAK]", pytrace=False)

            outcome.excinfo((RuntimeError, "error + memory leak",
                             "Both errors and a memory leak seem to have "
                             "occured. Pleaes check valgrind output."))
        elif error:
            pytest.fail("[VALGRIND ERROR]", pytrace=False)
            outcome.excinfo((RuntimeError, "error",
                             "A valgrind error occured, please check "
                             "valgrind output."))
        elif leak:
            pytest.fail("[VALGRIND LEAK]", pytrace=False)
            outcome.excinfo((RuntimeError, "memory leak",
                             "A memory leak occured. Please check valgrind"
                             "output."))
        elif outcome.excinfo is not None:
            # Do not care about actual errors, this likely not quite correct.
            pytest.skip("Error, but valgrind clean, hacking xfail.")
            outcome.excinfo = None
            outcome.force_result(True)
