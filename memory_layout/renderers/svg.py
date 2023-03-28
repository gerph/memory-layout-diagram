"""
SVG renderer for the memory layout diagrams.
"""

import io

from memory_layout import Sequence, MemoryRegion, DiscontinuityRegion
from memory_layout.structs import Bounds, Transform, Matrix, Translate

from . import MLDRenderBase


class SVGElement(object):
    """
    Base class for SVG elements.

    Each element has two parts - itself, and the inner elements.
    The element might have a transformation applied to its bounds.
    This transform needs to be placed in the element's body.
    """
    # Our configurables
    use_inches = True

    # Constants
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

    def prepend_inner(self, element):
        self.inner.insert(0, element)

    def append_inner(self, element):
        self.inner.append(element)

    def units(self, value):
        if self.use_inches:
            if value == int(value):
                return "{}in".format(int(value))
            else:
                return "{:.3f}in".format(value)
        else:
            value = value * self.DPI
            if value == int(value):
                return "{}".format(int(value))
            else:
                return "{:.3f}".format(value)

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

    def __init__(self, x0, y0, x1=None, y1=None, width=None, height=None, fill=None, stroke=None, stroke_width=None):
        super(SVGRect, self).__init__()
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1 if x1 is not None else x0 + width
        self.y1 = y1 if y1 is not None else y0 + height
        self.fill = fill
        self.stroke = stroke
        self.stroke_width = stroke_width

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
        attrs.append('fill="{}"'.format(self.fill or 'none'))
        if self.stroke:
            attrs.append('stroke="{}"'.format(self.stroke))
        if self.stroke_width:
            attrs.append('stroke-width="{}"'.format(self.units(self.stroke_width)))

        fh.write(indent + "<rect {}/>\n".format(" ".join(attrs)))


class SVGPath(SVGElement):

    def __init__(self, fill=None, stroke=None, stroke_width=None, stroke_pattern='solid'):
        super(SVGPath, self).__init__()
        self.components = []
        self.fill = fill
        self.stroke = stroke
        self.stroke_width = stroke_width
        self.stroke_pattern = stroke_pattern

    def move(self, x, y):
        self.components.append(('M', x, y))

    def line(self, x, y):
        self.components.append(('L', x, y))

    def bezier(self, cx0, xy0, cx1, cy1, x1, y1):
        self.components.append(('C', cx0, xy0, cx1, cy1, x1, y1))

    @property
    def self_bounds(self):
        bounds = Bounds()
        for component in self.components:
            if len(component) == 3:
                bounds += (component[1], component[2])
            if len(component) == 7:
                bounds += (component[1], component[2])
                bounds += (component[3], component[4])
                bounds += (component[5], component[6])
        return bounds

    def write_self(self, fh, indent):
        attrs = []

        if self.transform:
            attrs.append('transform="{}"'.format(self.transform_attribute()))
        attrs.append('fill="{}"'.format(self.fill if self.fill else 'none'))
        attrs.append('stroke="{}"'.format(self.stroke if self.stroke else 'none'))
        if self.stroke:
            if self.stroke_width:
                attrs.append('stroke-width="{}"'.format(self.units(self.stroke_width)))
            if self.stroke_pattern != 'solid':
                if self.stroke_pattern == 'dotted':
                    pattern = "{},{}".format(self.units(self.stroke_width * 2),
                                             self.units(self.stroke_width * 2))
                elif self.stroke_pattern == 'dashed':
                    pattern = "{},{}".format(self.units(self.stroke_width * 4),
                                             self.units(self.stroke_width * 2))
                else:
                    pattern = "{},{},{}".format(self.units(self.stroke_width * 4),
                                                self.units(self.stroke_width * 2),
                                                self.units(self.stroke_width * 4))
                attrs.append('stroke-dasharray="{}"'.format(pattern))

        path_data = []
        for component in self.components:
            if len(component) == 3:
                path_data.extend((component[0], self.pixels(component[1]), self.pixels(component[2])))
            if len(component) == 7:
                path_data.extend((component[0], self.pixels(component[1]), self.pixels(component[2]),
                                                self.pixels(component[3]), self.pixels(component[4]),
                                                self.pixels(component[5]), self.pixels(component[6])))
        attrs.append('d="{}"'.format(' '.join(path_data)))

        fh.write(indent + "<path {}/>\n".format(" ".join(attrs)))


class SVGText(SVGElement):
    fontsize = 12
    fontname = 'Optima, Rachana, Sawasdee, sans-serif'
    bounds_aspect = 0.75

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
            y0 = self.y - height
        elif ypos == 't':
            y0 = self.y

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
        # We apply an estimate of the aspect ratio for characters, as most will not be
        # square at the point size. We will probably still oversize things, but hopefully
        # not unreasonably.
        if not self.lines:
            return 0
        longest_line = max(len(line) for line in self.lines)
        return longest_line * self.fontsize / 72.0 * self.bounds_aspect

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

        y = self.y
        xpos = self.position[0]
        ypos = self.position[1]
        nlines = len(self.lines)
        if nlines > 1:
            # We might need to change the y-position so that it allows for the multiple lines,
            # as the position we supply to SVGText is for the first line.
            if ypos == 'b':
                # We need to move the text up by (nlines - 1) * lineheight
                y -= self.lineheight * (nlines - 1)
            elif ypos == 'c':
                # We need to move the text up by (nlines - 1) * lineheight / 2
                y -= self.lineheight * (nlines - 1) / 2

        attrs.append('x="{}"'.format(self.units(self.x)))
        attrs.append('y="{}"'.format(self.units(y)))

        styles = []
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
            attrs.append('fill="{}"'.format(self.colour))

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

        if False:
            # Diagnostics: draw a rectangle for our estimated text size.
            bounds = self.self_bounds
            rect = SVGRect(bounds.x0, bounds.y0, bounds.x1, bounds.y1, stroke='#F00')
            rect.write(fh, indent)

        # FIXME: Multiline not really supported
        for line in self.lines:
            fh.write(indent + "<text {}>{}</text>\n".format(" ".join(attrs), escape(line)))
            # We know that the y position is the 2nd attribute, so we update it:
            y += self.lineheight
            attrs[1] = 'y="{}"'.format(self.units(y))


class SVGGroup(SVGElement):

    def __init__(self):
        super(SVGGroup, self).__init__()

    def prepend(self, element):
        if isinstance(element, (Bounds, tuple)):
            self.self_bounds += element
        elif isinstance(element, SVGElement):
            self.prepend_inner(element)
        else:
            if not element.endswith('\n'):
                element += '\n'
            self.prepend_inner(SVGRaw(element))

    def append(self, element):
        if isinstance(element, (Bounds, tuple)):
            self.self_bounds += element
        elif isinstance(element, SVGElement):
            self.append_inner(element)
        else:
            if not element.endswith('\n'):
                element += '\n'
            self.append_inner(SVGRaw(element))

    def __iter__(self):
        return iter(self.inner)

    def write_leader(self, fh, indent=''):
        if self.transform:
            fh.write(indent + '<g transform="{}">\n'.format(self.transform_attribute()))
        else:
            fh.write(indent + '<g>\n')

    def write_trailer(self, fh, indent=''):
        fh.write(indent + '</g>\n')


class MLDRenderSVG(MLDRenderBase):
    file_suffix = '.svg'

    default_fontname = "Optima, Rachana, Sawasdee, sans-serif"

    def __init__(self, fh=None):
        super(MLDRenderSVG, self).__init__(fh)
        self.groups = []

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
            self.groups.append(self.render_sequence(memorymap))

        elif isinstance(memorymap, MultipleMaps):
            for (index, sequence) in enumerate(memorymap):
                # FIXME This isn't right; we want to transform the groups to move them around?
                self.groups.append(self.render_sequence(sequence))

        self.groups.prepend(SVGRect(self.groups.bounds.x0 - memorymap.document_padding,
                                    self.groups.bounds.y0 - memorymap.document_padding,
                                    self.groups.bounds.x1 + memorymap.document_padding,
                                    self.groups.bounds.y1 + memorymap.document_padding,
                                    fill=memorymap.document_bgcolour,
                                    stroke=None))

        # Transform the group so that it is origined at 0,0
        self.groups.transform = Translate(-self.groups.bounds.x0, -self.groups.bounds.y0)

        self.header(self.groups.bounds)
        self.groups.write(self.fh)
        self.footer()

    def render_discontinuity(self, sequence, groups, region, y, height):
        stroke = region.outline
        fill = region.fill
        if region.discontinuity_style in ('zig-zag', 'default'):
            # Zig-zag discontinuity
            xoffset = sequence.unit_height / 6.0
            ysegmentsize = (height - (xoffset * 2)) / 4.0

            for path_pass in range(0 if fill else 1, 2):
                if path_pass == 0:
                    path = SVGPath(fill=fill)
                else:
                    path = SVGPath(stroke=stroke,
                                   stroke_width=region.outline_width)
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

                groups.append(path)

        elif region.discontinuity_style == 'cut-out':
            # cut-out line
            #  _ |
            # / \|
            #  _  \_/
            # / \
            #    |\_/
            #    |
            xoffset = sequence.unit_height / 6.0
            ysegmentsize = (height - (xoffset * 1)) / 2.0

            if fill:
                path = SVGPath(fill=fill)
                # Upper section
                path.move(0, y)
                path.line(0, y + ysegmentsize)
                path.bezier(xoffset, y + ysegmentsize + xoffset,
                            xoffset * 2, y + ysegmentsize + xoffset,
                            xoffset * 3, y + ysegmentsize)

                path.bezier(xoffset * 4, y + ysegmentsize - xoffset,
                            sequence.region_width - xoffset * 4, y + ysegmentsize + xoffset,
                            sequence.region_width - xoffset * 3, y + ysegmentsize)

                path.bezier(sequence.region_width - xoffset * 2, y + ysegmentsize - xoffset,
                            sequence.region_width - xoffset, y + ysegmentsize - xoffset,
                            sequence.region_width, y + ysegmentsize)
                path.line(sequence.region_width, y)

                # Lower section
                path.move(0, y + height)
                path.line(0, y + height - ysegmentsize)
                path.bezier(xoffset, y + height - ysegmentsize + xoffset,
                            xoffset * 2, y + height - ysegmentsize + xoffset,
                            xoffset * 3, y + height - ysegmentsize)

                path.bezier(xoffset * 4, y + height - ysegmentsize - xoffset,
                            sequence.region_width - xoffset * 4, y + height - ysegmentsize + xoffset,
                            sequence.region_width - xoffset * 3, y + height - ysegmentsize)
                path.bezier(sequence.region_width - xoffset * 2, y + height - ysegmentsize - xoffset,
                            sequence.region_width - xoffset, y + height - ysegmentsize - xoffset,
                            sequence.region_width, y + height - ysegmentsize)
                path.line(sequence.region_width, y + height)

                groups.append(path)

            path = SVGPath(stroke=stroke,
                           stroke_width=region.outline_width)

            for xbase in (0, sequence.region_width):
                # Upper left
                path.move(xbase, y)
                path.line(xbase, y + ysegmentsize)
                path.move(xbase - xoffset * 3, y + ysegmentsize)
                path.bezier(xbase - xoffset * 2, y + ysegmentsize - xoffset,
                            xbase - xoffset, y + ysegmentsize - xoffset,
                            xbase, y + ysegmentsize)
                path.bezier(xbase + xoffset, y + ysegmentsize + xoffset,
                            xbase + xoffset * 2, y + ysegmentsize + xoffset,
                            xbase + xoffset * 3, y + ysegmentsize)

                # Lower left
                path.move(xbase, y + height)
                path.line(xbase, y + height - ysegmentsize)
                path.move(xbase - xoffset * 3, y + height - ysegmentsize)
                path.bezier(xbase - xoffset * 2, y + height - ysegmentsize - xoffset,
                            xbase - xoffset, y + height - ysegmentsize - xoffset,
                            xbase, y + height - ysegmentsize)
                path.bezier(xbase + xoffset, y + height - ysegmentsize + xoffset,
                            xbase + xoffset * 2, y + height - ysegmentsize + xoffset,
                            xbase + xoffset * 3, y + height - ysegmentsize)

            groups.append(path)

        elif region.discontinuity_style in ('dotted', 'dashed'):

            # First fill the inside of the region
            if fill:
                groups.append(SVGRect(x0=0, y0=y, width=sequence.region_width, height=height,
                                      fill=fill,
                                      stroke=None))

            # Now draw the top and bottom as solids
            if region.outline_upper == 'solid' or region.outline_lower == 'solid':
                path = SVGPath(stroke=stroke,
                               stroke_width=region.outline_width)
                if region.outline_upper == 'solid':
                    path.move(0, y)
                    path.line(sequence.region_width, y)

                if region.outline_lower == 'solid':
                    path.move(0, y + height)
                    path.line(sequence.region_width, y + height)

                groups.append(path)

            path = SVGPath(stroke=stroke,
                           stroke_width=region.outline_width,
                           stroke_pattern=region.discontinuity_style)
            path.move(0, y)
            path.line(0, y + height)                            # Down the left

            path.move(sequence.region_width, y + height)
            path.line(sequence.region_width, y)                 # Up the right

            groups.append(path)

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
                self.render_discontinuity(sequence, groups, region, y, height)

            else:
                if region.outline_lower == 'solid' and region.outline_upper == 'solid':
                    groups.append(SVGRect(x0=0, y0=y, width=sequence.region_width, height=height,
                                          fill=region.fill or '#fff',
                                          stroke=region.outline, stroke_width=region.outline_width))
                else:
                    # They requested a different type of line in the upper or lower, so this isn't
                    # a simple rectangle...
                    # First fill the inside of the region
                    groups.append(SVGRect(x0=0, y0=y, width=sequence.region_width, height=height,
                                          fill=region.fill or '#fff',
                                          stroke=None))
                    # Now draw the outline as required
                    path = SVGPath(stroke=region.outline,
                                   stroke_width=region.outline_width)
                    path.move(0, y)
                    path.line(0, y + height)                            # Down the left

                    if region.outline_lower in ('solid', 'double'):
                        path.line(sequence.region_width, y + height)
                    else:
                        path.move(sequence.region_width, y + height)

                    path.line(sequence.region_width, y)                 # Up the right

                    if region.outline_upper in ('solid', 'double'):
                        path.line(0, y)

                    if region.outline_lower == 'double':
                        path.move(0, y + height - region.outline_width * 2)
                        path.line(sequence.region_width, y + height - region.outline_width * 2)

                    if region.outline_upper == 'double':
                        path.move(0, y + region.outline_width * 2)
                        path.line(sequence.region_width, y + region.outline_width * 2)

                    groups.append(path)

                    if region.outline_lower in ('dotted', 'dashed'):
                        path = SVGPath(stroke=region.outline,
                                       stroke_width=region.outline_width,
                                       stroke_pattern=region.outline_lower)

                        path.move(0, y + height)
                        path.line(sequence.region_width, y + height)

                        groups.append(path)

                    if region.outline_lower == 'ticks':
                        path = SVGPath(stroke=region.outline,
                                       stroke_width=region.outline_width)
                        ticksize = sequence.region_width / 8.0

                        path.move(0, y + height)
                        path.line(ticksize, y + height)

                        path.move(sequence.region_width, y + height)
                        path.line(sequence.region_width - ticksize, y + height)

                        groups.append(path)

                    if region.outline_upper in ('dotted', 'dashed'):
                        path = SVGPath(stroke=region.outline,
                                       stroke_width=region.outline_width,
                                       stroke_pattern=region.outline_upper)

                        path.move(0, y)
                        path.line(sequence.region_width, y)

                        groups.append(path)

                    if region.outline_upper == 'ticks':
                        path = SVGPath(stroke=region.outline,
                                       stroke_width=region.outline_width)
                        ticksize = sequence.region_width / 12.0

                        path.move(0, y)
                        path.line(ticksize, y)

                        path.move(sequence.region_width, y)
                        path.line(sequence.region_width - ticksize, y)

                        groups.append(path)

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
                else:
                    print("Unrecognised y position '{}'".format(ypos))
                    pos += 'c'

                #print("Position %r => %r, %f, %f (%r)" % (label.position, pos, lx, ly - y, label))

                ele = SVGText(lx, ly, label.label, position=pos, colour=label.colour)
                groups.append(ele)

            y += height

        return groups
