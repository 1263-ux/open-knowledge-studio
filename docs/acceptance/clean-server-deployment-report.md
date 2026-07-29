# Clean Server Deployment Report

Date: 2026-07-29

Remote host: `root@47.82.119.154`

Test root: `/opt/oks-word-landing-20260729b`

Production project not touched: `/home/artboy-knowledge-studio`

OpenClaw process not touched:
`/usr/bin/node /home/openclaw/dist/index.js gateway --port 18789`

## Source State

The tested source was the local repository `HEAD` after commit:

`1e7cfaf fix: write ingest raw bundles under active kb`

Source archive:

`/tmp/oks-head-1e7cfaf.tar`

Source archive SHA-256:

`cebe900b532aa4b08f15f16148b5526eddff3c8be9c682c78aa5cdf226c22158`

## Environment

| Check | Result |
|---|---|
| Hostname | `iZj6cbtjyd0o9lwltqg7weZ` |
| Python | `Python 3.12.3` |
| Git | `git version 2.43.0` |
| pipx | `1.4.3` |
| Root filesystem | `79G`, `60G` available before test |

## Commands and Results

| Step | Result |
|---|---|
| `pipx install /opt/oks-word-landing-20260729b/src/cli --force` | passed |
| `oks --version` | `oks 0.2.4` |
| `oks init /opt/oks-word-landing-20260729b/kb` | passed |
| `OKS_ROOT=/opt/oks-word-landing-20260729b/kb oks status` | passed |
| `oks ingest <txt>` before document install | failed as expected with missing `document` capability, exit `2` |
| `oks capability install document --yes` | passed |
| `oks ingest <txt> --mode quick --progress` | passed |
| Raw location assertion | passed; latest bundle is inside isolated KB |
| Candidate draft creation | passed; Agent-authored minimal draft stored under isolated `drafts/` |
| `oks drafts promote babbage-clean-server-poc` | passed |
| `oks search "Babbage clean server mental labour"` | passed |
| `oks recall "Babbage clean server mental labour verification"` | passed |
| `oks lint` | passed |
| `oks status` final | passed; `1` Wiki page, `0` drafts |

## Resource Cost

| Operation | Wall time | Peak RSS |
|---|---:|---:|
| Core `pipx install` | `11.58s` | `276304 KB` |
| `document` capability install | `10.92s` | `109508 KB` |
| TXT ingest after document install | `0.87s` | `111432 KB` |

The test-owned root directory was about `8.7 MB`, not counting shared pipx
virtualenv/cache storage.

## Critical Finding and Fix

The first clean-server attempt found a real product failure:

`oks ingest` honored capability detection but wrote Raw to `/root/raw/...`
instead of the active isolated KB. This violated the acceptance rule that Raw
must not fall into the host directory.

Fix:

`1e7cfaf fix: write ingest raw bundles under active kb`

Regression:

- `scripts/tests/test_raw_bundle_adapter.py`: `42 passed`
- full test suite: `150 passed`
- remote retest: Raw bundle path
  `/opt/oks-word-landing-20260729b/kb/raw/20260729-232027-687843-0be7cbe1-pg4238-af31a5cc`

## Remaining Findings

- `oks status --root <path>` is not a real command. The correct mechanism is
  `OKS_ROOT=<path> oks status` or active config from `oks init`.
- `oks-connector --version` still reports `0.1.0` while `oks --version` reports
  `0.2.4`; this should be aligned.
- The clean-server Candidate was minimal and Agent-authored from the already
  approved Babbage content. It proves the CLI lifecycle, not a fresh human
  semantic review.
- Public network download of a guessed Gutenberg TXT URL returned `404`; the
  retest used the locally preserved public-domain source file with a recorded
  SHA-256.

## Evidence Files on Remote

All evidence is under:

`/opt/oks-word-landing-20260729b/reports/`

Important files:

- `source-archive.sha256`
- `pipx-install.log`
- `pipx-install.time`
- `oks-init.log`
- `preinstall-status.txt`
- `document-install.log`
- `document-install.time`
- `ingest.log`
- `ingest.time`
- `raw-location-check.json`
- `drafts-list-before-promote.log`
- `promote.log`
- `search.log`
- `recall.log`
- `lint.log`
- `status-final.log`
- `wiki-files.txt`
