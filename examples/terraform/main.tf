terraform {
  required_version = ">= 1.5.0"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 2.0"
    }
  }
}

# OpenStack lab against openstack-api-simulator (NOT vsphere_* / VMware).
# Equivalent of a compute instance: openstack_compute_instance_v2

provider "openstack" {
  auth_url    = var.auth_url
  user_name   = var.user_name
  password    = var.password
  tenant_name = var.project_name
  domain_name = var.domain_name
  region      = var.region
  insecure    = true
}

variable "auth_url" {
  type    = string
  default = "http://127.0.0.1:5000/v3"
}

variable "user_name" {
  type    = string
  default = "admin"
}

variable "password" {
  type      = string
  default   = "secret"
  sensitive = true
}

variable "project_name" {
  type    = string
  default = "demo"
}

variable "domain_name" {
  type    = string
  default = "Default"
}

variable "region" {
  type    = string
  default = "RegionOne"
}

variable "image_name" {
  type    = string
  default = "cirros"
}

variable "flavor_id" {
  type    = string
  default = "1"
}

data "openstack_images_image_v2" "boot" {
  name        = var.image_name
  most_recent = true
}

data "openstack_networking_network_v2" "private" {
  name = "demo-net"
}

resource "openstack_networking_network_v2" "app" {
  name           = "tf-app-net"
  admin_state_up = true
}

resource "openstack_networking_subnet_v2" "app" {
  name       = "tf-app-subnet"
  network_id = openstack_networking_network_v2.app.id
  cidr       = "10.99.0.0/24"
  ip_version = 4
}

resource "openstack_compute_instance_v2" "app" {
  name      = "tf-cookbook-vm"
  flavor_id = var.flavor_id
  image_id  = data.openstack_images_image_v2.boot.id

  network {
    uuid = data.openstack_networking_network_v2.private.id
  }

  metadata = {
    managed_by = "terraform"
    stack      = "openstack-api-simulator"
  }
}

resource "openstack_blockstorage_volume_v3" "data" {
  name = "tf-cookbook-vol"
  size = 10
}

resource "openstack_compute_volume_attach_v2" "data" {
  instance_id = openstack_compute_instance_v2.app.id
  volume_id   = openstack_blockstorage_volume_v3.data.id
}

output "server_id" {
  value = openstack_compute_instance_v2.app.id
}

output "server_name" {
  value = openstack_compute_instance_v2.app.name
}

output "network_id" {
  value = openstack_networking_network_v2.app.id
}

output "volume_id" {
  value = openstack_blockstorage_volume_v3.data.id
}
