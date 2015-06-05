import posixpath, operator, extutil, urllib
from itertools import izip, cycle, repeat

def filecount(posts):
        return len(filter(operator.attrgetter('filename'), posts))

# Format a timestamp
def timestamp(post, dateformat='futaba'):
        t = post.time
        return extutil.format_timestamp(t, dateformat)

# replacement for mako's "u" filter, which just replaces slashes and colons,
# and is generally useless for full paths
def upath(s):
        return urllib.quote(s.encode('utf8', 'ignore'), safe='/=:;@#?')

# 4chan appears to put the <a> tag on the *outside* of the spans, which
# results in the underline rendering as a different color from the text
def format_name_trip(seq, namefmt, tripfmt, link=None):
        if isinstance(seq, basestring): seq = [seq] # blah
        seq = [
                cycle([namefmt[0], tripfmt[0]]),
                seq,
                cycle([namefmt[1], tripfmt[1]]),
        ]
        if link:
                seq.insert(+1, repeat('<a href="%s">' % link))
                seq.insert(-1, repeat('</a>'))
        out = []
        for chunk in izip(*seq):
                out.extend(chunk)
        return ''.join(out)
