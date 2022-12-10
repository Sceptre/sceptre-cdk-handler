import logging
import logging
import subprocess
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, create_autospec

import aws_cdk
import yaml
from aws_cdk.cx_api import CloudAssembly
from sceptre.connection_manager import ConnectionManager
from sceptre.exceptions import SceptreException

from template_handler.cdk import CDK, ClassImporter, CdkBuilder, DEFAULT_CLASS_NAME


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


class TestCdkBuilder(TestCase):
    def setUp(self):
        self.logger = Mock(logging.Logger)
        self.profile = 'my_fancy_profile'
        self.region = 'us-west-2'
        self.iam_role = 'arn:aws:something:or:another:role'
        self.credentials = Mock(
            access_key="key",
            secret_key="secret",
            token=None
        )

        self.connection_manager = Mock(
            ConnectionManager,
            **{
                'profile': self.profile,
                'region': self.region,
                'iam_role': self.iam_role,
                '_get_session.return_value.get_credentials.return_value': self.credentials
            }
        )
        self.subprocess_run = create_autospec(subprocess.run)
        self.app_class = create_autospec(aws_cdk.App)
        self.assembly = Mock(CloudAssembly)
        self.app_class.return_value.synth.return_value = self.assembly
        self.assembly.artifacts = [
            Mock(name="irrelevant_artifact"),
            Mock(spec=aws_cdk.cx_api.AssetManifestArtifact, file="asset/file/path")
        ]
        self.environment_variables = {
            "PATH": "blah:blah:blah",
            "AWS_ACCESS_KEY_ID": "old key",
            "AWS_SECRET_ACCESS_KEY": "old secret",
            "AWS_SESSION_TOKEN": "old token"
        }

        self.builder = CdkBuilder(
            self.logger,
            self.connection_manager,
            subprocess_run=self.subprocess_run,
            app_class=self.app_class,
            environment_variables=self.environment_variables
        )

        self.stack_class = Mock()
        self.context = {'hello': 'you'}
        self.sceptre_user_data = {'user': 'data'}

    def test_build_template__instantiates_app_with_context(self):
        self.build()
        self.app_class.assert_any_call(context=self.context)

    def build(self):
        return self.builder.build_template(
            self.stack_class,
            self.context,
            self.sceptre_user_data
        )

    def test_build_template__adds_stack_instance_to_app_with_user_data(self):
        self.build()

        self.stack_class.assert_any_call(
            self.app_class.return_value,
            CdkBuilder.STACK_LOGICAL_ID,
            self.sceptre_user_data
        )

    def test_build_template__synthesized_assembly_has_no_manifest_artifact__raises_sceptre_exception(self):
        del self.assembly.artifacts[1]
        with self.assertRaises(SceptreException):
            self.build()

    def test_build_template__no_session_token__runs_cdk_assets_publish_on_the_asset_artifacts_file_with_correct_envs(self):
        self.credentials.token = None
        self.build()
        expected_command = f'npx cdk-assets publish --path asset/file/path'
        expected_envs = {
            **self.environment_variables,
            **{
                "AWS_ACCESS_KEY_ID": self.credentials.access_key,
                "AWS_SECRET_ACCESS_KEY": self.credentials.secret_key,
            }
        }
        del expected_envs['AWS_SESSION_TOKEN']
        self.subprocess_run.assert_any_call(
            expected_command,
            env=expected_envs,
            shell=True,
            stdout=sys.stderr,
            check=True
        )

    def test_build_template__with_session_token__runs_cdk_assets_publish_on_the_asset_artifacts_file_with_correct_envs(self):
        self.credentials.token = "special session token"
        self.build()
        expected_command = f'npx cdk-assets publish --path asset/file/path'
        expected_envs = {
            **self.environment_variables,
            **{
                "AWS_ACCESS_KEY_ID": self.credentials.access_key,
                "AWS_SECRET_ACCESS_KEY": self.credentials.secret_key,
                "AWS_SESSION_TOKEN": self.credentials.token
            }
        }
        self.subprocess_run.assert_any_call(
            expected_command,
            env=expected_envs,
            shell=True,
            stdout=sys.stderr,
            check=True
        )

    def test_build_template__returns_template_from_cloud_assembly_for_stack(self):
        expected_template = {'Resources': {}}

        def get_stack_by_name(stack_id):
            self.assertEqual(CdkBuilder.STACK_LOGICAL_ID, stack_id)
            return Mock(template=expected_template)

        self.assembly.get_stack_by_name = get_stack_by_name

        result = self.build()
        self.assertEqual(expected_template, result)


class TestClassImporter(TestCase):
    def test_import_class__imports_class_from_referenced_file(self):
        filepath = Path(__file__).parent / 'assets' / 'file_to_import.py'
        class_name = "MyFancyClassToImport"
        importer = ClassImporter()
        result = importer.import_class(filepath, class_name)
        self.assertEqual(
            'Success!',
            result.attribute
        )

    def test_import_class__named_class_isnt_on_module__raises_sceptre_exception(self):
        filepath = Path(__file__).parent / 'assets' / 'file_to_import.py'
        importer = ClassImporter()
        with self.assertRaises(SceptreException):
            importer.import_class(filepath, "CantFindMe")
