# README

## What is this?

`sceptre-cdk-handler` is a TemplateHandler for Sceptre (versions 2.7 and up) that lets you use a
Python AWS CDK template as a stack's template.

This template handler will use the AWS CDK to synthesize the CDK stack into a CloudFormation template
and then run `npx cdk-assets` to publish any required assets to S3/ECR.

**By using the CDK Handler, you are letting CDK synthesize a template, and upload artifacts to S3 and ECR
and then using Sceptre to actually do the deployment of the template to a stack.**
In other words, by using this handler with Sceptre, _you skip ever using `cdk deploy`; It's not needed_.

By using this handler, you can now use CDK templates with all your favorite Sceptre commands, like
`launch`, `validate`, `generate`, and `diff` (along with all the rest)!

## How to install sceptre-cdk-handler

1) Install the Sceptre CDK handler using `pip install sceptre-cdk-handler`
2) Install the AWS CDK following the instructions in [AWS CDK Getting Started]((https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html))
3) Install the [CDK-Assets](https://www.npmjs.com/package/cdk-assets) NPM package using `npm install cdk-assets`

## How to use sceptre-cdk-handler

The template "type" for this handler is `cdk`. 

### Arguments:

* `path` (string, required): The path to the CDK template.
* `context` (object, optional): The context for the CDK Stack. See [CDK Context](https://docs.aws.amazon.com/cdk/v2/guide/context.html) for further info.

#### CDK Template Requirements

1. The CDK template must only contain one CDK Stack class, and the class must be called `CdkStack`. 

#### CDK Feature Flags and Custom Bootstrap

To set any [CDK Feature Flags](https://docs.aws.amazon.com/cdk/v2/guide/featureflags.html) or to specify a modified
[CDK Bootstrap](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html) qualifier, set these in the handler's
`context` argument. See [sceptre-example](sceptre-example) for an example of this.

### How does this handler work?

When using _only_ the CDK CLI (not Sceptre) to deploy using `cdk deploy`, the CDK CLI effectively performs
the following steps:

1. Synthesises any constructs defined within the CDK Class into a CloudFormation Template and a
bundle of required assets.
2. Publishes the assets to a CDK bootstrapped S3 bucket and/or ECR registry.
3. Creates/updates a CloudFormation stack from the synthesized template.

When you use Sceptre with this handler, the CDK handler performs steps 1-2 above to create a template
that Sceptre can use, **but it does not use CDK to deploy it!**. Instead, Sceptre can use that template
produced in step 1 above to perform all it's usual commands with all it's usual magic!

In other words, using this handler lets you use resolvers, put your CDK stack into StackGroups, let
you name your stack according to Sceptre's naming conventions, `validate`, `diff`, and more! Basically,
the CDK stack can be managed using Sceptre just like any other.

### IAM and authentication

This handler uses the stack's connection information to generate AWS environment variables and sets
those on the CDK process, ensuring that the AWS authentication configuration on the stack config and
project is carried over to CDK without any need for additional arguments.

**Important:** CDK creates CloudFormation-ready templates and uses `cdk_assets` to publish artifacts
to S3 and ECR in the process. This means that Sceptre commands that do not normally require S3 and ECR
actions (such as `generate`, `validate`, `diff`, and others) will require them when using this
handler. You will need to ensure that any user or role executing these commands has proper
permissions for these operations.

### Example Sceptre CDK Stack

[sceptre-example](sceptre-example)
