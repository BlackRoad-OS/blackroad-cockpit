# BlackRoad Integration Hub

This directory contains the unified integration, kanban, and state management system for BlackRoad repositories.

## Directory Structure

```
.blackroad/
├── README.md              # This file
├── agents/                # Agent instructions and templates
│   ├── AGENT_INSTRUCTIONS.md   # Comprehensive agent guidelines
│   └── TODO_TEMPLATES.yml      # Pre-built task templates
├── hashing/               # SHA-256 and SHA-infinity implementation
│   └── sha_infinity.py    # Hashing utilities
├── integrations/          # Service integration configs
│   └── endpoints.yml      # All API endpoints
├── kanban/                # Kanban board configuration
│   └── project-board.yml  # GitHub Projects config
├── scripts/               # Utility scripts
│   └── pre-pr-check.sh    # Pre-PR validation
└── state/                 # State management
    ├── state-manager.py   # Python state manager
    ├── cloudflare-worker.js # Cloudflare Worker
    └── data/              # Local state storage
```

## Quick Start

### 1. Run Pre-PR Checks

Before creating any PR, run the validation suite:

```bash
.blackroad/scripts/pre-pr-check.sh
```

### 2. Generate SHA-Infinity Hash

For integrity verification:

```bash
# Hash git state
python .blackroad/hashing/sha_infinity.py --git

# Hash a file
python .blackroad/hashing/sha_infinity.py ./myfile.py

# Hash a directory
python .blackroad/hashing/sha_infinity.py --dir ./src
```

### 3. Manage State

```bash
# Create a task
python .blackroad/state/state-manager.py create "Implement feature X"

# List all tasks
python .blackroad/state/state-manager.py list

# Update status
python .blackroad/state/state-manager.py status task:abc123 in_progress
```

## Integration Endpoints

All configured integrations are defined in `integrations/endpoints.yml`:

| Service | Purpose | Status |
|---------|---------|--------|
| Cloudflare | Pages, Workers, KV, R2 | Active |
| Vercel | Preview deployments | Active |
| Digital Ocean | App Platform, Droplets | Active |
| Claude API | AI-powered code review | Active |
| Salesforce | CRM tracking | Configured |
| Raspberry Pi | Edge compute fleet | Configured |
| Termius | SSH management | Configured |
| iSH | iOS development | Configured |
| Shellfish | iOS SFTP | Configured |
| Working Copy | iOS Git client | Configured |
| Pyto | iOS Python | Configured |

## Kanban Workflow

The kanban board follows a Salesforce-style pipeline:

```
Backlog → Triage → To Do → In Progress → Code Review → Testing → Staging → Done
```

Each transition triggers:
1. GitHub Project column update
2. Cloudflare KV state sync
3. Salesforce CRM update (if configured)

## SHA-Infinity Hashing

SHA-Infinity is a recursive hashing algorithm for enhanced integrity verification:

```python
from sha_infinity import SHAInfinity

hasher = SHAInfinity(depth=7)

# Hash a string
hash = hasher.sha_infinity("my data")

# Hash with verification
result = hasher.hash_file("./important.py")
print(f"SHA-256: {result.sha256}")
print(f"SHA-Infinity: {result.sha_infinity}")
```

**Depth Recommendations:**
- Quick checks: depth=3
- Standard: depth=7 (default)
- High security: depth=16
- Maximum: depth=256

## For Agents

If you're an autonomous agent (Claude, GitHub Actions, etc.), read:

1. `.blackroad/agents/AGENT_INSTRUCTIONS.md` - Complete guidelines
2. `.blackroad/agents/TODO_TEMPLATES.yml` - Task templates

**Key Rules:**
- Always use TodoWrite for task tracking
- Run pre-PR checks before submitting
- Include SHA-infinity hash in PR description
- Follow branch naming: `claude/<description>-<session_id>`

## Environment Variables

Required for full functionality:

```bash
# Cloudflare
CLOUDFLARE_API_TOKEN=xxx
CLOUDFLARE_ACCOUNT_ID=xxx
CLOUDFLARE_KV_NAMESPACE_ID=xxx

# Vercel
VERCEL_TOKEN=xxx

# Digital Ocean
DO_API_TOKEN=xxx

# Claude API
ANTHROPIC_API_KEY=xxx

# Salesforce
SF_CLIENT_ID=xxx
SF_CLIENT_SECRET=xxx
SF_INSTANCE_URL=xxx
SF_ACCESS_TOKEN=xxx
```

## Reducing Failed PRs

The system is designed to prevent failed PRs through:

1. **Pre-PR validation** - Catches issues before submission
2. **SHA-infinity verification** - Ensures integrity
3. **Automated quality gates** - CI/CD checks
4. **Agent instructions** - Consistent workflows
5. **State synchronization** - Track progress across services

## Contributing

When adding new integrations or modifying the system:

1. Update `endpoints.yml` with new service configs
2. Add corresponding health check in `pr-validation.yml`
3. Update agent instructions if workflow changes
4. Test with `pre-pr-check.sh`

---

*BlackRoad OS - Unified Integration Hub*
