# coding: utf8

import re, urllib
from collections import deque

# --------------------------------------------------------------------------------------------------------------

class RecPattern(object):
        """Recursive pattern. To implement, write RecPattern(re.compile(x)) for the regex in the span rule."""
        def __init__(self, regex):
                self.regex = regex
        def sub(self, func, text):
                n = 1
                while n:
                        text, n = self.regex.subn(func, text)
                return text

PROTOCOL_PATTERN = r'(?:http://|https://|ftp://|mailto:|news:|irc:|gopher:|mms://|rtsp://)'
_url = r'[^\s<>()"]*?(?:\([^\s<>()"]*?\)[^\s<>()"]*?)*)((?:[\s<>".!?,]||&quot;)*(?:[\s<>()"]|$))'
URL_PATTERN = ('(' + PROTOCOL_PATTERN + _url)
SUBURL_PATTERN = ('(' + _url)
PROTOCOL_REGEX = re.compile(PROTOCOL_PATTERN)
URL_REGEX = re.compile(URL_PATTERN)

def _markdown_link(m, span, **args):
        text, link, paren = m.groups()
        if paren == ')' and not URL_REGEX.match(text):
                return ('<a href="%s" rel="nofollow" title="%s">%s</a>' % (link, link, span(text, **args)))
        return m.group(0)

def _image(m, span, **args):
        pre_newline, pos, filename, title, post_newline = m.groups()
        out = []
        pos = {'<': 'left', '&lt;': 'left', '>': 'right', '&gt;': 'right'}.get(pos, '')
        if pos: pre_newline = post_newline = False
        # Only output preceding line break if the image is at the start of the line and not floated
        if pre_newline: out.append('<br />')
        # If it's floated or titled, put it into a div.
        if title or pos:
                out.append('<div style="font-size: 75%')
                if pos: out.append('; float: %s; clear: %s; text-align: %s' % (pos, pos, pos))
                out.append('">')
        # could be better
        out.append('<img src="%s" alt="" />' % (urllib.quote(filename, safe='/=:;@#?')))
        if title: out.extend(('<br />', span(title, **args)))
        if title or pos: out.append('</div>')
        # Only output trailing line break if the image is at the end of the line and not floated
        if post_newline: out.append('<br />')
        return ''.join(out)

# --------------------------------------------------------------------------------------------------------------

SPAN_RULES = [

('escape',
        re.compile(ur"\\([\\/*_‾^`\[\]\(\)#+-])"),
        lambda m, span, **args: m.group(1)
),

('code',
        re.compile(r"""
        (`+) (                          # at least one backtick / begin group
                (?:                     # match...
                        (?!\1).         # not the opening marker
                )+                      # at least once
        ) \1                            # end group
        """, re.VERBOSE),
        lambda m, span, **args: '<code>' + m.group(2) + '</code>'
),

('spoiler',
        RecPattern(re.compile(r"""
                /\* (                           # opening marker / begin group
                        (?:                     # start a sub-group
                                (?!/\*|\*/)     # anything that is NOT the opening or closing marker
                                .               # consume one character
                        )+                      # ... match that at least once
                ) \*/                           # end group / closing marker
        """, re.DOTALL | re.VERBOSE)),
        lambda m, span, **args: '<span class="spoiler">' + span(m.group(1), **args) + '</span>'
),

('markdown link',
        re.compile(r"\[ \s* ((?:\S) [^\]]+?) \s* \] \s* \(" + URL_PATTERN, re.VERBOSE),
        _markdown_link
),

('auto link', URL_REGEX,
        lambda m, span, **args: '<a href="%s" rel="nofollow">%s</a>%s' % (m.group(1), m.group(1), m.group(2))
),



('strong', # see em for details
        re.compile(r"\*\*((?=\S)[^*]*[^\s*])\*\*"),
        lambda m, span, **args: '<strong>' + span(m.group(1), **args) + '</strong>'
),

('em',
# match a *, followed by a non-whitespace character which is not a *, followed by any number of non-* characters
# then terminating in another *
        re.compile(r"""
                \* (            # start with an asterisk; begin group(1)
                        (?=\S)  # make sure the first character after the opening * is not whitespace
                        [^*]*   # any number of non-asterisks
                        [^\s*]  # at least one character before the closing *, which is also not whitespace
                ) \*            # and end with an asterisk
        """, re.VERBOSE),
        lambda m, span, **args: '<em>' + span(m.group(1), **args) + '</em>'
),

('del',
        re.compile(r"""
                --\( (                          # opening marker / begin group
                        (?:                     # start a sub-group
                                (?!--\(|\)--)   # anything that is NOT the opening or closing marker
                                .               # consume one character
                        )+                      # ... match that at least once
                ) \)--                          # end group / closing marker
        """, re.VERBOSE),
        lambda m, span, **args: '<del>' + span(m.group(1), **args) + '</del>'
),

('overline',
        re.compile(ur"(\xaf\xaf+)(.+?)\1"),
        lambda m, span, **args: '<span style="text-decoration: overline">' + span(m.group(2), **args) + '</span>'
),

('underline', # oh god, this one hurts my head
        re.compile(r"""
                \b (?:                  # start on word boundary
                _ (                     # first case: opening marker / begin group
                        (?!_)           # not starting with an underscore
                        \S*             # anything but whitespace
                        [^\s_]          # and not ending with an underscore
                ) _                     # closing marker / end group
                |                       # ...OR...
                (__+) (                 # second case: opening marker (and remember it); begin group
                        (?!\s)          # first char is not whitespace
                        (?:             # start a subgroup...
                                (?!\2)  # ... for anything which isn't as many underscores as we just matched
                                .       # consume one character
                        )*?             # match that pattern many times
                        \S              # must have at least one non-whitespace char
                        (?<!__)         # hopefully that wasn't two underscores we just matched.
                ) \2                    # end group, closing marker same as opening
                ) \b                    # end on a word boundary
        """, re.VERBOSE),
        lambda m, span, **args: '<span style="text-decoration: underline">'
                                + span((m.group(1) or m.group(3)).replace('_', ' '), **args) + '</span>'
),

# these two use the same general regex as spoiler, but with different marker characters
('sub',
        RecPattern(re.compile(r"_\(((?:(?!_\(|\)).)+)\)")),
        lambda m, span, **args: '<sub>' + span(m.group(1), **args) + '</sub>'
),

('sup',
        RecPattern(re.compile(r"\^\(((?:(?!\^\(|\)).)+)\)")),
        lambda m, span, **args: '<sup>' + span(m.group(1), **args) + '</sup>'
),

# \0 = already-substituted blocks of text; args.update weirdness => self-recursive.
#('sup2',
#       re.compile(r"\^([\w\0^]+)(?![\w\0^])"),
#       lambda m, span, **args: '<sup>' + span(args.update(skip=None) or m.group(1), **args) + '</sup>'
#),

# make it look nice
('mdash', re.compile(r'---'), lambda m, span, **args: '&mdash;'),
('ndash', re.compile(r'--'), lambda m, span, **args: '&ndash;'),

] # END SPAN_RULES

# --------------------------------------------------------------------------------------------------------------
# Extra spans which can be added

RULE_IMAGE = ('image',
        re.compile(r"""
                ((?:\r?)\n)? \[ \s* ( | \< | \> | &gt; | &lt; ) img \s* \[
                \s* ( (?:\S) [^\]\|]+? ) \s* (?: \| \s* ( (?=\S) [^\]]+? ) ) ? \s*
                \] \s* \] ((?:\r?)\n)?
        """, re.VERBOSE | re.MULTILINE),
        _image, 'markdown link',
)

RULE_REL_LINK = ('relative markdown link',
        re.compile(r"\[ \s* ((?:\S) [^\]]+?) \s* \] \s* \(" + SUBURL_PATTERN, re.VERBOSE),
        _markdown_link, 'markdown link',
)

# --------------------------------------------------------------------------------------------------------------

def _hide(data, hidden):
        hidden.append(data)
        return '\0%d\0' % (len(hidden) - 1)

def _unhide(text, hidden):
        # naive, but works
        for n, s in reversed([n for n in enumerate(hidden)]):
                text = text.replace('\0%d\0' % n, s)
        return text

def _span(text, hidden, rules, skip):
        if skip:
                rules = (r for r in rules if r is not skip)
        for rule in rules:
                name, regex, func = rule
                text = regex.sub(lambda m: _hide(func(
                        m, _span, hidden=hidden, rules=rules, skip=rule
                ), hidden), text)
        return text

# --------------------------------------------------------------------------------------------------------------

CHUNK_TEXT = 0 # formatted text, which is run through _span
CHUNK_STEXT = 1 # unformatted text, not run through _span but newlines are still converted
CHUNK_HTML = 2 # html
CHUNK_IGNORE = 3 # not outputted
CHUNK_HLCODE = 4 # code, same as STEXT if the first line starts with -*-

# for re_first, None => anything not matching any previous block's re_first
# for re_next, None => use re_first
# for re_cont, None => use re_next
BLOCK_RULES = [
        # begin, subbegin, subend, end, re_first, re_next, re_cont, strip, chunk
        ('', None, None, '', r'(?:    |\t)(?=\#!|.*-\*.+\*-)', r'    |\t', None, True, CHUNK_HLCODE),
        ('<pre><code>', None, None, '</code></pre>', r'    |\t', None, None, True, CHUNK_STEXT),
        ('<p class="aa">', None, None, '</p>', u'\u3000', None, None, True, CHUNK_STEXT),
        ('<blockquote class="unkfunc"><p>', None, None, '</p></blockquote>', '&gt;\s*', None, None, False, CHUNK_TEXT),
        ('<ul>', '<li>', '</li>', '</ul>', r'[*#-]\s+', None, r'  |\t', True, CHUNK_TEXT),
        ('<ol>', '<li>', '</li>', '</ol>', r'1[.)]\s+', r'\d+[.)]\s+', r'  |\t', True, CHUNK_TEXT),
        ('', '<hr />', '', '', r'----+$', None, r'(?!.).', True, CHUNK_IGNORE), # hax
        ('<p>', None, None, '</p>', None, None, None, False, CHUNK_TEXT), # MUST BE LAST
]

def _iter_blocks(text):
        # Compile the regexes, and add a <p> rule.
        rules = []
        regexes = set()
        for (begin, subbegin, subend, end, re_first, re_next, re_cont, strip, chunk) in BLOCK_RULES:
                if re_first:
                        if '|' in re_first:
                                re_first = '(?:' + re_first + ')'
                        first = re.compile('^' + re_first)
                        regexes.add(re_first) # keep track of all the starting regexes
                else:
                        # None => anything not matching preceding rules (but at least one character)
                        first = re.compile('^(?!' + '|'.join(regexes) + ').')
                next = re_next and re.compile('^(?:' + re_next + ')') or first
                cont = re_cont and re.compile('^(?:' + re_cont + ')') or next
                rules.append((begin, subbegin, subend, end, first, next, cont, strip, chunk))

        lines = deque(line.rstrip() for line in text.splitlines())
        while lines:
                line = lines[0]
                if not line:
                        lines.popleft()
                        continue

                # Look for a block definition that matches the first line.
                for (begin, subbegin, subend, end, first, next, cont, strip, chunk) in rules:
                        if first.match(line):
                                break
                else:
                        raise Exception('mismatch')

                yield (CHUNK_HTML, begin)

                # find text (yes, the first line is matched twice)
                while lines:
                        line = lines[0]
                        if strip:
                                line, matched = next.subn('', line, 1)
                        else:
                                matched = next.match(line)
                        if not matched:
                                break

                        if subbegin:
                                yield (CHUNK_HTML, subbegin)

                        yield (chunk, line)
                        lines.popleft()

                        # find continuations to the current line
                        while lines:
                                line = lines[0]
                                if strip:
                                        line, matched = cont.subn('', line, 1)
                                else:
                                        matched = cont.match(line)
                                if not matched:
                                        break

                                yield (chunk, line)
                                lines.popleft()

                        if subend:
                                yield (CHUNK_HTML, subend)

                yield (CHUNK_HTML, end)
        yield (None, None) # sentinel

# --------------------------------------------------------------------------------------------------------------

def _tag_check(html):
        depth = {
                'strong': 0,
                'em': 0,
                'a': 0,
                'code': 0,
                'ins': 0,
                'del': 0,
        }
        out = []
        # tag regex from abbreviate_html
        tagstack = []
        for m in re.finditer(r'([^<]+)|<(/?)(\w+).*?(/?)>', html, re.DOTALL):
                text, closing, tag, implicit = m.groups()
                if text:
                        out.append(text)
                elif closing:
                        try:
                                ts = tagstack.pop()
                                if ts != tag:
                                        raise Exception("unbalanced tag %s != %s" % (ts, tag))
                        except IndexError: # pop from empty list
                                #raise Exception("unexpected closing tag")
                                continue
                        try:
                                depth[tag] -= 1
                        except:
                                pass
                        if depth.get(tag, 0) == 0:
                                out.append(m.group(0))
                elif implicit:
                        if depth.get(tag, 0) == 0:
                                out.append(m.group(0))
                else: # opening tag
                        try:
                                depth[tag] += 1
                        except:
                                pass
                        if depth.get(tag, 1) == 1:
                                out.append(m.group(0))
                        tagstack.append(tag)
        return ''.join(out)


def _highlight_code(src):
        import pygments, pygments.formatters, pygments.lexers, pygments.util
        m = re.compile(r'''
                  -\* .*? \b(?:mode|filetype|ft): \s* ([^\s:;]+) .*? \*-
                | -\*-? \s* ([^\s:;]+?) \s* -?\*-
        ''', re.VERBOSE).search(src)
        if m:
                m = (m.group(1) or m.group(2) or '').lower()
                m = {
                        'lisp': 'cl',
                        'fioc': 'python',
                        '_fioc_': 'python',
                        '__fioc__': 'python',
                        '___fioc___': 'python',
                        '____fioc____': 'python',
                }.get(m, m)

        html = None
        try:
                if m:
                        lexer = pygments.lexers.get_lexer_by_name(m)
                else:
                        lexer = pygments.lexers.guess_lexer(src)
        except:
                html = None
        else:
                # UGH
                hsrc = (src.replace('&gt;', '>')
                        .replace('&lt;', '<')
                        .replace('&amp;', '&')
                        .replace('&gtgt;', '>>'))
                try:
                        html = pygments.highlight(hsrc, lexer,
                                pygments.formatters.HtmlFormatter
                                        (cssclass="syn")).rstrip()
                except:
                        html = None
        return html or ('<pre><code>' + src + '</code></pre>')



def format(text, *span_extra):
        out = []
        hidden = []
        chunks = []
        chunktype = None

        span_rules = SPAN_RULES[:]

        for rule in span_extra:
                before = (lambda name, func, regex, before=None: before)(*rule) # hax
                if before:
                        for n, r in enumerate(span_rules):
                                if r[0] == before:
                                        span_rules.insert(n, rule[:3])
                                        break
                        else:
                                raise Exception('%r not found in rule list' % before)
                else:
                        span_rules.append(rule)

        for cur, data in _iter_blocks(text):
                if cur == chunktype:
                        chunks.append(data)
                else:
                        if chunks:
                                if chunktype == CHUNK_TEXT:
                                        out.append(_span('\n'.join(chunks), hidden, span_rules, None))
                                elif chunktype == CHUNK_HLCODE:
                                        out.append(_highlight_code('\n'.join(chunks)))
                                elif chunktype == CHUNK_STEXT:
                                        out.append('\n'.join(chunks))
                                else: # CHUNK_HTML
                                        out.append(''.join(chunks))
                        chunks = [data]
                chunktype = cur

        return _tag_check(_unhide(''.join(out), hidden).replace('\n', '<br />'))
