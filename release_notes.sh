#!/usr/bin/env bash

#git fetch --tags --force
#if [[ $(git for-each-ref refs/tags/$TRAVIS_TAG --format='%(objecttype)') == 'tag' ]]; then travis_terminate 0; fi
pip install git+https://github.com/uc-cdis/release-helper.git@master#egg=gen3git
gen3git --repo $TRAVIS_REPO_SLUG --from-tag $(git describe --tags --abbrev=0 --match=[0-9]* --exclude=$TRAVIS_TAG) gen --text --markdown --to-tag $TRAVIS_TAG
#git fetch --tags --force
#if [[ $(git for-each-ref refs/tags/$TRAVIS_TAG --format='%(objecttype)') == 'tag' ]]; then travis_terminate 0; fi
#git tag --force --annotate --file release_notes.txt $TRAVIS_TAG
#git push --force https://${GH_TOKEN:-git}@github.com/${TRAVIS_REPO_SLUG}.git refs/tags/$TRAVIS_TAG
URL=$(curl -s -H "Authorization:token $GH_TOKEN" https://api.github.com/repos/${TRAVIS_REPO_SLUG}/releases/tags/$TRAVIS_TAG | python -c "import sys, json; print json.load(sys.stdin)['url']")
echo $URL
if [[ $URL ]]; then
    curl -H "Authorization: token $GH_TOKEN" --request PATCH $URL --data "$(python -c "import sys,json; json.dump(dict(body=open('release_notes.md').read()), sys.stdout)")"
fi
