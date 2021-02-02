import subprocess
import os
import warnings
import ctypes
import posixpath
import julia.libjulia as jl_libjulia
from json import dumps
from julia.libjulia import LibJulia
from julia.juliainfo import JuliaInfo
from julia.find_libpython import find_libpython
from ..absint.abs import Out_Def as _Out_Def
from ..codegen.julia import Codegen

GenerateCache = _Out_Def.GenerateCache


def get_libjulia():
    global libjl
    if not libjl:
        libjl = startup()
    return libjl


def mk_libjulia(julia="julia", **popen_kwargs):
    if lib := getattr(jl_libjulia, "_LIBJULIA"):
        return lib

    proc = subprocess.Popen(
        [
            julia,
            "--startup-file=no",
            "-e",
            "using DIO; DIO.PyJulia_INFO()",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        **popen_kwargs,
    )

    stdout, stderr = proc.communicate()
    retcode = proc.wait()
    if retcode != 0:
        raise subprocess.CalledProcessError(
            retcode, [julia, "-e", "..."], stdout, stderr
        )

    stderr = stderr.strip()
    if stderr:
        warnings.warn("{} warned:\n{}".format(julia, stderr))

    args = stdout.rstrip().split("\n")

    libjl = LibJulia.from_juliainfo(JuliaInfo(julia, *args))
    libjl.jl_string_ptr.restype = ctypes.c_char_p
    libjl.jl_string_ptr.argtypes = [ctypes.c_void_p]
    libjl.jl_call1.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    libjl.jl_call1.restype = ctypes.c_void_p
    libjl.jl_eval_string.argtypes = [ctypes.c_char_p]
    libjl.jl_eval_string.restype = ctypes.c_void_p
    libjl.jl_stderr_stream.argtypes = []
    libjl.jl_stderr_stream.restype = ctypes.c_void_p
    libjl.jl_printf.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    libjl.jl_printf.restype = ctypes.c_int
    return libjl


class JuliaException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return self.msg


def check_jl_err(libjl: LibJulia):
    if o := libjl.jl_exception_occurred():
        msg = libjl.jl_string_ptr(
            libjl.jl_call1(libjl.jl_eval_string(b"error2str"), o)
        ).decode("utf-8")
        raise JuliaException(msg)


def startup():
    global libjl
    libjl = mk_libjulia()
    libjl.init_julia()
    # DIO package already checked when getting libjulia
    libjl.jl_eval_string(
        b"function error2str(e)\n"
        b"   sprint(showerror, e; context=:color=>true)\n"
        b"end"
    )
    libjl.jl_eval_string(b"using DIO")
    check_jl_err(libjl)

    libpython_path = posixpath.join(*find_libpython().split(os.sep))
    libjl.jl_eval_string(
        b"DIO.@setup(%s)" % dumps(libpython_path).encode("utf-8")
    )
    libjl.jl_eval_string(b"printerror(x) = println(showerror(x))")
    check_jl_err(libjl)
    libjl.jl_eval_string(b'println("setup correctly")')
    check_jl_err(libjl)
    libjl.jl_eval_string(b"println(Py_CallFunction)")
    check_jl_err(libjl)
    # a = libjl.jl_eval_string(
    #     b"Py_CallFunction(@DIO_Obj(%s), @DIO_Obj(%s), @DIO_Obj(%s))"
    #     % (
    #         Codegen.uint64(id(print)).encode(),
    #         Codegen.uint64(id(1)).encode(),
    #         Codegen.uint64(id(3)).encode(),
    #     )
    # )
    # check_jl_err(libjl)
    return libjl


def as_py(res: ctypes.c_void_p):
    """
    This should be used on the return of a JIT func.
    No need to incref as it's already done by the JIT func.
    """
    libjl = get_libjulia()
    if res == 0:
        return None
    pyobj = libjl.jl_unbox_voidpointer(res)
    return pyobj


def code_gen():
    libjl = get_libjulia()
    interfaces = bytearray()
    for out_def in GenerateCache.values():
        cg = Codegen(out_def)
        interfaces.extend(cg.get_py_interfaces().encode("utf-8"))
        libjl.jl_eval_string(cg.get_jl_definitions().encode("utf-8"))
        check_jl_err(libjl)
    libjl.jl_eval_string(bytes(interfaces))
    check_jl_err(libjl)

    for intrin in GenerateCache:
        v = libjl.jl_eval_string(
            b"PyFunc_%s" % repr(intrin).encode("utf-8")
        )
        check_jl_err(libjl)
        intrin._callback = as_py(v)
    GenerateCache.clear()


startup()
