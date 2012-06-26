WARC to ZIP service
===================

This is a small web-based tool that converts WARC files to ZIP files.

Usage:

    http://warctozip.herokuapp.com/<url to warc.gz>

Maybe the WARC file is part of a larger file: (the server must support HTTP Range requests)

    http://warctozip.herokuapp.com/<byte range>/<url to warc.gz>

A ZIP filename can be specified if you don't like the default:

    http://warctozip.herokuapp.com/<zip filename>/<url to warc.gz>
    http://warctozip.herokuapp.com/<byte range>/<zip filename>/<url to warc.gz>

Examples:

    http://warctozip.herokuapp.com/https://github.com/downloads/alard/warc-proxy/picplz-00454713-20120603-143400.warc.gz
    http://warctozip.herokuapp.com/example.zip/https://github.com/downloads/alard/warc-proxy/picplz-00454713-20120603-143400.warc.gz
    http://warctozip.herokuapp.com/30573088768-30573890406/http://archive.org/download/mobileme-hero-1335023445/mobileme-full-1335023445.tar
    http://warctozip.herokuapp.com/30573088768-30573890406/homepage.mac.com-jcarias.zip/http://archive.org/download/mobileme-hero-1335023445/mobileme-full-1335023445.tar

