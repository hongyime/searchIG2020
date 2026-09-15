"""Search Google for public Instagram URLs with explicit bounds and preserved output."""
from __future__ import annotations

import argparse
import inspect
from itertools import islice
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable, Iterable, TextIO
from urllib.parse import urlsplit


def validate_options(keywords: list[str], limit: int, deadline: float) -> None:
    if not 1 <= len(keywords) <= 5 or any(
            not isinstance(word, str) or not word.strip() or len(word) > 200
            or any(char in word for char in '\r\n"') for word in keywords):
        raise ValueError('Provide one to five plain keywords, each 1–200 characters without quotes or newlines')
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Result limit must be an integer from 1 to 100')
    if isinstance(deadline, bool) or not math.isfinite(deadline) or not 1 <= deadline <= 300:
        raise ValueError('Deadline must be between 1 and 300 seconds')


def load_search() -> Callable[..., Iterable[str]]:
    from googlesearch import search
    inspect.signature(search).bind('fixture', num_results=1, lang='en',
                                   sleep_interval=10, timeout=10)
    return search


def emit_results(keywords: list[str], limit: int, search: Callable[..., Iterable[str]],
                 output: TextIO) -> int:
    """Save matching URLs in provider order under one shared candidate budget."""
    scanned = written = 0
    for index, keyword in enumerate(keywords):
        if scanned >= limit:
            break
        if index:
            time.sleep(10)
        remaining = limit - scanned
        results = search(f'site:instagram.com "{keyword.strip()}"', num_results=remaining,
                         lang='en', sleep_interval=10, timeout=10)
        for url in islice(results, remaining):
            scanned += 1
            if not isinstance(url, str) or len(url) > 8192 or '\n' in url or '\r' in url:
                continue
            try:
                parsed = urlsplit(url)
                valid = (parsed.scheme in ('http', 'https')
                         and parsed.hostname in ('instagram.com', 'www.instagram.com')
                         and parsed.username is None and parsed.password is None)
            except ValueError:
                valid = False
            if valid:
                print(url, file=output, flush=True)
                written += 1
    return written


def run_worker(command: list[str], output: Path, deadline: float) -> subprocess.CompletedProcess:
    """Run one owned worker; subprocess.run kills and waits for it on timeout."""
    if os.path.lexists(output):
        raise FileExistsError(f'Output already exists; choose a new path: {output}')
    with output.open('x', encoding='utf-8', newline='\n') as handle:
        try:
            return subprocess.run(command, stdin=subprocess.DEVNULL, stdout=handle,
                                  stderr=subprocess.PIPE, text=True, encoding='utf-8',
                                  errors='replace', timeout=deadline, check=False,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        finally:
            handle.flush()
            os.fsync(handle.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keyword', action='append', required=True, help='Repeat for up to five keywords')
    parser.add_argument('--limit', type=int, default=20, help='Total candidate result limit, 1–100 (default: 20)')
    parser.add_argument('--deadline', type=float, default=60, help='Whole-search deadline in seconds, 1–300')
    parser.add_argument('--output', type=Path, default=Path('urls.txt'))
    parser.add_argument('--_worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        validate_options(args.keyword, args.limit, args.deadline)
        search = load_search()
        if args._worker:
            return 0 if emit_results(args.keyword, args.limit, search, sys.stdout) else 3
        command = [sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve()), '--_worker',
                   '--limit', str(args.limit), '--deadline', str(args.deadline)]
        for keyword in args.keyword:
            command.append('--keyword=' + keyword)
        result = run_worker(command, args.output, args.deadline)
        if result.returncode == 0:
            print(f'Results saved to {args.output}')
            return 0
        if result.returncode == 3:
            print('No matching URLs returned. This may also mean the provider response was unavailable or unrecognized.', file=sys.stderr)
            return 3
        print(result.stderr.strip() or 'Search worker stopped before completion.', file=sys.stderr)
        print(f'Any results already written are retained at {args.output}', file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print(f'Search deadline reached; partial results are retained at {args.output}', file=sys.stderr)
        return 124
    except KeyboardInterrupt:
        print(f'Interrupted; partial results are retained at {args.output}', file=sys.stderr)
        return 130
    except (ImportError, OSError, TypeError, ValueError) as error:
        print(f'{type(error).__name__}: {error}. Existing and partial files are retained.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
