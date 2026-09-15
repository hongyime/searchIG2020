# PRD: searchIG2020

## Purpose

A local CLI searches Google for public Instagram URLs matching explicitly supplied keywords and writes returned URLs to a fresh text file. The script does not fetch profile content, verify biography fields or provide a web application.

## Behavior

- Require one to five explicit keywords; construct `site:instagram.com "keyword"` queries.
- Use the pinned `googlesearch-python` API, retaining English results and ten-second page pacing.
- Share one candidate budget across keywords: default 20, maximum 100. Only HTTP/HTTPS Instagram URLs are saved; order and duplicate occurrences are retained.
- Bound the entire search worker with a default 60-second deadline (maximum 300). Requests have a ten-second timeout. Keyword transitions also wait ten seconds.
- Write UTF-8 lines progressively. Refuse any existing destination, including one appearing after preflight; retain partial results on interruption, timeout or failure.
- Import and help must be inert. Verify dependency compatibility before opening output.

## Non-goals

Profile-content scraping, automated Instagram actions, live monitoring, exhaustive results, automatic resume, automatic retries and bypassing provider blocks are outside this utility's scope. The application does not treat an empty provider response as proof that no matching URLs exist.

## Runtime and verification

Python 3.11+; install requirements.txt in a clean environment. The repository default and PR target is `master`; feature branches use the repository's typed naming convention. Eighteen offline tests cover the real dependency parser with an HTML fixture, CLI-worker integration, bounded results, preservation and a real worker timeout. Required Linux/Windows checks gate release. GitHub Pages hosts static documentation/source; there is no linked Vercel runtime or application database.

Live provider availability and results are unverified by these offline checks. See README for CLI examples, exact limits, exit codes and recovery behavior.
