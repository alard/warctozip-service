import os
import os.path
import re
import cgi
import tempfile
import requests
from zipfile import ZipFile, ZipInfo
from hanzo.warctools import ArchiveRecord, WarcRecord
from hanzo.httptools import RequestMessage, ResponseMessage

from stream_post import multipart_iter_content

def response_as_file(url, bytes_range=None):
  headers = { }
  if bytes_range:
    headers["Range"] = "bytes="+bytes_range

  response = requests.get(url, headers=headers)
  iter_content = response.iter_content(chunk_size=4096)
  name = os.path.basename(re.sub(r"\?.*$", "", url))

  return IterContentAsFile(name, iter_content)

def stream_as_file(name, io):
  def iter_content():
    b = io.read(4096)
    while b:
      yield b
      b = io.read(4096)

  return IterContentAsFile(name, iter_content())

class IterContentAsFile(object):
  def __init__(self, name, iter_content):
    self.name = name
    self.iter_content = iter_content
    self.offset = 0
    self.chunks = [( 0, "" )]

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
      if next_chunk != None:
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
  def __init__(self, url_or_io, bytes_range=None):
    if isinstance(url_or_io, str):
      self.archive = WarcRecord.open_archive(file_handle=response_as_file(url_or_io, bytes_range))
    elif isinstance(url_or_io, IterContentAsFile):
      self.archive = WarcRecord.open_archive(file_handle=url_or_io)
    else:
      self.archive = WarcRecord.open_archive(file_handle=stream_as_file("upload.warc.gz", url_or_io))

    self.path_types = {}

    self.files = {}
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

  def url_to_filename(self, url):
    """ Map url to a unique file name/path. Register the directories in the path. """
    filename = re.sub(r'^https?://', '', url)
    filename = os.path.normpath(filename)
    
    path = []
    path_parts = filename.split("/")

    for idx, part in enumerate(path_parts):
      tries = 0
      unique_part = part
      new_path = "/".join(path + [part])

      while new_path in self.path_types and (self.path_types[new_path] == "file" or len(path_parts)-1 == idx):
        tries += 1
        unique_part = "%s.%d" % (part, tries)
        new_path = "/".join(path + [unique_part])

      if len(path_parts)-1 == idx:
        self.path_types[new_path] = "file"
      else:
        self.path_types[new_path] = "dir"

      path.append(unique_part)

    return "/".join(path)

  def iter_zip(self):
    with ZipFile(self, "w") as outzip:
      for (offset, record, errors) in self.archive.read_records(limit=None):
        if record and record.type == WarcRecord.RESPONSE and re.sub(r'\s+', '', record.content[0]) == ResponseMessage.CONTENT_TYPE:
          message = ResponseMessage(RequestMessage())
          leftover = message.feed(record.content[1])
          message.close()

          filename = self.url_to_filename(record.url)
          date_time = record.date
          date_time = (int(date_time[0:4]), int(date_time[5:7]), int(date_time[8:10]),
                       int(date_time[11:13]), int(date_time[14:16]), int(date_time[17:19]))

          info = ZipInfo(filename, date_time)
          outzip.writestr(info, message.get_body())
          self.files[filename] = record.url

          for chunk in self.buffer:
            yield(chunk)
          self.buffer = []

        elif errors:
          self.errors.append("warc errors at %s:%d"%(name, offset if offset else 0))
          for e in errors:
            self.errors.append(e)

      outzip.writestr("files.txt", "\n".join([ "%s -> %s" % (v,k) for k,v in self.files.iteritems() ]))
      if len(self.errors) > 0:
        outzip.writestr("errors.txt", "\n".join(self.errors))

    for chunk in self.buffer:
      yield(chunk)

    self.buffer = []


def app(environ, start_response):
  if environ["REQUEST_METHOD"]=="POST":
    if "CONTENT_TYPE" in environ and re.match("multipart/", environ["CONTENT_TYPE"]):
      boundary = re.search(r"boundary=(\S+)", environ["CONTENT_TYPE"]).group(1)

      m = re.match(r"^/([^/:]+)$", environ["PATH_INFO"])
      if m:
        zip_filename = m.groups()[1]
      else:
        zip_filename = "warc.zip"
      
      tmp = tempfile.TemporaryFile(suffix="warctozip")
      d = environ["wsgi.input"].read()
      while d:
        tmp.write(d)
        d = environ["wsgi.input"].read()
      tmp.seek(0)

      # form POST
      w = WarcToZip(IterContentAsFile("input.warc.gz", multipart_iter_content(tmp, boundary)))
      start_response("200 OK", [
        ("Content-Type", "application/zip"),
        ("Content-Disposition", "attachment; filename="+zip_filename)
      ])
      return w.iter_zip()

    else:
      # raw POST
      zip_filename = "warc.zip"
      w = WarcToZip(environ["wsgi.input"])
      start_response("200 OK", [
        ("Content-Type", "application/zip"),
        ("Content-Disposition", "attachment; filename="+zip_filename)
      ])
      return w.iter_zip()

  if environ["PATH_INFO"]=="/":
    data = """<!DOCTYPE html><html><body><pre>
<strong>Experimental WARC to ZIP converter.</strong>

This conversion service converts .warc.gz to .zip files.
You can use it in several ways:

<strong>1. Create a WARC-to-ZIP download link.</strong>

You specify the HTTP location of the WARC and the conversion parameters. 

Usage:
  http://"""+environ["SERVER_NAME"]+"""/&lt;url to warc.gz&gt;

Maybe the WARC file is part of a larger file:
  http://"""+environ["SERVER_NAME"]+"""/&lt;byte range&gt;/&lt;url to warc.gz&gt;
(the server must support HTTP Range requests)

A ZIP filename can be specified if you don't like the default:
  http://"""+environ["SERVER_NAME"]+"""/&lt;zip filename&gt;/&lt;url to warc.gz&gt;
  http://"""+environ["SERVER_NAME"]+"""/&lt;byte range&gt;/&lt;zip filename&gt;/&lt;url to warc.gz&gt;

Examples:
  http://"""+environ["SERVER_NAME"]+"""/https://github.com/downloads/alard/warc-proxy/picplz-00454713-20120603-143400.warc.gz
  http://"""+environ["SERVER_NAME"]+"""/example.zip/https://github.com/downloads/alard/warc-proxy/picplz-00454713-20120603-143400.warc.gz
  http://"""+environ["SERVER_NAME"]+"""/30573088768-30573890406/http://archive.org/download/mobileme-hero-1335023445/mobileme-full-1335023445.tar
  http://"""+environ["SERVER_NAME"]+"""/30573088768-30573890406/homepage.mac.com-jcarias.zip/http://archive.org/download/mobileme-hero-1335023445/mobileme-full-1335023445.tar


<strong>2. Send the data via an HTTP POST request.</strong>

Use Curl or another download tool to upload your WARC. The service responds
with a ZIP version of the contents.

Usage:
  curl -d @your.warc.gz http://"""+environ["SERVER_NAME"]+"""/ > your.zip


<strong>3. Create a multipart file upload form.</strong>

Create an upload form that POSTs a WARC file to http://"""+environ["SERVER_NAME"]+"""/. You'll get a ZIP file back.

Usage:
  &lt;form method=&quot;post&quot; enctype=&quot;multipart/form-data&quot; action=&quot;http://"""+environ["SERVER_NAME"]+"""/&quot;&gt;
    &lt;input type=&quot;file&quot; name=&quot;warc&quot; /&gt;
    &lt;input type=&quot;submit&quot; value=&quot;Convert&quot; /&gt;
  &lt;/form&gt;

You can specify the file name of the ZIP file in the URL:
  http://"""+environ["SERVER_NAME"]+"""/&lt;zip filename&gt;

Example:
</pre>

<form method="post" enctype="multipart/form-data" action="http://"""+environ["SERVER_NAME"]+"""/">
  <p><input type="file" name="warc" /> <input type="submit" value="Convert"></p>
</form>

</body></html>
"""
    start_response("200 OK", [
      ("Content-Type", "text/html"),
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

