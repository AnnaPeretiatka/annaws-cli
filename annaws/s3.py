import click, uuid, json, os
from .globals import s3_client, s3_resource, OWNER, region, TAGS
from botocore.exceptions import ClientError

def s3_name_fix(base_name):
    fixed_name = base_name.lower().replace("_","-")
    return f"{OWNER}-{fixed_name}-{uuid.uuid4().hex[:6]}"

def anna_s3_buckets():
    all_buckets = s3_resource.buckets.all()
    annaws_buckets = []
    
    for bucket in all_buckets:
        bucket_tags_dict = {}
        try: #skipps buckets without tags
            bucket_tags = s3_client.get_bucket_tagging(Bucket=bucket.name) # get the bucket tags
            for tag in bucket_tags["TagSet"]: 
                bucket_tags_dict[tag["Key"]] = tag["Value"] #convert bucket tags list to dict for access
            if bucket_tags_dict.get("CreatedBy") == "annaws-cli":
                annaws_buckets.append(bucket)
        except ClientError:
            continue
    return annaws_buckets

@click.group()
def s3():
    """Manage S3 buckets"""
    pass

# ------------------------------------------------------------- annaws s3 create -------------------------------------------------------------

@s3.command()
@click.option("--name", default="annawS3", help="Name for the bucket(part of it)")
@click.option("--public", is_flag=True, help="Make the bucket public")
def create(name, public):
    """Create an S3 bucket (private by default)"""
    bucket_name = s3_name_fix(name)
    
    s3_args = {"Bucket": bucket_name}     
    
    # for creating s3 bucket outide us-east-1 AZ
    if region != "us-east-1":
        s3_args["CreateBucketConfiguration"]={"LocationConstraint": region}

    # create bucket
    s3_resource.create_bucket(**s3_args)

    # apply tags 
    s3_client.put_bucket_tagging(
        Bucket = bucket_name,
        Tagging={"TagSet": TAGS}
    )

    if public:
        if click.confirm("Are you sur you want to make this bucket PUBLIC?"):
            # Disable Block Public Access (bucket level)
            try:
                s3_client.put_public_access_block(
                    Bucket=bucket_name,
                    PublicAccessBlockConfiguration={
                        "BlockPublicAcls": False,
                        "IgnorePublicAcls": False,
                        "BlockPublicPolicy": False,
                        "RestrictPublicBuckets": False
                    }
                )
            except ClientError as e:
                click.echo(f"Warning: couldn't adjust PublicAccessBlock: {e}")
            
            # create policy for puclic access to bucket
            bucket_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"], #allows read/download
                    "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                }]
            }

            # applay policy for public
            try: 
                s3_client.put_bucket_policy(
                    Bucket = bucket_name,
                    Policy=json.dumps(bucket_policy)
                )
            except ClientError as e:
                click.echo(f"Unable to apply bucket policy: {e}")
            
            # applay ACL (public-read) --> if policy won't work and ACL not disabled by default (BucketOwnerEnforced)
            try:
                s3_resource.Bucket(bucket_name).Acl().put(ACL="public-read")
            except ClientError as e:
                click.echo(f"Unable to apply ACL: {e}")

            click.echo(f"Public bucket {bucket_name} was created")
        else: # not confirm public
            click.echo(f"Private bucket {bucket_name} was created instead")
    else: # not public
        click.echo(f"Private bucket {bucket_name} was created")

# ------------------------------------------------------------- annaws s3 upload_files -------------------------------------------------------------
            
@s3.command()
@click.argument("files") # local file path
@click.argument("bucket")
@click.option("--key", default=None, help="path inside bucket(defaults to filename)") #remote path in the s3 bucket
def upload_files(files, bucket, key):
    """Upload files to annaws-cli created bucket"""
    # check if bucket exists and was created by annaws
    annaws_buckets = []
    for b in anna_s3_buckets():
        annaws_buckets.append(b.name)
    if bucket not in annaws_buckets:
        click.echo(f"Bucket {bucket} was not created by annaws-cli")
        return

    # key gets file_names base-name if wasn't given
    if key is None:
        key = os.path.basename(files)

    # upload the file
    s3_client.upload_file(
        Filename = files,
        Bucket = bucket,
        Key = key,
        ExtraArgs={"ServerSideEncryption": "AES256"} # files encrypted in the bucket
    )
    click.echo(f"{files} was uploaded to {bucket}/{key}")    

# ------------------------------------------------------------- annaws s3 list -------------------------------------------------------------

@s3.command(name="list")
def list_s3():
    """List all annaws-cli created buckets"""
    annaws_buckets = anna_s3_buckets()
    if not annaws_buckets:
        click.echo("No annaws-cli buckets found")
        return
    #click.echo(annaws_buckets)
    for b in annaws_buckets:
        click.echo(b.name)