#!/usr/bin/env node

// This is just the basic CDK app that is auto-generated using the CDK CLI.

import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { CdkAppStack } from '../lib/cdk-app-stack';
// You can use the BootstraplessStackSynthesizer if you'd like to pass the required resources directly
// instead of relying on the CDK Bootstrap stack.
// import { BootstraplessStackSynthesizer} from "cdk-bootstrapless-synthesizer";

const app = new cdk.App();

/* Note: it's very possible to define more than one Stack on the CDK app. You'll need to reference
 * the stack_logical_id (CdkAppStack) on the template handler config. If multiple stacks have
 * dependencies between each other (i.e. A second stack references variables from first stack),
 * you'll need to deploy BOTH via Sceptre and make sure to explicitly add the first stack config path
 * in the second stack's dependencies on the Sceptre StackConfig for it. */
new CdkAppStack(app, 'CdkAppStack', {
  /* You don't need to use a BootstraplessStackSynthesizer. However, if you do, the CDK handler will
   * set the appropriate environment variables from your bootstrapless_config so Sceptre can point
   * the synthesizer to the appropriate resources. Thus, you don't need any arguments here, just set
   * the synthesizer this way and set whatever bootstrapless_config you need. */
  // synthesizer: new BootstraplessStackSynthesizer()
});
