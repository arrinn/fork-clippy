from . import helpers
from . import highlight
from .benchmark import print_benchmark_reports
from .config import Config
from .call import check_call, check_call_user_code, check_output_user_code
from .echo import echo
from .exceptions import ClientError
from .linters import ClangFormat, ClangTidy
from .build import Build
from .tasks import Tasks
from .test_runner import create_test_runner
from .solutions import Solutions

import click
import git

import os
import json
import shutil
import subprocess
import sys

from pathlib import Path


class ClientConfig:
    def __init__(self, repo_dir):
        self.config = self._open(repo_dir)

    @classmethod
    def _open(cls, repo_dir):
        return Config(cls._config_file_path(repo_dir))

    @classmethod
    def _config_file_path(cls, repo_dir):
        return os.path.join(repo_dir, ".clippy.json")

    def warmup_targets(self):
        return self.config.get_or("warmup_targets", default=[])

class CourseClient:
    def __init__(self):
        self.repo = self._this_client_repo()
        self.config = self._open_client_config()
        self.build = Build(self.repo)
        self.tasks = Tasks(self.repo)
        self._reopen_solutions()

    def _this_client_repo(self):
        this_tool_real_path = os.path.realpath(__file__)
        repo_root_dir = helpers.git_repo_root_dir(
            os.path.dirname(this_tool_real_path))
        return git.Repo(Path(repo_root_dir).parent)

    def _open_client_config(self):
        return ClientConfig(self.repo.working_tree_dir)

    def _reopen_solutions(self):
        self.solutions = Solutions.open(self.repo, ".grade.gitlab-ci.yml")

    def update(self):
        os.chdir(self.repo.working_tree_dir)

        echo.echo("Updating tasks repository\n")

        subprocess.check_call(["git", "pull", "origin", "master"])
        subprocess.check_call(["git", "submodule", "update", "--init", "--recursive"])

        echo.blank_line()
        self.cmake()

    # Generate build scripts
    def cmake(self, clean=False):
        if clean:
            self.build.reset()
        self.build.cmake()

    # Build common libraries
    def warmup(self):
        warmup_targets = self.config.warmup_targets()

        if not warmup_targets:
            echo.note("No targets to warmup")
            return

        for target in self.config.warmup_targets():
            self.build.warmup(target)

    def print_current_task(self):
        current_task = self.tasks.current_dir_task()

        if current_task:
            echo.echo("At homework {}, task {}".format(
                highlight.homework(current_task.homework), highlight.task(current_task.name)))
        else:
            echo.echo("Not in task directory: {}".format(
                highlight.path(os.getcwd())))

    def attach_remote_solutions(self, url, local_name=None):
        url = url.rstrip('/')
        helpers.check_gitlab(url)

        repo_parent_dir = os.path.dirname(self.repo.working_tree_dir)
        os.chdir(repo_parent_dir)

        if not local_name:
            local_name = helpers.get_repo_name(url)

        solutions_repo_dir = os.path.join(repo_parent_dir, local_name)

        link_path = os.path.join(
            self.repo.working_tree_dir,
            "client/.solutions")

        if os.path.exists(solutions_repo_dir):
            if click.confirm("Do you want remove existing solutions local repo '{}'?".format(
                    solutions_repo_dir), default=False):
                echo.echo(
                    "Remove existing solutions local repo '{}'".format(solutions_repo_dir))
                if os.path.exists(link_path):
                    os.remove(link_path)
                shutil.rmtree(solutions_repo_dir)
            else:
                # TODO(Lipovsky): interrupted
                sys.exit(1)

        echo.echo(
            "Clonging solutions repo '{}' to '{}'".format(
                url,
                highlight.path(solutions_repo_dir)))

        check_call(["git", "clone", url, local_name],
                   cwd=repo_parent_dir)

        # rewrite link
        with open(link_path, "w") as link:
            link.write(solutions_repo_dir)

        # try to "open" solutions repo
        self._reopen_solutions()
        self.solutions.setup_git_config()

        echo.echo("Solutions local repo: {}".format(
            highlight.path(solutions_repo_dir)))

    def attach_local_solutions(self, repo_dir):
        solutions_repo_dir = os.path.realpath(repo_dir)

        if not os.path.exists(solutions_repo_dir):
            raise ClientError(
                "Solutions local repo not found: '{}'".format(solutions_repo_dir))

        # TODO(Lipovsky): is git repo?

        # rewrite link
        link_path = os.path.join(
            self.repo.working_tree_dir,
            "client/.solutions")
        with open(link_path, "w") as link:
            link.write(solutions_repo_dir)

        self._reopen_solutions()

        echo.echo("Solutions local repo: {}".format(
            highlight.path(solutions_repo_dir)))

    def print_solutions(self):
        if not self.solutions.attached:
            echo.echo("Solutions repository not attached")
            return

        echo.echo("Working copy: {}".format(
            highlight.path(self.solutions.repo_dir)))
        echo.echo(
            "Remote repository: {}".format(
                self.solutions.remote))

    def current_task(self):
        return self.tasks.current_dir_task()

    def test(self, task, profile=None):
        if task.conf.theory:
            echo.note("Action disabled for theory task")
            return

        test_runner = create_test_runner(task, self.build)
        if profile:
            test_runner.run_all_profile_tests(profile)
        else:
            test_runner.run_all_tests()

    def benchmark(self, task):
        if task.conf.theory:
            echo.note("Action disabled for theory task")
            return

        with self.build.profile("Release"):
            check_call(["make", task.run_benchmark_target])

    def _include_dirs(self, task):
        libs_path = os.path.join(self.repo.working_tree_dir, "library")
        include_dirs = ["twist"] + task.conf.lint_includes
        return [task.dir] + [os.path.join(libs_path, d) for d in include_dirs]

    def format(self, task):
        clang_format = ClangFormat.locate()
        files_to_format = task.all_files_to_lint

        echo.echo(
            "Applying clang-format ({}) to {}".format(clang_format.binary, files_to_format))
        clang_format.format(files_to_format, style="file")

    def lint(self, task, verify=False):
        if task.conf.theory:
            echo.note("Action disabled for theory task")
            return

        os.chdir(task.dir)

        lint_targets = task.all_files_to_lint

        if not lint_targets:
            echo.echo("Nothing to lint")
            return

        for f in lint_targets:
            if not os.path.exists(f):
                raise ClientError("Lint target not found: '{}'".format(f))

        # clang-tidy

        clang_tidy = ClangTidy.locate()

        include_dirs = self._include_dirs(task)

        echo.echo("Include directories: {}".format(include_dirs))

        echo.echo(
            "Checking {} with clang-tidy ({})".format(task.conf.lint_files, clang_tidy.binary))

        if not clang_tidy.check(lint_targets, include_dirs):
            if verify:
                raise ClientError("clang-tidy check failed")

            if click.confirm("Do you want to fix these errors?", default=True):
                echo.echo(
                    "Applying clang-tidy --fix to {}".format(lint_targets))
                clang_tidy.fix(lint_targets, include_dirs)

        echo.blank_line()

        # clang-format

        clang_format = ClangFormat.locate()

        echo.echo(
            "Checking {} with clang-format ({})".format(task.conf.lint_files, clang_format.binary))

        ok, diffs = clang_format.check(lint_targets, style="file")
        if diffs:
            for target_file, diff in diffs.items():
                echo.echo("File: {}".format(
                    highlight.path(target_file)))
                echo.write(diff)

        if not ok:
            if verify:
                raise ClientError(
                    "clang-format check failed: replacements in {} file(s)".format(len(diffs)))
            else:
                files_to_format = list(diffs.keys())
                echo.echo(
                    "Applying clang-format ({}) to {}".format(clang_format.binary, files_to_format))
                clang_format.format(files_to_format, style="file")

    def _search_forbidden_patterns(self, task):
        forbidden_patterns = [
            "std::atomic",
            "std::mutex",
            "std::condition_variable",
            "std::thread",
            "Your code goes here",
            "not implemented",
            "Not implemented",
        ]

        task_forbidden_patterns = task.conf.forbidden_patterns
        if task_forbidden_patterns:
            forbidden_patterns.extend(task_forbidden_patterns)

        os.chdir(task.dir)

        solution_files = task.conf.solution_files
        echo.echo(
            "Searching for forbidden patterns in {}".format(solution_files))

        all_solution_files = task.all_solution_files

        for f in all_solution_files:
            source_code = open(f, 'rb').read().decode("utf-8").rstrip()
            for pattern in forbidden_patterns:
                if source_code.find(pattern) != -1:
                    raise ClientError(
                        "Forbidden pattern '{}' found in file '{}'".format(
                            pattern, f))

    def validate(self, task):
        if task.conf.theory:
            echo.note("Action disabled for theory task")
            return

        self.lint(task, verify=True)
        echo.blank_line()
        # NB: after linters!
        self._search_forbidden_patterns(task)

    def _get_benchmark_scores(self, task):
        with self.build.profile("Release") as build_dir:
            check_call(["make", task.benchmark_target])
            benchmark_bin = os.path.join(
                build_dir,
                'tasks',
                task.homework,
                task.name,
                'bin',
                task.benchmark_target)
            scores_json = check_output_user_code(
                [benchmark_bin, '--benchmark_format=json'], timeout=60).decode('utf-8')
            return json.loads(scores_json)

    def _run_perf_checker(self, task, solution_scores, private_scores):
        checker_path = os.path.join(task.dir, "benchmark_scores.py")
        checker = helpers.load_module("benchmark_scores", checker_path)
        success, report = checker.check_scores(solution_scores, private_scores)
        if not success:
            raise ClientError("Performance check failed: {}".format(report))

    def test_performance(self, task):
        if task.conf.theory:
            echo.note("Disabled for theory task")
            return

        if not task.conf.test_perf:
            echo.echo("No performance test")
            return

        private_solutions_repo_dir = self.repo.working_tree_dir + "-private"
        private_solution_dir = os.path.join(private_solutions_repo_dir, "perf_solutions", task.fullname)
        if not os.path.exists(private_solution_dir):
            echo.echo("Private solution not found: {}".format(private_solution_dir))
            return

        echo.echo("Collecting benchmark scores for current solution...")
        scores = self._get_benchmark_scores(task)

        with helpers.BackupDirectory(task.dir, task.conf.solution_files) as backup:
            echo.echo("Current solution backup: {}".format(backup.backup_dir))

            echo.echo("Switching to reference solution...")
            helpers.copy_files(private_solution_dir, task.dir, task.conf.solution_files)

            echo.echo("Collecting benchmark scores for reference solution...")
            private_scores = self._get_benchmark_scores(task)

        print_benchmark_reports(scores, private_scores)

        echo.blank_line()
        echo.echo("Comparing scores...")
        self._run_perf_checker(task, scores, private_scores)

    def commit(self, task, message=None, bump=False):
        self.solutions.commit(task, message, bump)

    def push_commits(self, task):
        self.solutions.push(task)

    def create_merge_request(self, task):
        self.solutions.merge(task)
