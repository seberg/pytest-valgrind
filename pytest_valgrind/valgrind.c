#include <Python.h>

#include "valgrind/valgrind.h"
#include "valgrind/memcheck.h"


PyObject *
running_valgrind(PyObject *self, PyObject *args)
{
    return PyLong_FromUnsignedLong(RUNNING_ON_VALGRIND);
}


PyObject *
get_valgrind_num_errs(PyObject *self, PyObject *args)
{
    unsigned long invalid_access;

    invalid_access = VALGRIND_COUNT_ERRORS;

    return PyLong_FromUnsignedLong(invalid_access);
}


PyObject *
do_leak_check(PyObject *self, PyObject *args)
{
    unsigned long leaked, dubious, reachable, suppressed;

    VALGRIND_DO_ADDED_LEAK_CHECK;

    VALGRIND_COUNT_LEAKS(leaked, dubious, reachable, suppressed);

    /* Flush errors, we just assume they were all leaks. */
    VALGRIND_COUNT_ERRORS;
    return PyLong_FromUnsignedLong(leaked);
}



PyObject *
create_leak(PyObject *self, PyObject *args)
{
    double *data = malloc(sizeof(double));
    /* Returning makes very sure that it can't be optimed away */
    return PyLong_FromVoidPtr(data);
}


PyObject *
access_invalid(PyObject *self, PyObject *args)
{
    PyObject * result;
    /* Use malloc, so C can't optimize it away... */
    long *never_initialized = malloc(sizeof(long));

    if (never_initialized == NULL) {
        PyErr_NoMemory();
        return NULL;
    }
    /* Casting to bool means that an invalid access occurs */
    result = PyBool_FromLong(*never_initialized);
    free(never_initialized);
    return result;
}

PyObject *
print_to_valgrind_log(PyObject *self, PyObject *arg)
{
    char *to_print = PyBytes_AsString(arg);
    if (to_print == NULL) {
        return NULL;
    }
    VALGRIND_PRINTF("%s\n", to_print);
    Py_RETURN_NONE;
}


static PyMethodDef valgrind_methods[] = {
    {"running_valgrind",  running_valgrind, METH_NOARGS,
        "Probe if valgrind exists."},
    {"get_valgrind_num_errs",  get_valgrind_num_errs, METH_NOARGS,
        "Get current number of run-time valgrind errors."},
    {"do_leak_check",  do_leak_check, METH_NOARGS,
        "Force a valgrind leak check and return the number of new leaks.\n"
        "WARNING: clears the error count for non-leak related errors!"},
    {"create_leak", create_leak, METH_NOARGS,
        "intentially leak some memory for testing."},
    {"access_invalid", access_invalid, METH_NOARGS,
        "intentionally access invalid data (conditional)."},
    {"print_to_valgrind_log", print_to_valgrind_log, METH_O,
        "Print message to the valgrind log file."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};


static struct PyModuleDef valgrindmodule = {
    PyModuleDef_HEAD_INIT,
    "valgrind",
    NULL,
    -1,
    valgrind_methods,
};

PyMODINIT_FUNC
PyInit_valgrind(void)
{
    return PyModule_Create(&valgrindmodule);
}
