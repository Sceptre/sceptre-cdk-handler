import aws_cdk
import constructs


class CdkStack(aws_cdk.Stack):
    '''
    Stack to perform the following:

    - Create an S3 Bucket
    - Deploy an 'object-key.txt' file to the bucket

    Notes:
    - 'sceptre_user_data' must contain the following keys:
        - 'bucket_name' - The name for the S3 Bucket
    '''

    def __init__(self, scope: constructs.Construct, construct_id: str, sceptre_user_data, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket_name = sceptre_user_data['bucket_name']
        s3_bucket = aws_cdk.aws_s3.Bucket(
            self, 'S3Bucket',
            bucket_name=bucket_name)

        aws_cdk.aws_s3_deployment.BucketDeployment(
            self,
            'S3Deployment',
            sources=[aws_cdk.aws_s3_deployment.Source.data(
                'object-key.txt', 'hello, world!')],
            destination_bucket=s3_bucket)
