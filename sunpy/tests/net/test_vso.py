# -*- coding: utf-8 -*-
# Author: Florian Mayer <florian.mayer@bitsrc.org>

#pylint: disable=W0613

from __future__ import absolute_import

import pytest

from sunpy.net import vso
from sunpy.net.vso import attrs as va
from sunpy.net import attr

from sunpy.util.util import energy, frequency

def pytest_funcarg__eit(request):
    return va.Instrument('eit')


def pytest_funcarg__client(request):
    return vso.VSOClient()


def pytest_funcarg__iclient(request):
    return vso.InteractiveVSOClient()


def test_simpleattr_apply():
    a = attr.ValueAttr({('test', ): 1})
    dct = {}
    va.walker.apply(a, None, dct)
    assert dct['test'] == 1


def test_simpleattr_create(client):
    a = attr.ValueAttr({('instrument', ): 'eit'})
    assert va.walker.create(a, client.api)[0].instrument == 'eit'


def test_simpleattr_and_duplicate():
    attr = va.Instrument('foo')
    pytest.raises(TypeError, lambda: attr & va.Instrument('bar'))
    attr |= va.Source('foo')
    pytest.raises(TypeError, lambda: attr & va.Instrument('bar'))
    otherattr = va.Instrument('foo') | va.Source('foo')
    pytest.raises(TypeError, lambda: attr & otherattr)
    pytest.raises(TypeError, lambda: (attr | otherattr) & va.Instrument('bar'))
    tst = va.Instrument('foo') & va.Source('foo')
    pytest.raises(TypeError, lambda: tst & tst)


def test_simpleattr_or_eq():
    attr = va.Instrument('eit')
    
    assert attr | attr == attr
    assert attr | va.Instrument('eit') == attr


def test_complexattr_apply():
    tst = {('test', 'foo'): 'a', ('test', 'bar'): 'b'}
    a = attr.ValueAttr(tst)
    dct = {'test': {}}
    va.walker.apply(a, None, dct)
    assert dct['test'] == {'foo': 'a', 'bar': 'b'}


def test_complexattr_create(client):
    a = attr.ValueAttr({('time', 'start'): 'test'})
    assert vso.walker.create(a, client.api)[0].time.start == 'test'


def test_complexattr_and_duplicate():
    attr = va.Time((2011, 1, 1), (2011, 1, 1, 1))
    pytest.raises(
        TypeError,
        lambda: attr & va.Time((2011, 2, 1), (2011, 2, 1, 1))
    )
    attr |= va.Source('foo')
    pytest.raises(
        TypeError,
        lambda: attr & va.Time((2011, 2, 1), (2011, 2, 1, 1))
    )


def test_complexattr_or_eq():
    attr = va.Time((2011, 1, 1), (2011, 1, 1, 1))
    
    assert attr | attr == attr
    assert attr | va.Time((2011, 1, 1), (2011, 1, 1, 1)) == attr


def test_attror_and():
    attr = va.Instrument('foo') | va.Instrument('bar')
    one = attr & va.Source('bar')
    other = (
        (va.Instrument('foo') & va.Source('bar')) | 
        (va.Instrument('bar') & va.Source('bar'))
    )
    assert one == other


def test_wave_toangstrom():
    for name, factor in energy:
        w = va.Wave(62 / factor, 62 / factor, name)
        assert int(w.min) == 199
    
    w = va.Wave(62, 62, 'eV')
    assert int(w.min) == 199
    w = va.Wave(62e-3, 62e-3, 'keV')
    assert int(w.min) == 199

    for name, factor in frequency:
        w = va.Wave(1.506e16 / factor, 1.506e16 / factor, name)
        assert int(w.min) == 199
    
    w = va.Wave(1.506e16, 1.506e16, 'Hz')
    assert int(w.min) == 199
    w = va.Wave(1.506e7, 1.506e7, 'GHz')
    assert int(w.min) == 199


def test_time_xor():
    one = va.Time((2010, 1, 1), (2010, 1, 2))
    a = one ^ va.Time((2010, 1, 1, 1), (2010, 1, 1, 2))
    
    assert a == attr.AttrOr(
        [va.Time((2010, 1, 1), (2010, 1, 1, 1)),
         va.Time((2010, 1, 1, 2), (2010, 1, 2))]
    )
    
    a ^= va.Time((2010, 1, 1, 4), (2010, 1, 1, 5))
    assert a == attr.AttrOr(
        [va.Time((2010, 1, 1), (2010, 1, 1, 1)),
         va.Time((2010, 1, 1, 2), (2010, 1, 1, 4)),
         va.Time((2010, 1, 1, 5), (2010, 1, 2))]
    )

def test_wave_xor():
    one = va.Wave(0, 1000)
    a = one ^ va.Wave(200, 400)
    
    assert a == attr.AttrOr([va.Wave(0, 200), va.Wave(400, 1000)])
    
    a ^= va.Wave(600, 800)
    
    assert a == attr.AttrOr(
        [va.Wave(0, 200), va.Wave(400, 600), va.Wave(800, 1000)])
