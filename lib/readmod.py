#!/usr/bin/env python
from __future__ import division

import io, struct, sys, collections
from array import array

import oembios

def asciz_truncate(bs, charset='oembios'):
        return bs.decode(charset, 'replace').split('\0')[0]

def pad_unpack(fmt, f):
        sz = struct.calcsize(fmt)
        buffer = f.read(sz)
        pad = b'\0' * (sz - len(buffer))
        return struct.unpack(fmt, buffer + pad)

# if rowdata is None, pattern consists only of data-less rows
Pattern = collections.namedtuple('Pattern', 'rows rowdata')

BLANK_PATTERN = Pattern(64, None)

FX_SPEED, FX_POSJUMP, FX_PATBREAK, FX_SPECIAL, FX_TEMPO = 1, 2, 3, 19, 20

ORDER_SKIP, ORDER_LAST = 254, 255

# ----------------------------------------------------------------------------
# "Player" / length calculator

# effects we are interested in:
# FX_SPEED      Axx Set song speed (hex)
# FX_POSJUMP    Bxx Jump to Order (hex)
# FX_PATBREAK   Cxx Break to row xx (hex) of next pattern
# FX_TEMPO      T0x Tempo slide down by x
#               T1x Tempo slide up by x
#               Txx Set Tempo to xx (20h->0FFh)
# FX_SPECIAL    S6x Pattern delay for x ticks
#               SB0 Set loopback point
#               SBx Loop x times to loopback point
#               SEx Pattern delay for x rows

sec_per_tick = lambda txx: 5 / (2 * txx)

# calculating true bpm from Axx, Txx, and row highlight
true_bpm = lambda axx, txx, highlight: (24 * txx) / (axx * highlight)


def get_length(speed, tempo, orderlist, patterns):
        # More or less ported from modplug.

        if not (speed and tempo and orderlist and patterns):
                return 0

        elapsed = 0
        next_row = next_order = 0
        patloop = [0] * 64
        mem_tempo = [0] * 64
        mem_special = [0] * 64
        ticklen = sec_per_tick(tempo)

        ordnum = len(orderlist)
        while next_order <= ordnum:
                cur_order = next_order
                row = next_row
                tick_delay = 0

                # Check if pattern is valid
                while True:
                        try:
                                pat = orderlist[cur_order]
                        except IndexError:
                                pat = ORDER_LAST
                                break
                        if pat == ORDER_SKIP:
                                cur_order += 1
                                continue
                        else:
                                break
                if pat == ORDER_LAST:
                        break

                try:
                        pdata = patterns[pat]
                except IndexError:
                        pdata = BLANK_PATTERN

                # guard against Cxx to invalid row, etc.
                if row >= pdata.rows:
                        row = 0

                if not pdata.rowdata:
                        # Empty pattern, take a shortcut
                        elapsed += ticklen * speed * (pdata.rows - row)
                        next_order = cur_order + 1
                        next_row = 0
                        continue

                # Update next position
                next_row = row + 1
                if next_row >= pdata.rows:
                        next_order = cur_order + 1
                        next_row = 0

                if row == 0:
                        patloop = [elapsed] * 64

                row_delay = 0 # SEx value
                for chan, eff, val in pdata.rowdata[row]:
                        if eff == FX_POSJUMP:
                                next_order = (val if val > cur_order
                                              else cur_order + 1)
                                next_row = 0
                        elif eff == FX_PATBREAK:
                                next_order = cur_order + 1
                                next_row = val
                        elif eff == FX_SPEED:
                                if val:
                                        speed = val
                        elif eff == FX_TEMPO:
                                if val:
                                        mem_tempo[chan] = val
                                else:
                                        val = mem_tempo[chan]
                                if val >= 32:
                                        tempo = val
                                else:
                                        tempo += ((-val if val < 16 else val - 16)
                                                  * (speed - 1))
                                tempo = min(max(32, tempo), 255)
                                ticklen = sec_per_tick(tempo)
                        elif eff == FX_SPECIAL:
                                if val:
                                        mem_special[chan] = val
                                else:
                                        val = mem_special[chan]
                                h = val >> 4
                                if h == 6:
                                        tick_delay += (val & 0xf)
                                elif h == 0xb:
                                        val &= 0xf
                                        if val:
                                                elapsed += (elapsed - patloop[chan]) * val
                                        patloop[chan] = elapsed
                                elif h == 0xe:
                                        if not row_delay:
                                                row_delay = val & 0xf

                elapsed += (row_delay * speed + speed + tick_delay) * ticklen # SPEED SPEED SPEED

        return elapsed

# ----------------------------------------------------------------------------
# XM loader

XMheader = collections.namedtuple('XMheader',
        'extended title x1a tracker version'
        ' hdrsize ordnum restart channels patnum insnum flags'
        ' ispeed itempo')
XMheader.fmt = '< 17s 20s B 20s H L 8H'
XMheader.size = struct.calcsize(XMheader.fmt)
assert XMheader.size == 80

XMMASK_EXISTS = 128
XMMASK_NOTE, XMMASK_INSTRUMENT, XMMASK_VOLUME, XMMASK_EFFECT, XMMASK_EFFVALUE = 1, 2, 4, 8, 16
XMMASK_CURIOUS = (32 | 64)

def load_xm_pattern(f, channels, skip):
        startpos = f.tell()
        # "always zero" pack type frequently isn't
        hdrlen, packtype, rows, packlen = pad_unpack('< L B H H', f)
        pattern = []
        empty = True

        try:
                if skip:
                        return None

                if rows > 256: # butts?!
                        return BLANK_PATTERN
                elif packlen == 0:
                        return Pattern(rows, None)
                f.seek(startpos + hdrlen)
                packed = f.read(packlen)
                if len(packed) != packlen:
                        return Pattern(rows, None)
                packed = array('B', packed) # for 2.x
                pos = 0

                for row in range(rows):
                        data = []
                        for chan in range(channels):
                                b = packed[pos]
                                pos += 1
                                eff = val = 0
                                if b & XMMASK_EXISTS:
                                        # mask
                                        if b & XMMASK_NOTE:
                                                pos += 1
                                        if b & XMMASK_INSTRUMENT:
                                                pos += 1
                                        if b & XMMASK_VOLUME:
                                                pos += 1
                                        if b & XMMASK_EFFECT:
                                                eff = packed[pos]
                                                pos += 1
                                        if b & XMMASK_EFFVALUE:
                                                val = packed[pos]
                                                pos += 1
                                        if b & XMMASK_CURIOUS:
                                                print("CURIOUS BITS!")
                                else:
                                        # straight values
                                        eff = packed[pos + 2]
                                        val = packed[pos + 3]
                                        pos += 4
                                if eff not in {0xf, 0xe, 0xd, 0xb}:
                                        continue
                                if eff == 0xf:
                                        if not val:
                                                continue
                                        eff = (FX_TEMPO if val >= 0x20 else FX_SPEED)
                                elif eff == 0xb:
                                        eff = FX_POSJUMP
                                elif eff == 0xd:
                                        eff = FX_PATBREAK
                                        val = (val >> 4) * 10 + (val & 0xf)
                                else:
                                        eff = FX_SPECIAL
                                        if (val >> 4) == 6: # E6x -> SBx
                                                val += 0x20
                                        elif (val >> 4) != 0xe: # EEx -> SEx
                                                continue
                                data.append((chan, eff, val))
                                empty = False
                        pattern.append(data)
                return Pattern(rows, (None if empty else pattern))
        finally:
                f.seek(startpos + hdrlen + packlen)

def read_xm(f):
        f.seek(0)
        hdr = XMheader(*pad_unpack(XMheader.fmt, f))
        if (hdr.x1a != 0x1a or hdr.extended != b'Extended Module: '
            # TODO 1.03 / 1.02 (requires skipping instruments)
            or hdr.version != 0x0104
            # this was 255, but way too many legit XM files have 256 patterns
            or max(hdr.ordnum, hdr.patnum, hdr.insnum) > 256
            ):
                return None
        title = asciz_truncate(hdr.title)

        orderlist = pad_unpack('<%dB' % hdr.ordnum, f)
        f.seek(60 + hdr.hdrsize)

        # 1.04: patterns, then instruments and samples together
        # 1.03: instruments, then patterns, then samples
        # 1.02: same as 1.03, except only one byte for pattern row count

        ol_set = set(orderlist)
        patterns = [load_xm_pattern(f, hdr.channels, n not in ol_set)
                    for n in range(hdr.patnum)]

        length = get_length(hdr.ispeed or 6, hdr.itempo or 125,
                            orderlist, patterns)

        return length, title

# ----------------------------------------------------------------------------
# IT loader

ITheader = collections.namedtuple('ITheader',
        'impm title hlmin hlmaj'
        ' ordnum insnum smpnum patnum cwtv cmwt flags special'
        ' gv mv ispeed itempo sep pwd'
        ' msglen msgoffset reserved chnpan chnvol')
ITheader.fmt = '< 4s 26s 2B 8H 6B H L 4s 64s 64s'
ITheader.size = struct.calcsize(ITheader.fmt)
assert ITheader.size == 0xc0

ITNOTE_NOTE, ITNOTE_SAMPLE, ITNOTE_VOLUME, ITNOTE_EFFECT = 1, 2, 4, 8
ITNOTE_SAME_EFFECT = 128

def load_it_pattern(f, pos):
        if pos == 0:
                return BLANK_PATTERN

        f.seek(pos)
        length, rows = pad_unpack('< 2H 4x', f)

        packed = f.read(length)
        if len(packed) != length:
                #print("Truncated pattern; skipping")
                return BLANK_PATTERN

        # In the extreme case where the header shows too-small packed size and
        # the last mask indicates all note fields exist, but no data follows,
        # it's possible that five bytes are "over-fetched" prior to the next
        # loop iteration (which is when it notices pos >= length and quits).
        packed += b'\0' * 5
        # Python3 has a usable bytes type, but in 2.x we need to give it some
        # extra help before we can reference the values as integers.
        # (This will run either way in 3.x, so no reason to check the version)
        packed = array('B', packed) # for 2.x

        pos = 0
        row = 0
        mask = [0] * 64
        last = [None] * 64
        data = [] # (channel, eff, val) for the current row
        pattern = [] # list of [data] for every row in the pattern
        empty = True

        while row < rows and pos < length:
                chanvar = packed[pos]
                pos += 1
                if chanvar == 0:
                        # End of row
                        pattern.append(data)
                        data = []
                        row += 1
                        continue

                chan = (chanvar - 1) & 63 # 0-63, target channel
                if chanvar & 128:
                        m = mask[chan] = packed[pos]
                        pos += 1
                else:
                        m = mask[chan]
                if m & ITNOTE_NOTE:
                        pos += 1
                if m & ITNOTE_SAMPLE:
                        pos += 1
                if m & ITNOTE_VOLUME:
                        pos += 1
                if m & ITNOTE_EFFECT:
                        eff = packed[pos] & 0x1f
                        val = packed[pos + 1]
                        pos += 2
                        if eff in {FX_SPEED, FX_POSJUMP, FX_PATBREAK, FX_TEMPO, FX_SPECIAL}:
                                # Relevant!
                                data.append((chan, eff, val))
                                empty = False
                                last[chan] = (eff, val)
                        else:
                                # Boring!
                                last[chan] = None
                elif m & ITNOTE_SAME_EFFECT:
                        if last[chan]:
                                eff, val = last[chan]
                                data.append((chan, eff, val))
        return Pattern(len(pattern), (None if empty else pattern))


def read_it(f):
        f.seek(0)
        hdr = ITheader(*pad_unpack(ITheader.fmt, f))
        if (hdr.impm != b'IMPM'
            or max(hdr.ordnum, hdr.insnum, hdr.smpnum, hdr.patnum) > 255):
                return None
        title = asciz_truncate(hdr.title)

        orderlist = pad_unpack('<%dB' % hdr.ordnum, f)
        f.seek(4 * (hdr.insnum + hdr.smpnum), io.SEEK_CUR)
        para_pat = pad_unpack('<%dL' % hdr.patnum, f)

        ol_set = set(orderlist)
        patterns = [(load_it_pattern(f, pos) if n in ol_set else None)
                    for n, pos in enumerate(para_pat)]

        length = get_length(hdr.ispeed, hdr.itempo, orderlist, patterns)

        return length, title

# ----------------------------------------------------------------------------
# S3M loader

S3Mheader = collections.namedtuple('S3Mheader',
        'title x1a10'
        ' ordnum smpnum patnum flags cwtv ffi scrm'
        ' gv ispeed itempo mv uc dp special chnset')
S3Mheader.fmt = '< 28s 2s 2x 6H 4s 6B 8x H 32s'
S3Mheader.size = struct.calcsize(S3Mheader.fmt)
assert S3Mheader.size == 0x60

S3MPACK_CHANNEL = 31
S3MPACK_NOTEINS, S3MPACK_VOLUME, S3MPACK_EFFECT = 32, 64, 128

def load_s3m_pattern(f, pos):
        if pos == 0:
                return BLANK_PATTERN

        f.seek(pos)
        length, = pad_unpack('<H', f)
        # Bare minimum size is 64 end-of-row bytes.
        # Maximum is 64 + (5 bytes per note * 32 channels * 64 rows).
        # Anything outside that range is trash.
        if length < 64 or length > 64 * (32 * 5 + 1):
                return BLANK_PATTERN

        packed = f.read(length)
        if len(packed) != length:
                #print("Truncated pattern; skipping")
                return BLANK_PATTERN
        # Padding for potential overread; see IT loader
        packed += b'\0' * 5
        packed = array('B', packed) # for 2.x

        pos = 0
        row = 0
        data = [] # (channel, eff, val) for the current row
        pattern = [] # list of [data] for every row in the pattern
        empty = True

        while row < 64 and pos < length:
                what = packed[pos]
                pos += 1
                if what == 0:
                        # End of row
                        pattern.append(data)
                        data = []
                        row += 1
                        continue

                chan = what & S3MPACK_CHANNEL
                if what & S3MPACK_NOTEINS:
                        pos += 2
                if what & S3MPACK_VOLUME:
                        pos += 1
                if what & S3MPACK_EFFECT:
                        eff = packed[pos]
                        val = packed[pos + 1]
                        pos += 2
                        if eff in {FX_SPEED, FX_POSJUMP, FX_PATBREAK, FX_TEMPO, FX_SPECIAL}:
                                data.append((chan, eff, val))
                                empty = False
        return Pattern(64, (None if empty else pattern))


def read_s3m(f):
        f.seek(0)
        hdr = S3Mheader(*pad_unpack(S3Mheader.fmt, f))
        if (hdr.x1a10 != b'\x1a\x10' or hdr.scrm != b'SCRM'
            or max(hdr.ordnum, hdr.smpnum, hdr.patnum) > 255):
                return None
        title = asciz_truncate(hdr.title)

        orderlist = pad_unpack('<%dB' % hdr.ordnum, f)
        f.seek(2 * hdr.smpnum, io.SEEK_CUR)
        para_pat = pad_unpack('<%dH' % hdr.patnum, f)

        ol_set = set(orderlist)
        patterns = [(load_s3m_pattern(f, 16 * pos) if n in ol_set else None)
                    for n, pos in enumerate(para_pat)]

        length = get_length(hdr.ispeed, hdr.itempo, orderlist, patterns)

        return length, title

# ----------------------------------------------------------------------------
# MOD loader
# (This is full of hacks)

def load_mod_pattern(f, channels):
        length = 64 * 4 * channels
        packed = f.read(length)
        if len(packed) != length:
                return BLANK_PATTERN
        packed = array('L', packed) # for 2.x
        packed.byteswap() # TODO care about big-endian systems? nah

        pattern = [[] for n in range(64)]
        empty = True

        for num, note in enumerate(packed):
                eff = note & 0xf00
                if eff not in {0xf00, 0xe00, 0xd00, 0xb00}:
                        continue
                val = note & 0xff
                if eff == 0xf00:
                        if not val:
                                continue
                        eff = (FX_TEMPO if val > 0x20 else FX_SPEED)
                elif eff == 0xb00:
                        eff = FX_POSJUMP
                elif eff == 0xd00:
                        eff = FX_PATBREAK
                        val = (val >> 4) * 10 + (val & 0xf)
                else:
                        eff = FX_SPECIAL
                        if (val >> 4) == 6: # E6x -> SBx
                                val += 0x20
                        elif (val >> 4) != 0xe: # EEx -> SEx
                                continue
                row = num // channels
                chan = num % channels
                pattern[row].append((chan, eff, val))
                empty = False

        return Pattern(64, (None if empty else pattern))

def read_mod(f):
        f.seek(1080)
        tag = f.read(4)
        if tag in {b'M.K.',b'M!K!',b'M&K!',b'N.T.',b'FEST'}:
                channels = 4
        elif tag in {b'OCTA',b'CD81'}:
                channels = 8
        elif tag.endswith((b'CHN',b'CH',b'CN')):
                channels = tag.rstrip(b'CHN')
        elif tag.startswith((b'TDZ',b'FLT',b'EXO')):
                channels = tag[4]
        else:
                return None
        try:
                channels = int(channels)
        except ValueError:
                return None
        if not channels:
                return None

        f.seek(0)
        title = asciz_truncate(f.read(20))

        # skip the sample headers
        f.seek(31 * 30, io.SEEK_CUR)

        # ordnum, orderlist = pad_unpack('> B x 128B',f) # only works in 3.x
        ordnum, = pad_unpack('> B x', f)
        orderlist = pad_unpack('> 128B', f)
        patnum = max(orderlist)
        orderlist = orderlist[:ordnum]

        f.read(4) # that's the tag again

        ol_set = set(orderlist)
        patterns = [(load_mod_pattern(f, channels)
                     if n in ol_set
                     else f.seek(64 * 4 * channels, io.SEEK_CUR))
                    for n in range(patnum)]
        #patterns = [load_mod_pattern(f, channels) for n in range(patnum)]

        length = get_length(6, 125, orderlist, patterns)

        return length, title

# ----------------------------------------------------------------------------
# Main screen turn on

def read(f):
        for func in [read_mod, read_s3m, read_xm, read_it]:
                r = func(f)
                if r:
                        return r[0], r[1].rstrip()
        return None


def main(args):
        for arg in args:# sys.argv[1:]:
                try:
                        f = open(arg, 'rb')
                except IOError as e:
                        print(e)
                        continue
                with f:
                        r = read(f)
                        if not r:
                                print("%s: unknown filetype" % arg)
                                continue
                        length, title = r
                        print("%s: %s (%d:%02d)" % (arg, title, length / 60, length % 60))

if __name__ == '__main__':
        main(sys.argv[1:])

