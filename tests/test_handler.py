import importlib.machinery
import importlib.util
import logging
import os
import shutil
import subprocess
import textwrap
from unittest import TestCase

import pytest
from aws_cdk.cx_api import CloudAssembly
from botocore.credentials import Credentials
from boto3.session import Session
from sceptre import exceptions
from template_handler.cdk import CDK
from unittest.mock import Mock, MagicMock
from sceptre.connection_manager import ConnectionManager

# name = 'dev/cdk'
# sceptre_user_data = {'object_name': 'object-key.txt'}
# stack_group_config = {'project_code': 'sceptre'}
# arguments = {
#     'path': 'CDK/s3.py'
# }
# aws_profile = 'profile1'
# aws_region = 'eu-west-1'
# aws_iam_role = 'role1'
#
# aws_access_key = '123'
# aws_secret_key = '456'
# aws_token = '789'
#
# connection_manager = MagicMock(
#     spec=ConnectionManager
# )


class TestCDK(TestCase):
    def test_handle__class_name_as_argument__imports_named_class_from_specified_template_path(self):
        assert False

    def test_handle__project_directory_is_different_from_cwd__imports_class_from_project_directory(self):
        assert False

    def test_handle__no_class_name_argument__imports_default_class_name_from_template_path(self):
        assert False

    def test_handle__builds_template_for_imported_stack_with_context_and_sceptre_user_data(self):
        assert False

    def test_handle__returns_dumped_yaml_template(self):
        assert False


class TestCdkBuilder(TestCase):
    def test_build_template__adds_stack_instance_to_app_with_user_data(self):
        assert False

    def test_build_template__synthesized_assembly_has_no_manifest_artifact__raises_sceptre_exception(self):
        assert False

    def test_build_template__no_session_token__runs_cdk_assets_publish_on_the_asset_artifacts_file_with_correct_envs(self):
        assert False

    def test_build_template__with_session_token__runs_cdk_assets_publish_on_the_asset_artifacts_file_with_correct_envs(self):
        assert False

    def test_build_template__returns_template_from_cloud_assembly_for_stack(self):
        assert False


class TestClassImporter(TestCase):
    def test_import_class__imports_class_from_referenced_file(self):
        assert False

    def test_import_class__named_class_isnt_on_module__raises_sceptre_exception(self):
        assert False








# def test_schema():
#     """
#     Test schema function
#     """
#     # Arrange
#     cdk_handler = CDK(
#         name,
#         arguments=arguments,
#         sceptre_user_data=sceptre_user_data,
#         connection_manager=connection_manager,
#         stack_group_config=stack_group_config)
#
#     # Act
#     result = cdk_handler.schema()
#
#     # Assert
#     assert result['type'] == 'object'
#     assert result['properties'] is not None
#     assert result['required'] is not None
#
#
# def test_get_envs():
#     """
#     Test _get_envs function
#     """
#     # Arrange
#     credentials = Credentials(
#         access_key=aws_access_key,
#         secret_key=aws_secret_key
#     )
#
#     connection_manager = MagicMock(
#         spec=ConnectionManager,
#         profile=aws_profile,
#         region=aws_region,
#         iam_role=aws_iam_role
#     )
#
#     connection_manager._get_session = MagicMock(
#         spec_set=Session
#     )
#     connection_manager._get_session.return_value.get_credentials.return_value = credentials
#
#     cdk_handler = CDK(
#         name,
#         arguments=arguments,
#         sceptre_user_data=sceptre_user_data,
#         connection_manager=connection_manager,
#         stack_group_config=stack_group_config
#     )
#
#     # Act
#     result = cdk_handler._get_envs()
#
#     # Assert
#     assert result.get('AWS_ACCESS_KEY_ID') == aws_access_key
#     assert result.get('AWS_SECRET_ACCESS_KEY') == aws_secret_key
#     assert result.get('AWS_SESSION_TOKEN') is None
#
#
# def test_get_envs_with_session_token():
#     """
#     Test _get_envs function
#     """
#     # Arrange
#     credentials = Credentials(
#         access_key=aws_access_key,
#         secret_key=aws_secret_key,
#         token=aws_token
#     )
#
#     connection_manager = MagicMock(
#         spec=ConnectionManager,
#         profile=aws_profile,
#         region=aws_region,
#         iam_role=aws_iam_role
#     )
#
#     connection_manager._get_session = MagicMock(
#         spec_set=Session
#     )
#     connection_manager._get_session.return_value.get_credentials.return_value = credentials
#
#     cdk_handler = CDK(
#         name,
#         arguments=arguments,
#         sceptre_user_data=sceptre_user_data,
#         connection_manager=connection_manager,
#         stack_group_config=stack_group_config
#     )
#
#     # Act
#     result = cdk_handler._get_envs()
#
#     # Assert
#     assert result.get('AWS_ACCESS_KEY_ID') == aws_access_key
#     assert result.get('AWS_SECRET_ACCESS_KEY') == aws_secret_key
#     assert result.get('AWS_SESSION_TOKEN') == aws_token
#
#
# def test_cmd_exists():
#     """
#     Test _cmd_exists function
#     """
#     # Arrange
#     cdk_handler = CDK(
#         name,
#         arguments=arguments,
#         sceptre_user_data=sceptre_user_data,
#         connection_manager=connection_manager,
#         stack_group_config=stack_group_config
#     )
#
#     shutil.which = MagicMock(
#         return_value='/bin/mock_cmd'
#     )
#
#     # Act
#     result = cdk_handler._cmd_exists('mock_cmd')
#
#     # Assert
#     assert result == True
#     shutil.which.assert_called_once()
#
#
# def test_cmd_exists_no_command():
#     """
#     Test _cmd_exists function
#     """
#     # Arrange
#     cdk_handler = CDK(
#         name,
#         arguments=arguments,
#         sceptre_user_data=sceptre_user_data,
#         connection_manager=connection_manager,
#         stack_group_config=stack_group_config
#     )
#
#     shutil.which = MagicMock(
#         return_value=None
#     )
#
#     # Act
#     result = cdk_handler._cmd_exists('mock_cmd')
#
#     # Assert
#     assert result == False
#     shutil.which.assert_called_once()
#
#
# def test_node_package_exists():
#     """
#     Test _node_package_exists function
#     """
#     # Arrange
#     cdk_handler = CDK(
#         name,
#         arguments=arguments,
#         sceptre_user_data=sceptre_user_data,
#         connection_manager=connection_manager,
#         stack_group_config=stack_group_config
#     )
#
#     success = 0
#     failure = 1
#     workspace_node_package = 'workspace'
#     global_node_package = 'global'
#     node_package_not_exists = 'notexist'
#
#     def run_side_effect(cmd, **kwargs):
#         completed_process = MagicMock(
#             spec=subprocess.CompletedProcess)
#         if cmd == f'npm list {workspace_node_package}':
#             completed_process.returncode = success
#             return completed_process
#         elif cmd == f'npm --global list {global_node_package}':
#             completed_process.returncode = success
#             return completed_process
#         else:
#             completed_process.returncode = failure
#             return completed_process
#
#     cdk_handler._subprocess_run = MagicMock(
#         side_effect=run_side_effect
#     )
#
#     # Act
#     result = cdk_handler._node_package_exists(workspace_node_package)
#
#     # Assert
#     assert result == True
#
#     # Act
#     result = cdk_handler._node_package_exists(global_node_package)
#
#     # Assert
#     assert result == True
#
#     # Act
#     result = cdk_handler._node_package_exists(node_package_not_exists)
#
#     # Assert
#     assert result == False
#
#
# def test_check_prerequisities():
#     """
#     Test _check_prerequisities function
#     """
#     # Arrange
#     cdk_handler = CDK(
#         name,
#         arguments=arguments,
#         sceptre_user_data=sceptre_user_data,
#         connection_manager=connection_manager,
#         stack_group_config=stack_group_config
#     )
#
#     cdk_handler._cmd_exists = MagicMock(
#         return_value=True
#     )
#     cdk_handler._node_package_exists = MagicMock(
#         return_value=True
#     )
#
#     cdk_handler._check_prerequisites()
#
#     cdk_handler._cmd_exists = MagicMock(
#         return_value=False
#     )
#     cdk_handler._node_package_exists = MagicMock(
#         return_value=True
#     )
#
#     # Act
#     with pytest.raises(exceptions.SceptreException) as excep:
#         cdk_handler._check_prerequisites()
#
#         # Assert
#         assert "Command prerequisite node not found" in excep
#
#     # Arrange
#     cdk_handler._cmd_exists = MagicMock(
#         return_value=True
#     )
#     cdk_handler._node_package_exists = MagicMock(
#         return_value=False
#     )
#
#     # Act
#     with pytest.raises(exceptions.SceptreException) as excep:
#         cdk_handler._check_prerequisites()
#
#         # Assert
#         assert "Node Package prerequisite 'sdk-assets' not found" in excep
#
#
# def test_import_python_template_module():
#     """
#     Test _import_python_template_module function
#     """
#     # Arrange
#     cdk_handler = CDK(
#         name,
#         arguments=arguments,
#         sceptre_user_data=sceptre_user_data,
#         connection_manager=connection_manager,
#         stack_group_config=stack_group_config
#     )
#
#     cwd = os.getcwd()
#     os.chdir('sceptre-example')
#     cdk_template_path = 'CDK/s3.py'
#
#     cdk_handler._import_python_template_module(cdk_template_path=cdk_template_path)
#
#     cdk_template_path = 'CDK/non-existent-template.py'
#
#     # Act
#     with pytest.raises(exceptions.SceptreException) as excep:
#         cdk_handler._import_python_template_module(cdk_template_path=cdk_template_path)
#
#         # Assert
#         assert f"Template not found: {cdk_template_path}" in excep
#
#     # Cleanup
#     os.chdir(cwd)
#
#
# def test_cdk_synthesize():
#     """
#     Test _cdk_synthesize function
#     """
#     # Arrange
#     cdk_handler = CDK(
#         name,
#         arguments=arguments,
#         sceptre_user_data=sceptre_user_data,
#         connection_manager=connection_manager,
#         stack_group_config=stack_group_config
#     )
#
#     cwd = os.getcwd()
#     os.chdir('sceptre-example')
#     cdk_template_path = 'CDK/s3.py'
#     template_module = cdk_handler._import_python_template_module(cdk_template_path=cdk_template_path)
#     stack_name = 'CDKStack'
#
#     # Act
#     result = cdk_handler._cdk_synthesize(stack_name, template_module=template_module)
#
#     # Assert
#     assert isinstance(result, CloudAssembly) == True
#
#     # Cleanup
#     os.chdir(cwd)
#
#
# def test_publish_cdk_assets():
#     """
#     Test _publish_cdk_assets function
#     """
#     # Arrange
#     cdk_handler = CDK(
#         name,
#         arguments=arguments,
#         sceptre_user_data=sceptre_user_data,
#         connection_manager=connection_manager,
#         stack_group_config=stack_group_config
#     )
#
#     cwd = os.getcwd()
#     os.chdir('sceptre-example')
#     cdk_template_path = 'CDK/s3.py'
#     module = cdk_handler._import_python_template_module(cdk_template_path=cdk_template_path)
#     stack_name = 'CDKStack'
#     app_synth = cdk_handler._cdk_synthesize(stack_name, template_module=module)
#
#     success = 0
#     failure = 1
#     completed_process = MagicMock(
#         spec=subprocess.CompletedProcess,
#         returncode=success,
#         stderr=MagicMock(
#             decode=MagicMock(
#                 return_value=''
#             )
#         )
#     )
#
#     cdk_handler._subprocess_run = MagicMock(
#         return_value=completed_process
#     )
#
#     cdk_handler._get_envs = MagicMock()
#
#     # Act
#     cdk_handler._publish_cdk_assets(app_synth=app_synth)
#
#     # Assert
#     cdk_handler._subprocess_run.assert_called_once()
#
#     # Cleanup
#     os.chdir(cwd)
#
#
# def test_handler():
#     """
#     Test handler function
#     """
#     # Arrange
#     cdk_handler = CDK(
#         name,
#         arguments=arguments,
#         sceptre_user_data=sceptre_user_data,
#         connection_manager=connection_manager,
#         stack_group_config=stack_group_config
#     )
#
#     module = MagicMock()
#     app_synth = MagicMock()
#     app_synth.get_stack_by_name.return_value.template = {
#         'Resources': {
#             'Resource1': {
#                 'Type': 'AWS::S3::Bucket'
#             }
#         }
#     }
#     template_result = textwrap.dedent(
#         """\
#         Resources:
#           Resource1:
#             Type: AWS::S3::Bucket
#         """)
#
#     cdk_handler._check_prerequisites = MagicMock()
#     cdk_handler._import_python_template_module = MagicMock(return_value=module)
#     cdk_handler._cdk_synthesize = MagicMock(return_value=app_synth)
#     cdk_handler._publish_cdk_assets = MagicMock()
#
#     # Act
#     result = cdk_handler.handle()
#
#     # Assert
#     assert result == template_result
#     cdk_handler._check_prerequisites.assert_called_once()
#     cdk_handler._import_python_template_module.assert_called_once_with(cdk_template_path=cdk_handler.cdk_template_path)
#     cdk_handler._cdk_synthesize.assert_called_once_with(stack_name=cdk_handler._internal_stack_name, template_module=module)
#     cdk_handler._publish_cdk_assets.assert_called_once_with(app_synth=app_synth)
#     app_synth.get_stack_by_name.assert_called_once_with(cdk_handler._internal_stack_name)
