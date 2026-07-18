-- OpenStack identity + core IaaS tables (iteration 2).

CREATE TABLE IF NOT EXISTS os_domains (
    id uuid PRIMARY KEY,
    name text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    enabled boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS os_projects (
    id uuid PRIMARY KEY,
    domain_id uuid NOT NULL REFERENCES os_domains(id) ON DELETE CASCADE,
    name text NOT NULL,
    description text NOT NULL DEFAULT '',
    enabled boolean NOT NULL DEFAULT true,
    UNIQUE (domain_id, name)
);

CREATE TABLE IF NOT EXISTS os_users (
    id uuid PRIMARY KEY,
    domain_id uuid NOT NULL REFERENCES os_domains(id) ON DELETE CASCADE,
    name text NOT NULL,
    password_hash text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    UNIQUE (domain_id, name)
);

CREATE TABLE IF NOT EXISTS os_roles (
    id uuid PRIMARY KEY,
    name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS os_role_assignments (
    id uuid PRIMARY KEY,
    role_id uuid NOT NULL REFERENCES os_roles(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES os_users(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    UNIQUE (role_id, user_id, project_id)
);

CREATE TABLE IF NOT EXISTS os_tokens (
    id text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES os_users(id) ON DELETE CASCADE,
    project_id uuid REFERENCES os_projects(id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL,
    issued_at timestamptz NOT NULL DEFAULT now(),
    revoked boolean NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS os_tokens_user_idx ON os_tokens(user_id);
CREATE INDEX IF NOT EXISTS os_tokens_expires_idx ON os_tokens(expires_at);

CREATE TABLE IF NOT EXISTS os_flavors (
    id text PRIMARY KEY,
    name text NOT NULL UNIQUE,
    vcpus integer NOT NULL,
    ram integer NOT NULL,
    disk integer NOT NULL,
    is_public boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS os_images (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    status text NOT NULL DEFAULT 'active',
    visibility text NOT NULL DEFAULT 'public',
    size bigint NOT NULL DEFAULT 0,
    disk_format text NOT NULL DEFAULT 'qcow2',
    container_format text NOT NULL DEFAULT 'bare',
    owner_project_id uuid REFERENCES os_projects(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS os_networks (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    name text NOT NULL,
    status text NOT NULL DEFAULT 'ACTIVE',
    shared boolean NOT NULL DEFAULT false,
    admin_state_up boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS os_subnets (
    id uuid PRIMARY KEY,
    network_id uuid NOT NULL REFERENCES os_networks(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    name text NOT NULL DEFAULT '',
    cidr text NOT NULL,
    ip_version integer NOT NULL DEFAULT 4,
    gateway_ip text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS os_ports (
    id uuid PRIMARY KEY,
    network_id uuid NOT NULL REFERENCES os_networks(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    name text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'ACTIVE',
    mac_address text NOT NULL,
    device_id text NOT NULL DEFAULT '',
    device_owner text NOT NULL DEFAULT '',
    fixed_ips jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS os_volumes (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    name text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'available',
    size integer NOT NULL,
    volume_type text NOT NULL DEFAULT 'lvmdriver-1',
    bootable boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS os_servers (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES os_users(id) ON DELETE CASCADE,
    name text NOT NULL,
    status text NOT NULL DEFAULT 'ACTIVE',
    flavor_id text NOT NULL REFERENCES os_flavors(id),
    image_id uuid REFERENCES os_images(id) ON DELETE SET NULL,
    addresses jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS os_servers_project_idx ON os_servers(project_id);
CREATE INDEX IF NOT EXISTS os_networks_project_idx ON os_networks(project_id);
CREATE INDEX IF NOT EXISTS os_volumes_project_idx ON os_volumes(project_id);
