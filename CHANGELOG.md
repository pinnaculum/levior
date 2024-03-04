## [1.3.2] - 2024-03-04

### Added

- Proxy access restriction by IP address/subnet
- Persist the access log in the diskcache (optional)

## [1.3.1] - 2024-03-03

### Added

- Logging of requests as an access log in the gemtext format
- Access log server endpoint
- Feeds aggregator: make it possible to only show entries from a specific
  feed by passing its index in the URL query
- Proxy access restriction by using IP address ACLs

## [1.3.0] - 2024-02-26

### Added

- Caching of web feeds (using etag and last-modified headers)
- New settings for the diskcache: eviction policy, size limit

## [1.2.9] - 2024-02-23

### Added

- Make it possible to enable or disable certain feeds when sourcing
  a config file containing "feeds aggregator" rules

### Changed

- Feeds aggregator: simplify the tinylog output
- AppImage: use python version 3.12.2 (niess/python-appimage)
- Use importlib.resources instead of pkg_resources

## [1.2.8] - 2024-02-21

### Added

- Support for Atom/RSS feeds aggregation rules. The feeds defined in the rule
  are aggregated and converted to a single tinylog accessible via a gemini URL.

## [1.2.7] - 2024-01-25

### Added

- Config files sourced via "include" can now receive parameters
- "only_linetypes" gemtext filter
- "uppercased" gemtext filter
- "puretext" rule
- Rules for "off-guardian.org"

### Changed

- The "url_remove" filter can now also remove links based on the URL's title

## [1.2.6] - 2024-01-18

### Added

- Support for including external config files

## [1.2.5] - 2023-12-03

### Added

- Gemtext filters system
- Support custom gemini responses by defining the response attributes in the
  YAML config inside the URL rule

## [1.2.4] - 2023-12-02

### Added

- Support for rendering webpages that use Javascript, by using pyppeteer
  (via the "requests-html" package)

## [1.2.3] - 2023-12-01

### Added

- Add unit tests for proxy+server

### Changed

- The "mode" setting can now be a comma-separated list of service modes
- Return PROXY_REQUEST_REFUSED when necessary

## [1.2.2] - 2023-11-24

### Added

- Convert Atom/RSS feeds to gemtext (tinylogs)
- Proxy mode: route IPFS URLs through dweb.link

### Changed

- Don't let aiohttp handle redirects so that we can notify the gemini browser
  of eventual redirections

## [1.2.1] - 2023-11-20

### Added

- Add an option to run as a daemo
- Catch markdownify errors
- Add unit tests for both service modes

### Changed

- Use setup.cfg
- Use omegaconf to merge cmd-line and config file settings
