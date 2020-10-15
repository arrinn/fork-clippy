import contextlib
import os
import shutil

from .call import check_call
from .compiler import ClangCxxCompiler
from .echo import echo
from .exceptions import ClientError
from . import helpers
from . import highlight


# Build directory ("build" directory in course repo)


class Build(object):
    class Profile(object):
        def __init__(self, name, entries):
            self.name = name
            self.entries = entries

    def __init__(self, git_repo):
        self.path = os.path.join(git_repo.working_tree_dir, 'build')
        self._reload_profiles()

    def _reload_profiles(self):
        self.profiles = self._read_profiles(self.path)

    @staticmethod
    def _read_profiles(build_dir):
        profiles_conf_path = os.path.join(build_dir, 'profiles.json')

        if not os.path.exists(profiles_conf_path):
            raise ClientError(
                "Build profiles not found at".format(
                    highlight.path(profiles_conf_path)))

        try:
            profiles_json = helpers.load_json(profiles_conf_path)
        except BaseException:
            raise ClientError(
                "Cannot load build profiles from {}".format(profiles_conf_path))

        profiles = []
        for name, entries in profiles_json.items():
            profiles.append(Build.Profile(str(name), entries))

        return profiles

    def list_profile_names(self):
        return [p.name for p in self.profiles]

    def _dir(self, profile):
        return os.path.join(self.path, profile.name)

    def _clear_all_dirs(self):
        for subdir in helpers.get_immediate_subdirectories(self.path):
            shutil.rmtree(subdir)

    def _create_profile_dirs(self):
        for profile in self.profiles:
            profile_dir = self._dir(profile)
            helpers.mkdir(profile_dir, parents=True)

    def reset(self):
        self._clear_all_dirs()
        self._create_profile_dirs()

    def profile_build_dirs(self):
        for profile in self.profiles:
            profile_dir = self._dir(profile)
            if not os.path.exists(profile_dir):
                helpers.mkdir(profile_dir, parents=True)
            os.chdir(profile_dir)
            yield profile, profile_dir

    def _find_profile(self, name):
        for profile in self.profiles:
            if profile.name == name:
                return profile
        raise ClientError("Build profile '{}' not found".format(name))

    @contextlib.contextmanager
    def profile(self, name):
        selected_profile = self._find_profile(name)
        cwd = os.getcwd()
        profile_dir = self._dir(selected_profile)
        if not os.path.exists(profile_dir):
            helpers.mkdir(profile_dir, parents=True)
        os.chdir(profile_dir)
        try:
            yield profile_dir
        finally:
            os.chdir(cwd)

    @staticmethod
    def _cmake_command(profile):
        def prepend(prefix, items):
            return [prefix + item for item in items]

        cxx_compiler = ClangCxxCompiler.locate()

        common_entries = [
            "CMAKE_CXX_COMPILER={}".format(cxx_compiler.binary),
            "TOOL_BUILD=ON",
            "TWIST_TESTS=ON"
        ]

        entries = profile.entries + common_entries

        echo.echo("CMake options for profile {}: {}".format(profile.name, entries))

        return ["cmake"] + prepend("-D", entries) + ["../.."]

    def cmake(self):
        helpers.check_tool("cmake")

        self._reload_profiles()

        for profile, build_dir in self.profile_build_dirs():
            echo.echo("Generate build scripts for profile {}".format(
                highlight.smth(profile.name)))
            cmake_cmd = self._cmake_command(profile)
            check_call(cmake_cmd)

    def warmup(self, target):
        self.cmake()
        for profile, dir in self.profile_build_dirs():
            echo.echo(
                "Warming up target {} for profile {}".format(
                    target, profile.name))
            check_call(["make", target])
