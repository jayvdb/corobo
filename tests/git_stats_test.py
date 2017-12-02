import logging
from tempfile import mkdtemp
import unittest
from unittest.mock import create_autospec

from IGitt.GitHub.GitHubMergeRequest import GitHubMergeRequest
from IGitt.GitLab.GitLabMergeRequest import GitLabMergeRequest
from IGitt.GitHub.GitHubIssue import GitHubIssue
from IGitt.GitLab.GitLabIssue import GitLabIssue
from git import Repo
import IGitt

import plugins.git_stats
import plugins.labhub

from tests.helper import plugin_testbot


class MockedGitStatsPlugin(plugins.git_stats.GitStats):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dependencies = ['LabHub']

    def get_plugin(self, name):
        class FakeLabHub():
            REPOS = None

        return FakeLabHub()


class TestGitStats(unittest.TestCase):

    def setUp(self):
        self.mock_repo = create_autospec(IGitt.GitHub.GitHub.GitHubRepository)

    def test_pr_list(self):
        git_stats, testbot = plugin_testbot(MockedGitStatsPlugin, logging.DEBUG)
        git_stats.activate()

        git_stats.REPOS = {'test': self.mock_repo}
        mock_github_mr = create_autospec(GitHubMergeRequest)
        mock_gitlab_mr = create_autospec(GitLabMergeRequest)
        mock_github_issue = create_autospec(GitHubIssue)
        mock_gitlab_issue = create_autospec(GitLabIssue)
        mock_github_mr.closes_issue = mock_github_issue
        mock_gitlab_mr.closes_issue = mock_gitlab_issue
        mock_github_mr.repository = self.mock_repo
        mock_gitlab_mr.repository = self.mock_repo
        mock_github_mr.url = 'http://www.example.com/'
        mock_gitlab_mr.url = 'http://www.example.com/'
        mock_repo_obj = create_autospec(Repo)
        cmd_github = '!mergable {}'
        cmd_gitlab = '!mergable {}'

        self.mock_repo.merge_requests = [mock_github_mr]

        # Non-existing repo
        testbot.assertCommand(cmd_github.format('b'),
                              'Repository doesn\'t exist.')
        testbot.assertCommand(cmd_gitlab.format('b'),
                              'Repository doesn\'t exist.')

        # PR is suitable
        mock_github_mr.labels = ['process/approved', 'difficulty/newcomer']
        mock_gitlab_mr.labels = ['process/approved', 'difficulty/newcomer']
        mock_github_mr.state = 'open'
        mock_gitlab_mr.state = 'open'
        self.mock_repo.get_clone.return_value = (mock_repo_obj, mkdtemp('mock_repo/'))
        mock_repo_obj.head.commit.hexsha = '1'
        mock_github_mr.base.sha = '1'
        mock_gitlab_mr.base.sha = '1'
        testbot.assertCommand(cmd_github.format('test'),
                              'PRs ready to be merged:\n '
                              'http://www.example.com/')
        self.mock_repo.get_clone.return_value = (mock_repo_obj, mkdtemp('mock_repo/'))
        testbot.assertCommand(cmd_gitlab.format('test'),
                              'PRs ready to be merged:\n '
                              'http://www.example.com/')

        # PR is not suitable (wrong labels)
        mock_github_mr.labels = ['process/wip', 'difficulty/newcomer']
        mock_gitlab_mr.labels = ['process/wip', 'difficulty/newcomer']
        self.mock_repo.get_clone.return_value = (mock_repo_obj, mkdtemp('mock_repo/'))
        testbot.assertCommand(cmd_github.format('test'),
                              'No merge-ready PRs!')
        self.mock_repo.get_clone.return_value = (mock_repo_obj, mkdtemp('mock_repo/'))
        testbot.assertCommand(cmd_gitlab.format('test'),
                              'No merge-ready PRs!')
        mock_github_mr.labels = ['process/approved', 'difficulty/newcomer']
        mock_gitlab_mr.labels = ['process/approved', 'difficulty/newcomer']

        # PR is not suitable (needs rebase)
        mock_repo_obj.head.commit.hexsha = '2'
        self.mock_repo.get_clone.return_value = (mock_repo_obj, mkdtemp('mock_repo/'))
        testbot.assertCommand(cmd_github.format('test'),
                              'No merge-ready PRs!')
        self.mock_repo.get_clone.return_value = (mock_repo_obj, mkdtemp('mock_repo/'))
        testbot.assertCommand(cmd_gitlab.format('test'),
                              'No merge-ready PRs!')
        mock_repo_obj.head.commit.hexsha = '1'

        # PR is not suitable (already closed)
        mock_github_mr.state = 'closed'
        mock_gitlab_mr.state = 'closed'
        self.mock_repo.get_clone.return_value = (mock_repo_obj, mkdtemp('mock_repo/'))
        testbot.assertCommand(cmd_github.format('test'),
                              'No merge-ready PRs!')
        self.mock_repo.get_clone.return_value = (mock_repo_obj, mkdtemp('mock_repo/'))
        testbot.assertCommand(cmd_gitlab.format('test'),
                              'No merge-ready PRs!')
