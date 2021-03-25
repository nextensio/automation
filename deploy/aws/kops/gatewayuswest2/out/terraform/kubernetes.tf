locals {
  cluster_name                      = "gatewayuswest2.kops.nextensio.net"
  master_autoscaling_group_ids      = [aws_autoscaling_group.master-us-west-2a-masters-gatewayuswest2-kops-nextensio-net.id]
  master_security_group_ids         = [aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id]
  masters_role_arn                  = aws_iam_role.masters-gatewayuswest2-kops-nextensio-net.arn
  masters_role_name                 = aws_iam_role.masters-gatewayuswest2-kops-nextensio-net.name
  node_autoscaling_group_ids        = [aws_autoscaling_group.nodes-us-west-2a-gatewayuswest2-kops-nextensio-net.id]
  node_security_group_ids           = [aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id]
  node_subnet_ids                   = [aws_subnet.us-west-2a-gatewayuswest2-kops-nextensio-net.id]
  nodes_role_arn                    = aws_iam_role.nodes-gatewayuswest2-kops-nextensio-net.arn
  nodes_role_name                   = aws_iam_role.nodes-gatewayuswest2-kops-nextensio-net.name
  region                            = "us-west-2"
  route_table_private-us-west-2a_id = aws_route_table.private-us-west-2a-gatewayuswest2-kops-nextensio-net.id
  route_table_public_id             = aws_route_table.gatewayuswest2-kops-nextensio-net.id
  subnet_us-west-2a_id              = aws_subnet.us-west-2a-gatewayuswest2-kops-nextensio-net.id
  subnet_utility-us-west-2a_id      = aws_subnet.utility-us-west-2a-gatewayuswest2-kops-nextensio-net.id
  vpc_cidr_block                    = aws_vpc.gatewayuswest2-kops-nextensio-net.cidr_block
  vpc_id                            = aws_vpc.gatewayuswest2-kops-nextensio-net.id
}

output "cluster_name" {
  value = "gatewayuswest2.kops.nextensio.net"
}

output "master_autoscaling_group_ids" {
  value = [aws_autoscaling_group.master-us-west-2a-masters-gatewayuswest2-kops-nextensio-net.id]
}

output "master_security_group_ids" {
  value = [aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id]
}

output "masters_role_arn" {
  value = aws_iam_role.masters-gatewayuswest2-kops-nextensio-net.arn
}

output "masters_role_name" {
  value = aws_iam_role.masters-gatewayuswest2-kops-nextensio-net.name
}

output "node_autoscaling_group_ids" {
  value = [aws_autoscaling_group.nodes-us-west-2a-gatewayuswest2-kops-nextensio-net.id]
}

output "node_security_group_ids" {
  value = [aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id]
}

output "node_subnet_ids" {
  value = [aws_subnet.us-west-2a-gatewayuswest2-kops-nextensio-net.id]
}

output "nodes_role_arn" {
  value = aws_iam_role.nodes-gatewayuswest2-kops-nextensio-net.arn
}

output "nodes_role_name" {
  value = aws_iam_role.nodes-gatewayuswest2-kops-nextensio-net.name
}

output "region" {
  value = "us-west-2"
}

output "route_table_private-us-west-2a_id" {
  value = aws_route_table.private-us-west-2a-gatewayuswest2-kops-nextensio-net.id
}

output "route_table_public_id" {
  value = aws_route_table.gatewayuswest2-kops-nextensio-net.id
}

output "subnet_us-west-2a_id" {
  value = aws_subnet.us-west-2a-gatewayuswest2-kops-nextensio-net.id
}

output "subnet_utility-us-west-2a_id" {
  value = aws_subnet.utility-us-west-2a-gatewayuswest2-kops-nextensio-net.id
}

output "vpc_cidr_block" {
  value = aws_vpc.gatewayuswest2-kops-nextensio-net.cidr_block
}

output "vpc_id" {
  value = aws_vpc.gatewayuswest2-kops-nextensio-net.id
}

provider "aws" {
  region = "us-west-2"
}

resource "aws_autoscaling_group" "master-us-west-2a-masters-gatewayuswest2-kops-nextensio-net" {
  enabled_metrics = ["GroupDesiredCapacity", "GroupInServiceInstances", "GroupMaxSize", "GroupMinSize", "GroupPendingInstances", "GroupStandbyInstances", "GroupTerminatingInstances", "GroupTotalInstances"]
  launch_template {
    id      = aws_launch_template.master-us-west-2a-masters-gatewayuswest2-kops-nextensio-net.id
    version = aws_launch_template.master-us-west-2a-masters-gatewayuswest2-kops-nextensio-net.latest_version
  }
  load_balancers      = [aws_elb.api-gatewayuswest2-kops-nextensio-net.id]
  max_size            = 1
  metrics_granularity = "1Minute"
  min_size            = 1
  name                = "master-us-west-2a.masters.gatewayuswest2.kops.nextensio.net"
  tag {
    key                 = "KubernetesCluster"
    propagate_at_launch = true
    value               = "gatewayuswest2.kops.nextensio.net"
  }
  tag {
    key                 = "Name"
    propagate_at_launch = true
    value               = "master-us-west-2a.masters.gatewayuswest2.kops.nextensio.net"
  }
  tag {
    key                 = "k8s.io/cluster-autoscaler/node-template/label/kops.k8s.io/instancegroup"
    propagate_at_launch = true
    value               = "master-us-west-2a"
  }
  tag {
    key                 = "k8s.io/cluster-autoscaler/node-template/label/kubernetes.io/role"
    propagate_at_launch = true
    value               = "master"
  }
  tag {
    key                 = "k8s.io/cluster-autoscaler/node-template/label/node-role.kubernetes.io/master"
    propagate_at_launch = true
    value               = ""
  }
  tag {
    key                 = "k8s.io/role/master"
    propagate_at_launch = true
    value               = "1"
  }
  tag {
    key                 = "kops.k8s.io/instancegroup"
    propagate_at_launch = true
    value               = "master-us-west-2a"
  }
  tag {
    key                 = "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net"
    propagate_at_launch = true
    value               = "owned"
  }
  vpc_zone_identifier = [aws_subnet.us-west-2a-gatewayuswest2-kops-nextensio-net.id]
}

resource "aws_autoscaling_group" "nodes-us-west-2a-gatewayuswest2-kops-nextensio-net" {
  enabled_metrics = ["GroupDesiredCapacity", "GroupInServiceInstances", "GroupMaxSize", "GroupMinSize", "GroupPendingInstances", "GroupStandbyInstances", "GroupTerminatingInstances", "GroupTotalInstances"]
  launch_template {
    id      = aws_launch_template.nodes-us-west-2a-gatewayuswest2-kops-nextensio-net.id
    version = aws_launch_template.nodes-us-west-2a-gatewayuswest2-kops-nextensio-net.latest_version
  }
  max_size            = 1
  metrics_granularity = "1Minute"
  min_size            = 1
  name                = "nodes-us-west-2a.gatewayuswest2.kops.nextensio.net"
  tag {
    key                 = "KubernetesCluster"
    propagate_at_launch = true
    value               = "gatewayuswest2.kops.nextensio.net"
  }
  tag {
    key                 = "Name"
    propagate_at_launch = true
    value               = "nodes-us-west-2a.gatewayuswest2.kops.nextensio.net"
  }
  tag {
    key                 = "k8s.io/cluster-autoscaler/node-template/label/kops.k8s.io/instancegroup"
    propagate_at_launch = true
    value               = "nodes-us-west-2a"
  }
  tag {
    key                 = "k8s.io/cluster-autoscaler/node-template/label/kubernetes.io/role"
    propagate_at_launch = true
    value               = "node"
  }
  tag {
    key                 = "k8s.io/cluster-autoscaler/node-template/label/node-role.kubernetes.io/node"
    propagate_at_launch = true
    value               = ""
  }
  tag {
    key                 = "k8s.io/role/node"
    propagate_at_launch = true
    value               = "1"
  }
  tag {
    key                 = "kops.k8s.io/instancegroup"
    propagate_at_launch = true
    value               = "nodes-us-west-2a"
  }
  tag {
    key                 = "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net"
    propagate_at_launch = true
    value               = "owned"
  }
  vpc_zone_identifier = [aws_subnet.us-west-2a-gatewayuswest2-kops-nextensio-net.id]
}

resource "aws_ebs_volume" "a-etcd-events-gatewayuswest2-kops-nextensio-net" {
  availability_zone = "us-west-2a"
  encrypted         = false
  size              = 20
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "a.etcd-events.gatewayuswest2.kops.nextensio.net"
    "k8s.io/etcd/events"                                      = "a/a"
    "k8s.io/role/master"                                      = "1"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
  }
  type = "gp2"
}

resource "aws_ebs_volume" "a-etcd-main-gatewayuswest2-kops-nextensio-net" {
  availability_zone = "us-west-2a"
  encrypted         = false
  size              = 20
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "a.etcd-main.gatewayuswest2.kops.nextensio.net"
    "k8s.io/etcd/main"                                        = "a/a"
    "k8s.io/role/master"                                      = "1"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
  }
  type = "gp2"
}

resource "aws_elb" "api-gatewayuswest2-kops-nextensio-net" {
  cross_zone_load_balancing = false
  health_check {
    healthy_threshold   = 2
    interval            = 10
    target              = "SSL:443"
    timeout             = 5
    unhealthy_threshold = 2
  }
  idle_timeout = 300
  listener {
    instance_port     = 443
    instance_protocol = "TCP"
    lb_port           = 443
    lb_protocol       = "TCP"
  }
  name            = "api-gatewayuswest2-kops-n-n1mct0"
  security_groups = [aws_security_group.api-elb-gatewayuswest2-kops-nextensio-net.id]
  subnets         = [aws_subnet.utility-us-west-2a-gatewayuswest2-kops-nextensio-net.id]
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "api.gatewayuswest2.kops.nextensio.net"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
  }
}

resource "aws_iam_instance_profile" "masters-gatewayuswest2-kops-nextensio-net" {
  name = "masters.gatewayuswest2.kops.nextensio.net"
  role = aws_iam_role.masters-gatewayuswest2-kops-nextensio-net.name
}

resource "aws_iam_instance_profile" "nodes-gatewayuswest2-kops-nextensio-net" {
  name = "nodes.gatewayuswest2.kops.nextensio.net"
  role = aws_iam_role.nodes-gatewayuswest2-kops-nextensio-net.name
}

resource "aws_iam_role_policy" "masters-gatewayuswest2-kops-nextensio-net" {
  name   = "masters.gatewayuswest2.kops.nextensio.net"
  policy = file("${path.module}/data/aws_iam_role_policy_masters.gatewayuswest2.kops.nextensio.net_policy")
  role   = aws_iam_role.masters-gatewayuswest2-kops-nextensio-net.name
}

resource "aws_iam_role_policy" "nodes-gatewayuswest2-kops-nextensio-net" {
  name   = "nodes.gatewayuswest2.kops.nextensio.net"
  policy = file("${path.module}/data/aws_iam_role_policy_nodes.gatewayuswest2.kops.nextensio.net_policy")
  role   = aws_iam_role.nodes-gatewayuswest2-kops-nextensio-net.name
}

resource "aws_iam_role" "masters-gatewayuswest2-kops-nextensio-net" {
  assume_role_policy = file("${path.module}/data/aws_iam_role_masters.gatewayuswest2.kops.nextensio.net_policy")
  name               = "masters.gatewayuswest2.kops.nextensio.net"
}

resource "aws_iam_role" "nodes-gatewayuswest2-kops-nextensio-net" {
  assume_role_policy = file("${path.module}/data/aws_iam_role_nodes.gatewayuswest2.kops.nextensio.net_policy")
  name               = "nodes.gatewayuswest2.kops.nextensio.net"
}

resource "aws_internet_gateway" "gatewayuswest2-kops-nextensio-net" {
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "gatewayuswest2.kops.nextensio.net"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
  }
  vpc_id = aws_vpc.gatewayuswest2-kops-nextensio-net.id
}

resource "aws_key_pair" "kubernetes-gatewayuswest2-kops-nextensio-net-89c2adaeb1ffbceba1bdb3048c938380" {
  key_name   = "kubernetes.gatewayuswest2.kops.nextensio.net-89:c2:ad:ae:b1:ff:bc:eb:a1:bd:b3:04:8c:93:83:80"
  public_key = file("${path.module}/data/aws_key_pair_kubernetes.gatewayuswest2.kops.nextensio.net-89c2adaeb1ffbceba1bdb3048c938380_public_key")
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "gatewayuswest2.kops.nextensio.net"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
  }
}

resource "aws_launch_template" "master-us-west-2a-masters-gatewayuswest2-kops-nextensio-net" {
  block_device_mappings {
    device_name = "/dev/sda1"
    ebs {
      delete_on_termination = true
      encrypted             = false
      volume_size           = 64
      volume_type           = "gp2"
    }
  }
  iam_instance_profile {
    name = aws_iam_instance_profile.masters-gatewayuswest2-kops-nextensio-net.id
  }
  image_id      = "ami-07e573cdaa16d4e61"
  instance_type = "t2.small"
  key_name      = aws_key_pair.kubernetes-gatewayuswest2-kops-nextensio-net-89c2adaeb1ffbceba1bdb3048c938380.id
  lifecycle {
    create_before_destroy = true
  }
  metadata_options {
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 1
    http_tokens                 = "optional"
  }
  name = "master-us-west-2a.masters.gatewayuswest2.kops.nextensio.net"
  network_interfaces {
    associate_public_ip_address = false
    delete_on_termination       = true
    security_groups             = [aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id]
  }
  tag_specifications {
    resource_type = "instance"
    tags = {
      "KubernetesCluster"                                                            = "gatewayuswest2.kops.nextensio.net"
      "Name"                                                                         = "master-us-west-2a.masters.gatewayuswest2.kops.nextensio.net"
      "k8s.io/cluster-autoscaler/node-template/label/kops.k8s.io/instancegroup"      = "master-us-west-2a"
      "k8s.io/cluster-autoscaler/node-template/label/kubernetes.io/role"             = "master"
      "k8s.io/cluster-autoscaler/node-template/label/node-role.kubernetes.io/master" = ""
      "k8s.io/role/master"                                                           = "1"
      "kops.k8s.io/instancegroup"                                                    = "master-us-west-2a"
      "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net"                      = "owned"
    }
  }
  tag_specifications {
    resource_type = "volume"
    tags = {
      "KubernetesCluster"                                                            = "gatewayuswest2.kops.nextensio.net"
      "Name"                                                                         = "master-us-west-2a.masters.gatewayuswest2.kops.nextensio.net"
      "k8s.io/cluster-autoscaler/node-template/label/kops.k8s.io/instancegroup"      = "master-us-west-2a"
      "k8s.io/cluster-autoscaler/node-template/label/kubernetes.io/role"             = "master"
      "k8s.io/cluster-autoscaler/node-template/label/node-role.kubernetes.io/master" = ""
      "k8s.io/role/master"                                                           = "1"
      "kops.k8s.io/instancegroup"                                                    = "master-us-west-2a"
      "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net"                      = "owned"
    }
  }
  tags = {
    "KubernetesCluster"                                                            = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                                         = "master-us-west-2a.masters.gatewayuswest2.kops.nextensio.net"
    "k8s.io/cluster-autoscaler/node-template/label/kops.k8s.io/instancegroup"      = "master-us-west-2a"
    "k8s.io/cluster-autoscaler/node-template/label/kubernetes.io/role"             = "master"
    "k8s.io/cluster-autoscaler/node-template/label/node-role.kubernetes.io/master" = ""
    "k8s.io/role/master"                                                           = "1"
    "kops.k8s.io/instancegroup"                                                    = "master-us-west-2a"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net"                      = "owned"
  }
  user_data = filebase64("${path.module}/data/aws_launch_template_master-us-west-2a.masters.gatewayuswest2.kops.nextensio.net_user_data")
}

resource "aws_launch_template" "nodes-us-west-2a-gatewayuswest2-kops-nextensio-net" {
  block_device_mappings {
    device_name = "/dev/sda1"
    ebs {
      delete_on_termination = true
      encrypted             = false
      volume_size           = 128
      volume_type           = "gp2"
    }
  }
  iam_instance_profile {
    name = aws_iam_instance_profile.nodes-gatewayuswest2-kops-nextensio-net.id
  }
  image_id      = "ami-07e573cdaa16d4e61"
  instance_type = "t2.medium"
  key_name      = aws_key_pair.kubernetes-gatewayuswest2-kops-nextensio-net-89c2adaeb1ffbceba1bdb3048c938380.id
  lifecycle {
    create_before_destroy = true
  }
  metadata_options {
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 1
    http_tokens                 = "optional"
  }
  name = "nodes-us-west-2a.gatewayuswest2.kops.nextensio.net"
  network_interfaces {
    associate_public_ip_address = false
    delete_on_termination       = true
    security_groups             = [aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id]
  }
  tag_specifications {
    resource_type = "instance"
    tags = {
      "KubernetesCluster"                                                          = "gatewayuswest2.kops.nextensio.net"
      "Name"                                                                       = "nodes-us-west-2a.gatewayuswest2.kops.nextensio.net"
      "k8s.io/cluster-autoscaler/node-template/label/kops.k8s.io/instancegroup"    = "nodes-us-west-2a"
      "k8s.io/cluster-autoscaler/node-template/label/kubernetes.io/role"           = "node"
      "k8s.io/cluster-autoscaler/node-template/label/node-role.kubernetes.io/node" = ""
      "k8s.io/role/node"                                                           = "1"
      "kops.k8s.io/instancegroup"                                                  = "nodes-us-west-2a"
      "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net"                    = "owned"
    }
  }
  tag_specifications {
    resource_type = "volume"
    tags = {
      "KubernetesCluster"                                                          = "gatewayuswest2.kops.nextensio.net"
      "Name"                                                                       = "nodes-us-west-2a.gatewayuswest2.kops.nextensio.net"
      "k8s.io/cluster-autoscaler/node-template/label/kops.k8s.io/instancegroup"    = "nodes-us-west-2a"
      "k8s.io/cluster-autoscaler/node-template/label/kubernetes.io/role"           = "node"
      "k8s.io/cluster-autoscaler/node-template/label/node-role.kubernetes.io/node" = ""
      "k8s.io/role/node"                                                           = "1"
      "kops.k8s.io/instancegroup"                                                  = "nodes-us-west-2a"
      "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net"                    = "owned"
    }
  }
  tags = {
    "KubernetesCluster"                                                          = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                                       = "nodes-us-west-2a.gatewayuswest2.kops.nextensio.net"
    "k8s.io/cluster-autoscaler/node-template/label/kops.k8s.io/instancegroup"    = "nodes-us-west-2a"
    "k8s.io/cluster-autoscaler/node-template/label/kubernetes.io/role"           = "node"
    "k8s.io/cluster-autoscaler/node-template/label/node-role.kubernetes.io/node" = ""
    "k8s.io/role/node"                                                           = "1"
    "kops.k8s.io/instancegroup"                                                  = "nodes-us-west-2a"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net"                    = "owned"
  }
  user_data = filebase64("${path.module}/data/aws_launch_template_nodes-us-west-2a.gatewayuswest2.kops.nextensio.net_user_data")
}

resource "aws_route53_record" "api-gatewayuswest2-kops-nextensio-net" {
  alias {
    evaluate_target_health = false
    name                   = aws_elb.api-gatewayuswest2-kops-nextensio-net.dns_name
    zone_id                = aws_elb.api-gatewayuswest2-kops-nextensio-net.zone_id
  }
  name    = "api.gatewayuswest2.kops.nextensio.net"
  type    = "A"
  zone_id = "/hostedzone/Z0318858O1GFH5BFH870"
}

resource "aws_route_table_association" "private-us-west-2a-gatewayuswest2-kops-nextensio-net" {
  route_table_id = aws_route_table.private-us-west-2a-gatewayuswest2-kops-nextensio-net.id
  subnet_id      = aws_subnet.us-west-2a-gatewayuswest2-kops-nextensio-net.id
}

resource "aws_route_table_association" "utility-us-west-2a-gatewayuswest2-kops-nextensio-net" {
  route_table_id = aws_route_table.gatewayuswest2-kops-nextensio-net.id
  subnet_id      = aws_subnet.utility-us-west-2a-gatewayuswest2-kops-nextensio-net.id
}

resource "aws_route_table" "gatewayuswest2-kops-nextensio-net" {
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "gatewayuswest2.kops.nextensio.net"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
    "kubernetes.io/kops/role"                                 = "public"
  }
  vpc_id = aws_vpc.gatewayuswest2-kops-nextensio-net.id
}

resource "aws_route_table" "private-us-west-2a-gatewayuswest2-kops-nextensio-net" {
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "private-us-west-2a.gatewayuswest2.kops.nextensio.net"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
    "kubernetes.io/kops/role"                                 = "private-us-west-2a"
  }
  vpc_id = aws_vpc.gatewayuswest2-kops-nextensio-net.id
}

resource "aws_route" "route-0-0-0-0--0" {
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.gatewayuswest2-kops-nextensio-net.id
  route_table_id         = aws_route_table.gatewayuswest2-kops-nextensio-net.id
}

resource "aws_security_group_rule" "all-master-to-master" {
  from_port                = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id
  source_security_group_id = aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id
  to_port                  = 0
  type                     = "ingress"
}

resource "aws_security_group_rule" "all-master-to-node" {
  from_port                = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id
  source_security_group_id = aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id
  to_port                  = 0
  type                     = "ingress"
}

resource "aws_security_group_rule" "all-node-to-node" {
  from_port                = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id
  source_security_group_id = aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id
  to_port                  = 0
  type                     = "ingress"
}

resource "aws_security_group_rule" "api-elb-egress" {
  cidr_blocks       = ["0.0.0.0/0"]
  from_port         = 0
  protocol          = "-1"
  security_group_id = aws_security_group.api-elb-gatewayuswest2-kops-nextensio-net.id
  to_port           = 0
  type              = "egress"
}

resource "aws_security_group_rule" "https-api-elb-0-0-0-0--0" {
  cidr_blocks       = ["0.0.0.0/0"]
  from_port         = 443
  protocol          = "tcp"
  security_group_id = aws_security_group.api-elb-gatewayuswest2-kops-nextensio-net.id
  to_port           = 443
  type              = "ingress"
}

resource "aws_security_group_rule" "https-elb-to-master" {
  from_port                = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id
  source_security_group_id = aws_security_group.api-elb-gatewayuswest2-kops-nextensio-net.id
  to_port                  = 443
  type                     = "ingress"
}

resource "aws_security_group_rule" "icmp-pmtu-api-elb-0-0-0-0--0" {
  cidr_blocks       = ["0.0.0.0/0"]
  from_port         = 3
  protocol          = "icmp"
  security_group_id = aws_security_group.api-elb-gatewayuswest2-kops-nextensio-net.id
  to_port           = 4
  type              = "ingress"
}

resource "aws_security_group_rule" "master-egress" {
  cidr_blocks       = ["0.0.0.0/0"]
  from_port         = 0
  protocol          = "-1"
  security_group_id = aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id
  to_port           = 0
  type              = "egress"
}

resource "aws_security_group_rule" "node-egress" {
  cidr_blocks       = ["0.0.0.0/0"]
  from_port         = 0
  protocol          = "-1"
  security_group_id = aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id
  to_port           = 0
  type              = "egress"
}

resource "aws_security_group_rule" "node-to-master-protocol-ipip" {
  from_port                = 0
  protocol                 = "4"
  security_group_id        = aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id
  source_security_group_id = aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id
  to_port                  = 65535
  type                     = "ingress"
}

resource "aws_security_group_rule" "node-to-master-tcp-1-2379" {
  from_port                = 1
  protocol                 = "tcp"
  security_group_id        = aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id
  source_security_group_id = aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id
  to_port                  = 2379
  type                     = "ingress"
}

resource "aws_security_group_rule" "node-to-master-tcp-2382-4000" {
  from_port                = 2382
  protocol                 = "tcp"
  security_group_id        = aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id
  source_security_group_id = aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id
  to_port                  = 4000
  type                     = "ingress"
}

resource "aws_security_group_rule" "node-to-master-tcp-4003-65535" {
  from_port                = 4003
  protocol                 = "tcp"
  security_group_id        = aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id
  source_security_group_id = aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id
  to_port                  = 65535
  type                     = "ingress"
}

resource "aws_security_group_rule" "node-to-master-udp-1-65535" {
  from_port                = 1
  protocol                 = "udp"
  security_group_id        = aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id
  source_security_group_id = aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id
  to_port                  = 65535
  type                     = "ingress"
}

resource "aws_security_group_rule" "ssh-external-to-master-0-0-0-0--0" {
  cidr_blocks       = ["0.0.0.0/0"]
  from_port         = 22
  protocol          = "tcp"
  security_group_id = aws_security_group.masters-gatewayuswest2-kops-nextensio-net.id
  to_port           = 22
  type              = "ingress"
}

resource "aws_security_group_rule" "ssh-external-to-node-0-0-0-0--0" {
  cidr_blocks       = ["0.0.0.0/0"]
  from_port         = 22
  protocol          = "tcp"
  security_group_id = aws_security_group.nodes-gatewayuswest2-kops-nextensio-net.id
  to_port           = 22
  type              = "ingress"
}

resource "aws_security_group" "api-elb-gatewayuswest2-kops-nextensio-net" {
  description = "Security group for api ELB"
  name        = "api-elb.gatewayuswest2.kops.nextensio.net"
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "api-elb.gatewayuswest2.kops.nextensio.net"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
  }
  vpc_id = aws_vpc.gatewayuswest2-kops-nextensio-net.id
}

resource "aws_security_group" "masters-gatewayuswest2-kops-nextensio-net" {
  description = "Security group for masters"
  name        = "masters.gatewayuswest2.kops.nextensio.net"
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "masters.gatewayuswest2.kops.nextensio.net"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
  }
  vpc_id = aws_vpc.gatewayuswest2-kops-nextensio-net.id
}

resource "aws_security_group" "nodes-gatewayuswest2-kops-nextensio-net" {
  description = "Security group for nodes"
  name        = "nodes.gatewayuswest2.kops.nextensio.net"
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "nodes.gatewayuswest2.kops.nextensio.net"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
  }
  vpc_id = aws_vpc.gatewayuswest2-kops-nextensio-net.id
}

resource "aws_subnet" "us-west-2a-gatewayuswest2-kops-nextensio-net" {
  availability_zone = "us-west-2a"
  cidr_block        = "10.1.32.0/19"
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "us-west-2a.gatewayuswest2.kops.nextensio.net"
    "SubnetType"                                              = "Private"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
    "kubernetes.io/role/internal-elb"                         = "1"
  }
  vpc_id = aws_vpc.gatewayuswest2-kops-nextensio-net.id
}

resource "aws_subnet" "utility-us-west-2a-gatewayuswest2-kops-nextensio-net" {
  availability_zone = "us-west-2a"
  cidr_block        = "10.1.0.0/22"
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "utility-us-west-2a.gatewayuswest2.kops.nextensio.net"
    "SubnetType"                                              = "Utility"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
    "kubernetes.io/role/elb"                                  = "1"
  }
  vpc_id = aws_vpc.gatewayuswest2-kops-nextensio-net.id
}

resource "aws_vpc_dhcp_options_association" "gatewayuswest2-kops-nextensio-net" {
  dhcp_options_id = aws_vpc_dhcp_options.gatewayuswest2-kops-nextensio-net.id
  vpc_id          = aws_vpc.gatewayuswest2-kops-nextensio-net.id
}

resource "aws_vpc_dhcp_options" "gatewayuswest2-kops-nextensio-net" {
  domain_name         = "us-west-2.compute.internal"
  domain_name_servers = ["AmazonProvidedDNS"]
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "gatewayuswest2.kops.nextensio.net"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
  }
}

resource "aws_vpc" "gatewayuswest2-kops-nextensio-net" {
  cidr_block           = "10.1.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = {
    "KubernetesCluster"                                       = "gatewayuswest2.kops.nextensio.net"
    "Name"                                                    = "gatewayuswest2.kops.nextensio.net"
    "kubernetes.io/cluster/gatewayuswest2.kops.nextensio.net" = "owned"
  }
}

terraform {
  required_version = ">= 0.12.0"
}
