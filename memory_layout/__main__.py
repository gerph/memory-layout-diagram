# pylint: skip-file
# flake8: noqa
"""
Process a memory layout definition to generate a diagram.
"""

import argparse
import difflib
import os
import re
import sys

import memory_layout.simpleyaml

from memory_layout import (
        Sequence, MemoryRegion, DiscontinuityRegion,
        ValueFormatterAcorn, ValueFormatterSI, ValueFormatterSI2,
        ValueFormatterHuman, ValueFormatterCommodore,
        ValueFormatterC, ValueFormatterC8
    )
from memory_layout.renderers.dot import MLDRenderGraphviz
from memory_layout.renderers.svg import MLDRenderSVG


try:
    unicode
except NameError:
    unicode = str


class MLDError(Exception):
    """
    A problem with the MLD file which prevents any diagram being produced.
    """
    pass


class Defaults(object):
    colour = None
    colour_size = None
    fontname = None
    fontname_address = None
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
        'c8': ValueFormatterC8,
        'si': ValueFormatterSI,
        'si2': ValueFormatterSI2,
        'human': ValueFormatterHuman,
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


# Valid label position parts (see RegionLabel)
position_x = ('il', 'ic', 'ir', 'el', 'elm', 'elf', 'er', 'erm', 'erf')
position_y = ('ib', 'ic', 'it', 'jt', 'jb')

# Junction types and discontinuity styles which the renderers understand.
junction_types = ('solid', 'dotted', 'dashed', 'double', 'ticks', 'none')
discontinuity_styles = ('default', 'zig-zag', 'cut-out', 'dotted', 'dashed')

# The CSS colour names, which are the names that the renderers can use
colour_names = frozenset("""
    aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet
    brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan
    darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta
    darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen darkslateblue
    darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey
    dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray
    green greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush
    lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray
    lightgreen lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray
    lightslategrey lightsteelblue lightyellow lime limegreen linen magenta maroon
    mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue
    mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin
    navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen
    paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple
    rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna
    silver skyblue slateblue slategray slategrey snow springgreen steelblue tan teal thistle
    tomato turquoise violet wheat white whitesmoke yellow yellowgreen
    none transparent
    """.split())
colour_hex_re = re.compile(r'^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')
colour_func_re = re.compile(r'^(rgb|rgba|hsl|hsla)\([-0-9.,%\s/]+\)$')

# The keys which are understood in each part of the file.
known_top_keys = ('defaults', 'layout', 'automatic')
known_defaults_keys = ('unit_size', 'unit_height', 'min_height', 'max_height', 'discontinuity_height',
                       'region_width', 'background', 'fill', 'outline', 'outline_width', 'colour',
                       'colour_size', 'fontname', 'fontname_address', 'position',
                       'address_format', 'size_format')
known_region_keys = ('size', 'label', 'labels', 'discontinuity', 'fill', 'outline', 'outline_width',
                     'junction_low', 'junction_high')
known_label_keys = ('label', 'position', 'colour')
known_automatic_keys = ('discontinuities', 'addresses')
known_discontinuities_keys = ('enable', 'fill', 'outline', 'style')
known_addresses_keys = ('enable', 'start', 'end', 'size', 'side', 'end_exclusive', 'final_end',
                        'omit', 'colour')


def decode_position(simple_position):
    if isinstance(simple_position, tuple):
        # This is a fully specified tuple
        return simple_position
    if not isinstance(simple_position, (str, unicode)):
        raise MLDError("Label position '{}' is not a string".format(simple_position))
    if ',' in simple_position:
        parts = [part.strip() for part in simple_position.split(',')]
        if len(parts) == 2:
            if parts[0] not in position_x:
                raise MLDError("Unrecognised horizontal label position '{}' in '{}'. Valid values are: {}"
                                    .format(parts[0], simple_position, ', '.join(position_x)))
            if parts[1] not in position_y:
                raise MLDError("Unrecognised vertical label position '{}' in '{}'. Valid values are: {}"
                                    .format(parts[1], simple_position, ', '.join(position_y)))
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
    if isinstance(distance, bool):
        raise MLDError("Distance '{}' is not a number".format(distance))
    if isinstance(distance, (int, float)):
        if distance < 0:
            raise MLDError("Distance '{}' must not be negative".format(distance))
        return distance
    if isinstance(distance, (str, unicode)):
        text = distance.strip()
        factor = 1
        if text.endswith('pt'):
            text = text[:-2].strip()
            factor = 72
        try:
            value = float(text) / factor
        except ValueError:
            value = None
        if value is not None and value >= 0:
            return value
    raise MLDError("Distance '{}' is not a number of inches, or a number of points with a 'pt' suffix"
                        .format(distance))


def decode_colour(colour):
    """
    Check that a colour is one we recognise.
    """
    if colour is None:
        raise MLDError("No colour was given (colours starting with '#' must be quoted)")
    if isinstance(colour, (str, unicode)):
        text = colour.strip()
        if colour_hex_re.match(text) or colour_func_re.match(text) or text.lower() in colour_names:
            return colour
    raise MLDError("Colour '{}' is not a CSS colour name, or in #RGB or #RRGGBB form".format(colour))


class Problems(object):
    """
    Collects the non-fatal problems found in an MLD file.
    """

    def __init__(self):
        self.messages = []

    def add(self, message):
        self.messages.append(message)

    def __len__(self):
        return len(self.messages)

    def __iter__(self):
        return iter(self.messages)


class Checker(object):
    """
    Validates values from the MLD file, recording a problem for each one that is wrong.

    Each check returns the (decoded) value if it was acceptable, or `None` if there was a
    problem, so that the caller can fall back to its default.
    """

    def __init__(self, problems):
        self.problems = problems

    def mapping(self, value, where):
        if value is None:
            return {}
        if not isinstance(value, dict):
            self.problems.add("'{}' should be a mapping of keys to values".format(where))
            return {}
        return value

    def keys(self, mapping, known, where):
        for key in mapping:
            if key in known:
                continue
            close = difflib.get_close_matches(str(key), known, n=1)
            if close:
                hint = " (did you mean '{}'?)".format(close[0])
            else:
                hint = " (known keys are: {})".format(', '.join(known))
            self.problems.add("Unknown key '{}' in {}{}".format(key, where, hint))

    def decode(self, function, value, where):
        try:
            return function(value)
        except MLDError as ex:
            self.problems.add("{}: {}".format(where, ex))
            return None

    def colour(self, value, where):
        return self.decode(decode_colour, value, where)

    def distance(self, value, where):
        return self.decode(decode_distance, value, where)

    def position(self, value, where):
        return self.decode(decode_position, value, where)

    def formatter(self, value, where):
        return self.decode(decode_formatter, value, where)

    def choice(self, value, choices, where):
        if value not in choices:
            self.problems.add("{}: '{}' is not one of: {}".format(where, value, ', '.join(choices)))
            return None
        return value

    def boolean(self, value, where):
        if not isinstance(value, bool):
            self.problems.add("{}: '{}' should be true or false".format(where, value))
            return None
        return value

    def integer(self, value, where, minimum=0):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            self.problems.add("{}: '{}' should be a whole number of at least {}".format(where, value, minimum))
            return None
        return value

    def text(self, value, where):
        if isinstance(value, bool) or value is None or isinstance(value, (dict, list)):
            self.problems.add("{}: '{}' should be text".format(where, value))
            return None
        return value if isinstance(value, (str, unicode)) else str(value)


def process_defaults(mlddefaults, check, sequence, defaults):
    """
    Apply the `defaults` section to the sequence and our defaults.
    """
    mlddefaults = check.mapping(mlddefaults, 'defaults')
    check.keys(mlddefaults, known_defaults_keys, "'defaults'")

    for key, value in mlddefaults.items():
        if key not in known_defaults_keys:
            continue
        where = "defaults.{}".format(key)

        # Layout options
        if key == 'unit_size':
            value = check.integer(value, where, minimum=1)
            if value is not None:
                sequence.unit_size = value
        elif key == 'unit_height':
            value = check.distance(value, where)
            if value is not None:
                sequence.unit_height = value
        elif key == 'min_height':
            value = check.distance(value, where)
            if value is not None:
                sequence.region_min_height = value
        elif key == 'max_height':
            value = check.distance(value, where)
            if value is not None:
                sequence.region_max_height = value
        elif key == 'discontinuity_height':
            value = check.distance(value, where)
            if value is not None:
                sequence.discontinuity_height = value
        elif key == 'region_width':
            value = check.distance(value, where)
            if value is not None:
                sequence.region_width = value

        # Presentation options
        elif key == 'background':
            value = check.colour(value, where)
            if value is not None:
                sequence.document_bgcolour = value
        elif key in ('fill', 'outline', 'colour', 'colour_size'):
            value = check.colour(value, where)
            if value is not None:
                setattr(defaults, key, value)
        elif key == 'outline_width':
            value = check.distance(value, where)
            if value is not None:
                defaults.outline_width = value
        elif key in ('fontname', 'fontname_address'):
            value = check.text(value, where)
            if value is not None:
                setattr(defaults, key, value)
        elif key == 'position':
            value = check.position(value, where)
            if value is not None:
                defaults.position = value

        # Label formats
        elif key == 'address_format':
            value = check.formatter(value, where)
            if value is not None:
                sequence.address_formatter = value
        elif key == 'size_format':
            value = check.formatter(value, where)
            if value is not None:
                sequence.size_formatter = value


def decode_layout_address(key):
    """
    In the simpleyaml parser, the keys are always strings.
    We need to ensure that they are numeric values.
    """
    try:
        # We could perform other translations - we could actually decode
        # the address given through the address formatter, to make the system
        # able to use the address labels that are in the output, if that was
        # useful.
        if key.startswith('0x'):
            return int(key[2:], 16)
        return int(key)
    except ValueError:
        raise MLDError("Layout address '{}' is not recognised".format(key))


def region_labels(config, defaults, check, where):
    """
    Decode the labels for a region into a list of (text, position, colour) tuples.
    """
    labels = config.get('labels', [])
    if labels is None:
        labels = []
    if 'label' in config:
        if isinstance(labels, dict):
            labels[defaults.position] = config['label']
        elif isinstance(labels, list):
            labels.append(config['label'])
    if isinstance(labels, dict):
        # Turn the dictionary into a list
        labels_list = []
        for position, label in labels.items():
            if isinstance(label, dict):
                if 'position' not in label:
                    label['position'] = position
            else:
                label = {
                        'label': label,
                        'position': position
                    }
            labels_list.append(label)
        labels = labels_list
    elif not isinstance(labels, list):
        check.problems.add("{}: 'labels' should be a list or mapping of labels".format(where))
        labels = []

    # Now the labels are a list, we can process them
    decoded = []
    for index, label in enumerate(labels):
        label_where = "{} label {}".format(where, index + 1)
        colour = defaults.colour
        position = defaults.position
        if isinstance(label, dict):
            check.keys(label, known_label_keys, label_where)
            if 'label' not in label:
                check.problems.add("{}: no 'label' text was given".format(label_where))
                continue
            text = check.text(label['label'], label_where)
            if 'position' in label:
                position = check.position(label['position'], label_where + " position") or position
            if 'colour' in label:
                colour = check.colour(label['colour'], label_where + " colour") or colour
        else:
            text = check.text(label, label_where)
        if text is None:
            continue
        if not isinstance(position, tuple):
            position = decode_position(position)
        decoded.append((text, position, colour))
    return decoded


def process_layout(layout, check, sequence, defaults):
    """
    Create the regions from the `layout` section.
    """
    if not isinstance(layout, dict) or not layout:
        raise MLDError("'layout' must contain at least one region, as a mapping of addresses to regions")

    ordered_layout = []
    seen = {}
    for (key, value) in layout.items():
        address = decode_layout_address(str(key))
        if address in seen:
            check.problems.add("Layout addresses '{}' and '{}' are the same address; one will be lost"
                                    .format(seen[address], key))
        seen[address] = key
        ordered_layout.append((address, key, value))
    ordered_layout.sort(key=lambda item: item[0])

    # We need to reset the junction points on the addresses afterwards as we need to change both
    # the high and low junctions on following/preceding regions, otherwise (for example) the solid
    # junction on the upper region will cover the dashed junction on the lower region.
    reset_junctions = []

    for (address, key, config) in ordered_layout:
        where = "layout '{}'".format(key)
        if config is None:
            config = {}
        elif not isinstance(config, dict):
            # A simple value is just the label for the region
            config = {
                    'label': config
                }
        check.keys(config, known_region_keys, where)

        is_discontinuity = False
        if 'discontinuity' in config:
            is_discontinuity = check.boolean(config['discontinuity'], where + " discontinuity") or False

        # The core region type
        size = sequence.unit_size
        if 'size' in config:
            size = check.integer(config['size'], where + " size", minimum=1) or size
        if is_discontinuity:
            region = DiscontinuityRegion(address, size)
        else:
            region = MemoryRegion(address, size)

        # The presentation options
        colour = defaults.fill
        if 'fill' in config:
            colour = check.colour(config['fill'], where + " fill") or colour
        if colour:
            region.set_fill_colour(colour)

        colour = defaults.outline
        if 'outline' in config:
            colour = check.colour(config['outline'], where + " outline") or colour
        if colour:
            region.set_outline_colour(colour)

        width = defaults.outline_width
        if 'outline_width' in config:
            width = check.distance(config['outline_width'], where + " outline_width") or width
        if width:
            region.set_outline_width(width)

        if config.get('junction_low', None):
            junction_type = check.choice(config['junction_low'], junction_types, where + " junction_low")
            if junction_type:
                reset_junctions.append((address, junction_type, None))

        if config.get('junction_high', None):
            junction_type = check.choice(config['junction_high'], junction_types, where + " junction_high")
            if junction_type:
                reset_junctions.append((address, None, junction_type))

        # Labels
        for (text, position, colour) in region_labels(config, defaults, check, where):
            region.add_label(text, position, colour=colour)

        sequence.add_region(region)

    for (address, low, high) in reset_junctions:
        if low:
            sequence.set_outline_lower(address, low)
        if high:
            sequence.set_outline_upper(address, high)


def process_automatic(mldauto, check, sequence, defaults):
    """
    Apply the `automatic` section to the sequence.
    """
    mldauto = check.mapping(mldauto, 'automatic')
    check.keys(mldauto, known_automatic_keys, "'automatic'")

    # Cannot think of a name for these options
    # If they were plugins that'd be kinda cute - to add in extras.
    if 'discontinuities' in mldauto:
        mlddisc = mldauto['discontinuities']
        where = "automatic.discontinuities"

        enable = True
        fill = defaults.fill
        outline = defaults.outline
        style = None
        if isinstance(mlddisc, bool):
            enable = mlddisc
        elif isinstance(mlddisc, dict) or mlddisc is None:
            mlddisc = check.mapping(mlddisc, where)
            check.keys(mlddisc, known_discontinuities_keys, "'{}'".format(where))
            if 'enable' in mlddisc:
                enable = check.boolean(mlddisc['enable'], where + ".enable")
                if enable is None:
                    enable = True
            if 'fill' in mlddisc:
                fill = check.colour(mlddisc['fill'], where + ".fill") or fill
            if 'outline' in mlddisc:
                outline = check.colour(mlddisc['outline'], where + ".outline") or outline
            if 'style' in mlddisc:
                style = check.choice(mlddisc['style'], discontinuity_styles, where + ".style")
        else:
            check.problems.add("{}: '{}' should be true, false or a mapping".format(where, mlddisc))

        if enable:
            sequence.add_discontinuities(fill=fill, outline=outline, style=style,
                                         outline_width=defaults.outline_width)

    if 'addresses' in mldauto:
        mldaddr = mldauto['addresses']
        where = "automatic.addresses"

        enable = True
        start = True
        end = False
        size = False
        side = 'right'
        end_exclusive = True
        final_end = False
        omit = []
        colour = defaults.colour

        if isinstance(mldaddr, bool):
            enable = mldaddr
        elif isinstance(mldaddr, dict) or mldaddr is None:
            mldaddr = check.mapping(mldaddr, where)
            check.keys(mldaddr, known_addresses_keys, "'{}'".format(where))
            flags = {
                    'enable': enable, 'start': start, 'end': end, 'size': size,
                    'end_exclusive': end_exclusive, 'final_end': final_end,
                }
            for name in sorted(flags):
                if name in mldaddr:
                    value = check.boolean(mldaddr[name], "{}.{}".format(where, name))
                    if value is not None:
                        flags[name] = value
            enable, start, end, size = flags['enable'], flags['start'], flags['end'], flags['size']
            end_exclusive, final_end = flags['end_exclusive'], flags['final_end']

            if 'side' in mldaddr:
                side = check.choice(mldaddr['side'], ('left', 'right'), where + ".side") or side
            if 'colour' in mldaddr:
                colour = check.colour(mldaddr['colour'], where + ".colour") or colour
            if 'omit' in mldaddr:
                omit = mldaddr['omit']
                if isinstance(omit, int) and not isinstance(omit, bool):
                    omit = [omit]
                if not isinstance(omit, list) or [x for x in omit if isinstance(x, bool) or not isinstance(x, int)]:
                    check.problems.add("{}.omit: '{}' should be an address, or a list of addresses"
                                            .format(where, omit))
                    omit = []
        else:
            check.problems.add("{}: '{}' should be true, false or a mapping".format(where, mldaddr))

        if enable:
            sequence.add_address_labels(start=start, end=end, size=size,
                                        side=side, end_exclusive=end_exclusive,
                                        final_end=final_end,
                                        omit=omit,
                                        colour=colour,
                                        colour_size=defaults.colour_size,
                                        fontname_address=defaults.fontname_address)


def build_sequence(mld, problems):
    """
    Create the memory layout sequence from a decoded MLD document.

    @param mld:         The decoded document (a mapping)
    @param problems:    Problems object which will be given the details of anything
                        that was wrong, but which we could work around.

    @return:    tuple of (Sequence, Defaults)

    @raises:    MLDError if the document cannot be turned into a diagram at all.
    """
    if not isinstance(mld, dict):
        raise MLDError("The document should be a mapping with 'defaults', 'layout' and 'automatic' sections")

    check = Checker(problems)
    check.keys(mld, known_top_keys, "the top level")

    defaults = Defaults()
    sequence = Sequence()

    if 'defaults' in mld:
        process_defaults(mld['defaults'], check, sequence, defaults)

    if 'layout' not in mld:
        raise MLDError("'layout' not defined")
    process_layout(mld['layout'], check, sequence, defaults)

    if 'automatic' in mld:
        process_automatic(mld['automatic'], check, sequence, defaults)

    return sequence, defaults


def main(argv=None):
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
    parser.add_argument('--strict', action='store_true',
                        help="Treat unrecognised keys and invalid values as errors, rather than warnings")

    options = parser.parse_args(argv)

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

    problems = Problems()
    try:
        with open(options.input, 'r') as fh:
            mld = memory_layout.simpleyaml.load(fh)
        sequence, defaults = build_sequence(mld, problems)

    except IOError as ex:
        sys.stderr.write("{}: error: {}\n".format(name, ex))
        return 1

    except memory_layout.simpleyaml.YAMLError as ex:
        sys.stderr.write("{}: error: {}: {}\n".format(name, options.input, ex))
        return 1

    except MLDError as ex:
        sys.stderr.write("{}: error: {}: {}\n".format(name, options.input, ex))
        return 1

    level = 'error' if options.strict else 'warning'
    for message in problems:
        sys.stderr.write("{}: {}: {}: {}\n".format(name, level, options.input, message))

    if problems and options.strict:
        # In strict mode we do not write out a diagram which we know to be wrong
        return 1

    renderer = renderer_class(output_filename)
    if defaults.fontname:
        renderer.default_fontname = defaults.fontname
    renderer.render(sequence)
    return 0


if __name__ == '__main__':
    sys.exit(main())
