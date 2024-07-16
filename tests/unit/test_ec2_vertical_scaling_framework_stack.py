import aws_cdk as core
import aws_cdk.assertions as assertions

from ec2_vertical_scaling_framework.ec2_vertical_scaling_framework_stack import Ec2VerticalScalingFrameworkStack

# example tests. To run these tests, uncomment this file along with the example
# resource in ec2_vertical_scaling_framework/ec2_vertical_scaling_framework_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = Ec2VerticalScalingFrameworkStack(app, "ec2-vertical-scaling-framework")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
