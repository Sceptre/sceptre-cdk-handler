import importlib.machinery
import importlib.util
import logging
import os
import pathlib
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

import aws_cdk
import yaml
from aws_cdk.cx_api import CloudAssembly
from botocore.credentials import Credentials
from sceptre import exceptions
from sceptre.connection_manager import ConnectionManager
from sceptre.helpers import normalise_path
from sceptre.template_handlers import TemplateHandler

try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol

DEFAULT_CLASS_NAME = 'CdkStack'


class SceptreCdkStackConstructor(Protocol):
    def __call__(self, scope: aws_cdk.App, id: str, sceptre_user_data: Any) -> aws_cdk.Stack: ...


class ClassImporter:
    def import_class(self, template_path: Path, class_name: str) -> SceptreCdkStackConstructor:
        """
        Import the CDK Python template module.

        Args:
            template_path: The path of the CDK Template
            class_name: The name of the class

        Returns:
            A ModuleType object containing the imported CDK Python module

        Raises:
            SceptreException: Template File not found
            SceptreException: importlib general exception
        """
        template_module_name = template_path.stem
        loader = importlib.machinery.SourceFileLoader(template_module_name, str(template_path))
        spec = importlib.util.spec_from_loader(template_module_name, loader)
        template_module = importlib.util.module_from_spec(spec)
        loader.exec_module(template_module)

        try:
            return getattr(template_module, class_name)
        except AttributeError:
            raise exceptions.SceptreException(
                f"No class named  {class_name} on template at {template_path}"
            )


class CdkBuilder:
    _internal_stack_name = 'CDKStack'

    def __init__(
        self,
        logger: logging.Logger,
        connection_manager: ConnectionManager,
        *,
        subprocess_run=subprocess.run,
        app_class=aws_cdk.App,
    ):
        self._logger = logger
        self._connection_manager = connection_manager
        self._subprocess_run = subprocess_run
        self._app_class = app_class

    def build_template(
        self,
        stack_class: SceptreCdkStackConstructor,
        cdk_context: Optional[dict],
        sceptre_user_data: Any
    ) -> dict:
        assembly = self._synthesize(stack_class, cdk_context, sceptre_user_data)
        self._publish(assembly)
        template = self._get_template(assembly)
        return template

    def _synthesize(
        self,
        stack_class: SceptreCdkStackConstructor,
        cdk_context: Optional[dict],
        sceptre_user_data: Any
    ) -> CloudAssembly:
        self._logger.debug(f'CDK synthesing CdkStack Class')
        self._logger.debug(f'CDK Context: {cdk_context}')
        app = self._app_class(context=cdk_context)
        stack_class(app, self._internal_stack_name, sceptre_user_data)
        return app.synth()

    def _publish(self, cloud_assembly: CloudAssembly):
        asset_artifacts = None

        for artifacts in cloud_assembly.artifacts:
            if isinstance(artifacts, aws_cdk.cx_api.AssetManifestArtifact):
                asset_artifacts = artifacts
                break
        if asset_artifacts is None:
            raise exceptions.SceptreException(f'CDK Asset manifest artifact not found')

        environment_variables = self._get_envs()
        self._logger.info(f'Publishing CDK assets')
        self._logger.debug(f'Assets manifest file: {asset_artifacts.file}')
        self._subprocess_run(
            f'npx cdk-assets publish --path {asset_artifacts.file}',
            env=environment_variables
        )

    def _get_template(self, cloud_assembly: CloudAssembly) -> dict:
        return cloud_assembly.get_stack_by_name(self._internal_stack_name).template

    def _run_command(self, command: str, env: Dict[str, str] = None):
        # TODO: Determine how we need to deal with current working directory and such
        result = subprocess.run(
            command,
            env=env,
            shell=True,
            stdout=sys.stderr,
            check=True
        )

        return result

    def _get_envs(self) -> Dict[str, str]:
        """
        Obtains the environment variables to pass to the subprocess.

        Sceptre can assume roles, profiles, etc... to connect to AWS for a given stack. This is
        very useful. However, we need that SAME connection information to carry over to CDK when we
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
        credentials: Credentials = self._connection_manager._get_session(
            self._connection_manager.profile,
            self._connection_manager.region,
            self._connection_manager.iam_role
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


class CDK(TemplateHandler):
    """
    A template handler for AWS CDK templates. Using this will allow Sceptre to work with the AWS CDK to
    build and package a CDK template and deploy it with Sceptre.
    """

    def __init__(
        self,
        name: str,
        arguments: dict = None,
        sceptre_user_data: Any = None,
        connection_manager: ConnectionManager = None,
        stack_group_config: dict = None,
        *,
        importer_class=ClassImporter,
        cdk_builder_class=CdkBuilder
    ):
        super().__init__(
            name=name,
            arguments=arguments,
            sceptre_user_data=sceptre_user_data,
            connection_manager=connection_manager,
            stack_group_config=stack_group_config
        )
        self._importer = importer_class()
        self._cdk_buidler = cdk_builder_class(self.logger, self.connection_manager)

    @property
    def cdk_template_path(self) -> Path:
        """
        CDK Template Path property handler.

        Returns:
            The specified CDK template path.
        """

        return self._resolve_template_path(self.arguments['path'])

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

    def handle(self) -> str:
        """
        Main Sceptre CDK Handler function

        Returns:
            str - The CDK synthesised CloudFormation template
        """
        self._check_prerequisites()
        stack_class = self._importer.import_class(self.cdk_template_path, self.cdk_class_name)
        template_dict = self._cdk_buidler.build_template(
            stack_class,
            self.cdk_context,
            self.sceptre_user_data
        )
        return yaml.safe_dump(template_dict)

    def _resolve_template_path(self, template_path):
        """
        Return the project_path joined to template_path as
        a string.

        Note that os.path.join defers to an absolute path
        if the input is absolute.
        """
        return pathlib.Path(
            self.stack_group_config["project_path"],
            "templates",
            normalise_path(template_path)
        )
