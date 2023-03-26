#!/usr/bin/env python
"""
Describe memory regions.
"""

import io


try:
    long
except NameError:
    # Python 3
    long = int


class RegionLabel(object):
    """
    Textual label for a region on the memory map.

    The label is plain text, with embedded \n for line breaks.
    The position is a tuple describing the position of the label relative to the memory region.
    The first element of the tuple is the x position; the second is the y position.
    The first element has values prefixed by 'i' for inside the memory region, and 'e' for external to the region:
        `il` - inside the region, left aligned
        `ic` - inside the region, centred
        `ir` - inside the region, right aligned
        `el` - outside the region, on the left, aligned right against the region's edge
        `elm` - outside the region, on the left, mid-way from the region's edge, centred
        `elf` - outside the region, on the left, aligned left, far from the region's edge
        `er` - outside the region, on the right, aligned left against the region's edge
        `erm` - outside the region, on the right, mid-way from the region's edge, centred
        `erf` - outside the region, on the right, aligned right, far from the region's edge
    The second element has values prefixed by 'i' for inside the memory region, and 'e' for external to the region:
        `ib` - inside the region, aligned to the bottom
        `ic` - inside the region, aligned to the centre vertically
        `it` - inside the region, aligned to the top
        `jt` - at the top region junction
        `jb` - at the bottom region junction
    """

    def __init__(self, label, position):
        self.label = label
        self.position = position

    def __repr__(self):
        return "<{}(position={!r}, label={!r}>".format(self.__class__.__name__,
                                                       self.position, self.label)

    def __str__(self):
        return self.label


class MemoryRegion(object):

    def __init__(self, address, size):
        self.address = address
        self.size = size
        self.end = self.address + self.size
        self.labels = {}
        self.fill = None
        self.outline = None
        # The container can be another sequence which we will expand out?
        self.container = None

    def __repr__(self):
        return "<{}(&{:08x} + &{:08x})>".format(self.__class__.__name__,
                                                self.address, self.size)

    def add_label(self, label, position=('ic', 'ic')):
        self.labels[position] = RegionLabel(label, position)

    def set_fill_colour(self, colour):
        self.fill = colour

    def set_outline_colour(self, colour):
        self.outline = colour


class DiscontinuityRegion(MemoryRegion):
    pass


class ValueFormatter(object):

    def __init__(self):
        pass

    def value(self, address):
        return str(address)


class ValueFormatterAcorn(ValueFormatter):

    def value(self, address):
        return "&%X" % (address,)


class ValueFormatterCommodore(ValueFormatter):

    def value(self, address):
        return "$%X" % (address,)


class ValueFormatterC(ValueFormatter):

    def value(self, address):
        return "0x%X" % (address,)


class ValueFormatterSI(ValueFormatter):

    def si(self, size):
        if size == 0:
            return "0 B"

        if size % (1024*1024*1024) == 0:
            return "{} GiB".format(size / (1024*1024*1024))
        if size % (1024*1024) == 0:
            return "{} MiB".format(size / (1024*1024))
        if size % 1024 == 0:
            return "{} KiB".format(size / 1024)
        if size < 1024:
            return "{} B".format(size)

        if size % 1024 != 0:
            return self.si(size - (size % 1024)) + " + {} B".format(size % 1024)

        if size % (1024*1024) != 0:
            return self.si(size - (size % (1024*1024))) + " + {} KiB".format((size % (1024*1024)) / 1024)

        # Should never reach here.
        return "{} B".format(size)

    def value(self, address):
        return self.si(address)


class Sequence(object):

    def __init__(self):
        self.regions = []
        self.address_formatter = ValueFormatterC()
        self.size_formatter = None

        # Render parameters
        self.unit_height = 0.2
        self.unit_size = 1024 * 32
        self.min_units = 1
        self.region_min_height = 0.625
        self.region_max_height = 2
        self.discontinuity_height = self.region_min_height * 1.5
        self.region_width = 2

    def add_region(self, region):
        self.regions.append(region)

    def sort(self):
        self.regions = sorted(self.regions, key=lambda region: region.address)

    def address_format(self, address):
        """
        Format an address.
        """
        return self.address_formatter.value(address)

    def size_format(self, size):
        """
        Format a size.
        """
        return self.size_formatter.value(size) if self.size_formatter else self.address_formatter.value(size)

    def add_discontinuities(self):
        new_regions = []
        last_end = None
        for region in self.regions:
            if last_end and last_end != region.address:
                # This is a region that doesn't butt up to the next one
                new_region = DiscontinuityRegion(last_end, region.address - last_end)
                new_regions.append(new_region)
            new_regions.append(region)
            last_end = region.end
        self.regions = new_regions

    def add_address_labels(self, start=True, end=False, size=False, side='right', end_exclusive=True,
                           final_end=False, initial_start=False):
        xpos_map = {
                'left': ('el', 'elf'),
                'right': ('er', 'erf'),
            }
        xpos = xpos_map[side]
        initial = True
        for index, region in enumerate(self.regions):
            final = (index == len(self.regions) - 1)
            if start or (initial and initial_start):
                address_string = self.address_format(region.address)
                region.add_label(address_string, (xpos[0], 'ib' if initial else 'jb'))
            if end or (final and final_end):
                address = region.address + region.size
                if not end_exclusive:
                    address -= 1
                address_string = self.address_format(address)
                region.add_label(address_string, (xpos[0], 'it' if final else 'jt'))

            if size:
                size_string = self.size_format(region.size)
                # The size can go against the edge if there's no start or end.
                pos = xpos[1] if start or end else xpos[0]
                region.add_label(size_string, (pos, 'ic'))

            initial = False


class MultipleMaps(object):

    def __init__(self):
        self.sequences = []

    def add_sequence(self, sequence):
        self.sequences.append(sequence)

    def __iter__(self):
        return iter(self.sequences)


class GraphvizRender(object):
    default_fontname = "Optima, Rachana, Sawasdee, sans-serif"

    def __init__(self, fh=None):
        if isinstance(fh, str):
            fh = open(fh, 'w')
        self.fh = fh or sys.stdout

    def __del__(self):
        self.fh.close()

    def write(self, content):
        self.fh.write(content)

    def region_table(self, sequence, width, height, labels, place='cell'):
        rows = []
        if place == 'cell':
            colkeys = ('il', 'ic', 'ir')
            rowkeys = ('it', 'ic', 'ib')
        elif place == 'right':
            colkeys = ('er', 'erm', 'erf')
            rowkeys = ('it', 'ic', 'ib')
        elif place == 'left':
            colkeys = ('elf', 'elm', 'el')
            rowkeys = ('it', 'ic', 'ib')

        # We don't support labels on the junction, so we just make them interior labels
        equivrow = {
                'jt': 'it',
                'jb': 'ib',
            }

        labels = dict(((key[0], equivrow.get(key[1], key[1])), value) for (key, value) in labels.items())
        rowspresent = list(any(labels.get((colkey, rowkey), None) for colkey in colkeys) for rowkey in rowkeys)
        rowsused = (bool(rowspresent[0]) * 4) + (bool(rowspresent[1]) * 2) + (bool(rowspresent[2]) * 1)

        cellpadding = 2

        rowsheight = (0, height, 0)
        if height > sequence.region_min_height * 3:
            # If there's space for 3 minimum height's we'll make each row the same height; otherwise we'll
            # split the size up.
            rowsheight = (height / 3.0, height / 3.0, height / 3.0)
        else:
            if rowsused in (0b100, 0b010, 0b001):
                rowsheight = (height if rowsused & 0b100 else 0,
                              height if rowsused & 0b010 else 0,
                              height if rowsused & 0b001 else 0)

            elif rowsused in (0b101, 0b110, 0b011):
                rowsheight = (height / 2.0 if rowsused & 0b100 else 0,
                              height / 2.0 if rowsused & 0b010 else 0,
                              height / 2.0 if rowsused & 0b001 else 0)

            elif rowsused == 0b111:
                rowsheight = (height / 3.0, height / 3.0, height / 3.0)

        def escape(s):
            if not s:
                return ''
            s = str(s)
            s = s.replace('&', '&amp;')
            s = s.replace('<', '&lt;')
            s = s.replace('>', '&gt;')
            s = s.replace('\n', '<br/>')
            return s

        for rownumber, rowkey in enumerate(rowkeys):
            collabels = list(labels.get((colkey, rowkey), None) for colkey in colkeys)
            used = (bool(collabels[0]) * 4) + (bool(collabels[1]) * 2) + (bool(collabels[2]) * 1)
            valign = ('top', 'middle', 'bottom')[rownumber]
            cellheight = max(0, (rowsheight[rownumber] * 72))
            if used == 0b000 and cellheight == 0:
                continue

            cellwidth = (sequence.region_width * 72)

            if used == 0b001:
                # Just right aligned
                row = '<td colspan="3" align="right" valign="{}" width="{}" height="{}">{}</td>'.format(valign, cellwidth, cellheight,
                                                                                                        escape(labels[(colkeys[2], rowkey)]))
            elif used == 0b010:
                # Just centred
                row = '<td colspan="3" align="center" valign="{}" width="{}" height="{}">{}</td>'.format(valign, cellwidth, cellheight,
                                                                                                         escape(labels[(colkeys[1], rowkey)]))
            elif used == 0b100:
                # Just left aligned
                row = '<td colspan="3" align="left" valign="{}" width="{}" height="{}">{}</td>'.format(valign, cellwidth, cellheight,
                                                                                                       escape(labels[(colkeys[0], rowkey)]))
            elif used == 0b000:
                # Nothing
                row = '<td colspan="3" align="center" valign="{}" width="{}" height="{}"></td>'.format(valign, cellwidth, cellheight)

            elif used == 0b101:
                # Left and right aligned
                row = '<td colspan="2" align="left" valign="{}" height="{}">{}</td>'.format(valign, cellheight,
                                                                                            escape(labels[(colkeys[0], rowkey)]))
                row += '<td align="right" valign="{}" height="{}">{}</td>'.format(valign, cellheight,
                                                                                  escape(labels[(colkeys[2], rowkey)]))
            else:
                row = '<td align="left" valign="{}" height="{}">{}</td>'.format(valign, cellheight,
                                                                                escape(labels.get((colkeys[0], rowkey), None)))
                row += '<td align="center" valign="{}" height="{}">{}</td>'.format(valign, cellheight,
                                                                                   escape(labels.get((colkeys[1], rowkey), None)))
                row += '<td align="right" valign="{}" height="{}">{}</td>'.format(valign, cellheight,
                                                                                  escape(labels.get((colkeys[2], rowkey), None)))
            rows.append("<tr>{}</tr>".format(row))

        return '<table cellborder="0" cellspacing="0" cellpadding="%s" border="0" fixedsize="false" color="blue" height="%.2f" width="%.2f">%s</table>' \
                    % (cellpadding, height * 72, width * 72, ''.join(rows))

    def header(self):
        self.write("""
digraph memory {
    ranksep = 0;
    nodesep = 0;
    node [
        shape=rect,
        penwidth=2,
        fontname="{}"
    ];
    edge [
        fontname="{}",
        style=invis
    ];
""".format(self.default_fontname))

    def footer(self):
        self.write("""
}
""")

    def render(self, memorymap):
        self.header()
        if isinstance(memorymap, Sequence):
            self.render_sequence(memorymap, '')

        elif isinstance(memorymap, MultipleMaps):
            for (index, sequence) in enumerate(memorymap):
                self.render_sequence(sequence, "_{}_".format(index))

        self.footer()

    def render_sequence(self, sequence, identifier):
        last_region = None
        last_left = None
        for region in reversed(sequence.regions):
            height_in_units = (region.size / sequence.unit_size)
            height_in_units = max(height_in_units, sequence.min_units)
            height = height_in_units * sequence.unit_height
            height = max(height, sequence.region_min_height)
            height = min(height, sequence.region_max_height)

            if isinstance(region, DiscontinuityRegion):
                height = min(height, sequence.discontinuity_height)

            # We must write the nodes in the correct order for positioning purposes
            has_left = any(position[0] == 'el' for position in region.labels.keys())
            has_right = any(position[0] == 'er' for position in region.labels.keys())
            if has_left or has_right:
                same = """
    {
        rank = same;
LEFT
        region%s%08x;
RIGHT
    }
""" % (identifier, region.address)
                if has_left:
                    region_left_table = self.region_table(sequence, sequence.region_width, height, region.labels, place='left')
                    region_left = '        region%s%08xleft [ label=<%s> labelloc=c, labeljust=c, shape=none ];\n' \
                                    % (identifier, region.address, region_left_table)
                    if last_left:
                        self.write('    region%s%08xleft -> region%s%08xleft;\n' % (identifier, last_region.address,
                                                                                    identifier, region.address))
                    last_left = region
                else:
                    region_left = ''

                if has_right:
                    region_right_table = self.region_table(sequence, sequence.region_width, height, region.labels, place='right')
                    region_right = '        region%s%08xright [ label=<%s> labelloc=c, labeljust=c, shape=none ];\n' \
                                    % (identifier, region.address, region_right_table)
                else:
                    region_right = ''
                same = same.replace('LEFT\n', region_left)
                same = same.replace('RIGHT\n', region_right)
                self.write(same)

            if isinstance(region, DiscontinuityRegion):
                self.write('    region%s%08x [ style=dashed ];\n' % (identifier, region.address))
            self.write('    region%s%08x [ width=%.2f, height=%.2f, fixedsize=true ];\n' % (identifier, region.address,
                                                                                            sequence.region_width, height))

            # The most common case will be a single label
            labels = region.labels.items()
            ilabels = dict((position, label) for position, label in labels if position[0][0] == 'i' and position[1][0] in ('i', 'j'))
            if len(ilabels) == 0:
                # If there are no labels, we still need to write the empty string
                # otherwise it will be given the name of the graphviz node.
                self.write('    region%s%08x [ label="" ];\n' % (identifier, region.address))

            elif len(ilabels) == 1:
                # If there is only 1 interior label, this is easy
                label = list(ilabels.values())[0]
                labeljust = ''
                if label.position[0][1] in ('l', 'r'):
                    labeljust = '\\' + label.position[0][1]
                text = label.label
                text = text.replace('\\', '\\\\')
                text = text.replace('\n', labeljust or '\\n')
                self.write('    region%s%08x [ label="%s%s", labelloc=%s ];\n' % (identifier, region.address,
                                                                                  text,
                                                                                  labeljust,
                                                                                  label.position[1][1]))
            else:
                # Multiple labels.
                # We turn them into a table.
                table = self.region_table(sequence, sequence.region_width, height, ilabels)
                self.write('    region%s%08x [ label=<%s> labelloc=c labeljust=c ];\n'
                            % (identifier, region.address, table))

            if region.fill or region.outline:
                attrs = []
                if region.fill:
                    attrs.append('fillcolor="{}"'.format(region.fill))
                    attrs.append('style=filled')
                if region.outline:
                    attrs.append('color="{}"'.format(region.outline))
                self.write('    region%s%08x [ %s ];\n' % (identifier, region.address,
                                                           ', '.join(attrs)))

            if last_region:
                self.write('    region%s%08x -> region%s%08x;\n' % (identifier, last_region.address,
                                                                    identifier, region.address))
            last_region = region


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


class SVGElement(object):
    """
    Base class for SVG elements.

    Each element has two parts - itself, and the inner elements.
    The element might have a transformation applied to its bounds.
    This transform needs to be placed in the element's body.
    """
    use_inches = True
    DPI = 96

    def __init__(self):
        try:
            self.self_bounds = Bounds()
        except AttributeError:
            # If you cannot assign as this is readonly, then it'll be handled by the child.
            pass
        self.transform = None
        self.inner = []

    def svg(self):
        fh = io.StringIO()
        self.write(fh, '')
        return fh.getvalue()

    def add_inner(self, element):
        self.inner.append(element)

    def units(self, value):
        if self.use_inches:
            if value == int(value):
                return "{}in".format(int(value))
            else:
                return "{:.2f}in".format(value)
        else:
            value = value * self.DPI
            if value == int(value):
                return "{}".format(int(value))
            else:
                return "{:.2f}".format(value)

    def pixels(self, value):
        value = value * self.DPI
        if value == int(value):
            return "{}".format(int(value))
        else:
            return "{:.2f}".format(value)

    def transform_attribute(self):
        if self.transform:
            # The translation must not use CSS units, but pixels, so we multiply by the DPI.
            return "matrix({:f} {:f} {:f} {:f} {:f} {:f})".format(self.transform.a, self.transform.b,
                                                              self.transform.c, self.transform.d,
                                                              self.transform.e * self.DPI, self.transform.f * self.DPI)
        else:
            return "translate(0)"

    @property
    def bounds(self):
        bounds = self.inner_bounds
        if self.transform:
            (x0, y0, x1, y1) = self.transform.bbox(bounds.x0, bounds.y0,
                                                   bounds.x1, bounds.y1)
            bounds = Bounds(x0, y0, x1, y1)
        return bounds

    @property
    def inner_bounds(self):
        bounds = self.self_bounds
        if self.inner:
            for inner in self.inner:
                bounds += inner.bounds
        return bounds

    def write_leader(self, fh, indent=''):
        pass

    def write_trailer(self, fh, indent=''):
        pass

    def write_inner(self, fh, indent=''):
        for element in self.inner:
            if isinstance(element, SVGElement):
                element.write(fh, indent + '  ')
            else:
                fh.write(indent + element)

    def write_self(self, fh, indent=''):
        self.write_inner(fh, indent)

    def write(self, fh, indent=''):
        self.write_leader(fh, indent)
        self.write_self(fh, indent)
        self.write_trailer(fh, indent)


class SVGRaw(SVGElement):

    def __init__(self, xml):
        super(SVGRaw, self).__init__()
        if not xml.endswith('\n'):
            xml += '\n'
        self.xml = xml

    def write_self(self, fh, indent):
        if self.transform:
            fh.write(indent + '<g transform="{}">\n'.format(self.transform_attribute()))
            fh.write(indent + '  ' + self.xml)
            fh.write(indent + '</g>\n')
        else:
            fh.write(indent + self.xml)


class SVGRect(SVGElement):

    def __init__(self, x0, y0, x1=None, y1=None, width=None, height=None, fill=None, stroke=None):
        super(SVGRect, self).__init__()
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1 if x1 is not None else x0 + width
        self.y1 = y1 if y1 is not None else y0 + height
        self.fill = fill
        self.stroke = stroke

    @property
    def self_bounds(self):
        return Bounds(self.x0, self.y0, self.x1, self.y1)

    def write_self(self, fh, indent):
        attrs = []
        attrs.append('x="{}"'.format(self.units(self.x0)))
        attrs.append('y="{}"'.format(self.units(self.y0)))
        attrs.append('width="{}"'.format(self.units(self.x1 - self.x0)))
        attrs.append('height="{}"'.format(self.units(self.y1 - self.y0)))

        if self.transform:
            attrs.append('transform="{}"'.format(self.transform_attribute()))
        if self.fill:
            attrs.append('fill="{}"'.format(self.fill))
        if self.stroke:
            attrs.append('stroke="{}"'.format(self.stroke))

        fh.write(indent + "<rect {}/>\n".format(" ".join(attrs)))


class SVGPath(SVGElement):

    def __init__(self, fill=None, stroke=None):
        super(SVGPath, self).__init__()
        self.components = []
        self.fill = fill
        self.stroke = stroke

    def move(self, x, y):
        self.components.append(('M', x, y))

    def line(self, x, y):
        self.components.append(('L', x, y))

    @property
    def self_bounds(self):
        bounds = Bounds()
        for component in self.components:
            if len(component) == 3:
                bounds += (component[1], component[2])
        return bounds

    def write_self(self, fh, indent):
        attrs = []

        if self.transform:
            attrs.append('transform="{}"'.format(self.transform_attribute()))
        attrs.append('fill="{}"'.format(self.fill if self.fill else 'none'))
        attrs.append('stroke="{}"'.format(self.stroke if self.stroke else 'none'))

        path_data = []
        for component in self.components:
            if len(component) == 3:
                path_data.extend((component[0], self.pixels(component[1]), self.pixels(component[2])))
        attrs.append('d="{}"'.format(' '.join(path_data)))

        fh.write(indent + "<path {}/>\n".format(" ".join(attrs)))


class SVGText(SVGElement):
    fontsize = 12
    fontname = 'Optima, Rachana, Sawasdee, sans-serif'

    def __init__(self, x, y, string, colour=None, position='cc'):
        super(SVGText, self).__init__()
        self.x = x
        self.y = y
        self.string = string
        # Position is espected to be a string describing the origin of the x, y position, using the characters:
        #   l, c, r : left, centre, right for the x position
        #   t, c, b : top, centre, bottom for the y position
        self.position = position
        self.colour = colour

    @property
    def self_bounds(self):
        width = self.width
        height = self.height
        x0 = self.x
        y0 = self.y

        xpos = self.position[0]
        ypos = self.position[1]
        if xpos == 'c':
            x0 = self.x - width / 2
        elif xpos == 'l':
            x0 = self.x
        elif xpos == 'r':
            x0 = self.x - width

        if ypos == 'c':
            y0 = self.y - height / 2
        elif ypos == 'b':
            y0 = self.y
        elif ypos == 't':
            y0 = self.y - height

        x1 = x0 + width
        y1 = y0 + height

        return Bounds(x0, y0, x1, y1)

    @property
    def lines(self):
        return self.string.splitlines()

    @property
    def width(self):
        # We estimate the width based on the number of characters in the longest line.
        # It's not going to be perfect, but without actually knowing the metrics of the
        # font in use, it cannot be. But it should be good enough to get a decent
        # estimate for the bounding box.
        # We return the width in inches, as we have for all the sizes, but font size
        # is based around points, which are measured in 1/72 inch units.
        # We assume that the characters will be equally spaced squares of the point
        # size - which is almost never true, but will probably be oversized.
        longest_line = max(len(line) for line in self.lines)
        return longest_line * self.fontsize / 72.0

    @property
    def height(self):
        # We estimate the height based on the number of lines in the string.
        # We return the height in inches, as we have for all the sizes, but font size
        # is based around points, which are measured in 1/72 inch units.
        nlines = len(self.lines)
        return nlines * self.lineheight

    @property
    def lineheight(self):
        # We assume that the characters will be equally spaced squares of the point
        # size - which is almost never true, but will probably be oversized.
        return self.fontsize / 72.0

    def write_self(self, fh, indent):
        attrs = []
        attrs.append('x="{}"'.format(self.units(self.x)))
        attrs.append('y="{}"'.format(self.units(self.y)))

        styles = []

        xpos = self.position[0]
        ypos = self.position[1]
        anchor = 'start'
        if xpos == 'c':
            anchor = 'middle'
        elif xpos == 'l':
            anchor = 'start'
        elif xpos == 'r':
            anchor = 'end'

        baseline = 'auto'
        if ypos == 'c':
            baseline = 'middle'
        elif ypos == 'b':
            baseline = 'auto'
        elif ypos == 't':
            baseline = 'hanging'

        if anchor != 'start':
            styles.append(('text-anchor', anchor))

        if baseline != 'auto':
            styles.append(('dominant-baseline', baseline))

        if self.fontname:
            styles.append(('font-family', self.fontname))

        if self.transform:
            attrs.append('transform="{}"'.format(self.transform_attribute()))
        if self.colour:
            styles.append(('color', self.colour))

        if styles:
            style = ' '.join("{}: {};".format(prop, value) for prop, value in styles)
            attrs.append('style="{}"'.format(style))

        def escape(s):
            if not s:
                return ''
            s = str(s)
            s = s.replace('&', '&amp;')
            s = s.replace('<', '&lt;')
            s = s.replace('>', '&gt;')
            return s

        # FIXME: Multiline not really supported
        y = self.y
        for line in self.lines:
            fh.write(indent + "<text {}>{}</text>\n".format(" ".join(attrs), escape(line)))
            # We know that the y position is the 2nd attribute, so we update it:
            y += self.lineheight
            attrs[1] = 'y="{}"'.format(self.units(y))


class SVGGroup(SVGElement):

    def __init__(self):
        super(SVGGroup, self).__init__()

    def add(self, element):
        if isinstance(element, (Bounds, tuple)):
            self.self_bounds += element
        elif isinstance(element, SVGElement):
            self.add_inner(element)
        else:
            if not element.endswith('\n'):
                element += '\n'
            self.add_inner(SVGRaw(element))

    def __iter__(self):
        return iter(self.inner)

    def write_leader(self, fh, indent=''):
        if self.transform:
            fh.write(indent + '<g transform="{}">\n'.format(self.transform_attribute()))
        else:
            fh.write(indent + '<g>\n')

    def write_trailer(self, fh, indent=''):
        fh.write(indent + '</g>\n')


class SVGRender(object):
    default_fontname = "Optima, Rachana, Sawasdee, sans-serif"

    def __init__(self, fh=None):
        if isinstance(fh, str):
            fh = open(fh, 'w')
        self.fh = fh or sys.stdout
        self.groups = []

    def __del__(self):
        self.fh.close()

    def write(self, content):
        self.fh.write(content)

    def header(self, bounds):
        self.write("""\
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{:.2f}in {:.2f}in {:.2f}in {:.2f}in" width="{:.2f}in" height="{:.2f}in">
<defs>
    <style type="text/css">
        text {{
            font-family: {};
        }}
    </style>
</defs>
""".format(bounds.x0, bounds.y0, bounds.x1, bounds.y1,
           bounds.x1 - bounds.x0,
           bounds.y1 - bounds.y0,
           self.default_fontname))

    def footer(self):
        self.write("""
</svg>
""")

    def render(self, memorymap):
        self.groups = SVGGroup()
        if isinstance(memorymap, Sequence):
            self.groups.add(self.render_sequence(memorymap))

        elif isinstance(memorymap, MultipleMaps):
            for (index, sequence) in enumerate(memorymap):
                # FIXME This isn't right; we want to transform the groups to move them around?
                self.groups.add(self.render_sequence(sequence))

        # Transform the group so that it is origined at 0,0
        self.groups.transform = Translate(-self.groups.bounds.x0, -self.groups.bounds.y0)

        self.header(self.groups.bounds)
        self.groups.write(self.fh)
        self.footer()

    def render_sequence(self, sequence):

        groups = SVGGroup()
        insetx = 0.05
        insety = 0.05

        y = 0
        for region in reversed(sequence.regions):
            height_in_units = (region.size / sequence.unit_size)
            height_in_units = max(height_in_units, sequence.min_units)
            height = height_in_units * sequence.unit_height
            height = max(height, sequence.region_min_height)
            height = min(height, sequence.region_max_height)

            if isinstance(region, DiscontinuityRegion):
                height = min(height, sequence.discontinuity_height)

            if isinstance(region, DiscontinuityRegion):
                stroke = '#000'
                fill = None
                xoffset = sequence.unit_height / 6.0
                ysegmentsize = (height - (xoffset * 2)) / 4.0

                for path_pass in range(0 if fill else 1, 2):
                    if path_pass == 0:
                        path = SVGPath(fill=fill)
                    else:
                        path = SVGPath(stroke=stroke)
                    path.move(0, y)
                    path.line(0, y + xoffset)
                    path.line(-xoffset, y + xoffset + ysegmentsize * 1)
                    path.line(0, y + xoffset + ysegmentsize * 2)
                    path.line(+xoffset, y + xoffset + ysegmentsize * 3)
                    path.line(0, y + height - xoffset)
                    path.line(0, y + height)

                    if path_pass == 0:
                        path.line(sequence.region_width, y + height)
                    else:
                        path.move(sequence.region_width, y + height)
                    path.line(sequence.region_width, y + height - xoffset)
                    path.line(sequence.region_width + xoffset, y + xoffset + ysegmentsize * 3)
                    path.line(sequence.region_width, y + xoffset + ysegmentsize * 2)
                    path.line(sequence.region_width - xoffset, y + xoffset + ysegmentsize * 1)
                    path.line(sequence.region_width, y + xoffset)
                    path.line(sequence.region_width, y)

                    groups.add(path)
            else:
                groups.add(SVGRect(x0=0, y0=y, width=sequence.region_width, height=height,
                                   fill=region.fill or '#fff', stroke=region.outline or '#000'))

            for label in region.labels.values():
                xpos = label.position[0]
                ypos = label.position[1]
                lx = insetx
                ly = y + insety

                pos = 'lb'
                if xpos[0] == 'i':
                    # The text position is simple to derive from the memory region position
                    pos = xpos[1]

                    if xpos[1] == 'c':
                        lx += (sequence.region_width - insetx * 2) / 2.0
                    elif xpos[1] == 'r':
                        lx += (sequence.region_width - insety * 2)

                elif xpos[0:2] == 'el' or xpos[0:2] == 'er':
                    if xpos == 'elf':
                        lx -= sequence.region_width
                        pos = 'l'
                    elif xpos == 'elm':
                        lx -= (insetx * 2) + (sequence.region_width - insetx * 2) / 2.0
                        pos = 'c'
                    elif xpos == 'el':
                        lx -= (insetx * 2)
                        pos = 'r'

                    elif xpos == 'erf':
                        lx += sequence.region_width * 2 - (insetx * 2)
                        pos = 'r'
                    elif xpos == 'erm':
                        lx += sequence.region_width + (sequence.region_width - insetx * 2) / 2.0
                        pos = 'c'
                    elif xpos == 'er':
                        lx += sequence.region_width
                        pos = 'l'

                else:
                    # This isn't a positioning we understand.
                    pass

                if ypos == 'it':
                    ly = y + insety
                    pos += ypos[1]
                elif ypos == 'ic':
                    ly = y + height / 2.0
                    pos += ypos[1]
                elif ypos == 'ib':
                    ly = y + height - insety
                    pos += ypos[1]
                elif ypos == 'jt':
                    ly = y
                    pos += 'c'
                elif ypos == 'jb':
                    ly = y + height
                    pos += 'c'

                #print("Position %r => %r, %f, %f (%r)" % (label.position, pos, lx, ly - y, label.label))

                groups.add(SVGText(lx, ly, label.label, position=pos))

            y += height

        return groups


import argparse
import os
import sys

parser = argparse.ArgumentParser(usage="%s [<options>] <dataset>" % (os.path.basename(sys.argv[0]),))
parser.add_argument('--format', choices=('svg', 'dot'), default='svg',
                    help="Format to generate output in")
parser.add_argument('dataset', choices=('bbc', 'bbcws', 'riscos'), default='riscos',
                    help="Internal data set to render")
options = parser.parse_args()

if options.format == 'svg':
    renderer_class = SVGRender
    filename = 'memory.svg'
elif options.format == 'dot':
    renderer_class = GraphvizRender
    filename = 'memory.dot'
example = options.dataset

if example.startswith('bbc'):
    # BBC memory map, from https://worldofspectrum.org/files/large/1f8d7859d89b51d
    memory = [
            (0x0000, 0x0100, "Zero page"),
            (0x0100, 0x0100, "6502 stack"),
            (0x0200, 0x0100, "Workspace"),
            (0x0300, 0x0100, "Workspace"),
            (0x0400, 0x0400, "BASIC workspace"),
            (0x0800, 0x0100, "Workspace"),
            (0x0900, 0x0200, "Buffers"),
            (0x0B00, 0x0100, "User defined keys"),
            (0x0C00, 0x0100, "User defined\ncharacters"),
            (0x0D00, 0x0100, "Paged ROM\nwkspace or user\nmachine code"),
            (0x0E00, 0x0B00, "BASIC program\nspace or DFS\nworkspace"),
            (0x1900, 0x0600, "BASIC program"),
            (0x1F00, 0x0100, "Variables"),
            (0x7B00, 0x0100, "BASIC stack"),
            (0x7C00, 0x0400, "Video RAM"),
            (0x8000, 0x4000, "BASIC ROM"),
            (0xC000, 0x3C00, "OS ROM"),
            (0xFC00, 0x0300, "Mem mapped I/O"),
            (0xFF00, 0x0100, "OS ROM"),
        ]
    sequence = Sequence()
    sequence.unit_size = 0x100
    sequence.unit_height = 0.5
    sequence.region_min_height = 0.625

    for (address, size, name) in memory:
        region = MemoryRegion(address, size)
        region.add_label(name, ('il', 'it'))
        region.set_fill_colour('#F9FBD3')
        region.set_outline_colour('#336DA5')
        sequence.add_region(region)

    sequence.address_formatter = ValueFormatterAcorn()
    sequence.size_formatter = ValueFormatterAcorn()

    sequence.add_discontinuities()
    sequence.add_address_labels(start=True, end=False, size=False, side='left', end_exclusive=False,
                                final_end=True)

    # Workspace
    ws_sequence = Sequence()
    ws_sequence.unit_size = 0x20
    ws_sequence.unit_height = 0.5
    ws_sequence.region_min_height = 0.625

    ws_memory = [
            (0x0200, 0x0036, "Vectors"),
            (0x0236, 0x00B4, "OS workspace\nand variables\nwritten by FX\ncalls"),
            (0x02EA, 0x0016, "Tape and filing\nsystem wkspace"),
            (0x0300, 0x0080, "VDU Wkspace for\ntext/graphics"),
            (0x0380, 0x0060, "Tape system\nvariables"),
            (0x03E0, 0x0020, "Keyboard buffer"),
        ]
    for (address, size, name) in ws_memory:
        region = MemoryRegion(address, size)
        region.add_label(name, ('il', 'it'))
        region.set_fill_colour('#C7E3EC')
        region.set_outline_colour('#336DA5')
        ws_sequence.add_region(region)
    ws_sequence.add_discontinuities()
    ws_sequence.add_address_labels(start=False, end=True, size=False, side='right', end_exclusive=False,
                                   initial_start=True)

    if False:
        mm = MultipleMaps()
        mm.add_sequence(sequence)
        mm.add_sequence(ws_sequence)

        renderer = renderer_class(filename)
        renderer.render(mm)

    elif example =='bbcws':
        renderer = renderer_class(filename)
        renderer.render(ws_sequence)

    else:
        renderer = renderer_class(filename)
        renderer.render(sequence)

elif example == 'riscos':
    memory = [
            (0x00000000, 0x00008000, 48, "Zero Page"),
            (0x00008000, 0x03000000, -1, "Application Space"),
            (0x03800000, 0x00800000, 11, "ROM"),
            (0x04000000, 0x00004000, 14, "IRQ Stack"),
            (0x04100000, 0x00008000, 13, "SVC Stack"),
            (0x04109000, 0x002f8000, 0, "System heap"),
            (0x04800000, 0x00020000, 50, "Utility executables"),
            (0x07000000, 0x00f00000, 1, "Module area"),
            (0x08400000, 0x00004000, 15, "UND Stack"),
            (0xffff0000, 0x00010000, 49, "Exception vectors"),
        ]
    sequence = Sequence()

    for (address, size, danum, name) in memory:
        region = MemoryRegion(address, size)
        region.add_label(name)
        region.add_label("DA #{}".format(danum), ('il', 'it'))
        sequence.add_region(region)

    sequence.address_formatter = ValueFormatterAcorn()
    sequence.size_formatter = ValueFormatterSI()

    sequence.add_discontinuities()
    sequence.add_address_labels(start=True, end=True, size=True)

    renderer = renderer_class(filename)
    renderer.render(sequence)

else:
    print("Unrecognised example '{}'".format(example))
