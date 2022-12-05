import aws_cdk
import importlib.machinery
import importlib.util
import logging
import os
import pathlib
import shutil
import subprocess
import yaml
from aws_cdk.cx_api import CloudAssembly
from botocore.credentials import Credentials
from pathlib import Path
from sceptre import exceptions
from sceptre.template_handlers import TemplateHandler
from types import ModuleType
from typing import Dict

DEFAULT_CLASS_NAME = 'CdkStack'

class CDK(TemplateHandler):
    """
    A template handler for AWS CDK templates. Using this will allow Sceptre to work with the AWS CDK to
    build and package a CDK template and deploy it with Sceptre.
    """

    _internal_stack_name = 'CDKStack'

    class PrefixLoggerAdapter(logging.LoggerAdapter):
        """
        Logger Adapter to specify a standard log entry prefix

        This logger adapter expects to be passed in a dict-like object with a
        'prefix' key, whose value is prefixed to the log message.
        """
        def process(self, msg, kwargs):
            return f'{self.extra["prefix"]} - {msg}', kwargs

    def schema(self):
        """
        Return a JSON schema of the properties that this template handler requires.

        Reference: https://github.com/Julian/jsonschema
        """
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "context": {"type": "object"},
                "class_name": {"type": "string"}
            },
            "required": [
                "path"
            ]
        }

    def _subprocess_run(self, cmd: str, env: Dict[str, str] = None) -> subprocess.CompletedProcess:
        """
        Run a command

        Args:
            cmd: str - The command to run
            env: Dict[str, str] - The environment variables to pass to the command

        Returns:
            subprocess.CompletedProcess
        """
        result = subprocess.run(
            cmd,
            env=env,
            shell=True,
            capture_output=True
        )

        return result

    def _get_envs(self) -> Dict[str, str]:
        """
        Obtains the environment variables to pass to the subprocess.

        Sceptre can assume roles, profiles, etc... to connect to AWS for a given stack. This is
        very useful. However, we need that SAME connection information to carry over to SAM when we
        invoke it. The most precise way to do this is to use the same session credentials being used
        by Sceptre for other stack operations. This method obtains those credentials and sets them
        as environment variables that are passed to the subprocess and will, in turn, be used by
        SAM CLI.

        The environment variables dict created by this method will inherit all existing
        environment variables in the current environment, but the AWS connection environment
        variables will be overridden by the ones for this stack.

        Returns:
            The dictionary of environment variables.
        """
        envs = os.environ.copy()
        # Set aws environment variables specific to whatever AWS configuration has been set on the
        # stack's connection manager.
        credentials: Credentials = self.connection_manager._get_session(
            self.connection_manager.profile,
            self.connection_manager.region,
            self.connection_manager.iam_role
        ).get_credentials()
        envs.update(
            AWS_ACCESS_KEY_ID=credentials.access_key,
            AWS_SECRET_ACCESS_KEY=credentials.secret_key,
        )

        # There might not be a session token, so if there isn't one, make sure it doesn't exist in
        # the envs being passed to the subprocess
        if credentials.token is None:
            envs.pop('AWS_SESSION_TOKEN', None)
        else:
            envs['AWS_SESSION_TOKEN'] = credentials.token

        return envs

    def _cmd_exists(self, cmd: str) -> bool:
        """
        Checks whether a specified CLI command exists.

        Args:
            cmd: str - The name of the CLI command to check

        Returns:
            bool
        """

        cmd_exists = shutil.which(cmd) is not None
        self.logger.debug(f"command '{cmd}' exists: {cmd_exists}")
        return cmd_exists

    def _node_package_exists(self, package: str) -> bool:
        """
        Checks whether a specifie Node package exists either in the workspace or global scope.

        Args:
            package: str - The name of the node package to check

        Returns:
            bool
        """

        package_exists = False
        workspace_result = self._subprocess_run(f'npm list {package}')
        self.logger.debug(f"Workspace NPM package '{package}' exists: {not bool(workspace_result.returncode)}")

        if workspace_result.returncode == 0:
            package_exists = True
        else:
            global_result = self._subprocess_run(f'npm --global list {package}')
            self.logger.debug(f"f'Global NPM package '{package}' exists: {not bool(global_result.returncode)}")

            if global_result.returncode == 0:
                package_exists = True

        return package_exists

    def _check_prerequisites(self) -> None:
        """
        Checks the command and Node package requirements for the handler.

        Raises:
            SceptreException: Command prerequisite not found
            SceptreException: Node Package prerequisite not found
        """

        # Check Command Prerequisites
        cmd_prerequisites = [
            'node',
            'npx'
        ]
        for cmd_prerequisite in cmd_prerequisites:
            if not self._cmd_exists(cmd_prerequisite):
                raise exceptions.SceptreException(f"{self.name} - Command prerequisite '{cmd_prerequisite}' not found")

        # Check Node Package Prerequisites
        node_prerequisites = [
            'cdk-assets'
        ]
        for node_prerequisite in node_prerequisites:
            if not self._node_package_exists(node_prerequisite):
                raise exceptions.SceptreException(f"{self.name} - Node Package prerequisite '{node_prerequisite}' not found")

    def _import_python_template_module(self, cdk_template_path: str) -> ModuleType:
        """
        Import the CDK Python template module.

        Args:
            cdk_template_path: str - The path of the CDK Template

        Returns:
            A ModuleType object containing the imported CDK Python module

        Raises:
            SceptreException: Template File not found
            SceptreException: importlib general exception
        """
        template_path = str(pathlib.Path('templates', cdk_template_path).as_posix())
        self.logger.debug(f'Importing CDK Python template module {template_path}')
        template_module_name = pathlib.Path(template_path).stem
        loader = importlib.machinery.SourceFileLoader(template_module_name, template_path)
        spec = importlib.util.spec_from_loader(template_module_name, loader)
        template_module = importlib.util.module_from_spec(spec)

        try:
            loader.exec_module(template_module)
        except FileNotFoundError as err:
            raise exceptions.SceptreException(f'{self.name} - Template not found: {err.filename}')
        except Exception as err:
            raise exceptions.SceptreException(f'{self.name} - {err}')

        return template_module

    def _cdk_synthesize(self, stack_name: str, template_module: ModuleType) -> CloudAssembly:
        """
        Synthesize the CDK App.

        Args:
            stack_name: str - The name of the CDK stack
            template_module: ModuleType - The imported CDK Python module

        Returns:
            A CloudAssembly object for the CDK stack

        Raises:
            SceptreException: CDK Class not found
        """
        self.logger.debug(f'CDK synthesing CdkStack Class')
        self.logger.debug(f'CDK Context: {self.cdk_context}')
        app = aws_cdk.App(context=self.cdk_context)
        try:
            stack_class = getattr(template_module, self.cdk_class_name)
        except Exception:
            raise exceptions.SceptreException(f"{self.name} - CDK Class '{self.cdk_class_name}' not found.")

        stack_class(app, stack_name, self.sceptre_user_data)
        return app.synth()

    def _publish_cdk_assets(self, app_synth: CloudAssembly) -> None:
        """
        Publishes the CDK Stack Assets.

        Args:
            app_synth: CloudAssembly - The Cloud Assembly of the CDK stack

        Raises:
            SceptreException: CDK Asset manifest artifact not found
            SceptreException: Error publishing CDK assets
        """
        asset_artifacts = None

        for artifacts in app_synth.artifacts:
            if isinstance(artifacts, aws_cdk.cx_api.AssetManifestArtifact):
                asset_artifacts = artifacts
                break
        if asset_artifacts is None:
            raise exceptions.SceptreException(f'{self.name} - CDK Asset manifest artifact not found')
        environment_variables = self._get_envs()
        self.logger.info(f'Publishing CDK assets')
        self.logger.debug(f'Assets manifest file: {asset_artifacts.file}')
        cdk_assets_result = self._subprocess_run(
            f'npx cdk-assets publish --path {asset_artifacts.file}',
            env=environment_variables)
        self.logger.info(f'{cdk_assets_result.stderr.decode()}')
        if cdk_assets_result.returncode != 0:
            raise exceptions.SceptreException(f'{self.name} - Error publishing CDK assets')

    def handle(self) -> str:
        """
        Main Sceptre CDK Handler function

        Returns:
            str - The CDK synthesised CloudFormation template
        """


        self.logger = self.PrefixLoggerAdapter(self.logger, {'prefix': self.name})

        self._check_prerequisites()

        module = self._import_python_template_module(cdk_template_path=self.cdk_template_path)
        app_synth = self._cdk_synthesize(stack_name=self._internal_stack_name, template_module=module)
        self._publish_cdk_assets(app_synth=app_synth)

        # Return synthesized template
        template = app_synth.get_stack_by_name(self._internal_stack_name).template
        return yaml.safe_dump(template)

    @property
    def cdk_template_path(self) -> Path:
        """
        CDK Template Path property handler.

        Returns:
            The specified CDK template path.
        """

        return self.arguments['path']

    @property
    def cdk_context(self) -> dict:
        """
        CDK Context property handler.

        Returns:
            The specified CDK context.
        """

        return self.arguments.get('context')

    @property
    def cdk_class_name(self) -> str:
        """
        CDK Class Name property handler.

        Returns:
            The specified CDK class name.
        """

        return self.arguments.get('class_name', DEFAULT_CLASS_NAME)
