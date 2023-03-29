# Memory layout diagrams

## Introduction

The Memory Layout Diagram tool is intended to produce graphical diagrams of the layout of memory regions in a system. These are most useful in describing retro systems, or systems which have fixed logical memory maps. They are commonly used to explain the layout of memory regions in developer guides for hardware systems.

The tool is a python program which can generate diagrams either programatically, or through a domain specific language. The domain specific language is described below.

## Example diagrams

Example diagrams can be found in the public Wiki: https://github.com/gerph/memory-layout-diagram/wiki#example-images

## Installation

The tool does not need to be installed, and can be used directly as a library. However, it can be installed with the PIP installation:

    pip install memory_layout

Once installed, the tool can be executed as `mld`. For example:

    mld elite-bbc.mld


## Usage

The Memory Layout Diagram tool can be used with the domain specific language, as defined below. The tool can be invoked as:

    python -m memory_layout [<options>] <filename>

or:

    mld [<options>] <filename>

which will generate with the default renderer format (`svg`) for the file, with the `.mld` suffix replaced by `.svg`.

Other renderer formats can be be specified with the `--format` option, eg `--format dot`.

If no output filename is given with `--output`, an output prefix can be specified with `--output-prefix`, which will have the default filename suffix applied to it. If no prefix is supplied, the `.mld` suffix will be replaced with the default filename suffix.

## Renderers (output formats)

Two renderers are currently defined. Initially the memory layout was produced using Graphviz `dot`. This does not allow the layout to be stacked close together, so is not ideal. So an `svg` renderer can be used - this is the preferred and default renderer. Other renderers may be created in the future.

The renderers will have its own limitations, although they will try to be as faithful to the request as possible.


## Terms and concepts

There are a number of terms used within the memory layout, which it helps to understand:

* `memory region`: A memory region is a block of continuous address space. It is usually delimited by lines which divide it from other memory regions.
* `memory layout`: The memory layout is the ordered collection of the memory regions. Internally this is called a sequence. The sequence is always layed out with the lowest address at the bottom, and the highest address at the top.
* `discontinuity`: A discontinuity is a region which is not explicitly defined by the memory sequence. Discontinuities usually indicate regions of memory which are not allocated, or which are grown into as the systems is used.
* `labels`: Each memory region may have 0 or more labels associated with it. These are text which is placed in relation to the memory region.
* `outline`: Each memory region is surrounded by a border, called the 'outline'. The outline may have edges that are not solid or styled differently.
* `unit size` / `unit height`: To convert from memory addresses to presentational blocks, a 'unit size' and 'unit height' are defined. This controls how big a block of memory will appear in the output. All blocks are scaled based on this size.
* `minimum height` / `maximum height`: Usually the regions describe will be much larger than the unit size, but they may also be much smaller. Two limits restrict the size of the regions so that the diagram does not become excessively tall, or produce regions that are too short for text.
* `region width`: The memory regions are always presented with a fixed width, and if there is text alongside the memory sequence, this will also take up space equivalent to the memory width.
* `junctions`: Between memory regions there are dividing lines. These lines are called 'junctions', and may be styled differently.
* `label position`: Labels are positioned relative to the memory region, and may be internal to the region, external to the region, or on the junction boundary. Label positions are described by a string of characters indicating the location.
* `automatic elements`: Some of the elements can be generated automatically, such as address labels or discontinuities.
* `address format`: Different systems use different formats for their addresses, and so a number of different formatters are useable to generate addresses automatically.
* `output format`: Different output formats can be used. At present only `dot` and `svg` are defined.
* Distances are always measured in inches, as these are a common measure for presentation.


### Labels

Label positions are described in terms of the x and y position relative to the memory region, as a tuple. In the DSL these are given as a two comma-separated strings, but the DSL also has shortcuts for these, to make it easier to use in the most common cases.

The x position is prefixed by `i` for positions internal to the memory region, and `e` for positions external to the memory region. For the external positions, an invisible region is placed to the side of the memory region, which can have labels placed within it.

| X position  | Meaning                                                             |
|-------------|---------------------------------------------------------------------|
|     `il`    | Inside the memory region, left aligned                              |
|     `ic`    | Inside the memory region, centred                                   |
|     `ir`    | Inside the memory region, right aligned                             |
|     `el`    | To the left of the memory region, right aligned against its edge    |
|     `elm`   | To the left of the memory region, centred                           |
|     `elf`   | To the left of the memory region, left aligned away from the edge   |
|     `er`    | To the right of the memory region, left aligned against its edge    |
|     `erm`   | To the right of the memory region, centred                          |
|     `erf`   | To the right of the memory region, right aligned away from the edge |


| Y position  | Meaning                                                             |
|-------------|---------------------------------------------------------------------|
|     `it`    | Inside the memory region, aligned to the top                        |
|     `ic`    | Inside the memory region, centred                                   |
|     `ib`    | Inside the memory region, aligned to the bottom                     |
|     `jt`    | Centred on the junction at the top of the memory region             |
|     `jb`    | Centred on the junction at the bottom of the memory region          |


Label text can have newlines (`\n`) present to separate lines.


### Address labels

The automatic generation of address labels can place addresses at the side of the memory region. This is commonly used in the memory layout diagrams to give an indication of where the addresses live. Sometimes it is necessary to omit addresss from part of the memory layout, as the actual address isn't defined, or isn't fixed, so this is allowed too.

Address labels can be placed beside the start of the region (at the low position), at the end of the region (at the high position) and may include the side of the region. The end of the memory region can also be presented as either the final address, or the address of the next byte after the region.

The following address formats are defined:

| Name          | Class                     | Example       |
| `acorn`       | `ValueFormatterAcorn`     | `&3800000`    |
| `commodore`   | `ValueFormatterCommodore` | `$f000`       |
| `c`           | `ValueFormatterC`         | `0x540000`    |
| `si`          | `ValueFormatterSI`        | `2 MiB`       |
| `si2`         | `ValueFormatterSI2`       | `3.75 GiB`    |


### Junction boundaries

By default each region is a bordered rectangle. Discontinuities change the outline of the region, but regular memory regions can also change the high and low junctions boundaries. These are described as different junction types:

* `solid`: A solid unbroken line.
* `dotted`: A dotted line.
* `dashed`: A dashed line (longer drawn sections).
* `double`: A double solid line.
* `ticks`: Marker ticks at the edges only, not continuing across the boundary.


### Discontinuity styles

Discontinuities may have different styles of presentation. These are described by discontinuity styles:

* `zig-zag`: a zig-zag line at the edges (this is the default).
* `cut-out`: a wavy line indicating a section has been cut from the diagram (often used on graph axes).
* `dotted`: a dotted line at the edges.
* `dashed`: a dashed line at the edges.


## DSL

The domain specific language uses a simplified form of YAML as its basis for describing the layout.
The YAML document consists of a mapping with three fields - 'defaults', 'layout' and 'automatic'.

Types of data:

* Distances are by default measured in inches, as these are commonly used for documents. They may be suffixed by `pt` to measure in points (1/72 of an inch).
* Colours may use the standard CSS colour names, or `#RGB` or `#RRGGBB` forms.
* Positions may use a comma separated canonical position as described above (eg `il,it`), or the following shortcuts:

| Shortcut  | Canonical form | Meaning |
|-----------|---------------|---------------|
| `c`       | `ic,ic`       | Centred in both axes |
| `t`       | `ic,it`       | Top centre |
| `b`       | `ic,ib`       | Bottom centre |
| `l`       | `il,ic`       | Left side, vertically centred |
| `r`       | `ir,ic`       | Right side, vertically centred |
| `tl`      | `il,it`       | Top left |
| `tr`      | `ir,it`       | Top right |
| `bl`      | `il,ib`       | Bottom left |
| `br`      | `ir,ib`       | Bottom right |


### Defaults

The `defaults` block has a number of fields which set the defaults for the output, and the memory regions within it. The fields are:

* `unit_size`: The default size of regions, and the size by which all regions will be scaled.
* `unit_height`: The height of one `unit_size`, as a distance.
* `min_height`: The smallest region size, as a distance. Any regions smaller than this will be given this height.
* `max_height`: The largest region size, as a distance. Any regions larger than this will be given this height.
* `discontinuity_height`: The maximum size of a discontinuity region, as a distance. Any discontinuity larger than this will be given this height.
* `region_width`: The width of all the regions (and the external text regions), as a distance.
* `background`: The background colour of the document.
* `fill`: The default fill colour of memory regions.
* `outline`: The default outline colour of memory regions.
* `outline_width`: The default outline width for the memory regions, as a distance.
* `address_format`: The name of the formatter to use for automatic addresses.
* `size_format`: The name of the formatter to use for automatic sizes.
* `position`: The default position of labels which have no position specified
* `colour`: The default colour of text.


### Layout

The `layout` block describes the memory regions. It consists of a mapping which is keyed by the address of each memory region. The address of the memory region will be given in either decimal or C-style hexadecimal (ie prefixed with `0x`).

Each value of the layout may be a single string, to place that label at the default position, for a region with the default size. Alternatively the value can be a mapping with the following keys:

* `size`: The size of this region in bytes. If not specified, the `unit_size` will be used.
* `label`: A single label, which will be placed at the default position. The value takes the same form as the keys in the `labels`.
* `labels`: A mapping of labels, keyed by the label position, with a value that may be either a string to just provide a label with the default parameters, or a mapping of:
    * `position`: Overrides the position given in the key.
    * `label`: The text of the label.
    * `colour`: The colour of the label text.
* `discontinuity`: 'true' if this region is a discontinuity.
* `fill`: Colour to fill the region with.
* `outline`: Colour of the border outline.
* `outline_width`: Width of the border outline.
* `junction_low`: Type of junction boundary for the low address.
* `junction_high`: Type of junction boundary for the high address.


### Automatic generation

To simplify the layout definition, common features may be automatically generated. Two features are able to be automatically generated at present - address labels and discontinuities.

Features for automatic generation are defined in the section `automatic`, which contains keys for each of the generation features.

* `discontinuities`: Defines whether discontinuities - gaps between the end of one memory region and the next memory region - should be filled in. The value of the field may be `true` to enable the discontinuities, or may contain a mapping to describe how the discontinuities are filled in:
    * `fill`: The colour that the discontinuity will be filled with.
    * `outline`: Colour of the border outline.
    * `style`: The style of discontinuity, which defaults to `zig-zag`.
    * `enable`: May be set to `false` to disable the discontinuity filling.
* `address`: Defines the automatic creation of address labels. The value of the field may be `true` to enable the address labels at the start of the regions, or may contain a mapping to describe how the address labels are generated.
    * `start`: `true` to enable labels for the start address of the region.
    * `end`: `true` to enable labels for the end address of the region.
    * `size`: `true` to include the size of the region.
    * `side`: `left` or `right` to place the address labels on each side.
    * `end_exclusive`: `true` to present the end address as the next address after the region, `false` to use the last byte in the region.
    * `final_end`: `true` to include the last end address, even if `end` is disabled.
    * `omit`: either a single address which will be omitted from the labels, or a list of addresses to omit.


