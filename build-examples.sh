#!/bin/bash
##
# Build all our examples

set -e

datasets=(elite-bbc bbc bbcws riscos)
formats=(dot svg)

if [[ "$1" == '--all' ]] ; then
    datasets+=(discontinuities labels)
fi

for dataset in "${datasets[@]}" ; do
    for format in "${formats[@]}" ; do
        ext=$format
        echo "Generating dataset $dataset as $format"
        prefix="memory-${dataset}-${format}"
        python examples.py --format "$format" --output-prefix "$prefix" "${dataset}"
        if [[ "$format" == 'dot' ]] ; then
            # Use the output to create some actual output diagrams
            dot "$prefix.dot" -Tsvg -o "$prefix.svg"
            dot "$prefix.dot" -Tpng -o "$prefix.png"
        fi
    done
done
