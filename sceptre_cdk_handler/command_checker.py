import shutil
import subprocess
from logging import Logger


class CommandChecker:
    """A utility for checking if specific commands and node packages exist in the environment."""
    def __init__(
        self,
        logger: Logger,
        *,
        subprocess_run=subprocess.run,
        which_func=shutil.which
    ):
        self._logger = logger
        self._subprocess_run = subprocess_run
        self._which = which_func

    def cmd_exists(self, cmd: str) -> bool:
        """
        Checks whether a specified CLI command exists.

        Args:
            cmd: The name of the CLI command to check

        Returns:
            bool
        """

        cmd_exists = self._which(cmd) is not None
        self._logger.debug(f"command '{cmd}' exists: {cmd_exists}")
        return cmd_exists

    def node_package_exists(self, package: str) -> bool:
        """
        Checks whether a specific Node package exists either in the workspace or global scope.

        Args:
            package: str - The name of the node package to check
        """
        workspace_result = self._subprocess_run(f'npm list {package}', shell=True)
        self._logger.debug(f"Workspace NPM package '{package}' exists: {not bool(workspace_result.returncode)}")

        if workspace_result.returncode == 0:
            return True

        global_result = self._subprocess_run(f'npm --global list {package}', shell=True)
        self._logger.debug(f"f'Global NPM package '{package}' exists: {not bool(global_result.returncode)}")

        return global_result.returncode == 0
