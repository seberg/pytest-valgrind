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

# Unfortunately, it did not seem obvious if I can get to the log file
# from within the virtual machine. But this works....
valgrind_log_file_help = """\
The valgrind log file. If passed in the plugin will extract the actual
valgrind errors and replace the traceback with the valgrind output.
"""

# Memory checking is seriously slow!
memory_check_option_help = """\
Check for memory leaks before a test. Leaks are not expected between
test runs, but if it happens they modify the following test, so this
option tries to mitigate this by running the memcheck also before (and
does not report a failure if it already occured before).
NOTE: The memchecker is always flushed once before the first test!
"""

no_memcheck_help = """\
Disables memory checking, this should make testing faster if you are sure
there are no memory leaks.
"""


def pytest_addoption(parser):
    group = parser.getgroup('valgrind')

    group.addoption(
        '--valgrind', action='store_true', dest='valgrind',
        help=valgrind_option_help)

    group.addoption('--valgrind-log', action='store', dest="valgrind_log",
                    help=valgrind_log_file_help)

    group.addoption(
        '--memcheck-before-func', action='store_true',
        dest="memcheck_before", help=memory_check_option_help)

    group.addoption(
        '--no-memcheck', action='store_true',
        dest="disable_memcheck", help=no_memcheck_help)


def pytest_configure(config):
    valgrind = config.getvalue("valgrind")
    if not valgrind:
        return

    if not running_valgrind():
        raise RuntimeError(
            "pytest is configured to used valgrind, but was not started "
            "within the valgrind virtual machine!\n"
            "Please check the README for the correct invocation.")

    checker = ValgrindChecker(config)
    config.pluginmanager.register(checker, 'valgrind_checker')


class ValgrindChecker(object):
    def __init__(self, config):
        self.no_memcheck = config.getvalue("disable_memcheck")
        if self.no_memcheck:
            # Just disable checking before completely.
            # TODO: Might be nicer to use a dummy method that just returns 0.
            self.first_run = False
            self.memcheck_before = False
        else:
            self.memcheck_before = config.getvalue("memcheck_before")
            self.first_run = True

            # This is somewhat confusing. Valgrind, by default, reports errors
            # for "possible" leaks. However, Python uses "interior-pointers"
            # for objects with cyclic garbage collection support.
            # Valgrind counts these as "possible" leaks meaning that we would
            # have a huge amount of false positives (valgrind has hardcoded
            # heuristics for some cases, but none seem to match Python).
            # Until a better solution is found, the solution here is to ignore
            # possible leaks. In the first version I did this by manually
            # counting leaks, instead of enforcing the use of:
            #     --errors-for-leak-kinds=definite
            # So we get the below sanity check: If the user passed the above
            # command to valgrind, possible leaks are not errors and we can
            # use the errors as reported by valgrind. If the user did not pass
            # the above (or similar?) command, we manually count leaks and use
            # that instead.
            # The main difference should be that directly counting leaks will
            # also report indirectly lost memory, while the above command
            # ignores them. Effectively, we ignore the valgrind setting and
            # enforce:
            #     --errors-for-leak-kinds=definite,indirect

            # Disable the GC just in case it might confuse things if it runs
            # while probing the error reporting behaviour:
            gc.disable()
            leaks = do_leak_check()
            errors = get_valgrind_num_errs()
            # This will use "interior-pointers" (possible leak):
            obj = object()
            new_leaks = do_leak_check() - leaks
            new_errors = get_valgrind_num_errs() - errors
            gc.enable()
            if new_leaks != 0:
                # There be no new leaks for the above simple code
                raise RuntimeError(
                        "Sanity check failed, please report this, as it is "
                        "probably a pytest-valgrind bug. (leak detected for "
                        "simple allocation)")
            if new_errors:
                self.count_leaks = True

            else:
                self.count_leaks = False
                print("pytest-valgrind: Reporting memory errors as set up "
                      "using the `--errors-for-leak-kinds` option of valgrind.")

        self.log_file_name = config.getvalue("valgrind_log")
        if self.log_file_name:
            self.log_file = open(self.log_file_name)
        else:
            self.log_file = None

        self.prev_leaked = 0
        self.prev_errors = 0

    def pytest_report_header(self, config):
        info = []
        info.append(f"pytest-valgrind: logfile={self.log_file_name}")
        if self.no_memcheck:
            info.append("Not performing runtime memory leak checks.")

        elif self.count_leaks:
            info.append("Reporting direct+indirect leaks and ignoring the")
            info.append("  `--errors-for-leak-kinds` valgrind option.")
            info.append('  Python always causes "possible" leaks but you can use ')
            info.append("  `--errors-for-leak-kinds=direct` to hide indirect leaks.)")
        else:
            info.append(
                "Reporting memory leaks as set up using the "
                "`--errors-for-leak-kinds` valgrind option.")


        if self.memcheck_before:
            info.append("Flushing memory leaks before each test "
                        "(hide leaks that occurred between tests).")

        return "\npytest-valgrind: ".join(info)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_pyfunc_call(self, pyfuncitem):
        sep = b"*" * 70


        if self.first_run or self.memcheck_before:
            # TODO: This could in principle hide import time errors.
            #       Possibly, should run the first one in __init__.
            if self.first_run:
                print_to_valgrind_log(sep)
                print_to_valgrind_log(b"Flushing errors before first test:")

                self.first_run = False
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
            self.prev_leaked = do_leak_check()
            self.prev_errors = get_valgrind_num_errs()

            # Read new info in the log file (no need to read it later)
            if self.log_file:
                self.log_file.read()

        print_to_valgrind_log(b"\n" + sep)

        test_identifier_string = pyfuncitem.nodeid.encode("utf8")
        print_to_valgrind_log(test_identifier_string)
        print_to_valgrind_log(sep)

        outcome = yield

        # Do this before leak/error checking. Errors can occur during garbage
        # collection. However, there could also be due to things occuring
        # between two test runs.
        # Note: We could skip this, especially if there is no leak checking.
        #       That would probably speed up test execution a lot.
        for i in range(20):
            if gc.collect() == 0:
                break
        else:
            # TODO: should print an internal error.
            raise RuntimeError("Garbage collection did not settle!?")

        # An error occurred, if the number of valgrind errors increased:
        error = get_valgrind_num_errs() - self.prev_errors > 0

        if self.no_memcheck:
            leak = False
        elif self.count_leaks:
            # Manually count leaks (not errors reported by valgrind)
            currently_leaked = do_leak_check()
            leak = currently_leaked - self.prev_leaked > 0
            self.prev_leaked = currently_leaked
        else:
            # See if valgrind reports new errors during leak check
            errors_before_leak_check = get_valgrind_num_errs()
            do_leak_check()
            leak = get_valgrind_num_errs() - errors_before_leak_check > 0

        print_to_valgrind_log(b"\n" + sep)

        # Need to get the errors again, because leaks may have added new ones:
        self.prev_errors = get_valgrind_num_errs()

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
                        test_identifier_string.decode('utf8')))

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
