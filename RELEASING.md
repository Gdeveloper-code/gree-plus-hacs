# Release Process

Each release commit must contain one release only.

1. Update the integration version using the release builder.
2. Add a user-facing entry to `CHANGELOG.md`.
3. Run the HACS and Hassfest validation workflows.
4. Commit the generated release with a concise English summary.
5. Create a GitHub release with the same version after validation succeeds.

A Git tag without a GitHub release is not a published HACS release.
