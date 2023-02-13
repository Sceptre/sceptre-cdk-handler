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
        # If the template path we're importing isn't somewhere in the CWD, we can't know how far up
        # to go with adding directories to the PATH, so we're not going to try. That could get kinda
        # screwy and cause unintended consequences.
        if cwd not in resolved_template_path.parents:
            # We'll consider the file name (without the stem) to be the module name.
            return template_path.stem

        module_path_segments = [template_path.stem]
        in_package_structure = True
        # We're going to climb up the hierarchy and add the whole directory structure to the PATH.
        # This would theoretically allow for imports from any level of the hierarchy. It's not ideal
        # but it's really the only way we can know how high up the import chain goes. However, we do
        # require each directory to have an __init__.py to consider it a part of the importable
        # hierarchy.
        for parent in resolved_template_path.parents:
            sys.path.append(str(parent))
            # If the parent directory is a valid python package in name and structure, we'll add it
            # to the module name segments and keep climbing
            if in_package_structure and (parent / '__init__.py').exists() and parent.name.isidentifier():
                module_path_segments.insert(0, parent.name)
            # But if the parent directory isn't a valid python package in name and structure, we'll
            # stop building out the module path.
            elif in_package_structure:
                in_package_structure = False

            # If we've climbed all the way up to the CWD.
            if parent == cwd:
                break

        # We'll make the full module path by joining all the segments together.
        return '.'.join(module_path_segments)
