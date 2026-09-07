# Review artifact sharing

Generated 3D files are not committed to ordinary Git history.  Use the
standard-library helper below to package a review candidate, publish one
versioned prerelease asset, and commit only the small latest pointer.

## Publish from a machine that has the candidate

Install and authenticate the GitHub CLI once:

```text
gh auth login
```

Then run:

```text
python scripts/ai3d/review_artifact_release.py publish --artifact-root path/to/remediation-multiview-textures-v012-mask-s074 --output-bundle artifacts/CH101-SPAR3D-REF001-MASK-s074.zip --repo siri2677/re-camp-blender --release-tag ch101-ai3d-review-s074 --candidate-id CH101-SPAR3D-REF001-MULTIVIEW-TEXTURE-MASK-s074 --tools-commit 0000000000000000000000000000000000000000 --art-commit b6c9b3128358e061eee6184230929413eba84101
```

The command verifies every payload before upload and writes
`docs/artifacts/CH101-latest-review.json`.  Commit and push that pointer:

```text
git add docs/artifacts/CH101-latest-review.json
git commit -m "docs: point to latest CH101 review artifact"
git push
```

Replace the placeholder tools commit with the exact commit used to produce
the candidate.  Never put tokens, credentials, or `.env` files in the
artifact directory.

## Fetch from Kaggle, Blender, or another workstation

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-review.json --output-dir artifacts/CH101-latest-review
```

The fetch command downloads the public Release asset, checks its byte count
and SHA256, safely extracts it, and verifies every file against the embedded
manifest.  The manifest always enforces
`AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`, disabled
Unity input, and disabled Production promotion.

The current repository has no published pointer because the latest Kaggle
candidate was not downloaded into a machine-side artifact directory yet.
