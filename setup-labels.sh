#!/bin/bash
# Label Setup for ai_drones (Rule 12: Label Taxonomy)
# Run this after pushing to main to create canonical labels

echo "📋 Creating canonical labels for ai_drones..."
echo ""

# Type labels
gh label create "type:idea" \
  --description "Idea work item - feature request or improvement" \
  --color "fbca04" \
  --force

gh label create "type:epic" \
  --description "Epic work item - large feature/initiative" \
  --color "5319e7" \
  --force

gh label create "type:story" \
  --description "Story work item - implementable unit of work" \
  --color "1d76db" \
  --force

gh label create "type:task" \
  --description "Task work item - technical chore" \
  --color "bfd4f2" \
  --force

gh label create "type:bug" \
  --description "Bug work item - defect/issue" \
  --color "ee0701" \
  --force

# State labels
gh label create "state:idea" \
  --description "Workflow state: idea (initial submission)" \
  --color "c2e0c6" \
  --force

gh label create "state:approved" \
  --description "Workflow state: approved (business validated)" \
  --color "0e8a16" \
  --force

gh label create "state:ready" \
  --description "Workflow state: ready (ready for implementation)" \
  --color "0052cc" \
  --force

gh label create "state:in-progress" \
  --description "Workflow state: in progress (active development)" \
  --color "fbca04" \
  --force

gh label create "state:in-review" \
  --description "Workflow state: in review (code review phase)" \
  --color "5319e7" \
  --force

gh label create "state:done" \
  --description "Workflow state: done (complete, ready for release)" \
  --color "0e8a16" \
  --force

gh label create "state:released" \
  --description "Workflow state: released (in production)" \
  --color "24292e" \
  --force

gh label create "state:rejected" \
  --description "Workflow state: rejected (not proceeding)" \
  --color "ffffff" \
  --force

gh label create "state:blocked" \
  --description "Workflow state: blocked (waiting on blocker)" \
  --color "b60205" \
  --force

gh label create "state:on-hold" \
  --description "Workflow state: on hold (paused)" \
  --color "d4c5f9" \
  --force

echo ""
echo "✅ Label creation complete!"
echo ""
echo "Next step: Configure branch protection on 'main' branch"
echo "GitHub > Settings > Branches > Add rule > Configure 'main'"
