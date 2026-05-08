data "aws_subnet" "selected" {
  id = var.subnet_id
}

data "aws_ami" "ubuntu" {
  count = var.ami_id == null ? 1 : 0

  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
}

locals {
  ami_id = var.ami_id != null ? var.ami_id : data.aws_ami.ubuntu[0].id
  vpc_id = coalesce(var.vpc_id, data.aws_subnet.selected.vpc_id)

  cloud_config = <<-YAML
#cloud-config
write_files:
  - path: /usr/local/sbin/ec2-bootstrap-tools.sh
    permissions: '0755'
    encoding: b64
    content: '${base64encode(file("${path.module}/bootstrap-tools.sh"))}'
runcmd:
  - [ /bin/bash, /usr/local/sbin/ec2-bootstrap-tools.sh ]
YAML
}

resource "aws_instance" "this" {
  ami                         = local.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = var.security_group_ids
  iam_instance_profile        = var.iam_instance_profile_name
  associate_public_ip_address = var.associate_public_ip_address
  user_data                   = local.cloud_config
  user_data_replace_on_change = true

  root_block_device {
    volume_size = var.root_volume_size
    volume_type = "gp3"
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tags = merge(
    {
      Name = var.instance_name
    },
    var.additional_tags,
  )
}
