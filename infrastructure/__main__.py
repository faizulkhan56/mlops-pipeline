import os
import pulumi
import pulumi_aws as aws
from pulumi import Output

# Use stable suffix instead of timestamp to avoid resource conflicts
unique_suffix = "main"
stack_name = pulumi.get_stack()
region = "ap-southeast-1"

# -------------------------------------------------------------------
# Key Pair
# Public key comes from GitHub Actions secret: SSH_PUBLIC_KEY
# -------------------------------------------------------------------
key = aws.ec2.KeyPair(
    "mlops-key",
    key_name=f"mlops-key-{unique_suffix}",
    public_key=os.environ.get("SSH_PUBLIC_KEY", ""),
    tags={"Project": f"mlops-pipeline-{stack_name}"},
)

# -------------------------------------------------------------------
# VPC
# -------------------------------------------------------------------
vpc = aws.ec2.Vpc(
    "mlops-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
    enable_dns_support=True,
    tags={
        "Name": f"mlops-vpc-{stack_name}",
        "Project": f"mlops-pipeline-{stack_name}",
    },
)

# -------------------------------------------------------------------
# Internet Gateway
# -------------------------------------------------------------------
igw = aws.ec2.InternetGateway(
    "mlops-igw",
    vpc_id=vpc.id,
    tags={
        "Name": f"mlops-igw-{stack_name}",
        "Project": f"mlops-pipeline-{stack_name}",
    },
)

# -------------------------------------------------------------------
# Public Subnet
# -------------------------------------------------------------------
public_subnet = aws.ec2.Subnet(
    "mlops-public-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    availability_zone=f"{region}a",
    map_public_ip_on_launch=True,
    tags={
        "Name": f"mlops-public-subnet-{stack_name}",
        "Project": f"mlops-pipeline-{stack_name}",
    },
)

# -------------------------------------------------------------------
# Route Table
# -------------------------------------------------------------------
route_table = aws.ec2.RouteTable(
    "mlops-route-table",
    vpc_id=vpc.id,
    routes=[
        aws.ec2.RouteTableRouteArgs(
            cidr_block="0.0.0.0/0",
            gateway_id=igw.id,
        )
    ],
    tags={
        "Name": f"mlops-route-table-{stack_name}",
        "Project": f"mlops-pipeline-{stack_name}",
    },
)

# -------------------------------------------------------------------
# Route Table Association
# -------------------------------------------------------------------
route_table_association = aws.ec2.RouteTableAssociation(
    "mlops-rta",
    subnet_id=public_subnet.id,
    route_table_id=route_table.id,
)

# -------------------------------------------------------------------
# Security Group
# -------------------------------------------------------------------
security_group = aws.ec2.SecurityGroup(
    "mlops-sg",
    name=f"mlops-sg-{unique_suffix}",
    vpc_id=vpc.id,
    description="Security group for MLOps services",
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=22,
            to_port=22,
            cidr_blocks=["0.0.0.0/0"],
            description="SSH",
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=8001,
            to_port=8001,
            cidr_blocks=["0.0.0.0/0"],
            description="ML Inference Service",
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=8002,
            to_port=8002,
            cidr_blocks=["0.0.0.0/0"],
            description="Data Ingestion Service",
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=9090,
            to_port=9090,
            cidr_blocks=["0.0.0.0/0"],
            description="Prometheus",
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=3000,
            to_port=3000,
            cidr_blocks=["0.0.0.0/0"],
            description="Grafana",
        ),
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
            description="Allow all outbound traffic",
        )
    ],
    tags={
        "Name": f"mlops-security-group-{stack_name}",
        "Project": f"mlops-pipeline-{stack_name}",
    },
)

# -------------------------------------------------------------------
# EC2 user_data
# Installs Docker, docker-compose, AWS CLI
# -------------------------------------------------------------------
user_data = """#!/bin/bash
set -e

apt-get update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker ubuntu

# Install Docker Compose binary
curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install utilities
apt-get install -y unzip curl jq

# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install
rm -rf aws awscliv2.zip get-docker.sh

# Configure Docker logging
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'DOCKER_EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
DOCKER_EOF

systemctl enable docker
systemctl restart docker

# Wait for Docker
timeout=60
while ! docker info > /dev/null 2>&1 && [ $timeout -gt 0 ]; do
  sleep 2
  timeout=$((timeout-2))
done

echo "Setup complete at $(date)" > /home/ubuntu/setup-info.txt
echo "Instance type: t2.micro" >> /home/ubuntu/setup-info.txt
echo "Docker status: $(systemctl is-active docker)" >> /home/ubuntu/setup-info.txt
chown ubuntu:ubuntu /home/ubuntu/setup-info.txt

apt-get clean
rm -f /var/lib/apt/lists/lock
rm -f /var/lib/dpkg/lock-frontend
rm -f /var/lib/dpkg/lock

echo "User data script completed successfully" >> /home/ubuntu/setup-info.txt
"""

# -------------------------------------------------------------------
# EC2 Instance
# -------------------------------------------------------------------
instance = aws.ec2.Instance(
    "mlops-instance",
    key_name=key.key_name,
    instance_type="t2.micro",
    ami="ami-0df7a207adb9748c7",  # Ubuntu 22.04 LTS in ap-southeast-1
    subnet_id=public_subnet.id,
    vpc_security_group_ids=[security_group.id],
    user_data=user_data,
    root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
        volume_type="gp2",
        volume_size=20,
        delete_on_termination=True,
    ),
    tags={
        "Name": f"mlops-instance-{stack_name}",
        "Project": f"mlops-pipeline-{stack_name}",
    },
)

# -------------------------------------------------------------------
# Elastic IP
# -------------------------------------------------------------------
elastic_ip = aws.ec2.Eip(
    "mlops-eip",
    instance=instance.id,
    domain="vpc",
    tags={
        "Name": f"mlops-eip-{stack_name}",
        "Project": f"mlops-pipeline-{stack_name}",
    },
)

# -------------------------------------------------------------------
# Exports
# -------------------------------------------------------------------
pulumi.export("vpc_id", vpc.id)
pulumi.export("subnet_id", public_subnet.id)
pulumi.export("security_group_id", security_group.id)
pulumi.export("instance_id", instance.id)
pulumi.export("instance_public_ip", elastic_ip.public_ip)
pulumi.export("grafana_url", Output.concat("http://", elastic_ip.public_ip, ":3000"))
pulumi.export("prometheus_url", Output.concat("http://", elastic_ip.public_ip, ":9090"))
pulumi.export("unique_suffix", unique_suffix)