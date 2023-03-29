#!/usr/bin/env python
"""
Packaging for the Memory Layout Diagrams.
"""

from distutils.core import setup
import setuptools  # noqa

from os import path
# io.open is needed for projects that support Python 2.7
# It ensures open() defaults to text mode with universal newlines,
# and accepts an argument to specify the text encoding
# Python 3 only projects can skip this import
from io import open

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup(
    name = 'memory_layout',
    packages = ['memory_layout', 'memory_layout.renderers'],
    version = '0.0.1',
    license='MIT',
    description = 'Generating diagrams to show memory map layouts from code or definition files',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    author = 'Charles Ferguson',
    author_email = 'gerph@gerph.org',
    url = 'https://github.com/gerph/memory-layout-diagram',
    keywords = ['diagram', 'generator', 'memory-map'],
    install_requires= [
        ],
    classifiers= [
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            "Operating System :: OS Independent"
        ],
    python_requires='>=2.7',
    entry_points="""
       [console_scripts]
       mld = memory_layout.__main__:main
""",
)
