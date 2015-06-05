import sys, os, posixpath, re, cgi, base64, sha, Cookie, time, codecs, urllib
import logging

import extutil, imagetools
from safewriter import SafeWriter

from matsuba import Board, adminpanel, db, io, mmark
import matsuba.config as cfg
from matsuba.io import url
from matsuba.errors import *

# This is terrible
imagetools.GIF_MAX_FILESIZE = cfg.GIF_MAX_FILESIZE
imagetools.GIFSICLE_PATH    = cfg.GIFSICLE_PATH
imagetools.CONVERT_PATH     = cfg.CONVERT_PATH
imagetools.SIPS_PATH        = cfg.SIPS_PATH
imagetools.JPEG_QUALITY     = cfg.JPEG_QUALITY

# shut up by default
logging.basicConfig(level=logging.FATAL)

# --------------------------------------------------------------------------------------------------------------
# _fmt_* get the message after it's been cgi.escape'd and wordfiltered; it will be spam-filtered upon return.

def _fmt_simple(board, threadid, postid, message):
        # Futaba style -- don't bother doing anything besides highlight > quotes.
        message = re.compile(r'^(&gt;.*?)$', re.MULTILINE).sub(r'<span class="unkfunc">\1</span>', message)
        message = '<p>' + '<br />'.join(message.splitlines()) + '</p>'
        return message


def _fmt_mmark(board, threadid, postid, message):
        #pat_2ch_quote = r'(n?(?:[0-9lrq,-]|&\#44;)*[0-9lrq-])'
        pat_2ch_quote = r'(n?(?:[0-9lr,-]|&\#44;)*[0-9lr-])'

        if io.template_config(board).POSTIDS_ABSOLUTE:
                _quote_pattern = re.compile(r'&gtgt;(\d+)')
                def _quotelink(m, span, **args):
                        text = m.group(0).replace('&gtgt;', '&gt;&gt;')
                        try:
                                post = board.threads.get_post(int(m.group(1)))
                        except (PostNotFoundError, ValueError):
                                return text
                        return '<a class="quotelink" href="%s">%s</a>' % (url(post=post), text)
        else:
                # pattern from kareha, this could be better (e.g. not grabbing the "-" in ">>1-san")
                _quote_pattern = re.compile(r'&gtgt;(?:/+(\d+)/+)?' + pat_2ch_quote)
                def _quotelink(m, span, **args):
                        text = m.group(0).replace('&gtgt;', '&gt;&gt;')
                        ql_threadid, ql_range = m.groups()
                        try:
                                ql_threadid = int(ql_threadid or threadid)
                        except ValueError:
                                return text
                        return '<a class="quotelink" href="%s">%s</a>' % \
                                (url(board=board, threadid=ql_threadid, postrange=(ql_range or '')), text)

        def _boardquotelink(m, span, **args):
                text = m.group(0).replace('&gtgt;', '&gt;&gt;')
                # therefore: text = head + threadid + tail
                head, ql_boardname, ql_threadid, tail, ql_range = m.groups()

                if ql_boardname == board.name:
                        ql_board = board
                else:
                        try:
                                ql_board = db.Board(ql_boardname)
                        except BoardNotFoundError:
                                return text

                if not ql_threadid:
                        return '<a class="quotelink" href="%s">%s</a>' % (url(board=ql_board), text)
                try:
                        ql_threadid = int(ql_threadid)
                except ValueError:
                        return text

                ql_dbthreadid = ql_board.postid_to_threadid(ql_threadid)
                if not ql_dbthreadid:
                        return text

                if io.template_config(ql_board).POSTIDS_ABSOLUTE:
                        # 'threadid' is really the post id in this case
                        return '<a class="quotelink" href="%s">%s%d</a>%s' % (
                                url(board=ql_board, threadid=ql_dbthreadid, postid=ql_threadid),
                                head, ql_threadid, tail
                        )
                else:
                        return '<a class="quotelink" href="%s">%s</a>' % (
                                url(board=ql_board, threadid=ql_threadid, postrange=(ql_range or '')),
                                text
                        )

        message, n = re.subn(r'(?<!&gt;)&gt;&gt;', '&gtgt;', message)
        if n > 50:
                raise PostDataError(board, 'Too many >> links')

        message = mmark.format(message,
                ('quote link', _quote_pattern, _quotelink, 'markdown link'),
                ('board + quote link', re.compile(r"""
                        ( &gtgt;&gt; /+ (\w+) /* )
                        (?: (?<=/) (\d+) ( /* (?: (?<=/) """ + pat_2ch_quote + r""" ) ? ) ) ?
                        """, re.VERBOSE), _boardquotelink, 'markdown link'),
                mmark.RULE_IMAGE,
        ).replace('&gtgt;', '&gt;&gt;')

        return message


DEFAULT_FORMAT = _fmt_mmark

def handle_message(board, threadid, postid, message, format=None):
        message = cgi.escape(message)

        try:
                rules = codecs.open(os.path.join(board.fspath, 'wordfilters.dat'), 'r', 'utf-8')
        except:
                pass
        else:
                message = extutil.wordfilter(message, rules)
                rules.close()

        formatter = globals().get('_fmt_%s' % format, DEFAULT_FORMAT)
        message = formatter(board, threadid, postid, message)

        return message

# --------------------------------------------------------------------------------------------------------------
# spam trap

def build_spam_trap(spam_files):
        def _spam_files():
                for spam_file in spam_files:
                        try:
                                f = codecs.open(os.path.join(cfg.PRIVATE_FSPATH, spam_file), 'r', 'utf-8')
                        except:
                                continue
                        for line in f:
                                s = line.strip()
                                # vaguely wakabaish
                                if s.startswith('#') or not s:
                                        continue
                                if s.startswith('/') and s.endswith(('/','/i')):
                                        if s.endswith('i'):
                                                s=s[1:-2]
                                                s=re.sub(r'(?<!\\)[A-Za-z]',
                                                # this function is becoming exceptionally wide
                                                lambda m:'['+(''.join(
                                                        c.upper()+c.lower() for c in m.group(0)
                                                ))+']'
                                                , s)
                                        else:
                                                s=s[1:-1]
                                        try:
                                                # make sure it's not broken
                                                re.compile(s)
                                        except:
                                                raise
                                                s = re.escape(s)
                                        yield '(?:%s)' % s
                                else:
                                        yield re.escape(s)

        pattern = '|'.join(_spam_files())
        if pattern:
                try:
                        pattern = re.compile(pattern)
                except:
                        pass
                else:
                        def findspam(x):
                                spam = pattern.search(x)
                                if spam:
                                        return spam.group(0)
                                return False
                        return findspam
        logging.critical("spam filter compilation failed!")
        return lambda x: None

def spam_trap(*content):
        try:
                from recfetch import fetch
        except ImportError:
                fetch = lambda x: ('', [x])

        # collapse it into one list item
        content = ['\n'.join(i.replace('\n', ' ') for i in content)]

        # less-restrictive secondary list for content of all fetched pages
        fetched = []

        # find links
        link_counts = {}
        for m in extutil.URL_REGEX.finditer(content[0]):
                try:
                        hist, data = fetch(m.group(1))
                except:
                        continue
                hist = map(urllib.unquote, hist)
                content.extend(hist)
                fetched.append(data)
                try:
                        href = hist[-1]
                        link_counts[href] = c = link_counts.get(href, 0) + 1
                except:
                        continue
                if c > cfg.MAX_REPEATED_LINKS > 1:
                        return '<%s repeated %d times>' % (href, c)

        return (build_spam_trap(cfg.SPAM_FILES)('\n'.join(content))
                or build_spam_trap(cfg.HARD_SPAM_FILES)('\n'.join(fetched)))

# --------------------------------------------------------------------------------------------------------------
# Handle the file for a post.

# a. Detect filetype and make sure this kind of file is allowed here
# b. Check that size is not too big
# c. Copy the file to the target directory, and make a checksum while doing so
# d. Check the DB to make sure the checksum is unique; if not, delete the file and bail
# e. Make a thumbnail
# f. If this is a new thread and the board has catalog view enabled, make a catnail

def handle_post_file(board, threadid, upload):
        # uguu~ this sucks

        if upload is None: return [None] * 11

        filename = width = height = checksum = thumbnail = tn_width = tn_height \
                = catnail = cat_width = cat_height = fileinfo = None

        if upload.length > board.max_filesize:
                raise FileTypeError(board, 'File too large (limit is %d bytes)' % board.max_filesize)

        base, ext = os.path.splitext(upload.filename)
        ext, width, height = imagetools.analyze_image(upload.file) or (ext[1:].lower(), 0, 0)
        # this will bail if the file type isn't allowed
        filetype = board.filetype(ext, bool(threadid))
        if len(base) > 35: base = base[:32] + '(...)' # XXX 4chan puts the full name in a tooltip in this case.
        fileinfo = [base + '.' + filetype.extension]

        # upload.filename = the original filename
        # basename = the timestamp string, nothing else
        # filename, thumbnail - no path; these go straight into the db
        # filepath, thumbpath, catpath - full paths to the files on disk
        basename = repr(time.time()).replace('.', '')

        # use a numeric name for all files for now
        filename = basename + '.' + filetype.extension

        filepath = os.path.join(board.fspath, 'src', filename)
        checksum = sha.new()
        filehandle = SafeWriter(filepath)
        filehandle.chmod(io.CHMOD) # ARGH
        upload.file.seek(0)
        while True:
                s = upload.file.read(32768)
                if not s: break
                checksum.update(s)
                filehandle.write(s)
        checksum = base64.b32encode(checksum.digest())

        upload.file.close()
        filehandle.close() # poke SafeWriter to do its stuff
        filehandle = open(filepath, 'rb') # and reopen read-only so thumbnailers can't clobber it

        try:
                if filetype.change_name:
                        dupename = ''
                else:
                        dupename = upload.filename
                board.dupe_check(dupename, checksum)
                imagetools.check_blacklist(filepath)
        except DuplicateError:
                # oops
                os.unlink(filepath)
                raise
        except imagetools.BlacklistError as e:
                os.unlink(filepath)
                logging.info("blacklisted file: %s filename=%r" % (e, upload.filename))
                raise SpamError(board)

        if not filetype.force_thumb:
                thumbpath = os.path.join(board.fspath, 'thumb', basename)
                tn_type, tn_width, tn_height = imagetools.make_thumbnail(filepath, thumbpath,
                        cfg.THUMBNAIL_SIZE[(1 if threadid else 0)], fileobj=filehandle, info=fileinfo,
                        allow_anim=board.animated_thumbs)
                if tn_type:
                        thumbnail = basename + '.' + tn_type
                        thumbpath += '.' + tn_type

        if thumbnail and not threadid:
                catpath = os.path.join(board.fspath, 'cat', basename)
                cat_type, cat_width, cat_height = imagetools.make_thumbnail(thumbpath, catpath,
                        cfg.CATNAIL_SIZE, allow_extract=False, allow_anim=False)
                if cat_type:
                        catnail = basename + '.' + cat_type
                        catpath += '.' + cat_type

        if not filetype.change_name:
                filename = upload.filename
                newfilepath = os.path.join(board.fspath, 'src', filename)
                os.rename(filepath, newfilepath)

        if not thumbnail:
                thumbnail = filetype.thumbnail or cfg.FALLBACK_THUMBNAIL
                thumbpath = os.path.join(cfg.IMG_FSPATH, thumbnail)
                thumbnail = posixpath.join(cfg.IMG_PATH, thumbnail)
                tn_width = tn_height = 0

        if thumbnail and not tn_width and not tn_height:
                try:
                        ext, tn_width, tn_height = imagetools.analyze_image(thumbpath)
                except TypeError:
                        # interesting, a thumbnail was made but it can't be identified...?????
                        pass

        if catnail and not cat_width and not cat_height:
                try:
                        ext, cat_width, cat_height = imagetools.analyze_image(catpath)
                except TypeError:
                        pass

        # drop the original filename if it's unchanged, or if the thumbnailer removed it
        if not (filetype.change_name and fileinfo[0]):
                fileinfo.pop(0)
        fileinfo = ', '.join(fileinfo)

        return (filename, width, height, checksum, thumbnail, tn_width, tn_height,
                catnail, cat_width, cat_height, fileinfo)

# --------------------------------------------------------------------------------------------------------------

def broadcast_new_post(board, post):
        # Write something clever in here! ;)
        pass


# this is way too complicated
def handle_post(environ, board, form, password, poster_ip):
        sage = False
        noko = False
        # if this is set, don't set the 'link' cookie (sage triggers this)
        link_kw = False

        # until poking the board for the next post id, threadid == 0 indicates a new thread.
        threadid = form.int('threadid')

        # Do some limiting checks

        message = form.message.rstrip()
        upload = form.file('upload')
        if not message and upload is None:
                raise EmptyPostError(board)
        if not threadid and not board.text_threads and upload is None:
                raise EmptyPostError(board, 'A file is required to post a new thread.')
        if not threadid and not form.subject and io.template_config(board).REQUIRE_SUBJECT:
                raise EmptyPostError(board, 'A subject is required to post a new thread.')

        for field in ('subject', 'name', 'link'):
                n = len(form.text(field)) - cfg.MAX_FIELD_LENGTH
                if n > 0:
                        logging.info("%s has the longest %s ever" % (poster_ip, field))
                        raise MessageLengthError(board, '%s is %d characters too long' % (field.title(), n))
        n = len(message) - cfg.MAX_MESSAGE_LENGTH
        if n > 0:
                logging.info("%s is trying to write a novel" % poster_ip)
                raise MessageLengthError(board, 'Message is %d characters too long' % n)

        bans = board.ban_check(poster_ip)
        if bans:
                boardid, ban_ip, name_trip, reason, bantime, expires = bans[0]
                # workaround
                if reason.startswith('<p>'):
                        reason = reason[3:]
                if reason.endswith('</p>'):
                        reason = reason[:-4]
                logging.info("%s: banned! reason=%r agent=%r password=%r message=%r"
                             % (poster_ip, reason, environ.get('HTTP_USER_AGENT', '-'), password, form.message))
                raise BannedError(board, reason)

        # Validate link
        #     a. Check for sage/noko
        #        - link_kw is set (meaning "don't cookie this") if the text starts with a hash mark.
        #        - If the ENTIRETY of the link is some combination of 'sage' and 'noko', then 'noko' is removed.
        #     b. If it's not http, ftp, news, irc, mailto, etc., put a '#' in front of it
        ## in: form.link
        ## out: link, sage, noko, link_kw
        link = form.link.strip()
        s = link.lower()
        link_kw = s.startswith('#')
        sage = 'sage' in s
        noko = 'noko' in s
        if re.match(r'(?:#|\s|sage|noko)*$', s):
                link = re.sub('noko', '', link, flags=re.IGNORECASE)

        if link and not extutil.PROTOCOL_REGEX.match(link):
                # make a naive guess
                if '@' in link:                 prefix = 'mailto:'
                elif link.startswith('www.'):   prefix = 'http://'
                elif link.startswith('ftp.'):   prefix = 'ftp://'
                elif link.startswith('irc.'):   prefix = 'irc://'
                elif not link.startswith('#'):  prefix = '#'
                else:                           prefix = ''
                link = prefix + link

        spam = spam_trap(message, form.name, link, form.subject)
        if spam:
                logging.info("%s loves cialis - match=%r name=%r link=%r subject=%r message=%r" % (poster_ip, spam, form.name, link, form.subject, message))
                raise SpamError(board)

        # At this point this is definitely a good post, so ask the board for a new postid
        # (2015 note: actually that's not *quite* true: if the threadid is nonzero but not a real thread, post()
        # will bail out. As a side effect, doing this loses a post id. I don't care enough to fix it.)
        postid = board.get_next_postid()
        if not threadid:
                threadid = postid
                sage = False

        # Handle the upload, if there is one
        # (handle_post_file just returns a bunch of None if there's no upload)
        (filename, width, height, checksum, thumbnail, tn_width, tn_height,
         catnail, cat_width, cat_height, fileinfo) = handle_post_file(board, threadid, upload)

        # Format the message
        message_src = message
        message = handle_message(board, threadid, postid, message_src, form.markup)


        # Handle identity (name, trip, link, secure trip, poster ID)
        # If this was up near the top, it could permit capcode-based
        # exemptions to the ban list and spam filters, but then those
        # same things might result in lingering unused post IDs --
        # which is why it ended up getting shoved way down here.
        name = board.generate_name(threadid, form.name, poster_ip)
        idcode = board.generate_idcode(threadid, sage, poster_ip)


        # Insert stuff into database (and get the post ID back)
        # oh god this hurts
        board.post(
                threadid=threadid,
                postid=postid,
                posttime=int(time.time()),
                sticky=False,
                sage=sage,
                name=name,
                idcode=idcode,
                ip=poster_ip,
                password=password,
                link=link,
                subject=form.subject,
                message=message,
                filename=filename,
                checksum=checksum,
                filesize=getattr(upload, 'length', None),
                width=width,
                height=height,
                thumbnail=thumbnail,
                tn_width=tn_width,
                tn_height=tn_height,
                catnail=catnail,
                cat_width=cat_width,
                cat_height=cat_height,
                fileinfo=fileinfo,
                message_src=message_src,
                markup_style=form.markup,
        )

        # now that we're done with the actual posting part, fetch the post and thread again
        try:
                post = board.threads.get_post(postid)
                thread = post.thread
        except PostNotFoundError:
                logging.critical("/%s/: just posted >>%r, and it disappeared!" % (board.name, postid))
                raise MatsubaError(board, 'Thread missing. Broken database?')

        broadcast_new_post(board, post)

        (changed, filenames, thumbnails, catnails) = board.trim(preserve=[thread])
        delete_cleanup(board, changed, filenames, thumbnails, catnails)

        # the use of == here is intentional, and allows for manually
        # turning off autosage in the database for certain threads
        # in order to preserve them for some reason or another
        if thread.length == board.sage_replies > 0:
                board.set_autosage(thread)

        board.write_index_pages()
        board.write_thread_page(board.threads.get_thread(threadid))
        board.write_other_pages()

        # set cookies for name, and link unless link_kw is set
        # (from the form, NOT locals, since the local values may have been modified)
        extutil.set_cookie('name', form.name or None, 30 * 24 * 3600, cfg.SITE_PATH)
        if not link_kw:
                extutil.set_cookie('link', form.link or None, 30 * 24 * 3600, cfg.SITE_PATH)
        extutil.set_cookie('password', password or None, 30 * 24 * 3600, cfg.SITE_PATH)

        if noko:
                return url(thread=thread, post=post, relative=False)
        else:
                return url(board=board, relative=False)

# --------------------------------------------------------------------------------------------------------------

def delete_cleanup(board, delthreads, filenames, thumbnails, catnails):
        for filename in [
                os.path.join(board.fspath, subdir, f)
                for subdir, group in [('src', filenames), ('thumb', thumbnails), ('cat', catnails)]
                for f in filter(lambda path: path and not path.startswith('/'), group)
        ]:
                try:
                        os.unlink(filename)
                except OSError:
                        pass

        for threadid in delthreads:
                # delete request given, and it's in the changed threads list? must mean this whole
                # thread got deleted. this assumes we're in cascade delete mode, which is currently
                # true, but perhaps it would be cleaner for the delete function to return the
                # threadids as well?
                try:
                        os.unlink(os.path.join(board.fspath, 'res', '%d.html' % threadid))
                except OSError:
                        pass

def handle_delete(board, posts, password, fileonly, referer, remote_addr=''):
        """Delete files. This tries to be relatively smart about where to send the user and redirects to the
        same thread rather than the index if the thread itself wasn't deleted."""

        # FIXME: this is magic, and sucks
        if referer:
                match = re.search(r'/(?:res|read)/+(\d+)', referer)
                referer_thread = (match.group(1) if match else None)
        else:
                referer_thread = None

        changed, filenames, thumbnails, catnails = board.delete(posts,
                password=password, fileonly=fileonly, admin=False,
                req_ip=remote_addr,
                aborn=(not io.template_config(board).POSTIDS_ABSOLUTE))

        # If a post id is in both the list of posts that was requested for deletion, and also in the list
        # of changed posts, then it was the OP of a thread that was just deleted.
        delthreads = set(changed) & set(posts)

        delete_cleanup(board, delthreads, filenames, thumbnails, catnails)

        # Return to the same thread if there was one, and if it was not deleted
        noko = (referer_thread and referer_thread not in (str(threadid) for threadid in delthreads))

        board.write_all_files() # EW

        # note: don't rewrite this as if/else
        return noko and referer or url(board=board, relative=False)

# --------------------------------------------------------------------------------------------------------------

def _main_inner(environ):
        remote_addr = environ.get('REMOTE_ADDR', '127.0.0.1')
        referer = environ.get('HTTP_REFERER', '')
        request_method = environ.get('REQUEST_METHOD', 'GET').upper()

        form = extutil.CGIForm()

        # Fetch the post/delete password from the cookie, or make one up.
        cookie = Cookie.SimpleCookie(environ.get('HTTP_COOKIE', ''))
        try:
                password = cookie['password'].value
        except KeyError:
                password = extutil.get_random_string(8, 14)
        else:
                password = extutil.strip_illegal_unicode(extutil.url_unidecode(password))

        # this will die if no 'board' parameter is given, or if it's not a valid board
        if 'board' in form:
                board = Board(form.board)
        else:
                board = None


        # The only thing we're interested in that *isn't* board-related is the admin panel, so let's get that
        # check out of the way right now.
        if 'login' in form and 'password' in form:
                io.assert_request_method(request_method, ['POST'])
                user = db.User(loginname=form.login, securehash=extutil.get_secure_hash(form.password, cfg.SECRET))

                # expire the cookie later than the login timeout to account for clock skew and whatnot
                extutil.set_cookie('sk', user.sessionkey, 4 * cfg.LOGIN_TIMEOUT, cfg.SITE_PATH)
                extutil.http_redirect(cfg.SITE_BASEURL + cfg.MATSUBA_PATH + '?task=' + (form.task or 'menu'))

        elif 'task' in form:
                # make sure there's no weird characters in the task name
                if not form.task.isalnum():
                        raise PostDataError

                user = None
                # make sure we have a valid user before doing stuff
                try:
                        sk = cookie['sk'].value
                except KeyError:
                        sk = None
                else:
                        sk = extutil.strip_illegal_unicode(extutil.url_unidecode(sk))
                        try:
                                user = db.User(sessionkey=sk)
                        except NoPermissionError:
                                extutil.set_cookie('sk', None, 0)
                        else:
                                extutil.set_cookie('sk', user.sessionkey, 4 * cfg.LOGIN_TIMEOUT, cfg.SITE_PATH)

                # look up the get/post functions
                methods = []
                if adminpanel.get('a_' + form.task): methods.append('GET')
                if adminpanel.get('s_' + form.task): methods.append('POST')
                if methods:
                        io.assert_request_method(request_method, methods)
                        task = adminpanel.get({'GET': 'a_', 'POST': 's_'}
                                                .get(request_method, 'a_') + form.task)
                else:
                        task = None
                if not task:
                        raise PostDataError(board, 'Invalid task')
                if request_method == 'POST':
                        try:
                                logging.info("admin [%s] %s %s %s %s" % (
                                        extutil.format_timestamp(time.time()),
                                        (user.loginname if user else '-'),
                                        remote_addr,
                                        form.task,
                                        ("/%s/" % board.name if board else '-'),
                                ))
                        except:
                                pass
                return task(user, board, form)


        # all right, anything from this point on requires a board
        if not board:
                raise PostDataError('Board parameter missing from request.')



        # request for partial thread (for text boards)
        elif 'read' in form:
                if io.template_config(board).POSTIDS_ABSOLUTE:
                        raise PostDataError(board)
                r = board.translate_post_ranges(form.read)
                io.serve_template('thread', board=board, thread=r)
                eturn

        # request for thread owned by a file
        elif 'srcfind' in form:
                p = board.filename_to_postid(form.srcfind)
                if not p:
                        raise PostNotFoundError('%r is not owned by any thread.' % form.srcfind)
                t = board.postid_to_threadid(p)
                if not t:
                        logging.warning("srcfind: what on earth is with %r?" % (form.srcfind))
                        raise PostNotFoundError('%r is owned by a nonexistent thread. Weird!' % form.srcfind)
                extutil.http_redirect(url(board=board, threadid=t, postid=p))

        elif 'preview' in form:
        # preview for post form:
        #     board = the board name
        #   * preview = thread id
        #     field4 = message
        #     markup = what markup to use (not implemented client-side yet)
        # other fields might exist, but we should ignore them
                io.assert_request_method(request_method, ['POST'])
                message = handle_message(board, form.int('preview'), 0,
                        form.field4, form.markup).encode('utf8', 'replace')
                io.write_http_header(length=len(message))
                sys.stdout.write(message)
                return


        # post form:
        #     board = the board name
        #   * threadid = what thread to reply to
        #     name = spam trap, leave blank
        #     link = spam trap, leave blank
        #     field1 = name
        #     field2 = link
        #     field3 = subject
        #     field4 = message
        #     file = file (duh)
        #     refer to cookie for password
        #     update password in cookie and set name/link after posting
        #     if link == 'noko', redirect to thread, otherwise redirect to board
        elif 'threadid' in form:
                io.assert_request_method(request_method, ['POST'])

                # rename the spamtrapped fields
                if form.name or (form.link not in ['', "'"]):
                        logging.debug("Idiot spambot at %s, name=%r link=%r" % (remote_addr, form.name, form.link))
                        raise SpamError(board)
                form.name = form.field1
                form.link = form.field2
                form.subject = form.field3
                form.message = form.field4

                try: text_style = cookie['textboardstyle'].value
                except: text_style= None
                try: img_style = cookie['imageboardstyle'].value
                except: img_style = None

                if 'filetag' in form:
                        # hack the file tag onto the subject (this sucks)
                        try:
                                tag = cfg.FILE_TAGS[form.int('filetag', -1)][0]
                        except:
                                tag = cfg.FILE_TAGS[-1][0] # last tag = unknown/other
                        form.subject = u'[%s] %s' % (tag, form.subject)

                loc = handle_post(environ, board, form, password, remote_addr)
                extutil.http_redirect(loc)


        # delete form:
        #     board = the board name
        #   * delete = list of post ids (absolute)
        #     fileonly = "on" => delete file only, leave post
        #     refer to cookie for password
        #     redirect to http referer or board
        #     (with a bit of magic to redirect to board if the thread was deleted)
        elif 'delete' in form:
                io.assert_request_method(request_method, ['POST'])

                posts = form.list('delete')
                try:
                        posts = map(int, posts)
                except:
                        logging.info("delete: broken post data, %r" % posts)
                        raise PostDataError(board)
                loc = handle_delete(board, posts, password, form.fileonly == 'on', referer=referer, remote_addr=remote_addr)
                extutil.http_redirect(loc)


        # Why are we still here?!
        raise PostDataError(board, 'Unhandled request')

# --------------------------------------------------------------------------------------------------------------

def cgi_main():
        remote_addr = os.environ.get('REMOTE_ADDR', '127.0.0.1')
        referer = os.environ.get('HTTP_REFERER', '')

        if remote_addr in ['127.0.0.1']:
                exceptionclass = MatsubaError
        else:
                exceptionclass = Exception

        try:
                _main_inner(os.environ)
        except exceptionclass as e:
                if not isinstance(e, MatsubaError):
                        logging.warning('%s: %s' % (e.__class__.__name__, str(e)))
                io.print_error_page(e, referer=referer)

