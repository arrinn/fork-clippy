from .call import check_call, check_call_user_code
from .echo import echo
from . import highlight
from . import helpers

import os
import datetime

class TaskTargets:
    def __init__(self, task, build):
        self.task = task
        self.build = build

    def _binary(self, build_dir, target):
        return os.path.join(build_dir, "tasks", self.task.fullname, "bin", target)

    def run(self, target_name, profile):
        echo.echo("Build and run task target {} in profile {}".format(
            highlight.smth(target_name), highlight.smth(profile)))

        target = self.task._target(target_name)

        with self.build.profile(profile) as build_dir:
            with echo.timed("Target {}".format(highlight.smth(target_name))):
                # Build
                check_call(helpers.make_target_command(target))
                # Run
                binary = self._binary(build_dir, target)
                check_call_user_code([binary])


class TestRunner:
    def __init__(self, task, build):
        self.task = task
        self.build = build

    def _binary(self, build_dir, target):
        return os.path.join(build_dir, "tasks", self.task.fullname, "bin", target)

    def _run_targets(self, task_targets, build_dir):
        make_targets = [self.task._target(name) for name in task_targets]

        for name, target in zip(task_targets, make_targets):
            with echo.timed("Target {}".format(highlight.smth(name))):
                # Build
                check_call(helpers.make_target_command(target))
                # Run
                binary = self._binary(build_dir, target)
                check_call_user_code([binary])

    def _run_tests_with_profile(self, targets, profile_name):
        with self.build.profile(profile_name) as build_dir:
            echo.echo("Test targets {} in profile {}".format(
                highlight.smth(targets), highlight.smth(profile_name)))

            self._run_targets(targets, build_dir)

    def run_tests(self, profile=None):
        targets = self.task.conf.test_targets

        if profile:
            profiles = [profile]
        else:
            profiles = self.task.conf.test_profiles

        for profile in profiles:
            self._run_tests_with_profile(targets, profile)

        echo.echo("All {}/{} tests completed!".format(
            highlight.homework(self.task.homework), highlight.task(self.task.name)))

def create_test_runner(task, build):
    return TestRunner(task, build)
