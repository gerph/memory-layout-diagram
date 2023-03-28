"""
Memory Layout Diagram renderer implementations.
"""


class MLDRenderBase(object):
    # Overridable suggested filename suffix
    file_suffix = '.dat'

    def __init__(self, fh=None):
        if isinstance(fh, str):
            fh = open(fh, 'w')
        self.fh = fh or sys.stdout

    def __del__(self):
        self.fh.close()

    def write(self, content):
        self.fh.write(content)

    def render(self, memorymap):
        raise NotImplementedError("{}.render() is not implemented".format(self.__class__.__name__))
