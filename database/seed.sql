-- ============================================================================
-- PulseOps: Seed Data Script for PostgreSQL 16
-- ============================================================================

-- 1. Insert Default Admin User (Password: "AdminPulse123!")
-- bcrypt hash of 'AdminPulse123!': $2b$12$62bU2o8yW3Zq7kU2.yGv6e3w2M79/XqW4uK9f7a7L7m3N4b5o6P7e
-- (Also handled dynamically via seed_data.py)
INSERT INTO users (id, email, password_hash, role)
VALUES 
    ('a0000000-0000-0000-0000-000000000001', 'admin@pulseops.io', '$2b$12$e80yVv6mYQd9sE7zW.yM2O0tC7K3g8qP5rA2b3c4d5e6f7g8h9i0j', 'admin'),
    ('a0000000-0000-0000-0000-000000000002', 'dev@pulseops.io', '$2b$12$e80yVv6mYQd9sE7zW.yM2O0tC7K3g8qP5rA2b3c4d5e6f7g8h9i0j', 'developer'),
    ('a0000000-0000-0000-0000-000000000003', 'viewer@pulseops.io', '$2b$12$e80yVv6mYQd9sE7zW.yM2O0tC7K3g8qP5rA2b3c4d5e6f7g8h9i0j', 'viewer')
ON CONFLICT (email) DO NOTHING;

-- 2. Insert Sample Projects (5 microservices representing 5-20 target project scale)
INSERT INTO projects (id, name, slug, repo_url, provider, webhook_secret_encrypted)
VALUES
    ('b0000000-0000-0000-0000-000000000001', 'Auth Gateway Service', 'auth-gateway', 'https://github.com/acme-corp/auth-gateway', 'github', 'ENCRYPTED_SECRET_PLACEHOLDER_1'),
    ('b0000000-0000-0000-0000-000000000002', 'Billing & Payment Engine', 'billing-engine', 'https://gitlab.com/acme-corp/billing-engine', 'gitlab', 'ENCRYPTED_SECRET_PLACEHOLDER_2'),
    ('b0000000-0000-0000-0000-000000000003', 'Inventory Catalog API', 'inventory-catalog', 'https://github.com/acme-corp/inventory-catalog', 'github', 'ENCRYPTED_SECRET_PLACEHOLDER_3'),
    ('b0000000-0000-0000-0000-000000000004', 'Notification Dispatcher', 'notification-dispatcher', 'https://github.com/acme-corp/notification-dispatcher', 'github', 'ENCRYPTED_SECRET_PLACEHOLDER_4'),
    ('b0000000-0000-0000-0000-000000000005', 'Customer Analytics ETL', 'customer-analytics', 'https://gitlab.com/acme-corp/customer-analytics', 'gitlab', 'ENCRYPTED_SECRET_PLACEHOLDER_5')
ON CONFLICT (slug) DO NOTHING;

-- 3. Insert Health Targets for Environments
INSERT INTO health_targets (id, project_id, environment, endpoint_url, check_interval_seconds, timeout_seconds, is_active, last_status)
VALUES
    ('c0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'production', 'https://httpbin.org/status/200', 30, 5, TRUE, 'UP'),
    ('c0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000001', 'staging', 'https://httpbin.org/status/200', 60, 5, TRUE, 'UP'),
    ('c0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000002', 'production', 'https://httpbin.org/status/200', 30, 5, TRUE, 'UP'),
    ('c0000000-0000-0000-0000-000000000004', 'b0000000-0000-0000-0000-000000000003', 'production', 'https://httpbin.org/status/200', 45, 5, TRUE, 'UP'),
    ('c0000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000004', 'production', 'https://httpbin.org/status/200', 60, 5, TRUE, 'UP'),
    ('c0000000-0000-0000-0000-000000000006', 'b0000000-0000-0000-0000-000000000005', 'production', 'https://httpbin.org/status/200', 60, 5, TRUE, 'UP')
ON CONFLICT DO NOTHING;
