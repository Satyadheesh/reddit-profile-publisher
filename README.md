# SatyaDheesh Reddit Profile Publisher

This repository contains the small, transparent publishing layer for the official
`u/SatyaDheesh` Reddit profile.

It is deliberately separate from the SatyaDheesh news, study, Telegram and
Instagram pipelines. Its sole job is to publish a limited number of factual,
original updates about SatyaDheesh and its public-information work.

## What it does

- publishes **at most one text post per day** to the official profile;
- builds each post from an approved capability registry;
- marks every claim as `live`, `building`, or `vision`;
- rejects a draft with unknown claims or duplicate content;
- keeps an auditable local ledger of submitted post IDs and timestamps.

## What it does not do

- post to third-party communities;
- comment, vote, follow users, send direct messages, or create accounts;
- scrape private or non-public Reddit data;
- use engagement metrics to alter publishing behaviour;
- publish unless explicitly invoked with `--publish`.

## Safety model

The text generator is not treated as a source of truth. It may propose a draft,
but a draft can only cite IDs present in [`content/capabilities.json`](content/capabilities.json).
The publisher checks the claim IDs, their publication status, a daily limit and
the post-content hash before it reaches Reddit.

## API access

This project is intended for Reddit Data API access after approval under
Reddit's Responsible Builder Policy. It uses OAuth and identifies itself with a
descriptive User-Agent. Do not run it with browser automation or use it to
circumvent Reddit limits.

Set these repository secrets only after API approval:

```text
REDDIT_CLIENT_ID
REDDIT_CLIENT_SECRET
REDDIT_USERNAME
REDDIT_PASSWORD
```

Set the repository variable `REDDIT_PUBLISH_ENABLED` to `true` only after a
successful dry run and an initial manual test. The scheduled workflow remains a
dry run otherwise.

## Local use

```bash
python -m pip install -r requirements.txt
python -m publisher --dry-run
python -m publisher --publish
```

`--publish` needs all four Reddit secrets. The default and `--dry-run` never
make a network request to Reddit.

## Content workflow

1. Add a reviewed draft to `content/drafts.json`.
2. Give it an ID, date, title, body and a list of registry claim IDs.
3. Run a dry run.
4. The daily workflow publishes the first due, unposted draft only when the
   explicit repository variable is enabled.

The initial drafts are examples, not a claim that every feature is presently
available. Keep the registry current when the underlying product changes.
