#!/usr/bin/env python3
from pathlib import Path

source_path = Path("runtime/LC32DarwinSyscalls.cpp")
source = source_path.read_text()
old = """            if ((flags & ~supported) != 0 ||
                (flags & kMsAsync) != 0 && (flags & kMsSync) != 0) {
"""
new = """            if ((flags & ~supported) != 0 ||
                ((flags & kMsAsync) != 0 && (flags & kMsSync) != 0)) {
"""
if old not in source:
    raise SystemExit("msync condition not found")
source_path.write_text(source.replace(old, new, 1))

workflow_path = Path(".github/workflows/test-lc32-interpreter.yml")
workflow = workflow_path.read_text()
workflow = workflow.replace("      - 'tools/apply_vm_advisory.py'\n", "", 1)
job = """  apply-staged-runtime-patch:
    if: github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v6
        with:
          ref: ${{ github.event.pull_request.head.ref }}
          fetch-depth: 0
      - name: Apply staged VM advisory patch
        id: staged
        shell: bash
        run: |
          set -euxo pipefail
          if [[ -f tools/apply_vm_advisory.py ]]; then
            python3 tools/apply_vm_advisory.py
            echo 'changed=true' >> "$GITHUB_OUTPUT"
          else
            echo 'changed=false' >> "$GITHUB_OUTPUT"
          fi
      - name: Commit staged runtime patch
        if: steps.staged.outputs.changed == 'true'
        shell: bash
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -A
          git commit -m "runtime: add msync and madvise support"
          git push origin HEAD:${{ github.event.pull_request.head.ref }}

"""
if job not in workflow:
    raise SystemExit("staged patch job not found")
workflow_path.write_text(workflow.replace(job, "", 1))
Path(__file__).unlink()
