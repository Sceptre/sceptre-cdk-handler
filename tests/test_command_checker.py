import shutil
import subprocess
from logging import Logger
from unittest import TestCase
from unittest.mock import create_autospec, Mock

from sceptre_cdk_handler.command_checker import CommandChecker


class TestCommandChecker(TestCase):

    def setUp(self):
        self.which_func = create_autospec(shutil.which, side_effect=self.which)
        self.subprocess_run_func = create_autospec(subprocess.run, side_effect=self.subprocess_run)
        self.logger = Mock(Logger)

        self.commands = {
            "exists": "/path/to/executable"
        }

        self.local_npm_packages = {
            'local': True
        }

        self.global_npm_packages = {
            'global': True
        }

        self.checker = CommandChecker(
            self.logger,
            which_func=self.which_func,
            subprocess_run=self.subprocess_run_func
        )

    def which(self, cmd):
        return self.commands.get(cmd)

    def subprocess_run(self, cmd, *, shell, stdout, stderr):
        self.assertTrue(shell)
        self.assertIs(stdout, subprocess.DEVNULL)
        self.assertIs(stderr, subprocess.DEVNULL)
        command_segments = cmd.split(' ')
        if command_segments[:2] == ['npm', 'list']:
            package_name = command_segments[2]
            found = self.local_npm_packages.get(package_name, False)
        elif command_segments[:3] == ['npm', '--global', 'list']:
            package_name = command_segments[3]
            found = self.global_npm_packages.get(package_name, False)
        else:
            raise AssertionError("Unexpected command!")

        return Mock(returncode=0 if found else 1)

    def test_cmd_exists__which_returns_none__returns_false(self):
        self.assertFalse(self.checker.cmd_exists('nonexistant'))

    def test_cmd_exists__which_returns_value__returns_true(self):
        self.assertTrue(self.checker.cmd_exists('exists'))

    def test_node_package_exists__exists_locally__returns_true(self):
        self.assertTrue(self.checker.node_package_exists('local'))

    def test_node_package_exists__exists_globally__returns_true(self):
        self.assertTrue(self.checker.node_package_exists('global'))

    def test_node_package_exists__does_not_exist__returns_false(self):
        self.assertFalse(self.checker.node_package_exists('nonexistant'))
