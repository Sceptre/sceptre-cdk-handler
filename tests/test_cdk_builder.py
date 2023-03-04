import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, create_autospec

import aws_cdk
from aws_cdk.cx_api import CloudAssembly
from cdk_bootstrapless_synthesizer import BootstraplessStackSynthesizer
from sceptre.connection_manager import ConnectionManager
from sceptre.exceptions import SceptreException, TemplateHandlerArgumentsInvalidError

from sceptre_cdk_handler.cdk_builder import (
    BootstrappedCdkBuilder,
    BootstraplessCdkBuilder,
    SceptreCdkStack,
    CdkBuilder, CdkJsonBuilder, CdkInvocationError
)
from pyfakefs.fake_filesystem_unittest import TestCase as PyFakeFsTestCase


class TestBootstrappedCdkBuilder(TestCase):
    def setUp(self):
        self.logger = Mock(logging.Logger)
        self.region = 'us-west-2'
        self.environment_variables = {
            "PATH": "blah:blah:blah",
            "AWS_ACCESS_KEY_ID": "old key",
            "AWS_SECRET_ACCESS_KEY": "old secret",
            "AWS_SESSION_TOKEN": "old token"
        }

        self.connection_manager = Mock(
            ConnectionManager,
            **{
                'region': self.region,
                'create_session_environment_variables.return_value': self.environment_variables
            }
        )
        self.subprocess_run = create_autospec(subprocess.run)
        self.app_class = create_autospec(aws_cdk.App)
        self.assembly = Mock(CloudAssembly)
        self.app_class.return_value.synth.return_value = self.assembly
        self.manifest = Mock(**{
            'spec': aws_cdk.cx_api.AssetManifestArtifact,
            'file': "asset/file/path",
            'contents.docker_images': {
                "hashhashhash": {"blah": "blah"}
            },
            'contents.files': {
                "hashyhashhash": {"blah": "blah"},
                "CDKStack.template.json": {"blah": "blah"}
            }
        })

        self.assembly.artifacts = [
            Mock(name="irrelevant_artifact"),
            self.manifest
        ]
        self.stack_class = create_autospec(SceptreCdkStack)
        self.stack_class.__name__ = "MyFancyStack"

        self.builder = BootstrappedCdkBuilder(
            self.logger,
            self.connection_manager,
            subprocess_run=self.subprocess_run,
            app_class=self.app_class,
            stack_class=self.stack_class
        )

        self.context = {'hello': 'you'}
        self.sceptre_user_data = {'user': 'data'}

    def test_build_template__instantiates_app_with_context(self):
        self.build()
        self.app_class.assert_any_call(context=self.context)

    def build(self):
        return self.builder.build_template(
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

    def test_build_template__synthesized_assembly_has_only_template_asset__does_not_publish_assets(self):
        self.manifest.contents.docker_images.clear()
        self.manifest.contents.files.pop('hashyhashhash')
        self.build()
        self.subprocess_run.assert_not_called()

    def test_build_template__runs_cdk_assets_publish_on_the_asset_artifacts_file_with_correct_envs(self):
        self.build()
        expected_command = 'npx cdk-assets -v publish --path asset/file/path'
        expected_envs = {
            **self.environment_variables,
            **{
                "CDK_DEFAULT_REGION": self.connection_manager.region,
            }
        }
        self.subprocess_run.assert_called_once_with(
            expected_command,
            env=expected_envs,
            shell=True,
            stdout=sys.stderr,
            check=True,
            cwd=None
        )

    def test_build_template__returns_template_from_cloud_assembly_for_stack(self):
        expected_template = {'Resources': {}}

        def get_stack_by_name(stack_id):
            self.assertEqual(CdkBuilder.STACK_LOGICAL_ID, stack_id)
            return Mock(template=expected_template)

        self.assembly.get_stack_by_name = get_stack_by_name

        result = self.build()
        self.assertEqual(expected_template, result)

    def test_build_template__running_cdk_assets_command_raises_called_process_error__reraises_cdk_invocation_error(self):
        self.subprocess_run.side_effect = subprocess.CalledProcessError(1, 'bad command')
        with self.assertRaises(CdkInvocationError):
            self.build()


class TestBootstraplessCdkBuilder(TestCase):
    def setUp(self):
        self.logger = Mock(logging.Logger)
        self.region = 'us-west-2'
        self.environment_variables = {
            "PATH": "blah:blah:blah",
            "AWS_ACCESS_KEY_ID": "old key",
            "AWS_SECRET_ACCESS_KEY": "old secret",
            "AWS_SESSION_TOKEN": "old token"
        }
        self.connection_manager = Mock(
            ConnectionManager,
            **{
                'region': self.region,
                'create_session_environment_variables.return_value': self.environment_variables
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

        self.bootstrapless_config = {
            'file_asset_bucket_name': 'my_bucket'
        }
        self.synthesizer_class = create_autospec(BootstraplessStackSynthesizer)
        self.stack_class = create_autospec(SceptreCdkStack)
        self.stack_class.__name__ = "MyFancyBootstraplessStack"
        self.builder = BootstraplessCdkBuilder(
            self.logger,
            self.connection_manager,
            self.bootstrapless_config,
            self.stack_class,
            subprocess_run=self.subprocess_run,
            app_class=self.app_class,
            synthesizer_class=self.synthesizer_class
        )

        self.context = {'hello': 'you'}
        self.sceptre_user_data = {'user': 'data'}

    def test_build_template__no_synthesizer_config__instantiates_synthesizer_with_no_kwargs(self):
        self.bootstrapless_config.clear()
        self.builder.build_template(self.context, self.sceptre_user_data)
        self.synthesizer_class.assert_any_call(**self.bootstrapless_config)

    def test_build_template__instantiates_synthesizer_with_synthesizer_config_kwargs(self):
        self.builder.build_template(self.context, self.sceptre_user_data)
        self.synthesizer_class.assert_any_call(**self.bootstrapless_config)

    def test_build_template__invalid_synthesizer_arguments__raises_template_handler_arguments_invalid_error(self):
        self.bootstrapless_config['bad'] = 'not-recognized'
        with self.assertRaises(TemplateHandlerArgumentsInvalidError):
            self.builder.build_template(self.context, self.sceptre_user_data)

    def test_build_template__instantiates_stack_with_synthesizer(self):
        self.builder.build_template(self.context, self.sceptre_user_data)
        self.stack_class.assert_any_call(
            self.app_class.return_value,
            CdkBuilder.STACK_LOGICAL_ID,
            self.sceptre_user_data,
            synthesizer=self.synthesizer_class.return_value
        )

    def test_build_template__running_cdk_assets_command_raises_called_process_error__reraises_cdk_invocation_error(self):
        self.subprocess_run.side_effect = subprocess.CalledProcessError(1, 'bad command')
        with self.assertRaises(CdkInvocationError):
            self.builder.build_template(self.context, self.sceptre_user_data)


class TestCdkJsonBuilder(PyFakeFsTestCase):
    def setUp(self):
        self.setUpPyfakefs()

        self.logger = Mock(logging.Logger)
        self.region = 'us-west-2'
        self.environment_variables = {
            "PATH": "blah:blah:blah",
            "AWS_ACCESS_KEY_ID": "old key",
            "AWS_SECRET_ACCESS_KEY": "old secret",
            "AWS_SESSION_TOKEN": "old token"
        }
        self.connection_manager = Mock(
            ConnectionManager,
            **{
                'region': self.region,
                'create_session_environment_variables.return_value': self.environment_variables.copy()
            }
        )
        self.subprocess_run = create_autospec(subprocess.run, side_effect=self.fake_subprocess_run)
        self.bootstrapless_config = {
            'file_asset_bucket_name': 'my_bucket'
        }
        self.cdk_json_path = Path(self.fs.create_file('/path/to/my/cdk.json').path)
        self.stack_logical_id = 'MyCdkStack'
        self.builder = CdkJsonBuilder(
            logger=self.logger,
            connection_manager=self.connection_manager,
            cdk_json_path=self.cdk_json_path,
            stack_logical_id=self.stack_logical_id,
            bootstrapless_config=self.bootstrapless_config,
            subprocess_run=self.subprocess_run
        )
        self.context = {'hello': 'you'}
        self.sceptre_user_data = {'user': 'data'}
        self.expected_template_file_name = f'{self.stack_logical_id}.template.json'
        self.expected_template = {}
        self.manifest = {'files': {self.expected_template_file_name: {}}}

        self.artifacts_published = False
        self.synth_context = {}
        self.subprocess_envs = {}

        self.raise_assets_error = False
        self.raise_synth_error = False

    def fake_subprocess_run(self, command, *, env, shell, stdout, check, cwd):
        self.assertTrue(shell)
        self.assertTrue(check)
        self.assertIs(sys.stderr, stdout)
        parser = argparse.ArgumentParser(prog='npx', exit_on_error=False)
        if command.startswith('npx cdk-assets'):
            if self.raise_assets_error:
                raise subprocess.CalledProcessError(1, 'bad command')
            self.subprocess_envs['assets'] = env
            parser.add_argument('--path')
            parsed, _ = parser.parse_known_args(command.split(' '))
            self.assertTrue(Path(parsed.path).exists())
            self.artifacts_published = True
        elif command.startswith('npx cdk synth'):
            if self.raise_synth_error:
                raise subprocess.CalledProcessError(1, 'bad command')
            self.assertEqual(str(self.cdk_json_path.parent.resolve()), cwd)
            self.subprocess_envs['synth'] = env
            parser.add_argument('npx')
            parser.add_argument('cdk')
            parser.add_argument('synth')
            parser.add_argument('stack_logical_id')
            parser.add_argument('-o', '--output')
            parser.add_argument('--context', action='append')
            parsed, _ = parser.parse_known_args(command.split(' '))
            self.synth_context = {
                key: value for key, value in
                [context.split('=') for context in parsed.context]
            }
            assets_file = Path(parsed.output, f'{parsed.stack_logical_id}.assets.json')
            template_file = Path(parsed.output, f'{parsed.stack_logical_id}.template.json')
            self.fs.create_file(str(assets_file), contents=json.dumps(self.manifest))
            self.fs.create_file(str(template_file), contents=json.dumps(self.expected_template))

    def test_build_template__sceptre_user_data_specified__logs_warning(self):
        self.builder.build_template(self.context, self.sceptre_user_data)
        self.assertTrue(self.logger.warning.called)

    def test_build_template__synthesizes_template_with_connection_manager_envs(self):
        self.bootstrapless_config.clear()
        self.builder.build_template(self.context, self.sceptre_user_data)
        expected_envs = {**self.environment_variables, "CDK_DEFAULT_REGION": self.region}
        self.assertEqual(self.subprocess_envs['synth'], expected_envs)

    def test_build_template__bootstrapless_config_specified__synthesizes_template_with_bootstrapless_envs(self):
        self.builder.build_template(self.context, self.sceptre_user_data)
        expected_envs = {**self.environment_variables, "CDK_DEFAULT_REGION": self.region}
        for key, value in self.bootstrapless_config.items():
            expected_envs[f'BSS_{key.upper()}'] = value
        self.assertEqual(self.subprocess_envs['synth'], expected_envs)

    def test_build_template_asset_manifest_only_has_template__does_not_publish_assets(self):
        self.builder.build_template(self.context, self.sceptre_user_data)
        self.assertFalse(self.artifacts_published)

    def test_build_template__asset_manifest_has_other_file_assets__publishes_artifacts_with_connection_manager_envs(self):
        self.manifest['files']['some_new_file.tar.gz'] = {'doesnt': 'matter'}
        self.builder.build_template(self.context, self.sceptre_user_data)
        self.assertTrue(self.artifacts_published)

    def test_build_template__asset_manifest_has_image_assets__publishes_artifacts_with_connection_manager_envs(self):
        self.manifest['dockerImages'] = {'doesnt': 'matter'}
        self.builder.build_template(self.context, self.sceptre_user_data)
        self.assertTrue(self.artifacts_published)

    def test_build_template__returns_template_from_json(self):
        result = self.builder.build_template(self.context, self.sceptre_user_data)
        self.assertEqual(
            self.expected_template,
            result
        )

    def test_build_template__running_cdk_assets_command_raises_called_process_error__reraises_cdk_invocation_error(self):
        self.raise_assets_error = True
        self.manifest['files']['some_new_file.tar.gz'] = {'doesnt': 'matter'}
        with self.assertRaises(CdkInvocationError):
            self.builder.build_template(self.context, self.sceptre_user_data)

    def test_build_template__running_cdk_synth_command_raises_called_process_error__reraises_cdk_invocation_error(self):
        self.raise_synth_error = True
        with self.assertRaises(CdkInvocationError):
            self.builder.build_template(self.context, self.sceptre_user_data)
