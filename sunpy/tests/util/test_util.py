from __future__ import absolute_import

from datetime import datetime
from sunpy.util import util
from numpy.testing import assert_almost_equal

LANDING = datetime(1966, 2, 3)

def test_anytim_tuple():
    assert util.anytim((1966, 2, 3)) == LANDING

def test_anytim_int():
    assert util.anytim(765548612.0) == datetime(2003, 4, 5, 12, 23, 32)
    assert util.anytim(1009685652.0) == datetime(2010, 12, 30, 4, 14, 12)

def test_anytim_ISO():
    assert util.anytim('1966-02-03') == LANDING
    assert (
        util.anytim('1966-02-03T20:17:40') == datetime(1966, 2, 3, 20, 17, 40)
    )
    assert (
        util.anytim('19660203T201740') == datetime(1966, 2, 3, 20, 17, 40)
    )
    
    lst = [
        ('2007-05-04T21:08:12.999999', datetime(2007, 5, 4, 21, 8, 12, 999999)),
        ('20070504T210812.999999', datetime(2007, 5, 4, 21, 8, 12, 999999)),
        ('2007/05/04 21:08:12.999999', datetime(2007, 5, 4, 21, 8, 12, 999999)),
        ('2007-05-04 21:08:12.999999', datetime(2007, 5, 4, 21, 8, 12, 999999)),
        ('2007/05/04 21:08:12', datetime(2007, 5, 4, 21, 8, 12)),
        ('2007-05-04 21:08:12', datetime(2007, 5, 4, 21, 8, 12)),
        ('2007-05-04 21:08', datetime(2007, 5, 4, 21, 8)),
        ('2007-05-04T21:08:12', datetime(2007, 5, 4, 21, 8, 12)),
        ('20070504T210812', datetime(2007, 5, 4, 21, 8, 12)),
        ('2007-May-04 21:08:12', datetime(2007, 5, 4, 21, 8, 12)),
        ('2007-May-04 21:08', datetime(2007, 5, 4, 21, 8)),
        ('2007-May-04', datetime(2007, 5, 4)),
        ('2007-05-04', datetime(2007, 5, 4)),
        ('2007/05/04', datetime(2007, 5, 4)),
        ('20070504_210812', datetime(2007, 5, 4, 21, 8, 12)),
    ]
    
    for k, v in lst:
        assert util.anytim(k) == v

def test_julian_day():
    assert util.julian_day('1900-01-01 12:00') == 2415021.0
    assert util.julian_day(LANDING) == 2439159.5
    result = util.julian_day('2000-03-01 15:30:26')
    assert_almost_equal(result, 2451605.1461111, decimal=3)

    
def test_break_time():
    assert util.break_time(datetime(2007, 5, 4, 21, 8, 12)) == '20070504_210812'
