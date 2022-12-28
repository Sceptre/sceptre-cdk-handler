import importlib.machinery
import importlib.util
from pathlib import Path
from typing import Type

from sceptre import exceptions

from sceptre_cdk_handler.cdk_builder import SceptreCdkStack


class ClassImporter:
    def import_class(self, template_path: Path, class_name: str) -> Type[SceptreCdkStack]:
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
