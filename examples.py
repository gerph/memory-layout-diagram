#!/usr/bin/env python
"""
Examples for rendering the memory layouts.
"""

import argparse
import os
import sys

from memory_layout import Sequence, MemoryRegion, ValueFormatterAcorn, ValueFormatterSI
from renderers.dot import MLDRenderGraphviz
from renderers.svg import MLDRenderSVG


parser = argparse.ArgumentParser(usage="%s [<options>] <dataset>" % (os.path.basename(sys.argv[0]),))
parser.add_argument('--format', choices=('svg', 'dot'), default='svg',
                    help="Format to generate output in")
parser.add_argument('--output-prefix', action='store', type=str, default='memory',
                    help="Output filename prefix")
parser.add_argument('dataset', choices=('bbc', 'bbcws', 'riscos'), default='riscos',
                    help="Internal data set to render")
options = parser.parse_args()


if options.format == 'svg':
    renderer_class = MLDRenderSVG
elif options.format == 'dot':
    renderer_class = MLDRenderGraphviz

filename = '{}{}'.format(options.output_prefix, renderer_class.file_suffix)
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
