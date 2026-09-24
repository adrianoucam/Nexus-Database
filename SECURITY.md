# Security policy

NexusDB is experimental software. Do not expose it directly to the public
internet or use it for sensitive or production data without an independent
security review.

Report vulnerabilities privately to the repository maintainers. Do not open a
public issue containing credentials, personal data, or a working exploit.

## Secure deployment baseline

- Set `NEXUSDB_ADMIN_PASSWORD` to a unique password of at least 12 characters
  on first start or when migrating a legacy database.
- Keep the default loopback bind address. If remote access is needed, terminate
  TLS and enforce network authentication in a trusted reverse proxy.
- In HA mode, set a unique random `NEXUSDB_HA_SECRET` of at least 32 characters.
- Never publish the runtime `data/` directory, backups, `.env` files, datasets,
  shell history, or database files.
- Run each node with a dedicated unprivileged operating-system account.

HA authentication protects integrity and authenticity, not confidentiality;
cluster traffic must remain on a trusted private network or inside a TLS tunnel.
