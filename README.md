![logo](https://gitlab.com/cipres/levior/-/raw/master/media/img/levior-256.png)

> *Pāpiliō levior est ave* (The butterfly is lighter than the bird)

*levior* (latin word meaning *lighter*) is a web (HTTP/HTTPs) to Gemini proxy.
It converts web pages on-the-fly to
the [gemtext](https://gemini.circumlunar.space/docs/gemtext.gmi) format,
allowing you to browse regular web pages with any Gemini browser without having
to suffer the heavyness associated with certain technologies of the modern web.

*levior* can either run as a gemini server with special "endpoints" that
will render the requested web page as gemtext and rewrite gemini URLs to be
routed through the levior service (this mode will work with
all gemini browsers), or as a transparent http proxy that renders the
web pages as gemtext without rewriting URLs (in this mode you will need
to use a Gemini browser that supports using proxies).
See [the usage section](#usage) below for more info on the different service
modes.

*levior* also supports serving other types of content, like ZIM files (the
archive format used by Wikipedia), making it possible to browse complete wikis
through Gemini ([see the config file](https://gitlab.com/cipres/levior/-/raw/master/examples/levior.zim.yaml)).

# Donate

If you want to support this project, you can
[make a donation here](https://ko-fi.com/cipres).

# AppImage

Get the [latest AppImage here](https://gitlab.com/cipres/levior/-/releases/continuous-master/downloads/levior-latest-x86_64.AppImage):

```sh
curl -L -o levior https://gitlab.com/cipres/levior/-/releases/continuous-master/downloads/levior-latest-x86_64.AppImage
chmod +x levior
./levior
```

# Manual Install

```sh
pip install -e .
```

For zim or uvloop support, install the extra requirements:

```sh
pip install -e '.[zim]'
pip install -e '.[uvloop]'
```

# Usage

*levior* can be configured from the command-line or via a *YAML* config file.
See [the example config file](https://gitlab.com/cipres/levior/-/raw/master/examples/levior.yaml). URL rules can only be configured with a config file.

```sh
levior
levior -c config.yaml
```

Socks5 proxies are supported with **--socks5-proxy**. **--tor**
will use the default socks5 proxy address for Tor (*socks5://localhost:9050*).

```sh
levior --socks5-proxy "socks5://localhost:9050"
levior --tor
```

## Service modes

*levior* can run in two different modes:

- *server* (default): run as a gemini server. When you visit the root gemini URL
  you'll be asked for a web domain to browse via a gemini input request
  (you can also simply go to *gemini://localhost/{domain}* in your Gemini
  browser).  The URLs in the HTML pages are rewritten to be routed to the levior
  gemini URL. **This mode is compatible with any Gemini browser.**

- *http-proxy*: in this mode, *levior* acts as a proxy for http and https URLs
  and serves pages without rewriting URLs. **To use this mode, you need a
  Gemini browser that supports http proxies** (here's a short list of them:
  Lagrange, Amfora, diohsc and Telescope)

The mode can be set with the **--mode** command-line argument or with the *mode*
setting in the config file. Use **--mode=http-proxy** or **--mode=proxy** to
run as a transparent http proxy.

## Links

The **--links** option controls the Gemini links generation mode (this is
an *md2gemini* option):

- **paragraph** (this is the default): This will result in footnotes being added to the document, and the links for each footnote being added at the end of each paragraph
- **copy**: Like **paragraph**, but without footnotes
- **at-end**: The links are added at the very end of the document
- **off**: Remove all links

```sh
levior --links=at-end
levior --links=off
```

Open your Gemini browser and go to *gemini://localhost* or *//localhost*.

## Mounting ZIM images

You can also mount ZIM files to be served via the gemini protocol. Once you've configured
a ZIM mountpoint, go to *gemini://localhost/{mountpoint}* (for example:
*gemini://localhost/wiki_en*). A great source of ZIM archives is the
[kiwix library](https://library.kiwix.org).

It's possible to run searches on the ZIM archive's contents. Go to
*gemini://localhost/{mountpoint}/search*
(for example: *gemini://localhost/wiki_en/search*), where you'll be prompted
for a search query (by default there's a limit of 4096 results, this can be
changed via the *search_results_max* option). The *search_path* option
sets the URL path of the search API:

```yaml
mount:
  /wiki_en:
    type: zim
    path: ./wikipedia_en_all_mini_2022-03.zim
    search_path: /
    search_results_max: 8192
```

See the [example config file here](https://gitlab.com/cipres/levior/-/raw/master/examples/levior.zim.yaml).

## URLs

### /

When accessing */*, you'll be prompted for a domain name to browse.

### /{domain}

When accessing */{domain}*, *levior* will proxy *https://domain* to the
Gemini browser. Examples:

```sh
gemini://localhost/searx.be
gemini://localhost/gitlab.com/cipres/levior
```

### /search

When accessing */search*, you'll be prompted for a search query. Your search
will be performed via the *searx* search engine.
