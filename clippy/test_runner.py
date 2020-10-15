from .call import check_call, check_call_user_code
from .echo import echo
from . import highlight

import os

class TestRunner:
    def __init__(self, task, build):
        self.task = task
        self.build = build

    def _binary(self, build_dir, target):
        return os.path.join(build_dir, "tasks", self.task.fullname, "bin", target)

    def _run_tests(self, targets, build_dir):
        targets = [self.task._target(t) for t in targets]

        for target in targets:
            # Build
            check_call(["make", target])
            # Run
            binary = self._binary(build_dir, target)
            check_call_user_code([binary])

    def _run_tests_with_profile(self, targets, profile_name):
        with self.build.profile(profile_name) as build_dir:
            echo.echo("Test targets {} in profile {}".format(
                highlight.smth(targets), highlight.smth(profile_name)))

            self._run_tests(targets, build_dir)

    def _run_test_group(self, test_group):
        # echo.echo("Test targets {} in profiles {}".format(
        #    highlight.smth(test_group.targets), highlight.smth(test_group.profiles)))

        for profile_name in test_group.profiles:
            self._run_tests_with_profile(test_group.targets, profile_name)

    def run_all_tests(self):
        for test_group in self.task.conf.tests:
            self._run_test_group(test_group)

        echo.echo("All {}/{} tests completed!".format(
            highlight.homework(self.task.homework), highlight.task(self.task.name)))

    def run_all_profile_tests(self, profile_name):
        for test_group in self.task.conf.tests:
            if profile_name in test_group.profiles:
                self._run_tests_with_profile(test_group.targets, profile_name)

def create_test_runner(task, build):
    return TestRunner(task, build)
