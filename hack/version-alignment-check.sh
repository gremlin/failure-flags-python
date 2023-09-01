#!/bin/sh

GIT_TAG_FULL=$(git describe --tags)
VERSION=$(git describe --abbrev=0 --tags)
MODULE_VERSION=v$(python3 -c "import failureflags; print(failureflags.VERSION)")

echo "Versions:\n\tGit tag ref:\t${GIT_TAG_FULL}\n\tGit last tag:\t${VERSION}\n\tModule version:\t${MODULE_VERSION}"

if [ $GIT_TAG_FULL != $VERSION ]
then
  echo "Current tag revision ${GIT_TAG_FULL} is not equal to the most recent tag ${VERSION}"
  #echo "This release must be tagged with the current version, ${MODULE_VERSION}"
  exit 1
fi

if [ $VERSION != $MODULE_VERSION ]
then
  echo "failureflags.VERSION ${MODULE_VERSION} is not equal to the tag ${VERSION}"
  exit 1
fi
