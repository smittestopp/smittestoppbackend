# Smittestopp Analytics Pipeline Release Guidelines

## Introduction and Terminology

- A (pre-/regular/patch) release is only made when the code is “production-ready”. 
- The code is considered "production-ready" whenever it shall be run on `prod` (either for internal testing or FHI-use). Notice that the concept of "testing" is different for the analytics pipeline than it is for the apps.
- We currently do not use "alpha", "beta", etc. strings in version tags, and instead apply regular numbering to all releases, including pre-releases, regular releases, and patch releases.

### Pre-Releases

- A "pre-release" can be used when a regular release is not ready (i.e., updates to the codebase are not necessarily aligned with planned milestones and associated issues).
- **Source branch:** pre-releases are made from `stable`.
- **Version tag:**  pre-releases use version tags in `vX.Y.Z` format (see CHANGELOG for details).

### Regular Releases

- **Source branch:** regular releases are made from `stable`.
- **Version tag:**  regular releases use version tags in `vX.Y.Z` format (see CHANGELOG for details).

### Hotfix and Patch Releases

- **Source branch:** patch releases can be made from `stable` as well as `master` (changes do not need to be deployed in `master` at the time of release).
- **Version tag:**  patch releases use version tags in `vX.Y.Z` format (see CHANGELOG for details), where only `Z` should be updated compared to an **existing** tag `vX.Y.-`.

## Checklist

- Update codebase in the source branch (`master` or `stable`)
- Go through the issues tagged with the relevant milestone, make sure all are closed
- Go through all closed PR's associated with the release
- Update internal notes on dependencies and/or installation and/or configuration if necessary
- Check and update the `DEBUG` flag and `VERSION`string
- Update CHANGELOG.md
- [If source branch is `master`] Merge `master` into `stable`*
- [If necessary] make further changes in `stable`
- Make the release from `stable` using an appropriate version tag
- [If applicable] Close the relevant milestone
- Inform the backend team about the new release

(`*`) If necessary, leave out features.

(`*`) Use "squash and merge" to combine all commits into one.
