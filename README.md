Overview
--------

Matsuba is an imageboard - a forum nominally centered around discussion of
images. Most "traditional" imageboards derive in spirit from the Japanese
website [Futaba Channel][], and are generally stylistically lightweight with
few features and a strong value on anonymity. As such, there are no user
profiles, post counts, or any of the other trappings of typical forum software.

While interest in imageboards has declined, the mid-2000s saw a burgeoning
community of boards large and small, for all manner of niche topics. Likewise,
there arose heaps of imageboard scripts. Most were terrible, or offered little
of added value over their predecessors. Matsuba tries not to be.

Matsuba's imageboard and text discussion styles are based respectively on
[Wakaba and Kareha][], two Perl scripts written by !WAHa.06x36. These are in
turn successors to the Japanese Futaba Channel and [Ni-channel][] -- again,
respectively.

[Futaba Channel]: http://www.2chan.net/
[Wakaba and Kareha]: http://wakaba.c3.cx/
[Ni-channel]: http://2ch.net/


Features
--------

Plenty!

* Automatic banner rotation
* Support for multiple boards in one installation
* Many options configurable on a per-board basis, including output
    template (imageboard, textboard, etc.)
* Catalog and thread list overview for each board
* RSS feeds
* Generates static files: blazing fast page response with light CPU load
* Support for many file types, including audio files (even extracts title
    and cover art from metadata tags in MP3 and MP4 files)
* Animated GIF thumbnails
* Transparent GIF and PNG thumbnails
* Robust, flexible text formatting, based on [Markdown][]
* Syntax highlighting for source code snippets
* Cross-board reply links (`>>>/a/1234`)
* Inter-thread links on text boards using thread-relative post numbering
    (for example, `>>7` will link to the seventh post in the same thread,
    whereas `>>/1234/7` links to the seventh post in thread 1234)
* Forced indentation of code
* Advanced anti-spam system, including remote URL downloading to apply
    spam filter checks to linked pages
* No CAPTCHA support whatsoever
* Post count-based permasage, with override ability
* Sticky threads
* Highly advanced, regular-expression based word filters
* Flexible anonymous name generator, similar to Wakaba, extended with a
    domain-specific language to define the context-free grammar
* `noko` support to stay in thread after submitting a post
* Proper support for 2ch `fusianasan` and `mokorikomo` in name field
* "Aborn" message when deleting posts in text board mode
* Customizable thread trimming
* A wide selection of stylesheets
* Customizable bans: per board or sitewide, expiring or permanent
* Practically no administrative panel whatsoever; hope you like SQL
* **100% UNMAINTAINED AND UNSUPPORTED!**

[Markdown]: daringfireball.net/projects/markdown/


Dependencies
------------

Not much!

* Python 2.x (might run with Python 3 using 2to3; untested)
* [mako](http://www.makotemplates.org/)
* [pygments](http://pygments.org/)
* a web server which supports CGI (*not* FastCGI) and URL rewriting
* an understanding of both SQL and Python -- you *will* be getting your hands
  hands dirty here!
* lots of time on your hands for both configuration and moderation


Installation
------------

I make absolutely no guarantee that this will even actually work. Important
files might be missing. There might be blatant errors preventing anything from
functioning. Best of luck if you actually want to make use of this.

Put everything under `public/` somewhere viewable via the web. The other
directories, `priv/` and `lib/`, should *not* be publically accessible.
`matsuba.py` is the entry point, and in a typical setup, should be marked
executable.

Have a look at `lib/matsuba/config.py` and also `matsuba.py` for settings to
configure for your local installation. If you have used Wakaba, some of the
variable names will sound vaguely familiar.

You will also need to set up some internal URL-rewriting rules. Assuming you
are hosting your boards directly under the site root, do something like this:

    /([^/]+)/read/([0-9]+)/*$            =>  /$1/$2.html
    /([^/]+)/read/l50/*$                 =>  /$1/res/$2_l50.html
    /([^/]+)/read/([0-9A-Za-z/_,-]+)/*$  =>  /matsuba.py?board=$1&read=$2
    /([^/]+)/src/([^/]+)/thread          =>  /matsuba.py?board=$1&srcfind=$2

Finally, you will need to initialize the database. Matsuba uses sqlite3, so
`sqlite3 priv/matsuba.db < matsuba.sql` will make some tables.

Matsuba offers no GUI for managing users, setting up boards, or doing
virtually anything you might want to do besides the most basic moderation
tasks. Get familiar with that schema!

There *used* to be an interface for handling some of these things via the web
admin panel as well as on the terminal, but it gradually fell out of sync with
the rest of the code until it was functionally useless.


License
-------

Matsuba is free software; you can modify and/or redistribute it under the
terms of the Artistic License. Please read through COPYING in the distribution
before using or sharing this code in any way.


Contact
-------

Storlek <storlek@rigelseven.com>

<http://rigelseven.com/>

Twitter: [@SwedishForSize](https://twitter.com/SwedishForSize)
