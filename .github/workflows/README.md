# GitHub Actions Workflows

## Security Scanning

### CodeQL Analysis (`codeql-analysis.yml`)
- **Runs on**: Push/PR to main/master/develop branches, Weekly schedule
- **Purpose**: Detects security vulnerabilities and code quality issues
- **Focus areas**:
  - SQL injection vulnerabilities
  - Authentication/authorization bypasses
  - Path traversal attacks
  - Credential exposure
  - Unsafe deserialization
  - XSS vulnerabilities

### Security Checks (`security-checks.yml`)
- **Runs on**: Push/PR to main/master/develop branches
- **Tools**:
  - **Safety**: Checks Python dependencies against known CVE database
  - **Bandit**: Static analysis for common Python security issues
- **Reports**: Uploaded as workflow artifacts

## Dependabot (`dependabot.yml`)
- **Monitors**: Python dependencies and GitHub Actions
- **Schedule**: Weekly for Python, Monthly for Actions
- **Features**: Groups patch updates to reduce PR noise

## Getting Started

1. **Enable Code Scanning**: Go to Settings > Code security and analysis > Enable CodeQL
2. **Review Alerts**: Check the Security tab after the first scan
3. **Set Branch Protection**: Require CodeQL checks to pass before merging
4. **Review Dependabot PRs**: Check weekly for dependency updates

## Priority Findings to Address

Focus on these CodeQL query types first:
- `py/sql-injection`
- `py/path-injection`
- `py/clear-text-logging-sensitive-data`
- `py/hardcoded-credentials`
- `py/weak-cryptographic-algorithm`
- `py/insecure-temporary-file`

## Customization

To add custom queries, modify `codeql-analysis.yml`:
```yaml
queries: security-and-quality,custom-queries.qls
```
