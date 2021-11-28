import datetime

from interpersonal.sitetypes.base import slugify


def test_slugify():
    inout = {
        "In this essay I will - without the slightest bit of concern - grapple,": "in-this-essay-i-will-without-the-slightest-bit-of",
        "": datetime.datetime.now().strftime("%Y%m%d-%H%M"),
    }
    for inp, outp in inout.items():
        assert slugify(inp) == outp
