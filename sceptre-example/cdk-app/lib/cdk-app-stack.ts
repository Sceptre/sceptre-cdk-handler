import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {aws_s3_assets} from "aws-cdk-lib";

export class CdkAppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    new aws_s3_assets.Asset(this, 'My file asset', {
      path: `${__dirname}/file-asset.txt`
    })
  }
}
