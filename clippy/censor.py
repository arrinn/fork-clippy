from .echo import echo
from .exceptions import ClientError
from . import helpers

import os


class CensorRule:
    def __init__(self, json_config):
        self.config = json_config

    @property
    def hint(self):
        return self.config.get("hint", None)

    @property
    def patterns(self):
        return self.config["patterns"]

    @property
    def files(self):
        return self.config.get("files", None)


class Censor:
    def __init__(self, config):
        self.forbidden = self._get_rules(config)

    @staticmethod
    def _get_rules(config):
        rules = []
        for json in config.get("forbidden"):
            rules.append(CensorRule(json))
        return rules

    @staticmethod
    def _files_to_check(task, rule):
        names = rule.files or task.conf.lint_files or task.conf.solution_files
        return helpers.cpp_files(helpers.all_files(task.dir, names))

    @staticmethod
    def _read_file_content(path):
        return open(path, 'rb').read().decode("utf-8").rstrip()

    @staticmethod
    def _error_report(file, pattern, rule):
        error = "Forbidden pattern '{}' found in file '{}'".format(
            pattern, file)

        if rule.hint:
            error = error + ", hint: {}".format(rule.hint)

        return error

    @staticmethod
    def _found(source_code, pattern):
        return source_code.find(pattern) != -1

    def _check_rule(self, task, rule):
        for fpath in self._files_to_check(task, rule):
            source_code = self._read_file_content(fpath)
            for pattern in rule.patterns:
                if self._found(source_code, pattern):
                    raise ClientError(self._error_report(fpath, pattern, rule))

    def check(self, task):
        echo.echo("Censoring...")

        rules = self.forbidden + task.conf.forbidden

        os.chdir(task.dir)

        for rule in rules:
            self._check_rule(task, rule)
