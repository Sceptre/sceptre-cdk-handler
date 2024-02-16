from pathlib import Path
from aws_cdk.aws_lambda import Runtime
from aws_cdk.aws_lambda_python_alpha import PythonFunction
from aws_cdk import CfnOutput, CfnParameter, aws_s3, aws_ecr_assets
from sceptre_cdk_handler import SceptreCdkStack


# Important: Notice how it subclasses SceptreCdkStack and passes **kwargs into the base class's
# __init__(). This is important to maintain compability with the different deployment_types.
class MyLambdaStack(SceptreCdkStack):
    def __init__(self, scope, id: str, sceptre_user_data: dict, **kwargs):
        super().__init__(scope, id, sceptre_user_data, **kwargs)
        # If you want to pass parameters like you do elsewhere in Sceptre, this works great!
        self.special_parameter = CfnParameter(self, "SpecialEnv")
        self.my_lambda = PythonFunction(
            self,
            "LambdaFunction",
            entry=str(Path(__file__).parent / "logging_lambda"),
            runtime=Runtime.PYTHON_3_9,
            handler="lambda_handler",
            index="handler.py",
            environment={
                "SPECIAL_ENV": self.special_parameter.value_as_string,
                # You can also access self.sceptre_user_data for compile-time variables
                "OTHER_ENVIRONMENT_VARIABLE": self.sceptre_user_data[
                    "special_variable"
                ],
            },
        )
        # Image asset uploads to ECR are fully supported as well
        self.image_asset = aws_ecr_assets.DockerImageAsset(
            self, "CustomImage", directory=str(Path(__file__).parent / "custom-image")
        )
        self.bucket = aws_s3.Bucket(self, "Bucket")

        # If you want to get values out of your stack for Sceptre to pass values to other stacks,
        # be sure to include CfnOutputs.
        self.function_output = CfnOutput(
            self, "OutputValue", value=self.my_lambda.function_arn
        )
