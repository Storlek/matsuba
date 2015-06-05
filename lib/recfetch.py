#!/usr/bin/env python2
from __future__ import print_function

import httplib, urlparse, socket

# how many seconds should we wait when trying to connect?
SOCKET_TIMEOUT = 5

# After this many HTTP redirects, give up.
# If someone is using a tinyurl service,
# which redirects to a site which is in turn using redirects to clean up
# URLs or reroute people who aren't logged in, and also happens to have
# some old URL redirection cruft, we might actually see four legitimate
# redirects for one shortened URL.
# Anything beyond that is likely junk.
MAX_REDIRECTS = 3


def _fetch(link, history):
        if len(history) > MAX_REDIRECTS:
                return u'<too many redirects>'

        http, domain, path, query, fragment = urlparse.urlsplit(link)
        if not path:
                path = '/'

        try:
                connection = {
                        'http': httplib.HTTPConnection,
                        'https': httplib.HTTPSConnection,
                }[http]
        except:
                return u''

        if query:
                path += '?' + query

        headers = {
                # some hosts do content filtering to show innocent pages
                # to bots but present malicious content to users
                'User-Agent': 'Mozilla/4.0 (compatible)',
        }
        if history:
                headers['Referer'] = history[0]

        history.append(link)

        c = connection(domain, timeout=SOCKET_TIMEOUT)
        c.connect()
        if c.sock.getpeername()[0] == c.sock.getsockname()[0]:
                # same host? someone trying to hax our anus?
                # (XXX find a concise way to do this without necessarily opening a connection!)
                c.close()
                return u'<localhost>'
        c.request('GET', path, headers=headers)
        r = c.getresponse()

        if r.status in {301, 302, 303, 307}:
                loc = r.getheader('Location')
                return _fetch(loc, history)

        ct = r.getheader('Content-Type')
        if ct.startswith(('text/', 'application/xhtml', 'application/xml')):
                data = r.read(16384)

                # warning: shitty code ahead
                try:
                        for enc in ['utf8', 'utf-8', 'shift-jis', 'shift_jis', 'shiftjis', 'sjis']:
                                if enc in ct:
                                        data = data.decode(enc, 'replace')
                                        break
                        else:
                                data = data.decode('latin1', 'replace')
                except UnicodeError:
                        if not isinstance(data, unicode):
                                # oh well, screw it
                                data = '<unhandled encoding>'

        else:
                # don't bother reading binary content
                data = '<binary data>'
        return data


# return: (history, data)
def fetch(link):
        if isinstance(link, unicode):
                link = link.encode('utf8', 'replace')
        history = []
        try:
                data = _fetch(link, history)
        except socket.timeout:
                # oh well
                data = '<socket timeout>'
        except socket.error as e:
                data = '<socket error: %r>' % e
        history = map(lambda s: s.decode('utf8', 'replace'), history)

        return history, data


if __name__ == '__main__':
        import sys
        for url in sys.argv[1:]:
                history, data = fetch(url)
                print("===", url, "===")
                print([e.encode('utf8','replace') for e in history])
                print(data.encode('utf8', 'replace'))
                print()
