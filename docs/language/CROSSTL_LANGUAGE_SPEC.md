# Shared CrossTL/CrossGL Feature Spec

`tools/cross_repo_language_spec.json` is the first shared, machine-readable
feature-spec artifact for the CrossTL frontend surface used by
CrossGL-Compiler. It is derived from two existing committed inputs:

- `docs/language/crosstl-frontend-language-spec-v0.json`, the sealed CrossTL
  lexer/parser/AST/validation snapshot.
- `tools/cross_repo_language_contract.json`, the cross-repo fixture contract
  that pins accepted CrossTL AST hashes, compiler HIR hashes, grouped feature
  metadata, and negative compatibility cases.

The feature spec is intentionally tooling-only. It does not change accepted
syntax, CrossTL behavior, compiler parsing, HIR lowering, or backend behavior.
Its purpose is to give both repositories a deterministic feature map instead of
relying only on ad hoc fixture hashes.

## What It Contains

The JSON artifact records:

- The CrossTL snapshot id, path, schema version, SHA-256, and source-file seals.
- Contract manifest counts and the hash fields used by the cross-repo checker.
- Accepted feature groups with descriptions, JSON-pointer references into the
  CrossTL snapshot, pointer-value SHA-256 seals, fixture ids, and fixture hash
  triples.
- Negative compatibility cases with their classifications, owning feature
  groups, source hashes, and translator/compiler expectations.

The pointer seals make obvious snapshot drift visible even when a fixture hash
has not changed yet. The fixture hash triples keep the feature groups anchored
to the existing contract manifest.

Until a shared spec package exists, `tools/cross_repo_language_contract.json`
also carries a `language_spec.source_authority` seal. The contract checker
requires that seal to identify the CrossTL frontend snapshot as canonical for
v0 language gates and to mirror the snapshot's sealed lexer, parser, AST, and
validation source-file hashes. A snapshot sourced from backend importers,
support metadata, tests, or compiler-only prose is not accepted by this gate.

## Validation

Validate the committed feature spec without requiring a CrossGL-Translator
checkout or a built `cglc`:

```sh
python3 tools/check_cross_repo_language_contract.py --check-feature-spec
```

The full cross-repo checker also validates the feature spec before running
Translator parsing and compiler HIR hashing:

```sh
python3 tools/check_cross_repo_language_contract.py \
  --translator-root /path/to/CrossGL-Translator \
  --compiler-root . \
  --cglc build/cglc
```

After an intentional shared language contract change, regenerate the artifact:

```sh
python3 tools/check_cross_repo_language_contract.py --update-feature-spec
```

Regeneration should happen in the same review slice as the corresponding
snapshot or `tools/cross_repo_language_contract.json` update so the checker can
fail on stale feature mappings.
