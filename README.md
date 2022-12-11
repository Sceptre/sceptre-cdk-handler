# README

## What is this?

`sceptre-cdk-handler` is a TemplateHandler for Sceptre (versions 2.7 and up) that lets you use a
Python AWS CDK stack class as a stack's template.

This template handler will use the AWS CDK to synthesize the CDK stack into a CloudFormation template
and then run `npx cdk-assets` to publish any required assets to S3/ECR.

**By using the CDK Handler, you are letting CDK synthesize a template, and upload artifacts to S3 and ECR
and then using Sceptre to actually do the deployment of the template to a stack.**
In other words, by using this handler with Sceptre, _you skip ever using `cdk deploy`; It's not needed_.

By using this handler, you can now use CDK templates with all your favorite Sceptre commands, like
`launch`, `validate`, `generate`, and `diff` (along with all the rest)!

## Why would you want to use CDK with Sceptre? Aren't those two ways to do the same thing?

## How to install sceptre-cdk-handler

1) Install the Sceptre CDK handler using `pip install sceptre-cdk-handler`
2) Install the AWS CDK following the instructions in [AWS CDK Getting Started](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html)
3) Install the [CDK-Assets](https://www.npmjs.com/package/cdk-assets) NPM package using `npm install cdk-assets`

## How to use sceptre-cdk-handler

The template "type" for this handler is `cdk`. 

### Deployment Types
The CDK Handler supports two different deployment types, which function somewhat differently. These
are "bootstrapped" and "bootstrapless", both passed to the `deployment_type` template handler argument

#### The "bootstrapped" deployment_type
The "bootstrapped" deployment type is a more typical CDK-like way to deploy infrastructure and 
conforms more to the standard ways CDK operates. If your organization has a lot of CDK infrastructure,
using this deployment_type likely will allow Sceptre to interoperate with existing patterns and 
policies. 

The `"bootstrapped"` deployment_type causes Sceptre assets (namely S3-destined files and 
ECR-destined images) to be deployed using the usual CDK Bootstrapped machinery. Specifically, by 
referencing a "qualifier", CDK looks for a corresponding stack in the AWS account that contains the
specific S3 bucket and ECR repo, as well as IAM roles to be assumed in order build and push those
assets up to the cloud.

In order to use the "bootstrapped" deployment type to push assets to the cloud, a CDK bootstrap stack 
with matching qualifier must already be deployed. It may be deployed via CDK (outside of Sceptre) or
you can use CDK to generate the bootstrap template for Sceptre to deploy using  
`cdk bootstrap --show-template > cdk-bootstrap.yaml`.

With that said, a bootstrap stack is not actually necessary if your stack includes no S3 or ECR 
assets to push.

**Important:** See section below on IAM implications and behavior of using this handler.

#### The "bootstrapless" deployment_type
While the "bootstrapped" deployment_type is more similar to CDK's way of operating, it's less typical
for Sceptre. Sceptre shines by allowing you to define infrastructure in different stacks and then
"wire them together" using powerful (and very handy) hooks and resolvers. Thus, a more "Sceptre-like"
way would be to avoid using the CDK bootstrap stack and just providing references to the required
asset-related infrastructure with resolvers like `!stack_output`.

The "bootstrapless" deployment_type uses the [cdk-bootstrapless-synthesizer](https://github.com/aws-samples/cdk-bootstrapless-synthesizer)
to handle assets without needing a bootstrap stack. Instead, you can provide the relevant asset-related
configurations as needed or desired, pulling values from other stack outputs using resolvers.

If you don't need to utilize a pre-existing bootstrap stack or don't need or want the overhead of 
having a bootstrap stack with all the infrastructure resources created along with that (many of which
you might not actually need), the "bootstrapless" deployment_type is a simpler approach.

### Arguments:

* `path` (string, required): The path to the CDK template.
* `class_name` (string, optional): The name of the Class in the CDK template to synthesize. Default: `CdkStack`.
* `context` (object, optional): The context for the CDK Stack. See [CDK Context](https://docs.aws.amazon.com/cdk/v2/guide/context.html) for further info.

#### Passing Data to a CDK Stack

There are two methods for passing data to a CDK Stack; using `sceptre_user_data` or CloudFormation parameters:

##### Sceptre User Data

Data can be passed to a CDK stack using the `sceptre_user_data` block of the Sceptre stack config. This will be resolved
when the template is synthesized and can contain complex objects.

##### CloudFormation Parameters

Data can be passed to a synthesized CDK template using standard CloudFormation parameters. These are resolved when the
CloudFormation stack is created from the template, but can only contain string or list values as supported by Cloudformation.

#### Stack Outputs

CloudFormation stack outputs can be defined in the CDK stack and then referenced from other Sceptre stacks using the
standard Sceptre `!stack_output` resolver. 

#### CDK Feature Flags and Custom Bootstrap

To set any [CDK Feature Flags](https://docs.aws.amazon.com/cdk/v2/guide/featureflags.html) or to specify a modified
[CDK Bootstrap](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html) qualifier, set these in the handler's
`context` argument. See [sceptre-example](sceptre-example) for an example of this.

Reminder: the `context` argument is a standard Sceptre resolvable property, so resolvers and/or Jinja variables can be used in the value. 

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

### Sceptre Management of the CDK Bootstrap

To optionally manage the CDK bootstrap CloudFormation template and stack with Sceptre, the bootstrap
template can be generated using the AWS CDK CLI: `cdk bootstrap --show-template > cdk-bootstrap.yaml`.
This can be deployed into a stack using the standard Sceptre process. 

### Example Sceptre CDK Stack

[sceptre-example](sceptre-example)
