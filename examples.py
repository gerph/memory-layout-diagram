#!/usr/bin/env python
"""
Examples for rendering the memory layouts.
"""

import argparse
import os
import sys

from memory_layout import Sequence, MemoryRegion, DiscontinuityRegion, ValueFormatterAcorn, ValueFormatterSI
from memory_layout.renderers.dot import MLDRenderGraphviz
from memory_layout.renderers.svg import MLDRenderSVG


parser = argparse.ArgumentParser(usage="%s [<options>] <dataset>" % (os.path.basename(sys.argv[0]),))
parser.add_argument('--format', choices=('svg', 'dot'), default='svg',
                    help="Format to generate output in")
parser.add_argument('--output-prefix', action='store', type=str, default='memory',
                    help="Output filename prefix")
parser.add_argument('dataset', choices=('bbc', 'bbcws', 'riscos', 'elite-bbc',
                                        'labels', 'labelsmiddle',
                                        'discontinuities'), default='riscos',
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
    sequence.region_max_height = sequence.region_min_height * 1.5
    sequence.discontinuity_height = sequence.region_min_height
    sequence.region_width = 1.5

    for (address, size, name) in memory:
        region = MemoryRegion(address, size)
        region.add_label(name, ('il', 'it'))
        region.set_fill_colour('#F9FBD3')
        region.set_outline_colour('#336DA5')
        sequence.add_region(region)

    sequence.address_formatter = ValueFormatterAcorn()
    sequence.size_formatter = ValueFormatterAcorn()

    sequence.add_discontinuities(fill=None, outline='#336DA5', style='zig-zag')
    sequence.add_address_labels(start=True, end=False, size=False, side='left', end_exclusive=False,
                                final_end=True)

    # Add some special labels
    sequence.find_region(0xE00).add_label("PAGE", ('er', 'jb'))
    region = sequence.find_region(0x1900)
    region.add_label("PAGE on disk systems", ('er', 'jb'))
    region.add_label("TOP", ('er', 'jt'))

    region = sequence.find_region(0x1F00)
    region.add_label("TOP of variables\n(?2 + 256 * ?3)", ('er', 'jt'))
    # Remove the address labels
    region.remove_label(('el', 'jb'))
    sequence.find_region(0x2000).remove_label(('el', 'jb'))
    sequence.find_region(0x7B00).remove_label(('el', 'jb'))
    region = sequence.find_region(0x7C00)
    region.remove_label(('el', 'jb'))
    region.add_label("HIMEM", ('er', 'jb'))
    region.add_label("RAMTOP", ('er', 'jt'))
    # Replace the address label
    region.add_label("&7FFF", ('el', 'jt'))
    region = sequence.find_region(0x8000)
    region.remove_label(('el', 'jb'))
    region.add_label('Paged ROMs', ('erm', 'ic'))
    region.outline_lower = 'double'     # Change the junction to be double

    # Make the BASIC region dashed
    sequence.set_outline_lower(0x1900, 'dashed')

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

elif example.startswith('elite-bbc'):
    # BBC memory map for Elite, from https://www.bbcelite.com/deep_dives/the_elite_memory_map.html
    memory = [
            (0x0000, 0x0100, "Zero page workspace",             "&0000 = ZP"),
            (0x0100, 0x0040, "Heap space ascends from XX3",     "&0100 = XX3"),
            (0x01C0, 0x0040, "6502 stack descends from &01FF",  ""),
            (0x0200, 0x0100, "MOS general workspace",           "&0200"),
            (0x0300, 0x0072, "T% workspace",                    "&0300 = T%"),
            (0x0372, 0x008E, "MOS tape filing system workspace", "&0372"),
            (0x0400, 0x0400, "Recursive tokens (WORDS9.bin)",   "&0400 = QQ18"),
            (0x0800, 0x0100, "MOS sound/printer workspace",     "&0800"),
            (0x0900, 0x0200, "Ship data blocks ascend from K%", "&0900 = K%"),
            (0x0C00, 0x0140, "Ship data blocks descend from WP", "SLSP"),
            (0x0D40, 0x01F4, "WP workspace",                    "&0D40 = WP"),
            (0x0F34, 0x000C, "&0F34-&F3F unused",               "&0F34"),
            (0x0F40, 0x46FA, "Main game code (ELTcode.bin)",    "&0F40 = S%"),
            (0x563A, 0x09C6, "Ship blueprints (SHIPS.bin)",     "&563A = XX21"),
            (0x6000, 0x1F00, "Memory for split screen",         "&6000"),
            (0x7F00, 0x0100, "Python blueprint (PYTHON.bin)",   "&7F00"),
            (0x8000, 0x4000, "Paged ROMs",                      "&8000"),
            (0xC000, 0x4000, "Machine Operating System (MOS)",  "&C000"),
        ]
    sequence = Sequence()
    sequence.unit_size = 0x100
    sequence.unit_height = 0.5
    sequence.region_min_height = 0.5
    sequence.region_max_height = sequence.region_min_height * 1.5
    sequence.discontinuity_height = 2
    sequence.region_width = 2.75
    sequence.document_bgcolour = '#000'

    for (address, size, name, label) in memory:
        region = MemoryRegion(address, size)
        region.add_label(name, ('il', 'ic'), colour='#90EE90')
        region.add_label(label, ('er', 'ib'), colour='#90EE90')
        region.set_fill_colour('#000000')
        region.set_outline_colour('#90EE90')
        sequence.add_region(region)

    sequence.address_formatter = ValueFormatterAcorn()
    sequence.size_formatter = ValueFormatterAcorn()

    sequence.add_discontinuities(fill=None, outline='#90EE90', style='dashed')
    sequence.add_address_labels(start=False, end=False, size=False, side='right', end_exclusive=False,
                                final_end=True)
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
    sequence.region_max_height = sequence.region_min_height

    for (address, size, danum, name) in memory:
        region = MemoryRegion(address, size)
        region.add_label(name)
        region.add_label("DA #{}".format(danum), ('il', 'it'))
        sequence.add_region(region)

    sequence.address_formatter = ValueFormatterAcorn()
    sequence.size_formatter = ValueFormatterSI()

    sequence.set_fill_colour(None, '#C7E3EC')
    sequence.set_outline_colour(None, '#336DA5')

    sequence.add_discontinuities(fill='#CCCCCC', outline='#336DA5', style='cut-out')
    sequence.add_address_labels(start=True, end=True, size=True)

    renderer = renderer_class(filename)
    renderer.render(sequence)

elif example == 'labels':
    # All the label positions
    sequence = Sequence()

    rownames = ('jt', 'it', 'ic', 'ib', 'jb')
    colnames = ('elf', 'elm', 'el', 'il', 'ic', 'ir', 'er', 'erm', 'erf')

    address = 0x1000

    # First all the row positions
    col = 'ic'
    for row in rownames:
        region = MemoryRegion(address, 1)
        region.add_label('(%s, %s)' % (col, row), (col, row))
        sequence.add_region(region)
        address -= 1

    sequence.add_region(DiscontinuityRegion(address, 1))
    address -= 1

    # Now all the column positions
    row = 'ic'
    for col in colnames:
        region = MemoryRegion(address, 1)
        region.add_label('(%s, %s)' % (col, row), (col, row))
        sequence.add_region(region)
        address -= 1

    renderer = renderer_class(filename)
    renderer.render(sequence)

elif example == 'labelsmiddle':
    # All the label positions
    sequence = Sequence()

    rownames = ('it', 'ic', 'ib')
    colnames = ('il', 'ic', 'ir')

    address = 0x1000

    # All the middle combinations
    combinations = 1<<(len(rownames) * len(colnames))
    for index in range(0, combinations):
        region = MemoryRegion(address, 1)
        for bit in range(0, len(rownames) * len(colnames)):
            if not (index & (1<<bit)):
                continue
            row = rownames[bit % len(rownames)]
            col = colnames[int(bit / len(rownames))]

            region.add_label('(%s, %s)' % (col, row), (col, row))
        sequence.add_region(region)
        address -= 1

    sequence.add_address_labels(start=True)

    renderer = renderer_class(filename)
    renderer.render(sequence)

elif example == 'discontinuities':
    # All the discontinuity styles
    sequence = Sequence()

    styles = ('default', 'zig-zag', 'cut-out', 'dotted', 'dashed')

    address = 0x1000

    region = MemoryRegion(address, 1)
    region.set_fill_colour('#C7E3EC')
    region.set_outline_colour('#336DA5')
    sequence.add_region(region)
    address -= 1

    for style in styles:
        region = DiscontinuityRegion(address, 1)
        region.set_style(style)
        region.set_fill_colour('#CCCCCC')
        region.set_outline_colour('#336DA5')
        region.add_label(style)
        sequence.add_region(region)
        address -= 1

        region = MemoryRegion(address, 1)
        region.set_fill_colour('#C7E3EC')
        region.set_outline_colour('#336DA5')
        sequence.add_region(region)
        address -= 1

    renderer = renderer_class(filename)
    renderer.render(sequence)

else:
    print("Unrecognised example '{}'".format(example))
