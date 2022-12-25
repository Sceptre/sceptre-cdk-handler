from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, create_autospec

import yaml
from sceptre.connection_manager import ConnectionManager
from sceptre.exceptions import SceptreException

from sceptre_cdk_handler.cdk import CDK, DEFAULT_CLASS_NAME, QUALIFIER_CONTEXT_KEY
from sceptre_cdk_handler.cdk_builder import BootstrappedCdkBuilder, BootstraplessCdkBuilder
from sceptre_cdk_handler.class_importer import ClassImporter
from sceptre_cdk_handler.command_checker import CommandChecker


class TestCDK(TestCase):
    def setUp(self):
        self.name = "CDK"
        self.connection_manager = Mock(ConnectionManager)
        self.arguments = {
            'path': 'my/template/path.py',
            'deployment_type': 'bootstrapped'
        }
        self.sceptre_user_data = {
            'key': 'value'
        }
        self.stack_group_config = {
            'project_path': 'root_sceptre_dir'
        }
        self.importer_class = create_autospec(ClassImporter)
        self.template_dict = {'Resources': {}}
        self.bootstrapped_builder_class = create_autospec(BootstrappedCdkBuilder)
        self.bootstrapless_builder_class = create_autospec(BootstraplessCdkBuilder)
        self.bootstrapped_builder_class.return_value.build_template.return_value = self.template_dict
        self.bootstrapless_builder_class.return_value.build_template.return_value = self.template_dict
        self.command_checker_class = create_autospec(CommandChecker)
        self.command_checker_class.return_value.cmd_exists.side_effect = self.cmd_exists
        self.command_checker_class.return_value.node_package_exists.side_effect = self.node_package_exists

        self.commands = {
            'node': True,
            'npx': True,
        }
        self.node_packages = {
            'cdk-assets': True
        }

    def cmd_exists(self, cmd_name):
        return self.commands.get(cmd_name, False)

    def node_package_exists(self, package_name):
        return self.node_packages.get(package_name, False)

    def get_handler(self) -> CDK:
        handler = CDK(
            self.name,
            self.arguments,
            self.sceptre_user_data,
            self.connection_manager,
            self.stack_group_config,
            importer_class=self.importer_class,
            bootstrapped_cdk_builder_class=self.bootstrapped_builder_class,
            bootstrapless_cdk_builder_class=self.bootstrapless_builder_class,
            command_checker_class=self.command_checker_class
        )
        return handler

    def validate_and_handle(self):
        handler = self.get_handler()
        handler.validate()
        return handler.handle()

    def test_handle__class_name_as_argument__imports_named_class_from_specified_template_path(self):
        self.arguments['class_name'] = "MyFancyClass"
        self.validate_and_handle()

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
        self.validate_and_handle()

        expected_template_path = Path(
            self.stack_group_config['project_path'],
            'templates',
            self.arguments['path']
        )
        self.importer_class.return_value.import_class.assert_any_call(
            expected_template_path,
            DEFAULT_CLASS_NAME
        )

    def test_handle__bootstrapped__bootstrap_qualifier_set__no_context__builds_template_with_qualifier_in_context(self):
        self.arguments['deployment_type'] = 'bootstrapped'
        self.arguments['bootstrap_qualifier'] = qualifier = 'blardyblahr'
        self.validate_and_handle()
        self.bootstrapped_builder_class.assert_any_call(self.get_handler().logger, self.connection_manager)
        expected_context = {
            QUALIFIER_CONTEXT_KEY: qualifier
        }
        self.bootstrapped_builder_class.return_value.build_template.assert_any_call(
            self.importer_class.return_value.import_class.return_value,
            expected_context,
            self.sceptre_user_data
        )

    def test_handle__bootstrapped__bootstrap_qualifier_set__has_context__builds_template_with_qualifier_in_context(self):
        self.arguments['deployment_type'] = 'bootstrapped'
        self.arguments['bootstrap_qualifier'] = qualifier = 'blardyblahr'
        self.arguments['context'] = context = {
            'something': 'else'
        }
        expected_context = context.copy()
        self.validate_and_handle()
        self.bootstrapped_builder_class.assert_any_call(self.get_handler().logger, self.connection_manager)

        expected_context[QUALIFIER_CONTEXT_KEY] = qualifier
        self.bootstrapped_builder_class.return_value.build_template.assert_any_call(
            self.importer_class.return_value.import_class.return_value,
            expected_context,
            self.sceptre_user_data
        )

    def test_handle__bootstrapped__bootstrap_qualifier_in_context__builds_template_with_qualifier_in_context(self):
        self.arguments['deployment_type'] = 'bootstrapped'
        self.arguments['context'] = context = {
            'something': 'else',
            QUALIFIER_CONTEXT_KEY: 'blardyblahr'
        }
        expected_context = context.copy()
        self.validate_and_handle()
        self.bootstrapped_builder_class.assert_any_call(self.get_handler().logger, self.connection_manager)

        self.bootstrapped_builder_class.return_value.build_template.assert_any_call(
            self.importer_class.return_value.import_class.return_value,
            expected_context,
            self.sceptre_user_data
        )

    def test_handle__bootstrapped__no_qualifier_but_has_context__builds_template_with_context(self):
        self.arguments['context'] = context = {'key': 'value'}
        self.validate_and_handle()
        self.bootstrapped_builder_class.assert_any_call(self.get_handler().logger, self.connection_manager)
        self.bootstrapped_builder_class.return_value.build_template.assert_any_call(
            self.importer_class.return_value.import_class.return_value,
            context,
            self.sceptre_user_data
        )

    def test_handle__bootstrapped__no_qualifier_or_context__builds_template_with_no_context(self):
        self.arguments['deployment_type'] = 'bootstrapped'
        self.validate_and_handle()
        self.bootstrapped_builder_class.assert_any_call(self.get_handler().logger, self.connection_manager)
        self.bootstrapped_builder_class.return_value.build_template.assert_any_call(
            self.importer_class.return_value.import_class.return_value,
            None,
            self.sceptre_user_data
        )

    def test_handle_bootstrapless__no_bootstrapless_config__builds_template_with_empty_bootstrapless_config(self):
        self.arguments['deployment_type'] = 'bootstrapless'
        self.arguments['context'] = context = {'something': 'else'}
        self.validate_and_handle()
        self.bootstrapless_builder_class.assert_any_call(self.get_handler().logger, self.connection_manager, {})
        self.bootstrapless_builder_class.return_value.build_template.assert_any_call(
            self.importer_class.return_value.import_class.return_value,
            context,
            self.sceptre_user_data
        )

    def test_handle_bootstrapless__bootstrapless_config__builds_template_with_bootstrapless_config(self):
        self.arguments['deployment_type'] = 'bootstrapless'
        self.arguments['context'] = context = {'something': 'else'}
        self.arguments['bootstrapless_config'] = config = {
            'file_asset_bucket_name': 'my_bucket'
        }
        self.validate_and_handle()
        self.bootstrapless_builder_class.assert_any_call(
            self.get_handler().logger,
            self.connection_manager,
            config
        )
        self.bootstrapless_builder_class.return_value.build_template.assert_any_call(
            self.importer_class.return_value.import_class.return_value,
            context,
            self.sceptre_user_data
        )

    def test_handle__returns_dumped_yaml_template(self):
        result = self.validate_and_handle()
        expected = yaml.dump(self.template_dict)
        self.assertEqual(expected, result)

    def test_validate__command_doesnt_exist__raises_sceptre_exception(self):
        for command in ['node', 'npx']:
            with self.subTest(command):
                self.setUp()
                self.commands.pop(command)
                with self.assertRaises(SceptreException):
                    self.get_handler().validate()

    def test_validate__cdk_assets_doesnt_exist__raises(self):
        self.node_packages.pop('cdk-assets')
        with self.assertRaises(SceptreException):
            self.get_handler().validate()
