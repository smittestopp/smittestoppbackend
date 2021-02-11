import pytest
from corona.config import Config


def test_read_simple():
    config = Config(dict(foo=dict(bar=5, zot=False, string="foobar")))

    assert config.foo.bar == 5
    assert not config.foo.zot
    assert config.foo.string == 'foobar'


def test_read_inferred_int():
    config = Config(dict(foo=dict(bar="5", zot=False, string="foobar")))

    assert config.foo.bar == 5


def test_read_inferred_bool_NOT():
    config = Config(dict(foo=dict(bar=5, zot="False", string="foobar")))

    assert not config.foo.zot


def test_read_inferred_bool_yes():
    config = Config(dict(foo=dict(bar=5, zot="Yes", string="foobar")))

    assert config.foo.zot


def test_read_inferred_bool_NO():
    config = Config(dict(foo=dict(bar=5, zot="NO", string="foobar")))

    assert not config.foo.zot


def test_read_inferred_bool():
    config = Config(dict(foo=dict(bar=5, zot="True", string="foobar")))

    assert config.foo.zot


def test_read_and_update():
    config = Config(dict(foo=dict(bar=5, zot="False", string="foobar")))
    config.add_section("foo", dict(bar="6", zot="True"))

    assert config.foo.bar == 6
    assert config.foo.zot
