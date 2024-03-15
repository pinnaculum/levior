# Web to Gemini proxy

![logo](https://gitlab.com/cipres/levior/-/raw/master/media/img/levior-256.png)

> *Pāpiliō levior est ave* (The butterfly is lighter than the bird)

*levior* (a latin word meaning *lighter*) is a web (HTTP/HTTPs) to
[Gemini](https://geminiprotocol.net) proxy.
It converts web pages (as well as Atom/RSS feeds) on-the-fly to
the [gemtext](https://geminiprotocol.net/docs/gemtext.gmi) format,
allowing you to browse regular web pages with any Gemini browser without having
to suffer the heavyness associated with certain technologies of the modern web.

*levior* supports Javascript rendering and can therefore be used to browse
dynamic websites.

*levior* also supports serving other types of content, like ZIM files (the
archive format used by Wikipedia), making it possible to browse complete wikis
through Gemini ([see the config file](https://gitlab.com/cipres/levior/-/raw/master/examples/levior.zim.yaml)).

## Supporting this project

If you want to support this project, you can
make a donation [here](https://ko-fi.com/cipres) (or
[here](https://liberapay.com/galacteek)).

## Installation

### AppImage

You can get the latest AppImage [here](https://gitlab.com/cipres/levior/-/releases/continuous-master/downloads/levior-latest-x86_64.AppImage). This would install levior in *~/.local/bin*:

```sh
curl -L -o ~/.local/bin/levior https://gitlab.com/cipres/levior/-/releases/continuous-master/downloads/levior-latest-x86_64.AppImage
chmod +x ~/.local/bin/levior
```

### Manual Install

```sh
pip install .
```

For zim or uvloop support, install the extra requirements:

```sh
pip install '.[zim]'
pip install '.[uvloop]'
```

For Javascript rendering, install the *js* extra:

```sh
pip install '.[js]'
```

## Usage

*levior* can be configured from the command-line or via a *YAML* config file
If a config file is provided, settings from both sources are merged to create
a unique config, with the config file settings taking precedence.
See [the example config file](https://gitlab.com/cipres/levior/-/raw/master/examples/levior.yaml). URL rules can only be configured with a config file.

levior uses the [OmegaConf library](https://omegaconf.readthedocs.io) to
parse the YAML config files, therefore all the specific syntax elements
supported by *OmegaConf* can be used in your configuration files.

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

### Generating a new configuration file

```sh
levior --config-gen levior.yaml
levior -c levior.yaml
```

## Daemonization

Use **--daemon** or **-d** to run levior as a daemon, or set the
*daemonize* setting in the config file:

```yaml hl_lines="1"
daemonize: true
pid_file_path: levior.pid
```

## Logging

### Access log

Requests are logged as gemtext links. Use **--log-file** if you want the
access log to be written to a file.

- If you are not running *levior* as a daemon, and you don't specify an access
  log file path, requests are logged to the console
- If you are running *levior* as a daemon, requests are logged to the specified
  log file (or the default: *levior-log.gmi*)

### Access log server endpoint

Set *access_log_endpoint* to *true* in your config file to enable the access
log endpoint **/access_log** on the server. This endpoint shows the
proxy's access log in the gemtext format.

```yaml hl_lines="1"
access_log_endpoint: true
```

## Restricting access by IP address or network

You can restrict access to the proxy by declaring a list of
allowed IP addresses or networks in your config file.

```yaml
client_ip_allow:
  - 127.0.0.1
  - 10.0.1.0/24
```

## URL rules

You can define your own rules in order to apply some processing on the gemtext
that will be sent to the browser, or return a specific gemini response.

A rule must define which URL(s) to match with the *url* attribute, which can
be a regular expression or a list of regular expressions. If the *response*
attribute is defined, the *status* attribute must be set as an
[aiogemini Status code](https://github.com/keis/aiogemini/blob/master/aiogemini/__init__.py). Here are some basic examples of custom rules:

```yaml hl_lines="3 4"
rules:
  - url: '^https?://[\\w.-]*google'
    response:
      status: 'PROXY_REQUEST_REFUSED'
```

```yaml
rules:
  - url: '^https?://www.example.org'
    response:
      status: 'SUCCESS'
      text: |-
        Gemtext content
```

Set *js_render* in the rule to enable JS rendering.

```yaml hl_lines="3"
rules:
  - url: '^https?://www.requires-js.org'
    js_render: true
```

### Caching

The raw content of the web resources fetched by the proxy can be cached.
The result of the *geminification* of the pages (the gemtext document)
is never cached.

Set the *cache* attribute in your rule to cache the data. The *ttl*
(time-to-live) attribute determines the expiration lifetime (in seconds) for the
resource's content in the cache. The data will be served from the cache
until the ttl expires (subsequent requests will trigger a refetch).

```yaml hl_lines="3 4"
rules:
  - url: '^https?://www.thingstokeep.org'
    cache: true
    ttl: 86400
```

#### Caching the access log

The access log can be persisted in the cache via the *persist_access_log*
setting (or with **--persist-access-log**). This is disabled by default.

```yaml
persist_access_log: true
```

#### Caching links on pages

Specific links to cache the page for a few days (or forever) can be shown
at the top of the page, with the *page_cachelinks* setting. This makes
it easy to cache a page that you've just browsed without having to define
custom rules.

```yaml
page_cachelinks: true
```

### Includes

It is also possible to load predefined rules by using the *include* keyword
in your config file. If you prefix the path with *levior:*, it will be loaded
from the builtin [rules library](https://gitlab.com/cipres/levior/-/tree/master/levior/configs) (please [open a PR](https://gitlab.com/cipres/levior/-/merge_requests/new) to submit new rules), otherwise it is assumed to be a local file. Because
all the config files use the YAML syntax, you can omit the *.yaml* suffix
in the filename (it will be appended automatically).

```yaml
include:
  - levior:sites/francetvinfo.yaml
  - my_rules.yaml
```

Rules can receive parameters, allowing the creation of more generic rules
that can be applied to any URL.

```yaml
rules:
  - url: ${URL}
    gemtext_filters:
      - filter: levior.filters:uppercased
        words: ${uwords}
```

To pass params to the rule from the config file, set the rule path by setting
the *src* attribute, and set the params via the *with* attribute.

```yaml hl_lines="2 3"
include:
  - src: words_upper.yaml
    with:
      URL:
        - https://example.org/.*.html
        - https://domain.io
      uwords:
        - coffee
        - milk
```

The *puretext* rule keeps only the text content:

```yaml
include:
  - src: levior:puretext
    with:
      URL:
        - https://example.org
        - https://example2.org
```

### Feeds aggregator

It is possible to aggregate multiple Atom/RSS web feeds into a single
tinylog, by setting the rule type to *feeds_aggregator* and defining the
list of feeds. Example:

```yaml hl_lines="3"
rules:
  - url: '^gemini://localhost/francetv'
    type: 'feeds_aggregator'

    # "feeds" is a dictionary, the key must be the feed's URL, the
    # dict value is for the feed's options
    feeds:
      https://www.francetvinfo.fr/titres.rss: {}
      https://www.francetvinfo.fr/monde.rss: {}
      https://www.francetvinfo.fr/culture.rss:
        enabled: false
```

When you are sourcing a config file that includes aggregation rules,
you can enable or disable certain feeds using the parameters:

```yaml hl_lines="4 5"
  - src: levior:sites/francetvinfo
    with:
      feeds:
        culture: true
        sports: true
```

### Gemtext filters

It's possible to run filters on the gemtext content that will be sent to
the browser. In your config file, set the *gemtext_filters* property for the
rule. For example, this will remove any email address link by running
the *strip_emailaddrs* function found in the *levior.filters.links* python
module (if you don't specify a function name, it will call the
*gemtext_filter* function/coroutine in that module by default):

```yaml hl_lines="6"
urules:
  - url:
    - "https://searx.be/search"
    - "https://lite.duckduckgo.com/lite/search"

    gemtext_filters:
      - levior.filters.links:strip_emailaddrs
      - filter: levior.filters:get_out
        re:
          - 'google'
          - 'stop'
```

You can also pass params to your filter. This rule removes all (English)
wikipedia URLs and PNG image URLs in the final gemtext:

```yaml hl_lines="5 6 7"
urules:
  - url: ".*"
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

Checkout [the filters package](https://gitlab.com/cipres/levior/-/tree/master/levior/filters) to see all the available builtin filters.

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

### /access_log

Shows the proxy's access log.

### /cache

Lists the objects stored in the cache.

### /search

When accessing */search*, you'll be prompted for a search query. Your search
will be performed via the *searx* search engine.
