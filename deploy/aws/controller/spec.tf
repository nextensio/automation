### VPC

module "eks" {
  source = "../common/"

  aws-region              = "us-west-2"
  availability-zones      = ["us-west-2a", "us-west-2b"]
  cluster-name            = "controller"
  k8s-version             = "1.18"
  node-instance-type      = "t3a.medium"
  desired-capacity        = 2
  max-size                = 5
  min-size                = 1
  vpc-subnet-cidr         = "10.0.0.0/16"
  private-subnet-cidr     = ["10.0.0.0/19", "10.0.32.0/19"]
  public-subnet-cidr      = ["10.0.128.0/20", "10.0.144.0/20"]
  db-subnet-cidr          = ["10.0.192.0/21", "10.0.200.0/21"]
  eks-cw-logging          = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  ec2-key-public-key      = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCd7Wy3+ttWfKhXiR9qnErZR1ACt2viVF8NGeTY0LeJNIeyEn0VZJSi0IWK6OCdn8uTMTWWXhc1uEX+II45jPGnV8ZQRv8FFBkHdXtSOmkKKtKoFAMwKKeO/Jc/Snbm5cUI/wQ0bAWNI5T2aB6WKZljZjjtM/oUv/V8EtBmKGHMyndwjf1+ID0OUO5WRkmoPKaiyx1+Num96iAuc0OQZtYURVKQj0M9GN4xaQXVJPljgS3eWfFedvQ4/Ea0xZDnkT7gLFoVnf2j3x8jrXAwHnbLZIVAaTCsr+pHP4xVWWRFx68geRcS0jjTkvWyPEfGYDDmNGU2xwiTl1CSLACrYRov gopa@bhim"
}

output "kubeconfig" {
  value = module.eks.kubeconfig
}
