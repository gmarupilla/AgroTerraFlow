# Autonomous routine outputs

Outputs of scheduled Claude routines (registered via `/schedule`) that run on cron without an interactive session. Tracks the research-impact metrics that JOSS editors weighed when rejecting [openjournals/joss-reviews#10686](https://github.com/openjournals/joss-reviews/issues/10686).

## Files

| File | Routine | Cadence | Notes |
|------|---------|---------|-------|
| `metrics.csv` | #1 Adoption metrics scan | Weekly, Mon 09:00 CDT | Append-only. One row per Monday. |
| `joss-bar.md` | #2 JOSS pulse | Weekly, Wed 09:00 CDT | Overwrite — captures the moving JOSS-acceptance bar. |
| `ecosystem-YYYY-MM-DD.md` | #3 Ecosystem watch | Weekly, Fri 09:00 CDT | One file per Friday — upstream commit/issue scan. |
| `monthly-review-YYYY-MM.md` | #4 Roadmap reconciliation | Monthly, 1st | Diff vs. Part-6 plan. Activates after Part 6 ships. |
| `gate-day90.md`, `gate-day180.md` | #5/#6 Gate checks | One-time | GO / NO-GO / EXTEND-3-MONTHS recommendations. |

## Guardrails

Per plan §C:

1. **Commit budget:** ≤1 file per routine run.
2. **Halt-on-stale:** routine pauses + opens a GH issue comment after 4 consecutive no-change runs.
3. **Read-only against code:** routines never touch `terraflow/*.py`.
4. **No external posts:** never comment on the JOSS issue, never post to third-party repos.
5. **Cost cap:** ≤10k tokens/run (monthly review excepted).

## metrics.csv schema

| Column | Source | Notes |
|--------|--------|-------|
| `date` | run date | ISO YYYY-MM-DD |
| `stars` | GitHub API | snapshot |
| `forks` | GitHub API | snapshot |
| `contributors` | GitHub API | unique authors all-time |
| `unique_commenters_nonmaintainer` | GitHub API | issue + PR comments excluding @gmarupilla, bots |
| `open_issues` | GitHub API | excludes PRs |
| `open_prs` | GitHub API | |
| `merged_prs_external` | GitHub API | PRs merged from non-maintainer authors |
| `pypi_downloads_30d` | pypistats API | rolling 30-day for `terraflow-agro` |
| `crossref_citations` | Crossref API | citations of TerraFlow Zenodo/JOSS DOI (0 until DOI minted) |
| `code_search_imports` | GitHub code-search | distinct repos containing `import terraflow` (excluding self) |

Final schema decided in Part 4 (#125). This file may extend then.
