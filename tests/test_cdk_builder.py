import logging
import subprocess
import sys
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
    CdkBuilder
)


class TestBootstrappedCdkBuilder(TestCase):
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
        self.environment_variables = {
            "PATH": "blah:blah:blah",
            "AWS_ACCESS_KEY_ID": "old key",
            "AWS_SECRET_ACCESS_KEY": "old secret",
            "AWS_SESSION_TOKEN": "old token"
        }

        self.builder = BootstrappedCdkBuilder(
            self.logger,
            self.connection_manager,
            subprocess_run=self.subprocess_run,
            app_class=self.app_class,
            environment_variables=self.environment_variables
        )

        self.stack_class = create_autospec(SceptreCdkStack)
        self.stack_class.__name__ = "MyFancyStack"
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

    def test_build_template__synthesized_assembly_has_only_template_asset__does_not_publish_assets(self):
        self.manifest.contents.docker_images.clear()
        self.manifest.contents.files.pop('hashyhashhash')
        self.build()
        self.subprocess_run.assert_not_called()

    def test_build_template__no_session_token__runs_cdk_assets_publish_on_the_asset_artifacts_file_with_correct_envs(self):
        self.credentials.token = None
        self.build()
        expected_command = 'npx cdk-assets -v publish --path asset/file/path'
        expected_envs = {
            **self.environment_variables,
            **{
                "AWS_ACCESS_KEY_ID": self.credentials.access_key,
                "AWS_SECRET_ACCESS_KEY": self.credentials.secret_key,
                "AWS_DEFAULT_REGION": self.connection_manager.region,
                "CDK_DEFAULT_REGION": self.connection_manager.region,
                "AWS_REGION": self.connection_manager.region
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

    def test_build_template__aws_session_token_in_envs__does_not_publish_assets_with_profile_specified(self):
        self.environment_variables['AWS_PROFILE'] = 'dont_use_me'
        called = False

        def fake_subprocess(*args, env, **kwargs):
            nonlocal called
            self.assertNotIn('AWS_PROFILE', env)
            called = True

        self.subprocess_run.side_effect = fake_subprocess

        self.build()
        self.assertTrue(called)

    def test_build_template__with_session_token__runs_cdk_assets_publish_on_the_asset_artifacts_file_with_correct_envs(self):
        self.credentials.token = "special session token"
        self.build()
        expected_command = 'npx cdk-assets -v publish --path asset/file/path'
        expected_envs = {
            **self.environment_variables,
            **{
                "AWS_ACCESS_KEY_ID": self.credentials.access_key,
                "AWS_SECRET_ACCESS_KEY": self.credentials.secret_key,
                "AWS_SESSION_TOKEN": self.credentials.token,
                "AWS_DEFAULT_REGION": self.connection_manager.region,
                "CDK_DEFAULT_REGION": self.connection_manager.region,
                "AWS_REGION": self.connection_manager.region
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


class TestBootstraplessCdkBuilder(TestCase):
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
        self.synthesizer_config = {
            'file_asset_bucket_name': 'my_bucket'
        }
        self.synthesizer_class = create_autospec(BootstraplessStackSynthesizer)
        self.builder = BootstraplessCdkBuilder(
            self.logger,
            self.connection_manager,
            self.synthesizer_config,
            subprocess_run=self.subprocess_run,
            app_class=self.app_class,
            environment_variables=self.environment_variables,
            synthesizer_class=self.synthesizer_class
        )

        self.stack_class = create_autospec(SceptreCdkStack)
        self.stack_class.__name__ = "MyFancyBootstraplessStack"
        self.context = {'hello': 'you'}
        self.sceptre_user_data = {'user': 'data'}

    def test_build_template__no_synthesizer_config__instantiates_synthesizer_with_no_kwargs(self):
        self.synthesizer_config.clear()
        self.builder.build_template(self.stack_class, self.context, self.sceptre_user_data)
        self.synthesizer_class.assert_any_call(**self.synthesizer_config)

    def test_build_template__instantiates_synthesizer_with_synthesizer_config_kwargs(self):
        self.builder.build_template(self.stack_class, self.context, self.sceptre_user_data)
        self.synthesizer_class.assert_any_call(**self.synthesizer_config)

    def test_build_template__invalid_synthesizer_arguments__raises_template_handler_arguments_invalid_error(self):
        self.synthesizer_config['bad'] = 'not-recognized'
        with self.assertRaises(TemplateHandlerArgumentsInvalidError):
            self.builder.build_template(self.stack_class, self.context, self.sceptre_user_data)

    def test_build_template__instantiates_stack_with_synthesizer(self):
        self.builder.build_template(self.stack_class, self.context, self.sceptre_user_data)
        self.stack_class.assert_any_call(
            self.app_class.return_value,
            CdkBuilder.STACK_LOGICAL_ID,
            self.sceptre_user_data,
            synthesizer=self.synthesizer_class.return_value
        )
