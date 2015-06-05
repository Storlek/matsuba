import os, tempfile

class SafeWriter(object):
        """Cleaner substitute for mucking about with NamedTemporaryFile or other stuff in tempfile directly.
        (2015 note: this is probably not actually Safe, but it's still far safer than just opening the target
        file directly which is what I was doing before I wrote this)"""
        # cache these to avoid errors. see tempfile.py for details.
        link = os.link
        unlink = os.unlink

        def __init__(self, *components):
                """Components are concatenated with os.path.join."""
                # need to make sure that the temp file is on the same fs as the target file so link() can
                # work. putting it in the target file's directory guarantees this.
                f = os.path.join(*components)
                self.filename = f
                fd, self.tempname = tempfile.mkstemp(dir=os.path.dirname(f))
                # mode/bufsize are args to TemporaryFile/NamedTemporaryFile but I don't care here
                self.file = os.fdopen(fd, 'w+b', -1)

        def chmod(self, mode):
                try:
                        os.chmod(self.tempname, mode)
                except:
                        pass
                try:
                        os.chmod(self.filename, mode)
                except:
                        pass

        # kopipe from tempfile.py
        # mirror any attributes that don't exist, and copy non-primitives
        def __getattr__(self, name):
                f = self.__dict__['file']
                a = getattr(f, name)
                if type(a) != type(0):
                        setattr(self, name, a)
                return a

        def close(self):
                self.close = lambda: None
                try:
                        self.unlink(self.filename)
                except:
                        pass
                self.link(self.tempname, self.filename)
                self.file.close()
                self.unlink(self.tempname)

        def __del__(self):
                self.close()
