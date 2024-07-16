import boto3


def call_ssm_automation(instance_id, instance_type):
    ssm_client = boto3.client('ssm')

    # Define the parameters for the Automation execution
    document_name = 'AWS-ResizeInstance'

    # Define the parameters for the Automation execution
    parameters = {
        'InstanceId': [instance_id],
        'InstanceType': [instance_type]
    }

    # Start the Automation execution
    response = ssm_client.start_automation_execution(
        DocumentName=document_name,
        Parameters=parameters
    )

    # Return the Automation execution details
    return {
        'automationExecutionId': response['AutomationExecutionId']
    }
    

# payload = {
#     "snsTopicARN": "arn:aws:sns:ap-east-1:383386985941:ec2_vscalling_inform",
#     "instanceId": "i-0a12135a00ace182c",
#     "targetInstanceType": "m5.xlarge"
# }
def lambda_handler(event, context):
    payload = event
    if isinstance(event, str):
        payload = json.loads(event)
        
    instance_id = payload['instanceId']
    instance_type = payload['targetInstanceType']
    snsTopicARN = payload['snsTopicARN']
    
    subject = "Will start to resize " + instance_id + " to " + instance_type
    sns_client = boto3.client('sns')
    response = sns_client.publish(
        TopicArn=snsTopicARN,
        Message=subject,
        Subject=subject
    )

    print("resizing ec2")
    response = call_ssm_automation(instance_id, instance_type)

    subject = "Finished resizing " + instance_id + " to " + instance_type
    response = sns_client.publish(
        TopicArn=snsTopicARN,
        Message=subject,
        Subject=subject
    )

    return response

