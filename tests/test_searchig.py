"""Synthetic search and output preservation tests; no live queries."""
from contextlib import redirect_stderr, redirect_stdout
from importlib import util
from io import StringIO
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scrape instagram code.py'
SPEC = util.spec_from_file_location('searchig', SCRIPT)
app = util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = self.root / 'urls.txt'

    def test_import_is_inert_and_keeps_existing_results(self):
        self.output.write_bytes(b'previous results\x00\xff')
        code = f'import importlib.util,sys; s=importlib.util.spec_from_file_location("searchig",{str(SCRIPT)!r}); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); assert "googlesearch" not in sys.modules'
        result = subprocess.run([sys.executable, '-c', code], cwd=self.root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(self.output.read_bytes(), b'previous results\x00\xff')

    def test_explicit_keyword_is_required(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], cwd=self.root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())

    def test_help_does_not_start_a_search(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--help'], cwd=self.root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--deadline', result.stdout)
        self.assertFalse(self.output.exists())

    def test_limits_and_keywords_are_validated_before_work(self):
        for keywords, limit, deadline in [([], 20, 60), ([' '], 20, 60), (['x'] * 6, 20, 60), (['x\ny'], 20, 60), (['x'], 0, 60), (['x'], 101, 60), (['x'], True, 60), (['x'], 20, 0), (['x'], 20, float('nan')), (['x'], 20, 301)]:
            with self.subTest(values=(keywords, limit, deadline)), self.assertRaises(ValueError):
                app.validate_options(keywords, limit, deadline)

    def test_result_budget_stops_even_an_unbounded_provider(self):
        calls = []
        def results(*args, **kwargs):
            for i in range(1000):
                calls.append(i)
                yield f'https://www.instagram.com/fixture_{i}/'
        output = StringIO()
        self.assertEqual(app.emit_results(['photography'], 3, results, output), 3)
        self.assertEqual(calls, [0, 1, 2])
        self.assertEqual(len(output.getvalue().splitlines()), 3)

    def test_only_http_instagram_urls_are_saved_in_original_order(self):
        urls = ['https://www.instagram.com/fixture/', 'https://instagram.com.evil.test/a', 'file:///tmp/x', 'https://instagram.com/fixture2/', 'https://instagram.com/a\nother', '', None, 'https://user:pass@instagram.com/a']
        output = StringIO()
        self.assertEqual(app.emit_results(['art'], 8, Mock(return_value=iter(urls)), output), 2)
        self.assertEqual(output.getvalue(), urls[0] + '\n' + urls[3] + '\n')

    def test_input_duplicates_are_not_silently_removed(self):
        output = StringIO()
        url = 'https://www.instagram.com/fixture/'
        self.assertEqual(app.emit_results(['art'], 2, Mock(return_value=iter([url, url])), output), 2)
        self.assertEqual(output.getvalue(), (url + '\n') * 2)

    def test_multiple_keywords_share_one_budget_and_delay(self):
        provider = Mock(side_effect=[iter(['https://instagram.com/a']), iter(['https://instagram.com/b', 'https://instagram.com/c'])])
        with patch.object(app.time, 'sleep') as pause:
            self.assertEqual(app.emit_results(['art', 'music'], 2, provider, StringIO()), 2)
        self.assertEqual(provider.call_args_list[0].kwargs['num_results'], 2)
        self.assertEqual(provider.call_args_list[1].kwargs['num_results'], 1)
        pause.assert_called_once_with(10)

    def test_existing_output_blocks_worker_start(self):
        self.output.write_bytes(b'original\xff')
        with patch.object(app.subprocess, 'run') as worker, self.assertRaises(FileExistsError):
            app.run_worker(['unused'], self.output, 1)
        worker.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b'original\xff')

    def test_exclusive_open_preserves_a_concurrent_destination(self):
        original = Path.open
        def race(path, mode='r', *args, **kwargs):
            if path == self.output and mode == 'x':
                with original(path, 'w', encoding='utf-8') as f:
                    f.write('concurrent original')
            return original(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', new=race), self.assertRaises(FileExistsError):
            app.run_worker(['unused'], self.output, 1)
        self.assertEqual(self.output.read_text(), 'concurrent original')

    def test_real_worker_deadline_keeps_partial_output(self):
        command = [sys.executable, '-c', 'import time; print("https://instagram.com/fixture/", flush=True); time.sleep(30)']
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            app.run_worker(command, self.output, 3)
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(self.output.read_text(), 'https://instagram.com/fixture/\n')

    def test_failed_worker_keeps_written_results_and_error(self):
        command = [sys.executable, '-c', 'import sys; print("https://instagram.com/fixture/", flush=True); print("fixture failure", file=sys.stderr); sys.exit(1)']
        result = app.run_worker(command, self.output, 10)
        self.assertEqual(result.returncode, 1)
        self.assertIn('fixture failure', result.stderr)
        self.assertIn('fixture', self.output.read_text())

    def test_dependency_failure_creates_no_output(self):
        with patch.object(app, 'load_search', side_effect=ImportError('fixture missing dependency')), redirect_stderr(StringIO()):
            self.assertEqual(app.main(['--keyword', 'art', '--output', str(self.output)]), 1)
        self.assertFalse(self.output.exists())

    def test_cli_deadline_and_interrupt_are_reported_as_incomplete(self):
        for error, code in [(subprocess.TimeoutExpired('fixture', 1), 124), (KeyboardInterrupt(), 130)]:
            with self.subTest(code=code), patch.object(app, 'load_search'), patch.object(app, 'run_worker', side_effect=error), redirect_stderr(StringIO()):
                self.assertEqual(app.main(['--keyword', 'art', '--output', str(self.output)]), code)

    def test_empty_provider_result_is_not_reported_as_complete_success(self):
        with patch.object(app, 'load_search'), patch.object(app, 'run_worker', return_value=Mock(returncode=3, stderr='')), redirect_stderr(StringIO()):
            self.assertEqual(app.main(['--keyword', 'art', '--output', str(self.output)]), 3)

    def test_cli_worker_round_trip_with_a_local_provider_fixture(self):
        (self.root / 'googlesearch.py').write_text('''def search(term, num_results=10, lang='en', sleep_interval=0, timeout=5):
    assert term == 'site:instagram.com "-topic"'
    assert num_results == 1 and timeout == 10 and sleep_interval == 10
    yield 'https://www.instagram.com/fixture/'
''', encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--keyword=-topic', '--limit', '1', '--output', str(self.output)],
                                cwd=self.root, env={**os.environ, 'PYTHONPATH': str(self.root)}, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_text(), 'https://www.instagram.com/fixture/\n')
        self.assertIn('Results saved', result.stdout)


class ProviderTests(unittest.TestCase):
    def test_real_parser_and_request_settings_use_an_offline_html_fixture(self):
        search = app.load_search()
        import googlesearch
        html = '<div class="ezO2md"><a href="/url?q=https://www.instagram.com/fixture/&amp;sa=U"><span class="CVA68e">Fixture</span></a><span class="FrIlee">Example</span></div>'
        response = Mock(text=html)
        with patch.object(googlesearch, 'get', return_value=response) as request, patch.object(googlesearch, 'sleep'):
            output = StringIO()
            self.assertEqual(app.emit_results(['art'], 1, search, output), 1)
        self.assertEqual(output.getvalue(), 'https://www.instagram.com/fixture/\n')
        self.assertEqual(request.call_args.kwargs['timeout'], 10)
        self.assertEqual(request.call_args.kwargs['params']['q'], 'site:instagram.com "art"')
        response.raise_for_status.assert_called_once()

    def test_http_failure_stops_without_retry(self):
        search = app.load_search()
        import googlesearch
        from requests.exceptions import HTTPError
        response = Mock()
        response.raise_for_status.side_effect = HTTPError('fixture 429')
        with patch.object(googlesearch, 'get', return_value=response) as request, self.assertRaises(HTTPError):
            app.emit_results(['art'], 1, search, StringIO())
        request.assert_called_once()


if __name__ == '__main__':
    unittest.main()
