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

## Why would you want to use CDK with Sceptre?
**Aren't those two ways to do the same thing?**

CDK and Sceptre really specialize in two different things, though there's definitely overlap.

CDK's whole philosophy is that developers should be able to write code in a language they know and
have that compile into an _artifact_ that defines cloud infrastructure resources. Of course, that
"artifact" is ultimately a CloudFormation template. **CDK's specialty, thus, is really in _programmatic_
template generation with sane defaults and constructs that simplify infrastructure configuration.** It
hides a lot of the "magic" behind the scenes so developers can simply prescribe what they want. CDK
also has deployment mechanisms to deploy that infrastructure, but they aren't really CDK's strength.

90% of everything CDK does is at "compile-time", when the templates are being rendered. It has a very
limited ability to execute custom code at deployment time, and never really _between_ the deployments
of custom stacks and resources. Furthermore, its way of wiring together stacks uses CloudFormation
exported outputs and imports, which are rather rigid and can have a host of unintended consequences,
especially when values might change.

In contrast, Sceptre is a _deployment orchestration_ tool. It excels in deploying entire environments
of stacks, "wiring them together" using powerful (and easily customizable) resolvers, hooks, and
template handlers. **Sceptre is "template agnostic"**, supporting YAML and JSON CloudFormation
templates, even augmented with Jinja2 execution logic. Furthermore, out-of-the-box, Sceptre supports
_any custom Python code to generate templates_, with the only requirement being that it needs to return
a string.

_So why use CDK and Sceptre together?_ Because CDK provides excellent template generation capabilities
and Sceptre will gladly use those. Furthermore, Sceptre has the ability to easily wire together an
entire environment _regardless of how that environment's CloudFormation templates are generated._ Thus,
Sceptre will happily (and fairly intuitively) deploy (and "wire together") stacks developed in vanilla
CloudFormation YAML/JSON, templates augmented with Jinja2, Troposphere-generated templates,
AWS SAM templates, and CDK constructs. They can be deployed as a coherent environment that
interoperates, deployed with insight into the various dependencies between stacks. Furthermore,
using Sceptre's powerful hooks, you can execute customized pre-deployment and post-deployment code
to prepare the way for or clean up after a given stack deployment. This is powerful and not something
CDK provides a means to accomplish.

## How to install sceptre-cdk-handler

1) Install the Sceptre CDK handler using `pip install sceptre-cdk-handler`
2) Install the AWS CDK following the instructions in [AWS CDK Getting Started](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html)
3) Install the [CDK-Assets](https://www.npmjs.com/package/cdk-assets) NPM package using `npm install cdk-assets`

If your project will require building and pushing docker image assets to ECR, you will also need to
install docker and make it accessible on your PATH.

## How to use sceptre-cdk-handler

The template "type" for this handler is `cdk`.

### Deployment Types
The CDK Handler supports two different deployment types, which function somewhat differently. These
are "bootstrapped" and "bootstrapless", both passed to the `deployment_type` template handler argument.

#### The "bootstrapped" deployment_type
The "bootstrapped" deployment type is a more typical CDK-like way to deploy infrastructure and
conforms more to the standard ways _CDK_ operates. If your organization has a lot of CDK infrastructure,
using this deployment_type likely will allow Sceptre to interoperate with existing patterns and
policies.

The `"bootstrapped"` deployment_type causes Sceptre assets (namely S3-destined files and
ECR-destined images) to be deployed using the usual CDK-bootstrapped machinery. Specifically, by
referencing a "qualifier", CDK looks for a corresponding stack in the AWS account that contains the
specific S3 bucket and ECR repo, as well as IAM roles to be assumed in order to build and push those
assets up to the cloud.

In order to use the "bootstrapped" deployment type to push assets to the cloud, a CDK bootstrap stack
with matching qualifier must already be deployed. It may be deployed via CDK (outside of Sceptre) or
you can use CDK to generate the bootstrap template for Sceptre to deploy using
`cdk bootstrap --show-template > cdk-bootstrap.yaml`. It is recommended, if not reusing an existing
bootstrap stack, to deploy the bootstrap stack using Sceptre, as it will allow you to add outputs to
the template and reference those when setting up your CDK-based StackConfigs.

With that said, a bootstrap stack is not actually necessary if your stack includes no S3 or ECR
assets to push.

**Important:** See section below on IAM implications and behavior of using this handler and how it
corresponds to the roles in the bootstrap stack.

#### The "bootstrapless" deployment_type
While the "bootstrapped" deployment_type is more similar to CDK's way of operating, it's less typical
for Sceptre. Sceptre shines by allowing you to define your infrastructure however you want (in however
many stacks you want) and then "wire them together" using powerful (and very handy) hooks and
resolvers (like `!stack_output`). Thus, a more "Sceptre-like" way would be to avoid using the CDK
bootstrap stack and just providing references to the required asset-related infrastructure with
resolvers like `!stack_output`.

The "bootstrapless" deployment_type uses the [cdk-bootstrapless-synthesizer](https://github.com/aws-samples/cdk-bootstrapless-synthesizer)
to handle assets without needing a bootstrap stack. Instead, you can provide the relevant asset-related
configurations as needed, pulling values from other stack outputs using resolvers.

If you don't need to utilize a pre-existing bootstrap stack or don't need or want the overhead of
having a bootstrap stack with all the infrastructure resources created along with that (many of which
you might not actually need), the "bootstrapless" deployment_type is a simpler approach. However,
it will require you to supply the needed bucket, ECR repository, and other configurations if you're
deploying file or image assets. These will need to be supplied on the `bootstrapless_config` argument.

**Why wouldn't you want to use the CDK Boostrap stack if it provides "everything you'd need"?**
A CDK bootstrap stack has a lot of resources, defined all together in a single stack. It's
auto-generated via CDK. As such, it has a lot of resources you probably might not actually need,
depending on the sort of resources you have in your stack. For example, if you aren't actually
building and pushing images to ECR, creating a new ECR repository (which is in every CDK bootstrap
stack) isn't necessary.

Also, every CDK bootstrap stack contains 4 different IAM roles used for four different actions
(cloudformation service role, execution role, file asset pushing, image asset pushing). While it is
possible to make Sceptre use all four of these roles for all four of these actions, it's not the
normal way Sceptre operates (where it uses the same role/profile for the all deployment actions).
For more information on this handler and IAM, see [the section on IAM](#IAM-and-authentication).

If there is an existing bootstrap stack you need Sceptre to integrate
with, using `deployment_type: "bootstrapped"` will adhere to those norms. But if you don't need to
integrate with an existing CDK ecosystem and the rest of your infrastructure is deployed with
Sceptre as well, using `deployment_type: "bootstrapless"`  will prove a simpler, more straight-forward
way to deploy and integrate your CDK-stacks into the rest of your environment.

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
Project configuration, with examples of both `bootstrapped` and `bootstrapless` configurations,
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
        # to be set with resolvers to chain the resolver value. It makes sense to use the
        # same bucket as Sceptre uses for its template uploads for your file assets.
        file_asset_bucket_name: !stack_attr template_bucket_name
        # It can be useful to apply the same prefix as your template_key_prefix to ensure your
        # assets are namespaced similarly to the rest of Sceptre's uploaded artifacts.
        file_asset_prefix: {{template_key_prefix}}/cdk-assets
        # You can use !stack_output (and other resolvers) in all of these configurations, which is
        # especially helpful when "wiring together" this stack with other stacks deployed in your
        # environment.
        image_asset_repository_name: !stack_output ecr.yaml::RepoName
    # You can explicitly define your stack name, or use the default class name "CdkStack"
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

* `path` (string, required): The path to the CDK template file, relative to the `templates/` directory of
  your project. This should be a python file with your stack class, subclassing `SceptreCdkStack`.
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
    - "file_asset_bucket_name" (required if your stack has file assets)
    - "file_asset_prefix"
    - "file_asset_publishing_role_arn"
    - "file_asset_region_set"
    - "image_asset_account_id"
    - "image_asset_publishing_role_arn"
    - "image_asset_region_set"
    - "image_asset_repository_name" (required if your stack has image assets)
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

### Importing from other files
Your CDK Stack module _can_ import from other packages/modules in your local directory structure.
This is useful to break your constructs up with a file-based organization. While you could
theoretically point the CDK handler to any python file path on your computer, there are limitations
on how other modules will be accessible for import:

1. All modules/packages to be imported **must be somewhere inside your current working directory.**
If the files you intend to import are _outside_ your CWD, they will not be accessible.
2. They must _either_...
   1. Be in the immediate directory structure between your CWD and the python file your
handler is referencing via `path` _or_
   2. Be inside importable python packages that _are_ in the immediate structure between your CWD and
your handler's `path`.

```
other_directory/
    file.py                         # You CANNOT import this because it is out of your CWD
project_directory/
   templates/                       # No __init__.py in here, but it's in the directory hierarchy of
                                    # your_cdk_stack.py, so you can technically import any direct
                                    # children of this directory.

       random_python_file.py        # You CAN import this ("import random_python_file")
       unrelated_directory/         # No __init__.py in here...
           nested_dir/              # No __init__.py in here...
               some_python_file.py  # You CANNOT import this because this isn't in a python package
       my_cdk_files/
           __init__.py              # this lets you import from this dir (my_cdk_files/)
           constructs/
               __init__.py          # This lets you import from this dir (constructs/)
               ec2/
                   __init__.py      # This lets you import from this dir (ec2/)
                   vpc.py           # You CAN import this (my_cdk_files.constructs.ec2.vpc)
                   autoscaling.py   # You CAN import this (my_cdk_files.constructs.ec2.autoscaling)
           stacks/
               __init__.py          # This lets you import from this dir (my_cdk_files/)
               >> your_cdk_stack.py # This is where your CDK Handler points to
   scripts/
      some_dir/
          random_python_file.py     # You cannot import this because it's not in the directory
                                    # hierarchy of your_cdk_stack.py and it's not in a python package
                                    # importable from any of the directories that ARE in that hierarchy.
   app/
       __init__.py                  # This makes app/ an importable python package
       my_application_resources.py  # You CAN import this (app.my_application_resources)
```

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
Some sorts of CDK constructs require the packaging and upload to the cloud of S3-destined file assets
or ECR-destined image assets. These will each be published with different IAM permissions, depending
on how you've configured your CDK handler.

* If using the `"bootstrapless"` `deployment_type` and you have _not_ explicitly specified a
`file_asset_publishing_role_arn` or `image_asset_publishing_role_arn`, CDK will use your configured
Sceptre deployment role (if you have an iam_role specified), your profile (if specified), or your
AWS environment credentials to push those credentials. If this is the case, be sure your credentials
have permissions to perform those Put/Push operations.
* If using the `"bootstrapless"` `deployment_type` and you _have_ explicitly specified a
`file_asset_publishing_role_arn` and/or `image_asset_publishing_role_arn`, CDK will assume those
roles (from your current deployment iam_role, profile, or AWS environment credentials) for their
respective actions in order to perform those Put/Push operations. If this is the case, be sure that
your iam_role, profile, or AWS environment credentials have permission to assume those roles.
* If using the `"bootstrapped"` `deployment_type`, CDK will assume the respective roles from your
bootstrap stack in order to perform those operations. If this is the case, be sure that
your iam_role, profile, or AWS environment credentials have permission to assume those roles.

### Example Sceptre CDK Stack

[sceptre-example](sceptre-example)
