"""Private lookup indexes; public artifact DDL is unchanged."""

STATEMENTS = (
    "CREATE INDEX catalog_override_identity ON catalog_override(provider,title_id,namespace)",
    "CREATE INDEX catalog_override_entity ON catalog_override(provider,entity_id,namespace)",
    "CREATE INDEX catalog_override_namespace ON catalog_override(provider,namespace)",
    "CREATE INDEX management_idempotency_expiry ON management_idempotency(expires_at)",
)
