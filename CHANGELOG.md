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
