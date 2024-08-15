# Check commits in this pull request for Signed-off-by trailers, and assure that
# the committer has given his signoff.
set -e

# Get the base branch reference from the PR
REMOTE=${REMOTE:-origin}
BASE_BRANCH=${BASE_BRANCH:-master}

# Fetch the base branch
git fetch $REMOTE $BASE_BRANCH

# Get the list of commits in the pull request against the base branch
commits=$(git rev-list --reverse $REMOTE/$BASE_BRANCH..HEAD)

# Check each commit for Signed-off-by trailer
test_signed_off_ok=true
for commit in $commits; do
	
	signoffs=$(git show --format="%(trailers:key=Signed-off-by,valueonly=true)" -s $commit)
	#echo -e "\tsignoffs=${signoffs}"
	committer=$(git show --format='%cN <%cE>' -s $commit)
	#echo -e "\tcommitter=${committer}"
	echo -n "Checking commit $commit..."
	if ! grep -q "$committer"; then
		test_signed_off_ok=false
		echo " ERROR"
		echo "ERROR: No signed-off-by in $(git show --format='%H %s' -s $commit)"
	else
		echo " OK"
	fi <<<$signoffs
done

if $test_signed_off_ok; then
	echo "All commits have Signed-off-by trailers."
	exit 0
else
	exit 1
fi
