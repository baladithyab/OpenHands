# Modular Development Sandboxes

## Overview

This proposal outlines a modular sandbox system using Nix and Ansible for creating customizable development environments.

```
┌──────────────────────────────────────────────────────────────┐
│                   Sandbox Factory System                     │
├──────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐   │
│  │    Nix      │   │  Ansible    │   │   Container     │   │
│  │   Flakes    │   │  Playbooks  │   │    Registry     │   │
│  └──────┬──────┘   └──────┬──────┘   └───────┬─────────┘   │
│         │                 │                   │             │
│  ┌──────┴──────┐   ┌─────┴─────┐   ┌────────┴──────────┐  │
│  │   Base      │   │ Language   │   │    Tool           │  │
│  │  Images     │   │  Stacks    │   │    Chains         │  │
│  └──────┬──────┘   └─────┬─────┘   └────────┬──────────┘  │
│         │                 │                   │             │
│  ┌──────┴──────┐   ┌─────┴─────┐   ┌────────┴──────────┐  │
│  │  Custom     │   │ Community  │   │    Sandbox        │  │
│  │  Sandboxes  │   │  Recipes   │   │    Manager        │  │
│  └─────────────┘   └───────────┘   └─────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Base System

### 1. Nix Base Configuration

```nix
# flake.nix
{
  description = "OpenHands Development Sandboxes";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells = {
          base = pkgs.mkShell {
            buildInputs = with pkgs; [
              git
              curl
              wget
              jq
              ripgrep
              fd
            ];
          };

          python = pkgs.mkShell {
            buildInputs = with pkgs; [
              python312
              poetry
              black
              mypy
              pytest
            ];
          };

          nodejs = pkgs.mkShell {
            buildInputs = with pkgs; [
              nodejs_20
              yarn
              typescript
              nodePackages.prettier
              nodePackages.eslint
            ];
          };

          rust = pkgs.mkShell {
            buildInputs = with pkgs; [
              rustc
              cargo
              rustfmt
              clippy
              rust-analyzer
            ];
          };
        };
      }
    );
}
```

### 2. Ansible Base Playbook

```yaml
# base-playbook.yml
---
- name: Configure base sandbox environment
  hosts: all
  become: yes
  vars:
    sandbox_user: developer
    sandbox_home: /home/developer

  tasks:
    - name: Create sandbox user
      user:
        name: "{{ sandbox_user }}"
        shell: /bin/bash
        create_home: yes

    - name: Install base packages
      package:
        name:
          - build-essential
          - git
          - curl
          - wget
          - vim
          - tmux
        state: present

    - name: Configure git
      git_config:
        name: "{{ item.name }}"
        value: "{{ item.value }}"
        scope: global
      loop:
        - { name: 'core.editor', value: 'vim' }
        - { name: 'pull.rebase', value: 'false' }
```

## Language-Specific Configurations

### 1. Python Development Environment

```nix
# python-dev.nix
{ pkgs ? import <nixpkgs> {} }:

let
  pythonEnv = pkgs.python312.withPackages (ps: with ps; [
    # Core development
    pip
    poetry
    virtualenv
    
    # Development tools
    black
    mypy
    pylint
    pytest
    pytest-cov
    
    # Data science & ML
    numpy
    pandas
    torch
    transformers
    
    # Web development
    flask
    fastapi
    uvicorn
  ]);
in
pkgs.mkShell {
  buildInputs = [
    pythonEnv
    pkgs.poetry
    pkgs.pre-commit
  ];

  shellHook = ''
    export PYTHONPATH="$PWD:$PYTHONPATH"
    export POETRY_VIRTUALENVS_IN_PROJECT=true
  '';
}
```

### 2. Node.js/TypeScript Environment

```nix
# nodejs-dev.nix
{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    nodejs_20
    yarn
    nodePackages.typescript
    nodePackages.ts-node
    nodePackages.prettier
    nodePackages.eslint
    nodePackages.jest
    nodePackages.webpack
    nodePackages.webpack-cli
  ];

  shellHook = ''
    export PATH="$PWD/node_modules/.bin:$PATH"
    export NODE_ENV=development
  '';
}
```

## Sandbox Manager

### 1. Sandbox Configuration

```yaml
# sandbox-config.yaml
version: "1.0"
sandboxes:
  python-ml:
    base: python
    nix_file: python-dev.nix
    ansible_playbook: python-ml-setup.yml
    tools:
      - jupyter
      - pytorch
      - transformers
    gpu: true

  web-dev:
    base: nodejs
    nix_file: nodejs-dev.nix
    ansible_playbook: web-dev-setup.yml
    tools:
      - react
      - next
      - vite
    ports:
      - "3000:3000"
      - "5173:5173"

  rust-dev:
    base: rust
    nix_file: rust-dev.nix
    ansible_playbook: rust-setup.yml
    tools:
      - cargo-watch
      - cargo-edit
      - wasm-pack
```

### 2. Sandbox Creation Script

```python
#!/usr/bin/env python3

import argparse
import subprocess
import yaml
from pathlib import Path

class SandboxManager:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.sandbox_dir = Path.home() / '.sandboxes'
        self.sandbox_dir.mkdir(exist_ok=True)

    def _load_config(self, path: str) -> dict:
        with open(path) as f:
            return yaml.safe_load(f)

    def create_sandbox(self, name: str, sandbox_type: str):
        if sandbox_type not in self.config['sandboxes']:
            raise ValueError(f"Unknown sandbox type: {sandbox_type}")

        sandbox_config = self.config['sandboxes'][sandbox_type]
        sandbox_path = self.sandbox_dir / name

        # Create sandbox directory
        sandbox_path.mkdir(exist_ok=True)

        # Apply Nix configuration
        self._apply_nix_config(sandbox_path, sandbox_config)

        # Run Ansible playbook
        self._run_ansible_playbook(sandbox_path, sandbox_config)

        # Install additional tools
        self._install_tools(sandbox_path, sandbox_config)

    def _apply_nix_config(self, path: Path, config: dict):
        nix_file = config['nix_file']
        subprocess.run(['nix-shell', nix_file], cwd=path, check=True)

    def _run_ansible_playbook(self, path: Path, config: dict):
        playbook = config['ansible_playbook']
        subprocess.run([
            'ansible-playbook',
            playbook,
            '-i', 'localhost,',
            '--connection=local'
        ], cwd=path, check=True)

    def _install_tools(self, path: Path, config: dict):
        for tool in config.get('tools', []):
            subprocess.run(['nix-env', '-iA', tool], cwd=path, check=True)

def main():
    parser = argparse.ArgumentParser(description='Sandbox Manager')
    parser.add_argument('command', choices=['create', 'list', 'delete'])
    parser.add_argument('--name', help='Sandbox name')
    parser.add_argument('--type', help='Sandbox type')
    args = parser.parse_args()

    manager = SandboxManager('sandbox-config.yaml')

    if args.command == 'create':
        manager.create_sandbox(args.name, args.type)
    elif args.command == 'list':
        manager.list_sandboxes()
    elif args.command == 'delete':
        manager.delete_sandbox(args.name)

if __name__ == '__main__':
    main()
```

## Community Recipes

### 1. Recipe Format

```yaml
# recipe-format.yaml
name: custom-recipe
description: Custom development environment
author: username
version: 1.0.0

base:
  type: python
  version: "3.12"

nix:
  packages:
    - name: package1
      version: "1.0"
    - name: package2
      version: "2.0"
  
  environment:
    - name: ENV_VAR1
      value: value1
    - name: ENV_VAR2
      value: value2

ansible:
  playbooks:
    - setup.yml
    - configure.yml
  
  roles:
    - role1
    - role2

tools:
  - name: tool1
    version: "1.0"
  - name: tool2
    version: "2.0"
```

### 2. Recipe Registry

```python
# recipe_registry.py
import requests
import yaml
from pathlib import Path

class RecipeRegistry:
    def __init__(self):
        self.registry_url = "https://registry.openhands.dev"
        self.local_cache = Path.home() / '.openhands' / 'recipes'
        self.local_cache.mkdir(parents=True, exist_ok=True)

    def search_recipes(self, query: str) -> list:
        response = requests.get(
            f"{self.registry_url}/recipes/search",
            params={'q': query}
        )
        return response.json()

    def download_recipe(self, name: str, version: str) -> Path:
        cache_path = self.local_cache / f"{name}-{version}.yaml"
        
        if not cache_path.exists():
            response = requests.get(
                f"{self.registry_url}/recipes/{name}/{version}"
            )
            with open(cache_path, 'w') as f:
                yaml.dump(response.json(), f)
        
        return cache_path

    def publish_recipe(self, recipe_path: Path):
        with open(recipe_path) as f:
            recipe = yaml.safe_load(f)
        
        response = requests.post(
            f"{self.registry_url}/recipes",
            json=recipe
        )
        return response.json()
```

## Implementation Plan

### Phase 1: Core System (Week 1-2)
1. Set up Nix configurations
2. Create base Ansible playbooks
3. Implement sandbox manager
4. Test basic functionality

### Phase 2: Language Support (Week 2-3)
1. Add Python environment
2. Add Node.js environment
3. Add Rust environment
4. Test language-specific features

### Phase 3: Community Features (Week 3-4)
1. Create recipe format
2. Set up recipe registry
3. Add recipe management
4. Test recipe sharing

## Best Practices

1. Sandbox Creation:
- Use declarative configurations
- Keep base images minimal
- Enable reproducibility
- Support customization

2. Development Workflow:
- Consistent environments
- Easy tool installation
- Project isolation
- Resource management

3. Community Engagement:
- Clear recipe format
- Easy sharing mechanism
- Version control
- Documentation

4. Maintenance:
- Regular updates
- Security patches
- Dependency management
- Clean-up procedures

## Recommendations

1. Development Setup:
- Use Nix for reproducibility
- Ansible for configuration
- Container isolation
- Tool management

2. Language Support:
- Specific toolchains
- Development utilities
- Testing frameworks
- Debugging tools

3. Community Features:
- Recipe sharing
- Version control
- Documentation
- Support channels

4. Resource Management:
- Container limits
- Cache management
- Network access
- Storage optimization

## Next Steps

1. Core Implementation:
- Set up Nix system
- Create base playbooks
- Build sandbox manager
- Add basic recipes

2. Language Support:
- Python environment
- Node.js environment
- Rust environment
- Testing tools

3. Community Features:
- Recipe format
- Registry system
- Documentation
- Examples