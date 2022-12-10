from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, create_autospec

import yaml
from sceptre.connection_manager import ConnectionManager

from sceptre_cdk_handler.cdk import CDK, DEFAULT_CLASS_NAME
from sceptre_cdk_handler.cdk_builder import CdkBuilder
from sceptre_cdk_handler.class_importer import ClassImporter


class TestCDK(TestCase):
    def setUp(self):
        self.name = "CDK"
        self.connection_manager = Mock(ConnectionManager)
        self.arguments = {
            'path': 'my/template/path.py',
            'context': {
                '@aws-cdk/core:bootstrapQualifier': 'hnb659fds'
            }
        }
        self.sceptre_user_data = {
            'key': 'value'
        }
        self.stack_group_config = {
            'project_path': 'root_sceptre_dir'
        }
        self.importer_class = create_autospec(ClassImporter)
        self.template_dict = {'Resources': {}}
        self.builder_class = create_autospec(CdkBuilder)
        self.builder_class.return_value.build_template.return_value = self.template_dict

    @property
    def handler(self) -> CDK:
        return CDK(
            self.name,
            self.arguments,
            self.sceptre_user_data,
            self.connection_manager,
            self.stack_group_config,
            importer_class=self.importer_class,
            cdk_builder_class=self.builder_class
        )

    def test_handle__class_name_as_argument__imports_named_class_from_specified_template_path(self):
        self.arguments['class_name'] = "MyFancyClass"
        self.handler.handle()

        expected_template_path = Path(
            self.stack_group_config['project_path'],
            'templates',
            self.arguments['path']
        )
        self.importer_class.return_value.import_class.assert_any_call(
            expected_template_path,
            'MyFancyClass'
        )

    def test_handle__no_class_name_argument__imports_default_class_name_from_template_path(self):
        self.handler.handle()

        expected_template_path = Path(
            self.stack_group_config['project_path'],
            'templates',
            self.arguments['path']
        )
        self.importer_class.return_value.import_class.assert_any_call(
            expected_template_path,
            DEFAULT_CLASS_NAME
        )

    def test_handle__builds_template_for_imported_stack_with_context_and_sceptre_user_data(self):
        self.handler.handle()
        self.builder_class.return_value.build_template.assert_any_call(
            self.importer_class.return_value.import_class.return_value,
            self.arguments['context'],
            self.sceptre_user_data
        )

    def test_handle__returns_dumped_yaml_template(self):
        result = self.handler.handle()
        expected = yaml.dump(self.template_dict)
        self.assertEqual(expected, result)
