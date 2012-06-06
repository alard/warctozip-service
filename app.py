import os
import os.path
import re
import requests
from zipfile import ZipFile, ZipInfo
from hanzo.warctools import ArchiveRecord, WarcRecord
from hanzo.httptools import RequestMessage, ResponseMessage

class ResponseAsFile(object):
  def __init__(self, url, bytes_range=None):
    headers = { }
    if bytes_range:
      headers["Range"] = "bytes="+bytes_range

    self.url = url
    self.response = requests.get(url, headers=headers)
    self.iter_content = self.response.iter_content(chunk_size=1024)
    self.offset = 0
    self.chunks = [( 0, "" )]

  def name(self):
    return os.path.basename(re.sub(r"\?.*$", "", self.url))

  def read(self, size):
    result = ""
    chunk_index = 0
    while size > 0:
      if chunk_index == len(self.chunks):
        self.read_chunk()

      if self.chunks[chunk_index] == None:
        raise RuntimeError("End of file!")

      chunk = self.chunks[chunk_index]
      relative_offset = self.offset - chunk[0]
      bytes_in_current = min(size, len(chunk[1]) - relative_offset)
      if bytes_in_current > 0:
        result += chunk[1][relative_offset : relative_offset+bytes_in_current]
        self.offset += bytes_in_current
        size -= bytes_in_current

      if size > 0:
        chunk_index += 1

    if len(self.chunks) > 2:
      del self.chunks[0:len(self.chunks)-2]

    return result

  def read_chunk(self):
    last_chunk = self.chunks[-1]
    if last_chunk:
      next_chunk = self.iter_content.next()
      if next_chunk:
        chunk_offset = last_chunk[0] + len(last_chunk[1])
        self.chunks.append(( chunk_offset, next_chunk ))
      else:
        self.chunks.append(None)

  def tell(self):
    return self.offset

  def seek(self, offset, whence=None):
    if whence == os.SEEK_CUR:
      self.offset += offset
    else:
      raise RuntimeError("Unsupported seek with whence=" + str(whence))

    if self.offset < self.chunks[0][0]:
      raise RuntimeError("Seek too far back.")

class FileToIter(object):
  def __init__(self):
    self.offset = 0
    pass

  def tell(self):
    return self.offset

  def write(self, data):
    self.offset += len(data)

  def flush(self):
    pass

  def close(self):
    print "Close at "+str(self.offset)

class WarcToZip(object):
  def __init__(self, url, bytes_range=None):
    self.archive = WarcRecord.open_archive(file_handle=ResponseAsFile(url, bytes_range))

    self.files = []
    self.errors = []

    self.offset = 0
    self.buffer = []

  def tell(self):
    return self.offset

  def write(self, data):
    self.offset += len(data)
    self.buffer.append(data)

  def flush(self):
    pass

  def iter_zip(self):
    with ZipFile(self, "w") as outzip:
      for (offset, record, errors) in self.archive.read_records(limit=None):
        if record and record.type == WarcRecord.RESPONSE and record.content[0] == ResponseMessage.CONTENT_TYPE:
          message = ResponseMessage(RequestMessage())
          leftover = message.feed(record.content[1])
          message.close()

          filename = re.sub(r'^https?://', '', record.url)
          date_time = record.date
          date_time = (int(date_time[0:4]), int(date_time[5:7]), int(date_time[8:10]),
                       int(date_time[11:13]), int(date_time[14:16]), int(date_time[17:19]))

          info = ZipInfo(filename, date_time)
          outzip.writestr(info, message.get_body())
          self.files.append(record.url)

          for chunk in self.buffer:
            yield(chunk)
          self.buffer = []

        elif errors:
          self.errors.append("warc errors at %s:%d"%(name, offset if offset else 0))
          for e in errors:
            self.errors.append(e)

      outzip.writestr("files.txt", "\n".join(self.files))
      if len(self.errors) > 0:
        outzip.writestr("errors.txt", "\n".join(self.errors))

    for chunk in self.buffer:
      yield(chunk)

    self.buffer = []


def app(environ, start_response):
  if environ["PATH_INFO"]=="/":
    data = """Experimental WARC to ZIP converter.

Usage:
  http://"""+environ["SERVER_NAME"]+"""/<url to warc.gz>

Maybe the WARC file is part of a larger file:
  http://"""+environ["SERVER_NAME"]+"""/<byte range>/<url to warc.gz>
(the server must support HTTP Range requests)

A ZIP filename can be specified if you don't like the default:
  http://"""+environ["SERVER_NAME"]+"""/<zip filename>/<url to warc.gz>
  http://"""+environ["SERVER_NAME"]+"""/<byte range>/<zip filename>/<url to warc.gz>

Examples:
  http://"""+environ["SERVER_NAME"]+"""/https://github.com/downloads/alard/warc-proxy/picplz-00454713-20120603-143400.warc.gz
  http://"""+environ["SERVER_NAME"]+"""/example.zip/https://github.com/downloads/alard/warc-proxy/picplz-00454713-20120603-143400.warc.gz
  http://"""+environ["SERVER_NAME"]+"""/30573088768-30573890406/http://archive.org/download/mobileme-hero-1335023445/mobileme-full-1335023445.tar
  http://"""+environ["SERVER_NAME"]+"""/30573088768-30573890406/homepage.mac.com-jcarias.zip/http://archive.org/download/mobileme-hero-1335023445/mobileme-full-1335023445.tar

"""
    start_response("200 OK", [
      ("Content-Type", "text/plain"),
      ("Content-Length", len(data))
    ])
    return iter([data])

  m = re.match(r"^/(?:([0-9]+-[0-9]+)/)?(?:([^/:]+)/)?(https?://.+)$", environ["PATH_INFO"])
  if m:
    bytes_range = m.groups()[0]
    zip_filename = m.groups()[1]
    url = m.groups()[2]

    if zip_filename == None:
      zip_filename = re.sub(r"\.warc(\.gz)?$", "", os.path.basename(re.sub(r"\?.*$", "", url))) + ".zip"

    w = WarcToZip(url, bytes_range)
    start_response("200 OK", [
      ("Content-Type", "application/zip"),
      ("Content-Disposition", "attachment; filename="+zip_filename)
    ])
    return w.iter_zip()
  else:
    data = "Not a valid URL."
    start_response("404 Not Found", [
      ("Content-Type", "text/plain"),
      ("Content-Length", len(data))
    ])
    return iter([data])

