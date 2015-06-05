import os, posixpath, time, operator, cgi, random, itertools
try:
        import json # 2.6+
except ImportError:
        import simplejson
try:
        import sqlite3 # 2.5+
except ImportError:
        from pysqlite2 import dbapi2 as sqlite3

import extutil, imagetools
from extutil import coalesce
import matsuba.config as cfg
from matsuba.errors import *
import urlparse

import logging

# --------------------------------------------------------------------------------------------------------------

db = sqlite3.connect(cfg.DB_DATABASE)

# --------------------------------------------------------------------------------------------------------------

class Post(object):
        # blah
        def __cmp__(self, other): return cmp(self.id, other.id)
        def __repr__(self): return '<Post /%s/ No.%d>' % (self.board.name, self.id)
        def __hash__(self): return (self.id << 8) ^ self.board.id ^ 74857 # completely arbitrary

        def __init__(self, board, thread, resid, postid, posttime, sticky, sage, aborn, name, idcode,
        ip, password, link, subject, message, filename, checksum, filesize, width, height, thumbnail, tn_width,
        tn_height, catnail, cat_width, cat_height, fileinfo, message_src, markup_style):
                # wheesh
                self.board = board
                self.thread = thread
                self.resid = resid # reply counter within this post's thread, always starts with 1
                self.id = postid # global postid

                self.time = posttime
                self.sticky = sticky
                self.sage = sage
                self.aborn = aborn
                self.idcode = idcode

                # patch up name for json data
                try:
                        name = json.loads(name)
                except:
                        name = []
                if not isinstance(name, list):
                        name = []
                self.name_trip = name

                self.ip = ip
                self.password = password
                self.link = link
                self.subject = subject
                self.message = message
                self.filename = filename
                self.basename = filename and posixpath.split(filename)[-1]
                # why yes, this IS a very stupid way to do this
                try:
                        f, ext = os.path.splitext(self.basename)
                        if len(f) >= 13 and f.isdigit() and 1000000000 < int(f[:10]) < 2147385600:
                                f = f[:10]
                        elif len(f) > 24:
                                f = f[:24] + '(...)'
                        self.short_basename = f + ext
                except:
                        self.short_basename = self.basename
                self.checksum = checksum
                self.filesize = filesize
                self.width = width
                self.height = height
                self.thumbnail = thumbnail
                self.tn_width = tn_width
                self.tn_height = tn_height
                self.catnail = catnail
                self.cat_width = cat_width
                self.cat_height = cat_height
                self.extrainfo = fileinfo
                self.message_src = message_src
                self.markup_style = markup_style

                # .sizeinfo = just dimensions and filesize
                # .extrainfo = just original filename and other stuff
                # .fileinfo = sizeinfo and extrainfo combined
                i = []
                if self.filesize:
                        i.append(extutil.format_filesize(self.filesize))
                if width or height:
                        i.append('%dx%d' % (width, height))
                self.sizeinfo = ', '.join(i)
                if self.extrainfo:
                        i.append(self.extrainfo)
                self.fileinfo = ', '.join(i)

# --------------------------------------------------------------------------------------------------------------

class Thread(list):
        # sort() only uses lt
        def __lt__(self, other): return (self.sticky, self.age) >= (other.sticky, other.age)
        def __gt__(self, other): return NotImplemented
        def __le__(self, other): return NotImplemented
        def __ge__(self, other): return NotImplemented
        def __eq__(self, other): return NotImplemented
        def __ne__(self, other): return NotImplemented

        def __repr__(self): return '<Thread /%s/ No.%d>' % (self.board.name, self.id)
        def __hash__(self): return (self.id << 8) ^ self.board.id ^ 30427 # also completely arbitrary

        def __init__(self, board, threadid, data=None):
                """Build a thread object.
                If data is not None, it should be an iterable returning either Post objects or tuples
                equivalent to the SQL statement below. Otherwise, the database is queried for the thread
                contents.

                age = last time the thread was bumped
                """
                threadid = int(threadid) # data check

                if data is None:
                        curs = db.cursor()
                        # the order here MUST match Post.__init__
                        curs.execute("""
                        SELECT
                                postid, posttime, sticky, sage, aborn, name, idcode, ip, password, link,
                                subject, message, filename, checksum, filesize, width, height, thumbnail,
                                tn_width, tn_height, catnail, cat_width, cat_height, fileinfo,
                                message_src, markup_style
                        FROM posts
                        WHERE boardid = ? AND threadid = ?
                        ORDER BY postid ASC
                        """, (board.id, threadid))
                        data = iter(curs.fetchone, None)

                # Really, the thread age, sticky, closed, permasage, etc. should be in a separate table in the
                # database so that it isn't necessary to read the entire table when building a board.
                # Most of these settings make no sense attached to individual posts anyway, and this makes
                # migrating posts between one thread and another complicated.
                self.board = board
                self.id = threadid
                self.age = threadid
                self.sticky = False
                self.closed = False # TODO

                self.filename = os.path.join(self.board.fspath, 'res', '%d.html' % self.id)
                self.filename_l50 = os.path.join(self.board.fspath, 'res', '%d_l50.html' % self.id)

                for n, row in enumerate(data):
                        post = Post(board, self, n + 1, *row)
                        self.append(post)
                        self.sticky |= post.sticky
                if not len(self):
                        # something that might be interesting: return a 410 Gone if the board has any post ids
                        # greater than the given threadid
                        raise PostNotFoundError(board, "Thread #%d not found." % threadid)
                self.length = len(self)

                # blahh
                self.subject = self[0].subject
                self.sage = self[0].sage

                self._find_age()
                self.sort()

        def _find_age(self):
                for post in reversed(self):
                        if not (post.sage or post.aborn):
                                break
                self.age = post.id

        def get_file_size(self):
                """Calculate the amount of disk space used by the files in this thread. Thumbnails are not
                counted in this calculation. (Perhaps they should be? Maybe fudge it.)"""
                return sum(filter(None, map(operator.attrgetter('filesize'), self)))

        def get_text_size(self):
                """Get the size of the thread on disk. This isn't always accurate and might not even work."""
                try:
                        s = os.stat(self.filename).st_size
                except:
                        s = 0
                return s

        def append(self, post):
                """Add a post to the thread."""
                list.append(self, post)
                post.thread = self
                post.resid = self.length = len(self)
                self.sticky |= post.sticky
                self._find_age()
                self.sort()

        def remove(self, post):
                """Remove a post from the thread. Note that this does *not* update the post resids, but when
                the board is reinitialized and the database is fetched again, they will be different. If this
                is problematic (i.e. for text boards) the post should be aborn'd instead of being deleted
                completely."""
                # can't just do del self[post.resid - 1], that will
                # break hideously when a second post is deleted.
                list.remove(self, post)
                if self.age == post.id:
                        self._find_age()
                        self.sort()

# --------------------------------------------------------------------------------------------------------------

# cheat sheet:
# tl.get_thread(threadid)
# tl.get_post(postid)
# deleted_posts, affected_threads = tl.delete_posts([postid, postid])
# tl[3] - 3rd thread relative to top of board
# tl[:10] - first ten threads
# for thread in tl: pass - iterate all threads
# for post in tl.posts(): pass - iterate posts in id order (for RSS)
# (thread.id for thread in tl) - all thread ids (why was this needed?)
# len(tl) - thread count

class ThreadList(list):
        def __init__(self, board):
                self.board = board

                curs = db.cursor()
                curs.execute("""
                SELECT
                        threadid, postid, posttime, sticky, sage, aborn, name, idcode, ip, password,
                        link, subject, message, filename, checksum, filesize, width, height, thumbnail,
                        tn_width, tn_height, catnail, cat_width, cat_height, fileinfo,
                                message_src, markup_style
                FROM posts
                WHERE boardid = ?
                ORDER BY threadid ASC, postid ASC
                """, (board.id,))

                threads = {} # threadid: Thread
                for row in iter(curs.fetchone, None):
                        threadid, row = row[0], row[1:]
                        threads.setdefault(threadid, []).append(row)

                self._all_posts = []
                for threadid, data in threads.iteritems():
                        thread = Thread(board, threadid, data)
                        self.append(thread)
                        self._all_posts.extend(thread)

                self._posts_by_id = dict((post.id, post) for post in self._all_posts)
                self._all_posts.sort(reverse=True)
                self.sort()


        def add_post(self, threadid, post):
                if post.id == threadid:
                        # it won't be in the thread list already because this is a new thread, so fetch it
                        post.thread = thread = Thread(self.board, threadid)
                        post.resid = thread.length
                        self.append(thread)
                else:
                        # this is an existing thread, should be able to find it
                        post.thread = thread = self.get_thread(threadid)
                        thread.append(post)
                self._all_posts.insert(0, post)
                self._posts_by_id[post.id] = post
                self._all_posts.sort(reverse=True)
                self.sort()


        def delete_posts(self, postids):
                """Delete posts, keeping track of internal references like it should. This doesn't touch the
                database; doing so is up to the caller.

                Return value is a tuple of (deleted_posts, affected_threads)."""
                deleted_posts = []
                affected_threads = set()

                # de-reference this post everywhere
                for postid in postids:
                        try:
                                post = self._posts_by_id[postid]
                        except:
                                # guess it doesn't exist, can't delete it in this case!
                                continue
                        thread = post.thread
                        affected_threads.add(thread)

                        if postid == thread.id: # first post; nuke the thread
                                for post in thread:
                                        deleted_posts.append(post)
                                        self._all_posts.remove(post)
                                        del self._posts_by_id[post.id]
                                self.remove(thread)
                        else: # reply; delete the post from the thread and our own lists
                                deleted_posts.append(post)
                                thread.remove(post)
                                del self._posts_by_id[postid]

                if affected_threads:
                        self.sort()
                return deleted_posts, affected_threads


        def trim(self, max_threads=None, max_age=None, max_size=None, preserve=None):
                preserve = frozenset(preserve or [])

                deleted_posts = []
                affected_threads = set()

                if max_age is not None:
                        d, a = self.delete_posts(
                                thread.id for thread in self
                                if thread[0].time > max_age
                                and thread not in preserve
                        )
                        deleted_posts.extend(d)
                        affected_threads.update(a)

                if max_size is not None:
                        size = self.get_file_size()
                        postids = []
                        for thread in reversed(self):
                                if thread in preserve:
                                        continue
                                if size <= max_size:
                                        break
                                size -= thread.get_file_size()
                                postids.append(thread.id)

                        d, a = self.delete_posts(postids)
                        deleted_posts.extend(d)
                        affected_threads.update(a)

                if max_threads is not None and len(self) > max_threads:
                        d, a = self.delete_posts(t.id for t in self[max_threads:] if t not in preserve)
                        deleted_posts.extend(d)
                        affected_threads.update(a)

                return deleted_posts, affected_threads


        def get_thread(self, threadid):
                """Look up a thread by id. PostNotFoundError is raised if the thread doesn't exist."""
                thread = self.get_post(threadid).thread
                if thread.id != threadid:
                        raise PostNotFoundError(self.board, "Thread #%d not found." % threadid)
                return thread


        def get_post(self, postid):
                try:
                        return self._posts_by_id[postid]
                except KeyError:
                        raise PostNotFoundError(self.board, "Post #%d not found." % postid)


        def posts(self, numposts=None):
                if numposts:
                        return iter(self._all_posts[:numposts])
                else:
                        return iter(self._all_posts)


        def get_file_size(self):
                return sum(filter(None, map(operator.attrgetter('filesize'), self._all_posts)))

# --------------------------------------------------------------------------------------------------------------

class Board(object):
        def __init__(self, boardname):
                curs = db.cursor()
                curs.execute("""
                SELECT
                        boardid, host, name, title, max_filesize, max_pages, sage_replies,
                        close_replies, template, text_threads, forced_anon, anonymous, id_ruleset
                FROM boards
                WHERE name = ?
                """, (boardname,))

                try:
                        (
                                self.id, self.host, self.name, self.title, max_filesize, max_pages, sage_replies,
                                close_replies, template, text_threads, forced_anon, anonymous, id_ruleset
                        ) = curs.fetchone()
                except:
                        raise BoardNotFoundError('Unknown board /%s/' % boardname)
                # This is a stupid check, there should be a SITE_HOST that's used to construct the url
                if self.host not in cfg.SITE_BASEURL:
                        raise BoardNotFoundError('Your princess is in another castle')

                self.animated_thumbs = True

                self.text_threads       = coalesce(text_threads,        cfg.ALLOW_TEXT_THREADS)
                self.forced_anon        = coalesce(forced_anon,         cfg.FORCED_ANON)
                self.anonymous          = coalesce(anonymous,           cfg.ANONYMOUS)
                self.id_ruleset         = coalesce(id_ruleset,          cfg.DEFAULT_ID_RULESET)
                self.max_filesize       = coalesce(max_filesize,        cfg.MAX_FILESIZE)
                self.max_pages          = coalesce(max_pages,           cfg.MAX_PAGES)
                self.sage_replies       = coalesce(sage_replies,        cfg.THREAD_AUTOSAGE_REPLIES)
                self.close_replies      = coalesce(close_replies,       cfg.THREAD_AUTOCLOSE_REPLIES)
                self.template           = coalesce(template,            cfg.DEFAULT_TEMPLATE)

                if self.name == self.host:
                        # This is a board running on its own domain
                        self.path = cfg.SITE_PATH or '/'
                        self.fspath = cfg.SITE_FSPATH
                else:
                        self.path = posixpath.join(cfg.SITE_PATH or '/', self.name)
                        self.fspath = os.path.join(cfg.SITE_FSPATH, self.name)
                self.fullurl = cfg.SITE_BASEURL + self.path

                self.__threads = None


        def _get_all_threads(self):
                if not self.__threads:
                        self.__threads = ThreadList(self)
                return self.__threads
        threads = property(_get_all_threads, doc="""ThreadList of all threads on the board.
                This is generated when it is first accessed.""")


        def _fetch_filetypes(self):
                """Read the acceptable file types for this board.
                This function replaces itself with a dummy function so that it is only called once.
                To re-run this: Board._fetch_filetypes(self)
                """
                self._fetch_filetypes = lambda: None

                curs = db.cursor()
                # the order here MUST match that in FileType.__init__
                curs.execute("""
                SELECT
                        allow_new, allow_reply, extension, change_name, force_thumb, thumbnail
                FROM filetypes
                INNER JOIN board_filetypes ON filetypes.typeid = board_filetypes.typeid
                WHERE board_filetypes.boardid = ?
                """, (self.id,))

                self._filetypes_new, self._filetypes_reply = [], []
                for row in iter(curs.fetchone, None):
                        if not (row[0] or row[1]):
                                # Why is this file type even here?!
                                continue
                        t = FileType(*row[2:])
                        if row[0]:      self._filetypes_new.append(t)
                        if row[1]:      self._filetypes_reply.append(t)

        def all_filetypes(self, reply=None):
                """Get all file types allowed for the board.
                Values of reply:
                        None    Return types allowed in either a new thread or reply
                        True    Return types allowed for replies only
                        False   Return types allowed for new threads only


                *** This function IS NOT intended to be used for file type validation! ***
                Only use this for display purposes.
                """
                self._fetch_filetypes()

                r = []
                if reply in (None, True):
                        r += self._filetypes_reply
                if reply in (None, False):
                        r += self._filetypes_new
                return [t.extension for t in r if t.extension != 'apng']

        def filetype(self, ext, reply):
                """Check that 'ext' is an acceptable file type to post, and return the FileType struct for
                that type of file. This should be the file's extension, without a dot.

                If reply is True, the reply filetype list is checked; otherwise, the new thread list is."""
                self._fetch_filetypes()

                if reply:
                        r = self._filetypes_reply
                else:
                        r = self._filetypes_new
                for t in r:
                        if t.extension == ext:
                                return t
                raise FileTypeError(self, "File type %s not allowed" % ext.upper())


        def postid_to_threadid(self, postid):
                """Return: None or threadid. This is just for the post quoting code."""
                curs = db.cursor()
                curs.execute("SELECT threadid FROM posts WHERE boardid = ? AND postid = ?", (self.id, postid))
                row = curs.fetchone()
                return row and row[0]

        def filename_to_postid(self, filename):
                """Return: None or postid."""
                curs = db.cursor()
                curs.execute("SELECT postid FROM posts WHERE boardid = ? AND filename = ?", (self.id, filename))
                row = curs.fetchone()
                return row and row[0]


        def ban_check(self, ip):
                """Return a list of all bans associated with the given IP address on either this board or globally."""
                curs = db.cursor()
                curs.execute("""
                        SELECT boardid, ip, name, reason, bantime, expires
                        FROM bans
                        WHERE COALESCE(boardid, ?) = ?
                        AND ? LIKE ip
                        AND (expires IS NULL or expires >= ?)
                        ORDER BY bantime DESC
                """, (self.id, self.id, ip, int(time.time())))
                rows = curs.fetchall()
                return rows

        def dupe_check(self, filename, checksum):
                """Raise an exception if the same file was already posted somewhere on the board."""

                curs = db.cursor()
                curs.execute("""
                        SELECT threadid, postid, filename, checksum FROM posts
                        WHERE boardid = ? AND (
                                (filename IS NOT NULL AND filename = ?)
                                OR (checksum IS NOT NULL AND checksum = ?)
                        ) ORDER BY posttime DESC LIMIT 1
                """, (self.id, filename, checksum))
                row = curs.fetchone()
                if not row:
                        return

                threadid, postid, last_filename, last_checksum = row
                from matsuba.io import url
                loc = cgi.escape(url(board=self, threadid=threadid, postid=postid))
                if filename == last_filename:
                        msg = 'A file named "%s"' % filename
                else:
                        msg = "This file"
                raise DuplicateError(self, '%s has already been posted <a href="%s">here</a>.' % (msg, loc))


        def get_next_postid(self):
                """Get the next auto-increment number."""
                try:
                        curs = db.cursor()
                        curs.execute('BEGIN EXCLUSIVE TRANSACTION')
                        curs.execute('UPDATE boards SET post_seq = post_seq + 1 WHERE boardid = ?', (board.id,))
                        curs.execute('SELECT post_seq FROM boards WHERE boardid = ?', (board.id,))
                        db.commit()
                        row = curs.fetchone()
                        val = int(row[0])
                except:
                        raise BoardNotFoundError("Board sequence missing or broken. (Configuration error?)")
                return val

        def post(self, threadid, postid, posttime, sticky, sage, name, idcode, ip, password, link,
        subject, message, filename, checksum, filesize, width, height, thumbnail, tn_width, tn_height, catnail,
        cat_width, cat_height, fileinfo, message_src, markup_style):
                """Post. Most fields should be self-explanatory."""

                curs = db.cursor()

                if threadid != postid:
                        # two birds, one stone: make sure the thread exists, and see if it's been permasaged
                        curs.execute("""
                                SELECT sage FROM posts WHERE boardid = ? AND threadid = ? LIMIT 1
                        """, (self.id, threadid))

                        row = curs.fetchone()
                        if not row:
                                raise PostNotFoundError(self, "Thread #%d not found." % threadid)
                        sage = sage or row[0]

                # OH GOD IT'S FULL OF ?s
                curs.execute("""
                INSERT INTO posts (
                        boardid, threadid, postid, posttime, sticky, sage, name, idcode, ip, password,
                        link, subject, message, filename, checksum, filesize, width, height, thumbnail,
                        tn_width, tn_height, catnail, cat_width, cat_height, fileinfo,
                        message_src, markup_style
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (self.id, threadid, postid, posttime, sticky, sage, name, idcode, ip, password,
                link, subject, message, filename, checksum, filesize, width, height, thumbnail, tn_width,
                tn_height, catnail, cat_width, cat_height, fileinfo, message_src, markup_style))
                # And just for privacy's sake: wipe IP and password from posts over 30 days old
                curs.execute("""
                UPDATE posts SET ip='', password=''
                WHERE posttime < ?
                """, (int(time.time()) - (60*60*24*30),))

                # When is this actually needed? I seem to be getting along just fine without it.
                db.commit()

                if self.__threads:
                        # thread=None, resid=0, aborn=False
                        # the first two are filled in by the thread object when the post is added, and aborn
                        # makes no sense when inserting a new post
                        self.__threads.add_post(threadid, Post(self, None, 0, postid, posttime, sticky, sage,
                                False, name, idcode, ip, password, link, subject, message, filename,
                                checksum, filesize, width, height, thumbnail, tn_width, tn_height, catnail,
                                cat_width, cat_height, fileinfo, message_src, markup_style))


        # TODO: 'single' and 'hybrid' modes.
        def delete(self, postids, password=None, fileonly=False, admin=False, firstpost='cascade', req_ip='',
                   aborn=False):
                """Delete posts.
                If the password given for *any* post is incorrect, none of the posts will be deleted and this
                will raise an exception, unless admin is also enabled.

                The firstpost parameter changes the effect that deleting the first post in a thread has;
                this has no effect when fileonly is enabled. Possible values are as follows:
                        single  - if first post is deleted, other posts stay put
                        cascade - the entire thread is deleted (default)
                        hybrid  - delete thread if no (non-deleted) replies, otherwise delete the post only
                (unimplemented -- only 'cascade' works)

                req_ip is the request IP; this should normally not need to be set. Users with cookies disabled
                may still delete posts if they screwed up, via the same IP address within a day of posting.
                """

                oldtime = time.time() - 86400 # allow delete from same ip without password for one day
                changed = set() # threads which have had data changed
                filenames = set() # files to delete
                thumbnails = set() # thumbnails referenced in deleted posts
                catnails = set() # catalog thumbnails referenced in deleted posts
                postids = list(postids)
                if len(postids) > 20:
                        raise PostDataError("trying to delete too many things")
                if not postids:
                        return changed, filenames, thumbnails, catnails

                if firstpost == 'cascade' and not fileonly:
                        threadids = postids # select all posts in the thread when deleting threads
                else:
                        threadids = []

                # If aborn is defined, it should be a string to set the post message to, and the 'aborn' flag
                # in the database will be set.
                # aborn is ignored if fileonly is set.
                # FIXME: thread trimming will result in a hell of a lot of aborns in text mode...
                if aborn:
                        if admin:
                                aborn = 'Post deleted by moderator.'
                        else:
                                aborn = 'Post deleted by user.'
                else:
                        aborn = None

                # never allow a blank password -- set it to something that will never match any value in the db
                req_password = password or None

                in_clause = ("postid IN ("
                             + ",".join("?" * len(postids))
                             + ")")
                if threadids:
                        in_clause += (" OR threadid IN ("
                                      + ",".join("?" * len(threadids))
                                      + ")")

                curs = db.cursor()
                curs.execute("""
                        SELECT threadid, postid, ip, password, posttime, filename, thumbnail, catnail
                        FROM posts
                        WHERE boardid = ? AND (""" + in_clause + ")",
                    ((self.id,) + tuple(postids) + tuple(threadids)))
                meta = curs.fetchall()

                del_postids = []
                for (threadid, postid, ip, password, posttime, filename, thumbnail, catnail) in meta:
                        # should this post be deleted?
                        if postid in postids and not (admin or password == req_password or (ip == req_ip and posttime > oldtime)):
                                # no!
                                db.rollback()
                                logging.info("delete post: no permission - admin=%s password=%s req_password=%s ip=%s req_ip=%s posttime=%s oldtime=%s" %
                                                (admin, password, req_password, ip, req_ip, posttime, oldtime))
                                raise NoPermissionError(self, "Cannot delete (incorrect deletion key)")
                        changed.add(threadid)
                        filenames.add(filename)
                        thumbnails.add(thumbnail)
                        catnails.add(catnail)
                        if fileonly:
                                # this really doesn't belong here...
                                if threadid == postid:
                                        tn_file = cfg.DELETED_THUMBNAIL
                                else:
                                        tn_file = cfg.DELETED_THUMBNAIL_RES
                                thumbpath = os.path.join(cfg.IMG_FSPATH, tn_file)
                                _, tn_width, tn_height = imagetools.analyze_image(thumbpath)
                                tn_file = posixpath.join(cfg.IMG_PATH, tn_file)
                                curs.execute("""
                                UPDATE posts SET
                                        filename = NULL, checksum = NULL, filesize = NULL, width = NULL,
                                        height = NULL, thumbnail = ?, tn_width = ?, tn_height = ?,
                                        catnail = NULL, cat_width = NULL, cat_height = NULL,
                                        fileinfo = 'deleted'
                                WHERE filename IS NOT NULL and boardid = ? AND postid = ?
                                """, (tn_file, tn_width, tn_height, self.id, postid))
                        elif aborn:
                                curs.execute("""
                                UPDATE posts SET
                                        aborn = 1, link = '', message = ?,
                                        message_src = NULL, markup_style = NULL,
                                        subject = (CASE postid WHEN threadid THEN subject ELSE '' END),
                                        filename = NULL, checksum = NULL, filesize = NULL, width = NULL,
                                        height = NULL, thumbnail = NULL, tn_width = NULL, tn_height = NULL,
                                        catnail = NULL, cat_width = NULL, cat_height = NULL, fileinfo = NULL
                                WHERE boardid = ? AND postid = ?
                                """, (aborn, self.id, postid))
                        else: # easy
                                curs.execute("""
                                DELETE FROM posts WHERE boardid = ? AND postid = ?
                                """, (self.id, postid))
                                del_postids.append(postid)

                # clumsy:
                if del_postids and self.__threads:
                        self.__threads.delete_posts(del_postids)
                db.commit()

                return changed, filenames, thumbnails, catnails


        def trim(self, preserve=None):
                """Trim old threads. If preserve is defined, it should be a list of threads to keep."""
                deleted_posts, affected_threads = self.threads.trim(
                        max_threads=(self.max_pages and self.max_pages * cfg.THREADS_PER_PAGE or None),
                        preserve=preserve
                )
                (changed, filenames, thumbnails, catnails) = self.delete((post.id for post in deleted_posts),
                        admin=True, firstpost='cascade')
                return (changed, filenames, thumbnails, catnails)


        def fetch_all_filenames(self):
                """for the orphan finder"""
                curs = db.cursor()
                curs.execute("SELECT threadid, postid, filename, thumbnail, catnail FROM posts WHERE boardid = ?", (self.id,))
                return curs.fetchall()


        def set_autosage(self, thread):
                curs = db.cursor()
                curs.execute("UPDATE posts SET sage = 1 WHERE boardid = ? AND postid = ?",
                        (self.id, thread.id))
                # I don't think this matters anywhere, but for completeness's sake...
                thread.sage = thread[0].sage = True
                db.commit()

# --------------------------------------------------------------------------------------------------------------

class FileType(object):
        """File type information. This class is pretty mundane.
        'thumbnail' here is used if force_thumb is enabled or if the image thumbnailer failed."""
        def __init__(self, extension, change_name, force_thumb, thumbnail):
                self.extension = extension # no dot
                self.change_name = change_name
                self.force_thumb = force_thumb
                self.thumbnail = thumbnail

# --------------------------------------------------------------------------------------------------------------

class User(object):
        # a NoPermissionError raised from the initializer should show a login form on the error page, because it
        # indicates the user hasn't logged in properly yet. elsewhere, it should just show the message because
        # the user is logged in and valid, just trying to do something they're not allowed to do.

        def __init__(self, loginname=None, securehash=None, sessionkey=None):
                if not loginname and not sessionkey:
                        raise NoPermissionError
                curs = db.cursor()
                curs.execute("""
                SELECT userid, securehash, authority, capcode, loginname, lasthit, lastmark, sessionkey
                FROM users
                WHERE loginname = ? OR sessionkey = ?
                """, (loginname, sessionkey))

                try:
                        (
                                self.id, db_hash, self.authority, self.cap, self.loginname,
                                lasthit, self.lastmark, db_sesskey
                        ) = curs.fetchone()
                except:
                        raise NoPermissionError
                self.lasthit = lasthit
                # May proceed if...
                # 1. Session key provided is valid, and not expired
                #    Note that this doesn't need a user name, as session keys are unique.
                if sessionkey and sessionkey == db_sesskey:
                        if lasthit + cfg.LOGIN_TIMEOUT < time.time():
                                # session timed out
                                raise NoPermissionError("Login timed out.")
                # 2. Password hash is valid (in which case, set the session key)
                elif (loginname, securehash) == (self.loginname, db_hash):
                        pass
                # 3. Too bad.
                else:
                        raise NoPermissionError

                self.set_sessionkey()
                self._acl = {} # boardid => permissions


        def invalidate_session(self):
                curs = db.cursor()
                curs.execute("UPDATE users SET sessionkey = NULL WHERE userid = ?", (self.id,))
                db.commit()

        def set_sessionkey(self):
                """The session key is a one-shot token for keeping a login; every time the user does something,
                a new key is assigned. This key expires after LOGIN_TIMEOUT seconds.
                Don't write code like this, kids - it sucks."""
                self.sessionkey = extutil.get_random_string(64)
                curs = db.cursor()
                curs.execute("UPDATE users SET sessionkey = ?, lasthit = ? WHERE userid = ?",
                        (self.sessionkey, int(time.time()), self.id))
                db.commit()


        def get_authorized_boards(self):
                sp = urlparse.urlsplit(cfg.SITE_BASEURL)
                thishost = sp.netloc or sp.path
                curs = db.cursor()
                curs.execute("""
                        SELECT boards.name, boards.title FROM boards
                        INNER JOIN user_boards ON boards.boardid = user_boards.boardid
                        WHERE user_boards.userid = ?
                        AND boards.host = ?
                        AND COALESCE(user_boards.authority, ?) <> 0
                """, (self.id, thishost, self.authority))
                return curs.fetchall()


        def get_acl(self, board):
                # users.authority tells global settings
                # user_boards.authority tells board-specific settings
                # if a bit is not set in users.authority, it doesn't matter what user_boards.authority is,
                # because the user is not authorized to do that action on any board.
                # if user_boards.authority is NULL, then the bit is assumed to be set, i.e. users.authority is
                # used as a fallback in this case.
                # the following settings will enable a user to do everything on all boards (admin):
                #     - users.authority = 0x7fffffff
                #     - user_boards.authority = NULL for all boards
                # to lock that user out from only one board, set user_boards.authority to 0 on that board.
                # to permit a user only to moderate one board, but dictate the permission via users table:
                #     - users.authority = (set relevant bits here)
                #     - user_boards.authority = 0x7fffffff on that board
                #     - user_boards.authority = 0 for all other boards
                # for a user who should be given specific settings on all boards, and full reign over one:
                #     - users.authority = 0x7fffffff
                #     - user_boards.authority = 0x7fffffff for the full-access board
                #     - user_boards.authority = (settings) for the other boards.
                # note that there is no way to give a user *more* permission for one board than the rest; you
                # need to allow full permission globally, and then restrict it for each board.

                # potential security holes abound if this is misused or misconfigured!
                if board is None:
                        return self.authority

                try:
                        board_acl = self._acl[board.id]
                except:
                        curs = db.cursor()
                        curs.execute("""
                                SELECT authority FROM user_boards
                                WHERE userid = ? AND boardid = ?
                        """, (self.id, board.id))
                        res = curs.fetchone()

                        if res is None:
                                board_acl = 0
                        elif res[0] is None:
                                board_acl = self.authority
                        else:
                                board_acl = res[0]

                        board_acl &= self.authority
                        self._acl[board.id] = board_acl

                return board_acl

# --------------------------------------------------------------------------------------------------------------
# misc helpers

def get_all_boards():
        curs = db.cursor()
        curs.execute("SELECT name FROM boards")
        return curs.fetchall()

def add_ban(boardid, ip, name_trip, reason, bantime, expires):
        curs = db.cursor()
        curs.execute("""
                INSERT INTO bans (
                        boardid, ip, name, reason, bantime, expires
                ) VALUES (?,?,?,?,?,?)
        """, (boardid, ip, json.dumps(name_trip), reason, bantime, expires))
        db.commit()

