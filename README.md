
*levior* (latin word meaning *lighter*) is an HTTP/HTTPs to Gemini gateway.
It converts web pages on-the-fly to
the [gemtext](https://gemini.circumlunar.space/docs/gemtext.gmi) format,
allowing you to browse regular web pages with any Gemini browser without having
to suffer the heavyness associated with certain technologies of the modern web.

# Install

```sh
pip install -e .
```

With uvloop:

```sh
pip install -e '.[uvloop]'
```

# Usage

```sh
levior
```

Socks5 proxies are supported with **--socks5-proxy** (there's also **--tor**
which will use *localhost* on port *9050*):

```sh
levior --socks5-proxy localhost:9050
levior --tor
```

Open your Gemini browser and open *gemini://localhost* or *//localhost*.

## URLs

### /

When accessing */*, you'll be prompted for a domain name to browse.

### /{domain}

When accessing */{domain}*, *levior* will proxy *https://domain} to the
Gemini browser. Examples:

```sh
gemini://localhost/searx.be
gemini://localhost/gitlab.com/cipres/levior
```

### /search

When accessing */search*, you'll be prompted for a search query. Your search
will be performed via the *searx* search engine.
