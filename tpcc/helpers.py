import glob
import importlib
import json
import os
import shutil
import subprocess

from .exceptions import ToolNotFound, ClientError

try:
    from shutil import which
except ImportError:
    # python2.7 compatibility

    def which(tool):
        which = subprocess.Popen(["which", tool], stdout=subprocess.PIPE)
        stdout, stderr = which.communicate()
        if which.returncode:
            return None

        bin_path = stdout.strip().decode("utf-8")
        return bin_path


def locate_binary(possible_names):
    for name in possible_names:
        binary = which(name)
        if binary:
            return binary
    return None


def check_tool(name):
    binary = which(name)
    if not binary:
        raise ToolNotFound("Cannot locate a tool: '{}'".format(name))


def get_immediate_subdirectories(dir):
    return [os.path.join(dir, child) for child in os.listdir(
        dir) if os.path.isdir(os.path.join(dir, child))]


def mkdir(dir, parents=False):
    cmd = ["mkdir"]
    if parents:
        cmd.append("-p")
    cmd.append(dir)
    subprocess.check_call(cmd)


def glob_expand(patterns):
    files = set()
    for pattern in patterns:
        files.update(glob.glob(pattern))
    return list(files)


def filter_out(items, blacklist):
    return [item for item in items if item not in blacklist]


def load_json(path):
    if not os.path.exists(path):
        raise RuntimeError("File not found: {}".format(path))

    with open(path, "r") as f:
        return json.load(f)


def get_repo_name(url):
    url = url.rstrip('/')

    name = url.split('/')[-1]
    # rstrip .git
    if name.endswith(".git"):
        name = name[:-4]
    return name


def copy_files(source_dir, dest_dir, files):
    for file in files:
        source_file_path = os.path.join(source_dir, file)
        if not os.path.exists(source_file_path):
            raise RuntimeError(
                "File '{}' not found in '{}'".format(
                    file, source_dir))

    for file in files:
        source_file_path = os.path.join(source_dir, file)
        shutil.copy(source_file_path, dest_dir)


class BackupDirectory:
    def __init__(self, dir, files):
      self.dir = dir
      self.backup_dir = os.path.join(self.dir, ".backup")
      self.files = files

    def __enter__(self):
      os.makedirs(self.backup_dir, exist_ok=True)
      copy_files(self.dir, self.backup_dir, self.files)
      return self

    def __exit__(self, *args):
      copy_files(self.backup_dir, self.dir, self.files)
      shutil.rmtree(self.backup_dir)


def try_get_branch(gitlab_project, branch_name):
    for branch in gitlab_project.branches.list(all=True):
        if branch.name == branch_name:
            return branch
    return None


def check_gitlab(url):
    allowed_prefixes = ["https://gitlab.com/", "git@gitlab.com:"]
    for prefix in allowed_prefixes:
        if url.startswith(prefix):
            return

    raise ClientError(
        "Expected gitlab.com repository, provided: '{}'".format(url))


def git_repo_root_dir(cwd):
    output = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    return output.strip().decode("utf-8")


def load_module(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
