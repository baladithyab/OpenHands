# Development Sandbox Architecture

## Overview

This proposal outlines improvements to the development sandbox containers for OpenHands, focusing on developer experience, model development, and testing environments.

```
┌──────────────────────────────────────────────────────────────┐
│                   Development Sandboxes                      │
├──────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐   │
│  │   Base      │   │   Model     │   │    Testing      │   │
│  │  Sandbox    │   │   Dev       │   │    Sandbox      │   │
│  └──────┬──────┘   └──────┬──────┘   └───────┬─────────┘   │
│         │                 │                   │             │
│  ┌──────┴──────┐   ┌─────┴─────┐   ┌────────┴──────────┐  │
│  │   OLLAMA    │   │  PyTorch   │   │     Browser      │  │
│  │   Tools     │   │   Tools    │   │     Tools        │  │
│  └──────┬──────┘   └─────┬─────┘   └────────┬──────────┘  │
│         │                 │                   │             │
│  ┌──────┴──────┐   ┌─────┴─────┐   ┌────────┴──────────┐  │
│  │  Dev Tools  │   │  Model     │   │    Test           │  │
│  │  & Utils    │   │  Registry  │   │    Runners        │  │
│  └─────────────┘   └───────────┘   └─────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Container Types

### 1. Base Development Sandbox

```dockerfile
# base-sandbox.dockerfile
FROM ubuntu:22.04 as base

# Essential development tools
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    git-lfs \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    nodejs \
    npm \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Development utilities
RUN apt-get update && apt-get install -y \
    ripgrep \
    fd-find \
    jq \
    htop \
    tmux \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Python tools
RUN pip install --no-cache-dir \
    poetry \
    black \
    isort \
    mypy \
    pytest

# Node.js tools
RUN npm install -g \
    typescript \
    prettier \
    eslint

WORKDIR /workspace
```

### 2. Model Development Sandbox

```dockerfile
# model-dev.dockerfile
FROM base-sandbox as model-dev

# CUDA and GPU support
RUN apt-get update && apt-get install -y \
    nvidia-container-toolkit \
    && rm -rf /var/lib/apt/lists/*

# ML development tools
RUN pip install --no-cache-dir \
    torch \
    torchvision \
    transformers \
    datasets \
    accelerate \
    tensorboard

# OLLAMA integration
RUN curl -fsSL https://ollama.com/install.sh | sh

# Model development utilities
COPY ./scripts/model-utils /usr/local/bin/
RUN chmod +x /usr/local/bin/model-*

WORKDIR /workspace/models
```

### 3. Testing Sandbox

```dockerfile
# test-sandbox.dockerfile
FROM base-sandbox as test-sandbox

# Browser testing tools
RUN apt-get update && apt-get install -y \
    chromium-browser \
    firefox \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Testing frameworks
RUN pip install --no-cache-dir \
    pytest \
    pytest-xdist \
    pytest-cov \
    selenium \
    playwright

# Install browser drivers
RUN playwright install chromium firefox

WORKDIR /workspace/tests
```

## Development Tools

### 1. Model Development Tools

```bash
# model-utils/model-test
#!/bin/bash
set -e

function run_tests() {
    pytest tests/models \
        --cov=models \
        --cov-report=html \
        --cov-report=term
}

function run_benchmarks() {
    python benchmarks/run.py \
        --model $1 \
        --batch-size $2 \
        --iterations $3
}

case "$1" in
    "test") run_tests ;;
    "bench") run_benchmarks $2 $3 $4 ;;
    *) echo "Unknown command" ;;
esac
```

### 2. OLLAMA Integration Tools

```bash
# model-utils/ollama-setup
#!/bin/bash
set -e

function setup_model() {
    ollama pull $1
    ollama create $2 -f Modelfile
}

function run_model() {
    ollama run $1 --gpu
}

case "$1" in
    "setup") setup_model $2 $3 ;;
    "run") run_model $2 ;;
    *) echo "Unknown command" ;;
esac
```

## Development Workflow

### 1. Local Development

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  dev:
    build:
      context: .
      dockerfile: containers/base-sandbox.dockerfile
    volumes:
      - .:/workspace
      - ~/.gitconfig:/root/.gitconfig
      - ~/.ssh:/root/.ssh
    environment:
      - PYTHONPATH=/workspace
      - NODE_ENV=development
    ports:
      - "3000:3000"
      - "8000:8000"

  model-dev:
    build:
      context: .
      dockerfile: containers/model-dev.dockerfile
    volumes:
      - .:/workspace
      - ~/.cache/huggingface:/root/.cache/huggingface
      - ~/.cache/torch:/root/.cache/torch
    environment:
      - CUDA_VISIBLE_DEVICES=all
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  test:
    build:
      context: .
      dockerfile: containers/test-sandbox.dockerfile
    volumes:
      - .:/workspace
    environment:
      - DISPLAY=:99
      - PYTEST_ADDOPTS="--color=yes"
```

### 2. CI/CD Integration

```yaml
# .github/workflows/test-sandboxes.yml
name: Test Development Sandboxes

on:
  push:
    paths:
      - 'containers/**'
      - '.github/workflows/test-sandboxes.yml'

jobs:
  test-sandboxes:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        sandbox: [base, model-dev, test]

    steps:
      - uses: actions/checkout@v4
      
      - name: Build sandbox
        run: |
          docker build \
            -f containers/${{ matrix.sandbox }}-sandbox.dockerfile \
            -t openhands-${{ matrix.sandbox }} .

      - name: Test sandbox
        run: |
          docker run --rm openhands-${{ matrix.sandbox }} \
            bash -c "/version.sh && make test"
```

## Best Practices

1. Container Organization:
- Keep base image minimal
- Layer dependencies efficiently
- Use multi-stage builds
- Cache development tools

2. Development Environment:
- Mount source code as volume
- Share configuration files
- Enable hot reloading
- Preserve cache directories

3. Testing Strategy:
- Isolated test environments
- Reproducible test runs
- Coverage reporting
- Performance benchmarks

4. Resource Management:
- GPU access control
- Memory limits
- Cache management
- Network configuration

## Implementation Plan

### Phase 1: Base Setup (Week 1)
1. Create base sandbox
2. Add development tools
3. Configure volumes
4. Test basic workflow

### Phase 2: Model Development (Week 2)
1. Set up GPU support
2. Add ML tools
3. Configure OLLAMA
4. Test model workflows

### Phase 3: Testing Environment (Week 3)
1. Set up test sandbox
2. Add browser support
3. Configure test runners
4. Implement CI/CD

## Recommendations

1. Development Workflow:
- Use docker-compose for local dev
- Mount source code and configs
- Enable live reload
- Share GPU resources

2. Testing Strategy:
- Isolated test environments
- Parallel test execution
- Coverage reporting
- Performance metrics

3. Resource Management:
- GPU sharing
- Memory limits
- Cache optimization
- Network access

4. Tool Integration:
- VSCode integration
- Debugger support
- Linting/formatting
- Git hooks

## Next Steps

1. Create Base Images:
- Build base sandbox
- Add development tools
- Test basic functionality
- Document usage

2. Model Development:
- Add GPU support
- Configure OLLAMA
- Test model workflows
- Add utilities

3. Testing Setup:
- Configure test runners
- Add browser support
- Set up CI/CD
- Add benchmarks

4. Documentation:
- Setup guides
- Best practices
- Troubleshooting
- Examples