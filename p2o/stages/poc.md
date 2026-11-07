# Your stage: reproduce under the sanitizer

Using the root cause in the verified facts above, produce an input file for the project's
fuzz target that makes the sanitizer report this vulnerability at (or reached through) the
location identified in the root-cause analysis.

Write:
- `{workspace}/poc.bin` — the input file.
- `{workspace}/poc_notes.md` — <= 100 words on how the input reaches the root cause.
- In `claim.json`, also set `"expected_crash_location": "<function where you expect the report>"`.

An independent checker will run your input in a clean copy of the original build and
compare the sanitizer report with the root-cause location. Do not patch the source in this stage.
