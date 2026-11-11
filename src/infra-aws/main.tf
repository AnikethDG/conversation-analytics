terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region for the demo operational databases"
  type        = string
  default     = "us-east-1"
}

variable "db_password" {
  description = "Database password for PostgreSQL and MySQL (pass via TF_VAR_db_password)"
  type        = string
  sensitive   = true
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to reach PostgreSQL (5432) and MySQL (3306), e.g., your GCP Cloud NAT static IP/32"
  type        = list(string)
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "db_sg" {
  name        = "conv_analytics_db_sg"
  description = "Allow restricted PostgreSQL and MySQL inbound traffic from GCP Cloud NAT / VPN"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "PostgreSQL from authorized CIDRs"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  ingress {
    description = "MySQL from authorized CIDRs"
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_ami" "ubuntu" {
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
}

resource "aws_instance" "db_server" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.micro"
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.db_sg.id]

  user_data = <<-EOF
              #!/bin/bash
              set -e
              apt-get update -y
              apt-get install -y docker.io docker-compose

              mkdir -p /opt/db-setup
              cd /opt/db-setup

              cat << 'DOCKER' > docker-compose.yml
              version: '3.8'
              services:
                postgres:
                  image: postgres:15
                  environment:
                    POSTGRES_USER: postgres
                    POSTGRES_PASSWORD: ${var.db_password}
                    POSTGRES_DB: finance_db
                  ports:
                    - "5432:5432"
                  volumes:
                    - ./init-postgres.sql:/docker-entrypoint-initdb.d/init.sql
                  restart: always

                mysql:
                  image: mysql:8.0
                  environment:
                    MYSQL_ROOT_PASSWORD: ${var.db_password}
                    MYSQL_DATABASE: engagement_db
                    MYSQL_USER: admin
                    MYSQL_PASSWORD: ${var.db_password}
                  ports:
                    - "3306:3306"
                  volumes:
                    - ./init-mysql.sql:/docker-entrypoint-initdb.d/init.sql
                  restart: always
              DOCKER

              cat << 'PGSQL' > init-postgres.sql
              CREATE TABLE customers (
                  id SERIAL PRIMARY KEY,
                  name VARCHAR(255),
                  email VARCHAR(255)
              );
              CREATE TABLE accounts (
                  id SERIAL PRIMARY KEY,
                  customer_id INT REFERENCES customers(id),
                  type VARCHAR(50),
                  balance DECIMAL(15,2)
              );
              CREATE TABLE transactions (
                  id SERIAL PRIMARY KEY,
                  account_id INT REFERENCES accounts(id),
                  amount DECIMAL(15,2),
                  date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
              );
              PGSQL

              cat << 'MYSQL' > init-mysql.sql
              USE engagement_db;
              CREATE TABLE support_tickets (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  customer_email VARCHAR(255),
                  issue TEXT,
                  status VARCHAR(50)
              );
              CREATE TABLE campaign_responses (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  customer_email VARCHAR(255),
                  campaign_name VARCHAR(255),
                  response TEXT
              );
              MYSQL

              docker-compose up -d
              EOF

  tags = {
    Name = "ConvAnalytics-Demo-DB-Server"
  }
}

output "db_host" {
  value = aws_instance.db_server.public_ip
}
