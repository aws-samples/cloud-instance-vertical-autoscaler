import json
import boto3
import os
from datetime import datetime

# Create AWS clients
#events_client = boto3.client('events')
scheduler_client = boto3.client('scheduler')
lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    # Parse input parameters
    # input_params = json.loads(event['body'])
    input_params = event['body']
    print(event)
    print(context)
    if isinstance(event['body'], str):
        input_params = json.loads(event['body'])
    print("input_params")
    print(input_params)
    target_datetime = datetime.fromisoformat(input_params['datetime'])
    #lambda_arn = "arn:aws:lambda:ap-east-1:383386985941:function:ResizeEC2" 
    lambda_arn = os.environ['ec2_resize_lambda_ARN']
    sns_topic_arn = os.environ['sns_topic_arn']
    scheduler_role_arn = os.environ['scheduler_role_arn']
    resize_time_zone = os.environ['resize_time_zone']
    
    
    # payload = {
    #     "snsTopicARN": "arn:aws:sns:ap-east-1:383386985941:ec2_vscalling_inform",
    #     "instanceId": "i-0a12135a00ace182c",
    #     "targetInstanceType": "m5.xlarge"
    # }
    payload = {}
    payload["instanceId"] = input_params['instanceId']
    payload["targetInstanceType"] = input_params['targetInstanceType']
    payload["snsTopicARN"] = sns_topic_arn
    payload_json = json.dumps(payload)

    # Create a CloudWatch Events rule
    rule_name = f"TriggerLambdaAt{target_datetime.strftime('%Y%m%d%H%M%S')}"
    
    schedule_response = scheduler_client.create_schedule(
        Name=rule_name,
        FlexibleTimeWindow={
            'Mode': 'OFF'
        },
        ScheduleExpression=f"cron({target_datetime.minute} {target_datetime.hour} {target_datetime.day} {target_datetime.month} ? {target_datetime.year})",
        ScheduleExpressionTimezone=resize_time_zone,
        State='ENABLED',
        Description=f"Trigger Lambda {lambda_arn} at {target_datetime}",
        Target={
            'Arn': lambda_arn,
            'Input': payload_json,
            'RoleArn': scheduler_role_arn
            }
    )

    return {
        'statusCode': 200,
        'body': json.dumps(f"Scheduled Lambda {lambda_arn} to run at {target_datetime}")
    }
