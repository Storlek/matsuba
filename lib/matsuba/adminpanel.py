import os
import re
import time
import posixpath
import urllib
from glob import glob
import extutil
from matsuba import io, db, Board, mmark
import matsuba.config as cfg
from matsuba.acl import *
from matsuba.errors import *

# some random notes:
# - ACLs only work for specific boards; for stuff that doesn't depend on a board, use acl(0)
#   (which allows anybody who is logged in)
# - if working with more than one board use acl(0) and do acl_check(user, board, privs) by hand
# - to check if the user can do anything at all on a board, use acl(ACL_ANY)

@acl(0)
def a_rebuild(user, board, form):
        io.serve_template('rebuild', template='admin', header='Rebuild', user=user)

def _do_rebuild(board):
        for subdir in ('res', 'src', 'thumb', 'cat'):
                try:
                        os.makedirs(os.path.join(board.fspath, subdir))
                except OSError: # already exists?
                        pass
        board.write_all_files()


@acl(0)
def s_rebuild(user, board, form):
        boards = map(Board, form['board'] or [n for n, t in user.get_authorized_boards()])
        rebuilt = []
        for board in boards:
                if not acl_check(user, board, ACL_ANY):
                        continue
                _do_rebuild(board)
                rebuilt.append(board.name)
        io.serve_template('message', template='admin', header='Rebuild', user=user,
                message='Boards rebuilt: ' + ', '.join(rebuilt))

#no acl
def a_login(user, board, form):
        io.serve_template('login', template='admin', header='Login')
def a_logout(user, board, form):
        if user:
                user.invalidate_session()
        extutil.http_redirect(cfg.SITE_BASEURL + cfg.MATSUBA_PATH + '?task=login')

@acl(0)
def a_menu(user, board, form):
        io.serve_template('menu', template='admin', header='Main Menu', user=user)

@acl(ACL_DELETE)
def a_delpost(user, board, form):
        io.serve_template('delpost', template='admin', header='Delete Post', user=user, board=board)

re_refs = re.compile(r'[ ,.]+')
def tryints(a):
        for i in a:
                try:
                        ii = int(i)
                except:
                        pass
                else:
                        yield ii

@acl(ACL_DELETE)
def s_delpost(user, board, form):
        postids = list(tryints(re_refs.split(form.ref))) # this is stupid
        if len(postids) == 0:
                happened = "Nothing happened"
                form.ban = False
        elif len(postids) == 1:
                happened = "Post deleted"
                poster = 'poster'
        else:
                happened = "Posts deleted"
                poster = 'posters'
        if form.ban:
                now = int(time.time())
                then = now + (15 * (24 * 60 * 60))
                ban_served = False
                for p in postids:
                        try:
                                post = board.threads.get_post(p)
                        except PostNotFoundError:
                                continue
                        if post.ip:
                                db.add_ban(board.id,
                                        post.ip, post.name_trip,
                                        mmark.format(form.banreason),
                                        now, then)
                                ban_served = True
                if ban_served:
                        happened += ' and %s banned' % poster
        happened += '.'
        changed, filenames, thumbnails, catnails = board.delete(postids, admin=True)
        board.delete_cleanup(list(set(postids) & set(changed)), filenames, thumbnails, catnails)

        board.write_all_files() # asdfjkjksdfjk

        io.serve_template('message', template='admin', header='Delete Post', user=user, board=board,
                          message=happened)


def do_stuff_with_orphans(boards, do_delete=False):
        # all filenames here are relative to the board's path
        orphans = []
        ndel = 0 # how many files were deleted?

        for board in boards:
                in_db = set()
                in_fs = set()
                for threadid, postid, filename, thumbnail, catnail in board.fetch_all_filenames():
                        in_db.update((posixpath.join(a, b), postid)
                                for a, b in [('res', '%d.html' % threadid), ('src', filename), ('thumb', thumbnail), ('cat', catnail)]
                                if b and not b.startswith('/'))
                filename_to_postid = dict(in_db)
                in_db = set(t[0] for t in in_db)
                try:
                        os.chdir(board.fspath)
                except:
                        # If it doesn't exist, this dir is probably living on some other domain (ugly ugly ugly!)
                        continue
                for d in ('res', 'src', 'thumb', 'cat'):
                        in_fs.update(p.decode('utf8') for p in glob(os.path.join(d, '*')))
                if posixpath is not os.path:
                        in_fs = set(posixpath.join(*os.path.split(f)) for f in in_fs)

                # toss out everything that's in both sets
                good = in_db & in_fs
                in_db -= good
                in_fs -= good

                # ignore last-50 caches
                in_fs -= set(f for f in in_fs if f.endswith('_l50.html'))

                # let's delete the dangling files straight away
                if do_delete:
                        for f in list(in_fs):
                                try:
                                        os.unlink(f.encode('utf8'))
                                except:
                                        pass
                                else:
                                        ndel += 1
                                        in_fs.remove(f)

                in_db = [(f, filename_to_postid[f]) for f in in_db]
                if in_db or in_fs:
                        orphans.append((board, in_db, in_fs))

        return ndel, orphans

@acl(0)
def a_orphans(user, board, form):
        ndel, orphans = do_stuff_with_orphans((board and [board] or map(Board, [n for n, t in user.get_authorized_boards()])))
        io.serve_template('orphans', template='admin', header='Orphan Check', user=user, orphans=orphans)

@acl(0)
def s_orphans(user, board, form):
        do_delete = (form.action == 'delete')
        ndel, orphans = do_stuff_with_orphans((board and [board] or map(Board, [n for n, t in user.get_authorized_boards()])), do_delete)
        io.serve_template('message', template='admin', header='Orphan Check', user=user, board=board,
                message='%d orphan%s%s deleted.' % (
                        ndel, ["s", ""][ndel == 1], ["", " NOT"][not do_delete]
                ))


get = globals().get
