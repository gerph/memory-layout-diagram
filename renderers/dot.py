"""
Graphviz Dot renderer for the Memory Layout Diagrams.
"""

from memory_layout import Sequence, MemoryRegion, DiscontinuityRegion

from . import MLDRenderBase


class MLDRenderGraphviz(MLDRenderBase):
    file_suffix = '.dot'
    default_fontname = "Optima, Rachana, Sawasdee, sans-serif"

    def expand_colour(self, colour):
        if not colour:
            return '#FFFFFF00'
        if colour[0] == '#' and len(colour) == 4:
            return '#{}{}{}{}{}{}'.format(colour[1], colour[1],
                                          colour[2], colour[2],
                                          colour[3], colour[3])
        return colour


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

        def font_and_escape(label):
            if not label:
                return ''
            escaped = escape(label)
            if label.colour and escaped:
                return '<font color="%s">%s</font>' % (self.expand_colour(label.colour),
                                                       escaped)
            return escaped

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
                                                                                                        font_and_escape(labels[(colkeys[2], rowkey)]))
            elif used == 0b010:
                # Just centred
                row = '<td colspan="3" align="center" valign="{}" width="{}" height="{}">{}</td>'.format(valign, cellwidth, cellheight,
                                                                                                         font_and_escape(labels[(colkeys[1], rowkey)]))
            elif used == 0b100:
                # Just left aligned
                row = '<td colspan="3" align="left" valign="{}" width="{}" height="{}">{}</td>'.format(valign, cellwidth, cellheight,
                                                                                                       font_and_escape(labels[(colkeys[0], rowkey)]))
            elif used == 0b000:
                # Nothing
                row = '<td colspan="3" align="center" valign="{}" width="{}" height="{}"></td>'.format(valign, cellwidth, cellheight)

            elif used == 0b101:
                # Left and right aligned
                row = '<td colspan="2" align="left" valign="{}" height="{}">{}</td>'.format(valign, cellheight,
                                                                                            font_and_escape(labels[(colkeys[0], rowkey)]))
                row += '<td align="right" valign="{}" height="{}">{}</td>'.format(valign, cellheight,
                                                                                  font_and_escape(labels[(colkeys[2], rowkey)]))
            else:
                row = '<td align="left" valign="{}" height="{}">{}</td>'.format(valign, cellheight,
                                                                                font_and_escape(labels.get((colkeys[0], rowkey), None)))
                row += '<td align="center" valign="{}" height="{}">{}</td>'.format(valign, cellheight,
                                                                                   font_and_escape(labels.get((colkeys[1], rowkey), None)))
                row += '<td align="right" valign="{}" height="{}">{}</td>'.format(valign, cellheight,
                                                                                  font_and_escape(labels.get((colkeys[2], rowkey), None)))
            rows.append("<tr>{}</tr>".format(row))

        return '<table cellborder="0" cellspacing="0" cellpadding="%s" border="0" fixedsize="false" color="blue" height="%.2f" width="%.2f">%s</table>' \
                    % (cellpadding, height * 72, width * 72, ''.join(rows))

    def header(self, memorymap):
        self.write("""
digraph memory {{
    ranksep = 0;
    nodesep = 0;
    graph [
        pad = {};
        bgcolor = "{}";
    ];
    node [
        shape=rect,
        penwidth=2,
        fontname="{}",
        fontsize = 12
    ];
    edge [
        fontname="{}",
        style=invis
    ];
""".format(memorymap.document_padding, self.expand_colour(memorymap.document_bgcolour),
           self.default_fontname, self.default_fontname))

    def footer(self):
        self.write("""
}
""")

    def render(self, memorymap):
        self.header(memorymap)
        if isinstance(memorymap, Sequence):
            self.render_sequence(memorymap, '')

        elif isinstance(memorymap, MultipleMaps):
            for (index, sequence) in enumerate(memorymap):
                self.render_sequence(sequence, "_{}_".format(index))

        self.footer()

    def render_sequence(self, sequence, identifier):
        last_region = None
        last_left = None

        any_on_left = False
        for region in sequence.regions:
            if any(position[0][0:2] == 'el' for position in region.labels.keys()):
                any_on_left = True
                break

        for region in reversed(sequence.regions):
            height_in_units = (region.size / sequence.unit_size)
            height_in_units = max(height_in_units, sequence.min_units)
            height = height_in_units * sequence.unit_height
            height = max(height, sequence.region_min_height)
            height = min(height, sequence.region_max_height)

            if isinstance(region, DiscontinuityRegion):
                height = min(height, sequence.discontinuity_height)

            # We must write the nodes in the correct order for positioning purposes
            has_left = any_on_left
            has_right = any(position[0][0:2] == 'er' for position in region.labels.keys())
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

            style = []
            if isinstance(region, DiscontinuityRegion):
                if region.discontinuity_style in ('dotted', 'dashed'):
                    style.append(region.discontinuity_style)
                else:
                    style.append('dashed')

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
                self.write('    region%s%08x [ label="%s%s", labelloc=%s%s ];\n' % (identifier, region.address,
                                                                                    text,
                                                                                    labeljust,
                                                                                    label.position[1][1],
                                                                                    ', fontcolor="%s"' % (label.colour,) if label.colour else ''))
            else:
                # Multiple labels.
                # We turn them into a table.
                table = self.region_table(sequence, sequence.region_width, height, ilabels)
                self.write('    region%s%08x [ label=<%s> labelloc=c labeljust=c ];\n'
                            % (identifier, region.address, table))

            if region.fill or region.outline or style:
                attrs = []
                if region.fill:
                    attrs.append('fillcolor="{}"'.format(self.expand_colour(region.fill)))
                    style.append('filled')
                if region.outline:
                    attrs.append('color="{}"'.format(self.expand_colour(region.outline)))
                    attrs.append('penwidth="{}"'.format(region.outline_width * 72))
                if style:
                    attrs.append('style="{}"'.format(','.join(style)))
                self.write('    region%s%08x [ %s ];\n' % (identifier, region.address,
                                                           ', '.join(attrs)))

            if last_region:
                self.write('    region%s%08x -> region%s%08x;\n' % (identifier, last_region.address,
                                                                    identifier, region.address))
            last_region = region

