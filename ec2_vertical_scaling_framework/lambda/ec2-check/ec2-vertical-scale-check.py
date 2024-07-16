import boto3
import os
from datetime import datetime, timedelta, timezone
from botocore.exceptions import ClientError
'''
{
"instance_id":"${id}",
"cpu_threshold_upsize":"${threshold}",
"mem_threshold_upsize":"${threshold}",
"cpu_threshold_downsize":"${threshold}",
"mem_threshold_downsize":"${threshold}",
"sns_topic_arn":"${sns_topic_arn}"
}
'''
def lambda_handler(event, context):
    cloudwatch = boto3.client('cloudwatch',region_name='ap-east-1')
    #get parameter
    instance_id=event['instance_id']
    cpu_threshold_upsize=float(event['cpu_threshold_upsize'])*100
    mem_threshold_upsize=float(event['mem_threshold_upsize'])*100
    cpu_threshold_downsize=float(event['cpu_threshold_downsize'])*100
    mem_threshold_downsize=float(event['cpu_threshold_downsize'])*100
  
    #check metric and decide upsize or downsize or keep as is
    period = 3600 # 1 hours
    statistic = 'Average'  # e.g., 'Average', 'Sum', 'Minimum', 'Maximum'
    start_time = datetime.now(timezone.utc)- timedelta(days=7)
    end_time = datetime.now(timezone.utc)

    #check cpu
    metric_name = 'CPUUtilization'
    namespace = 'AWS/EC2'
    print(f"begin call cloudwatch for ec2 cpu metric data")
    cpu_down=False
    cpu_up=False
    bypass_times=0
    bypass_times_threshold=7
    try:
      cpu_response = cloudwatch.get_metric_data(
        MetricDataQueries=[
            {
                'Id': "query_cpu",
                'MetricStat': {
                    'Metric': {
                        'Namespace': namespace,
                        'MetricName': metric_name,
                        'Dimensions': [
                        {
                            'Name': 'InstanceId',
                            'Value': instance_id
                        }
                    ]
                    },
                    'Period': period,
                    'Stat': statistic
                },
                'ReturnData': True
            }
        ],
        StartTime=start_time,
        EndTime=end_time
     )
      cpu_metric_data_points = cpu_response['MetricDataResults'][0]['Values']
      print(f"begin call cloudwatch for ec2 cpu metric data ok,no exception")
      print(f"cpu metric data name={metric_name}, value={cpu_metric_data_points}")
      # downsize check
      cpu_down = all(float(value) < cpu_threshold_downsize for value in cpu_metric_data_points)
         #upsize check
      bypass_times=0
      bypass_times_threshold=7
      for  value in cpu_metric_data_points:
        if float(value) > cpu_threshold_upsize :
            bypass_times+=1
      cpu_up=bypass_times>=bypass_times_threshold
    except ClientError as e:
      print(f"An error occurred: {e.response['Error']['Message']}")
    except Exception as e:
      print(f"An unexpected error occurred: {e}")   


    print(f"the result for check cpu_down:{cpu_down} cpu_up:{cpu_up}")
 
    #check mem_down mem_up
    mem_metric_name = 'mem_used_percent'
    mem_namespace = 'CWAgent'
    print(f"begin call cloudwatch for ec2 mem metric data")
    mem_down=False
    mem_up=False
    try:
      mem_response = cloudwatch.get_metric_data(
        MetricDataQueries=[
            {
                'Id': "query_mem",
                'MetricStat': {
                    'Metric': {
                        'Namespace': mem_namespace,
                        'MetricName': mem_metric_name,
                        'Dimensions': [
                        {
                            'Name': 'InstanceId',
                            'Value': instance_id
                        }
                    ]
                    },
                    'Period': period,
                    'Stat': statistic
                },
                'ReturnData': True
            }
        ],
        StartTime=start_time,
        EndTime=end_time
     )
      mem_metric_data_points = mem_response['MetricDataResults'][0]['Values']
      print(f"begin call cloudwatch for ec2 mem metric data ok,no exception")
      print(f"mem metric data name={mem_metric_name}, value={mem_metric_data_points}")
      #downsize check
      mem_down = all(float(value) < mem_threshold_downsize for value in mem_metric_data_points)
      #upsize check
      mem_bypass_times=0
      mem_bypass_times_threshold=7
      for  value in mem_metric_data_points:
        if float(value) > mem_threshold_upsize :
            mem_bypass_times+=1
      mem_up=mem_bypass_times>=mem_bypass_times_threshold
    except ClientError as e:
      print(f"An error occurred: {e.response['Error']['Message']}")
    except Exception as e:
      print(f"An unexpected error occurred: {e}")   

    print(f"the result for call cloudwatch_check mem_down:{mem_down} mem_up:{mem_up}")

    if (cpu_up or mem_up or cpu_down or mem_down):
       print(f"the result for cloudwatch metric,need to find next instanceType")
       ec2 = boto3.resource('ec2')
       instance = ec2.Instance(instance_id)
       intance_type_now = instance.instance_type
       intance_type_next=get_next_instancetype(intance_type_now,cpu_down,mem_down,cpu_up,mem_up)
       print(f"the result for find nextType is {intance_type_next}")  
       
       if intance_type_now != intance_type_next:
          #really click_url todo
          NEXT_STEP_BASE_URL = os.environ['ec2_scheduler_url']
          #get private_IP
          private_ip=instance.private_ip_address
          print(f"intance_type_now:{intance_type_now},private_ip:{private_ip}")
          click_url=NEXT_STEP_BASE_URL+"?instanceId="+instance_id+"&targetInstanceType="+intance_type_next+"&datetime=YYYY-MM-DDThh:mm:00"
          mail_msg=build_mail_message(private_ip,intance_type_now,intance_type_next,cpu_down,mem_down,cpu_up,mem_up,click_url)
          print(mail_msg)

          sns = boto3.resource('sns')
          sns_topic_arn=event['sns_topic_arn']
          sns_topic = sns.Topic(sns_topic_arn)
 
          sns_topic.publish(
            TopicArn=sns_topic_arn,
            Message=mail_msg,
            Subject='Instance adjusting Notification'
          )
       else:
          print(f'instance not need change')
 

# only support c m r faimly,and greater than large
def get_next_instancetype(nowType,cpu_down,mem_down,cpu_up,mem_up):
  dot_index=nowType.index(".")

  instance_type_name=nowType[0:dot_index]
  instance_type_spec=nowType[dot_index+1:len(nowType)]
  # ex,m5
  #print(instance_type_name)
  # ex,xlarge
  #print(instance_type_spec)
  # ex,m
  instance_type_faimly=instance_type_name[0]
  #print(instance_type_faimly)
  large_inex=instance_type_spec.index("large")
  #print(large_inex)
  instance_type_spec_sizestr=instance_type_spec[0:large_inex]
  #ex,x,2x,
  #print(instance_type_spec_sizestr)
 
  #decide faimly and typename
  next_typename=""
  next_type=""
  if cpu_down and mem_down:
  #do same failmy downsize
    next_typename=instance_type_name
    next_type=get_next_downtype_bysize(next_typename,instance_type_spec)
    print(f"next downsize is {next_type}")
  elif cpu_down and not mem_down and not mem_up:
  #do different failmly downsize for cpu
     if instance_type_faimly == "r":
       #todo nothing to or down same
       next_type=nowType
       # r6i.2xlarge -> r6i.xlage,not so good,maybe cause mem not enough,so do nothing
    #    next_typename=instance_type_name
    #    next_type=get_next_downtype_bysize(next_typename,instance_type_spec)
       print(f"keep size is {next_type}")
     elif instance_type_faimly == "m":
       #m->r change faimly on downsize
       next_typename='r'+instance_type_name[1:len(instance_type_name)]
       next_type=get_next_downtype_bysize(next_typename,instance_type_spec)
       print(f"next downsize is {next_type}")
     elif instance_type_faimly == "c":
       #c->m change faimly on downsize
       next_typename='m'+instance_type_name[1:len(instance_type_name)]
       next_type=get_next_downtype_bysize(next_typename,instance_type_spec)
       print(f"next downsize is {next_type}")
     else:
       next_type=nowType
       print(f"the family is not in (c m r) not suport {next_type}")
  elif cpu_down and not mem_down and  mem_up:
     if instance_type_faimly == "r":
       #todo nothing to or down same
       #r6i.2xlarge -> r6i.4xlage,so that satisfy  the mem need
       next_typename=instance_type_name
       next_type=get_next_uptype_bysize(next_typename,instance_type_spec)
       print(f"next upsize is {next_type}")
     elif instance_type_faimly == "m":
       #m->r change faimly only
       #m6i.2xlarge -> r6i.2xlage
       next_typename='r'+instance_type_name[1:len(instance_type_name)]
       next_type=next_typename+"."+instance_type_spec
       print(f"next changefaimly only size is {next_type}")
     elif instance_type_faimly == "c":
       #c->r change faimly and downsize
       next_typename='r'+instance_type_name[1:len(instance_type_name)]
       next_type=get_next_downtype_bysize(next_typename,instance_type_spec)
       print(f"next downsize is {next_type}")
     else:
       next_type=nowType
       print(f"the family is not in (c m r) not suport {next_type}")
  elif mem_down and not cpu_down and not cpu_up:
     if instance_type_faimly == "r":
       #r->m change faimly only
       #r6i.2xlage->m6i.2xlarge 
       next_typename='m'+instance_type_name[1:len(instance_type_name)]
       next_type=next_typename+"."+instance_type_spec
       print(f"next changefaimly only size is {next_type}")
     elif instance_type_faimly == "m":
       #m->c change faimly only
       #m6i.2xlarge -> c6i.2xlage
       next_typename='c'+instance_type_name[1:len(instance_type_name)]
       next_type=next_typename+"."+instance_type_spec
       print(f"next changefaimly only size is {next_type}")
     elif instance_type_faimly == "c":
       #todo nothing to or down same
       #do nothing ,because may be cpu is not enough
       next_type=nowType
       print(f"keep size is {next_type}")
     else:
       next_type=nowType
       print(f"the family is not in (c m r) not suport {next_type}")
  elif mem_down and not cpu_down and cpu_up:
     if instance_type_faimly == "r":
       #r->c change faimly and upszie
       #r6i.2xlage->c6i.4xlarge 
       next_typename='c'+instance_type_name[1:len(instance_type_name)]
       next_type=get_next_uptype_bysize(next_typename,instance_type_spec)
       print(f"next changefaimly  upsize is {next_type}")
     elif instance_type_faimly == "m":
       #m->c change faimly and upsize
       #m6i.2xlarge -> c6i.4xlage
       next_typename='c'+instance_type_name[1:len(instance_type_name)]
       next_type=get_next_uptype_bysize(next_typename,instance_type_spec)
       print(f"next changefaimly upsize is {next_type}")
     elif instance_type_faimly == "c":
       #todo nothing to or up same
       #upsame satify cpu
       next_typename=instance_type_name
       next_type=get_next_uptype_bysize(next_typename,instance_type_spec)
       print(f"next upsize is {next_type}")
     else:
       next_type=nowType
       print(f"the family is not in (c m r) not suport {next_type}")
  elif cpu_up and mem_up:
       next_typename=instance_type_name
       next_type=get_next_uptype_bysize(next_typename,instance_type_spec)
       print(f"next upsize is {next_type}")
  elif cpu_up and not mem_up and not mem_down:
     if instance_type_faimly == "r":
       #r->m change faimly and upszie
       #r6i.2xlage->m6i.4xlarge 
       next_typename='m'+instance_type_name[1:len(instance_type_name)]
       next_type=get_next_uptype_bysize(next_typename,instance_type_spec)
       print(f"next changefaimly  upsize is {next_type}")
     elif instance_type_faimly == "m":
       #m->c change faimly and upsize
       #m6i.2xlarge -> c6i.4xlage
       next_typename='c'+instance_type_name[1:len(instance_type_name)]
       next_type=get_next_uptype_bysize(next_typename,instance_type_spec)
       print(f"next changefaimly upsize is {next_type}")
     elif instance_type_faimly == "c":
       #todo nothing to or up same
       #upsame satify cpu
       next_typename=instance_type_name
       next_type=get_next_uptype_bysize(next_typename,instance_type_spec)
       print(f"next upsize is {next_type}")
     else:
       next_type=nowType
       print(f"the family is not in (c m r) not suport {next_type}")
  elif mem_up and not cpu_up and not cpu_down:
     if instance_type_faimly == "r":
       #todo nothing to or up same
       #upsame satify mem
       next_typename=instance_type_name
       next_type=get_next_uptype_bysize(next_typename,instance_type_spec)
       print(f"next upsize is {next_type}")
     elif instance_type_faimly == "m":
       #m->r change faimly only
       #m6i.2xlage->r6i.2xlarge 
       next_typename='r'+instance_type_name[1:len(instance_type_name)]
       next_type=next_typename+"."+instance_type_spec
       print(f"next changefaimly only size is {next_type}")
     elif instance_type_faimly == "c":
       #c->m change faimly only
       #m6i.2xlage->r6i.2xlarge 
       next_typename='m'+instance_type_name[1:len(instance_type_name)]
       next_type=next_typename+"."+instance_type_spec
       print(f"next changefaimly only size is {next_type}")
     else:
       next_type=nowType
       print(f"the family is not in (c m r) not suport {next_type}")      
  else :
       next_type=nowType
       print(f"nothing need to keepsize{next_type}")
  return next_type

def get_next_downtype_bysize(next_typename,instance_type_spec):
  large_inex=instance_type_spec.index("large")
  #print(large_inex)
  instance_type_spec_sizestr=instance_type_spec[0:large_inex]
  #ex,x,2x,
  #print(instance_type_spec_sizestr)
      # xlarge ->large
  next_type=""
  if large_inex==1:
       next_type = next_typename + "." + "large"
    # 4xlarge ->2xlarge;2x->xlarge
  elif large_inex>1:
       size = instance_type_spec_sizestr[0:instance_type_spec_sizestr.index("x")]
       newsize=int(size)//2
       print(newsize)
       #2x->x
       if newsize ==1: 
        newsize_str ="x"
       #4x->2x
       else:
        newsize_str=str(newsize)+"x"
       next_type = next_typename + "." +newsize_str+"large"
    #large ->large
  else:
      next_type=next_typename+"."+instance_type_spec
      print(f"keep size nochange {next_type}")
  return next_type


def get_next_uptype_bysize(next_typename,instance_type_spec):
  large_inex=instance_type_spec.index("large")
  #print(large_inex)
  instance_type_spec_sizestr=instance_type_spec[0:large_inex]
  #ex,x,2x,
  #print(instance_type_spec_sizestr)
      # xlarge ->large
  next_type=""
  if large_inex==1:
    newsize_str = "2x"
  elif large_inex<1 :
    newsize_str = "x"
  else:
    size = instance_type_spec_sizestr[0:instance_type_spec_sizestr.index("x")]
    #print(size)
    #newsize_str=str(size*2)+"x"
  next_type = next_typename + "." +newsize_str+"large"
  return next_type

#"[triggered/did not trigger] [scale-out/scale-in] "

def build_mail_message(private_ip,instance_nowtype,instance_nexttype,cpu_down,mem_down,cpu_up,mem_up,click_url):
  mail_template='''
Dear cloud ops:
The instance({private_ip}), current intanceType {instance_nowtype}.
During the last monitoring period (one week):

--CPU utilization metric:{cpu_triggerd_ornot} {cpu_scale_outorin} threshold
--Memory utilization metric:{mem_triggerd_ornot} {mem_scale_outorin}  threshold

Based on this, we recommend adjusting now instance type {instance_nowtype} to {instance_nexttype}.

please paste the below url to browser and change the datatime to resize:

{click_url}

'''
  cpu_triggerd_ornot= "triggered" if (cpu_down or cpu_up) else "did not trigger"
  cpu_scale_outorin= "scale-out or scale-in"
  if cpu_up :
     cpu_scale_outorin= "scale-out"
  elif cpu_down:
    cpu_scale_outorin= "scale-in"

  mem_triggerd_ornot= "triggered" if (mem_down or mem_up) else "did not trigger"
  mem_scale_outorin= "scale-out or scale-in"
  if mem_up :
     mem_scale_outorin= "scale-out"
  elif mem_down:
    mem_scale_outorin= "scale-in"
  
  mail_message=mail_template.format(
      private_ip=private_ip,
      instance_nowtype=instance_nowtype,
      cpu_triggerd_ornot=cpu_triggerd_ornot,
      cpu_scale_outorin=cpu_scale_outorin,
      mem_triggerd_ornot=mem_triggerd_ornot,
      mem_scale_outorin=mem_scale_outorin,
      instance_nexttype=instance_nexttype,
      click_url=click_url)
  return mail_message
