from .call import check_call, check_call_user_code
from .echo import echo
from . import highlight
from . import helpers

import os

class TaskTargets:
    def __init__(self, task, build):
        self.task = task
        self.build = build

    def _binary(self, build_dir, target):
        return os.path.join(build_dir, "tasks", self.task.fullname, "bin", target)

    def run(self, target, profile):
        echo.echo("Build and run task target {} in profile {}".format(
            highlight.smth(target), highlight.smth(profile)))

        target = self.task._target(target)

        with self.build.profile(profile) as build_dir:
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

    def _run_targets(self, targets, build_dir):
        targets = [self.task._target(t) for t in targets]

        for target in targets:
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
