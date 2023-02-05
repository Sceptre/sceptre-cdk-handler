import json
import logging
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from tempfile import TemporaryDirectory
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

    def __init__(
        self,
        logger: logging.Logger,
        connection_manager: ConnectionManager,
        *,
        subprocess_run=subprocess.run,
    ):
        """A base class in the hierarchy for CdkBuilders that import and use a Python Stack Class

        Args:
            logger: The Template Handler's logger
            connection_manager: The Template Handler's ConnectionManager
            subprocess_run: An callable used to run subprocesses
        """
        self._logger = logger
        self._connection_manager = connection_manager
        self._subprocess_run = subprocess_run

    @abstractmethod
    def build_template(
        self,
        cdk_context: Optional[dict],
        sceptre_user_data: Any
    ) -> dict: ...

    def _publish_artifacts(self, artifact_file: str, envs: Dict[str, str]):
        self._logger.info('Publishing CDK assets')
        self._logger.debug(f'Assets manifest file: {artifact_file}')
        self._run_command(
            f'npx cdk-assets -v publish --path {artifact_file}',
            env=envs
        )

    def _run_command(self, command: str, env: Dict[str, str] = None, cwd: str = None):
        # We're assuming here that the cwd is the directory to run the command from. I'm not certain
        # that will always be correct...
        result = self._subprocess_run(
            command,
            env=env,
            shell=True,
            stdout=sys.stderr,
            check=True,
            cwd=cwd
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


class PythonCdkBuilder(CdkBuilder):
    def __init__(
        self,
        logger: logging.Logger,
        connection_manager: ConnectionManager,
        stack_class: Type[SceptreCdkStack],
        *,
        subprocess_run=subprocess.run,
        app_class=aws_cdk.App,
    ):
        """A base class in the hierarchy for CdkBuilders that import and use a Python Stack Class

        Args:
            logger: The Template Handler's logger
            connection_manager: The Template Handler's ConnectionManager
            stack_class: The stack class that will be synthesized
            subprocess_run: An callable used to run subprocesses
            app_class: The CDK App class used to synthesize the template
        """
        super().__init__(
            logger,
            connection_manager,
            subprocess_run=subprocess_run,
        )
        self._stack_class = stack_class
        self._app_class = app_class

    def build_template(
        self,
        cdk_context: Optional[dict],
        sceptre_user_data: Any
    ) -> dict:
        assembly = self._synthesize(cdk_context, sceptre_user_data)
        manifest_artifact = self._get_assets_manifest(assembly)
        if self._only_asset_is_template(manifest_artifact):
            # Sceptre already has a mechanism to upload the template if configured. We don't
            # need to deploy assets if the only asset is the template
            self._logger.debug("Only asset is template; Skipping asset upload.")
        else:
            environment_variables = self._get_envs()
            self._publish_artifacts(manifest_artifact.file, environment_variables)

        template = self._get_template(assembly)
        return template

    def _get_assets_manifest(self, cloud_assembly: CloudAssembly):
        asset_artifacts = None
        for artifacts in cloud_assembly.artifacts:
            if isinstance(artifacts, aws_cdk.cx_api.AssetManifestArtifact):
                asset_artifacts = artifacts
                break
        if asset_artifacts is None:
            raise exceptions.SceptreException('CDK Asset manifest artifact not found')
        return asset_artifacts

    @abstractmethod
    def _synthesize(self, cdk_context: Optional[dict], sceptre_user_data: Any): ...

    def _get_template(self, cloud_assembly: CloudAssembly) -> dict:
        return cloud_assembly.get_stack_by_name(self.STACK_LOGICAL_ID).template

    def _only_asset_is_template(self, asset_artifacts: aws_cdk.cx_api.AssetManifestArtifact):
        manifest_contents = asset_artifacts.contents
        if manifest_contents.docker_images:
            return False

        keys = list(manifest_contents.files.keys())
        expected_template = f'{self.STACK_LOGICAL_ID}.template.json'
        return keys == [expected_template]


class BootstrappedCdkBuilder(PythonCdkBuilder):
    """A PythonCdkBuilder that leverages the CDK Bootstrap Stack to handle assets."""
    def _synthesize(
        self,
        cdk_context: Optional[dict],
        sceptre_user_data: Any
    ) -> CloudAssembly:
        self._logger.debug('CDK synthesizing CdkStack Class')
        self._logger.debug(f'CDK Context: {cdk_context}')
        app = self._app_class(context=cdk_context)
        self._stack_class(app, self.STACK_LOGICAL_ID, sceptre_user_data)
        return app.synth()


class BootstraplessCdkBuilder(PythonCdkBuilder):
    """A PythonCdkBuilder that uses the BootstraplessStackSynthesizer to handle assets."""
    def __init__(
        self,
        logger: logging.Logger,
        connection_manager: ConnectionManager,
        bootstrapless_config: dict,
        stack_class: Type[SceptreCdkStack],
        *,
        subprocess_run=subprocess.run,
        app_class=aws_cdk.App,
        synthesizer_class=BootstraplessStackSynthesizer
    ):
        """A PythonCdkBuilder that uses the BootstraplessStackSynthesizer to handle assets.

        Args:
            logger: The Template Handler's logger
            connection_manager: The Template Handler's ConnectionManager
            bootstrapless_config: The configurations (in snake_case) used for the bootstrapless
                synthesizer.
            stack_class: The stack class that will be synthesized
            subprocess_run: An callable used to run subprocesses
            app_class: The CDK App class used to synthesize the template
            environment_variables: The system environment variables
            synthesizer_class: The BootstraplessStackSynthesizer class that will be instantiated and
                added to the Stack for synthesis.
        """
        super().__init__(
            logger,
            connection_manager,
            stack_class,
            subprocess_run=subprocess_run,
            app_class=app_class,
        )
        self._bootstrapless_config = bootstrapless_config
        self._synthesizer_class = synthesizer_class

    def _synthesize(
        self,
        cdk_context: Optional[dict],
        sceptre_user_data: Any
    ) -> CloudAssembly:
        self._logger.debug(f'CDK synthesizing stack class: {self._stack_class.__name__}')
        self._logger.debug(f'CDK Context: {cdk_context}')
        app = self._app_class(context=cdk_context)
        try:
            synthesizer = self._synthesizer_class(**self._bootstrapless_config)
        except TypeError as e:
            raise TemplateHandlerArgumentsInvalidError(
                "Error encountered attempting to instantiate the BootstraplessSynthesizer with the "
                f"specified deployment config: {e}"
            ) from e

        self._stack_class(app, self.STACK_LOGICAL_ID, sceptre_user_data, synthesizer=synthesizer)
        return app.synth()


class CdkJsonBuilder(CdkBuilder):
    """A CdkBuilder that uses the CDK CLI to synthesize the stack template.

    This class is useful for deploying non-Python CDK projects with Sceptre.
    """
    def __init__(
        self,
        logger: logging.Logger,
        connection_manager: ConnectionManager,
        cdk_json_path: Path,
        stack_logical_id: str,
        bootstrapless_config: Dict[str, str],
        *,
        subprocess_run=subprocess.run,
    ):
        """A CdkBuilder that uses the CDK CLI to synthesize the stack template.

        This class is useful for deploying non-Python CDK projects with Sceptre.

        Args:
            logger: The Template Handler's logger
            connection_manager: The Template Handler's ConnectionManager
            cdk_json_path: The Path to the cdk.json file
            bootstrapless_config: The configurations (in snake_case) used for the bootstrapless
                synthesizer.
            stack_logical_id: The LogicalID of the stack to be deployed as it is configured on the
                App in the CDK project.
            subprocess_run: An callable used to run subprocesses
            environment_variables: The system environment variables
        """
        super().__init__(
            logger,
            connection_manager,
            subprocess_run=subprocess_run,
        )
        self._cdk_json_path = cdk_json_path
        self._stack_logical_id = stack_logical_id
        self._bootstrapless_config = bootstrapless_config

    def build_template(self, cdk_context: Optional[dict], sceptre_user_data: Any):
        if sceptre_user_data:
            self._logger.warning(
                "The cdk_json deployment_type does not support sceptre_user_data. Any values passed "
                "to your stack must be done via the cdk context. All values in your sceptre_user_data "
                "will be ignored."
            )

        environment_variables = self._get_envs()
        if self._bootstrapless_config:
            self._add_bootstrapless_envs(environment_variables)

        with TemporaryDirectory() as output_dir:
            self._synthesize(output_dir, cdk_context, environment_variables)
            assets_manifest = self._get_assets_manifest(output_dir)
            if self._only_asset_is_template(assets_manifest):
                # Sceptre already has a mechanism to upload the template if configured. We don't
                # need to deploy assets if the only asset is the template
                self._logger.debug("Only asset is template; Skipping asset upload.")
            else:
                assets_file = Path(output_dir, f'{self._stack_logical_id}.assets.json')
                self._publish_artifacts(str(assets_file), environment_variables)

            template_file = Path(output_dir, f'{self._stack_logical_id}.template.json')
            template = self._get_template(template_file)
            return template

    def _synthesize(self, output_dir: str, cdk_context: Optional[dict], envs: Dict[str, str]):
        command = self._create_synth_command(output_dir, cdk_context)
        # Run the synth in with the cwd of the cdk.json's directory
        self._run_command(command, envs, str(self._cdk_json_path.parent.resolve()))

    def _create_synth_command(self, output_dir: str, cdk_context: Dict[str, str]):
        command = f'npx cdk synth {self._stack_logical_id} -o {output_dir} -q '
        for key, value in cdk_context.items():
            command += f'--context {key}={value} '

        return command

    def _get_assets_manifest(self, output_dir: str):
        assets_file = Path(output_dir, f'{self._stack_logical_id}.assets.json')
        if not assets_file.exists():
            raise exceptions.SceptreException('CDK Asset manifest artifact not found')

        with assets_file.open(mode='r') as f:
            assets_dict = json.load(f)
        return assets_dict

    def _only_asset_is_template(self, assets_dict: dict) -> bool:
        if assets_dict.get('dockerImages', {}):
            return False

        keys = list(assets_dict.get('files', {}).keys())
        expected_template = f'{self._stack_logical_id}.template.json'
        return keys == [expected_template]

    def _get_template(self, template_path: Path):
        with template_path.open(mode='r') as f:
            return json.load(f)

    def _add_bootstrapless_envs(self, environment_variables: Dict[str, str]):
        for key, value in self._bootstrapless_config.items():
            environment_variables[f'BSS_{key.upper()}'] = value
