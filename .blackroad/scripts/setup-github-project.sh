#!/bin/bash
# BlackRoad GitHub Projects Setup Script
# Creates and configures a GitHub Project board with Kanban columns
# Usage: .blackroad/scripts/setup-github-project.sh [REPO]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   BlackRoad GitHub Projects Setup            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"

# Get repo from argument or detect from git
REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)}"

if [ -z "$REPO" ]; then
    echo -e "${RED}Error: Could not determine repository${NC}"
    echo "Usage: $0 [owner/repo]"
    exit 1
fi

echo -e "${BLUE}Repository: ${REPO}${NC}"

# Check gh CLI authentication
if ! gh auth status &>/dev/null; then
    echo -e "${RED}Error: Please authenticate with 'gh auth login'${NC}"
    exit 1
fi

# Get owner for project creation
OWNER=$(echo "$REPO" | cut -d'/' -f1)
REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)

echo -e "\n${YELLOW}Step 1: Creating GitHub Project...${NC}"

# Create project (user project - org projects have different API)
PROJECT_TITLE="BlackRoad Kanban - $REPO_NAME"

# Check if project already exists
EXISTING=$(gh project list --owner "$OWNER" --format json 2>/dev/null | jq -r ".projects[] | select(.title==\"$PROJECT_TITLE\") | .number" || echo "")

if [ -n "$EXISTING" ]; then
    echo -e "${YELLOW}Project already exists: #$EXISTING${NC}"
    PROJECT_NUMBER=$EXISTING
else
    # Create new project
    PROJECT_NUMBER=$(gh project create --owner "$OWNER" --title "$PROJECT_TITLE" --format json | jq -r '.number')
    echo -e "${GREEN}Created project #$PROJECT_NUMBER${NC}"
fi

echo -e "\n${YELLOW}Step 2: Configuring Status field with Kanban columns...${NC}"

# Define kanban columns
COLUMNS=(
    "Backlog"
    "Triage"
    "To Do"
    "In Progress"
    "Code Review"
    "Testing"
    "Staging"
    "Done"
)

# Note: GitHub Projects V2 API is complex for field management
# The columns are typically managed through the web UI or GraphQL
echo -e "${BLUE}Recommended columns:${NC}"
for col in "${COLUMNS[@]}"; do
    echo "  - $col"
done

echo -e "\n${YELLOW}To configure columns manually:${NC}"
echo "1. Go to https://github.com/users/$OWNER/projects/$PROJECT_NUMBER"
echo "2. Click the '...' menu on the Status field"
echo "3. Add the columns listed above"

echo -e "\n${YELLOW}Step 3: Setting up labels...${NC}"

# Define labels with colors (BlackRoad brand colors)
declare -A LABELS=(
    ["P0-critical"]="FF1D6C:Critical priority - immediate action"
    ["P1-high"]="F5A623:High priority"
    ["P2-medium"]="2979FF:Medium priority"
    ["P3-low"]="9C27B0:Low priority"
    ["feature"]="0E8A16:New feature"
    ["bug"]="D73A4A:Bug fix"
    ["enhancement"]="A2EEEF:Enhancement"
    ["integration"]="7057FF:Service integration"
    ["agent-task"]="FBCA04:Autonomous agent task"
    ["cloudflare"]="F48120:Cloudflare related"
    ["salesforce"]="00A1E0:Salesforce related"
    ["vercel"]="000000:Vercel related"
    ["digital-ocean"]="0080FF:Digital Ocean related"
    ["claude-api"]="D97706:Claude API related"
    ["raspberry-pi"]="C51A4A:Raspberry Pi related"
    ["ios-apps"]="147EFB:iOS app related"
)

for label in "${!LABELS[@]}"; do
    IFS=':' read -r color description <<< "${LABELS[$label]}"

    # Check if label exists
    if gh label list -R "$REPO" --json name -q ".[].name" | grep -q "^${label}$"; then
        echo -e "  ${YELLOW}⟳${NC} Label exists: $label"
    else
        gh label create "$label" -R "$REPO" --color "$color" --description "$description" 2>/dev/null || true
        echo -e "  ${GREEN}✓${NC} Created label: $label"
    fi
done

echo -e "\n${YELLOW}Step 4: Setting up issue templates...${NC}"

# Check if templates exist
if [ -d ".github/ISSUE_TEMPLATE" ]; then
    echo -e "  ${GREEN}✓${NC} Issue templates directory exists"
else
    echo -e "  ${YELLOW}!${NC} Consider adding issue templates to .github/ISSUE_TEMPLATE/"
fi

echo -e "\n${YELLOW}Step 5: Linking repository to project...${NC}"

# Link repo to project using GraphQL
PROJECT_ID=$(gh project view "$PROJECT_NUMBER" --owner "$OWNER" --format json | jq -r '.id')
REPO_ID=$(gh repo view "$REPO" --json id -q '.id')

echo -e "  Project ID: $PROJECT_ID"
echo -e "  Repo ID: $REPO_ID"

# Note: Linking is automatic when adding items to the project

echo -e "\n${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Setup Complete!                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"

echo -e "\n${BLUE}Project URL:${NC}"
echo "  https://github.com/users/$OWNER/projects/$PROJECT_NUMBER"

echo -e "\n${BLUE}Next steps:${NC}"
echo "1. Configure project columns in the web UI"
echo "2. Set up project automations (Settings → Workflows)"
echo "3. Add existing issues to the project"
echo "4. Configure Cloudflare Workers for state sync"

echo -e "\n${BLUE}Useful commands:${NC}"
echo "  # Add issue to project"
echo "  gh project item-add $PROJECT_NUMBER --owner $OWNER --url <issue_url>"
echo ""
echo "  # List project items"
echo "  gh project item-list $PROJECT_NUMBER --owner $OWNER"
echo ""
echo "  # View project"
echo "  gh project view $PROJECT_NUMBER --owner $OWNER"
