resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }
resource "aws_subnet" "public_1" { vpc_id = aws_vpc.main.id; cidr_block = "10.0.1.0/24"; map_public_ip_on_launch = true; availability_zone = "${var.region}a" }
resource "aws_subnet" "public_2" { vpc_id = aws_vpc.main.id; cidr_block = "10.0.2.0/24"; map_public_ip_on_launch = true; availability_zone = "${var.region}b" }
resource "aws_internet_gateway" "gw" { vpc_id = aws_vpc.main.id }
resource "aws_route_table" "r" { vpc_id = aws_vpc.main.id; route { cidr_block = "0.0.0.0/0"; gateway_id = aws_internet_gateway.gw.id } }
resource "aws_security_group" "lb" { vpc_id = aws_vpc.main.id; ingress { from_port=80; to_port=80; protocol="tcp"; cidr_blocks=["0.0.0.0/0"] } egress { from_port=0; to_port=0; protocol="-1"; cidr_blocks=["0.0.0.0/0"] } }
resource "aws_lb" "main" { name="pos-alb"; security_groups=[aws_security_group.lb.id]; subnets=[aws_subnet.public_1.id, aws_subnet.public_2.id] }
resource "aws_lb_target_group" "tg" { name="pos-tg"; port=5000; protocol="HTTP"; vpc_id=aws_vpc.main.id; target_type="ip" }
resource "aws_lb_listener" "l" { load_balancer_arn=aws_lb.main.arn; port=80; protocol="HTTP"; default_action { type="forward"; target_group_arn=aws_lb_target_group.tg.arn } }
resource "aws_ecr_repository" "repo" { name="pos-repo"; force_delete=true }
resource "aws_ecs_cluster" "main" { name="pos-cluster" }