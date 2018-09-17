import os
import sys
import pytest

# import the tlcontracts module so no pip install is necessary
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture()
def tester():
    """ethereum.tools.tester compatible class"""

    class tester:
        pass

    t = tester()
    t.k0 = b"\x04HR\xb2\xa6p\xad\xe5@~x\xfb(c\xc5\x1d\xe9\xfc\xb9eB\xa0q\x86\xfe:\xed\xa6\xbb\x8a\x11m"
    t.a0 = b"\x82\xa9x\xb3\xf5\x96*[\tW\xd9\xee\x9e\xefG.\xe5[B\xf1"
    return t
