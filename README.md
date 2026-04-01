# pjobs

A CLI tool to find product leadership job listings directly from ATS platforms — roles that often never make it to LinkedIn or Indeed.

Searches **Ashby**, **Lever**, and **Greenhouse** for titles like VP of Product, Head of Product, Director of Product, and more.

## Install

```bash
pip install -e .
```

Then add `~/.local/bin` to your PATH if it isn't already:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

## Usage

```bash
# Search using your configured default titles
pjobs search

# Search for a specific title
pjobs search "Chief Product Officer"

# Only show listings from the last 24 hours (great for daily runs)
pjobs search --since 24h

# Combine title + time window
pjobs search "Head of Product" --since 7d

# Open your config file
pjobs config

# See which sources are active
pjobs sources
```

## Config

Config lives at `~/.jobs/config.yaml` and is created automatically on first run.

```yaml
titles:
  - VP of Product
  - VP Product
  - Head of Product
  - Director of Product
  - Chief Product Officer

sources:
  - ashby
  - lever
  - greenhouse

# Optional: add a SerpAPI key for more reliable results (~100 free searches/month)
# Sign up at https://serpapi.com
serpapi_key: null
```

Edit it with:

```bash
pjobs config
```

## How it works

`pjobs` queries Google for job listings hosted directly on ATS platforms, bypassing the aggregators. Most companies post to their own Ashby, Lever, or Greenhouse board without syndicating to LinkedIn — especially at the VP/Director level where they prefer direct inbound.

By default it uses `googlesearch-python` (no API key needed, rate-limited for personal use). For heavier use, add a SerpAPI key to your config.

## Daily habit

Add a shell alias for your morning routine:

```bash
alias standup="pjobs search --since 24h"
```
