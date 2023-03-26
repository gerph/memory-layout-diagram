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
