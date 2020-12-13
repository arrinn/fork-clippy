import datetime
import os
import re
import shutil
import subprocess

import click
import gitlab
import git

from . import helpers
from . import highlight
from .echo import echo
from .exceptions import ClientError
from .config import Config


CONFIG_TEMPLATE = {
    "gitlab.user": "-",
    "gitlab.token": "-",
    "name.first": "-",
    "name.last": "-",
    "group": "group",
    "assignee": "-",
}

# Solutions local repository


class Solutions(object):
    def __init__(self, repo_dir, task_ci_config):
        if repo_dir and not os.path.exists(repo_dir):
            raise RuntimeError(
                "Solutions repository not found at '{}'".format(repo_dir))

        self.repo_dir = repo_dir
        self.task_ci_config_path = task_ci_config

        if repo_dir:
            self._open_config()

    def setup_git_config(self):
        return_dir = os.getcwd()
        os.chdir(self.repo_dir)
        try:
            self._git(["config", "--get", "user.email"])
        except subprocess.CalledProcessError:
            self._git(["config", "user.email", ""])
        try:
            self._git(["config", "--get", "user.name"])
        except subprocess.CalledProcessError:
            self._git(["config", "user.name", '"{} {}"'.format(
                self.config.get("name.first"), self.config.get("name.last"))])
        os.chdir(return_dir)

    def _open_config(self):
        config_path = os.path.join(self.repo_dir, ".clippy-user.json")

        template = CONFIG_TEMPLATE
        if not os.path.exists(config_path):
            template = self._config_init_template()

        self.config_ = Config(config_path, template=template)

    def _parse_repo_name(self, repo_name):
        # Expected format: {group}-{name}-U-{login}

        prefix, login = repo_name.rsplit('-u-', 1)
        group, name = prefix.split('-', 1)

        def capitalize(name):
            if not name:
                return name
            return name[0].upper() + name[1:]

        name_parts = list(map(capitalize, name.split('-')))

        if len(name_parts) == 2:
            first, last = name_parts
        elif len(name_parts) > 2:
            first, last = name_parts[0], '-'.join(name_parts[1:])
        else:
            first, last = 'first', 'last'

        return group, first, last, login

    def _config_init_template(self):
        template = CONFIG_TEMPLATE

        print(self.remote)

        repo_name = helpers.get_repo_name(self.remote)

        EXPECTED_NAME_PATTERN = r"(\S+)-(\S+)-u-(\S+)"

        if re.match(EXPECTED_NAME_PATTERN, repo_name):
            try:
                group, first, last, login = self._parse_repo_name(repo_name)

                template["group"] = group
                template["name.first"] = first
                template["name.last"] = last
                template["gitlab.user"] = login
            except Exception:
                pass

        return template

    @staticmethod
    def open(tasks_repo, task_ci_config):
        tasks_repo_dir = tasks_repo.working_tree_dir
        task_ci_config = os.path.join(tasks_repo_dir, task_ci_config)

        link_path = os.path.join(tasks_repo_dir, "client/.solutions")

        solutions_repo_dir = None

        if os.path.exists(link_path):
            with open(link_path) as link:
                solutions_repo_dir = link.read().strip()

        if solutions_repo_dir:
            if not os.path.exists(solutions_repo_dir):
                os.remove(link_path)  # outdated
                solutions_repo_dir = None

        return Solutions(solutions_repo_dir, task_ci_config)

    @property
    def attached(self):
        return self.repo_dir is not None

    def _check_attached(self):
        if not self.attached:
            raise RuntimeError("Solutions repository not attached")

    @property
    def config(self):
        self._check_attached()
        return self.config_

    @property
    def remote(self):
        self._check_attached()
        git_repo = git.Repo(self.repo_dir)
        return git_repo.remotes.origin.url

    def _git(self, cmd, **kwargs):
        self._check_attached()
        echo.echo("Running git: {}".format(cmd))
        subprocess.check_call(["git"] + cmd, **kwargs)

    def _git_output(self, cmd, **kwargs):
        self._check_attached()
        echo.echo("Running git: {}".format(cmd))
        return subprocess.check_output(["git"] + cmd, **kwargs)

    @staticmethod
    def _task_branch_name(task):
        return "{}/{}".format(task.homework, task.name)

    def _task_dir(self, task):
        return "{}/{}".format(task.homework, task.name)

    def _switch_to_or_create_branch(self, branch):
        try:
            self._git(["checkout", branch], cwd=self.repo_dir)
        except subprocess.CalledProcessError:
            self._git(["checkout", "-b", branch], cwd=self.repo_dir)

    def _switch_to_branch(self, name):
        self._git(["checkout", name], cwd=self.repo_dir)

    def _switch_to_master(self):
        self._switch_to_branch("master")

    @staticmethod
    def _default_commit_message(task):
        return "Bump task {}/{}".format(task.homework, task.name)

    def _unstage_all(self):
        self._git(["reset", "HEAD", "."], cwd=self.repo_dir)

    def commit(self, task, message=None, bump=False):
        self._check_attached()

        solution_files = task.conf.solution_files

        os.chdir(self.repo_dir)
        echo.echo("Moving to repo {}".format(highlight.path(self.repo_dir)))

        self._unstage_all();
        self._switch_to_master()

        task_branch = self._task_branch_name(task)
        echo.echo("Switching to task branch '{}'".format(task_branch))
        self._switch_to_or_create_branch(task_branch)

        os.chdir(self.repo_dir)

        task_dir = self._task_dir(task)

        if not os.path.exists(task_dir):
            helpers.mkdir(task_dir, parents=True)

        echo.echo("Copying solution files: {}".format(solution_files))
        helpers.copy_files(task.dir, task_dir, solution_files, clear_dest=True)

        echo.echo("Adding solution files to index")
        self._git(["add"] + solution_files, cwd=task_dir)

        if bump:
            bumpfile = os.path.join(task_dir, "bump")
            now = datetime.datetime.now()
            with open(bumpfile, "w") as f:
                f.write(now.strftime("%Y-%m-%d %H:%M:%S"))
            self._git(["add", "bump"], cwd=task_dir)

        # Add CI config
        if self.task_ci_config_path:
            shutil.copy(
                self.task_ci_config_path,
                os.path.join(
                    self.repo_dir,
                    ".gitlab-ci.yml"))
            self._git(["add", ".gitlab-ci.yml"], cwd=self.repo_dir)

        diff = self._git_output(["diff", "--staged", "."], cwd=self.repo_dir)
        if not diff:
            echo.note("Empty diff, nothing to commit")
            self._switch_to_master()
            return

        if not message:
            message = self._default_commit_message(task)

        echo.note("Committing task solution")
        self._git(["commit", "-m", message], cwd=task_dir)

        self._switch_to_master()

    def push(self, task):
        self._check_attached()

        os.chdir(self.repo_dir)
        echo.echo("Moving to repo {}".format(highlight.path(self.repo_dir)))

        task_branch = self._task_branch_name(task)

        self._switch_to_branch(task_branch)
        self._git(["push", "origin", task_branch], cwd=self.repo_dir)

        self._switch_to_master()

    def _get_remote_repo_address(self):
        url = self.remote

        def _cut_dot_git(addr):
            if addr.endswith(".git"):
                addr = addr[:-4]
            return addr

        prefixes = ["https://gitlab.com/", "git@gitlab.com:"]
        for prefix in prefixes:
            if url.startswith(prefix):
                return _cut_dot_git(url[len(prefix):])

        raise ClientError(
            "Cannot get solutions repo address for '{}'".format(url))

    def merge(self, task):
        self._check_attached()

        echo.echo("Creating merge request...")

        task_branch_name = self._task_branch_name(task)

        # Create Gitlab client

        token = self.config.get("gitlab.token")
        gitlab_client = gitlab.Gitlab(
            "https://gitlab.com", private_token=token)
        gitlab_client.auth()

        remote_repo_address = self._get_remote_repo_address()
        echo.echo("Solutions Gitlab repo: {}".format(remote_repo_address))
        project = gitlab_client.projects.get(remote_repo_address)

        task_branch = helpers.try_get_branch(project, task_branch_name)
        if not task_branch:
            raise ClientError(
                "Task branch not found in remote repository: {}".format(task_branch_name))

        labels = [
            self.config.get("group"),
            task.homework,
            task.fullname,
        ]

        title = "[{group}] [{student}] {task}".format(
            group=self.config.get("group"),
            student="{}-{}".format(self.config.get("name.first"),
                                   self.config.get("name.last")),
            task="{}/{}".format(task.homework, task.name)
        )

        assignee_username = self.config.get("assignee")
        assignees = gitlab_client.users.list(username=assignee_username)
        if not assignees:
            raise ClientError(
                "Assignee not found: '{}'".format(assignee_username))
        assignee = assignees[0]

        merge_request_attrs = {
            'source_branch': task_branch_name,
            'target_branch': 'master',
            'labels': labels,
            'title': title,
            'assignee_id': assignee.id
        }

        try:
            mr = project.mergerequests.create(merge_request_attrs)
            echo.echo("Merge request created: {}".format(mr.web_url))
        except gitlab.exceptions.GitlabCreateError as error:
            if error.response_code == 409:
                echo.note(
                    "Merge request for task {} already exists".format(
                        task.fullname))

    def apply_to(self, task, force=False):
        self._check_attached()

        os.chdir(self.repo_dir)
        echo.echo("Moving to repo {}".format(highlight.path(self.repo_dir)))

        task_branch = self._task_branch_name(task)
        self._switch_to_branch(task_branch)

        task_dir = self._task_dir(task)

        if not os.path.exists(task_dir):
            raise ClientError(
                "Cannot find task directory '{}' in branch '{}'".format(
                    task_dir, task_branch))

        if force or click.confirm(
                "Apply solutions to task {}?".format(task.fullname)):
            echo.echo("Applying solution from solutions repo...")
            helpers.copy_files(task_dir, task.dir, task.conf.solution_files)

        # TODO: does new gitlab-runner fetch master?
        #self._switch_to_master()

