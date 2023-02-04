import logging
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, Type

import aws_cdk
from aws_cdk.cx_api import CloudAssembly
from cdk_bootstrapless_synthesizer import BootstraplessStackSynthesizer
from sceptre import exceptions
from sceptre.connection_manager import ConnectionManager
from sceptre.exceptions import TemplateHandlerArgumentsInvalidError


class SceptreCdkStack(aws_cdk.Stack):
    def __init__(self, scope: aws_cdk.App, id: str, sceptre_user_data: Any, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.sceptre_user_data = sceptre_user_data


class CdkBuilder(ABC):
    """A base class for CDK builders to define the interface they all must meet."""
    STACK_LOGICAL_ID = 'CDKStack'

    @abstractmethod
    def build_template(
        self,
        stack_class: Type[SceptreCdkStack],
        cdk_context: Optional[dict],
        sceptre_user_data: Any
    ) -> dict: ...


class BootstrappedCdkBuilder(CdkBuilder):
    """A CdkBuilder for stacks utilizing the CDK bootstrap stack for asset-related actions."""
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
        stack_class: Type[SceptreCdkStack],
        cdk_context: Optional[dict],
        sceptre_user_data: Any
    ) -> dict:
        assembly = self._synthesize(stack_class, cdk_context, sceptre_user_data)
        self._publish(assembly)
        template = self._get_template(assembly)
        return template

    def _synthesize(
        self,
        stack_class: Type[SceptreCdkStack],
        cdk_context: Optional[dict],
        sceptre_user_data: Any
    ) -> CloudAssembly:
        self._logger.debug(f'CDK synthesizing stack class: {stack_class.__name__}')
        self._logger.debug(f'CDK Context: {cdk_context}')
        app = self._app_class(context=cdk_context)
        stack_class(app, self.STACK_LOGICAL_ID, sceptre_user_data)
        return app.synth()

    def _publish(self, cloud_assembly: CloudAssembly):
        asset_artifacts = self._get_assets_manifest(cloud_assembly)
        if self._only_asset_is_template(asset_artifacts):
            # Sceptre already has a mechanism to upload the template if configured. We don't
            # need to deploy assets if the only asset is the template
            self._logger.debug("Only asset is template; Skipping asset upload.")
            return

        environment_variables = self._get_envs()
        self._logger.info('Publishing CDK assets')
        self._logger.debug(f'Assets manifest file: {asset_artifacts.file}')
        self._run_command(
            f'npx cdk-assets -v publish --path {asset_artifacts.file}',
            env=environment_variables
        )

    def _get_assets_manifest(self, cloud_assembly):
        asset_artifacts = None
        for artifacts in cloud_assembly.artifacts:
            if isinstance(artifacts, aws_cdk.cx_api.AssetManifestArtifact):
                asset_artifacts = artifacts
                break
        if asset_artifacts is None:
            raise exceptions.SceptreException('CDK Asset manifest artifact not found')
        return asset_artifacts

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
        envs = self._connection_manager.create_session_environment_variables()
        envs.update(
            # CDK frequently uses CDK_DEFAULT_REGION in its docs
            CDK_DEFAULT_REGION=self._connection_manager.region,
        )
        return envs

    def _only_asset_is_template(self, asset_artifacts: aws_cdk.cx_api.AssetManifestArtifact):
        manifest_contents = asset_artifacts.contents
        if manifest_contents.docker_images:
            return False

        keys = list(manifest_contents.files.keys())
        expected_template = f'{self.STACK_LOGICAL_ID}.template.json'
        return keys == [expected_template]


class BootstraplessCdkBuilder(BootstrappedCdkBuilder):
    """A CdkBuilder that does not use the CDK bootstrap stack for asset actions; Instead, specific
    asset-required resources can be specified in the synthesizer_config.
    """
    def __init__(
        self,
        logger: logging.Logger,
        connection_manager: ConnectionManager,
        synthesizer_config: dict,
        *,
        subprocess_run=subprocess.run,
        app_class=aws_cdk.App,
        synthesizer_class=BootstraplessStackSynthesizer
    ):
        super().__init__(
            logger,
            connection_manager,
            subprocess_run=subprocess_run,
            app_class=app_class,
        )
        self._synthesizer_config = synthesizer_config
        self._synthesizer_class = synthesizer_class

    def _synthesize(
        self,
        stack_class: Type[SceptreCdkStack],
        cdk_context: Optional[dict],
        sceptre_user_data: Any
    ) -> CloudAssembly:
        self._logger.debug(f'CDK synthesizing stack class: {stack_class.__name__}')
        self._logger.debug(f'CDK Context: {cdk_context}')
        app = self._app_class(context=cdk_context)
        try:
            synthesizer = self._synthesizer_class(**self._synthesizer_config)
        except TypeError as e:
            raise TemplateHandlerArgumentsInvalidError(
                "Error encountered attempting to instantiate the BootstraplessSynthesizer with the "
                f"specified deployment config: {e}"
            ) from e

        stack_class(app, self.STACK_LOGICAL_ID, sceptre_user_data, synthesizer=synthesizer)
        return app.synth()
