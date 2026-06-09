# Discord AI Code Review Bot

A production-ready Discord bot that reviews GitHub repositories with DeepSeek AI. It supports both prefix commands and modern slash commands, stores review history in SQLite, and can run on Render, Railway, Fly.io, or any Python worker host.

## Features

- Prefix command: `!review <github-url>`
- Slash command: `/review`
- User statistics: `!stats` and `/stats`
- Optional focus modes: `security` and `performance`
- GitHub API integration with optional personal access token support
- DeepSeek API integration through manual HTTP requests with `httpx`
- Per-user rate limiting: one review every 5 minutes
- SQLite persistence for users and review history
- Automatic database schema creation on startup
- Discord 2000-character handling with message splitting and Markdown file uploads
- Russian Discord responses for all user-facing bot messages
- Structured logging for review requests and failures

## Requirements

- Python 3.10+
- Discord bot token
- DeepSeek API key
- Optional GitHub personal access token

## Environment Variables

Create a `.env` file locally or configure these variables in your hosting provider:

```env
DISCORD_TOKEN=your_discord_token
DEEPSEEK_API_KEY=your_deepseek_key
GITHUB_TOKEN=optional_github_pat
```

`DISCORD_TOKEN` and `DEEPSEEK_API_KEY` are required. `GITHUB_TOKEN` is optional, but recommended to improve GitHub API rate limits.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Fill `.env` before starting the bot.

## Discord Setup

Enable the Message Content Intent in the Discord Developer Portal so prefix commands can work. Slash commands are synchronized automatically when the bot starts.

Required bot permissions:

- Send Messages
- Attach Files
- Use Slash Commands
- Read Message History

## Commands

```text
!review https://github.com/user/repository
!review https://github.com/user/repository --focus security
!review https://github.com/user/repository --focus performance
!stats
```

Slash commands:

```text
/review github_url:https://github.com/user/repository
/review github_url:https://github.com/user/repository focus:security
/review github_url:https://github.com/user/repository focus:performance
/stats
```

## Review Scope

The bot analyzes repositories with up to 30 supported code files.

Supported extensions:

- `.py`
- `.js`
- `.ts`
- `.html`
- `.css`
- `.go`
- `.rs`

If a repository contains more than 30 supported code files, the bot returns a Russian error message instead of starting the review.

## Architecture Overview

- `main.py` starts the application.
- `bot.py` contains Discord command registration and response delivery.
- `config.py` loads environment-based settings.
- `database.py` manages SQLite schema and review history.
- `github_client.py` retrieves repository metadata, file trees, and file contents through GitHub API.
- `deepseek_client.py` calls DeepSeek Chat Completions directly through `httpx`.
- `review_service.py` coordinates validation, GitHub retrieval, prompt creation, AI review, logging, and rate limiting.
- `rate_limiter.py` enforces per-user review cooldowns.
- `utils.py` contains URL parsing, argument parsing, chunking, and shared constants.
- `exceptions.py` defines application errors with Russian Discord messages.

## Deployment on Render

This repository includes `render.yaml` for a worker service.

1. Push the project to GitHub.
2. Create a new Render Blueprint or Worker service.
3. Configure environment variables:
   - `DISCORD_TOKEN`
   - `DEEPSEEK_API_KEY`
   - `GITHUB_TOKEN` if needed
4. Use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `python main.py`

## Deployment on Railway

1. Create a new Railway project from the GitHub repository.
2. Add environment variables in Railway.
3. Railway will install dependencies from `requirements.txt`.
4. Set the start command to:

```bash
python main.py
```

## Deployment on Fly.io

Create a Fly app and configure secrets:

```bash
fly launch
fly secrets set DISCORD_TOKEN=your_discord_token
fly secrets set DEEPSEEK_API_KEY=your_deepseek_key
fly secrets set GITHUB_TOKEN=optional_github_pat
```

Use a Python worker process that runs:

```bash
python main.py
```

## Operational Notes

- `reviews.db` is created automatically on startup.
- On ephemeral platforms, SQLite data may reset between deployments unless persistent storage is configured.
- The bot never hardcodes secrets.
- All Discord user-facing messages are written in Russian.
