# annaws-cli

AWS CLI tool wrapper for managing **EC2**, **S3**, and **Route53** resources with safe defaults and tagging.

## What the tool does
- Request AWS resources through a single CLI.
- Only allows specific instance types (t3.micro, t2.small).
- Max 2 running EC2 instances.
- Creates S3 buckets - private by default, for public requires explicit confirmation.
- Upload local files to S3 bucket.
- Only resources tagged `CreatedBy=annaws-cli` are listed and managed.
- Route53 hosted zones + DNS records are manageable only if created by this tool.

---

## Prerequisites
1. Python 3.9+
    - Windows - Download: https://www.python.org/downloads/windows/ --> run installer | verify with powershell, run: python --version
    - macOS - Download: brew install python@3.11 | verify: python3 --version
    - Linux (Ubuntu) - Download: sudo apt update --> sudo apt install -y python3 python3-pip | verify: python3 --version
    - Amazon Linux - Download: sudo yum install -y python3 | verify: python3 --version

2. AWS CLI configured with a profile that has permissions for EC2, S3, and Route53.
    - Windows - Download: https://awscli.amazonaws.com/AWSCLIV2.msi --> run installer | verify: aws --version
    - macOS - Download: brew install awscli | verify: aws --version
    - Linux (Ubuntu) - Download, run: curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" 
                                        --> unzip awscliv2.zip --> sudo ./aws/install | verify: aws --version
    - Amazon Linux - Download, run: sudo yum install -y unzip --> curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
                                    --> unzip awscliv2.zip --> sudo ./aws/install | verify: aws --version
!!! MUST run: aws configure to connect to your aws account

3. Installed python packages (will be installed with the requirements):
    - boto3
    - click
---

## Installation
```bash
git clone https://github.com/AnnaPeretiatka/annaws-cli.git
cd annaws-cli
pip install -r requirements.txt
pip install -e .
```
---

## Usage

## ----- EC2 -----
Help: annaws ec2 --help
Recommended to include --key. Otherwise SSH access won't work.
Must insert arg: "instance_type": <t3.micro or t2.small>


### 1. annaws s3 create 
Creates EC2 instances
Help: annaws ec2 create --help
Flags:
 --name: Optional friendly name for the instance
 --amount: Number of instances to create (default 1, max 2 running)
 --image-os: Choose OS: ubuntu (default) or amazon-linux
 --key: Name of the EC2 Key Pair for SSH access. Will generate new key if not exists

Create 1 Ubuntu instance (default), type t3.micro, named "annawsEC2" (default)
```bash
annaws ec2 create t3.micro --key <YourExistingKeyPair or newName>
```

Create 2 Amazon Linux instances with custom names
```bash
annaws ec2 create t2.small --name <chooseEC2name> --amount 2 --image-os amazon-linux --key <YourExistingKeyPair or newName>
```

### 2. annaws s3 list
List EC2 instances created by annaws-cli
Help: annaws ec2 list --help
```bash
annaws ec2 list
```

### 3. annaws s3 Start/Stop 
strt/stop instances created by annaws-cli
Help: annaws ec2 manage --help
```bash
annaws ec2 manage start <instance_id> # i-123..
annaws ec2 manage stop  <instance_id>
```

## ----- S3 -----     
Help: annaws s3 --help

### 1. annaws s3 create
creates private/public buckets
Help: annaws s3 create --help
Flags:
 --name: Base name of the bucket. Full name is <awsusername>-<name>-<6 chars>
 --public: Makes the bucket public (requires confirmation)

Create a private bucket (default)
```bash
annaws s3 create --name mybucket
```
Create a public bucket (will prompt to confirm, if N -> will create private)
```bash
annaws s3 create --name mybucket-public --public
```

### 2. annaws s3 upload_files
Upload files to S3 bucket
Help: annaws s3 upload-files --help
Must insert args: <local file path> and <bucket full name>
##Flags:
 --key: Path in the bucket for uploading files. Defaults to the file’s basename

Upload a file to the main path (filename as key)
```bash
annaws s3 upload-files ./logo.png <FULL-bucket-name>
```
Upload a file to a specific path inside the bucket
```bash
annaws s3 upload-files ./logo.png <FULL-bucket-name> --key bucketpath/logo.png
```

### 3. annaws s3 list --> List S3 buckets created by annaws-cli
Help: annaws s3 list --help
```bash
annaws s3 list
```

## ---- Route53 ----      
Help: annaws route53 --help

### 1. annaws route53 create-zones
Help: annaws route53 create-zones --help
Must insert arg: <domain-name>
##Flags:
 --private: for private hosted zone 
 --vpc-id: ID of the VPC (required for private zones)
 --commant: Optional comment about the hosted zone

Create a PUBLIC hosted zone
```bash
annaws route53 create-zones annaws.com
```
Create a PRIVATE hosted zone (requires VPC ID)
```bash
annaws route53 create-zones annaws.private --private --vpc-id vpc-09549181f6d60927a --commant "private hosted zone by annaws-cli"
```
### 2. annaws route53 list-zones --> List hosted zones created by the CLI
Help: annaws route53 list-zones --help
```bash
annaws route53 list-zones
```
### 3. annaws route53 list-records --> List records for all CLI-created zones
Help: annaws route53 list-records --help
```bash
annaws route53 list-records
```

### 4. annaws route53 manage-records --> Manage DNS records. Supports: 
Help: annaws route53 manage-records --help
#Standard records (Maps a domain to an IPv4/another domain, A, CNAME, MX, TXT..) use --value (can repeat).
#Alias records (Domain point to AWS resource without ip, A → ALB/CloudFront/S3 website) use --alias-dns and --alias-zone

Must insert arg: <action:{create, update, delete}> and <zone-id>
##Flags:
 --name: Record name (FQDN) - required
 --type: Record type - required
 --value: The destination (IP address, another hostname) required for Standard records , can be repeat.
 --ttl: Time-to-live in seconds (default 300)
 --alias-dns & --alias-zone: DNS name and Hosted zone ID, required for alias records
 --evaluate-health: Whether to evaluate target health (only for alias records)

Create a standard A record
```bash
annaws route53 manage-records create <Zone-Id> --name api.annaws.com --type A --value 1.2.3.4 --ttl 400
```
Update (UPSERT) the A record with a different value
```bash
annaws route53 manage-records update <Zone-Id> --name api.annaws.com --type A --value 1.2.3.4 --value 5.6.7.8 --ttl 300
```
Delete the A record
```bash
annaws route53 manage-records delete <Zone-Id> --name api.annaws.com --type A --value 1.2.3.4 --value 5.6.7.8
```
Create Alias records
```bash
annaws route53 manage-records create <Zone-Id> --name app.annaws.com --type A --alias-dns talawstest-1797435910.us-east-1.elb.amazonaws.com --alias-zone Z35SXDOTRQ7X7K --evaluate-health False
```

---

## Tagging Convention
All resource gets those TAGS:
- CreatedBy = annaws-cli
- Owner = <your AWS username>

---

## Cleanup
- Terminate EC2 instances
- Delete S3 buckets.
- Delete hosted zones and DNS records


