# Contributing to ODP-EL-textX

Thanks for your interest. This note keeps the terms simple.

## What is welcome now

- New example scenarios in `scenarios/`, and improvements to documentation.
- Bug reports and small fixes. For anything touching the grammar, validator
  or engine, please open an issue first so we can agree the approach before
  you write code.

## Scenario requirements

- Illustrative data only. No confidential, client or third-party material.
- The specification must parse and validate with no errors and no warnings
  on the current release, and any tests you add must pass. Say which release
  you tested against.
- Include a short README in the scenario folder: what it models, which
  constructs it uses, and any limits of the current release it runs into.

Checking a specification (from the repository root, after
`pip install -r requirements.txt -r requirements-dev.txt`):

```bash
python -c "import sys; sys.path.insert(0,'toolchain'); from el_parser import parse; r = parse('scenarios/<folder>/<spec>.el'); print(r.ok, r.errors, r.warnings)"
python -m pytest -q tests/<your_test_file>.py
```

## Licence and sign-off

- Contributions are licensed under the repository's MIT licence, the same
  terms as the rest of the project. You keep your copyright.
- Sign off each commit (`git commit -s`) to confirm the Developer
  Certificate of Origin (https://developercertificate.org): that you wrote
  the contribution, or have the right to submit it under this licence.
- If you contribute as part of your work, please confirm that your employer
  agrees to the contribution before you submit it.

## Review

The maintainer reviews contributions and may ask for changes, hold a
contribution for a later release, or decline it. Acceptance creates no
obligation in either direction beyond the licence above.
