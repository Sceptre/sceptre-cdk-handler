import aws_cdk
import constructs


class CdkStack(aws_cdk.Stack):
    '''
    Stack to perform the following:

    - Create an S3 Bucket named from the 'BucketName' CloudFormation template parameter
    - Deploy a file to the bucket with a key name of the sceptre user data 'object_name' property.

    Notes:
    - 'sceptre_user_data' must contain the following keys:
        - 'object_name' - The name of the S3 Object to create

    - Parameters:
        - 'BucketName' - The name for the S3 Bucket

    - Outputs:
        - 'BucketDomainName' - The domain name of the S3 Bucket
    '''

    def __init__(self, scope: constructs.Construct, construct_id: str, sceptre_user_data, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket_name=aws_cdk.CfnParameter(self,
            id='BucketName',
            description='The name for the S3 Bucket',
            )

        s3_bucket = aws_cdk.aws_s3.Bucket(
            self, 'S3Bucket',
            bucket_name=bucket_name.value_as_string)

        aws_cdk.aws_s3_deployment.BucketDeployment(
            self,
            'S3Deployment',
            sources=[aws_cdk.aws_s3_deployment.Source.data(
                sceptre_user_data['object_name'], 'hello, world!')],
            destination_bucket=s3_bucket)

        aws_cdk.CfnOutput(self,
            id='BucketDomainName',
            description='The domain name of the S3 Bucket',
            value=s3_bucket.bucket_domain_name)
