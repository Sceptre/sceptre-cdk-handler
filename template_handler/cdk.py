import pathlib
from pathlib import Path
from typing import Any

import yaml
from sceptre.connection_manager import ConnectionManager
from sceptre.helpers import normalise_path
from sceptre.template_handlers import TemplateHandler

from template_handler.cdk_builder import CdkBuilder
from template_handler.class_importer import ClassImporter

try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol

DEFAULT_CLASS_NAME = 'CdkStack'


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

    def handle(self) -> str:
        """
        Main Sceptre CDK Handler function

        Returns:
            str - The CDK synthesised CloudFormation template
        """
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
