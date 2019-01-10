import pytest
import gc

from .valgrind import (
    running_valgrind, get_valgrind_num_errs, print_to_valgrind_log,
    do_leak_check)
# Debuggin/testing helpers:
from .valgrind import access_invalid, create_leak


valgrind_option_help = """\
Runs valgrind checks after every test and replaces the actual results with
valgrind analysis result. One main point is that it enforces regular checks
for memory leaks, to allow to find the leaking test quicker.
"""

# Memory checking is seriously slow!
memory_check_option_help = """\
Check for memory leaks before a test. Leaks are not expected between
test runs, but if it happens they modify the following test, so this
option tries to mitigate this by running the memcheck also before (and
does not report a failure if it already occured before).
NOTE: The memchecker is always flushed once before the first test!
"""

# Unfortunately, it did not seem obvious if I can get to the log file
# from within the virtual machine. But this works....
valgrind_log_file_help = """\
The valgrind log file. If passed in the plugin will extract the actual
valgrind errors and replace the traceback with the valgrind output.
"""


def pytest_addoption(parser):
    group = parser.getgroup('valgrind')

    group.addoption(
        '--valgrind', action='store_true', dest='valgrind',
        help=valgrind_option_help)

    group.addoption(
        '--memcheck-before-func', action='store_true',
        dest="memcheck_before", help=memory_check_option_help)

    group.addoption('--valgrind-log', action='store', dest="valgrind_log",
                    help=valgrind_log_file_help)

def pytest_configure(config):
    valgrind = config.getvalue("valgrind")
    if valgrind:
        if 0 and not running_valgrind():
            raise RuntimeError(
                "pytest is configured to used valgrind, but was not started "
                "within the valgrind virtual machine!\n"
                "Please check the README for the correct invocation.")

        checker = ValgrindChecker(config)
        config.pluginmanager.register(checker, 'valgrind_checker')


class ValgrindChecker(object):
    def __init__(self, config):
        self.memcheck_before = config.getvalue("memcheck_before")
        self.first_run = True
        log_file = config.getvalue("valgrind_log")
        if log_file:
            self.log_file = open(log_file)
        else:
            self.log_file = None

    @pytest.hookimpl(hookwrapper=True)
    def pytest_pyfunc_call(self, pyfuncitem):
        sep = b"*" * 70


        if self.first_run or self.memcheck_before:
            # TODO: This could in principle hide import time errors.
            #       Possibly, should run the first one in __init__.
            if self.first_run:
                print_to_valgrind_log(sep)
                print_to_valgrind_log(b"Flushing errors before first test:")
            else:
                # I am not sure this is a smart option, normal python is very
                # unlikely to leak, and it is slow to check...
                print_to_valgrind_log(b"Preparing for next function call "
                                      b"(Leaks here occured between tests)")

            for i in range(20):
                if gc.collect() == 0:
                    break
            else:
                # TODO: should print an internal error.
                raise RuntimeError("Garbage collection did not settle!?")
            before_leaked = do_leak_check()
            before_errors = get_valgrind_num_errs()

            # Read new info in the log file (no need to read it later)
            if self.log_file:
                self.log_file.read()

        print_to_valgrind_log(b"\n" + sep)

        test_identifier_string = pyfuncitem.nodeid.encode("utf8")
        print_to_valgrind_log(test_identifier_string)
        print_to_valgrind_log(sep)

        outcome = yield

        # Do this before, maybe errors can occur during garbage collection,
        # and they are probably due to the previous test as well.
        for i in range(20):
            if gc.collect() == 0:
                break
        else:
            # TODO: should print an internal error.
            raise RuntimeError("Garbage collection did not settle!?")

        after_errors = get_valgrind_num_errs()
        after_leaked = do_leak_check()

        print_to_valgrind_log(b"\n" + sep)

        error = after_errors - before_errors > 0
        leak = after_leaked - before_leaked > 0

        # Check for any marks about the test run:
        if any(pyfuncitem.iter_markers("valgrind_known_error")):
            known_error = True
        else:
            known_error = False

        if any(pyfuncitem.iter_markers("valgrind_known_leak")):
            known_leak = True
        else:
            known_leak = False

        if self.log_file is not None:
            # This in a sense silly, doing it in the virtual machine is just
            # slow. But lets hope there is not much output ;)
            valgrind_info = self._fetch_tests_valgrind_log()
        else:
            valgrind_info = (
                "Check valgrind log for details. Test ID is:\n{}".format(
                        test_identifier_string))

        if not error and not leak:
            if outcome.excinfo is not None:
                # Do not care about actual errors, this likely not quite correct
                # I am not sure this is right, since maybe there can be error
                # returns without `excinfo`?
                pytest.xfail("Error, but valgrind clean, using xfail.")

                outcome.excinfo = None
                outcome.force_result(True)
            return

        # A valgrind error occured, so report it (unless it is known failure).
        use_xfail = False

        if error and leak:
            type = "[VALGRIND ERROR+LEAK]"
            msg = ("Valgrind detected both an error(s) and a leak(s):")
            if known_error and known_leak:
                use_xfail = True

        elif error:
            type = "[VALGRIND ERROR]"
            msg = ("Valgrind has detected an error:")
            if known_error:
                use_xfail = True

        elif leak:
            type = "[VALGRIND LEAK]"
            msg = ("Valgrind has detected a memory leak:")
            if known_leak:
                use_xfail = True

        full_message = "{}\n\n{}\n\n{}".format(type, msg, valgrind_info)
        if use_xfail:
            pytest.xfail(full_message)
            outcome.force_result(True)
        else:
            pytest.fail(full_message, pytrace=False)

    def _fetch_tests_valgrind_log(self):
        """Read new results from the valgrind log. Should probably parse the
        log at some point...
        """
        new_output = self.log_file.read()

        return new_output