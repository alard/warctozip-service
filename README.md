Experimental WARC to ZIP converter.
===================================

This conversion service converts .warc.gz to .zip files.
You can use it in several ways:

1. Create a WARC-to-ZIP download link.
--------------------------------------

You specify the HTTP location of the WARC and the conversion parameters. 

Usage:

    http://warctozip.archive.org/<url to warc.gz>

Maybe the WARC file is part of a larger file:

    http://warctozip.archive.org/<byte range>/<url to warc.gz>

(the server must support HTTP Range requests)

A ZIP filename can be specified if you don't like the default:

    http://warctozip.archive.org/<zip filename>/<url to warc.gz>
    http://warctozip.archive.org/<byte range>/<zip filename>/<url to warc.gz>

To link to WARC records within a larger file, without converting to ZIP:

    http://warctozip.archive.org/<byte range>/<warc filename>/<url to warc.gz>

(the server must support HTTP Range requests)

Examples:

    http://warctozip.archive.org/https://github.com/downloads/alard/warc-proxy/picplz-00454713-20120603-143400.warc.gz
    http://warctozip.archive.org/example.zip/https://github.com/downloads/alard/warc-proxy/picplz-00454713-20120603-143400.warc.gz
    http://warctozip.archive.org/30573088768-30573890406/http://archive.org/download/mobileme-hero-1335023445/mobileme-full-1335023445.tar
    http://warctozip.archive.org/30573088768-30573890406/homepage.mac.com-jcarias.zip/http://archive.org/download/mobileme-hero-1335023445/mobileme-full-1335023445.tar
    http://warctozip.archive.org/30573088768-30573890406/homepage.mac.com-jcarias.warc.gz/http://archive.org/download/mobileme-hero-1335023445/mobileme-full-1335023445.tar


2. Send the data via an HTTP POST request.
--------------------------------------

Use Curl or another download tool to upload your WARC. The service responds
with a ZIP version of the contents.

Usage:

    curl -d @your.warc.gz http://warctozip.archive.org/ > your.zip


3. Create a multipart file upload form.
--------------------------------------

Create an upload form that POSTs a WARC file to http://warctozip.archive.org/. You'll get a ZIP file back.

Usage:

    <form method="post" enctype="multipart/form-data" action="http://warctozip.archive.org/">
      <input type="file" name="warc" />
      <input type="submit" value="Convert" />
    </form>

You can specify the file name of the ZIP file in the URL:

    http://warctozip.archive.org/<zip filename>

