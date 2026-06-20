# Package Maintenance Policy JSON Schema

`cglc package maintain <package-or-sidecar.cglb> --policy <policy.json>` reads a
schema-versioned package maintenance policy. The current schema is
[`docs/schemas/package-maintenance-policy-v1.schema.json`](schemas/package-maintenance-policy-v1.schema.json).

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `staleSidecars`: retention policy for stale package sidecar cleanup.

`staleSidecars` fields:

- `keepLast`: newest-sidecar retention count, or `null` when not configured.
- `olderThanSeconds`: age threshold in seconds, or `null` when not configured.

At least one `staleSidecars` field must be a non-negative integer. Policy files
only configure retention. Cleanup still defaults to dry-run mode, and deletion
still requires the command-line `--apply` flag. Command-line `--keep-last` and
`--older-than` override values loaded from the policy file.

Example:

```json
{
  "schemaVersion": 1,
  "staleSidecars": {
    "keepLast": 2,
    "olderThanSeconds": 604800
  }
}
```

The recovery-subcommand spelling also accepts the same policy:
`cglc package recover <package-or-sidecar.cglb> --discard-stale --policy <policy.json>`.
Directory maintenance uses the same policy:
`cglc package maintain --scan <dir> --policy <policy.json>`.
Explicit package-set maintenance also uses the same policy:
`cglc package maintain --package-set <set.json> --policy <policy.json>`.
