# Profile metrics

The README loads six SVGs committed to this repository. A matching accessible
[plain-text summary](../profile/summary.md) contains the real numbers and public
activity text extracted from those same SVGs. Visitors do not call a
third-party stats endpoint. The daily workflow fetches real data from GitHub,
renders into a staging directory, and publishes a complete validated batch.

## Schedule and manual refresh

`.github/workflows/magic.yml` runs once a day at **03:37 UTC** and through
**Actions → Update profile metrics → Run workflow**. The daily schedule operates
on the default branch after merge. GitHub may delay scheduled runs. Public
repository schedules can be disabled after 60 days without repository activity.

The `codex/loop-lab-profile` push trigger bootstraps the implementation branch
when the workflow or its validation scripts change. Generated SVG commits do
not match the trigger paths. No workflow modifies another repository.

## Integrations and credentials

| Component | What it adds | Account, credential, cost |
| --- | --- | --- |
| GitHub Actions / GitHub API | Daily updates and real account statistics | The existing GitHub account. The automatic, repository-scoped `GITHUB_TOKEN` is used for public stats and committing assets. Standard hosted runners are free for public repositories. No paid service is required. |
| GitHub Readme Stats Action | Local dark/light Stats and Top Languages cards | Runs inside GitHub Actions. No external hosting account or new secret. Uses the automatic `GITHUB_TOKEN`. |
| lowlighter/metrics | Isometric contribution calendar | Reuses the existing repository secret `METRICS_TOKEN`. A valid GitHub personal access token is needed; the public plugins do not require private-repository access. No payment or additional account. |

Recent public activity is fetched directly from GitHub's public Events API with the automatic token.
This small local collector accepts reduced event payloads without requiring
missing author, commit-array, or pull-request metadata. It adds no service, account,
secret, or payment. A fetch failure fails the complete refresh.

The former WakaTime settings and `WAKATIME_API_KEY` reference have been removed.
WakaTime is not needed or enabled. No secret values belong in files or SVGs.

The workflow checks that `METRICS_TOKEN` is present without logging its value.
If it has expired or been removed, replace that repository Actions secret with
a valid GitHub token. Public-only metrics need no broad private-repository
scope. Existing secrets are reused; the workflow does not create or change them.

## Meaning of the data

- **Stats** comes from the upstream GitHub Readme Stats core using GitHub's
  API. Commit and contribution labels retain their upstream time ranges;
  these are not claimed to be lifetime totals.
- **Top Languages** measures the language distribution in analyzed repositories.
  It does not measure proficiency, personal coding time, or all professional work.
  No language is hidden to manufacture a preferred result.
- **Isocalendar** uses GitHub's contribution calendar for the last year.
  Its aggregate counts can include private contributions accessible to the
  existing metrics token. Calendar bars do not disclose private project names.
  The upstream labels say “commits”; GitHub's underlying calendar counts
  contributions, which can also include issues, reviews, and pull requests.
- **Recent activity** explicitly uses public events only, excludes the profile
  repository and the common automation bots, and shows up to three qualifying
  events from the past 90 days. An empty event list is reported honestly.
- Both calendar themes are made from the same generated SVG. Theme conversion
  changes colors and accessibility descriptions, never counts or bar geometry.

No private repository, issue, or commit text is intentionally displayed by the
configured public activity collector. The token may have broader permissions from its
previous use; that does not enable private activity in this workflow.

## Preservation and validation

1. Generate all four stats cards in `.profile-stage/` with
   `fail_on_error: true`. A failed API request must fail the step.
2. Render metrics with `output_action: none` and
   `plugins_errors_fatal: yes`; lowlighter does not commit independently.
3. Fetch public activity, append it to both metrics themes, then validate all six SVGs as a batch: valid XML,
   measured dimensions, expected data fields, complete calendar, no error
   panels, executable elements, or externally loaded images/styles.
4. Derive the text summary from the validated data. Only then replace the published files. The publisher rolls back an
   interrupted local installation. A workflow failure before the final push
   leaves the last committed valid batch available to the README.
5. Commit only when the SVG or text-summary bytes changed. No “last checked” timestamp is
   inserted solely to force a daily commit. Push failures remain failures;
   they are not masked.

Branch-specific concurrency prevents simultaneous refreshes from overwriting
each other. If another commit advances the branch during a run, a normal push
can reject it safely; rerun the workflow against the latest branch.

Run the meaningful failure-retention tests locally with:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/profile_assets.py check --directory profile
```

Test fixtures are synthetic and used only inside tests. They are never copied
to the profile or used as a fallback for real API data.

## Upstream versions and credits

- [lowlighter/metrics](https://github.com/lowlighter/metrics), MIT:
  action pinned to `65836723097537a54cd8eb90f61839426b4266b6` (3.34.0).
  Its official prebuilt container follows the upstream 3.34 release channel.
- [GitHub Readme Stats Action](https://github.com/stats-organization/github-readme-stats-action),
  MIT: action pinned to `2c498845f71017821efaad14293ebc736156ef21`
  (v2.1.0), with its lockfile-pinned bundled core 2.2.0.
  This project builds on
  [GitHub Readme Stats](https://github.com/anuraghazra/github-readme-stats)
  and [GitHub Stats Extended](https://github.com/stats-organization/github-stats-extended).
- [actions/checkout](https://github.com/actions/checkout), MIT:
  pinned to `d23441a48e516b6c34aea4fa41551a30e30af803` (v6).
- The repository-local Stats/Top Languages delivery pattern is inspired by
  [david-lev/david-lev](https://github.com/david-lev/david-lev). Its visual design
  and content have not been copied.
- GitHub's [theme-aware picture markup](https://github.blog/developer-skills/github/how-to-make-your-images-in-markdown-on-github-adjust-for-dark-mode-and-light-mode/)
  selects the appropriate local SVGs.
