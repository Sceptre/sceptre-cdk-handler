import logging
import os
import subprocess
import sys
from typing import Protocol, Any, Optional, Dict, Type

import aws_cdk
from aws_cdk.cx_api import CloudAssembly
from botocore.credentials import Credentials
from sceptre import exceptions
from sceptre.connection_manager import ConnectionManager


class SceptreCdkStackConstructor(Protocol):
    def __call__(self, scope: aws_cdk.App, id: str, sceptre_user_data: Any) -> aws_cdk.Stack: ...


class CdkBuilder:
    STACK_LOGICAL_ID = 'CDKStack'

    def __init__(
        self,
        logger: logging.Logger,
        connection_manager: ConnectionManager,
        *,
        subprocess_run=subprocess.run,
        app_class=aws_cdk.App,
        environment_variables=os.environ
    ):
        self._logger = logger
        self._connection_manager = connection_manager
        self._subprocess_run = subprocess_run
        self._app_class = app_class
        self._environment_variables = environment_variables

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
        stack_class(app, self.STACK_LOGICAL_ID, sceptre_user_data)
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
        self._run_command(
            f'npx cdk-assets -v publish --path {asset_artifacts.file}',
            env=environment_variables
        )

    def _get_template(self, cloud_assembly: CloudAssembly) -> dict:
        return cloud_assembly.get_stack_by_name(self.STACK_LOGICAL_ID).template

    def _run_command(self, command: str, env: Dict[str, str] = None):
        # We're assuming here that the cwd is the directory to run the command from. I'm not certain
        # that will always be correct...
        result = self._subprocess_run(
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
        envs = self._environment_variables.copy()
        envs.pop("AWS_PROFILE", None)
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
            # Most AWS SDKs use AWS_DEFAULT_REGION for the region
            AWS_DEFAULT_REGION=self._connection_manager.region,
            # CDK frequently uses CDK_DEFAULT_REGION in its docs
            CDK_DEFAULT_REGION=self._connection_manager.region,
            # cdk-assets requires AWS_REGION to determine what region's STS endpoint to use
            AWS_REGION=self._connection_manager.region
        )

        # There might not be a session token, so if there isn't one, make sure it doesn't exist in
        # the envs being passed to the subprocess
        if credentials.token is None:
            envs.pop('AWS_SESSION_TOKEN', None)
        else:
            envs['AWS_SESSION_TOKEN'] = credentials.token

        return envs
