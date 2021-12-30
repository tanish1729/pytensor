import os.path as path
from tempfile import mkdtemp

import numpy as np
import pytest

import aesara.tensor as at
from aesara.configdefaults import config
from aesara.tensor.type import TensorType


def test_numpy_dtype():
    test_type = TensorType(np.int32, [])
    assert test_type.dtype == "int32"


def test_in_same_class():
    test_type = TensorType(config.floatX, [False, False])
    test_type2 = TensorType(config.floatX, [False, True])

    assert test_type.in_same_class(test_type)
    assert not test_type.in_same_class(test_type2)


def test_is_super():
    test_type = TensorType(config.floatX, [False, False])
    test_type2 = TensorType(config.floatX, [False, True])

    assert test_type.is_super(test_type)
    assert test_type.is_super(test_type2)
    assert not test_type2.is_super(test_type)

    test_type3 = TensorType(config.floatX, [False, False, False])
    assert not test_type3.is_super(test_type)


def test_convert_variable():
    test_type = TensorType(config.floatX, [False, False])
    test_var = test_type()

    test_type2 = TensorType(config.floatX, [True, False])
    test_var2 = test_type2()

    res = test_type.convert_variable(test_var)
    assert res is test_var

    res = test_type.convert_variable(test_var2)
    assert res is test_var2

    res = test_type2.convert_variable(test_var)
    assert res.type == test_type2

    test_type3 = TensorType(config.floatX, [True, False, True])
    test_var3 = test_type3()

    res = test_type2.convert_variable(test_var3)
    assert res is None

    const_var = at.as_tensor([[1, 2], [3, 4]], dtype=config.floatX)
    res = test_type.convert_variable(const_var)
    assert res is const_var


def test_filter_variable():
    test_type = TensorType(config.floatX, [])

    with pytest.raises(TypeError):
        test_type.filter(test_type())

    test_type = TensorType(config.floatX, [True, False])

    with pytest.raises(TypeError):
        test_type.filter(np.empty((0, 1), dtype=config.floatX))

    with pytest.raises(TypeError, match=".*not aligned.*"):
        test_val = np.empty((1, 2), dtype=config.floatX)
        test_val.flags.aligned = False
        test_type.filter(test_val)

    with pytest.raises(ValueError, match="Non-finite"):
        test_type.filter_checks_isfinite = True
        test_type.filter(np.full((1, 2), np.inf, dtype=config.floatX))

    test_type2 = TensorType(config.floatX, [False, False])
    test_var = test_type()
    test_var2 = test_type2()

    res = test_type.filter_variable(test_var, allow_convert=True)
    assert res is test_var

    # Make sure it returns the more specific type
    res = test_type.filter_variable(test_var2, allow_convert=True)
    assert res.type == test_type


def test_filter_strict():
    test_type = TensorType(config.floatX, [])

    with pytest.raises(TypeError):
        test_type.filter(1, strict=True)

    with pytest.raises(TypeError):
        test_type.filter(np.array(1, dtype=int), strict=True)


def test_filter_ndarray_subclass():
    """Make sure `TensorType.filter` can handle NumPy `ndarray` subclasses."""
    test_type = TensorType(config.floatX, [False])

    class MyNdarray(np.ndarray):
        pass

    test_val = np.array([1.0], dtype=config.floatX).view(MyNdarray)
    assert isinstance(test_val, MyNdarray)

    res = test_type.filter(test_val)
    assert isinstance(res, MyNdarray)
    assert res is test_val


def test_filter_float_subclass():
    """Make sure `TensorType.filter` can handle `float` subclasses."""
    with config.change_flags(floatX="float64"):
        test_type = TensorType("float64", broadcastable=[])

        nan = np.array([np.nan], dtype="float64")[0]
        assert isinstance(nan, float) and not isinstance(nan, np.ndarray)

        filtered_nan = test_type.filter(nan)
        assert isinstance(filtered_nan, np.ndarray)

    with config.change_flags(floatX="float32"):
        # Try again, except this time `nan` isn't a `float`
        test_type = TensorType("float32", broadcastable=[])

        nan = np.array([np.nan], dtype="float32")[0]
        assert isinstance(nan, np.floating) and not isinstance(nan, np.ndarray)

        filtered_nan = test_type.filter(nan)
        assert isinstance(filtered_nan, np.ndarray)


def test_filter_memmap():
    r"""Make sure `TensorType.filter` can handle NumPy `memmap`\s subclasses."""
    data = np.arange(12, dtype=config.floatX)
    data.resize((3, 4))
    filename = path.join(mkdtemp(), "newfile.dat")
    fp = np.memmap(filename, dtype=config.floatX, mode="w+", shape=(3, 4))

    test_type = TensorType(config.floatX, [False, False])

    res = test_type.filter(fp)
    assert res is fp


def test_tensor_values_eq_approx():
    # test, inf, -inf and nan equal themselves
    a = np.asarray([-np.inf, -1, 0, 1, np.inf, np.nan])
    with pytest.warns(RuntimeWarning):
        assert TensorType.values_eq_approx(a, a)

    # test inf, -inf don't equal themselves
    b = np.asarray([np.inf, -1, 0, 1, np.inf, np.nan])
    with pytest.warns(RuntimeWarning):
        assert not TensorType.values_eq_approx(a, b)
    b = np.asarray([-np.inf, -1, 0, 1, -np.inf, np.nan])
    with pytest.warns(RuntimeWarning):
        assert not TensorType.values_eq_approx(a, b)

    # test allow_remove_inf
    b = np.asarray([np.inf, -1, 0, 1, 5, np.nan])
    assert TensorType.values_eq_approx(a, b, allow_remove_inf=True)
    b = np.asarray([np.inf, -1, 0, 1, 5, 6])
    assert not TensorType.values_eq_approx(a, b, allow_remove_inf=True)

    # test allow_remove_nan
    b = np.asarray([np.inf, -1, 0, 1, 5, np.nan])
    assert not TensorType.values_eq_approx(a, b, allow_remove_nan=False)
    b = np.asarray([-np.inf, -1, 0, 1, np.inf, 6])
    with pytest.warns(RuntimeWarning):
        assert not TensorType.values_eq_approx(a, b, allow_remove_nan=False)
