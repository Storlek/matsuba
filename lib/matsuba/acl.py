import matsuba.config as cfg
from matsuba.errors import NoPermissionError
import extutil

# Access-control verbs for user_boards.authority.

# 2015 NOTE: I honestly don't remember if this ever completely worked, or if
# maybe I was in the midst of rewriting a previous system and got distracted
# by something. From the last database backup I have, I'd granted all mods
# full admin rights, and now I don't remember why.


ACL_SETFLAGS    = 1 # toggle thread flags -- sticky, permasage, hidden, closed
ACL_DELETE      = 2 # delete file, post, or thread
ACL_BAN         = 4 # ban, unban, permaban, view ban list
ACL_MODPOST     = 8 # make a raw-html post, use capcodes
ACL_FILTER      = 16 # wordfilters (ideally this should also require modpost)
ACL_CONFIGURE   = 32 # change board settings (anon name, ID, template, etc.)
ACL_VIEWIP      = 64 # see posters' IP addresses (not generally necessary)
ACL_MOVEPOST    = 128 # relocate a post to a new thread or board
ACL_EDITSTYLE   = 256 # change the inline html/css includes, and text strings
ACL_FILEMAN     = 512 # manipulate shared files such as title banners, etc.

ACL_ALL_PRIVS   = 0x7fffffff # all existing AND FUTURE controls

# make this something that's impossible to get from the above
ACL_ANY = -1


def acl_check(user, board, flags):
        if not user:
                return False
        user_acl = user.get_acl(board)
        if flags == ACL_ANY:
                return user_acl != 0
        else:
                return ((user_acl & flags) == flags)

# decorator
def acl(flags):
        def wrap(f):
                def decorated(user, board, form):
                        if acl_check(user, board, flags):
                                return f(user, board, form)
                        elif user is None:
                                extutil.http_redirect(cfg.SITE_BASEURL + cfg.MATSUBA_PATH + '?task=login')
                        else:
                                raise NoPermissionError
                return decorated
        return wrap

