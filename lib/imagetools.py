import os, struct, subprocess, tempfile
import logging # this module just uses logging.debug(), which is hidden by default


from extutil import strip_illegal_unicode
from matsuba.errors import *

# Probably want to alter these. Hopefully something is in the path.
GIF_MAX_FILESIZE = None
GIFSICLE_PATH = None
CONVERT_PATH = 'convert'
SIPS_PATH = 'sips'
JPEG_QUALITY = 70

# --------------------------------------------------------------------------------------------------------------
# image analysis (from wakaba)

def _analyze_jpeg(f):
        f.seek(0)
        buf = f.read(2)
        if buf != '\xff\xd8': return None
        while True: # outer
                while buf != '\xff':
                        buf = f.read(1)
                        if buf == '': return None
                buf = f.read(3)
                if len(buf) < 3: return None
                mark, size = struct.unpack('>BH', buf)
                if mark in (0xda, 0xd9): return None
                if size < 2: raise FileTypeError, "Possible virus in image" # MS GDI+ JPEG exploit uses short chunks
                if mark >= 0xc0 and mark <= 0xc2: # SOF0..SOF2 - what the hell are the rest?
                        buf = f.read(5)
                        if len(buf) < 5: return None
                        bits, height, width = struct.unpack('>BHH', buf)
                        return 'jpg', width, height
                f.seek(size - 2, 1)
        # never get here

def _analyze_png(f):
        """APNG identification from Popcorn Mariachi !9i78bPeIxI"""
        f.seek(0)
        buf = f.read(24)
        if len(buf) < 24: return None
        magic1, magic2, length, ihdr, width, height = struct.unpack('>6L', buf)
        if magic1 != 0x89504e47L or magic2 != 0x0d0a1a0aL or ihdr != 0x49484452L:
                return None
        f.seek(8)
        while True:
                buf = f.read(8)
                if len(buf) < 8:
                        break
                length, tag = struct.unpack('>L4s', buf)
                if tag in ('IDAT', 'IEND'):
                        break
                elif tag == 'acTL':
                        return 'apng', width, height
                f.seek(length + 4, 1)

        return 'png', width, height

def _analyze_gif(f):
        f.seek(0)
        buf = f.read(10)
        if len(buf) < 10: return None
        magic, width, height = struct.unpack('<6shh', buf)
        if magic in ('GIF87a', 'GIF89a'): return 'gif', width, height
        return None

def analyze_image(f):
        if not hasattr(f, 'seek'):
                # it's a string?
                f = file(f, 'rb')
        return _analyze_jpeg(f) or _analyze_png(f) or _analyze_gif(f)

# --------------------------------------------------------------------------------------------------------------
# thumbnailers
# These are split into two classes:
# - Thumbnailers, which do actual scaling work.
# - Extractors, which are capable of pulling image data from other types of
#   files, and pass these onto the thumbnailers. The MP3/MP4 thumbnailers
#   are examples of this.
# Extractors are tried first, then thumbnailers.

class ThumbnailTypeError(Exception): pass # thumbnailer couldn't handle the file
_thumbnailers = []
_tnextractors = []


def _gif_thumbnail(fileobj, filename, thumbnail, thumbsize, extrainfo):
        """Animated GIF thumbnails. This also uses PIL if available to make sure the image is actually
        an animated GIF first.
        """
        if not (GIFSICLE_PATH and GIF_MAX_FILESIZE > 0):
                raise ThumbnailTypeError, 'gifsicle not configured'

        fileobj.seek(0, 2)
        if fileobj.tell() > GIF_MAX_FILESIZE:
                raise ThumbnailTypeError, 'too big'
        # PIL is slightly smarter, since it can catch non-animated gif files
        try:
                import Image
        except:
                # XXX this breaks
                fileobj.seek(0)
                gif, w, h = _analyze_gif(fileobj)
                if gif != 'gif':
                        raise ThumbnailTypeError, 'not a gif'
        else:
                fileobj.seek(0)
                try:
                        i = Image.open(fileobj)
                except:
                        raise ThumbnailTypeError, 'PIL died'
                #if 'duration' not in i.info:
                #       raise ThumbnailTypeError, 'not animated'
                try:
                        i.seek(1)
                except:
                        raise ThumbnailTypeError, 'not animated'
                else:
                        i.seek(0)
                w, h = i.size
        # don't bother doing "optimizations" like copy the file if it's smaller than thumbsize!
        # gifsicle is pretty fast, and it usually can produce a smaller file anyway.
        if w > thumbsize: w, h = thumbsize, h * thumbsize / w
        if h > thumbsize: w, h = w * thumbsize / h, thumbsize
        try:
                subprocess.call((
                        GIFSICLE_PATH, '-O2', '--resize', '%dx%d' % (w, h), filename,
                        '-o', thumbnail + '.gif'
                        ), stdout=file(os.devnull, 'w'), stderr=subprocess.STDOUT)
        except OSError:
                raise ThumbnailTypeError, "gifsicle failed"
        extrainfo.append('animated')
        return 'gif', w, h
_thumbnailers.append(_gif_thumbnail)


# 2015 note: I don't know if this still works now, but it worked in 2006
#try:    from CoreGraphics import *
#except: pass
#else:
#        def _cg_thumbnail(fileobj, filename, thumbnail, thumbsize, extrainfo):
#                """OS X CoreGraphics thumbnail. Blazing fast."""
#                if os.path.splitext(filename)[1].lower() in ('.jpg', '.jpeg'):
#                        # apparently this is faster for jpegs
#                        orig = CGImageCreateWithJPEGDataProvider(CGDataProviderCreateWithFilename(filename),
#                                                                 [0, 1, 0, 1, 0, 1], 1, kCGRenderingIntentDefault)
#                        tn_type, format = 'jpg', kCGImageFormatJPEG
#                else:
#                        orig = CGImageImport(CGDataProviderCreateWithFilename(filename))
#                        tn_type, format = 'png', kCGImageFormatPNG
#                w, h = orig.getWidth(), orig.getHeight()
#                if w > thumbsize: w, h = thumbsize, h * thumbsize / w
#                if h > thumbsize: w, h = w * thumbsize / h, thumbsize
#                cs = CGColorSpaceCreateDeviceRGB()
#                c = CGBitmapContextCreateWithColor(w, h, cs, (0, 0, 0, 0))
#                c.setInterpolationQuality(kCGInterpolationHigh)
#                c.drawImage(CGRectMake(0, 0, w, h), orig)
#                c.writeToFile(thumbnail, format)
#                return tn_type, w, h
#        _thumbnailers.append(_cg_thumbnail)

# 2015 note: same
# this is lightning fast, but some people complained about the quality
# personally idgaf, it looks fine to me
#try:    import Image
#except: pass
#else:
#        def _pil_thumbnail(fileobj, filename, thumbnail, thumbsize, extrainfo):
#                """PIL thumbnailing. Fast, but needs PIL (obviously), and interlaced PNGs don't work."""
#                try: # PIL throws lots of errors
#                        fileobj.seek(0) # stupid PIL.
#                        i = Image.open(fileobj)
#                        options = {'optimize': True, 'quality': JPEG_QUALITY}
#                        tn_type = 'jpg'
#                        if i.mode == 'RGBA':
#                                tn_type = 'png'
#                        elif 'transparency' in i.info:
#                                # Only bother saving it as png if it is in fact transparent somewhere.
#                                t = i.info['transparency']
#                                for tup in i.getcolors():
#                                        if tup[1] == t:
#                                                options['transparency'] = t
#                                                tn_type = 'png'
#                                                break
#                        if tn_type == 'jpg' and i.mode not in ('1', 'L', 'RGB', 'RGBA', 'RGBX', 'CMYK', 'YCbCr'):
#                                i = i.convert('RGB') # barbecue cakes
#                        try:
#                                i.seek(1)
#                        except:
#                                pass
#                        else:
#                                i.seek(0)
#                                extrainfo.append('animated')
#                        if i.size[0] <= thumbsize and i.size[1] <= thumbsize:
#                                # don't make the thumbnail bigger
#                                i.thumbnail(i.size)
#                        else:
#                                i.thumbnail((thumbsize, thumbsize))
#                        i.save(thumbnail + '.' + tn_type, **options)
#                        return tn_type, i.size[0], i.size[1]
#                except: raise ThumbnailTypeError
#        _thumbnailers.append(_pil_thumbnail)


def _im_thumbnail(fileobj, filename, thumbnail, thumbsize, extrainfo):
        """ImageMagick thumbnail. This should be a last resort."""
        if not CONVERT_PATH:
                raise ThumbnailTypeError, 'path to convert not set'

        if filename.lower().endswith('.gif'):
                filename += '[0]'
                tn_type = 'png' # to allow for transparent parts
        elif filename.lower().endswith('.png'):
                tn_type = 'png'
        else:
                tn_type = 'jpg'
        try:
                if subprocess.call((CONVERT_PATH, '-resize', '%dx%d>' % (thumbsize, thumbsize),
                                    '-quality', str(JPEG_QUALITY), filename, thumbnail + '.' + tn_type),
                                   stdout=file(os.devnull, 'w'), stderr=subprocess.STDOUT) != 0:
                        raise OSError, "whatever"
        except OSError: # convert not found or didn't work
                logging.debug('imagemagick failed.')
                raise ThumbnailTypeError, "ImageMagick thumbnail failed"
        #extrainfo.append('imagemagick')
        return tn_type, 0, 0
_thumbnailers.append(_im_thumbnail)



#def _sips_thumbnail(fileobj, filename, thumbnail, thumbsize, extrainfo):
#        """OS X thumbnailer that runs SIPS in a subshell. Not terribly reliable with png/gif files.
#        ImageMagick isn't installed on OS X by default, though, so..."""
#        if not SIPS_PATH:
#                raise ThumbnailTypeError, 'path to sips not defined'
#
#        if filename.lower()[-4:] in ('.gif', '.png'):
#                tn_type = format = 'png' # to allow for transparent pixels
#        else:
#                tn_type, format = 'jpg', 'jpeg'
#        thumbnail += '.' + tn_type
#        # sips prints lots of garbage to stdout and doesn't return
#        # a useful error code, so just see if it made a file
#        try:
#                subprocess.call((SIPS_PATH, '-Z', str(thumbsize), '-s', 'format', format, '--out',
#                        thumbnail, filename), stdout=file(os.devnull, 'w'), stderr=subprocess.STDOUT)
#        except OSError: pass # no sips?
#        if not os.path.exists(thumbnail):
#                raise ThumbnailTypeError, "sips thumbnail failed"
#        #extrainfo.append('sips')
#        return tn_type, 0, 0
#_thumbnailers.append(_sips_thumbnail)

try:    from mutagen.mp4 import MP4
except: pass
else:
        def _mp4_thumbnail(fileobj, filename, thumbnail, thumbsize, extrainfo):
                """Thumbnail from cover art for MP4 files."""
                try:
                        mp4 = MP4(filename)
                except Exception, e:
                        logging.debug('%s is not an mp4 (%r)' % (filename, e))
                        raise ThumbnailTypeError

                # Don't allow itunes-protected files. They won't play anywhere anyway.
                if 'purd' in mp4 or 'apID' in mp4:
                        logging.debug('%s has DRM' % filename)
                        raise FileTypeError

                extrainfo.append('%d:%02d' % (mp4.info.length / 60, int(mp4.info.length) % 60))

                a = mp4.get(b'\xa9ART'); a = strip_illegal_unicode(a[0] if a else '')
                t = mp4.get(b'\xa9nam'); t = strip_illegal_unicode(t[0] if t else '')
                if a and t:     extrainfo.append(u'%s / %s' % (a, t))
                elif t:         extrainfo.append(t)
                if t:           extrainfo[0] = None

                if 'covr' not in mp4:
                        return (None, 0, 0)
                tf = tempfile.NamedTemporaryFile()
                tf.write(mp4['covr'][0])
                tf.flush()
                return make_thumbnail(tf.name, thumbnail, thumbsize, fileobj=tf.file, info=extrainfo,
                        allow_extract=False, allow_anim=False)
        _tnextractors.append(_mp4_thumbnail)

try:    from mutagen.mp3 import MP3
except: pass
else:
        def _id3_thumbnail(fileobj, filename, thumbnail, thumbsize, extrainfo):
                """Thumbnail from APIC tag frame of ID3 header in MP3 files. BBQ."""
                try:
                        mp3 = MP3(filename)
                except Exception, e:
                        logging.debug('%s is not an mp3 (%r)' % (filename, e))
                        raise ThumbnailTypeError
                if mp3.info.sketchy:
                        # this catches a bunch of garbage (such as some jpgs or whatever)
                        logging.debug('%s is maybe not an mp3, playing it safe' % filename)
                        raise ThumbnailTypeError

                extrainfo.append('%d:%02d' % (mp3.info.length / 60, int(mp3.info.length) % 60))

                a = mp3.get('TPE1'); a = strip_illegal_unicode(a[0] if a else '')
                t = mp3.get('TIT2'); t = strip_illegal_unicode(t[0] if t else '')
                if a and t:     extrainfo.append(u'%s / %s' % (a, t))
                elif t:         extrainfo.append(t)
                if t:           extrainfo[0] = None # delete the original filename

                apic = mp3.get('APIC:')
                if not apic: # no pic tag
                        return (None, 0, 0)
                tf = tempfile.NamedTemporaryFile()
                tf.write(apic.data)
                tf.flush()
                return make_thumbnail(tf.name, thumbnail, thumbsize, fileobj=tf.file, info=extrainfo,
                        allow_extract=False, allow_anim=False)
        _tnextractors.append(_id3_thumbnail)

try:    from mutagen.oggvorbis import OggVorbis
except: pass
else:
        def _ogg_thumbnail(fileobj, filename, thumbnail, thumbsize, extrainfo):
                """Artist/title extractor for Ogg Vorbis. No actual thumbnailing happening here."""
                try:
                        ogg = OggVorbis(filename)
                except Exception, e:
                        logging.debug('%s is not an ogg (%r)' % (filename, e))
                        raise ThumbnailTypeError

                extrainfo.append('%d:%02d' % (ogg.info.length / 60, int(ogg.info.length) % 60))

                a = ogg.get('artist'); a = strip_illegal_unicode(a[0] if a else '')
                t = ogg.get('title');  t = strip_illegal_unicode(t[0] if t else '')
                if a and t:     extrainfo.append(u'%s / %s' % (a, t))
                elif t:         extrainfo.append(t)
                if t:           extrainfo[0] = None # delete the original filename

                # does ogg even do images?
                return (None, 0, 0)
        _tnextractors.append(_ogg_thumbnail)

try:    import readmod
except: pass
else:
        def _tracker_thumbnail(fileobj, filename, thumbnail, thumbsize, extrainfo):
                r = readmod.read(fileobj)
                if not r:
                        raise ThumbnailTypeError
                length, title = r
                extrainfo.append('%d:%02d' % (length / 60, int(length) % 60))
                if title:
                        extrainfo.append(title)
                        extrainfo[0] = None
                # none of these formats can embed images (well, not sanely :)
                return (None, 0, 0)
        _tnextractors.append(_tracker_thumbnail)


# --------------------------------------------------------------------------------------------------------------

def make_thumbnail(filename, thumbnail, thumbsize, fileobj=None, info=None, allow_extract=True, allow_anim=False, check_blacklist=False):
        """Create a thumbnail.

        tl;dr usage:
                thumbnail = os.path.splitext(filename)[0] + '_thumb'
                tn_type, tn_width, tn_height = make_thumbnail(filename, thumbnail, 200)
                thumbnail += '.' + tn_type

        'thumbnail' should NOT contain an extension. The full path to the thumbnail after creation will be
        (thumbnail + '.' + tn_type).

        If this fails, tn_type will be None.

        If tn_width == 0, run the thumbnail through analyze_image to get its size if necessary.

        If defined, 'info' should be a list containing at least one item, the original filename. This may be
        modified by the thumbnailer if it finds something more interesting or useful. (e.g. artist/title info
        for an MP3 file) Other items may be appended to this list, such as "animated". This is all entirely up
        to the particular function that made the thumbnail.

        fileobj should be None or a file()-like structure; in particular, it needs seek(), tell(), and read().
        Not all thumbnailers will use the file object; not all will use the name."""

        if not fileobj:
                fileobj = open(filename, 'rb')
        if not info:
                info = [None]

        if allow_extract:
                funcs = (_thumbnailers + _tnextractors)
        else:
                funcs = _thumbnailers[:]
        if not allow_anim:
                try:    funcs.remove(_gif_thumbnail)
                except: pass
        logging.debug('thumbnailing %r using %r' % (filename, [f.__name__ for f in funcs]))
        for func in funcs:
                try:
                        r = func(fileobj, filename, thumbnail, thumbsize, info)
                except (ImportError, ThumbnailTypeError), e:
                        pass
                else:
                        logging.debug('%r: %r gave us %r' % (filename, func.__name__, r))
                        return r
        logging.debug('%r: thumbfail' % filename)
        return (None, 0, 0)


# all of this stuff doesn't belong here, but here it is because it was easier
class BlacklistError(Exception):
        pass

import re, struct, zlib, sys
def check_blacklist_swf(filename):
        infile = open(filename, 'rb')
        sig, x_size = struct.unpack('3s5s', infile.read(8))
        chunks = ['FWS', x_size]
        if sig == 'CWS':
                d = zlib.decompressobj()
                chunks.append(d.decompress(infile.read()))
                chunks.append(d.flush())
        else:
                chunks.append(infile.read())
        data = ''.join(chunks)
        # 2015 note: I don't know?????
        if '2012tehnicidesalvare' in data:
                raise BlacklistError("Malicious SWF file")

try:
        import Image, ImageOps, ImageFilter, math, operator, sys
except:
        def imgscan(f):
                return (0, None)
        def imgdiff(f1, f2):
                return None
        def check_blacklist(filename):
                if filename.lower().endswith('.swf'):
                        check_blacklist_swf(filename)
else:
        def imgscan(f):
                i = Image.open(f)
                # Reasonably small, but still big enough to preserve detail.
                # This way transforms don't take too long on big images.
                i.thumbnail((300, 300))
                if i.mode != "RGB":
                        i = i.convert("RGB")
                i = i.filter(ImageFilter.EDGE_ENHANCE_MORE) # CSI
                w, h = i.size
                hist = i.histogram()
                return (float(w) / float(h), hist)
        def imgdiff(scan1, scan2):
                a1, h1 = scan1
                a2, h2 = scan2
                return ((1 + abs(a1 - a2)) * math.sqrt(reduce(operator.add,
                        map(lambda i, j: (i - j) ** 2, h1, h2)) / len(h1)))

        def check_blacklist(filename):
                if filename.lower().endswith('.swf'):
                        return check_blacklist_swf(filename)
                try:
                        scan1 = imgscan(filename)
                except:
                        return
                for mindelta, file2 in [
                        # (file list trimmed)
                ]:
                        try:
                                scan2 = imgscan(file2)
                        except:
                                continue
                        delta = imgdiff(scan1, scan2)
                        if delta < 250:
                                raise BlacklistError("Image is blacklisted")

