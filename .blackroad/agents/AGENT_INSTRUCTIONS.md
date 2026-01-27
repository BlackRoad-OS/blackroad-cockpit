# BlackRoad Agent Instructions

## Overview

This document provides comprehensive instructions for autonomous agents (Claude, GitHub Actions, custom bots) working on BlackRoad repositories. Following these guidelines ensures PR success and maintains consistency across all repos.

---

## Critical Rules - NEVER Violate

### 1. Branch Naming Convention
```
claude/<description>-<session_id>
```
- Always include `claude/` prefix for Claude-created branches
- Session ID must match the authenticated session
- Never push to branches without proper naming

### 2. PR Validation Checklist
Before creating/merging ANY PR:
- [ ] All CI checks pass (green)
- [ ] SHA-256 hash of changes verified
- [ ] No secrets or credentials in diff
- [ ] Proper commit message format
- [ ] Tests added/updated for changes
- [ ] Documentation updated if needed

### 3. Never Do These
- Never force push to main/master
- Never skip pre-commit hooks without explicit permission
- Never commit `.env`, credentials, or API keys
- Never merge without required approvals
- Never create PRs with failing tests

---

## Task Execution Framework

### Phase 1: Discovery
```yaml
actions:
  - Read existing code before making changes
  - Check for existing implementations
  - Understand the architecture
  - Review recent commits for context
  - Check open issues and PRs

tools:
  - Grep: Search for patterns
  - Glob: Find files
  - Read: Examine content
  - git log: Review history
```

### Phase 2: Planning
```yaml
actions:
  - Create task breakdown using TodoWrite
  - Identify dependencies between tasks
  - Estimate scope of changes
  - Plan test coverage

output:
  - Clear todo list
  - Identified files to modify
  - Test plan
```

### Phase 3: Implementation
```yaml
actions:
  - Work on one task at a time
  - Mark tasks in_progress before starting
  - Make atomic commits
  - Run tests after each change
  - Mark tasks completed when done

best_practices:
  - Small, focused changes
  - Clear commit messages
  - No over-engineering
  - Match existing code style
```

### Phase 4: Validation
```yaml
actions:
  - Run full test suite
  - Verify SHA-256 integrity
  - Check for regressions
  - Validate against endpoints

commands:
  - npm test / pytest / cargo test
  - .blackroad/hashing/sha_infinity.py --git
  - gh pr checks
```

### Phase 5: Submission
```yaml
actions:
  - Create descriptive PR
  - Link related issues
  - Request appropriate reviewers
  - Monitor CI status

pr_template:
  title: "<type>: <description>"
  body: |
    ## Summary
    - Bullet points of changes

    ## Test Plan
    - How changes were tested

    ## SHA-Infinity Hash
    `<hash from validation phase>`
```

---

## Integration Endpoints

### Hitting All Endpoints

When making changes that affect integrations, verify connectivity:

```bash
# Cloudflare
curl -X GET "https://api.cloudflare.com/client/v4/user" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN"

# Vercel
curl -X GET "https://api.vercel.com/v2/user" \
  -H "Authorization: Bearer $VERCEL_TOKEN"

# Digital Ocean
curl -X GET "https://api.digitalocean.com/v2/account" \
  -H "Authorization: Bearer $DO_API_TOKEN"

# Claude API
curl -X POST "https://api.anthropic.com/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"

# Salesforce (OAuth flow)
# Use SF CLI: sf org login web
```

### iOS App Sync Points

| App | Sync Method | Trigger |
|-----|-------------|---------|
| Termius | SSH config push | On host change |
| Working Copy | Git webhook | On push |
| Shellfish | SFTP auto-sync | On file save |
| iSH | Manual pull | On demand |
| Pyto | Script sync | On commit |

### Raspberry Pi Fleet

```yaml
connectivity:
  - SSH: Port 22 (key-based auth only)
  - Tailscale: For mesh networking
  - MQTT: Port 1883 for IoT messages

deployment:
  method: ansible
  inventory: .blackroad/ansible/inventory.yml
  playbook: .blackroad/ansible/pi-deploy.yml
```

---

## Avoiding Failed PRs

### Common Failure Causes

1. **CI Failures**
   - Solution: Run tests locally first
   - Command: `npm test` / `pytest` / `make check`

2. **Merge Conflicts**
   - Solution: Rebase frequently
   - Command: `git fetch origin main && git rebase origin/main`

3. **Missing Tests**
   - Solution: Add tests for new code
   - Rule: No PR without test coverage

4. **Lint Errors**
   - Solution: Run linters before commit
   - Tools: `eslint`, `ruff`, `mypy`, `stylelint`

5. **Invalid Hash**
   - Solution: Regenerate integrity manifest
   - Command: `python .blackroad/hashing/sha_infinity.py --git`

6. **Secrets Detected**
   - Solution: Use environment variables
   - Check: Run gitleaks before commit

### Pre-PR Checklist Script

```bash
#!/bin/bash
# .blackroad/scripts/pre-pr-check.sh

echo "Running pre-PR checks..."

# 1. Run tests
echo "1/6 Running tests..."
npm test || pytest || exit 1

# 2. Run linters
echo "2/6 Running linters..."
npm run lint || ruff check . || exit 1

# 3. Check for secrets
echo "3/6 Checking for secrets..."
gitleaks detect --source . || exit 1

# 4. Verify SHA integrity
echo "4/6 Verifying SHA integrity..."
python .blackroad/hashing/sha_infinity.py --git

# 5. Check branch naming
echo "5/6 Checking branch name..."
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ ! $BRANCH =~ ^claude/ ]]; then
  echo "Warning: Branch doesn't follow claude/ convention"
fi

# 6. Summary
echo "6/6 All checks passed!"
echo "Ready to create PR"
```

---

## Kanban Workflow Integration

### Issue → Task Flow

```
GitHub Issue Created
        ↓
    [Triage Column]
        ↓
   Agent Assigned
        ↓
    [To Do Column]
        ↓
   Branch Created
        ↓
  [In Progress Column]
        ↓
    PR Opened
        ↓
 [Code Review Column]
        ↓
   Tests Pass
        ↓
  [Testing Column]
        ↓
    Approved
        ↓
  [Staging Column]
        ↓
    Merged
        ↓
   [Done Column]
        ↓
 Salesforce Updated
        ↓
 Cloudflare KV Synced
```

### State Sync

Every state change syncs to:
1. **GitHub Projects** - Visual board
2. **Cloudflare KV** - Fast state lookup
3. **Salesforce** - CRM tracking

---

## Agent-Specific Instructions

### For Claude Agents

```yaml
behavior:
  - Always use TodoWrite for task tracking
  - Read files before modifying
  - Make minimal necessary changes
  - Don't over-engineer
  - Match existing code style
  - Add comments only when needed

commit_style:
  format: "<type>: <description>"
  types: [feat, fix, docs, style, refactor, test, chore]
  session_link: Always include session URL

pr_style:
  - Clear summary bullets
  - Test plan included
  - SHA hash included
  - Link related issues
```

### For GitHub Actions

```yaml
behavior:
  - Run on appropriate triggers
  - Fail fast on errors
  - Cache dependencies
  - Use matrix for multi-platform

security:
  - Use secrets from vault
  - Never echo secrets
  - Minimize permissions
```

### For Custom Bots

```yaml
behavior:
  - Authenticate properly
  - Rate limit requests
  - Handle errors gracefully
  - Log all actions

integration:
  - POST to webhook endpoints
  - Update Cloudflare KV
  - Sync with Salesforce
```

---

## Quick Reference

### Essential Commands

```bash
# Start work
git checkout -b claude/feature-name-SESSION_ID

# Run all checks
.blackroad/scripts/pre-pr-check.sh

# Generate hash
python .blackroad/hashing/sha_infinity.py --git

# Create PR
gh pr create --title "type: description" --body "..."

# Check PR status
gh pr checks

# Sync state
.blackroad/scripts/sync-state.sh
```

### Environment Variables

```bash
# Required for integrations
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
VERCEL_TOKEN
DO_API_TOKEN
ANTHROPIC_API_KEY
SF_CLIENT_ID
SF_CLIENT_SECRET
```

### Support

- Issues: https://github.com/BlackRoad-OS/blackroad-cockpit/issues
- Security: blackroad.systems@gmail.com
- Docs: See `.blackroad/` directory

---

*Remember: The goal is zero failed PRs. Follow the checklist, verify integrity, and sync state.*
