import importlib.machinery
import importlib.util
import sys
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
        template_module_name = self._enable_import_hierarchy(template_path)

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

    def _enable_import_hierarchy(self, template_path: Path) -> str:
        resolved_template_path = template_path.resolve()
        cwd = Path.cwd()
        if cwd not in resolved_template_path.parents:
            return template_path.stem

        module_path_segments = [template_path.stem]
        in_package_structure = True
        for parent in resolved_template_path.parents:
            sys.path.append(str(parent))
            if in_package_structure and (parent / '__init__.py').exists() and parent.name.isidentifier():
                module_path_segments.insert(0, parent.name)
            elif in_package_structure:
                in_package_structure = False

            if parent == cwd:
                break

        return '.'.join(module_path_segments)
