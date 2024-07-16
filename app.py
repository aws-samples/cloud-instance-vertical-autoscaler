#!/usr/bin/env python3
import os
import cdk_nag
from aws_cdk import App, Environment, Aspects

from ec2_vertical_scaling_framework.ec2_vertical_scaling_framework_stack import Ec2VerticalScalingFrameworkStack

# for development, use account/region from cdk cli
account = os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"])
region = os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"])
dev_env = Environment(account=account, region=region)
print(f"Deploying in {account}/{region}")

app = App()
stage = app.node.try_get_context("stage")
stack = Ec2VerticalScalingFrameworkStack(app, "Ec2VerticalScalingFrameworkStack", env=dev_env
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    #env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

cdk_nag.NagSuppressions.add_stack_suppressions(
    stack,
    [
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-APIG4",
            reason="This endpoint is private and does not require authorization",
        ),
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-APIG3",
            reason="This endpoint is private and don't need AWS WAFv2 web ACL.",
        ),
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-APIG2",
            reason="The REST API does not need to have request validation enabled",
        ),
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-COG4",
            reason="This endpoint is private and does not require Cognito user pool authorizer",
        ),
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-IAM4",
            reason="Default role created by CDK LogRetention and BucketNotificationsHandler ",
        ),
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-IAM5",
            reason="Use case allows for wildcard actions",
        ),
    ],
)
Aspects.of(app).add(cdk_nag.AwsSolutionsChecks())

app.synth()
