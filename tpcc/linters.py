import subprocess

from .call import call_with_live_output
from .exceptions import ToolNotFound
from . import helpers


class ClangFormat(object):
    def __init__(self, binary):
        self.binary = binary

    _names = [
        "clang-format",
        "clang-format-9.0",
        "clang-format-8.0",
        "clang-format-7.0",
        "clang-format-6.0",
    ]

    @classmethod
    def locate(cls):
        binary = helpers.locate_binary(cls._names)
        if not binary:
            raise ToolNotFound(
                "'clang-format' tool not found. See https://clang.llvm.org/docs/ClangFormat.html")
        return cls(binary)

    def apply_to(self, targets, style):
        cmd = [self.binary, "-style", style, "-i"] + targets
        subprocess.check_call(cmd)

    def check(self, targets, style):
        cmd = [self.binary, "-style", style,
               "-output-replacements-xml"] + targets
        report = subprocess.check_output(cmd).decode("utf-8")

        # count replacements
        count = 0
        for line in report.splitlines():
            if line.startswith("<replacement "):
                count += 1

        return count == 0, count


class ClangTidy(object):
    def __init__(self, binary):
        self.binary = binary

    _names = [
        "clang-tidy",
        "clang-tidy-8.0",
        "clang-tidy-7.0",
        "clang-tidy-6.0",
        "clang-tidy-5.0"
    ]

    @classmethod
    def locate(cls):
        binary = helpers.locate_binary(cls._names)
        if not binary:
            raise ToolNotFound(
                "'clang-tidy' tool not found. See http://clang.llvm.org/extra/clang-tidy/")
        return cls(binary)

    def _make_command(self, targets, include_dirs, fix=True):
        cmd = [self.binary] + targets + ["--quiet"]
        if fix:
            cmd.append("--fix")

        cmd.append("--")

        # TODO(Lipovsky): customize
        cmd.append("-std=c++17")

        for dir in include_dirs:
            cmd.extend(["-I", str(dir)])

        return cmd

    def check(self, targets, include_dirs):
        cmd = self._make_command(targets, include_dirs, fix=False)
        exit_code = call_with_live_output(cmd)
        # todo: separate style errors from all other errors
        return exit_code == 0

    def fix(self, targets, include_dirs):
        cmd = self._make_command(targets, include_dirs, fix=True)
        call_with_live_output(cmd)  # intentionally ignore exit code
