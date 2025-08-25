import click
from .ec2 import ec2
from .s3 import s3
from .route53 import route53

@click.group()
def cli():
    """annaws - AWS CLI tool for creating, manageing and listine EC2, S3 Buckets and Route53"""

cli.add_command(ec2)
cli.add_command(s3)
cli.add_command(route53)

if __name__ == "__main__":
    cli()