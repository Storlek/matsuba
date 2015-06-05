from __future__ import print_function

import base64, cgi, crypt, codecs, os, random, re, sha, string
import struct, tempfile, time, unicodedata, urllib, urlparse
import htmlentitydefs
from collections import deque
from safewriter import SafeWriter

# --------------------------------------------------------------------------------------------------------------
# URL matching nastiness

PROTOCOL_PATTERN = r'(?:http://|https://|ftp://|mailto:|news:|irc:|gopher:|data:)'
_url = r'[^\s<>()"]*?(?:\([^\s<>()"]*?\)[^\s<>()"]*?)*)((?:[\s<>".!?,]||&quot;)*(?:[\s<>()"]|$)'
URL_PATTERN = ('(' + PROTOCOL_PATTERN + _url + ')')
SUBURL_PATTERN = ('(' + _url + ')')
PROTOCOL_REGEX = re.compile(PROTOCOL_PATTERN)
URL_REGEX = re.compile(URL_PATTERN)

# --------------------------------------------------------------------------------------------------------------
# some necessary formatting/output functions used by templates

def format_timestamp(unixtime, style='futaba', gmt=False):
        """Format a timestamp.
        Style can be any of futaba, 2ch, http, tiny, or a strftime format."""
        styles = {
                'futaba': '%y/%m/%d(%a)%H:%M', # image boards
                '2ch': '%Y-%m-%d %H:%M', # text boards
                'http': '%a, %d %b %Y %H:%M:%S GMT', # cookies
                'tiny-n': '%m/%d&nbsp;%H:%M', # subback on imageboards
                'date': '%B %d, %Y', # ban page
                'cats': '%y/%m/%d(Cat)%H:%M', # /cats/
                'rfc3339': '%Y-%m-%dT%H:%M:%SZ', # for atom dates
        }
        if style in styles: style = styles[style]
        timestamp = (gmt and time.gmtime or time.localtime)(float(unixtime))
        return time.strftime(style, timestamp)

def format_filesize(filesize):
        """Make a human-readable file size with the smallest practical unit."""
        # this will break when it hits the terabyte range (it divides one too many times)
        # -- but i don't care, since we won't be dealing with anything nearly that size.
        for unit in '%d b','%d kb','%.2f mb','%.2f gb':
                if filesize < 2048: break
                filesize /= 1024.0
        return unit % filesize

def make_plural(n, s, p=None, zero='0'):
        return '%s %s' % (n or zero, n == 1 and s or p or s + 's')

re_entity = re.compile(r'''\& (?:
        (?P<named> [0-9A-Za-z]+)
        | \#[Xx] (?P<hex> [0-9A-Fa-f]+)
        | \# (?P<dec> [0-9]+)
) (?:;|\s|$)''', re.VERBOSE)
def deamplicate(s):
        """Undo entity encodings (&amp; or &#123; style only)"""
        def rep(m):
                g = m.groupdict()
                #print(g)
                n = None
                if g['named']: n = htmlentitydefs.name2codepoint.get(g['named'])
                elif g['hex']: n = int(g['hex'], 16)
                elif g['dec']: n = int(g['dec'])
                return (unichr(n) if n else m.group(0))
        return re_entity.sub(rep, s)

# This makes all sorts of assumptions...
re_html_tag = re.compile(ur'\s*<.+?>\s*')
re_partial_entity = re.compile(ur'&[^;]*$')
def strip_html(s, maxlen=None):
        """Probably needs to be renamed or split or something..."""
        s = re_html_tag.sub(' ', s)
        # substitute xml entities
        s = deamplicate(s)
        s = s.strip()
        if maxlen > 0:
                s = s[:maxlen]
        return re_partial_entity.sub('', s)

# Algorithm adapted from Wakaba.
def abbreviate_html(html, max_lines=15, line_len=150):
        chars = total = lines = 0
        tagstack, abbrev, cut_word = [], None, None
        max_chars = max_lines * line_len
        for m in re.finditer(r'([^<]+)|<(/?)(\w+).*?(/?)>', html, re.DOTALL):
                text, closing, tag, implicit = m.groups()
                if text:
                        n = len(text)
                        chars += n
                        total += n
                        if total > max_chars:
                                total -= n
                                abbrev = m.start() - total + max_chars
                                for c in sorted(xrange(-10, 11), key=abs):
                                        if html[abbrev + c] in ' \t\r\n':
                                                # cutting off midsentence
                                                abbrev += c
                                                cut_word = ' [...]'
                                                break
                                else:
                                        # cutting off midword
                                        cut_word = '[...]'
                                break
                else:
                        if closing:
                                tagstack.pop()
                        elif not implicit:
                                tagstack.append(tag)
                        if (closing or implicit) and tag in ('p', 'blockquote', 'pre', 'li', 'ol', 'ul', 'br'):
                                lines += int(chars / line_len) + 1
                                if tag in ('p', 'blockquote'):
                                        lines += 1
                                chars = 0
                                if lines >= max_lines:
                                        abbrev = m.span()[not implicit]
                                        break
        if abbrev is not None:
                if re.match(r'(?:\s*</\w+>)*\s*$', html[abbrev:]):
                        return None
                abbrev = [html[:abbrev]]
                if cut_word is not None:
                        abbrev.append('<span class="abbrev">%s</span>' % cut_word)
                abbrev.extend('</%s>' % tag for tag in reversed(tagstack))
                return ''.join(abbrev)
        return None

# --------------------------------------------------------------------------------------------------------------
# utility functions

_salt_table = (
        '.............................................../0123456789ABCDEF'
        'GABCDEFGHIJKLMNOPQRSTUVWXYZabcdefabcdefghijklmnopqrstuvwxyz.....'
        '................................................................'
        '................................................................'
)

def get_tripcode(pw):
        """Wakaba/Futaba-compatible."""
        pw = pw.encode('sjis', 'xmlcharrefreplace')
        if 0: # compatible with Wakaba?
                pw = (pw
                        .replace('&', '&amp;')
                        .replace("'", '&#39;')
                        .replace(',', '&#44;')
                )
        if 1: # compatible with 0ch (apart from the weirder replacements)
                pw = (pw
                        .replace('"', '&quot;')
                        .replace('<', '&lt;')
                        .replace('>', '&gt;')
                )
        salt = (pw + 'H..')[1:3].translate(_salt_table)
        return crypt.crypt(pw, salt)[-10:]

def get_secure_hash(seed, secret):
        """Generate a hash value based on a given seed. This is used for
        secure tripcodes and password authentication."""
        if isinstance(seed, unicode):
                seed = seed.encode('utf8', 'ignore')
        return base64.b64encode(sha.new(seed + secret).digest(), './')[:-1]

def get_random_string(minlength, maxlength=None, charset=urllib.always_safe, randobj=random):
        if maxlength <= minlength:
                length = minlength
        else:
                length = random.randrange(minlength, maxlength)
        return ''.join(randobj.choice(charset) for n in xrange(length))

# urllib.quote doesn't properly handle unicode characters
def url_encode(s, safe='/'):
        return urllib.quote(s.encode('utf-8'), safe)

def cookie_encode(s, safe='/'):
        o = []
        safe += urllib.always_safe
        for c in s:
                if c in safe:                   o.append(c)
                elif ord(c) < 256:              o.append('%%%02X' % ord(c))
                elif ord(c) < 65536:            o.append('%%u%04X' % ord(c))
                else:                           o.append('%%U%08X' % ord(c)) # ?
        return ''.join(o)

def url_unidecode(s):
        return (urllib.unquote(s)
                .replace('%u', '\\u')
                .replace('%U', '\\U')
                .decode('unicode_escape', 'replace'))


def set_cookie(cookie, value, maxage, path='/'):
        """Set a cookie. Use None for value to clear (in which case maxage is irrelevant)
        maxage = seconds from now when the cookie should expire"""
        if value is None:
                maxage = 0
        print('Set-Cookie: %s=%s; path=%s; max-age=%s; expires=%s' % (
                cookie, cookie_encode(value or ''), path.rstrip('/') + '/', maxage,
                format_timestamp(time.time() + maxage, 'http', True)))

def http_redirect(page):
        """Point the browser elsewhere and exit."""
        # Try very hard to get a full URL. Lynx complains if it's relative.
        try:
                base = 'http://' + os.environ['SERVER_NAME']
        except:
                pass
        else:
                page = urlparse.urljoin(base, page.strip() or '/')
        print("""\
Status: 303 Go Grizzly or Go Home
Location: %(page)s
Content-Type: text/html

<html><head><title>303 See Other</title></head><body><h1>303 See Other</h1>
<p><a href="%(html)s">%(html)s</a></p></body></html>
""" % {'page': page, 'html': cgi.escape(page)})
        raise SystemExit

# http://boodebr.org/main/python/all-about-python-and-unicode
re_illegal_unicode = re.compile(
        ur'([\u0000-\u0008\u000b-\u000c\u000e-\u001f\ufffe-\uffff])'
        + ur'|([\ud800-\udbff][^\udc00-\udfff])'
        + ur'|([^\ud800-\udbff][\udc00-\udfff])'
        + ur'|([\ud800-\udbff]$)'
        + ur'|(^[\udc00-\udfff])'
)

def strip_illegal_unicode(s):
        """Strip off any illegal unicode characters, replacing them with '?'. If no legal characters are
        present, this returns an empty unicode string."""
        clean, count = re_illegal_unicode.subn(u'?', s)
        if count == len(clean):
                clean = u''
        return clean

def preserve_case(match, replace):
        """Return 'replace' with the letter case of 'match'."""
        if match.isupper():
                return replace.upper()
        elif match.islower():
                return replace.lower()
        elif match.lower() == match.upper():
                return replace
        elif len(replace) > len(match):
                match += match[-1] * (len(replace) - len(match))
        else:
                match = match[:len(replace)]
        out = []
        start = 0
        transform = type(replace)
        for pos, c in enumerate(match):
                if c.islower():
                        f = type(replace).lower
                elif c.isupper():
                        f = type(replace).upper
                else:
                        f = transform
                if transform is not f:
                        if pos:
                                out.append(transform(replace[start:pos]))
                        start = pos
                        transform = f
        out.append(transform(replace[start:]))
        return ''.join(out)

def roundrobin(*iterables):
        """From the Python documentation. http://docs.python.org/lib/deque-recipes.html"""
        pending = deque(iter(i) for i in iterables)
        while pending:
                task = pending.popleft()
                try:
                        yield task.next()
                except StopIteration:
                        continue
                pending.append(task)

def group(L, count):
        """Return an iterator whose next() method returns the next 'count' items from a list.
        (Doesn't work on all iterables, since it uses slices.)"""
        start = 0
        end = len(L)
        while start < end:
                yield L[start:start+count]
                start += count
        raise StopIteration

def coalesce(*args):
        """Return the first argument which is not None. If all arguments are None, return None."""
        for a in args:
                if a is not None: return a
        return None

# --------------------------------------------------------------------------------------------------------------
# context free grammar
# based on stuff from http://www.ruf.rice.edu/~pound/ and wakaba's context free grammar implementation

_cfg_token = re.compile(r'%(.)')
def cfg_expand(grammar, randobj=random, text='%*', descent=0):
        if descent > 20:
                return text # avoid infinite loops
        return _cfg_token.sub(lambda m: cfg_expand
                        (grammar, randobj,
                         randobj.choice(grammar.get(m.group(1), [m.group(1)])).strip(),
                         descent + 1), text)

def cfg_parse_file(f):
        grammar = {'*': ['']} # default rule -- *should* be redefined, but who knows.
        for line in f:
                # Split first, then strip k and check for comments.
                # This way fewer strips need to be done (since k has to be stripped on the right end anyway)
                try:
                        k, v = line.split('=>', 1)
                except:
                        continue
                k = k.strip()
                if k.startswith('#'):
                        continue
                # The values in 'v' are stripped as they are output.
                grammar[k.strip()] = v.split('|')
        return grammar

def cfg_parse_expand(f, randobj=random):
        return cfg_expand(cfg_parse_file(f), randobj)

# --------------------------------------------------------------------------------------------------------------
# wordfilter engine (which uses a syntax intentionally similar to the context-free grammar engine above)

def wordfilter(message, rules, randobj=random):
        """rules should be some sort of iterable containing strings.
        A file() object will suffice, but an array of strings works just as well."""

        for line in rules:
                try:
                        find, replace = line.split('=>', 1)
                except:
                        continue
                find = find.strip()
                if find.startswith('#'):
                        continue
                if '|' in replace:
                        replace = randobj.choice(replace.split('|')).strip()
                else:
                        replace = replace.strip()
                # If the find and replace texts are both lowercase, and no replacement backrefs
                # are present, make the replacement case-insensitive, but case-preserving.
                preserve = (find.islower() and replace.islower() and '\\' not in replace)
                flags = (0, re.I)[preserve]
                try:
                        regex = re.compile(find, flags)
                except:
                        regex = re.compile(re.escape(find), flags)
                if preserve:
                        replace = lambda m, p=replace: preserve_case(m.group(0), p)
                try:
                        message = regex.sub(replace, message)
                except:
                        pass
        return message

# --------------------------------------------------------------------------------------------------------------
# FieldStorage replacement, because FieldStorage sucks

#cgi.maxlen - maximum number of bytes to allow in a file upload
# (set this before fiddling with FieldStorage)

class CGIForm(object):
        """FieldStorage wrapper with a more sane API.

        Methods available:
                'field' in form - check for existence of a field
                form.field - get a form field as a string, u'' if not defined
                        Note: this ALWAYS returns a unicode string. by default utf-8 encoding is used.
                        Set the 'encoding' parameter to change this behavior.
                form['field'] - get a form field as a list, [] if not defined
                form.list('field') - same as form['field']
                form.text('field') - same as form.field
                form.int('field', default=0) - get the value as a number.
                        Returns 'default' (which defaults to None) if non-numeric.
                form.file('upload') - return a file object. only works for uploaded files, returns None if not a file.
                        Note: the syntax form.upload will return the file's contents as a string.

        This may raise ValueError on instantiation if an uploaded file has a completely invalid filename.
        """
        encoding = 'utf-8'

        def __init__(self):
                self._fs = cgi.FieldStorage(keep_blank_values=True)
                self._cache = {}

        def __contains__(self, field):
                """Check for the existence of a given field in the form. This is subtly
                different from checking its *value*."""
                return field in self._fs

        def _decode(self, s):
                return unicodedata.normalize('NFC', strip_illegal_unicode(s.decode(self.encoding, 'ignore')))

        def _fixup(self, fs):
                """Make a much more useful representation of a field.
                input: cgi.FieldStorage
                output: depends!
                        - if it's a file, the FieldStorage with 'filename' and 'length' attributes added.
                        - if it's a string, a unicode version of that string decoded with the proper encoding.
                """
                if not getattr(fs, 'filename', False):
                        # this is just a normal string field; decode it
                        return self._decode(fs.value)

                # this is a file... need to do some leg work
                fn = self._decode(fs.filename)

                # hackarounds for stupid browsers, notably msie but others might do this as well
                if '/' in fn:           fn = fn.split('/')[-1]
                elif '\\' in fn:        fn = fn.split('\\')[-1]
                # throw out garbage characters (hax?)
                fn = re.sub(r'[/\\:|~%*?]', '_', fn)
                fn = re.sub(r'^[.~]+|[.~]+$', '', fn)
                if not fn:
                        raise ValueError, 'Invalid filename'
                fs.filename = fn

                # get the filename. (the cgi parser already knew this at some point, so why didn't it save it?)
                fs.file.seek(0, 2) # EOF
                fs.length = fs.file.tell()
                fs.file.seek(0) # BOF

                return fs

        def list(self, field):
                """Retrieve all values for a given field name as a list.
                String values are returned as unicode; files are returned as modified FieldStorage objects
                with .filename and .length parameters properly defined."""
                if field in self._cache:
                        return self._cache[field]

                # _fs[field] will either be a FieldStorage of some sort, or a list thereof
                # or it won't exist, in which case we'll turn it into a blank list
                try:
                        data = self._fs[field]
                except:
                        data = []

                # FieldStorage doesn't always return lists, so let's fix that.
                if isinstance(data, list):
                        data = map(self._fixup, data)
                else:
                        data = [self._fixup(data)]

                # from the client side, when requesting a list, if it's not an instance of basestring, then
                # assume it's a file -- guaranteed to have field.filename, and the usual file manipulation
                # functions (read, seek, etc.) are located in field.file.*
                self._cache[field] = data
                return data

        def text(self, field):
                """Get the text value of a field.
                If the field is an uploaded file, behavior is undefined. (Currently, the filename is returned.)
                A blank Unicode string is returned for nonexistent fields; use __contains__ to see if a given
                field actually exists or not."""
                try:
                        data = self[field][0]
                except:
                        data = u''
                if not isinstance(data, basestring):
                        return data.filename # ?
                return data

        def int(self, field, default=None):
                """Get a field's value as an integer.
                If the field does not exist or cannot be coerced to an integer, this returns 'default'."""
                try:
                        data = int(self[field][0])
                except:
                        data = default
                return data

        def file(self, field):
                """Get a file field.
                If the field does not exist or is not a file, this returns None."""
                try:
                        data = self[field][0]
                except:
                        data = None
                if isinstance(data, basestring):
                        return None
                return data

        # Remember that square brackets == list, and these will make sense.
        __getitem__ = list
        __getattr__ = text
