import pathlib
from pathlib import Path
from typing import Any, Optional, Type

import yaml
from sceptre.connection_manager import ConnectionManager
from sceptre.exceptions import TemplateHandlerArgumentsInvalidError, SceptreException
from sceptre.helpers import normalise_path
from sceptre.template_handlers import TemplateHandler

from sceptre_cdk_handler.cdk_builder import (
    BootstrappedCdkBuilder,
    BootstraplessCdkBuilder,
    SceptreCdkStack,
    CdkJsonBuilder
)
from sceptre_cdk_handler.class_importer import ClassImporter
from sceptre_cdk_handler.command_checker import CommandChecker

try:
    # Literal was defined in py3.8.
    from typing import Literal
except ImportError:
    # If running this in py3.7, we'll need to instead import it from typing_extensions, which
    # back-ports a lot of the typing constructs of later versions of Python.
    from typing_extensions import Literal

DEFAULT_CLASS_NAME = 'CdkStack'
QUALIFIER_CONTEXT_KEY = '@aws-cdk/core:bootstrapQualifier'


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
        bootstrapped_cdk_builder_class=BootstrappedCdkBuilder,
        bootstrapless_cdk_builder_class=BootstraplessCdkBuilder,
        nonpython_cdk_bulder_class=CdkJsonBuilder,
        command_checker_class=CommandChecker
    ):
        super().__init__(
            name=name,
            arguments=arguments,
            sceptre_user_data=sceptre_user_data,
            connection_manager=connection_manager,
            stack_group_config=stack_group_config
        )
        self._importer = importer_class()
        self._bootstrapped_cdk_builder_class = bootstrapped_cdk_builder_class
        self._bootstrapless_cdk_builder_class = bootstrapless_cdk_builder_class
        self._non_python_cdk_builder_class = nonpython_cdk_bulder_class
        self._command_checker = command_checker_class(self.logger)

    def schema(self):
        """
        Return a JSON schema of the properties that this template handler requires.

        Reference: https://github.com/Julian/jsonschema
        """
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "path": {"type": "string"},
                "deployment_type": {
                    "type": "string",
                    "enum": ["bootstrapped", "bootstrapless", "cdk_json"]
                },
                "bootstrap_qualifier": {"type": "string"},
                "context": {"type": "object"},
                "class_name": {"type": "string"},
                "stack_logical_id": {"type": "string"},
                "bootstrapless_config": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "file_asset_bucket_name": {"type": "string"},
                        "file_asset_prefix": {"type": "string"},
                        "file_asset_publishing_role_arn": {"type": "string"},
                        "file_asset_region_set": {"type": "string"},
                        "image_asset_account_id": {"type": "string"},
                        "image_asset_publishing_role_arn": {"type": "string"},
                        "image_asset_region_set": {"type": "string"},
                        "image_asset_repository_name": {"type": "string"},
                        "image_asset_tag_prefix": {"type": "string"},
                        "template_bucket_name": {"type": "string"},
                    },
                }
            },
            "required": [
                "path",
                'deployment_type'
            ]
        }

    @property
    def cdk_template_path(self) -> Path:
        """CDK Template file path, relative to the the project's templates directory"""

        return self._resolve_template_path(self.arguments['path'])

    def _resolve_template_path(self, template_path: str) -> Path:
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

    @property
    def cdk_context(self) -> dict:
        """The CDK context dict to pass to the app. Used to pass feature flags, etc..."""

        return self.arguments.get('context')

    @property
    def cdk_class_name(self) -> str:
        """The name of the CDK Stack class on the template file to import."""

        return self.arguments.get('class_name', DEFAULT_CLASS_NAME)

    @property
    def bootstrap_qualifier(self) -> Optional[str]:
        """The bootstrap stack qualifier to use for the "bootstrapped" deployment_type."""
        return self.arguments.get('bootstrap_qualifier')

    @property
    def deployment_type(self) -> Literal['bootstrapped', 'bootstrapless']:
        """The way Sceptre should handle the deployment of file and image assets. Can be one of
        "bootstrapped" or "bootstrapless".
        """
        return self.arguments['deployment_type']

    @property
    def bootstrapless_config(self) -> dict:
        """The synthesizer args for CDK Bootstrapless Synthesizer. Used only with the "bootstrapless"
        deployment_type.
        """
        return self.arguments.get('bootstrapless_config', {})

    @property
    def path_is_to_cdk_json(self) -> bool:
        return self.cdk_template_path.name.lower() == 'cdk.json'

    @property
    def stack_logical_id(self) -> Optional[str]:
        return self.arguments.get('stack_logical_id')

    def validate(self):
        self._check_prerequisites()
        if self.deployment_type == 'cdk_json':
            self._check_cdk_json()
        if self.path_is_to_cdk_json and self.deployment_type != 'cdk_json':
            raise TemplateHandlerArgumentsInvalidError(
                "You cannot use a cdk.json file as your template path unless you use \"cdk_json\" "
                "as your deployment_type."
            )
        super().validate()

    def _check_cdk_json(self):
        if not self.path_is_to_cdk_json:
            raise TemplateHandlerArgumentsInvalidError(
                "Using the cdk_json deployment_type requires the \"path\" argument to point to "
                "the cdk.json file in your CDK project."
            )
        if self.cdk_context and any(isinstance(v, (list, dict)) for v in self.cdk_context.values()):
            raise TemplateHandlerArgumentsInvalidError(
                "You cannot use nested values within your CDK context when using the cdk_json "
                "deployment type. If you need to specify such values, put them in the context of"
                "your cdk.json."
            )
        if self.stack_logical_id is None:
            raise TemplateHandlerArgumentsInvalidError(
                "You must specify the logical ID of the stack in your app in order to use the "
                "cdk_json deployment_type."
            )

    def handle(self) -> str:
        """
        Main Sceptre CDK Handler function

        Returns:
            str - The CDK synthesised CloudFormation template
        """
        if self.deployment_type == 'cdk_json':
            builder = self._create_cdk_json_builder()
            context = self._create_bootstrapped_context()
        elif self.deployment_type == 'bootstrapped':
            builder, stack_class = self._create_bootstrapped_builder()
            context = self._create_bootstrapped_context()
        elif self.deployment_type == "bootstrapless":
            builder = self._create_bootstrapless_builder()
            context = self.cdk_context
        else:
            # It shouldn't be possible to get here due to the json schema validation
            raise ValueError("deployment_type must be 'bootstrapped' or 'bootstrapless'")

        template_dict = builder.build_template(context, self.sceptre_user_data)
        return yaml.safe_dump(template_dict)

    def _create_cdk_json_builder(self):
        return CdkJsonBuilder(
            self.logger,
            self.connection_manager,
            self.cdk_template_path,
            self.stack_logical_id,
        )

    def _create_bootstrapped_builder(self):
        stack_class: Type[SceptreCdkStack] = self._importer.import_class(
            self.cdk_template_path,
            self.cdk_class_name
        )
        builder = self._bootstrapped_cdk_builder_class(
            self.logger,
            self.connection_manager,
            stack_class
        )
        return builder, stack_class

    def _create_bootstrapped_context(self):
        if self.cdk_context and QUALIFIER_CONTEXT_KEY in self.cdk_context:
            return self.cdk_context
        # As a convenience, the qualifier can be set as its own argument to simplify the
        # configuration. If it's passed this way, we need to add it to whatever context dict there
        # is, if one exists; We'll make one if it doesn't.
        if self.bootstrap_qualifier:
            context = self.cdk_context or {}
            context[QUALIFIER_CONTEXT_KEY] = self.bootstrap_qualifier
            return context

        # If there's no qualifier specified anywhere, we're falling back to CDK's default
        # context-retrieval mechanisms.
        return self.cdk_context

    def _create_bootstrapless_builder(self) -> BootstraplessCdkBuilder:
        stack_class: Type[SceptreCdkStack] = self._importer.import_class(
            self.cdk_template_path,
            self.cdk_class_name
        )
        return self._bootstrapless_cdk_builder_class(
            self.logger,
            self.connection_manager,
            self.bootstrapless_config,
            stack_class
        )

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
            if not self._command_checker.cmd_exists(cmd_prerequisite):
                raise SceptreException(f"Command prerequisite '{cmd_prerequisite}' not found")

        # Check Node Package Prerequisites
        node_prerequisites = [
            'cdk-assets'
        ]
        for node_prerequisite in node_prerequisites:
            if not self._command_checker.node_package_exists(node_prerequisite):
                raise SceptreException(f"Node Package prerequisite '{node_prerequisite}' not found")
