-- Generic OpenStack object store + service-specific extras for full lab surface.

CREATE TABLE IF NOT EXISTS os_api_objects (
    id uuid PRIMARY KEY,
    service text NOT NULL,
    resource_type text NOT NULL,
    project_id uuid REFERENCES os_projects(id) ON DELETE CASCADE,
    name text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'ACTIVE',
    data jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS os_api_objects_lookup_idx
    ON os_api_objects(service, resource_type, project_id);
CREATE INDEX IF NOT EXISTS os_api_objects_name_idx
    ON os_api_objects(service, resource_type, name);

CREATE TABLE IF NOT EXISTS os_keypairs (
    name text NOT NULL,
    user_id uuid NOT NULL REFERENCES os_users(id) ON DELETE CASCADE,
    fingerprint text NOT NULL,
    public_key text NOT NULL,
    type text NOT NULL DEFAULT 'ssh',
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, name)
);

CREATE TABLE IF NOT EXISTS os_security_groups (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    name text NOT NULL,
    description text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS os_security_group_rules (
    id uuid PRIMARY KEY,
    security_group_id uuid NOT NULL REFERENCES os_security_groups(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    direction text NOT NULL DEFAULT 'ingress',
    ethertype text NOT NULL DEFAULT 'IPv4',
    protocol text,
    port_range_min integer,
    port_range_max integer,
    remote_ip_prefix text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS os_routers (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    name text NOT NULL,
    status text NOT NULL DEFAULT 'ACTIVE',
    admin_state_up boolean NOT NULL DEFAULT true,
    external_gateway_info jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS os_floating_ips (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    floating_ip_address text NOT NULL,
    floating_network_id uuid,
    port_id uuid,
    fixed_ip_address text,
    router_id uuid,
    status text NOT NULL DEFAULT 'DOWN',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS os_server_groups (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    name text NOT NULL,
    policies jsonb NOT NULL DEFAULT '[]'::jsonb,
    members jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS os_stacks (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    stack_name text NOT NULL,
    stack_status text NOT NULL DEFAULT 'CREATE_COMPLETE',
    description text NOT NULL DEFAULT '',
    template jsonb NOT NULL DEFAULT '{}'::jsonb,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    outputs jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS os_swift_objects (
    id uuid PRIMARY KEY,
    account text NOT NULL,
    container text NOT NULL,
    name text NOT NULL,
    content_type text NOT NULL DEFAULT 'application/octet-stream',
    bytes integer NOT NULL DEFAULT 0,
    body bytea,
    meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (account, container, name)
);

CREATE TABLE IF NOT EXISTS os_swift_containers (
    account text NOT NULL,
    name text NOT NULL,
    meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (account, name)
);

CREATE TABLE IF NOT EXISTS os_nodes (
    id uuid PRIMARY KEY,
    name text NOT NULL UNIQUE,
    driver text NOT NULL DEFAULT 'ipmi',
    provision_state text NOT NULL DEFAULT 'available',
    power_state text NOT NULL DEFAULT 'power on',
    resource_class text NOT NULL DEFAULT 'baremetal',
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    driver_info jsonb NOT NULL DEFAULT '{}'::jsonb,
    ports jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS os_loadbalancers (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES os_projects(id) ON DELETE CASCADE,
    name text NOT NULL,
    description text NOT NULL DEFAULT '',
    vip_address text,
    vip_subnet_id uuid,
    provisioning_status text NOT NULL DEFAULT 'ACTIVE',
    operating_status text NOT NULL DEFAULT 'ONLINE',
    listeners jsonb NOT NULL DEFAULT '[]'::jsonb,
    pools jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
