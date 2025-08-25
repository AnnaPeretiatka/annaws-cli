import click, uuid, re
from botocore.exceptions import ClientError
from .globals import TAGS, region, route53_client

@click.group()
def route53():
    """Manage Route 53 DNS records"""
    pass

# ------------------------------------------------------------- Helpers ------------------------------------------------------------

def annaws_route53():
    hosted_zones_resp = route53_client.list_hosted_zones()
    all_hosted_zones = hosted_zones_resp.get("HostedZones", [])
    annaws_zones = []
    zone_tags_dict = {}
    for zone in all_hosted_zones:
        zone_id = zone["Id"].split("/")[-1]
        zone_tags = route53_client.list_tags_for_resource(
            ResourceType='hostedzone',
            ResourceId=zone_id
        )["ResourceTagSet"]["Tags"]
        #zone_tags_dict = {t["Key"]: t["Value"] for t in zone_tags} #convert tags list to dict for access
        for tag in zone_tags:
                key = tag["Key"]
                value = tag["Value"]
                zone_tags_dict[key] = value
        if zone_tags_dict.get("CreatedBy") == "annaws-cli":
            annaws_zones.append({
                "Id": zone_id,
                "Name":  zone["Name"],
                #"Private": zone["Config"]["PrivateZone"],
                "Private": zone["Config"].get("PrivateZone", False),
                #"Comment": zone["Config"]["Comment"],
                "Comment": zone["Config"].get("Comment", ""),
                "Records": zone.get("ResourceRecordSetCount", 0)
            })

    if not annaws_zones:
        click.echo("No hosted zones created by annaws-cli found.")
        return
    return annaws_zones

def validate_domain(domain_name):
    pattern = r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z]{2,})+$"
    if not re.match(pattern, domain_name):
        raise click.BadParameter(f"Invalid domain name: {domain_name}")

# ------------------------------------------------------------- annaws route53 create-zones -------------------------------------------------------------

@route53.command()
@click.argument("domain_name")
@click.option("--private", is_flag=True, help="For private hosted zones, requires --vpc-id")
@click.option("--vpc-id", default=None, help="ID of the VPC (required for private zones)")  
@click.option("--commant", default="Created by annaws-cli", help="Optional comment about the hosted zone")
def create_zones(domain_name, private, vpc_id, commant):
    """Create a new Route53 hosted zone"""
###########################################################################make sure validate domain works
    validate_domain(domain_name)
    
    route53_args = {
        "Name": domain_name,
        "CallerReference": uuid.uuid4().hex[:8],
        "HostedZoneConfig":{
            'Comment': commant,
            'PrivateZone': private #bool(private)
        }
    }

    if private:
        if not vpc_id:
            click.echo("Error: must add --vpc-id for private hosted zones")
            return
        route53_args["VPC"] = {
            "VPCId": vpc_id,
            "VPCRegion": region
        }

    try:
        hosted_zone=route53_client.create_hosted_zone(**route53_args)
        zone_id = hosted_zone["HostedZone"]["Id"].split("/")[-1]
        #tag hosted zone
        route53_client.change_tags_for_resource(
            ResourceType='hostedzone',
            ResourceId=zone_id,
            AddTags=TAGS
        )
        click.echo(f"Hosted zone {domain_name} created with ID:{zone_id}")
    except ClientError as e:
        click.echo(f"Error creating hosted zone: {e}")

# ------------------------------------------------------------- annaws route53 manage-records -------------------------------------------------------------

@route53.command()
@click.argument("action", type=click.Choice(['create', 'update', 'delete'], case_sensitive=False))
@click.argument("zone-id")
@click.option("--name", required=True, help="Record name (FQDN)")
@click.option("--type", "record_type", required=True, help="Record type") #cli: "--type" in python "record_type"
@click.option("--value",multiple=True, help="The destination (IP address, another hostname), required for Standard records, can be repeat")
@click.option("--ttl", type=int, default=300, help="Time-to-live in seconds (default 300)")
@click.option("--alias-dns", help="DNS name for alias target")
@click.option("--alias-zone", help="Hosted zone ID for alias target")
@click.option("--evaluate-health", type=bool, default=False, help="Whether to evaluate target health (only for alias records)")
def manage_records(action, zone_id, name, record_type, value, ttl, alias_dns, alias_zone, evaluate_health):
    """Manage DNS records inside annaws-cli created hosted zones."""
    if not value and not alias_dns:
        click.echo("--value is required for standard records")
        return

    #Check if zone created by annaws-cli
    annaws_zones = annaws_route53()
    zone_ids = []
    for z in annaws_zones:
        zone_ids.append(z["Id"])
    if zone_id not in zone_ids:
        click.echo("The hosted zone wasn't created by annaws-cli")
        return
    
    action_dict = {"create": "CREATE", "update":"UPSERT", "delete":"DELETE"} #UPSERT like update but also overwrite if exists
    wanted_action = action_dict[action]

    # standard vs alias record
    record_set = {
        "Name": name,
        "Type": record_type
    }
    if alias_dns and alias_zone: # for alias record (A --> ALB, CloudFront)
        record_set["AliasTarget"] = {
            "HostedZoneId": alias_zone,
            "DNSName": alias_dns,
            "EvaluateTargetHealth": evaluate_health
    }
    else:   # for standard record (A, CNAME, MX, etc.) 
        record_set["TTL"] = ttl
        record_set["ResourceRecords"] = [{"Value": val} for val in value]

    # making the change
    try:
        manage_record = route53_client.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch = {
                "Comment": f"Managed by annaws-cli ({action})",
                "Changes": [
                    {
                        "Action": wanted_action,
                        "ResourceRecordSet": record_set
                    }
                ]
            }  
        )
        change_info = manage_record["ChangeInfo"]
        click.echo(f"The {action} was submitted, it's on {change_info['Status']}. Changeinfo ID:{change_info['Id']} ")
    except ClientError as e:
        click.echo(f"Error {action} the record: {e}")

# ------------------------------------------------------------- annaws route53 list-zones -------------------------------------------------------------

@route53.command(name="list-zones")
def list_hosted_zones():
    """List all hosted zones created by annaws-cli"""
    annaws_zones = annaws_route53()
    if not annaws_zones:
        click.echo("No hosted zones created by annaws-cli found")
        return
    for zone in annaws_zones:
        click.echo(f"  Zone-Id: {zone['Id']}, Zone-Name: {zone['Name']}, Is Privet: {zone['Private']}, Records: {zone['Records']}, Comment: {zone['Comment']}")

# ------------------------------------------------------------- annaws route53 list-record -------------------------------------------------------------

@route53.command(name="list-records")
def list_resource_record_sets():
    """List all DNS records in hosted zones created by annaws-cli"""
    annaws_zones = annaws_route53()
    if not annaws_zones:
        click.echo("No hosted zones created by annaws-cli found")
        return
    for zone in annaws_zones:
        resource_records = route53_client.list_resource_record_sets(HostedZoneId=zone["Id"])
        for record in resource_records["ResourceRecordSets"]:
            record_name = record["Name"]
            record_type = record["Type"]
            values = []
            if "ResourceRecords" in record:
                for val in record["ResourceRecords"]:
                    values.append(val["Value"])
            elif "AliasTarget" in record:
                values = [record["AliasTarget"]["DNSName"]]
            click.echo(f"  Zone-Name: {record_name}, Type: ({record_type}), Values: {values}")

