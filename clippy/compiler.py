import subprocess

from .exceptions import ToolNotFound
from . import helpers


class ClangCxxCompiler(object):
    def __init__(self, binary):
        self.binary = binary

    @property
    def version(self):
        output = subprocess.check_output([self.binary, "--version"])
        lines = output.splitlines()
        return lines[0].strip().decode("utf-8")

    @classmethod
    def locate(cls):
        binary = helpers.locate_binary([
            "clang++-10", "clang++-9", "clang++-8", "clang++"
        ])
        if binary is None:
            raise ToolNotFound("Clang++ compiler not found")
        return cls(binary)
