#!/usr/bin/env python
"""
The SimpleYAML class is intended to allow a subset of the YAML
standard to be processed as a configuration file, without having
to install the large PyYAML module.

The idea is that the whole module, or just the class, can be
dropped into a project where YAML is required, without any other
dependencies. It is expected to function on Python 2.7 to 3.7.

Whilst it's intended to be used only for a small management,
test and setup scripts which need to be able to perform operations
without affecting the environment in which they are used.

Supported features of YAML:

- Lists (must be indented from keys)
- Mappings
- Comments
- Simple mapping keys (no quoting; no compound keys)
- Single line quoted strings (no wrapping over lines)
- Escapes in double quoted strings
- Multi-line value strings (following a bare key name; no block notation)
- Integers (decimal, binary, octal, hexadecimal, sexagesimal; with _ separators)
- Floats (decimal, sexagesimal, infinity, NaN; with _ separators)
- Nulls
- Booleans (only 'true' and 'false' supported)
- Single document only (terminates at a subsequent document introducer)

Not supported (non-inclusive list):

- Non-string keys
- Type tags
- Global tags
- Directives
- Flow style (eg inline JSON)
- Anchors and aliases ('&' and '*')
- Block strings

The library tries to match common YAML usage, and tries to take
YAML 1.2 format where possible. In particular this means that
YAML 1.1 booleans are not recognised (eg 'yes', 'off'). That
specific case can be supported by subclassing SimpleYAML and
overriding the `boolean_values` property.

"""

import re


class YAMLError(Exception):

    def __init__(self, message, lineno, *args):
        super(YAMLError, self).__init__(message, *args)
        self.lineno = lineno


class SimpleYAMLState(object):
    lineno = -1
    root = None
    indent_level = None
    current_level = None
    current = None
    last = None
    version = None


class SimpleYAML(object):
    # Special introducer characters: https://yaml.org/spec/1.1/#c-indicator
    directive_re = re.compile(r"^%([a-zA-Z0-9]+)(.*)$")
    key_value_re = re.compile(r"^([^\-?:,.[\]{}#&*!|>'\"%@`\s](?:[^,[\]{}:#\t]|[^,[\]{}:#\t]#|:[^,[\]{}:#\t])*?)(?!< )"
                              r" *:(?: +(.*))?$")
    keydq_value_re = re.compile(r'^"(.*)" *:(?: +(.*))?$')
    keysq_value_re = re.compile(r"^'(.*)' *:(?: +(.*))?$")

    value_dqstr_re = re.compile(r'^"(.*)"(\s*#.*)?$')
    value_sqstr_re = re.compile(r"^'(.*)'(\s*#.*)?$")
    value_float_re = re.compile(r'^[-+]?([0-9][0-9_]*\.[0-9]*|\.[0-9]+)([eE][-+][0-9]+)?$')
    value_base60_re = re.compile(r'^[-+]?[0-9][0-9_]*(:[0-5]?[0-9])+(\.[0-9_]*)?$')
    value_inf_re = re.compile(r'^[-+]?\.(inf|Inf|INF)$')
    value_nan_re = re.compile(r'^\.(nan|NaN|NAN)$')

    escape_split_re = re.compile(r'\\(?!\\)')
    escape_re = re.compile(r'\\(.)')
    escapes = {  # See: https://yaml.org/spec/1.1/#id872840
            '0': '\0',
            'a': '\a',
            'b': '\b',
            't': '\t', '\t': '\t',
            'n': '\n', 'N': '\x85',
            'v': '\v', 'f': '\f',
            'r': '\r',
            'e': '\x1e',
            ' ': ' ', '_': '\xa0',
            'L': u'\u2028', 'P': u'\u2029',
        }
    boolean_values = {  # Limited subset (like 1.2)
            'true': True,
            'false': False,
        }
    null_values = ('~', 'null', 'Null', 'NULL')
    try:
        unichr = unichr  # pylint: disable=undefined-variable
    except Exception:  # pylint: disable=broad-except
        unichr = chr

    def __init__(self, debug=False):
        self.debug = debug

    @staticmethod
    def warning(message):
        print("YAML Warnings: %s" % (message,))

    @staticmethod
    def is_hex(s):
        try:
            int(s, 16)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_bin(s):
        try:
            int(s, 2)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_oct(s):
        try:
            int(s, 8)
            return True
        except ValueError:
            return False

    def decode_value(self, s):
        # String types
        match = self.value_sqstr_re.search(s)
        if match:
            value = match.group(1)
            value = value.replace("''", "'")
            return value
        match = self.value_dqstr_re.search(s)
        if match:
            value = match.group(1)
            parts = self.escape_split_re.split(value)
            value = parts[0]
            for part in parts[1:]:
                if part and part[0] in self.escapes:
                    part = self.escapes[part[0]] + part[1:]
                elif part[0] == 'x':
                    c = part[1:3]
                    part = chr(int(c, 16)) + part[3:]
                elif part[0] == 'u':
                    c = part[1:5]
                    part = self.unichr(int(c, 16)) + part[5:]
                elif part[0] == 'U':
                    c = part[1:9]
                    part = self.unichr(int(c, 16)) + part[9:]
                value += part
            return value

        # Once we've passed the quoted strings, we know that the
        # comments after the value are strippable, and that comments
        # must be preceeded by one space at least
        if ' #' in s:
            s = s[:s.index(' #')].rstrip()

        # Booleans
        if s in self.boolean_values:
            return self.boolean_values[s]

        # Nulls
        if s in self.null_values:
            return None

        # Integer types
        if s[0] == '0':
            snum = s.replace('_', '')
            if s[1] == 'x' and self.is_hex(snum[2:]):
                return int(snum[2:], 16)
            if s[1] == 'b' and self.is_bin(snum[2:]):
                return int(snum[2:], 2)
            if self.is_oct(snum[1:]):
                return int(snum[1:], 8)

        if s.isdigit() or (s[0] in ('-', '+') and s[1:].isdigit()):
            return int(s)
        if '_' in s:
            snum = s.replace('_', '')
            if snum.isdigit() or (snum[0] in ('-', '+') and snum[1:].isdigit()):
                return int(snum)

        match = self.value_base60_re.search(s)
        if match:
            s = s.replace('_', '')
            sign = 1
            if s[0] == '-':
                sign = -1
                s = s[1:]
            elif s[0] == '+':
                s = s[1:]

            parts = s.split(':')
            value = 0
            for part in parts:
                value = value * 60
                part = float(part) if '.' in part else int(part)
                value += part
            if sign == -1:
                value = -value

            return value

        # Floating point types
        match = self.value_float_re.search(s)
        if match:
            s = s.replace('_', '')
            return float(s)

        match = self.value_inf_re.search(s)
        if match:
            if s[0] == '-':
                return -float('inf')
            else:
                return float('inf')

        match = self.value_nan_re.search(s)
        if match:
            return float('nan')

        return s

    def parse_directive(self, state, line):
        """
        Process a directive.

        @param line:    Directive line being processed
        @return:        True if processed; False if not recognised
        """
        match = self.directive_re.search(line)
        if not match:
            return False

        directive = match.group(1)
        args = match.group(2).strip()
        if self.debug:
            print("Directive '%s' ('%s') encountered" % (directive, args))
        if directive == 'YAML':
            if args:
                try:
                    state.version = float(args)
                except ValueError:
                    raise YAMLError("YAML version '%s' not parseable" % (state.version,), state.lineno)
                if state.version >= 2:
                    raise YAMLError("YAML version %s not supported" % (state.version,), state.lineno)
                if state.version >= 1.2:
                    self.warning("YAML version %s probably not supported" % (state.version,))
            else:
                state.version = None
        else:
            self.warning("Directive '%s' not supported" % (directive,))
        return True

    def load(self, fh):
        state = SimpleYAMLState()
        state.lineno = -1
        state.root = None
        state.indent_level = [0]
        state.current_level = [state.root]
        state.current = None
        state.last = None
        state.version = None

        # pylint: disable=too-many-nested-blocks
        try:
            for line in fh:
                state.lineno += 1
                line = line.rstrip()
                if line == '':
                    continue
                if self.debug:
                    print("---- Line: '%s'" % (line,))

                if line == '---':
                    # Document introducer.
                    if state.root is not None:
                        # We're already in a document, so this means we are leaving
                        # this document
                        break
                    continue

                no_indent = line.lstrip()
                indent = len(line) - len(no_indent)
                line = no_indent
                if line[0] == '#':
                    if self.debug:
                        print("Comment ignored")
                    continue

                if indent == 0 and line[0] == '%':
                    # Directives, which open with a %
                    if self.parse_directive(state, line):
                        continue

                if self.debug:
                    print("Indent levels: %r" % (state.indent_level,))
                    print("This indent: %s" % (indent,))

                while state.indent_level[-1] > indent:
                    state.indent_level.pop()
                    state.current = state.current_level.pop()
                    state.last = None
                    if self.debug:
                        print("Up one level")

                while line[0] == '-' and (len(line) == 1 or line[1] == ' '):
                    # List item introduced
                    list_indent = indent

                    no_indent = line[1:].lstrip()
                    indent += len(line) - len(no_indent)
                    line = no_indent

                    if state.root is None:
                        state.root = []
                        state.current = state.root
                        state.indent_level = [list_indent]
                    else:
                        if list_indent == state.indent_level[-1]:
                            # Same level, so we're just appending.
                            if self.debug:
                                print("List at same level")
                        else:
                            # Indented, so we're adding to the current item.
                            if self.debug:
                                print("List indented")
                            if state.last:
                                state.current[state.last] = []
                                state.current_level.append(state.current)
                                state.current = state.current[state.last]
                                state.last = None
                            else:
                                state.current.append([])
                                state.current_level.append(state.current)
                                state.current = state.current[-1]
                            state.indent_level.append(list_indent)

                    if self.debug:
                        print("List introducer: now at level %s" % (len(state.indent_level),))

                match = self.keydq_value_re.search(line)
                if not match:
                    match = self.keysq_value_re.search(line)
                if not match:
                    match = self.key_value_re.search(line)
                if match:
                    key = match.group(1)
                    value = match.group(2) or ''
                    if value and value[0] == '#':
                        # There isn't really a value there; it's a comment.
                        value = ''
                    if state.root is None:
                        state.root = {}
                        state.current = state.root
                    else:
                        if indent == state.indent_level[-1]:
                            # Same level, so we're just appending.
                            if self.debug:
                                print("Key at same level")
                        else:
                            # Indented, so we're adding to the current item.
                            if self.debug:
                                print("Key indented")
                            if state.last:
                                state.current[state.last] = {}
                                state.current_level.append(state.current)
                                state.current = state.current[state.last]
                            else:
                                state.current.append({})
                                state.current_level.append(state.current)
                                state.current = state.current[-1]
                            state.indent_level.append(indent)

                    if value == '':
                        state.current[key] = None
                        state.last = key
                    else:
                        state.current[key] = self.decode_value(value)
                        state.last = None

                else:
                    value = self.decode_value(line)
                    if state.root is None:
                        # Single root value assignment. Weird.
                        state.root = value
                    else:
                        if state.last:
                            if state.current[state.last] is None:
                                state.current[state.last] = value
                            else:
                                state.current[state.last] += ' ' + value
                        else:
                            if isinstance(state.current, list):
                                state.current.append(value)
                            else:
                                raise YAMLError("Unparseable line '%s'" % (line,), state.lineno)

                if self.debug:
                    print("last = %r" % (state.last,))
                    print("current = %r" % (state.current,))
        except YAMLError:
            raise

        except Exception as ex:
            raise YAMLError("%s: %s (failed at line %s)" % (ex.__class__.__name__,
                                                            ex,
                                                            state.lineno,),
                            state.lineno)

        return state.root


def load(fh, debug=False):
    yaml = SimpleYAML(debug=debug)
    return yaml.load(fh)
safe_load = load
