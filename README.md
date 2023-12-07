![logo](https://gitlab.com/cipres/levior/-/raw/master/media/img/levior-256.png)

> *Pāpiliō levior est ave* (The butterfly is lighter than the bird)

*levior* (latin word meaning *lighter*) is a web (HTTP/HTTPs) to Gemini proxy.
It converts web pages on-the-fly to
the [gemtext](https://geminiprotocol.net/docs/gemtext.gmi) format,
allowing you to browse regular web pages with any Gemini browser without having
to suffer the heavyness associated with certain technologies of the modern web.

*levior* supports Javascript rendering and can therefore be used to browse
dynamic websites.

*levior* also supports serving other types of content, like ZIM files (the
archive format used by Wikipedia), making it possible to browse complete wikis
through Gemini ([see the config file](https://gitlab.com/cipres/levior/-/raw/master/examples/levior.zim.yaml)).

# Donate

If you want to support this project, you can
[make a donation here](https://ko-fi.com/cipres).

# AppImage

Get the [latest AppImage here](https://gitlab.com/cipres/levior/-/releases/continuous-master/downloads/levior-latest-x86_64.AppImage):

```sh
curl -L -o levior.AppImage https://gitlab.com/cipres/levior/-/releases/continuous-master/downloads/levior-latest-x86_64.AppImage
chmod +x levior.AppImage
./levior.AppImage
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

For JS rendering, use the *js* extra:

```sh
pip install -e '.[js]'
```

# Usage

*levior* can be configured from the command-line or via a *YAML* config file
(if a config file is provided, settings from both sources are merged to create
a unique config, with the config file settings taking precedence).
See [the example config file](https://gitlab.com/cipres/levior/-/raw/master/examples/levior.yaml). URL rules can only be configured with a config file.

```sh
levior
levior -d --mode=proxy
levior -c config.yaml
```

Socks5 proxies are supported with **--socks5-proxy**. **--tor**
will use the default socks5 proxy address for Tor (*socks5://localhost:9050*).

```sh
levior --socks5-proxy "socks5://localhost:9050"
levior --tor
```

## Daemonization

Use **--daemon** or **-d** to run levior as a daemon.

## Gemtext filters

It's possible to run filters on the gemtext content that will be sent to
the browser. In your config file, set the *gemtext_filters* property for the
rule. For example, this will remove any email address link by running
the *strip_emailaddrs* function found in the *levior.filters.links* python
module (if you don't specify a function name, it will call the
*gemtext_filter* function/coroutine in that module by default):

```yaml
urules:
  - regexp:
    - "https://searx.be/search"
    - "https://lite.duckduckgo.com/lite/search"

    gemtext_filters:
      - levior.filters.links:strip_emailaddrs
      - levior.filters:get_out
        re:
          - 'google'
          - 'stop'
```

You can also pass params to your filter. This rule removes all (English)
wikipedia URLs and PNG image URLs in the final gemtext:

```yaml
urules:
  - regexp: ".*"
    gemtext_filters:
      - filter: levior.filters.links:url_remove
        urls:
          - ^https://en.wikipedia.org
          - \.png$
```

Your filter (which can be a function or a coroutine) can return different
value types:

- *boolean*: if your filter returns *True*, that gemtext line will be **removed** (filtered out).
- [Line](https://gitlab.com/lofidevops/trimgmi/-/blob/main/trimgmi/__init__.py?ref_type=heads#L99) (*trimgmi* class): If you return a *Line* object, it will be used
  to **replace** the original gemtext line.
- *list*: If you return a list of *Line* objects, they will be inserted in
  place
- *str*: **replace** the original gemtext line with this raw string value
- *int*: If your filter returns a negative integer, everything after that in
  the document (including that line) will be removed.

Any other return value type will be ignored.

Checkout [https://gitlab.com/cipres/levior/-/tree/master/levior/filters](the
filters package) to see the available builtin filters.

## Javascript rendering

*Experimental feature*.

*levior* (through the use of
[requests-html](https://github.com/psf/requests-html) which uses the
[pyppeteer](https://github.com/pyppeteer/pyppeteer)
headless automation library) can render webpages that contain
Javascript code.

Pass **--js** on the command-line to enable Javascript
rendering. Use **js-force** to always run JS rendering even if no JS scripts
were detected on the page.

**Note**: when you run levior with JS rendering for the first time, pyppeteer
will download a copy of the browser binary that it requires to run
(about ~300 Mb of free disk space is required).

## Service modes

- *server*: serves web content as gemtext, via gemini URLs. When you visit levior's
  gemini URL ([gemini://localhost](gemini://localhost) by default) you'll be
  asked for a web domain to browse via a gemini input request.
  You can also simply go to **gemini://localhost/{domain}** in your Gemini
  browser, for example [gemini://localhost/sr.ht](gemini://localhost/sr.ht)
  to browse [https://sr.ht](https://sr.ht).
  The URLs in the HTML pages are rewritten to be routed through the
  levior server. **This mode is compatible with any Gemini browser.**

- *proxy*: in this mode, *levior* acts as a proxy for http and https URLs
  and serves pages without rewriting URLs. **To use this mode, you need a
  Gemini browser that supports http proxies**. Here's a list of browsers
  supporting proxies:
  [Gemalaya](https://gemalaya.gitlab.io) (bundles and uses levior in proxy mode
  by default), [Lagrange](https://gmi.skyjake.fi/lagrange/),
  [Amfora](https://github.com/makew0rld/amfora),
  [diohsc](https://hackage.haskell.org/package/diohsc) and
  [Telescope](https://telescope.omarpolo.com/).

The allowed modes can be set with the **--mode** (or **-m**) command-line
argument or with the *mode* setting in the config file. Use **--mode=proxy** to
run only as a transparent http proxy, or **--mode=server** to only serve
requests made with gemini URLs.

Use **--mode=proxy,server** to handle both request types (this is the default).

## Configuring your Gemini browser to use levior as a proxy

### Lagrange

In the *File* menu, select *Preferences*, and go to the
*Network* section. Set the *HTTP proxy* text field to *127.0.0.1:1965*.
If you're not running levior on *localhost*, set it
to levior's listening IP and port.

### Telescope

As explained in the [docs](https://telescope.omarpolo.com/telescope.1.html),
edit *~/.config/telescope/config* and add the following:

```
proxy http via "gemini://127.0.0.1:1965"
proxy https via "gemini://127.0.0.1:1965"
```

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

## Server endpoints

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
