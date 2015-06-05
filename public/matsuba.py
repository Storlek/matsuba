#!/usr/bin/env python2

# you might want this for testing; DON'T enable it for production
#import cgitb;cgitb.enable()

# Maybe set a time zone?
#import time, os
#os.environ['TZ'] = 'America/New_York'
#time.tzset()

import sys
sys.path.insert(0, '/home/you/matsuba/lib')

import matsuba.config, matsuba.io, matsuba.processor


# you should probably do this, and set a sensible filename
import logging
logging.basicConfig(
        filename=matsuba.config.PRIVATE_FSPATH + '/matsuba.log',
        level=logging.INFO,
        format='%(asctime)s:%(levelname)s:%(funcName)s:%(message)s',
)

# If you want multiple subdomains with separate configurations, but
# still keep one sitewide installation, you can do a trick like this:
#matsuba.config.__dict__.update(dict(
#SITE_BASEURL = 'http://someothersite.com',
#SITE_FSPATH = '/home/you/public_html',
#CSS_FSPATH = '/home/you/public_html/css',
#...etc...
#SITE_TITLE = 'Totally different site',
#BOARD_LIST = u'[with / its / own / board / links]',
#))


# pass off execution to the main processor
matsuba.processor.cgi_main()
