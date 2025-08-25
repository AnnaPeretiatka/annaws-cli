import click, os
from botocore.exceptions import ClientError
from .globals import ec2_resource, ec2_client, TAGS, latest_ami

#makes subgroups under cli (the root command) {annaws ec2 / annaws s3}
@click.group()
def ec2(): 
    """Manage EC2 instances"""
    pass

# ------------------------------------------------------------- Helpers -------------------------------------------------------------

#retrives all annaws-cli created EC2 + option to extend with extra_filters
def annaws_instances(extra_filters=None):
    filters = [{'Name': 'tag:CreatedBy', 'Values': ['annaws-cli']}]
    if extra_filters:
        filters.extend(extra_filters)
    return list(ec2_resource.instances.filter(Filters=filters)) #convert collection to python list

# return ID's in format i-123.. or () if none
def format_instance_ids(instances):
    ids = [i.id for i in instances]
    return f"({', '.join(ids)})" if ids else "()"

# Ensures --key exsists in AWS account, else it will create it and save locally
def ensure_key_pair(key_name):
    try:
        ec2_client.describe_key_pairs(KeyNames=[key_name])
        click.echo(f"Using existing key pair: {key_name}")
        return key_name
    except ClientError as e:
        if e.response["Error"]["Code"] in ("InvalidKeyPair.NotFound", "InvalidKeyPair.Duplicate"): pass

    # Create new key pair
    click.echo(f"Key pair '{key_name}' not found. Creating it now..")
    response = ec2_client.create_key_pair(KeyName=key_name)
    private_key_material = response["KeyMaterial"]

    pem_path = os.path.abspath(f"{key_name}.pem")

    with open(pem_path, "w", encoding="utf-8") as f:
        f.write(private_key_material)

    try: # prevent the crush on windows
        os.chmod(pem_path, 0o400)
    except Exception:
        pass

    click.echo(f"Generated new key pair: {key_name}")
    click.echo(f"Private key saved to: {pem_path}")
    return key_name

# ------------------------------------------------------------- annaws ec2 create -------------------------------------------------------------

@ec2.command()
@click.argument("instance_type", type=click.Choice(['t3.micro', 't2.small'], case_sensitive=False)) #case_sensetive allows capslock writting
@click.option("--name", default="annawsEC2", help="Name tag for the instance/s")
@click.option("--amount", type=int, default=1, help="Number of instances to create")
@click.option("--image-os", type=click.Choice(['ubuntu', 'amazon-linux'], case_sensitive=False), default='ubuntu', help="Operating system for the instance")
@click.option("--key", default=None, help="EC2 Key Pair name for SSH access  (will be created if missing)")
def create(instance_type, name, amount, image_os, key):
    """Create EC2 instances (annaws ec2 create) """
    # user can't insert 0 or less instances to create
    if amount <= 0: 
        click.echo("amount must be at least 1")
        return

    # Deny creation when (running + asked amount) > 2
    annaws_running_instances = annaws_instances([{'Name': 'instance-state-name', 'Values': ['running']}])
    if len(annaws_running_instances) + amount > 2:
        ids_str = format_instance_ids(annaws_running_instances)
        click.echo(f"You already have {len(annaws_running_instances)} running instances {ids_str} "
                    f"Stop one before creating new ones:\n"
                    f"   use: annaws ec2 manage stop <instance_id>")
        return

    all_tags = TAGS + [{"Key": "Name", "Value": name}]

    click.echo(f"Creating {amount} instance/s of type {instance_type} with OS {image_os}")
    click.echo(f"Tags: {all_tags}")

    # Key pair handling
    key_to_use = None
    if key:
        key_to_use = ensure_key_pair(key)
    else:
        click.echo("WARNING: No --key provided. SSH access will not work for these instances.")

    ec2_args = {
        "ImageId": latest_ami(image_os),
        "MinCount": amount,
        "MaxCount": amount, 
        "InstanceType": instance_type,
        "TagSpecifications": [
            {
                "ResourceType": "instance",
                "Tags": all_tags
            }
        ]
    }  
    if key_to_use:
        ec2_args["KeyName"] = key_to_use
    
    #create instance command
    instances = ec2_resource.create_instances(**ec2_args)
    for i in instances:
        i.wait_until_running()
        i.reload()

    # print what was created
    click.echo(f"Instances created:")
    for i in instances:
        click.echo(f"ID: {i.id}, Public IPv4: {i.public_ip_address}, Name: {name}")
    
# ------------------------------------------------------------- annaws ec2 manage -------------------------------------------------------------

@ec2.command()
@click.argument('action', type=click.Choice(['start', 'stop']))
@click.argument('instance_id')
def manage(action, instance_id):
    """Start/Stop an EC2 instance (annaws ec2 manage) """
    existing_ids = [i.id for i in annaws_instances()]
    if instance_id not in existing_ids:
        click.echo(f"Instance {instance_id} was not created by annaws-cli")
        return
    
    current_instance = ec2_resource.Instance(instance_id)
    if action == "start":
        annaws_running_instances = annaws_instances([{'Name': 'instance-state-name', 'Values': ['running']}])
        if len(annaws_running_instances) == 2:
            click.echo(f"You can only have 2 running instances. Currently running: {len(annaws_running_instances)}")
            return
        current_instance.start()
        click.echo(f"Starting instance {instance_id}, please wait")
        current_instance.wait_until_running()
        click.echo(f"Instance {instance_id} is now running")
    elif action == 'stop':
        current_instance.stop()
        click.echo(f"Stopping instance {instance_id}, please wait")
        current_instance.wait_until_stopped()
        click.echo(f"Instance {instance_id} has stopped")

# ------------------------------------------------------------- annaws ec2 list -------------------------------------------------------------
@ec2.command(name="list")
def list_ec2():
    """List EC2 instances created by annaws-cli """

    instances = annaws_instances()
    if not instances:
        click.echo("No instance was created by annaws")
        return
    
    # mapping: AMI → OS
    ami_to_os = {
        latest_ami("ubuntu"): "Ubuntu",
        latest_ami("amazon-linux"): "Amazon Linux"
    }
    
    for i in instances:
        for tag in i.tags:
            if tag["Key"] == "Name":
                click.echo(f"Instance Name: {tag['Value']}")
        os_name = ami_to_os.get(i.image_id, i.image_id)        
        click.echo(
            f"  Id: {i.id}, " 
            f"State: {i.state['Name']}, "
            f"Type: {i.instance_type}, "
            f"public IP: {i.public_ip_address}, "
            f"OS: {os_name} "
        )

