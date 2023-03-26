"""
Structures for managing graphics operations.
"""

try:
    long
except NameError:
    # Python 3
    long = int


class Bounds(object):
    """
    Manipulation of a signed bounding box.
    """

    def __init__(self, x0=1, y0=1, x1=0, y1=0):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

        if self.x0 > self.x1 or self.y0 > self.y1:
            self.clear()

    def __eq__(self, other):
        if self.x0 > self.x1 or self.y0 > self.y1:
            # Nothing matches if this box is unset
            return False

        if isinstance(other, Bounds):
            return (self.x0 == other.x0 and
                    self.y0 == other.y0 and
                    self.x1 == other.x1 and
                    self.y1 == other.y1)
        elif isinstance(other, tuple):
            return (self.x0 == other[0] and
                    self.y0 == other[1] and
                    self.x1 == other[2] and
                    self.y1 == other[3])

        return NotImplemented

    def __repr__(self):
        if not self:
            return "<{}(unset)>".format(self.__class__.__name__)
        return "<{}({},{} - {},{})>".format(self.__class__.__name__,
                                            self.x0, self.y0,
                                            self.x1, self.y1)

    def merge(self, other):
        """
        Merge a second bounding box (or point) with ourselves.
        """
        if isinstance(other, tuple):
            # If it's a tuple, we'll treat it as coordinates.
            if len(other) == 2:
                self.x0 = min(self.x0, other[0])
                self.y0 = min(self.y0, other[1])
                self.x1 = max(self.x1, other[0])
                self.y1 = max(self.y1, other[1])
            elif len(other) == 4:
                self.x0 = min(self.x0, other[0])
                self.y0 = min(self.y0, other[1])
                self.x1 = max(self.x1, other[2])
                self.y1 = max(self.y1, other[3])
            else:
                raise NotImplementedError("{} cannot be added to a {}-tuple".format(self.__class__.__name__,
                                                                                    len(other)))

        elif isinstance(other, Bounds):
            self.x0 = min(self.x0, other.x0)
            self.y0 = min(self.y0, other.y0)
            self.x1 = max(self.x1, other.x1)
            self.y1 = max(self.y1, other.y1)

        else:
            raise NotImplementedError("{} cannot be added to an object of type {}".format(self.__class__.__name__,
                                                                                          other.__class__.__name__))
        return self

    def __iadd__(self, other):
        return self.merge(other)

    def __bool__(self):
        """
        Whether the bounds are valid or not.
        """
        return self.x0 <= self.x1 and self.y0 <= self.y1
    __nonzero__ = __bool__

    def __getitem__(self, index):
        """
        Read like a tuple.
        """
        if index < 2:
            if index == 0:
                return self.x0
            return self.y0
        elif index < 4:
            if index == 2:
                return self.y1
            return self.y1
        raise IndexError("Index {} out of range for 4 element tuple-like class {}".format(index, self.__class__.__name__))

    def __len__(self):
        return 4

    def clear(self):
        self.x0 = 0x7FFFFFFF
        self.y0 = 0x7FFFFFFF
        self.x1 = -0x7FFFFFFF
        self.y1 = -0x7FFFFFFF
        return self

    def copy(self):
        return self.__class__(x0=self.x0, y0=self.y0, x1=self.x1, y1=self.y1)


class Transform(object):
    """
    A Transform object is the base for transforming coordinates.

    There are two commonly used transformation methods in RISC OS:

    * 2-dimensional scaling ratios
    * 6-element matrix, using 16.16 fixed point values.

    Although the RISC OS values are fixed point and scaled, the values in these objects
    are converted to floating point.

    Usage:

    (dx, dy) = transform.apply(sx, sy)
        - transform a single coordinate pair

    (bl, br, tl, tr) = transform.quad(x0, y0, x1, y1)
        - transform the 4 corners of the supplied box as tuples of coordinate pairs

    (x0, y0, x1, y1) = transform.bbox(x0, y0, x1, y1)
        - transform the 4 corners of the supplied box, and turn the new limits of the box.

    new_transform = transform.multiply(other_transform)
        - apply the transformation matrices to one another.

    new_transform = transform.copy()
        - create a copy of the tranformation matrix

    bool(transform)
        - False if the transform is an identity
          True if the transform will make changes

    transform.scale
        - The equivalent Scale tranformation, or None if the transform cannot be represented as a Scale.

    transform.matrix
        - The equivalent Matrix transformation, or None if the tranform cannot be represented as a Matrix.
    """
    scale = None
    matrix = None

    def __init__(self):
        pass

    def copy(self):
        raise NotImplementedError("{}.copy is not implemented".format(self.__class__.__name__))

    def apply(self, x, y):
        raise NotImplementedError("{}.apply is not implemented".format(self.__class__.__name__))

    def apply_nooffset(self, x, y):
        raise NotImplementedError("{}.apply_nooffset is not implemented".format(self.__class__.__name__))

    def __bool__(self):
        raise NotImplementedError("{}.__bool__ is not implemented".format(self.__class__.__name__))

    def __nonzero__(self):
        return self.__bool__()

    def valid(self):
        raise NotImplementedError("{}.valid is not implemented".format(self.__class__.__name__))

    def multiply(self, other_transform):
        this = self.matrix
        if this is None:
            raise NotImplementedError("{}.multiply is not possible".format(self.__class__.__name__))
        other = other_transform.matrix
        if other is None:
            raise NotImplementedError("{}.multiply is not possible on a {}".format(self.__class__.__name__,
                                                                                   other_transform.__class__.__name__))

        new_matrix = Matrix()
        new_matrix.a = this.a * other.a + this.c * other.b
        new_matrix.c = this.a * other.c + this.c * other.d
        new_matrix.e = this.a * other.e + this.c * other.f + this.e
        new_matrix.b = this.b * other.a + this.d * other.b
        new_matrix.d = this.b * other.c + this.d * other.d
        new_matrix.f = this.b * other.e + this.d * other.f + this.f
        return new_matrix

    def quad(self, x0, y0, x1, y1):
        """
        Obtain the four coordinates of the corners of a rectangle.

        @param: x0, y0:     bottom left
        @param: x1, y1:     top right

        @return: Tuple of (bl, br, tl, tr), where each is a tuple of (x, y).
        """
        bl = self.apply(x0, y0)
        br = self.apply(x1, y0)
        tl = self.apply(x0, y1)
        tr = self.apply(x1, y1)
        return (bl, br, tl, tr)

    def bbox(self, x0, y0, x1, y1):
        """
        Apply the transformation to a bounding box to produce a new bounding box.
        """
        (bl, br, tl, tr) = self.quad(x0, y0, x1, y1)

        x0 = min(bl[0], br[0], tl[0], tr[0])
        x1 = max(bl[0], br[0], tl[0], tr[0])
        y0 = min(bl[1], br[1], tl[1], tr[1])
        y1 = max(bl[1], br[1], tl[1], tr[1])

        return (x0, y0, x1, y1)


class Matrix(Transform):
    """
    Matrix transformation object.

    A 6-element matrix.

    Usage:

    matrix = Matrix(ro, array=(1, 0, 0, 1, 0, 0))
        - Constructs a new identity matrix.

    matrix = Matrix(ro, array=(-1, 0, 0, 1, 0, 0))
        - Matrix which flips the coordinates about the y axis.
    """
    allowed_error = 1.0/65536
    maximum_ratios = 1<<15

    def __init__(self, array=None):
        super(Matrix, self).__init__()

        # Default to an identity matrix
        if array:
            (self.a, self.b, self.c, self.d, self.e, self.f) = array
        else:
            self.a = 1
            self.b = 0
            self.c = 0
            self.d = 1
            self.e = 0
            self.f = 0
        self.matrix = self

    def __repr__(self):
        return "<Matrix(%12.4f, %12.4f, %12.4f, %12.4f, %9i, %9i)>" \
                % (self.a, self.b, self.c, self.d, self.e, self.f)

    def copy(self):
        new_transform = Matrix()
        new_transform.a = self.a
        new_transform.b = self.b
        new_transform.c = self.c
        new_transform.d = self.d
        new_transform.e = self.e
        new_transform.f = self.f
        return new_transform

    def apply(self, x, y):
        """
        Apply the transformation to a coordinate pair.
        """
        x = float(x)
        y = float(y)
        return (self.a * x + self.c * y + self.e,
                self.b * x + self.d * y + self.f)

    def apply_nooffset(self, x, y):
        """
        Apply the transformation to a coordinate pair, omitting any offset.
        """
        x = float(x)
        y = float(y)
        return (self.a * x + self.c * y,
                self.b * x + self.d * y)

    def _ratio(self, value):
        """
        Return the ratio to use for a floating point value.

        This is only approximate, but the error will be small enough that it does not matter for the
        scale that we use on RISC OS.

        @return: Tuple of (mult, div)
        """
        if value == int(value):
            return (value, 1)

        mult = value * 2
        div = 2

        # Try multiplying up to get a better error ratio
        error = abs((float(int(mult * 0x10000)) / int(div * 0x10000)) - value)
        if error:
            #print("ratio(1) %0.7f, %i : %i : error %0.7f" % (value, mult, div, error))
            for allowed_error in (0, self.allowed_error):
                # First we try to get an exact answer, then we just try to get a better ratio
                if error <= allowed_error:
                    break
                for factor in range(3, 255, 2):
                    newmult = value * 2 * factor
                    newdiv = 2 * factor
                    if newmult > self.maximum_ratios or newdiv > self.maximum_ratios:
                        break
                    newvalue = float(int(newmult * 0x10000)) / int(newdiv * 0x10000)
                    newerror = abs(newvalue - value)
                    #print("  multiplier %i : ratio %0.7f, %i : %i : error %0.7f" % (factor, newvalue, newmult, newdiv, newerror))
                    if newerror < error:
                        mult = newmult
                        div = newdiv
                        error = newerror
                        if error <= allowed_error:
                            break

        mult = int(mult * 0x10000)
        div = int(div * 0x10000)

        # Shift down so that the lowest set bit is at the bottom (ie repeatedly divide by 2 until we cannot any longer)
        lowest_set_bit = min(mult & ~(mult - 1),
                             div & ~(div - 1))
        mult = mult / lowest_set_bit
        div = div / lowest_set_bit

        #print("ratio(2) %0.7f, %i : %i : error %0.7f" % (value, mult, div, error))
        # Look for factors
        still_going = True
        while still_going and False:
            still_going = False
            for factor in range(3, min(mult, div), 2):
                while True:
                    newmult = float(mult) / factor
                    newdiv = float(div) / factor
                    if newmult == int(newmult) and \
                       newdiv == int(newdiv):
                        # We got an exact division; so we can keep searching
                        newvalue = float(int(newmult)) / int(newdiv)
                        #print("  factor %i : ratio %0.7f, %i : %i" % (factor, newvalue, newmult, newdiv))
                        mult = newmult
                        div = newdiv
                        still_going = True
                    else:
                        break

        return (mult, div)

    @property
    def scale(self):
        """
        Return a Scale object, if this is a simple scaling matrix, or None if not.

        @return: Scale object equivalent to this transformation matrix,
                 or None if it cannot be represented as a Scale.
        """
        if self.b or self.c or self.e or self.f:
            return None

        scale = Scale()
        (scale.xmult, scale.xdiv) = self._ratio(self.a)
        (scale.ymult, scale.ydiv) = self._ratio(self.d)
        return scale

    def __bool__(self):
        """
        Transform is 'true' if it is not an identity.
        """
        if self.a == 1 and self.b == 0 and \
           self.c == 0 and self.d == 1 and \
           self.e == 0 and self.f == 0:
            return False
        return True

    def valid(self):
        """
        Whether the transformation would produce an area on the screen.
        """
        determinant = self.a * self.d - self.b * self.c
        if determinant == 0:
            return False
        return True


class Scale(Transform):
    """
    Scaling block.

    2 ratios for the x and y dimensions.
    """

    def __init__(self, array=None):
        super(Scale, self).__init__()

        # Default to an identity scale
        if array:
            self.xmult = array[0]
            self.ymult = array[1]
            self.xdiv = array[2]
            self.ydiv = array[3]
        else:
            self.xmult = 1
            self.ymult = 1
            self.xdiv = 1
            self.ydiv = 1
        self.scale = self

    def __repr__(self):
        return "<Scale(%i/%i, %i/%i => %12.4f, %12.4f)>" \
                % (self.xmult, self.xdiv,
                   self.ymult, self.ydiv,
                   float(self.xmult) / self.xdiv,
                   float(self.ymult) / self.ydiv)

    def copy(self):
        new_scale = Scale()
        new_scale.xmult = self.xmult
        new_scale.ymult = self.ymult
        new_scale.xdiv = self.xdiv
        new_scale.ydiv = self.ydiv
        return new_scale

    def apply(self, x, y):
        return (int(float(x) * self.xmult / self.xdiv),
                int(float(y) * self.ymult / self.ydiv))
    apply_nooffset = apply

    @property
    def matrix(self):
        """
        Return the transformation matrix for this scale block.

        @return: Transform for this scale block
                 or None if there isn't a Transform (never true)
        """
        matrix = Matrix()
        matrix.a = float(self.xmult) / self.xdiv
        matrix.d = float(self.ymult) / self.ydiv
        return matrix

    def __bool__(self):
        """
        Transform is 'true' if it is not an identity.
        """
        if self.xmult == 1 and self.xdiv == 1 and \
           self.ymult == 1 and self.ydiv == 1:
            return False
        return True

    def valid(self):
        """
        Whether the transformation would produce an area on the screen.
        """
        if self.xmult == 0 or self.xdiv == 0:
            return False
        if self.ymult == 0 or self.ydiv == 0:
            return False
        return True


def Translate(x, y):
    return Matrix(array=(1, 0, 0, 1, x, y))
