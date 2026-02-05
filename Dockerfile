# syntax=docker/dockerfile:1
FROM python:3.13-slim

# Basic runtime env (helps interactive TUIs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TERM=xterm-256color

WORKDIR /app

# System deps (git is needed because gitex uses GitPython repo checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install your package
COPY pyproject.toml README.md requirements.txt /app/
COPY gitex /app/gitex

RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir .

# Default working dir when users mount repos
WORKDIR /work

ENTRYPOINT ["gitex"]
