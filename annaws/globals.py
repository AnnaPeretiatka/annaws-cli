import click, boto3
from botocore.exceptions import ClientError

# global resources
ec2_client = boto3.client("ec2")
ec2_resource = boto3.resource("ec2")
s3_resource = boto3.resource("s3")
s3_client = boto3.client("s3")
route53_client = boto3.client("route53")

region = boto3.session.Session().region_name
ssm_client = boto3.client("ssm", region_name=region)

#get aws username
def aws_username():
    sts = boto3.client("sts")
    identity = sts.get_caller_identity()
    return identity["Arn"].split('/')[-1]

# Build base tags
OWNER = aws_username()
TAGS = [
    {"Key": "CreatedBy", "Value": "annaws-cli"},
    {"Key": "Owner", "Value": OWNER}
]

# find lates ubuntu or amazon-linux
def latest_ami(image_os):
    if image_os == 'amazon-linux':
        os_path = '/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2'
    elif image_os == 'ubuntu':
        os_path = '/aws/service/canonical/ubuntu/server/20.04/stable/current/amd64/hvm/ebs-gp2/ami-id'
    else:
        raise ValueError("Unsupported OS")
    try:
        image = ssm_client.get_parameter(Name=os_path)
        return image['Parameter']['Value']
    except ClientError as e:
        click.echo(f"Error retrieving AMI Id from SSM: {e}")
        raise