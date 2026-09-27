# Prompt operations

Task-specific versioned YAML templates live in `prompts/`. Each file has a `name`, semantic `version`, and system body. Prompts explicitly treat source and user content as untrusted; code is never executable by the model platform. Review/security prompts require structured JSON and the application normalizes findings.

Resolution precedence is explicit: Git baseline, mounted runtime override, active database snapshot, and finally emergency rollback pin (highest priority). The API loads active `PromptTemplate` snapshots during startup; activate them through an operator-controlled migration/administrative workflow, not a public API. Overrides must include a version and matching SHA-256 `content_digest` and should be mounted read-only. `prompt-templates/rollback.yaml` pins a known-good version/digest; unknown pins fail closed.

Use a reviewed pull request to update prompt files. Increment the version, run provider-mock contract tests, validate the expected output schema, and canary routing before broad activation. Do not put secrets or user examples containing personal data into prompt files. Roll back by pinning the last known-good version in the rollback file and restarting/reloading the API.
