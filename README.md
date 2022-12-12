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

**Important:** See section below on IAM implications and behavior of using this handler and how it
corresponds to the roles in the bootstrap stack.

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

### Making your stack class
In order to properly support this handler's functionality, your Stack class on your Python file 
should subclass [`sceptre_cdk_handler.SceptreCdkStack`](sceptre_cdk_handler/cdk_builder.py).
Furthermore, it should have this `__init__` signature and invoke the base class `__init__()` this 
way:

```python
import aws_cdk
from sceptre_cdk_handler import SceptreCdkStack

# Subclass SceptreCDKStack
class CdkStack(SceptreCdkStack):
  def __init__(self, scope: aws_cdk.App, id: str, sceptre_user_data: dict, **kwargs):
    # Be sure you invoke super().__init__() and pass the **kwargs along to it
    super().__init__(scope, id, sceptre_user_data, **kwargs)
    # and then you can add your resources...
```

### Creating your StackConfig
Here is a simple example of how to configure the template handler. For a more complete Sceptre 
Project configuration, with both examples of both `bootstrapped` and `bootstrapless` configurations,
see [the example directory in this repo](sceptre-example/).

```yaml
template:
    # To use the CDK handler, you should use the "cdk" template type
    type: cdk
    # The path is always within your project's templates/ directory.
    path: lambda_stack.py
    deployment_type: bootstrapless
    # bootstrapless_config are the snake_cased arguments passed to the cdk-bootstrapless-synthesizer
    # for definitions of possible parameters, see the API docs here:
    # https://github.com/aws-samples/cdk-bootstrapless-synthesizer/blob/main/API.md
    bootstrapless_config:
        # You can use !stack_attr to reference other stack attributes that happen
        # to be set with resolvers to chain the resolver value.
        file_asset_bucket_name: !stack_attr template_bucket_name
        file_asset_prefix: {{template_key_prefix}}/cdk-assets
        image_asset_repository_name: !stack_output ecr.yaml::RepoName
    # You can explicitly define your stack name
    class_name: MyLambdaStack

# Parameters are DEPLOY-TIME values passed to the CloudFormation template. Your CDK stack construct
# needs to have CfnParameters in order to support this, though.
parameters:
    SpecialEnv: "This is my Sceptre test"

# sceptre_user_data is passed to your Stack Class's constructor for supplying values at COMPILE-TIME.
sceptre_user_data:
    special_variable: "use this directly at compile_time"
```

### Arguments:

* `path` (string, required): The path to the CDK template, relative to the `templates/` directory of
  your project.
* `deployment_type` (string, required): This determines the way CDK assets should be pushed to the
  cloud. Options are `"bootstrapless"` and `"bootstrapped"`. See section above on "How to use" for
  more details.
* `bootstrap_qualifier` (string, optional): This is only used if you are using the `bootstrapped`
  deployment type. This qualifier refers to the qualifier on a given CDK bootstrap stack in your 
  AWS account, whether deployed via CDK externally or within the same Sceptre project. If you use
  the `bootstrapped` deployment_type and do NOT specify a qualifier, CDK will default to the default
  qualifier and look to use that in your account.  
* `class_name` (string, optional): The name of the class on your CDK template to synthesize. 
  Defaults to `CdkStack`.
* `context` (dict, optional): The context for the CDK Stack. See [CDK Context](https://docs.aws.amazon.com/cdk/v2/guide/context.html) 
for further info on this.
* `bootstrapless_config` (dict, optional): This is only used if you are using the `bootstrapless`
deployment type. The keys here are the snake-casings of the documented parameters using the  
[cdk-bootstrapless-synthesizer](https://github.com/aws-samples/cdk-bootstrapless-synthesizer/blob/main/API.md):
    - "file_asset_bucket_name"
    - "file_asset_prefix"
    - "file_asset_publishing_role_arn"
    - "file_asset_region_set"
    - "image_asset_account_id"
    - "image_asset_publishing_role_arn"
    - "image_asset_region_set"
    - "image_asset_repository_name"
    - "image_asset_tag_prefix"
    - "template_bucket_name"

#### Passing Data to a CDK Stack

There are two methods for passing data to a CDK Stack; using `sceptre_user_data` or CloudFormation parameters:

##### Sceptre User Data

Data can be passed to a CDK stack using the `sceptre_user_data` block of the Sceptre stack config. 
This will be resolved when the template is synthesized and can contain complex objects. Since
`sceptre_user_data` is a resolvable property, you can use Resolvers to pass values from other 
deployed stacks and other sources as well.

##### CloudFormation Parameters

Data can be passed to a synthesized CDK template using standard CloudFormation parameters. 
These are resolved when the CloudFormation stack is created from the template, but can only contain 
string or list values as supported by Cloudformation. In order to use these, you need to create
[`CfnParameter`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.CfnParameter.html) resources 
in your stack class.

#### Stack Outputs

CloudFormation stack outputs can be defined in the CDK stack and then referenced from other Sceptre 
stacks using the standard Sceptre `!stack_output` resolver. In order to do this, your Stack Class
will need to create [`CfnOutput`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.CfnOutput.html) 
resources in your stack class.

#### CDK Feature Flags and Custom Bootstrap

To set any [CDK Feature Flags](https://docs.aws.amazon.com/cdk/v2/guide/featureflags.html), set these 
in the handler's `context` argument. See [lambda-stack-bootstrapped.yaml](sceptre-example/config/lambda-stack-bootstrapped.yaml) 
for an example of this.

Reminder: the `context` argument is a standard Sceptre resolvable property, so resolvers and/or Jinja 
variables can be used for values. 

### How does this handler work?

When using _only_ the CDK CLI (not Sceptre) to deploy using `cdk deploy`, the CDK CLI effectively performs
the following steps:

1. Synthesises any constructs defined within the CDK Class into a CloudFormation Template and a
bundle of required assets.
2. Publishes the assets to a CDK bootstrapped S3 bucket and/or ECR registry.
3. Creates/updates a CloudFormation stack from the synthesized template.

When you use Sceptre with this handler, the CDK handler performs steps 1-2 above to create a template
that Sceptre can use and publish the assets, **but it does not use CDK to deploy it!**. Instead, 
Sceptre can use that template produced in step 1 above to perform all its usual commands with all 
it's usual magic!

In other words, using this handler lets you use resolvers, put your CDK stack into StackGroups, let
you name your stack according to Sceptre's naming conventions, `validate`, `diff`, and more! Basically,
the CDK stack can be managed using Sceptre just like any other.

### IAM and authentication

There are several dimensions to how using this handler applies to IAM roles, policies, and permissions.

#### The Role to deploy the CloudFormation Stacks themselves
Sceptre will always use the AWS environment configuration, `profile` and/or `iam_role` to deploy 
the CloudFormation _Stacks_ themselves. This is consistent with how Sceptre always operates and it's 
no different when using this handler.

If you want Sceptre to assume the Deployment Role from the CDK bootstrap stack, you'll need to 
specify that role as the `iam_role` for your stack(s). If you want to do this, it's recommended you 
add the deployment role as an output on your bootstrap stack and then set `iam_role` using a 
`!stack_output` or `!stack_output_external` resolver. Be aware that your current AWS environment's
credentials will need permission to assume this role.

For more information on the `iam_role` configuration, see [Sceptre docs on it](https://docs.sceptre-project.org/3.2.0/docs/stack_config.html#iam-role).

#### The role provided to CloudFormation as the execution role
By default, Sceptre doesn't provide an [execution/service role](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-iam-servicerole.html) 
to CloudFormation for stacks. This is a permanent action with implications you should be aware of.
CDK _does_ tend to prefer using these, however, and one is created within the standard CDK bootstrap
stack.

If you want Sceptre to provide a service role to the stack, you'll need to specify that role as the
stack's `role_arn`. Thus, you can use the Bootstrapped CloudFormation execution role if you want to
or your organization generally requires that. If you want to do this, it's recommended you add the 
execution role as an output on your bootstrap stack and then set `role_arn` using `!stack_output` or
`!stack_output_external`.

For more information on the `role_arn` configuration, see [Sceptre docs on it](https://docs.sceptre-project.org/3.2.0/docs/stack_config.html#role-arn).

#### The roles used to push file and image assets to the Cloud

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
