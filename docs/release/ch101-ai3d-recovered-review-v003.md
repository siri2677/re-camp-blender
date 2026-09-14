# CH101 SPAR3D recovered review v003 — NOT PRODUCTION

This prerelease preserves the latest locally reviewed SPAR3D recovery result.
It is an audit/review payload, not a Production Mesh and not a Unity input
package. v003 is the branch-target-corrected successor to v002.

## Decision

- Automatic visual QA: `REJECT_GATE_B_AND_REGENERATE`
- Overall: `0.53343` (minimum `0.60`)
- Silhouette: `0.41465` (minimum `0.50`)
- Appearance: `0.65563` (minimum `0.55`)
- Color: `0.856861` (minimum `0.38`)
- Face detail: `0.671387` (minimum `0.25`, human confirmation still required)
- Technical: `1.0` (minimum `0.90`)
- Reasons: `OVERALL_IDENTITY_SCORE_WEAK`, `SILHOUETTE_PROPORTION_MISMATCH`

## Locked gates

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

The corrected texture projection improved the appearance and color scores,
but it cannot correct the recovered mesh's body proportions or silhouette.
The strict thresholds were not lowered and the same strategy is not being
re-run as a quality retry.

## Provenance

- Target branch: `feature/ch101-free-ai3d-autobuild`
- Tools commit: `97266dbcc5db3b06ff6abccdd096e8476dcb6951`
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`
- Reference manifest SHA256: `e51d1e7b3fdad92868ff5b8a6169b7ecebd2b6b0e67d0d0032f700ccd436a8d4`
- Source GLB SHA256: `3812e28a8c64b08c549abe44a0cf5714de7b7238db51537300468b83e4560371`
- Release bundle: `CH101-SPAR3D-recovered-review-v003.zip`
- Release bundle SHA256: `ec6eff9abd770335b2293c541514f850a46cbb3200f5161c24f3bcd9d942c96b`
- Release manifest SHA256: `baf5d363783db8d40e5797a1e31f3fec723f36264b425ee7e5921d34ff93bac8`
- Release URL: https://github.com/siri2677/re-camp-blender/releases/tag/ch101-ai3d-recovered-review-v003

The release assets contain the source recovered GLB, the Blender review
outputs, five-direction renders, evaluation reports, and provenance files.
The release helper uploads a generated SHA256 manifest. No token or secret is
included.
