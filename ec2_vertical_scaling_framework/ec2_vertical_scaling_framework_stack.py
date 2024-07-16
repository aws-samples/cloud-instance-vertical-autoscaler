from aws_cdk import (
    # Duration,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_cloudwatch,
    aws_events as events,
    aws_events_targets as targets,
    aws_apigateway as apigateway,
    aws_scheduler as scheduler,
    aws_logs as logs,
    Duration,
)
from constructs import Construct
import json

class Ec2VerticalScalingFrameworkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # get context
        sns_topic_arn = self.node.try_get_context("sns_topic_arn")
        resize_time_zone = self.node.try_get_context("resize_time_zone")
        instance_id = self.node.try_get_context("instance_id")
        cpu_threshold_upsize = self.node.try_get_context("cpu_threshold_upsize")
        mem_threshold_upsize = self.node.try_get_context("mem_threshold_upsize")
        cpu_threshold_downsize = self.node.try_get_context("cpu_threshold_downsize")
        mem_threshold_downsize = self.node.try_get_context("mem_threshold_downsize")

        # policy document for the EventBridge Scheduler calling lamada
        policy_string_for_scheduler_call_lambda='''
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "lambda:InvokeFunction"
            ],
            "Resource": [
                "*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "*",
            "Condition": {
                "StringEquals": {
                    "iam:PassedToService": "lambda.amazonaws.com"
                }
            }
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:DescribeLogStreams",
                "logs:GetLogEvents",
                "logs:FilterLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/*"
        }
    ]
}
        '''
        
        policy_document_for_scheduler_call_lambda=iam.PolicyDocument.from_json(json.loads(policy_string_for_scheduler_call_lambda))
        # create IAM role with trust relationship by Principal scheduler.amazonaws.com by Custom policy 
        # this IAM role will be used by the EventBridge Scheduler
        #
        ec2_resize_scheduler_role = iam.Role(
            self, "Ec2ResizeSchedulerRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("scheduler.amazonaws.com"),
            ),
            inline_policies={"ec2vs-policy-scheduler-call-lambda":policy_document_for_scheduler_call_lambda}
        )

        policy_string_for_lambda_doresize='''
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ec2policy",
            "Effect": "Allow",
            "Action": [
                "ec2:RunInstances",
                "ec2:StartInstances",
                "ec2:StopInstances",
                "ec2:TerminateInstances",
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceStatus",
                "ec2:DescribeInstanceTypes",
                "ec2:ModifyInstanceAttribute",
                "ec2:CreateNetworkInterface",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DescribeSubnets",
                "ec2:DeleteNetworkInterface",
                "ec2:AttachNetworkInterface",
                "ec2:DetachNetworkInterface",
                "ec2:AssignPrivateIpAddresses",
                "ec2:UnassignPrivateIpAddresses",
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets",
                "ec2:DescribeSecurityGroups",
                "ec2:CreateSecurityGroup",
                "ec2:DeleteSecurityGroup"
            ],
            "Resource": "*"
        },
        {
            "Sid": "snspolicy",
            "Effect": "Allow",
            "Action": [
                "sns:Publish",
                "sns:PutDataProtectionPolicy",
                "sns:SetTopicAttributes"
            ],
            "Resource": "*"
        },
        {
            "Sid": "ssmpolicy",
            "Effect": "Allow",
            "Action": [
                "ssm:DescribeAutomationExecutions",
                "ssm:GetAutomationExecution",
                "ssm:DescribeAutomationStepExecutions",
                "ssm:ResumeSession",
                "ssm:StartAutomationExecution",
                "ssm:SendAutomationSignal",
                "ssm:TerminateSession",
                "ssm:StopAutomationExecution",
                "ssm:StartSession"
            ],
            "Resource": "*"
        },
        {
            "Sid": "cloudwatchpolicy",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
       ''' 
        policy_document_for_lambda_doresize=iam.PolicyDocument.from_json(json.loads(policy_string_for_lambda_doresize))
        #
        # Create the Lambda function EC2Resize to resize the EC2
        #
        # Define the IAM role for the Lambda function
        EC2ResizeRole = iam.Role(
            self, "EC2ResizeLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
           inline_policies={"ec2vs-policy-lambda-doresize":policy_document_for_lambda_doresize}
        )
        ec2_resize_lambda = lambda_.Function(
            self, "EC2Resize",
            code=lambda_.Code.from_asset("ec2_vertical_scaling_framework/lambda/ec2-resize"),
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="ec2-resize.lambda_handler",
            role=EC2ResizeRole,
            timeout=Duration.seconds(60),
        )

        policy_string_for_lambda_createscheduler='''
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ec2policy",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceTypes"
            ],
            "Resource": "*"
        },
        {
            "Sid": "snspolicy",
            "Effect": "Allow",
            "Action": [
                "sns:Publish",
                "sns:PutDataProtectionPolicy",
                "sns:SetTopicAttributes"
            ],
            "Resource": "*"
        },
        {
            "Sid": "eventbridgeschedule2policy",
            "Effect": "Allow",
            "Action": [
                "scheduler:CreateSchedule",
                "scheduler:CreateScheduleGroup",
                "scheduler:GetSchedule",
                "scheduler:GetScheduleGroup"
            ],
            "Resource": "*"
        },
        {
            "Sid": "cloudwatchpolicy",
            "Effect": "Allow",
            "Action": [
                "cloudwatch:PutMetricData",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        },
        {
            "Sid": "iampolicy",
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "arn:aws:iam::*:role/*",
            "Condition": {
                "StringLike": {
                    "iam:PassedToService": "scheduler.amazonaws.com"
                }
            }
        }
    ]
}
'''
        policy_document_for_lambda_createscheduler=iam.PolicyDocument.from_json(json.loads(policy_string_for_lambda_createscheduler))
        #
        # Create the Lambda function EC2SchedulerResize which can create schedule for callling resize lambda
        # using role ec2_scheduler_resize_lambda_role for itself,and using ec2_scheduler_resize_lambda_role for created scheduler
        #
        ec2_scheduler_resize_lambda_role = iam.Role(
            self, "EC2SchedulerResizeRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={"ec2vs-policy-lambda-createscheduler":policy_document_for_lambda_createscheduler}
        )
        ec2_scheduler_resize_lambda = lambda_.Function(
            self, "EC2SchedulerResize",
            code=lambda_.Code.from_asset("ec2_vertical_scaling_framework/lambda/ec2-scheduler"),
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="ec2-scheduler-resize.lambda_handler",
            role=ec2_scheduler_resize_lambda_role,
            environment={
                "ec2_resize_lambda_ARN": ec2_resize_lambda.function_arn,
                "sns_topic_arn": sns_topic_arn,
                "scheduler_role_arn": ec2_resize_scheduler_role.role_arn,
                "resize_time_zone": resize_time_zone
            },
            timeout=Duration.seconds(60),
        )

        #
        # Create the API Gateway EC2SchedulerResizeAPI to create a resize scheduler
        #
        log_group = logs.LogGroup(self, "Ec2AutoScalingApiGatewayAccessLogs",
            retention=logs.RetentionDays.ONE_WEEK  # Adjust retention as needed
        )

        policy_statement = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            principals=[iam.AnyPrincipal()],  # Allow all principals
            actions=["execute-api:Invoke"],
            resources=["execute-api:/*/*/*"],
        )
        policy_document = iam.PolicyDocument(statements=[policy_statement])
        api = apigateway.RestApi(
            self, "EC2SchedulerResizeAPI",
            endpoint_types=[apigateway.EndpointType.PRIVATE],
            deploy_options=apigateway.StageOptions(
                data_trace_enabled=True,
                logging_level=apigateway.MethodLoggingLevel.INFO,
                metrics_enabled=True,
                access_log_destination=apigateway.LogGroupLogDestination(log_group),
                access_log_format=apigateway.AccessLogFormat.clf()                 
            ),
            policy=policy_document 
        )
        # Define the Lambda integration
        policy_string_for_apigateway_call_lambda='''
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams",
                "logs:PutLogEvents",
                "logs:GetLogEvents",
                "logs:FilterLogEvents"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "lambda:InvokeFunction"
            ],
            "Resource": [
                "*"
            ]
        }
    ]
}

'''        

        policy_document_for_apigateway_call_lambda=iam.PolicyDocument.from_json(json.loads(policy_string_for_apigateway_call_lambda))
        ec2_apigateway_call_lambda_role = iam.Role(
            self, "EC2ApiGatewayCallLambdaRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            inline_policies={"ec2vs-policy-apigateway-call-lambda":policy_document_for_apigateway_call_lambda}
        )

        lambda_integration = apigateway.LambdaIntegration(
            ec2_scheduler_resize_lambda,
            proxy=False,
            credentials_role=ec2_apigateway_call_lambda_role,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    },
                )
            ],
            request_templates={
                "application/json": """
                {
                    "body": {
                        "datetime": "$input.params('datetime')",
                        "instanceId": "$input.params('instanceId')",
                        "targetInstanceType": "$input.params('targetInstanceType')"
                    }
                }
                """
            },
        )
        # Create the API Gateway resource and method
        api_resource = api.root.add_resource("resize")
        method = api_resource.add_method("GET", 
                                lambda_integration,
                                method_responses=[
                                    apigateway.MethodResponse(
                                        status_code="200",
                                        response_parameters={
                                            "method.response.header.Access-Control-Allow-Origin": True
                                        },
                                    )
                                ],)


        policy_string_for_lambda_vscheckadvisor='''
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ec2policy",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceTypes",
                "ec2:CreateNetworkInterface",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DescribeSubnets",
                "ec2:DeleteNetworkInterface",
                "ec2:AttachNetworkInterface",
                "ec2:DetachNetworkInterface",
                "ec2:AssignPrivateIpAddresses",
                "ec2:UnassignPrivateIpAddresses",
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets",
                "ec2:DescribeSecurityGroups",
                "ec2:CreateSecurityGroup",
                "ec2:DeleteSecurityGroup"
            ],
            "Resource": "*"
        },
        {
            "Sid": "snspolicy",
            "Effect": "Allow",
            "Action": [
                "sns:Publish",
                "sns:PutDataProtectionPolicy",
                "sns:SetTopicAttributes"
            ],
            "Resource": "*"
        },
        {
            "Sid": "cloudwatchpolicy",
            "Effect": "Allow",
            "Action": [
                "cloudwatch:GetMetricData",
                "cloudwatch:GetMetricStatistics",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
'''
        policy_document_for_lambda_vscheckadvisor=iam.PolicyDocument.from_json(json.loads(policy_string_for_lambda_vscheckadvisor))

        ec2vs_check_advisor_lambda_role = iam.Role(
            self, "EC2VSCheckAdvisorLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={"ec2vs-policy-lambda-vscheckadvisor":policy_document_for_lambda_vscheckadvisor}
        )

        #
        # Define the Lambda function EC2VerticalScaleCheck to check whether the EC2 needs vertical scaling
        #
        vertical_scale_check_lambda = lambda_.Function(
            self, "EC2VerticalScaleCheck",
            code=lambda_.Code.from_asset("ec2_vertical_scaling_framework/lambda/ec2-check"),
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="ec2-vertical-scale-check.lambda_handler",
            role=ec2vs_check_advisor_lambda_role,
            timeout=Duration.seconds(60),
            environment={
                "instance_id": instance_id,
                "cpu_threshold_upsize": cpu_threshold_upsize,
                "mem_threshold_upsize": mem_threshold_upsize,
                "cpu_threshold_downsize": cpu_threshold_downsize,
                "mem_threshold_downsize": mem_threshold_downsize,
                "sns_topic_arn": sns_topic_arn,
                "ec2_scheduler_url": f"{api.url}resize"
            }
        )
        # Grant necessary permissions to the Lambda function
        # vertical_scale_check_lambda.add_to_role_policy(
        #     iam.PolicyStatement(
        #         actions=[
        #             "ec2:DescribeInstances",
        #             "ec2:ModifyInstanceAttribute",
        #             "ec2:TerminateInstances",
        #         ],
        #         resources=["*"],
        #     )
        # )
        # vertical_scale_check_lambda.add_to_role_policy(
        #     iam.PolicyStatement(
        #         actions=[
        #             "cloudwatch:GetMetricData",
        #             "cloudwatch:GetMetricStatistics",
        #             "sns:Publish"
        #         ],
        #         resources=["*"],
        #     )
        # )

        #
        # Create a EventBridge Scheduler to run every week to trigger Lambda function EC2VerticalScaleCheck
        # using role ec2_resize_scheduler_role for call lambbda
        #
        ec2_scheduler_weekly = scheduler.CfnSchedule(
            self, "EC2SchedulerWeekly",
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(
                mode="OFF",
            ),
            schedule_expression="cron(0 19 ? * 2 *)",
            schedule_expression_timezone = "Asia/Hong_Kong",
            group_name="default",
            target=scheduler.CfnSchedule.TargetProperty(
                arn=vertical_scale_check_lambda.function_arn,
                role_arn=ec2_resize_scheduler_role.role_arn,
                input="{\"instance_id\":\"" + instance_id + 
                "\",\"cpu_threshold_upsize\":\"" + cpu_threshold_upsize + 
                "\",\"mem_threshold_upsize\":\"" + mem_threshold_upsize + 
                "\",\"cpu_threshold_downsize\":\"" + cpu_threshold_downsize + 
                "\",\"mem_threshold_downsize\":\"" + mem_threshold_downsize + 
                "\",\"sns_topic_arn\":\"" + sns_topic_arn + "\"}",
            ),
        )
        # # Define the payload
        # payload = {
        #     "instance_id": instance_id,
        #     "cpu_threshold_upsize": cpu_threshold_upsize,
        #     "mem_threshold_upsize": mem_threshold_upsize,
        #     "cpu_threshold_downsize": cpu_threshold_downsize,
        #     "mem_threshold_downsize": mem_threshold_downsize,
        #     "sns_topic_arn": sns_topic_arn,
        # }