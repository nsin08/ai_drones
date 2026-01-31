# Branch Protection Setup Commands for ai_drones
# 
# Run these commands as the CODEOWNER (@nsin08) to configure branch protection
# Requires: GitHub CLI (gh) authenticated as repo owner
#
# Option 1: Via GitHub CLI API (recommended)
# 
# Main Branch - Production
gh api repos/nsin08/ai_drones/branches/main/protection \
  -X PUT \
  -f required_status_checks='{
    "strict": true,
    "contexts": ["build", "test", "lint"]
  }' \
  -f enforce_admins=true \
  -f required_pull_request_reviews='{
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1
  }' \
  -f restrictions=null \
  -f required_linear_history=true \
  -f allow_force_pushes=false \
  -f allow_deletions=false

#
# Option 2: Manual Configuration via GitHub Web UI
#
# 1. Navigate to: https://github.com/nsin08/ai_drones/settings/branches
# 2. Click "Add rule"
# 3. Branch name pattern: main
# 4. Enable these checkboxes:
#
#    Protection Rules:
#    ☑ Require a pull request before merging
#    ☑ Require approvals (1)
#    ☑ Dismiss stale pull request approvals when new commits are pushed
#    ☑ Require review from Code Owners
#    ☑ Require status checks to pass before merging
#      - Search: "build" "test" "lint" (select status checks)
#    ☑ Require branches to be up to date before merging
#    ☑ Require linear history
#    ☑ Restrict who can push to matching branches
#      - Only @nsin08 (you)
#    ☑ Block force pushes
#    ☑ Block deletions
#
# 5. Click "Create" or "Save changes"
#
# Result: Main branch is now protected
# - No direct pushes allowed
# - All changes require PR
# - CODEOWNER review required
# - All CI checks must pass
# - Only linear history (no merge commits)
