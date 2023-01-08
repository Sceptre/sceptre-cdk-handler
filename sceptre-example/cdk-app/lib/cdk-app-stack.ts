/* This is an example Stack construct defined in CDK using a non-Python language. It is imported
   and added to the CDK app in bin/cdk-app.ts. This isn't a very comprhensive example, but it's
   enough to demonstrate how a non-Python CDK app could be deployed via Sceptre, even if it has
   assets that need to be deployed.
 */

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {aws_s3_assets} from "aws-cdk-lib";

export class CdkAppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // You can create whatever sort of CDK resources you want, even those that include image and
    // file assets. This is just a minimal example as a proof of concept.
    new aws_s3_assets.Asset(this, 'My file asset', {
      path: `${__dirname}/file-asset.txt`
    })
  }
}
