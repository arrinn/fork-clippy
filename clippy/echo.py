import json
import sys
import contextlib

from . import highlight
from . import helpers

class Echo(object):
    def echo(self, line):
        sys.stdout.write(line + '\n')

    def write(self, text):
        sys.stdout.write(text + '\n')

    def note(self, line):
        sys.stdout.write(highlight.smth(line) + '\n')

    def success(self, text):
        sys.stdout.write(highlight.success(text) + '\n')

    def error(self, text):
        sys.stdout.write(highlight.error(text) + '\n')

    def json(self, data):
        sys.stdout.write(json.dumps(data, sort_keys=True, indent=4, separators=(',', ': ')) + '\n')

    def separator_line(self):
        sys.stdout.write(('-' * 80) + '\n')

    def blank_line(self):
        sys.stdout.write('\n')

    def done(self):
        self.blank_line()
        self.success("Done")

    @contextlib.contextmanager
    def timed(self, task):
        stop_watch = helpers.StopWatch()
        yield
        seconds = stop_watch.elapsed_seconds()
        self.echo("{} completed in {:.2f} seconds".format(task, seconds))

echo = Echo()
