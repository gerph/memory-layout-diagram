#!/usr/bin/env python
"""
Describe memory regions.
"""


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

    def __init__(self, label, position, colour=None):
        self.label = label
        self.position = position

        # Presentational properties
        self.colour = colour

    def __repr__(self):
        return "<{}(position={!r}, label={!r}, colour={!r}>".format(self.__class__.__name__,
                                                                    self.position, self.label,
                                                                    self.colour)

    def __str__(self):
        return self.label


class MemoryRegion(object):

    def __init__(self, address, size):
        self.address = address
        self.size = size
        self.end = self.address + self.size
        self.labels = {}
        self.fill = None
        self.outline = '#000'
        self.outline_width = 2.0 / 72
        self.outline_lower = 'solid'
        self.outline_upper = 'solid'
        # The container can be another sequence which we will expand out?
        self.container = None

    def __repr__(self):
        return "<{}(&{:08x} + &{:08x})>".format(self.__class__.__name__,
                                                self.address, self.size)

    def add_label(self, label, position=('ic', 'ic'), colour=None):
        label = RegionLabel(label, position, colour=colour)
        self.labels[position] = label
        return label

    def remove_label(self, position=('ic', 'ic')):
        if position in self.labels:
            del self.labels[position]

    def set_fill_colour(self, colour):
        self.fill = colour

    def set_outline_colour(self, colour):
        self.outline = colour

    def set_outline_width(self, width):
        self.outline_width = width

    def set_outline_lower(self, junction_type):
        self.outline_lower = junction_type

    def set_outline_upper(self, junction_type):
        self.outline_upper = junction_type


class DiscontinuityRegion(MemoryRegion):
    discontinuity_style = 'default'

    def set_style(self, style):
        self.discontinuity_style = style


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
    accuracy = 1

    def si(self, size):
        if size == 0:
            return "0 B"

        if size % (1024*1024*1024 / self.accuracy) == 0:
            return "{} GiB".format(size / (1024*1024*1024.0))
        if size % (1024*1024 / self.accuracy) == 0:
            return "{} MiB".format(size / (1024*1024.0))
        if size % (1024) == 0:
            return "{} KiB".format(size / 1024)
        if size < 1024:
            return "{} B".format(size)

        if size % 1024 != 0:
            return self.si(size - (size % 1024)) + " + {} B".format(size % 1024)

        if size % (1024*1024 / self.accuracy) != 0:
            return self.si(size - (size % (1024*1024 / self.accuracy))) + " + {} KiB".format((size % (1024*1024 / self.accuracy)) / 1024.0)

        # Should never reach here.
        return "{} B".format(size)

    def value(self, address):
        return self.si(address)


class ValueFormatterSI2(ValueFormatterSI):
    """
    SI units, but to 2 decimal places (actually 0.25, .5 and 0.75 only).
    """
    accuracy = 4


class Sequence(object):

    def __init__(self):
        self.regions = []
        self.address_formatter = ValueFormatterC()
        self.size_formatter = None

        # Layout parameters
        self.unit_height = 0.2
        self.unit_size = 1024 * 32
        self.min_units = 1
        self.region_min_height = 0.625
        self.region_max_height = 2
        self._discontinuity_height = None
        self.region_width = 2

        # Render parameters
        self.document_bgcolour = '#fff'
        self.document_padding = 0.125

    @property
    def discontinuity_height(self):
        if self._discontinuity_height is None:
            return self.region_min_height * 1.5
        else:
            return self._discontinuity_height

    @discontinuity_height.setter
    def discontinuity_height(self, value):
        self._discontinuity_height = value

    def add_region(self, region):
        self.regions.append(region)

    def find_region(self, address):
        for region in self.regions:
            if region.address == address:
                return region
        raise RuntimeError("Cannot find region for address {}".format(self.address_format(address)))

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

    def add_discontinuities(self, fill=None, outline=None, style='default'):
        if style is None:
            style = 'default'
        new_regions = []
        last_end = None
        for region in self.regions:
            if last_end and last_end != region.address:
                # This is a region that doesn't butt up to the next one
                new_region = DiscontinuityRegion(last_end, region.address - last_end)
                new_region.set_style(style)
                new_region.set_fill_colour(fill)
                if outline:
                    new_region.set_outline_colour(outline)
                new_regions.append(new_region)
            new_regions.append(region)
            last_end = region.end
        self.regions = new_regions

    def add_address_labels(self, start=True, end=False, size=False, side='right', end_exclusive=True,
                           final_end=False, initial_start=False, omit=None, colour=None):
        xpos_map = {
                'left': ('el', 'elf'),
                'right': ('er', 'erf'),
            }
        if not omit:
            omit = ()
        xpos = xpos_map[side]
        initial = True
        for index, region in enumerate(self.regions):
            final = (index == len(self.regions) - 1)
            if (start or (initial and initial_start)) and region.address not in omit:
                address_string = self.address_format(region.address)
                region.add_label(address_string, (xpos[0], 'ib' if initial or (start and end) else 'jb'), colour=colour)
            if (end or (final and final_end)) and region.address + region.size not in omit:
                address = region.address + region.size
                if not end_exclusive:
                    address -= 1
                address_string = self.address_format(address)
                region.add_label(address_string, (xpos[0], 'it' if final or (start and end) else 'jt'), colour=colour)

            if size:
                size_string = self.size_format(region.size)
                # The size can go against the edge if there's no start or end.
                pos = xpos[1] if start or end else xpos[0]
                region.add_label(size_string, (pos, 'ic'), colour=colour)

            initial = False

    def match_address(self, address):
        """
        Find a matching addess and report the region, OR report all regions

        @param address:     Address to match, or None to report all regions
        """

        for index, region in enumerate(self.regions):
            if region.address == address or address is None:
                yield (index, region)
                if address is not None:
                    return
        if address is not None:
            raise RuntimeError("Cannot find region for address {}".format(self.address_format(address)))

    def set_outline_colour(self, address, colour):
        """
        Change the outline colour of a region (or all regions)

        @param address:     Address to change, or None to change all regions
        @param colour:      Outline colour
        """
        for index, region in self.match_address(address):
            region.set_outline_colour(colour)

    def set_fill_colour(self, address, colour):
        """
        Change the fill colour of a region (or all regions)

        @param address:     Address to change, or None to change all regions
        @param colour:      Full colour
        """
        for index, region in self.match_address(address):
            region.set_fill_colour(colour)

    def set_outline_lower(self, address, outline):
        """
        Change the outline of the lower boundary of a region (or all regions)

        @param address:     Address to change, or None to change all regions
        @param outline:     Outline type
        """
        for index, region in self.match_address(address):
            region.outline_lower = outline
            if index != 0:
                # If we weren't the first region, we change the region before it to have
                # no outline.
                self.regions[index - 1].outline_upper = 'solid' if outline == 'solid' else 'none'

    def set_outline_upper(self, address, outline):
        """
        Change the outline of the upper boundary of a region.

        @param address:     Address to change, or None to change all regions
        @param outline:     Outline type
        """
        for index, region in self.match_address(address):
            region.outline_upper = outline
            if index != len(self.regions) - 1:
                # If we weren't the last region, we change the region after it to have
                # no outline.
                self.regions[index + 1].outline_lower = 'solid' if outline == 'solid' else 'none'


class MultipleMaps(object):

    def __init__(self):
        self.sequences = []

    def add_sequence(self, sequence):
        self.sequences.append(sequence)

    def __iter__(self):
        return iter(self.sequences)
