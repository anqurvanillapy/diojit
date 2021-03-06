from __future__ import annotations
from .abs import *
from .intrinsics import *
from collections.abc import Iterable
from functools import lru_cache
import warnings
import typing
import operator
import math
import builtins
import io

if typing.TYPE_CHECKING:
    from mypy_extensions import VarArg

_undef = object()
__all__ = ["create_shape", "register"]

_not_inferred_types = (Top, Bot)


def lit(x: str):
    """directly pass this string to the backend"""
    return typing.cast(AbsVal, x)


def u64i(i: int):
    """uint64 from integer"""
    return f"{i:#0{18}x}"


concrete_numeric_types = {
    int: "PyInt_Compare",
    float: "PyObject_RichCompare",
    complex: "PyObject_RichCompare",
    bool: "PyInt_Compare",
}


def create_shape(
    o: object, oop: bool = False, self_bound=False, instance=_undef
):
    """
    o: 'Special Object' in the paper. Must be immutable.
    oop: whether attached methods will be
         used as bound method in method resolution.
    instance: only works when 'o' is a 'type'.
              It is defined only the type has only
              one instance.
    """
    try:
        hash(o)
    except TypeError:
        raise TypeError(f"create shape for non immuatble object {o}")
    if instance is _undef:
        instance = None
    else:
        instance = from_runtime(instance)
        assert not isinstance(instance, D)

    if shape := ShapeSystem.get(o):
        return shape
    shape = ShapeSystem[o] = Shape(o, oop, {}, instance, self_bound)
    return shape


_create_shape = create_shape


def register(
    o: object,
    attr="__call__",
    create_shape: typing.Union[dict, None, typing.Literal[True]] = None,
):

    if shape := ShapeSystem.get(o):
        pass
    else:
        if create_shape is not None:
            if create_shape is True:
                create_shape = {}
            shape = _create_shape(o, **create_shape)
        else:
            raise ValueError(
                f"No shape found for {{ o={o} }}.\n"
                f" Maybe use {{ create_shape(o, oop_or_not) }} firstly?"
            )
    if attr in shape.fields:
        warnings.warn(
            Warning(
                f"field {attr} exists for the shape of object f{o}."
            )
        )

    def ap(f: typing.Callable[[Judge, VarArg(AbsVal)], CallSpec]):
        shape.fields[attr] = f
        return f

    return ap


def shape_of(o):
    return ShapeSystem[o]


create_shape(Intrinsic, oop=True)
create_shape(list, oop=True)
create_shape(dict, oop=True)
create_shape(bytes, oop=True)
create_shape(bool, oop=True)
create_shape(bytearray, oop=True)
create_shape(int, oop=True)
# create_shape(type, self_bound=True, oop=True)
create_shape(next)
create_shape(io.BytesIO)
_NoneType_shape = create_shape(type(None))
_NoneType_shape.instance = S(None)


@register(Intrinsic, "__call__")
def py_call_intrinsic(
    self: Judge, f: AbsVal, *args: AbsVal
) -> CallSpec:
    return CallSpec(None, f(*args), (Top,))


@register(
    Intrinsic.Py_LoadGlobal, "__call__", create_shape=dict(oop=False)
)
def py_load_global(self: Judge, a_str: AbsVal) -> CallSpec:
    """
    TODO: S(self.glob) is UNSAFE here.
    Theoretically, 'S' shall not be used for
    a mutable data. This is a special case.
    """

    def slow_path():
        instance = None
        func = S(intrinsic("PyDict_LoadGlobal"))
        e_call = func(S(self.func), S(builtins), a_str)
        ret_types = (Top,)
        return CallSpec(instance, e_call, ret_types)

    def constant_key_path():
        instance = None
        hash_val = hash(a_str.base)
        func = S(intrinsic("PyDict_LoadGlobal_KnownHash"))
        e_call = func(
            S(self.func), S(builtins), a_str, lit(str(hash_val))
        )
        ret_types = (Top,)
        return CallSpec(instance, e_call, ret_types)

    if a_str.is_literal():
        if isinstance(a_str.base, str):
            attr = a_str.base
            if attr in self.abs_glob:
                a = self.abs_glob[attr]
                return CallSpec(a, a, possibly_return_types=(a.type,))

            return constant_key_path()
    return slow_path()


@register(bool, attr="__call__")
def py_call_bool_type(self: Judge, *args: AbsVal):
    if not args:
        # bool() = False
        constant_return = S(False)
        return CallSpec(
            constant_return, constant_return, (Values.A_Bool,)
        )
    if len(args) != 1:
        # bool(a, b, c) = False
        return NotImplemented
    # bool(a)
    arg = args[0]
    if isinstance(arg.type, S) and issubclass(arg.type.base, bool):
        constant_return = isinstance(arg, S) and arg or None
        return CallSpec(constant_return, arg, (Values.A_Bool,))
    return CallSpec(
        None,
        S(intrinsic("Py_CallBoolIfNecessary"))(arg),
        (Values.A_Bool,),
    )


@register(isinstance, create_shape=True)
def spec_isinstance(self: Judge, *args: AbsVal):
    if len(args) != 2:
        return NotImplemented
    l, r = args
    return_types = tuple({Values.A_Bool})
    if (
        isinstance(l.type, S)
        and isinstance(r, S)
        and isinstance(r.base, type)
    ):
        const = l.type == r or l.type.base in r.base.__bases__
        return CallSpec(S(const), S(const), return_types)

    func = S(intrinsic("PyObject_IsInstance"))
    return CallSpec(None, func(l, r), return_types)


@register(operator.__pow__, create_shape=True)
def spec_pow(self: Judge, l: AbsVal, r: AbsVal):
    if l.type == Values.A_Int:
        if r.type == Values.A_Int:
            py_int_power_int = S(intrinsic("Py_IntPowInt"))
            return_types = tuple({Values.A_Int})
            constant_result = None  # no constant result

            return CallSpec(
                constant_result, py_int_power_int(l, r), return_types
            )
    return NotImplemented


@register(len, create_shape=True)
def spec_len(self: Judge, *args: AbsVal):
    if len(args) != 1:
        return NotImplemented
    arg = args[0]

    func = S(intrinsic("PySequence_Length"))
    e_call = func(arg)
    return CallSpec(None, e_call, tuple({Values.A_Int}))


@register(operator.__add__, create_shape=True)
def spec_add(self: Judge, l: AbsVal, r: AbsVal):
    if l.type == Values.A_Int:
        if r.type == Values.A_Int:
            py_int_add_int = S(intrinsic("Py_IntAddInt"))
            return_types = tuple({Values.A_Int})
            constant_result = None  # no constant result
            return CallSpec(
                constant_result, py_int_add_int(l, r), return_types
            )
    return NotImplemented


@register(operator.__iadd__, create_shape=True)
def spec_add(self: Judge, l: AbsVal, r: AbsVal):
    if l.type == Values.A_Int:
        if r.type == Values.A_Int:
            py_int_add_int = S(intrinsic("Py_IntAddInt"))
            return_types = tuple({Values.A_Int})
            constant_result = None  # no constant result
            return CallSpec(
                constant_result, py_int_add_int(l, r), return_types
            )
    return NotImplemented


def spec_cmp(op):
    def spec_op(self: Judge, *args: AbsVal):
        if len(args) != 2:
            return NotImplemented
        l, r = args
        func_name = "PyObject_RichCompare"
        l_t = l.type
        r_t = r.type
        if (
            l_t.is_s()
            and r_t.is_s()
            and l_t.base in concrete_numeric_types
            and r_t.base in concrete_numeric_types
        ):
            if l_t.base == r_t.base:
                func_name = concrete_numeric_types[l_t.base]
            ret_types = tuple({Values.A_Bool})
        else:
            ret_types = tuple({Top})

        func = S(intrinsic(func_name))
        return CallSpec(None, func(l, r, lit(op)), ret_types)

    return spec_op


register(operator.__le__, create_shape=True)(spec_cmp("Py_LE"))
register(operator.__lt__, create_shape=True)(spec_cmp("Py_LT"))
register(operator.__ge__, create_shape=True)(spec_cmp("Py_GE"))
register(operator.__gt__, create_shape=True)(spec_cmp("Py_GT"))
register(operator.__eq__, create_shape=True)(spec_cmp("Py_EQ"))
register(operator.__ne__, create_shape=True)(spec_cmp("Py_NE"))


@register(math.sqrt, create_shape=True)
def spec_sqrt(self: Judge, a: AbsVal):
    if a.type == Values.A_Int:
        int_sqrt = S(intrinsic("Py_IntSqrt"))
        return CallSpec(None, int_sqrt(a), tuple({Values.A_Float}))
    return NotImplemented


@register(setattr, create_shape=True)
def call_setattr(self: Judge, *args: AbsVal):
    if len(args) != 3:
        return NotImplemented

    func = S(intrinsic("PyObject_SetAttr"))
    e_call = func(*args)
    return CallSpec(S(None), e_call, (Values.A_NoneType,))


@register(getattr, create_shape=True)
def call_getattr(self: Judge, *args: AbsVal):
    if len(args) != 2:
        return NotImplemented
    ret_types = (Top,)
    subject, attr = args
    # noinspection PyUnboundLocalVariable
    if (
        subject.type.is_s()
        and (shape := subject.type.shape)
        and (__getattr__ := shape.fields.get("__getattr__"))
    ):
        # noinspection PyUnboundLocalVariable
        __getattr__ = __getattr__
        if not shape.oop:
            args = [attr]
        if isinstance(__getattr__, S):
            r = self.spec(__getattr__, "__call__", *args)
            if r is not NotImplemented:
                return r
        else:
            r = __getattr__(self, *args)
            if r is not NotImplemented:
                return r

    func = S(intrinsic("PyObject_GetAttr"))
    e_call = func(subject, attr)
    instance = None
    return CallSpec(instance, e_call, ret_types)


@register(operator.__getitem__, create_shape=True)
def call_getitem(self: Judge, *args: AbsVal):
    if len(args) != 2:
        return NotImplemented
    subject, item = args
    ret_types = (Top,)
    sub_t = subject.type
    if sub_t not in (Top, Bot):
        if sub_t.shape and (
            dispatched := sub_t.shape.fields.get("__getitem__")
        ):
            # noinspection PyUnboundLocalVariable
            if isinstance(dispatched, FunctionType):
                # noinspection PyUnboundLocalVariable
                return dispatched(self, *args)
            return self.spec(subject, "__call__", *args)

    func = S(intrinsic("PyObject_GetItem"))
    e_call = func(subject, item)
    instance = None
    return CallSpec(instance, e_call, ret_types)


@register(list, attr="__getitem__")
def call_list_getitem(self: Judge, *args):
    if len(args) != 2:
        return NotImplemented
    ret_types = (Top,)
    subject, item = args
    func = S(intrinsic("PyList_GetItem"))
    e_call = func(subject, item)
    instance = None
    return CallSpec(instance, e_call, ret_types)


@register(dict, attr="__getitem__")
def call_list_getitem(self: Judge, *args):
    if len(args) != 2:
        return NotImplemented
    ret_types = (Top,)
    subject, item = args
    func = S(intrinsic("PyDict_GetItemWithError"))
    e_call = func(subject, item)
    instance = None
    return CallSpec(instance, e_call, ret_types)


@register(bytearray, attr="__getitem__")
def call_bytearray_getitem(self: Judge, *args):
    if len(args) != 2:

        return NotImplemented
    ret_types = (Values.A_Int,)
    subject, item = args
    func = S(intrinsic("PyObject_GetItem"))
    e_call = func(subject, item)
    instance = None
    return CallSpec(instance, e_call, ret_types)


@register(bytes, attr="join")
def call_bytearray_join(self: Judge, *args: AbsVal):
    if not args != 2:
        return NotImplemented
    sep, iters = args
    if (
        sep.type.is_s()
        and sep.type.base is bytes
        and iters.type.is_s()
        and issubclass(iters.type.base, Iterable)
    ):
        # https://sourcegraph.com/github.com/python/cpython@3.9/-/blob/Include/cpython/bytesobject.h#L36
        func = S(intrinsic("_PyBytes_Join"))
        e_call = func(sep, iters)
        return CallSpec(None, e_call, (S(bytes),))

    spec = self.no_spec(sep, "join", [iters])
    return CallSpec(None, spec.e_call, (S(bytes),))


@register(bytes, attr="__getitem__")
def call_bytearray_getitem(self: Judge, *args: AbsVal):
    if len(args) != 2:
        return NotImplemented
    ret_types = (Values.A_Int,)
    subject, item = args
    # Sequence protocol is slower:
    # if item.type.is_s() and issubclass(item.type.base, int):
    #     func = S(intrinsic("PySequence_GetItem"))
    # else:
    func = S(intrinsic("PyObject_GetItem"))
    e_call = func(subject, item)
    instance = None
    return CallSpec(instance, e_call, ret_types)


@register(operator.__setitem__, create_shape=True)
def call_getitem(self: Judge, *args: AbsVal):
    if len(args) != 3:
        # default python impl
        return NotImplemented
    subject, item, value = args
    func = S(intrinsic("PyObject_SetItem"))
    e_call = func(subject, item, value)
    instance = None
    ret_types = (Top,)
    return CallSpec(instance, e_call, ret_types)


@register(list, attr="copy")
def call_list_copy(self: Judge, *args: AbsVal):
    if len(args) != 1:
        return NotImplemented
    return CallSpec(
        None,
        S(Intrinsic.Py_CallMethod)(args[0], S("copy")),
        tuple({S(list)}),
    )


@register(list, attr="append")
def list_append_analysis(self: Judge, *args: AbsVal):
    if len(args) != 2:
        # rollback to CPython's default code
        return NotImplemented
    lst, elt = args

    return CallSpec(
        instance=None,  # return value is not static
        e_call=S(intrinsic("PyList_Append"))(lst, elt),
        possibly_return_types=tuple({S(type(None))}),
    )


@register(Intrinsic.Py_BuildList, create_shape=True)
def call_build_list(self: Judge, *args: AbsVal):
    ret_types = tuple({S(list)})
    func = S(intrinsic("PyList_Construct"))

    return CallSpec(None, func(*args), ret_types)


@register(io.BytesIO)
def call_bytes_io(self: Judge, *args: AbsVal):
    if len(args) != 1:
        return NotImplemented

    arg = args[0]
    func = S(Intrinsic.Py_CallFunction)
    abs_bytes_io = S(io.BytesIO)
    return CallSpec(None, func(abs_bytes_io, arg), (abs_bytes_io,))


next_type_maps = {io.BytesIO: bytes}


@register(operator.is_, create_shape=True)
def call_is(self: Judge, *args: AbsVal):
    if len(args) != 2:
        return NotImplemented
    ret_types = (Values.A_Bool,)
    l, r = args
    if l == r:
        return CallSpec(S(True), S(True), ret_types)
    if l.type.is_s() and r.type.is_s() and l.type.base != r.type.base:

        return CallSpec(S(False), S(False), ret_types)

    func = S(intrinsic("Py_AddressCompare"))
    return CallSpec(None, func(*args), ret_types)


@register(operator.__not__, create_shape=True)
def call_not_(self: Judge, *args: AbsVal):
    if len(args) != 1:
        return NotImplemented
    ret_types = (Values.A_Bool,)
    arg = args[0]
    if arg.is_literal():
        const = S(not arg.base)
        return CallSpec(const, const, ret_types)
    c = self.no_spec(S(operator.__not__), "__call__", list(args))
    return CallSpec(c.instance, c.e_call, ret_types)


@register(next, create_shape=True)
def call_next(self: Judge, *args: AbsVal):
    if len(args) not in (1, 2):
        return NotImplemented

    o = args[0]
    if o.type in (Top, Bot):
        return NotImplemented

    t = o.type.base
    if eltype := next_type_maps.get(t):
        ret_types = {S(eltype)}
    else:
        ret_types = {Top}

    if len(args) == 2:
        default = args[1]
        ret_types.add(default.type)
    func = S(Intrinsic.Py_CallFunction)

    ret_types = tuple(sorted(ret_types))
    return CallSpec(None, func(S(next), *args), ret_types)


# @register(int, "__init__")
# def call_int(self: Judge, *args: AbsVal):
#     return CallSpec(S(None), S(None), (Values.A_NoneType, ))


@register(int)
def call_int(self: Judge, t: AbsVal, *args: AbsVal):
    A_Int = S(int)
    return_types = (A_Int,)
    if len(args) == 0:
        return CallSpec(S(0), S(0), return_types)
    if len(args) != 1:
        return NotImplemented
    o = args[0]
    if o.type == A_Int:
        return CallSpec(None, o, return_types)

    func = S(intrinsic("PyNumber_Long"))
    return CallSpec(None, func(o), return_types)


# @lru_cache()
# def mk_call_type_n(N):
#     args = ",".join(f"x{a}" for a in range(N))
#     name = f"call_type{N}"
#     f = f"""
# def {name}(typ: AbsVal, {args}):
#     o = typ.__new__(typ, {args})
#     if not isinstance(o, typ):
#         return o
#     typ.__init__(o, {args})
#     return o
# """
#     scope = {}
#     exec(f, scope)
#     func = scope[name]
#     from diojit.user.client import jit
#
#     return jit(func, fixed_references=["isinstance"])
#
#
# @register(type)
# def call_type(self: Judge, typ: AbsVal, *args: AbsVal):
#     if typ == Values.A_Type and args:
#         if len(args) == 1:
#             arg = args[0]
#             if arg.type.is_s():
#                 a_t = arg.type
#                 return CallSpec(a_t, a_t, (Values.A_Type,))
#             func = S(intrinsic("PyObject_Type"))
#             return CallSpec(None, func(arg), (Values.A_Type,))
#         return NotImplemented
#     if typ.is_s():
#         return self.spec(
#             S(mk_call_type_n(len(args))), "__call__", [typ, *args]
#         )
#     return NotImplemented
