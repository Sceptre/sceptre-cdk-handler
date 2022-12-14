import pathlib
from pathlib import Path
from typing import Any, Optional, Tuple, Type

import yaml
from sceptre.connection_manager import ConnectionManager
from sceptre.helpers import normalise_path
from sceptre.template_handlers import TemplateHandler

from sceptre_cdk_handler.cdk_builder import (
    BootstrappedCdkBuilder,
    BootstraplessCdkBuilder,
    SceptreCdkStack,
    NonPythonCdkBuilder
)
from sceptre_cdk_handler.class_importer import ClassImporter

try:
    from typing import Literal
except ImportError:
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
        bootstrapless_cdk_builder_class=BootstraplessCdkBuilder
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
                    "enum": ["bootstrapped", "bootstrapless"]
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
        """
        CDK Template Path property handler.

        Returns:
            The specified CDK template path.
        """

        return self._resolve_template_path(self.arguments['path'])

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

    @property
    def bootstrap_qualifier(self) -> Optional[str]:
        return self.arguments.get('bootstrap_qualifier')

    @property
    def deployment_type(self) -> Literal['bootstrap', 'bootstrapless']:
        return self.arguments['deployment_type']

    @property
    def bootstrapless_config(self) -> dict:
        return self.arguments.get('bootstrapless_config', {})

    @property
    def path_is_to_cdk_json(self) -> bool:
        return self.cdk_template_path.name == 'cdk.json'

    @property
    def stack_logical_id(self) -> Optional[str]:
        return self.arguments.get('stack_logical_id')

    def handle(self) -> str:
        """
        Main Sceptre CDK Handler function

        Returns:
            str - The CDK synthesised CloudFormation template
        """
        if self.path_is_to_cdk_json:
            builder = NonPythonCdkBuilder(self.logger, self.connection_manager)
            context = self._create_bootstrapped_context()
            return builder.build_template(self.cdk_template_path, context, self.stack_logical_id)

        stack_class: Type[SceptreCdkStack] = self._importer.import_class(self.cdk_template_path, self.cdk_class_name)
        if self.deployment_type == 'bootstrapped':
            builder = self._bootstrapped_cdk_builder_class(self.logger, self.connection_manager)
            context = self._create_bootstrapped_context()
        elif self.deployment_type == "bootstrapless":
            builder = self._get_bootstrapless_builder()
            context = self.cdk_context
        else:
            # It shouldn't be possible to get here due to the json schema validation
            raise ValueError("deployment_type must be 'bootstrapped' or 'bootstrapless'")

        template_dict = builder.build_template(
            stack_class,
            context,
            self.sceptre_user_data
        )
        return yaml.safe_dump(template_dict)

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

    def _get_bootstrapless_builder(self) -> BootstraplessCdkBuilder:
        return self._bootstrapless_cdk_builder_class(
            self.logger,
            self.connection_manager,
            self.bootstrapless_config
        )
