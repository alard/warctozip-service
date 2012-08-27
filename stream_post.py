import mimetools
import re
import email.parser

class LineReader(object):
    def __init__(self, fp):
        self.fp = fp
        self.data = ""

    def readline(self, size=None):
        if self.data == None:
            return None
        pos = self.data.find("\n")
        if pos == -1:
            more_data = self.fp.read(size)
        else:
            more_data = None
        while more_data:
            self.data += more_data
            pos = self.data.find("\n")
            if pos == -1:
                if size and len(self.data) >= size:
                    self.data = ""
                    return self.data
                more_data = self.fp.read(4096)
            else:
                more_data = None
        if pos == -1:
            line = self.data
            self.data = None
        else:
            line = self.data[:pos+1]
            self.data = self.data[pos+1:]
        return line


def multipart_iter_content(fp, boundary):
    # Contains a few lines from Python's cgi.py.
    nextpart = "--" + boundary
    lastpart = "--" + boundary + "--"
    partdict = {}
    terminator = ""

    fp = LineReader(fp)

    while terminator != lastpart:
        is_file = False
        if terminator:
            # At start of next part.  Read headers first.
            headers = mimetools.Message(fp)
            clength = headers.getheader('content-length')
            line = headers.getheader('content-disposition')
            if line and re.search(r'filename=".+warc\.gz"', line):
                is_file = True
            bytes = 0
            if clength:
                try:
                    bytes = int(clength)
                except ValueError:
                    pass
            if bytes > 0:
                if maxlen and bytes > maxlen:
                    raise ValueError, 'Maximum content length exceeded'
                offset = 0
                while offset < bytes:
                  data = fp.read(min(bytes - offset, 4096))
                  if is_file:
                      yield data
                  offset += 4096
        # Read lines until end of part.
        data = []
        data_len = 0
        while 1:
            line = fp.readline(4096)
            if not line:
                terminator = lastpart # End outer loop
                break
            if line[:2] == "--":
                terminator = line.strip()
                if terminator in (nextpart, lastpart):
                    break
            if is_file:
                data.append(line)
                data_len += len(line)
                if data_len > 4096:
                    yield "".join(data)
                    data = []
                    data_len = 0
        if data_len > 0:
            yield "".join(data)

        # Done with part.
    yield ""

