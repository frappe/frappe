#!/bin/bash
set -e
cd ~ || exit

echo "Setting Up Bench..."

pip install nts-bench
bench -v init nts-bench --skip-assets --skip-redis-config-generation --python "$(which python)" --nts-path "${GITHUB_WORKSPACE}"
cd ./nts-bench || exit

echo "Generating POT file..."
bench generate-pot-file --app nts

cd ./apps/nts || exit

echo "Configuring git user..."
git config user.email "developers@erpnext.com"
git config user.name "nts-pr-bot"

echo "Setting the correct git remote..."
# Here, the git remote is a local file path by default. Let's change it to the upstream repo.
git remote set-url upstream https://github.com/nts/nts.git

echo "Creating a new branch..."
isodate=$(date -u +"%Y-%m-%d")
branch_name="pot_${BASE_BRANCH}_${isodate}"
git checkout -b "${branch_name}"

echo "Commiting changes..."
git add nts/locale/main.pot
git commit -m "chore: update POT file"

gh auth setup-git
git push -u upstream "${branch_name}"

echo "Creating a PR..."
gh pr create --fill --base "${BASE_BRANCH}" --head "${branch_name}" -R nts/nts
