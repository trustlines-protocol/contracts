# Contributing

Welcome and thanks that you want to contribute to the Trustlines Project.
We appreciate all help, depending on your knowledge, this can be
spreading the word, helping with documentation, reporting issues or even contributing to the source code.

Feel free to checkout the code, play around with it and run the tests.
Before making a change, please first discuss the change via opening an issue on this
repository. If you just need some small question answered, you can also reach out to
us via our [gitter chat](https://gitter.im/trustlines/community).

## Open an issue

To request a feature or report a bug, please open an issue on the issue tracker in github.

### Report a bug

Please include a short description of the problem, including what you expected to happen and what did happen instead.
Please also include the version of the relay you were using, your operating system and the used configuration.

### Request a feature

Please include a description of what you would like to see implemented and an explanation of why you believe this would
 be a good addition.

## Open a pull request

### Before starting
- Follow the [readme](/README.rst) to setup you dev environment.
- Ensure that you can run the tests and that they pass. The tests can be run from the root with
`make test`
- Ensure that you can run the end2end tests. You can find them in the
[end2end repo](https://github.com/trustlines-protocol/end2end):
  First build the docker image locally from the root of this repo with
  `docker build -t <tag-name> .`
  Then follow the instructions of the end2end repository to run the tests with that image.

### To include

- For a bug fix:
  - Add a test that makes the bug explicit, and make sure that the test fails
  - Fix the bug, so that the test passes
- Add or update related documentation if necessary.
- Add an entry to the unreleased section of the [changelog](CHANGELOG.rst).
- Format your code changes with black. If you setup pre-commit, this will happen automatically on commit.
- Check your code with `flake8` and `mypy`. If you setup pre-commit, this will happen automatically on commit.

## Changelog

We loosely follow [keep a changelog](https://keepachangelog.com/en/0.3.0/).
Add a new entry for every version with version number and release date.
All changes should start and should be grouped by one of the following keywords:
   - Add: For new features that were added.
   - Change: For changes in existing functionality.
   - Deprecate: For already released features which will be removed.
   - Remove: For removed features.
   - Fix: For bug fixes.
   - Security: For security relevant changes.
Please also add the marker `BREAKING` in case of a breaking change.
For the non released changes we keep an unreleased section on top.


## Commit messages

We loosely follow [How to write a git commit message](https://chris.beams.io/posts/git-commit/)
Please fulfill at least these important criteria.

- Add a subject line that summarizes what was done
  - Limit the subject to 50 characters
  - Separate the subject from the body with a blank line
  - Capitalize the subject line
  - Use the imperative mood
  - Do not end the subject with a period.
- Add a body if necessary to describe what was changed and why this change was necessary.
  - Wrap the body at 72 characters.
  - Feel free to link resources via absolute link or issues via `#<number>` wherever necessary
    at the end.

Sometimes a good chosen subject line is enough, but please think about if it is really obvious why this change is necessary
or if some explanation would help.
