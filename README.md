# pjobs

A CLI tool to find product leadership job listings directly from ATS platforms — roles that often never make it to LinkedIn or Indeed.

Searches **Ashby**, **Lever**, and **Greenhouse** for titles like VP of Product, Head of Product, Director of Product, and more.

## Requirements

- Python 3.9+
- A free [SerpAPI](https://serpapi.com) account and API key (required for reliable search results)

SerpAPI's free tier includes ~100 searches/month, which is plenty for daily personal use. Without it, searches will likely return no results as Google blocks automated requests.

## Install

```bash
pip install -e .
```

Then add `~/.local/bin` to your PATH if it isn't already:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

## Setup

On first run, create your config file:

```bash
pjobs config
```

Add your SerpAPI key to `~/.jobs/config.yaml`:

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

serpapi_key: "your-key-here"
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

## How it works

`pjobs` queries Google (via SerpAPI) for job listings hosted directly on ATS platforms, bypassing the big aggregators. Most companies post to their own Ashby, Lever, or Greenhouse board without syndicating to LinkedIn — especially at the VP/Director level where they prefer direct inbound.

## Daily habit

Add a shell alias for your morning routine:

```bash
alias standup="pjobs search --since 24h"
```
