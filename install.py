#!/usr/bin/env python

from __future__ import print_function

import argparse
import subprocess
import os
import platform
import shutil
import sys

# --------------------------------------------------------------------

try:
    input = raw_input
except NameError:
    pass


CLIENT_PROXY_TEMPLATE = '''#!/bin/sh
exec '{0}/venv/bin/python' '{0}/client.py' "$@"
'''


def query_yesno(string):
    result = input(string + ' [Y/n] ').strip().lower()
    return not result or result.startswith('y')


class Installer(object):
    def __init__(self):
        self.installer_dir = os.path.dirname(os.path.realpath(__file__))
        self.venv_dir = os.path.join(self.installer_dir, "venv")

        os.chdir(self.installer_dir)

    def check_required_files(self):
        required = ['requirements.txt']

        for f in required:
            f_path = os.path.join(self.installer_dir, f)
            if not os.path.exists(f_path):
                self._fail(
                    "{} not found in installer directory '{}'".format(
                        f, self.installer_dir))

    @staticmethod
    def _fail(reason):
        sys.stderr.write("Installation FAILED: {}\n".format(reason))
        sys.exit(1)

    @staticmethod
    def _interrupt(reason):
        sys.stderr.write("Installation INTERRUPTED: {}".format(reason))

    @staticmethod
    def _run(command, **kwargs):
        print("Running command {}".format(command))
        try:
            subprocess.check_call(command, **kwargs)
        except subprocess.CalledProcessError as error:
            Installer._fail(str(error))

    # Install

    def _choose_profile(self):
        system = platform.system()

        profiles = {
            'Linux': '.bashrc',
            'Darwin': '.bash_profile'
        }

        return profiles.get(system, '.profile')

    def _profile_path(self, profile):
        return os.path.expanduser('~/{}'.format(profile))

    def _update_profile(self):
        profile = self._choose_profile()

        if not query_yesno('Add tpcc client to PATH in {}?'.format(profile)):
            return

        command = "if [ -f '{0}' ]; then . '{0}'; fi".format(
            os.path.join(self.installer_dir, 'activate'))
        with open(self._profile_path(profile), 'a') as f:
            f.write('\n' + command + '\n')

    def _is_virtualenv_installed(self):
        try:
            subprocess.check_call(['python3', '-m', 'virtualenv', '--version'])
        except subprocess.CalledProcessError as error:
            return False
        return True

    def _install_virtualenv_linux(self):
        distname, _, _ = platform.linux_distribution()

        if distname == 'Ubuntu':
            if query_yesno('Install virtualenv via apt-get?'):
                self._run(['sudo', 'apt-get', 'update'])
                self._run(['sudo', 'apt-get', 'install', 'python3-virtualenv'])
            else:
                self._interrupt('Please install virtualenv manually.')
        elif distname == 'arch':
            if query_yesno('Install virtualenv via pacman?'):
                self._run(['sudo', 'pacman', '-S',
                           'python-virtualenv', '--noconfirm'])
            else:
                self._interrupt('Please install virtualenv manually.')

    def _install_virtualenv_darwin(self):
        if query_yesno('Install virtualenv using pip?'):
            self._run(['python3', '-m', 'pip', 'install', 'virtualenv'])
        else:
            self._interrupt('Please install virtualenv manually.')

    def _install_virtualenv(self):
        system = platform.system()
        if system == 'Linux':
            self._install_virtualenv_linux()
        elif system == 'Darwin':
            self._install_virtualenv_darwin()
        else:
            self._fail("System is not supported: '{}'".format(system))

    def _create_venv(self):
        os.chdir(self.installer_dir)

        print("Creating virtual environment...")
        self._run(['python3', '-m', 'venv', 'venv'])
        #self._run(['python3', '-m', 'virtualenv', 'venv', '-p', 'python3'])

        venv_pip = os.path.join(self.venv_dir, 'bin/pip')

        print("Upgrading pip...")
        self._run([venv_pip, 'install', '--upgrade', 'pip'])

        print("Installing requirements...")
        self._run([venv_pip, 'install', '-r', 'requirements.txt'])

        print("Virtual environment prepared: '{}'".format('venv'))

    def _create_proxy(self, alias):
        print('Creating client proxy...')
        if not os.path.isdir('bin'):
            os.mkdir('bin')
        with open('bin/' + alias, 'w') as f:
            f.write(CLIENT_PROXY_TEMPLATE.format(self.installer_dir))
        os.chmod('bin/' + alias, 0o755)

    def _create_path_file(self):
        print('Creating activation file...')
        with open('activate', 'w') as f:
            f.write(
                "export PATH='{}':$PATH\n".format(
                    os.path.join(
                        self.installer_dir,
                        'bin')))

    def install(self, alias):
        if not self._is_virtualenv_installed():
            print('You seem to have no virtualenv installed.')
            self._install_virtualenv()
        self._create_venv()
        self._create_proxy(alias)
        self._create_path_file()
        self._update_profile()

    def _remove_env(self):
        print("Removing existing venv directory...")

        if not os.path.exists(self.venv_dir):
            return

        if not os.path.isdir(self.venv_dir):
            self._fail("Directory expected: '{}'".format(self.venv_dir))

        # TODO(Lipovsky): more checks

        shutil.rmtree(self.venv_dir)

# --------------------------------------------------------------------


def cli():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        '-a',
        '--alias',
        default='tpcc',
        help="alias for client tool")

    return parser.parse_args()


def install(installer, args):
    installer.install(args.alias)

    print("\nRunning '{} help' to check that client works...".format(args.alias))
    subprocess.check_call(['bash', '-i', '-c', args.alias + ' help'])
    print("\nStart a new shell for the changes to take effect.")
    print("Type '{} {{cmd}}' for usage.".format(args.alias))


def main():
    print("Python version: {}".format(platform.python_version()))

    installer = Installer()

    args = cli()

    try:
        install(installer, args)
    except KeyboardInterrupt:
        sys.stderr.write("Exiting on user request\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
