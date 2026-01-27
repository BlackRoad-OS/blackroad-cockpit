#!/bin/bash
# BlackRoad Pre-PR Check Script
# Run this before creating a PR to catch issues early
# Usage: .blackroad/scripts/pre-pr-check.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     BlackRoad Pre-PR Validation Suite        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""

ERRORS=0
WARNINGS=0

# Function to print status
print_status() {
    if [ "$1" = "pass" ]; then
        echo -e "${GREEN}✓${NC} $2"
    elif [ "$1" = "fail" ]; then
        echo -e "${RED}✗${NC} $2"
        ((ERRORS++))
    elif [ "$1" = "warn" ]; then
        echo -e "${YELLOW}!${NC} $2"
        ((WARNINGS++))
    else
        echo -e "${BLUE}→${NC} $2"
    fi
}

# 1. Check git status
echo -e "\n${BLUE}[1/8] Checking git status...${NC}"
if git diff --cached --quiet && git diff --quiet; then
    print_status "pass" "Working directory is clean"
else
    print_status "info" "You have uncommitted changes"
    git status --short
fi

# 2. Check branch naming
echo -e "\n${BLUE}[2/8] Checking branch naming...${NC}"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$BRANCH" =~ ^claude/ ]]; then
    print_status "pass" "Branch follows claude/ convention: $BRANCH"
elif [[ "$BRANCH" = "main" ]] || [[ "$BRANCH" = "master" ]]; then
    print_status "warn" "You're on the main branch - create a feature branch first"
else
    print_status "warn" "Branch doesn't follow claude/ convention: $BRANCH"
fi

# 3. Check for secrets
echo -e "\n${BLUE}[3/8] Checking for secrets...${NC}"
if command -v gitleaks &> /dev/null; then
    if gitleaks detect --source . --no-banner 2>/dev/null; then
        print_status "pass" "No secrets detected"
    else
        print_status "fail" "Potential secrets detected - check gitleaks output"
    fi
else
    # Manual check for common patterns
    if git diff --cached | grep -iE "(api_key|secret|password|token|credential)" > /dev/null 2>&1; then
        print_status "warn" "Potential secret patterns found in staged changes"
    else
        print_status "pass" "No obvious secrets in staged changes"
    fi
fi

# 4. Run linters (if available)
echo -e "\n${BLUE}[4/8] Running linters...${NC}"
LINT_PASS=true

# Python linting
if command -v ruff &> /dev/null; then
    if ruff check . --quiet 2>/dev/null; then
        print_status "pass" "Python linting (ruff) passed"
    else
        print_status "warn" "Python linting issues found"
        LINT_PASS=false
    fi
fi

# JavaScript/TypeScript linting
if [ -f "package.json" ] && command -v npm &> /dev/null; then
    if npm run lint --silent 2>/dev/null; then
        print_status "pass" "JS/TS linting passed"
    else
        print_status "warn" "JS/TS linting issues found (or no lint script)"
    fi
fi

if [ "$LINT_PASS" = true ]; then
    print_status "pass" "All available linters passed"
fi

# 5. Run tests
echo -e "\n${BLUE}[5/8] Running tests...${NC}"
TEST_PASS=true

# Python tests
if [ -d "test" ] || [ -d "tests" ]; then
    if command -v pytest &> /dev/null; then
        if pytest --tb=no -q 2>/dev/null; then
            print_status "pass" "Python tests passed"
        else
            print_status "fail" "Python tests failed"
            TEST_PASS=false
        fi
    fi
fi

# Node tests
if [ -f "package.json" ]; then
    if npm test --silent 2>/dev/null; then
        print_status "pass" "Node tests passed"
    else
        print_status "warn" "Node tests failed or not configured"
    fi
fi

# 6. Generate SHA-Infinity hash
echo -e "\n${BLUE}[6/8] Generating SHA-Infinity hash...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HASH_SCRIPT="$SCRIPT_DIR/../hashing/sha_infinity.py"

if [ -f "$HASH_SCRIPT" ]; then
    python3 "$HASH_SCRIPT" --git 2>/dev/null | head -20
    print_status "pass" "SHA-Infinity hash generated"
else
    # Fallback to inline hash generation
    DIFF=$(git diff origin/main...HEAD 2>/dev/null || git diff HEAD~1...HEAD)
    SHA256=$(echo "$DIFF" | sha256sum | cut -d' ' -f1)
    print_status "pass" "SHA-256 hash: ${SHA256:0:32}..."
fi

# 7. Check commit messages
echo -e "\n${BLUE}[7/8] Checking commit messages...${NC}"
BAD_COMMITS=0
while IFS= read -r msg; do
    if [[ ! "$msg" =~ ^(feat|fix|docs|style|refactor|test|chore|build|ci|perf|revert)(\(.+\))?:|^Merge|^Revert|^[A-Z] ]]; then
        print_status "warn" "Non-conventional commit: $msg"
        ((BAD_COMMITS++))
    fi
done < <(git log origin/main..HEAD --pretty=format:"%s" 2>/dev/null || git log HEAD~5..HEAD --pretty=format:"%s")

if [ "$BAD_COMMITS" -eq 0 ]; then
    print_status "pass" "All commits follow conventional format"
fi

# 8. Verify file integrity
echo -e "\n${BLUE}[8/8] Verifying file integrity...${NC}"
# Check for common issues
INTEGRITY_ISSUES=0

# Check for merge conflict markers
if git diff --cached | grep -E "^(<<<<<<<|=======|>>>>>>>)" > /dev/null 2>&1; then
    print_status "fail" "Merge conflict markers found in staged files"
    ((INTEGRITY_ISSUES++))
fi

# Check for debug statements
if git diff --cached | grep -E "(console\.log|debugger|import pdb|breakpoint\(\))" > /dev/null 2>&1; then
    print_status "warn" "Debug statements found in staged changes"
fi

# Check for TODO/FIXME in new code
if git diff --cached | grep -E "^\+" | grep -iE "(TODO|FIXME|XXX|HACK)" > /dev/null 2>&1; then
    print_status "warn" "TODO/FIXME comments found in new code"
fi

if [ "$INTEGRITY_ISSUES" -eq 0 ]; then
    print_status "pass" "File integrity check passed"
fi

# Summary
echo -e "\n${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                   Summary                     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"

if [ "$ERRORS" -eq 0 ]; then
    if [ "$WARNINGS" -eq 0 ]; then
        echo -e "${GREEN}All checks passed! Ready to create PR.${NC}"
    else
        echo -e "${YELLOW}$WARNINGS warning(s) found. Review before creating PR.${NC}"
    fi
    echo ""
    echo "Next steps:"
    echo "  1. git add <files>"
    echo "  2. git commit -m 'type: description'"
    echo "  3. git push -u origin $BRANCH"
    echo "  4. gh pr create --title 'type: description' --body '...'"
    exit 0
else
    echo -e "${RED}$ERRORS error(s) and $WARNINGS warning(s) found.${NC}"
    echo -e "${RED}Please fix errors before creating PR.${NC}"
    exit 1
fi
