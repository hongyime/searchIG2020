# Instagram URL Search

A local Python CLI that searches Google for public Instagram URLs matching explicit keywords. [Published instructions and source](https://hongyime.github.io/searchIG2020/) are static; the website does not perform searches.

## Installation

Use Python 3.11 or newer and a clean virtual environment:

```sh
git clone https://github.com/hongyime/searchIG2020.git
cd searchIG2020
python -m venv .venv
# Activate .venv using your shell, then:
python -m pip install -r requirements.txt
```

The pinned [googlesearch-python provider](https://pypi.org/project/googlesearch-python/1.3.0/) uses `sleep_interval`, not the incompatible `pause` argument from the old script.

## Usage

Supply a keyword explicitly; the script no longer searches a placeholder at startup:

```sh
python "scrape instagram code.py" --keyword photography
python "scrape instagram code.py" --keyword art --keyword music --limit 20 --deadline 60 --output next-results.txt
```

Up to five keywords are accepted, each 1–200 characters without embedded quotes or newlines. Prefix a leading-dash keyword with `--keyword=`, for example `--keyword=-topic`.

Each query uses `site:instagram.com "keyword"`. Only HTTP/HTTPS URLs hosted by `instagram.com` or `www.instagram.com` are saved. Result order and duplicate occurrences are retained. The script does not fetch Instagram profiles, verify biography text or determine whether each result is a profile rather than a post or other page.

| Setting | Default | Limit |
| --- | --- | --- |
| Candidate results across all keywords | 20 | 1–100 |
| Whole-search deadline | 60 seconds | 1–300 seconds |
| Request timeout | 10 seconds | Fixed |
| Delay between provider pages and keywords | 10 seconds | Fixed |
| Output | `urls.txt` | Must not already exist |

The candidate budget includes discarded, malformed and non-Instagram results, so fewer URLs may be saved. A single worker covers provider requests, parsing and delays; it is stopped and reaped on timeout. Local dependency loading and CLI setup happen before that deadline begins. The old 35-second delay before writing every result is removed; page/keyword pacing remains. HTTP failures stop without automatic retry, proxy rotation or CAPTCHA bypass logic in this application.

## Output preservation

Existing output paths are refused, including a file created concurrently after preflight. URLs are written progressively as UTF-8 lines. A timeout, interruption or provider failure retains any output already written; incomplete files are not automatically resumed or overwritten. Choose a new filename for another run. Keep retained partial files for inspection.

Exit codes: `0` means the worker completed and returned matching URLs; `3` means no matching URLs were returned; `124` means the search deadline expired; `130` means Ctrl+C; `1` covers dependency, file or provider failures; `2` covers invalid CLI arguments.

A zero-result response can also indicate a changed or blocked provider page. A completed search is not an exhaustive index of Instagram. Live search availability and result quality are not established by the offline tests.

Importing the module and running `--help` do not search, load the provider or touch result files.

## Development

```sh
python -m pip install -r requirements.txt
python -m pip check
python -B -m unittest discover -s tests -v
```

All 18 tests use synthetic URLs, local provider/HTML fixtures and owned temporary worker processes. They cover the installed parser and request options, candidate limits, output races, missing dependencies, interruption, HTTP errors and a real three-second worker deadline. No live queries, profile requests or existing result lists are used. Hosted Linux and Windows checks run on PRs and the default `master` branch.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
