"""
Process a memory layout definition to generate a diagram.
"""

import argparse
import os
import sys

import memory_layout.simpleyaml

from memory_layout import (
        Sequence, MemoryRegion, DiscontinuityRegion,
        ValueFormatterAcorn, ValueFormatterSI, ValueFormatterSI2, ValueFormatterCommodore,
        ValueFormatterC
    )
from memory_layout.renderers.dot import MLDRenderGraphviz
from memory_layout.renderers.svg import MLDRenderSVG


try:
    unicode
except NameError:
    unicode = str


class MLDError(Exception):
    pass


class Defaults(object):
    colour = None
    fill = None
    outline = None
    outline_width = 2.0 / 72
    position = 'c'


# Renderer names to classes
renderers = {
        'svg': MLDRenderSVG,
        'dot': MLDRenderGraphviz,
    }


# Decoding the formatter names to the classes they represent
formatters = {
        'acorn': ValueFormatterAcorn,
        'commodore': ValueFormatterCommodore,
        'c': ValueFormatterC,
        'si': ValueFormatterSI,
        'si2': ValueFormatterSI2,
    }


# Some simple positionings to make it easier to say where to put things
simple_positions = {
        'c': ('ic', 'ic'),
        't': ('ic', 'it'),
        'b': ('ic', 'ib'),
        'l': ('il', 'ic'),
        'r': ('ir', 'ic'),
        'tl': ('il', 'it'),
        'tr': ('ir', 'it'),
        'bl': ('il', 'ib'),
        'br': ('ir', 'ib'),
    }


def decode_position(simple_position):
    if isinstance(simple_position, tuple):
        # This is a fully specified tuple
        return simple_position
    if ',' in simple_position:
        parts = simple_position.split(',')
        if len(parts) == 2:
            return tuple(parts)
    position = simple_positions.get(simple_position, None)
    if position:
        return position

    raise MLDError("Unrecognised label position '{}'".format(simple_position))


def decode_formatter(format_name):
    cls = formatters.get(format_name, None)
    if not cls:
        raise MLDError("Unrecognised formatter name '{}'. Valid names are: {}'"
                            .format(format_name, ', '.join(sorted(formatters))))
    return cls()


def decode_distance(distance):
    """
    Decode a distance that might be a string.

    By default distances are in inches, but it's useful to be able to specify them in points.
    """
    if isinstance(distance, (int, float)):
        return distance
    if distance.endswith('pt'):
        distance = distance[:-2].strip()
        distance = float(distance) / 72
    return distance


def main():
    name = os.path.basename(sys.argv[0])
    if name == '__main__.py':
        name = 'python -m memory_layout'
    parser = argparse.ArgumentParser(usage="%s [<options>] <input>" % (name,))
    parser.add_argument('input', action='store',
                        help="Input MLD file")
    parser.add_argument('--format', choices=sorted(renderers.keys()), default='svg',
                        help="Format to generate output in")
    parser.add_argument('--output-prefix', action='store', type=str,
                        help="Output filename prefix")
    parser.add_argument('--output', action='store', type=str,
                        help="Output filename")

    options = parser.parse_args()

    renderer_class = renderers.get(options.format)

    if options.output:
        output_filename = options.output
    elif options.output_prefix:
        output_filename = "{}{}".format(options.output_prefix, renderer_class.file_suffix)
    else:
        # They didn't give any output name, so default to the input, without the extension,
        # with the extension for the format.
        output_filename = options.input
        if output_filename.endswith('.mld'):
            output_filename = output_filename[:-4]
        output_filename = "{}{}".format(output_filename, renderer_class.file_suffix)


    defaults = Defaults()

    with open(options.input, 'r') as fh:
        mld = memory_layout.simpleyaml.load(fh)

        sequence = Sequence()

        if 'defaults' in mld:
            mlddefaults = mld['defaults']

            # Layout options
            if 'unit_size' in mlddefaults:
                sequence.unit_size = mlddefaults['unit_size']

            if 'unit_height' in mlddefaults:
                sequence.unit_height = decode_distance(mlddefaults['unit_height'])

            if 'min_height' in mlddefaults:
                sequence.region_min_height = decode_distance(mlddefaults['min_height'])

            if 'max_height' in mlddefaults:
                sequence.region_max_height = decode_distance(mlddefaults['max_height'])

            if 'discontinuity_height' in mlddefaults:
                sequence.discontinuity_height = decode_distance(mlddefaults['discontinuity_height'])

            if 'region_width' in mlddefaults:
                sequence.region_width = decode_distance(mlddefaults['region_width'])

            # Presentation options
            if 'background' in mlddefaults:
                sequence.document_bgcolour = mlddefaults['background']

            if 'fill' in mlddefaults:
                defaults.fill = mlddefaults['fill']

            if 'outline' in mlddefaults:
                defaults.outline = mlddefaults['outline']

            if 'outline_width' in mlddefaults:
                defaults.outline_width = mlddefaults['outline_width']

            if 'colour' in mlddefaults:
                defaults.colour = mlddefaults['colour']

            if 'position' in mlddefaults:
                defaults.position = decode_position(mlddefaults['position'])

            # Label formats
            if 'address_format' in mlddefaults:
                sequence.address_formatter = decode_formatter(mlddefaults['address_format'])

            if 'size_format' in mlddefaults:
                sequence.size_formatter = decode_formatter(mlddefaults['size_format'])

        if 'layout' not in mld:
            raise MLDError("'layout' not defined")

        layout = mld['layout']

        # In the simpleyaml parser, the keys are always strings.
        # We need to ensure that they are decimal values.
        ordered_layout = []
        for (key, value) in layout.items():
            try:
                # We could perform other translations - we could actually decode
                # the address given through the address formatter, to make the system
                # able to use the address labels that are in the output, if that was
                # useful.
                if key.startswith ('0x'):
                    key = int(key[2:], 16)
                else:
                    key = int(key)
            except ValueError:
                raise MLDError("Layout address '{}' is not recognised".format(key))
            ordered_layout.append((key, value))
        ordered_layout = sorted(ordered_layout)

        # We need to reset the junction points on the addresses afterwards as we need to change both
        # the high and low junctions on following/preceding regions, otherwise (for example) the solid
        # junction on the upper region will cover the dashed junction on the lower region.
        reset_junctions = []

        for (address, config) in ordered_layout:
            if isinstance(config, str):
                config = {
                        'label': config
                    }
            is_discontinuity = config.get('discontinuity', False)

            # The core region type
            size = config.get('size', sequence.unit_size)
            if is_discontinuity:
                region = DiscontinuityRegion(address, size)
            else:
                region = MemoryRegion(address, size)

            # The presentation options
            colour = config.get('fill', defaults.fill)
            if colour:
                region.set_fill_colour(colour)
            colour = config.get('outline', defaults.outline)
            if colour:
                region.set_outline_colour(colour)

            width = config.get('outline_width', defaults.outline_width)
            if width:
                region.set_outline_width(decode_distance(width))

            junction_type = config.get('junction_low', None)
            if junction_type:
                reset_junctions.append((address, junction_type, None))

            junction_type = config.get('junction_high', None)
            if junction_type:
                reset_junctions.append((address, None, junction_type))

            # Labels
            labels = config.get('labels', [])
            if 'label' in config:
                if isinstance(labels, dict):
                    labels[defaults.position] = config['label']
                elif isinstance(labels, list):
                    labels.append(config['label'])
            if isinstance(labels, dict):
                # Turn the dictionary into a list
                labels_list = []
                for position, label in labels.items():
                    if isinstance(label, str):
                        label = {
                                'label': label,
                                'position': position
                            }
                    else:
                        if 'position' not in label:
                            label['position'] = position
                    labels_list.append(label)
                labels = labels_list

            # Now the labels are a list, we can process them
            for label in labels:
                colour = defaults.colour
                position = defaults.position
                if isinstance(label, (str, unicode)):
                    text = label
                elif isinstance(label, dict):
                    text = label['label']
                    position = label.get('position', position)
                    colour = label.get('colour', colour)

                label = region.add_label(text, decode_position(position), colour=colour)


            sequence.add_region(region)

        for (address, low, high) in reset_junctions:
            if low:
                sequence.set_outline_lower(address, low)
            if high:
                sequence.set_outline_upper(address, high)

        # Cannot think of a name for these options
        # If they were plugins that'd be kinda cute - to add in extras.
        if 'automatic' in mld:
            mldauto = mld['automatic']

            if 'discontinuities' in mldauto:
                mlddisc = mldauto['discontinuities']

                enable = True
                fill = defaults.fill
                outline = defaults.outline
                style = None
                if isinstance(mlddisc, bool):
                    enable = mlddisc
                elif isinstance(mlddisc, dict):
                    enable = mlddisc.get('enable', True)
                    fill = mlddisc.get('fill', fill)
                    outline = mlddisc.get('outline', outline)
                    style = mlddisc.get('style', None)

                if enable:
                    sequence.add_discontinuities(fill=fill, outline=outline, style=style)

            if 'addresses' in mldauto:
                mldaddr = mldauto['addresses']
                enable = True

                start = True
                end = False
                size = False
                side = 'right'
                end_exclusive = True
                final_end = False
                omit = []

                if isinstance(mldaddr, bool):
                    enable = mldaddr
                elif isinstance(mldaddr, dict):
                    enable = mldaddr.get('enable', True)
                    start = mldaddr.get('start', start)
                    end = mldaddr.get('end', end)
                    size = mldaddr.get('size', size)
                    side = mldaddr.get('side', side)
                    end_exclusive = mldaddr.get('end_exclusive', end_exclusive)
                    final_end = mldaddr.get('final_end', final_end)
                    omit = mldaddr.get('omit', [])
                    colour = mldaddr.get('colour', defaults.colour)
                    if isinstance(omit, int):
                        omit = [omit]

                if enable:
                    sequence.add_address_labels(start=start, end=end, size=size,
                                                side=side, end_exclusive=end_exclusive,
                                                final_end=final_end,
                                                omit=omit,
                                                colour=colour)

    renderer = renderer_class(output_filename)
    renderer.render(sequence)


if __name__ == '__main__':
    main()
