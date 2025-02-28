########################################################################
#
#       License: BSD
#       Created: August 5, 2010
#       Author:  Francesc Alted - francesc@blosc.org
#
########################################################################

"""Utility functions (mostly private).
"""

from __future__ import absolute_import

import os
import os.path
import subprocess
import math
from time import time
import numpy as np


def show_stats(explain, tref):
    "Show the used memory (only works for Linux 2.6.x)."
    # Build the command to obtain memory info
    cmd = "cat /proc/%s/status" % os.getpid()
    sout = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout
    for line in sout:
        if line.startswith("VmSize:"):
            vmsize = int(line.split()[1])
        elif line.startswith("VmRSS:"):
            vmrss = int(line.split()[1])
        elif line.startswith("VmData:"):
            vmdata = int(line.split()[1])
        elif line.startswith("VmStk:"):
            vmstk = int(line.split()[1])
        elif line.startswith("VmExe:"):
            vmexe = int(line.split()[1])
        elif line.startswith("VmLib:"):
            vmlib = int(line.split()[1])
    sout.close()
    print("Memory usage: ******* %s *******" % explain)
    print("VmSize: %7s kB\tVmRSS: %7s kB" % (vmsize, vmrss))
    print("VmData: %7s kB\tVmStk: %7s kB" % (vmdata, vmstk))
    print("VmExe:  %7s kB\tVmLib: %7s kB" % (vmexe, vmlib))
    tnow = time()
    print("WallClock time:", round(tnow - tref, 3))
    return tnow


##### Code for computing optimum chunksize follows  #####

def csformula(expectedsizeinMB):
    """Return the fitted chunksize for expectedsizeinMB."""
    # For a basesize of 4 KB, this will return:
    # 16 KB for datasets <= .1 KB
    # 256 KB for datasets == 1 MB
    # 4 MB for datasets >= 10 GB
    # The next figure is based on experiments with 'movielens-bench' repo
    basesize = 4 * 1024
    return basesize * int(2**(math.log10(expectedsizeinMB)+6))


def limit_es(expectedsizeinMB):
    """Protection against creating too small or too large chunks."""
    if expectedsizeinMB < 1e-4:     # < .1 KB
        expectedsizeinMB = 1e-4
    elif expectedsizeinMB > 1e4:    # > 10 GB
        expectedsizeinMB = 1e4
    return expectedsizeinMB


def calc_chunksize(expectedsizeinMB):
    """Compute the optimum chunksize for memory I/O in carray/ctable.

    carray stores the data in chunks and there is an optimal length for
    this chunk for compression purposes (it is around 1 MB for modern
    processors).  However, due to the implementation, carray logic needs
    to always reserve all this space in-memory.  Booking 1 MB is not a
    drawback for large carrays (>> 1 MB), but for smaller ones this is
    too much overhead.

    The tuning of the chunksize parameter affects the performance and
    the memory consumed.  This is based on my own experiments and, as
    always, your mileage may vary.
    """

    expectedsizeinMB = limit_es(expectedsizeinMB)
    zone = int(math.log10(expectedsizeinMB))
    expectedsizeinMB = 10**zone
    chunksize = csformula(expectedsizeinMB)
    return chunksize


def get_len_of_range(start, stop, step):
    """Get the length of a (start, stop, step) range."""
    n = 0
    if start < stop:
        n = ((stop - start - 1) // step + 1)
    return n


def to_ndarray(array, dtype, arrlen=None, safe=True):
    """Convert object to a ndarray."""

    if not safe:
        return array

    if not isinstance(array, np.ndarray) and dtype is None:
        array = np.array(array)

    # Arrays with a 0 stride are special
    if type(array) == np.ndarray and len(array.strides) and array.strides[0] == 0:
        if dtype is not None and array.dtype != dtype.base:
            raise TypeError("dtypes do not match")
        return array

    # Ensure that we have an ndarray of the correct dtype
    if dtype is not None:
        if type(array) != np.ndarray or array.dtype != dtype.base:
            try:
                array = np.array(array, dtype=dtype.base)
            except ValueError:
                raise ValueError("cannot convert to an ndarray object")

    # We need a contiguous array
    if not array.flags.contiguous:
        array = array.copy()

    # We treat scalars like undimensional arrays
    if len(array.shape) == 0:
        array.shape = (1,)

    # Check if we need a broadcast
    if arrlen is not None and arrlen != len(array):
        array2 = np.empty(shape=(arrlen,), dtype=dtype)
        array2[:] = array   # broadcast
        array = array2

    return array


def human_readable_size(size):
    """Return a string for better assessing large number of bytes."""
    if size < 2**10:
        return "%s" % size
    elif size < 2**20:
        return "%.2f KB" % (size / float(2**10))
    elif size < 2**30:
        return "%.2f MB" % (size / float(2**20))
    elif size < 2**40:
        return "%.2f GB" % (size / float(2**30))
    else:
        return "%.2f TB" % (size / float(2**40))


def build_carray(array, rootdir):
    """ Used in ctable.__reduce__

    Pickling functions can't be in pyx files.  Putting this tiny helper
    function here instead.
    """
    from bcolz import carray
    if rootdir:
        return carray(rootdir=rootdir)
    else:
        return carray(array)


def quantize(data, significant_digits):
    """Quantize data to improve compression.

    Data is quantized using around(scale*data)/scale, where scale is
    2**bits, and bits is determined from the significant_digits.  For
    example, if significant_digits=1, bits will be 4.

    """
    import math

    if data.dtype.kind != 'f':
        raise TypeError("quantize is meant only for floating point data")

    if not significant_digits:
        return data

    precision = 10. ** -significant_digits
    exp = math.log(precision, 10)
    if exp < 0:
        exp = int(math.floor(exp))
    else:
        exp = int(math.ceil(exp))
    bits = math.ceil(math.log(10. ** -exp, 2))
    scale = 2. ** bits
    return np.around(scale * data) / scale



# Main part
# =========
if __name__ == '__main__':
    print(human_readable_size(1023))
    print(human_readable_size(10234))
    print(human_readable_size(10234*100))
    print(human_readable_size(10234*10000))
    print(human_readable_size(10234*1000000))
    print(human_readable_size(10234*100000000))
    print(human_readable_size(10234*1000000000))


# Local Variables:
# mode: python
# tab-width: 4
# fill-column: 72
# End:
