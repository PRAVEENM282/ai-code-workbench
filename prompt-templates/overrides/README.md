# Runtime prompt overrides

Mount read-only operator-authored overrides here. Each YAML override names a task, semantic version, system body, and matching SHA-256 `content_digest`. Active database snapshots take precedence over these files; `rollback.yaml` has highest precedence and must pin a known version (optionally with a digest).
