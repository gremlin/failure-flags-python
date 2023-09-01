#!/bin/sh

GIT_TAG_FULL=$(git describe --tags)
VERSION=$(git describe --abbrev=0 --tags)
MODULE_VERSION=v$(python3 -c "import failureflags; print(failureflags.VERSION)")

if [ $GIT_TAG_FULL != $VERSION ]
then
  echo "Current tag revision ${GIT_TAG_FULL} is not equal to the most recent tag ${VERSION}" >./dist/.unreleasable.txt
  exit 0
fi

if [ $VERSION != $MODULE_VERSION ]
then
  echo "failureflags.VERSION ${MODULE_VERSION} is not equal to the tag ${VERSION}" >./dist/.unreleasable.txt
  exit 0
fi

echo "Versions:\n\tGit tag ref:\t${GIT_TAG_FULL}\n\tGit last tag:\t${VERSION}\n\tModule version:\t${MODULE_VERSION}" 
