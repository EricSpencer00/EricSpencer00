import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from update_commit_badge import latest_authored_commit, write_badge


def commit(author, day, message='Update'):
    return NS(author=NS(login=author), sha=str(day) * 40,
              html_url=f'https://github.com/EricSpencer00/work/commit/{day}' ,
              commit=NS(author=NS(date=datetime(2026, 10, day, tzinfo=timezone.utc)), message=message))


class Repo:
    private = False

    def __init__(self, name, commits, status=None):
        self.name, self.commits, self.status = name, commits, status
        self.authors = []

    def get_commits(self, author=None):
        self.authors.append(author)
        if self.status:
            error = RuntimeError('GitHub API failure')
            error.status = self.status
            raise error
        return (c for c in self.commits if not author or c.author.login.lower() == author.lower())


def user(repos):
    return NS(login='EricSpencer00', get_repos=lambda: repos)


class BadgeTests(unittest.TestCase):
    def test_bot_or_other_contributor_at_head_does_not_hide_eric(self):
        for head in ('github-actions[bot]', 'Contributor'):
            with self.subTest(head=head):
                newer = Repo('newer', [commit(head, 3), commit('EricSpencer00', 2)])
                older = Repo('older', [commit('EricSpencer00', 1)])
                result = latest_authored_commit(user([older, newer]))
                self.assertEqual(result['repo'], 'newer')
                self.assertEqual(newer.authors, ['EricSpencer00'])

    def test_empty_and_non_eric_histories(self):
        self.assertIsNone(latest_authored_commit(user([
            Repo('empty', []), Repo('uninitialized', [], status=409),
            Repo('other', [commit('Contributor', 3)])])))

    def test_api_failure_does_not_publish_partial_result(self):
        with self.assertRaises(RuntimeError):
            latest_authored_commit(user([Repo('ok', [commit('EricSpencer00', 1)]),
                                         Repo('denied', [], status=403)]))

    def test_empty_history_preserves_badge_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('README.md', 'recent-commit.json', 'commit-url.txt'):
                (root / name).write_text('existing')
            self.assertFalse(write_badge(None, root))
            self.assertTrue(all(p.read_text() == 'existing' for p in root.iterdir()))

    def test_json_escaping_and_other_readme_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'README.md').write_text('[project](https://github.com/EricSpencer00/work) [commit](https://github.com/EricSpencer00/work/commit/abc)')
            result = latest_authored_commit(user([Repo('work', [commit('EricSpencer00', 2, 'Say "hi"\n$(command)')])]))
            write_badge(result, root)
            self.assertEqual(json.loads((root / 'recent-commit.json').read_text())['message'], 'work | Say hi (command)')
            self.assertIn('[project](https://github.com/EricSpencer00/work)', (root / 'README.md').read_text())
            self.assertIn(result['url'], (root / 'README.md').read_text())
