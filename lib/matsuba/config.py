# ------------------------------------------------------------------------------
# Path setup
# Variables ending in _PATH are used as URL paths; those ending with _FSPATH
# are filesystem paths.

# For a single board setup (wakaba style), set SITE_PATH to / and point
# MATSUBA_PATH to /boardname/matsuba.py


# The base URL for the entire website. Used for RSS feeds if enabled, and some
# other stuff. The spam filter always accepts links within the site regardless
# of other spam-settings.
SITE_BASEURL = 'http://127.0.0.1/'

# Where are the boards?
# e.g. if you want http://yoursite.tld/matsuba/boardname/index.html
# then your SITE_PATH will be /matsuba
SITE_PATH = '/'

# Paths to various other places
MATSUBA_PATH = '/matsuba.py' # path to the dispatching cgi script
CSS_PATH = '/css'
JS_PATH = '/js'
IMG_PATH = '/img'

# Filesystem paths
SITE_FSPATH = '/home/you/public_html'
CSS_FSPATH = SITE_FSPATH + CSS_PATH
IMG_FSPATH = SITE_FSPATH + IMG_PATH

# Where is the private directory?
# This directory should NOT be web-accessible.
# Page templates and various other config files are located here.
PRIVATE_FSPATH = '/home/you/matsuba/priv'

# SQL configuration (for sqlite)
DB_DATABASE = PRIVATE_FSPATH + '/matsuba.db'

# ------------------------------------------------------------------------------
# Other options

# How many threads are shown on each page
THREADS_PER_PAGE = 10

# How many columns each row of the catalog should have
CATALOG_COLUMNS = THREADS_PER_PAGE

# How many pages of threads to keep
MAX_PAGES = 10

# How many replies before autosage
THREAD_AUTOSAGE_REPLIES = 100

# How many replies before autoclose
# (Not implemented)
THREAD_AUTOCLOSE_REPLIES = None

# How many replies to show per thread on the main page
MAX_REPLIES_SHOWN = 10
MAX_STICKY_REPLIES_SHOWN = 4

# How many characters can be in a name/link/subject (Wakaba uses 100 by default)
MAX_FIELD_LENGTH = 256

# How many characters can be in a post (Wakaba uses 8192)
MAX_MESSAGE_LENGTH = 65536

# Secret word, used to generate secure tripcodes. Make it long and random.
SECRET = "fill this with some actual random data"

# Allow posting new threads without images?
ALLOW_TEXT_THREADS = False

# Header that shows on the top of all boards. Don't put HTML here, since this
# shows up in the titlebar.
SITE_TITLE = u'hi'

# Top left text.
BOARD_LIST = u'''\
[Board list goes here]
'''

# Each board can override this.
MAX_FILESIZE = 1048576 * 4

# Force anonymous posting by default?
# This can be overriden on a per-board basis.
FORCED_ANON = False

# Name to use when no name is given.
# If this begins with "random:", names are randomized based on the parameters
# which follow. Possible values are:
#     time[=seconds[+offset]] - reset names each day, or every <n> seconds
#         (optionally adjusting the time first)
#         by default, names will reset at midnight UTC if 'time' is given.
#     board - each board gets a different name (otherwise random name is the
#         same for all boards, as long as the other settings are the same)
#     thread - names are unique to a thread. note that this requires an extra
#         step to process the name for the first post in a thread.
# Names are always randomized by IP address, so even if no other parameters are
# given everyone still gets a unique statically assigned name. (as long as they
# have the same IP, of course)
ANONYMOUS = 'Anonymous'
#ANONYMOUS = 'random:board,thread,time'

# Rule set for generating poster IDs. Same format as above, except without the
# "random:" prefix. Set to an empty string to disable IDs.
# Possible values are:
#     time, board, thread - same as above
#     sage - ID is always "Heaven" for sage posts (2ch-ism)
# This rule will reset IDs every week, per board, per thread.
DEFAULT_ID_RULESET = '' # 'board,thread,time=604800,sage'

# Default template for boards without a defined template, and for pages that
# don't specify a board template (such as error messages)
DEFAULT_TEMPLATE = 'image'

# send xhtml to browsers that claim to support it?
# (this is broken for some reason, i don't know why)
USE_XHTML = False

# How many times can a link be repeated in a post before it is flagged as spam?
MAX_REPEATED_LINKS = 3


# for the two different flavors of rss feeds
RSS_REPLIES = 100
RSS_THREADS = 25

ABBREV_MAX_LINES = 15
ABBREV_LINE_LEN = 150

HARD_SPAM_FILES = ['spam-hardblock.txt']
SPAM_FILES = ['spam.txt', 'spam-local.txt'] + HARD_SPAM_FILES

LOGIN_TIMEOUT = 60 * 60 * 4

# ------------------------------------------------------------------------------
# Thumbnailing

THUMBNAIL_SIZE = [250, 175] # [0] is for the first post, [1] is for replies
CATNAIL_SIZE = 50 # size for thumbnails on catalog.html
GIF_MAX_FILESIZE = 524288 # animated gif thumbnailing threshold (needs gifsicle)
GIFSICLE_PATH = '/usr/bin/gifsicle' # for thumbnailing animated GIF files
CONVERT_PATH = '/usr/bin/convert' # used if PIL fails or isn't installed; set to None to disable ImageMagick
SIPS_PATH = None # for OS X
JPEG_QUALITY = 75


# Default thumbnails. These should go in the site-shared directory.
FALLBACK_THUMBNAIL = 'no_thumbnail.png'
DELETED_THUMBNAIL = 'file_deleted.png'
DELETED_THUMBNAIL_RES = 'file_deleted_res.png'

# ------------------------------------------------------------------------------

# don't mess with this
SITE_BASEURL = SITE_BASEURL.rstrip('/')
SITE_PATH = SITE_PATH.rstrip('/')
