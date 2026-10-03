"""Refresh the public profile badge from the latest Eric-authored commit."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def clean_message(message):
    message = re.sub(r'\s+', ' ', message)
    message = re.sub(r'[^\w\s\-.,:;!?()]', '', message).strip() or 'Update'
    return message[:50] + ('...' if len(message) > 50 else '')


def latest_authored_commit(user):
    latest = None
    latest_date = datetime.min.replace(tzinfo=timezone.utc)
    for repo in user.get_repos():
        if repo.private:
            continue
        try:
            # GitHub filters the history before pagination, so a bot or another
            # contributor at HEAD cannot hide Eric's most recent contribution.
            commit = next(iter(repo.get_commits(author=user.login)), None)
        except Exception as error:
            if getattr(error, 'status', None) == 409:  # Empty Git repository.
                continue
            raise  # Do not publish an incomplete result after an API failure.
        if commit is None:
            continue
        if not commit.author or commit.author.login.casefold() != user.login.casefold():
            continue
        commit_date = commit.commit.author.date
        if commit_date > latest_date:
            latest_date = commit_date
            latest = {
                'repo': repo.name,
                'hash': commit.sha[:7],
                'message': clean_message(commit.commit.message),
                'url': commit.html_url,
                'date': commit_date.isoformat(),
            }
    return latest


def write_badge(commit, root=ROOT):
    if commit is None:
        return False  # Preserve existing files when the history is empty.
    badge = {
        'schemaVersion': 1,
        'label': 'Latest Commit',
        'message': f"{commit['repo']} | {commit['message']}",
        'color': '0A66C2',
        'namedLogo': 'github',
        'logoColor': 'white',
        'cacheSeconds': 0,
    }
    (root / 'recent-commit.json').write_text(json.dumps(badge, indent=2) + '\n')
    (root / 'commit-url.txt').write_text(commit['url'] + '\n')
    readme = root / 'README.md'
    text = re.sub(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/commit/[0-9a-f]+',
                  lambda _: commit['url'], readme.read_text())
    readme.write_text(text)
    return True


def main():
    from github import Auth, Github
    with Github(auth=Auth.Token(os.environ['GITHUB_TOKEN'])) as client:
        latest = latest_authored_commit(client.get_user('EricSpencer00'))
    if write_badge(latest):
        print(f"Updated badge from {latest['repo']}: {latest['hash']}")
    else:
        print('No Eric-authored commits found; existing badge preserved')


if __name__ == '__main__':
    main()
