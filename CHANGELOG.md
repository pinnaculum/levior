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
