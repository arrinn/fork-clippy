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

    def _run_all_tests(self, build_dir):
        for target in self.task.test_targets:
            # Build
            check_call(["make", target])
            # Run
            binary = self._binary(build_dir, target)
            check_call_user_code([binary])

    def test_profile(self, profile_name):
        with self.build.profile(profile_name) as build_dir:
            echo.echo("Test task {}/{} in profile {}".format(
                highlight.homework(self.task.homework), highlight.task(self.task.name), highlight.smth(profile_name)))

            self._run_all_tests(build_dir)

    def test_all_profiles(self):
        blacklist = ["Release"]  # almost all

        test_profiles = self.task.conf.test_profiles
        if not test_profiles:
            test_profiles = self.build.list_profile_names()

        echo.echo("Build profiles: {}".format(test_profiles))

        for profile_name in test_profiles:
            if profile_name in blacklist:
                continue
            self.test_profile(profile_name)

        echo.echo("All {}/{} tests completed!".format(
            highlight.homework(self.task.homework), highlight.task(self.task.name)))


def create_test_runner(task, build):
    return TestRunner(task, build)
