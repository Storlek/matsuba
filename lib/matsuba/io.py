from __future__ import print_function

import sys, os, posixpath, pwd, random, re, cgi, sha, time, urlparse, itertools, operator, socket
try:
        import json
except ImportError:
        import simplejson
from glob import glob

import extutil
from safewriter import SafeWriter

from mako.template import Template
from mako.lookup import TemplateLookup

from matsuba import db
import matsuba.config as cfg
from matsuba.errors import *

CHMOD = 0664 # blah

# --------------------------------------------------------------------------------------------------------------
# dunno where to put this

def get_random_banner(board=None):
        re_image = re.compile(r'^[^.].*\.(?:jpe?g|png|gif)$', re.IGNORECASE)
        def get_banners(urlpath, fspath):
                try:
                        return [posixpath.join('/', urlpath, 'title', os.path.basename(f))
                                for f in os.listdir(os.path.join(fspath, 'title'))
                                if re_image.match(f)]
                except OSError:
                        return None
        banners = None
        if board and random.random() < (2. / 3.):
                # Use a board-specific banner, if there are any.
                banners = get_banners(board.path, board.fspath)
                if banners:
                        # per-board banners follow a weighted distribution
                        # so that newer ones show up more often
                        r = max(random.random(), random.random())
        if not banners:
                banners = get_banners(cfg.IMG_PATH, cfg.IMG_FSPATH)
                r = random.random()
        if not banners:
                return None
        banners.sort()
        try:
                banner = banners[int(r * len(banners))]
        except IndexError:
                # uh?
                return random.choice(banners)
        else:
                return banner

# --------------------------------------------------------------------------------------------------------------

lookup = TemplateLookup(directories=[os.path.join(cfg.PRIVATE_FSPATH, 'templates')],
                        module_directory=os.path.join(cfg.PRIVATE_FSPATH, 'templates',
                                'cache.' + pwd.getpwuid(os.getuid())[0]),
                        input_encoding='utf-8', output_encoding='utf-8', encoding_errors='replace',
                        imports=['from matsuba.templatetools import upath', 'from matsuba.io import url'])

def _template(board, func, template=None):
        template = template or getattr(board, 'template', cfg.DEFAULT_TEMPLATE)
        return lookup.get_template('/%s/%s.html' % (template, func))

def template_config(board=None):
        """Return the module for the common template."""
        return _template(board, 'common').module

def serve_template(func, fileobj=None, **kwargs):
        # config vars should ALWAYS take precedence over local vars
        kwargs.update(cfg.__dict__, get_random_banner=get_random_banner, url=url)
        out = _template(kwargs.get('board'), func, kwargs.get('template')).render(**kwargs)
        if not kwargs.get('_nostrip'):
                out = re.sub(r'\s*\n+\s*', '\n', out)
        out = out.strip()
        if not fileobj:
                fileobj = sys.stdout
                write_http_header(length=len(out))
        fileobj.write(out)


def write_http_header(ctype=None, length=None):
        if ctype is None:
                ctype = 'text/html'
                if cfg.USE_XHTML:
                        xhtml = 'application/xhtml+xml'
                        if xhtml in os.environ.get('HTTP_ACCEPT', ''):
                                ctype = xhtml
        if length is not None:
                print('Content-Length:', length)
        print('Content-Type: %s; charset=utf-8\n' % ctype)
        sys.stdout.flush()

        # and don't come back!
        write_http_header = lambda *a, **k: None

# --------------------------------------------------------------------------------------------------------------
# Error formatting
# (should this be in errors.py maybe?)

def print_error_page(err, form=None, referer=None):
        status = getattr(err, 'status', None)
        if not referer:
                referer = cfg.SITE_PATH + '/'
        header = getattr(err, 'header', err.__doc__) or ("Error: " + err.__class__.__name__)
        board = None
        message = None

        for arg in err.args:
                if isinstance(arg, db.Board):
                        board = arg
                elif not message and isinstance(arg, basestring):
                        message = arg
                #elif isinstance(arg, extutil.CGIForm):
                #        form = arg

        if not message:
                message = getattr(err, 'message', err.__class__.__name__)

        if status is not None:
                print("Status:", status)
        print("X-Python-Error:", repr(err.args))
        serve_template('message', returnlink=referer, header=header, message=message, board=board)

def assert_request_method(request_method, allowed, error=None):
        """Make sure the data was submitted with an appropriate method, and bail if not.
        Example: assert_request_method(request_method, ['POST', 'GET'], 'This is the message body text.')"""
        if not allowed:
                raise ValueError("no request methods given")
        elif request_method not in allowed:
                print("Allow:", ", ".join(allowed))
                raise MethodNotAllowedError(error or ("Method %r not accepted." % request_method))

# --------------------------------------------------------------------------------------------------------------
# url constructor
# this sucks but it works

def url(thread=None, threadid=None, post=None, postid=None, board=None, postrange=None,
        src=None, thumb=None, cat=None, path=None, relative=True, quote=False):
        """Build a complete URL to the base of the board, a thread, post, or filename.
        If file/thumb/cat are set, board needs to be given as well.
        If postrange is set, thread is required.

        If ext is set, thread, post, postrange, src, cat, and thumb should all be None, and board is required.
        Otherwise, the board is inferred from the thread/post if it is not given.

        If both thread and post are given, a thread link is constructed with the post ID in the path fragment
        (e.g.: /t/read/1234/l50#123)

        Additionally, threadid and postid may be given instead of thread and post. This is solely for the post
        quoting code, and should not be used elsewhere if at all possible. The thread and post objects override
        threadid and postid if both are given.

        If relative is False, the base URL is prepended to all requests.

        Regardless of mode, if src/cat/thumb *always* returns /board/(src,cat,thumb)/(file)

        POSTIDS_ABSOLUTE=False
        thread,postrange        /board/read/${thread.id}/${postrange}
        thread                  /board/read/${thread.id}/l50
        post                    /board/read/${post.thread.id}/${post.resid}
        post,quote              /board/read/${post.thread.id}/${post.resid}#i${post.resid}

        POSTIDS_ABSOLUTE=True
        thread (range ignored)  /board/read/${thread.id}/
        post                    /board/read/${post.thread.id}#${post.id}
        post,quote              /board/read/${post.thread.id}#i${post.id}
        """

        if not board:
                try:
                        board = extutil.coalesce(post, thread).board
                except AttributeError:
                        return '/' # idfk?
                        raise MatsubaError('Missing parameters to url()')

        if relative:
                base = board.path
        else:
                base = board.fullurl

        if src or cat or thumb:
                f, d = (src and (src, 'src') or cat and (cat, 'cat') or thumb and (thumb, 'thumb'))
                if f.startswith('http://'):
                        return f
                return urlparse.urljoin(posixpath.join(base, d, ''), f)

        c = template_config(board)

        if thread:
                threadid = thread.id

        if threadid:
                if c.POSTIDS_ABSOLUTE:
                        path = 'read/%d/' % threadid
                else:
                        path = 'read/%d/%s' % (threadid, ('l50' if postrange is None else postrange))
                if post:
                        path += '#%d' % (post.id if c.POSTIDS_ABSOLUTE else post.resid)
                elif postid:
                        path += '#%d' % postid
        elif post:
                if c.POSTIDS_ABSOLUTE:
                        path = 'read/%d/#%s%d' % (post.thread.id, ('i' if quote else ''), post.id)
                else:
                        path = 'read/%d/%d' % (post.thread.id, post.resid)
                        if quote:
                                path += '#i%d' % post.resid
        else:
                path = path or ''
        return posixpath.join(base, path)

# --------------------------------------------------------------------------------------------------------------

class BoardIO(object):
        def write_index_pages(self):
                multi = template_config(self).THREADLIST_MULTIPAGE
                tpp = getattr(template_config(self), 'THREADS_PER_PAGE', cfg.THREADS_PER_PAGE)
                page = 0 # if no threads, 'for page,...' will never run and thus page will never be set
                if multi and self.threads:
                        numpages = (len(self.threads) + tpp - 1) // tpp
                        for page, threads in enumerate(extutil.group(self.threads, tpp)):
                                f = SafeWriter(self.fspath, '%s.html' % (page or 'index'))
                                f.chmod(CHMOD)
                                serve_template('threadlist', fileobj=f, board=self, threads=threads,
                                                page=page, numpages=numpages)
                else:
                        f = SafeWriter(self.fspath, 'index.html')
                        f.chmod(CHMOD)
                        serve_template('threadlist', fileobj=f, board=self, threads=(self.threads or []))

                # delete any stale pages
                # (this is ACTUALLY REALLY STUPID)
                if not multi:
                        page = 1
                for page in xrange(page, sys.maxint):
                        try:
                                os.unlink(os.path.join(self.fspath, '%d.html' % page))
                        except OSError:
                                break

        def write_thread_page(self, thread):
                f = SafeWriter(thread.filename)
                f.chmod(CHMOD)
                serve_template('thread', fileobj=f, board=self, thread=thread)
                if not template_config(self).POSTIDS_ABSOLUTE:
                        op, last50 = thread[0], thread[-50:]
                        del thread[:]
                        # can't use thread.append() here, because that does extra magic!
                        # the code that keeps track of thread properties tries to be way too clever
                        # why did i write it like that
                        if op not in last50:
                                thread.extend([op])
                        thread.extend(last50)
                        f = SafeWriter(thread.filename_l50)
                        f.chmod(CHMOD)
                        serve_template('thread', fileobj=f, board=self, thread=thread)

        def write_other_pages(self):
                for template, page in template_config(self).OTHER_PAGES:
                        f = SafeWriter(self.fspath, page)
                        f.chmod(CHMOD)
                        serve_template(template, fileobj=f, board=self, threads=self.threads)

        def write_all_files(self):
                self.write_index_pages()
                self.write_other_pages()

                for thread in self.threads:
                        self.write_thread_page(thread)

        # ------------------------------------------------------------------------------------------------------
        # Name/ID/etc. generation

        def eval_ruleset(self, ruleset, threadid, ip):
                seed = [cfg.SECRET, ip]
                if 'thread' in ruleset:
                        seed.append(str(threadid))
                if 'board' in ruleset:
                        seed.append(str(self.id))
                m = re.search(r'time(?:=(\d+)(?:\+(\d+))?)?', ruleset)
                if m:
                        seconds = int(m.group(1) or 86400) or 1 # default to a day; don't divide by zero
                        offset = int(m.group(2) or 0) # no timezone shift
                        seed.append('%d' % ((time.time() + offset) / seconds))
                return '.'.join(seed)


        # a. If forced anon, throw out 'name' field contents, and generate a name
        # b. Generate tripcode and secure trip as necessary
        # c. Look up tripcode in capcode list and replace if found
        # d. Handle fusianasan
        def generate_name(self, threadid, name, ip):
                # return: JSON-encoded list of properly cgi-escaped strings.
                # (even elements are name, odd parts are trip)
                if self.forced_anon:
                        name = ''
                if not name:
                        if self.anonymous.startswith('random:'):
                                ruleset = self.anonymous.split(':', 2)[1]
                                # generate a name
                                try:
                                        datafile = file(os.path.join(self.fspath, 'names.dat'))
                                except:
                                        try:
                                                datafile = file(os.path.join(cfg.PRIVATE_FSPATH, 'names.dat'))
                                        except:
                                                datafile = None
                                                name = '' # oh well, we tried

                                seed = self.eval_ruleset(ruleset, threadid, ip)
                                n = sum((256**n * ord(k)) for n, k in enumerate(sha.new(seed).digest()))
                                if datafile:
                                        name = extutil.cfg_parse_expand(datafile, random.Random(n))
                        else:
                                name = self.anonymous

                name, hastrip, tripkey = name.partition('#')
                tripkey, hassecure, securekey = tripkey.partition('#')
                name = cgi.escape(name)

                # don't generate a regular tripcode for name##secure
                if hassecure and not tripkey:
                        hastrip = False
                trip = ''
                if hastrip:
                        trip = '!' + extutil.get_tripcode(tripkey)
                if hassecure:
                        trip += '!!' + extutil.get_secure_hash(securekey, cfg.SECRET)[:8]

                name = name.strip()
                if not self.forced_anon and ('fusianasan' in name or 'mokorikomo' in name):
                        try:
                                host = socket.gethostbyaddr(ip)[0]
                        except:
                                host = ip
                        name = list(reduce(operator.add,
                                           zip(name.replace('mokorikomo', 'fusianasan')
                                                   .split('fusianasan'), itertools.repeat(host))))[:-1]
                else:
                        name = [name]
                if trip:
                        name.append(' ' + trip)
                return json.dumps(name)

        def generate_idcode(self, threadid, sage, ip):
                rs = self.id_ruleset
                if not rs:
                        return ''
                if sage and 'sage' in rs:
                        return 'Heaven'
                return extutil.get_secure_hash(self.eval_ruleset(rs, threadid, ip), cfg.SECRET)[:8]

        # ------------------------------------------------------------------------------------------------------

        def delete_cleanup(self, delthreads, filenames, thumbnails, catnails):
                for filename in [
                        os.path.join(self.fspath, subdir, f)
                        for subdir, group in [('src', filenames), ('thumb', thumbnails), ('cat', catnails)]
                        for f in filter(lambda path: path and not path.startswith('/'), group)
                ]:
                        try:
                                os.unlink(filename)
                        except OSError:
                                pass

                for threadid in delthreads:
                        for middle in ['_l50', '']:
                                try:
                                        os.unlink(os.path.join(self.fspath, 'res', '%d%s.html' % (threadid, middle)))
                                except OSError:
                                        pass

        # ------------------------------------------------------------------------------------------------------

        def translate_post_ranges(self, ranges):
                """Convert a post range string (such as '1-10,24,l5') into a flat list of posts.
                Return value is a Thread object containing just the posts requested."""

                re_range = re.compile(r'^(\d*)-(\d*)$') # posts with ids between x and y
                re_lrange = re.compile(r'^[Ll](\d+)$') # last x posts
                re_qrange = re.compile(r'^[Qq](\d+)$') # any post containing a >>x link
                re_rrange = re.compile(r'^[Rr](\d{0,4})$') # x random posts
                re_drange = re.compile(r'^[Dd](\d+)$') # posts in last x days
                re_post = re.compile(r'^\d+$')
                view_posts = []
                now = int(time.time())

                try:
                        threadid, ranges = ranges.split('/')
                        threadid = int(threadid)
                except: # bogus
                        raise PostDataError(self)
                if not ranges:
                        ranges = '1-' # all posts

                thread = db.Thread(self, threadid)

                first, last = 1, len(thread)

                showfirst = False
                if ranges[0] in 'Nn':
                        ranges = ranges[1:]
                elif re_lrange.match(ranges) or re_drange.match(ranges):
                        showfirst = True
                else:
                        m = re_range.match(ranges)
                        if m:
                                a = int(m.group(1) or '0') or first
                                b = int(m.group(2) or '0') or last
                                if first < a < b:
                                        showfirst = True

                for r in ranges.split(','):
                        # range matching code is straight from kareha.

                        # "1-100" (posts between #1 and #100 inclusive)
                        # * either endpoint may be omitted (or even both)
                        # * range may be specified in reverse order
                        m = re_range.match(r)
                        if m:
                                a = min(int(m.group(1) or '0') or first, last)
                                b = min(int(m.group(2) or '0') or last, last)
                                d = cmp(b, a) or 1 # direction
                                view_posts.extend(xrange(a, b + d, d))
                                continue

                        # "l50" (last 50 posts)
                        m = re_lrange.match(r)
                        if m:
                                a = max(1, last - int(m.group(1)) + 1)
                                view_posts.extend(xrange(a, last + 1))
                                continue

                        # "r4" (4 random posts)
                        m = re_rrange.match(r)
                        if m:
                                r = int(m.group(1) or '1') or 1
                                view_posts.extend(random.randrange(first, last + 1) for n in xrange(r))
                                continue

                        # "q71" (any post referencing >>71)
                        m = re_qrange.match(r)
                        if m:
                                #target_postid = int(m.group(1) or '0')
                                # TODO
                                continue

                        # "d10" (all posts in last 10 days)
                        m = re_drange.match(r)
                        if m:
                                r = now - int(m.group(1) or '0') * 86400 # seconds/day
                                view_posts.extend(p.resid for p in thread if p.time > r)
                                continue

                        # "71" (post #71 by itself)
                        if re_post.match(r):
                                r = int(r)
                                if first <= r <= last:
                                        view_posts.append(r)
                                continue

                        # random junk in the post range list is not an error, just ignore it
                        #raise PostDataError(self)

                if showfirst and first not in view_posts:
                        view_posts.insert(0, first)

                try:
                        view_posts = [thread[post - 1] for post in view_posts]
                except IndexError: # shouldn't happen, but we'll catch it
                        raise PostNotFoundError(self)

                del thread[:]
                thread.extend(view_posts)
                return thread
