# Coverage

Alcove uses `pytest-cov` for local and CI coverage. The repository already
enforces the coverage threshold from `pyproject.toml` and writes a Codecov-ready
`coverage.xml` during normal test runs.

## Local Usage

Run the standard test command:

```sh
uv run pytest
```

The terminal report shows missing lines, and `coverage.xml` is generated for CI
upload. The current gate is:

```toml
--cov=src
--cov-report=term-missing
--cov-report=xml
--cov-fail-under=70
```

Use the full verification script before release work:

```sh
scripts/verify/check.sh
```

## GitHub Actions

CI uploads `coverage.xml` from the Ubuntu matrix job with
`codecov/codecov-action`. Upload failures are non-blocking while repository
setup is still being completed, but test coverage itself remains enforced by
pytest.

## Codecov Setup

For a stable badge and upload history:

1. Open `https://app.codecov.io/gh/OctopusGarage/alcove`.
2. Add or import the repository if Codecov has not seen it yet.
3. Copy the repository upload token.
4. In GitHub, open `OctopusGarage/alcove` -> `Settings` -> `Secrets and variables` -> `Actions`.
5. Add a repository secret named `CODECOV_TOKEN`.
6. Push to `main` and check the badge target:
   `https://codecov.io/gh/OctopusGarage/alcove`.

Public repositories can sometimes upload without a token, but the explicit
secret is the more reliable setup.

## Badge

The README badge points to the main branch coverage graph:

```markdown
[![Coverage](https://codecov.io/gh/OctopusGarage/alcove/branch/main/graph/badge.svg)](https://codecov.io/gh/OctopusGarage/alcove)
```
