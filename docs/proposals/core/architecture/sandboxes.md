# Ansible-Based Development Sandboxes

## Overview

This proposal outlines an Ansible-based approach for creating and managing development sandboxes, focusing on flexibility and OS-agnostic configuration.

```
┌──────────────────────────────────────────────────────────────┐
│                   Sandbox Architecture                       │
├──────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐   │
│  │  Ansible    │   │  Container  │   │    Recipe       │   │
│  │  Playbooks  │   │  Builder    │   │    Registry     │   │
│  └──────┬──────┘   └──────┬──────┘   └───────┬─────────┘   │
│         │                 │                   │             │
│  ┌──────┴──────┐   ┌─────┴─────┐   ┌────────┴──────────┐  │
│  │  Role       │   │ Environment│   │    Sandbox        │  │
│  │  Library    │   │  Manager   │   │    Manager        │  │
│  └──────┬──────┘   └─────┬─────┘   └────────┬──────────┘  │
│         │                 │                   │             │
│  ┌──────┴──────┐   ┌─────┴─────┐   ┌────────┴──────────┐  │
│  │  Custom     │   │ Community  │   │    Testing        │  │
│  │  Roles      │   │  Recipes   │   │    Framework      │  │
│  └─────────────┘   └───────────┘   └─────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Base Ansible Structure

```yaml
# ansible/
├── inventory/
│   ├── group_vars/
│   │   └── all.yml
│   └── hosts.yml
├── roles/
│   ├── common/
│   ├── python/
│   ├── nodejs/
│   ├── rust/
│   └── ollama/
└── playbooks/
    ├── setup.yml
    ├── sandbox.yml
    └── cleanup.yml
```

### 2. Base Role Configuration

```yaml
# roles/common/tasks/main.yml
---
- name: Install common packages
  package:
    name: "{{ item }}"
    state: present
  loop:
    - git
    - curl
    - wget
    - build-essential
    - docker.io
    - python3-pip
    - nodejs
    - npm

- name: Configure Docker
  docker_container:
    name: sandbox
    image: "{{ sandbox_image }}"
    state: started
    volumes:
      - "{{ workspace_dir }}:/workspace"
    env:
      WORKSPACE_DIR: "/workspace"
      SANDBOX_TYPE: "{{ sandbox_type }}"

- name: Setup development tools
  pip:
    name:
      - docker-compose
      - pytest
      - black
      - mypy
    state: present
```

### 3. Language-Specific Roles

```yaml
# roles/python/tasks/main.yml
---
- name: Set up Python environment
  block:
    - name: Install Python tools
      pip:
        name:
          - poetry
          - virtualenv
          - jupyterlab
        state: present

    - name: Configure Poetry
      command: poetry config virtualenvs.in-project true

    - name: Initialize Python project
      command: poetry init --name="{{ project_name }}" --quiet
      args:
        chdir: "{{ workspace_dir }}"
        creates: "{{ workspace_dir }}/pyproject.toml"

# roles/nodejs/tasks/main.yml
---
- name: Set up Node.js environment
  block:
    - name: Install Node.js tools
      npm:
        name: "{{ item }}"
        global: yes
      loop:
        - typescript
        - ts-node
        - prettier
        - eslint

    - name: Initialize Node.js project
      command: npm init -y
      args:
        chdir: "{{ workspace_dir }}"
        creates: "{{ workspace_dir }}/package.json"

# roles/ollama/tasks/main.yml
---
- name: Set up OLLAMA environment
  block:
    - name: Install OLLAMA
      shell: curl https://ollama.ai/install.sh | sh
      args:
        creates: /usr/local/bin/ollama

    - name: Configure OLLAMA
      copy:
        dest: "{{ workspace_dir }}/Modelfile"
        content: |
          FROM {{ model_name }}
          PARAMETER temperature {{ temperature | default(0.7) }}
          PARAMETER top_p {{ top_p | default(0.9) }}

    - name: Pull model
      command: ollama pull {{ model_name }}
```

### 4. Sandbox Creation Playbook

```yaml
# playbooks/sandbox.yml
---
- name: Create development sandbox
  hosts: localhost
  vars:
    sandbox_type: "{{ sandbox_type | default('python') }}"
    workspace_dir: "{{ workspace_dir | default('/workspace') }}"
    project_name: "{{ project_name | default('sandbox-project') }}"
  
  pre_tasks:
    - name: Validate inputs
      assert:
        that:
          - sandbox_type in ['python', 'nodejs', 'rust', 'ollama']
        msg: "Invalid sandbox type specified"

  roles:
    - common
    - "{{ sandbox_type }}"

  tasks:
    - name: Configure sandbox environment
      block:
        - name: Create workspace directory
          file:
            path: "{{ workspace_dir }}"
            state: directory
            mode: '0755'

        - name: Copy configuration files
          template:
            src: "templates/{{ item }}.j2"
            dest: "{{ workspace_dir }}/{{ item }}"
          loop:
            - .gitignore
            - README.md
            - docker-compose.yml

        - name: Initialize Git repository
          command: git init
          args:
            chdir: "{{ workspace_dir }}"
            creates: "{{ workspace_dir }}/.git"

    - name: Set up development container
      docker_compose:
        project_src: "{{ workspace_dir }}"
        state: present
```

### 5. Environment Templates

```yaml
# templates/docker-compose.yml.j2
version: '3.8'

services:
  sandbox:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        SANDBOX_TYPE: {{ sandbox_type }}
    volumes:
      - .:/workspace
      - ~/.gitconfig:/root/.gitconfig
      - ~/.ssh:/root/.ssh
    environment:
      - SANDBOX_TYPE={{ sandbox_type }}
      {% if sandbox_type == 'ollama' %}
      - OLLAMA_MODEL={{ model_name | default('llama2') }}
      - OLLAMA_HOST=0.0.0.0
      {% endif %}
    ports:
      - "8000:8000"  # API
      - "8888:8888"  # Jupyter
      {% if sandbox_type == 'ollama' %}
      - "11434:11434"  # OLLAMA
      {% endif %}
```

### 6. Custom Recipe Format

```yaml
# recipes/custom-recipe.yml
name: custom-environment
description: Custom development environment
version: 1.0.0

base:
  type: python
  version: "3.12"

ansible:
  roles:
    - common
    - python
    - custom-tools

  vars:
    project_name: custom-project
    python_packages:
      - numpy
      - pandas
      - scikit-learn
    
  tasks:
    - name: Install custom tools
      package:
        name: "{{ item }}"
        state: present
      loop:
        - vim
        - tmux
        - ripgrep

docker:
  base_image: python:3.12-slim
  ports:
    - "8000:8000"
    - "8888:8888"
  volumes:
    - .:/workspace
  environment:
    - PYTHONPATH=/workspace
    - JUPYTER_ENABLE_LAB=yes
```

### 7. Sandbox Manager Script

```python
#!/usr/bin/env python3

import argparse
import subprocess
import yaml
from pathlib import Path

class SandboxManager:
    def __init__(self):
        self.workspace_dir = Path.home() / 'sandboxes'
        self.workspace_dir.mkdir(exist_ok=True)

    def create_sandbox(self, name: str, recipe: str = None):
        sandbox_dir = self.workspace_dir / name
        sandbox_dir.mkdir(exist_ok=True)

        # Load recipe if provided
        if recipe:
            with open(recipe) as f:
                recipe_data = yaml.safe_load(f)
        else:
            recipe_data = {'base': {'type': 'python'}}

        # Run Ansible playbook
        subprocess.run([
            'ansible-playbook',
            'playbooks/sandbox.yml',
            '-e', f'sandbox_type={recipe_data["base"]["type"]}',
            '-e', f'workspace_dir={sandbox_dir}',
            '-e', f'project_name={name}'
        ], check=True)

    def list_sandboxes(self):
        return [d.name for d in self.workspace_dir.iterdir() if d.is_dir()]

    def delete_sandbox(self, name: str):
        sandbox_dir = self.workspace_dir / name
        if sandbox_dir.exists():
            subprocess.run([
                'ansible-playbook',
                'playbooks/cleanup.yml',
                '-e', f'workspace_dir={sandbox_dir}'
            ], check=True)
            sandbox_dir.rmdir()

def main():
    parser = argparse.ArgumentParser(description='Sandbox Manager')
    parser.add_argument('command', choices=['create', 'list', 'delete'])
    parser.add_argument('--name', help='Sandbox name')
    parser.add_argument('--recipe', help='Recipe file')
    args = parser.parse_args()

    manager = SandboxManager()

    if args.command == 'create':
        manager.create_sandbox(args.name, args.recipe)
    elif args.command == 'list':
        print('\n'.join(manager.list_sandboxes()))
    elif args.command == 'delete':
        manager.delete_sandbox(args.name)

if __name__ == '__main__':
    main()
```

## Implementation Plan

### Phase 1: Core Setup (Week 1)
1. Set up Ansible structure
2. Create base roles
3. Implement sandbox playbook
4. Add basic testing

### Phase 2: Language Support (Week 2)
1. Add Python environment
2. Add Node.js support
3. Add Rust toolchain
4. Add OLLAMA integration

### Phase 3: Recipe System (Week 3)
1. Create recipe format
2. Add recipe parsing
3. Implement validation
4. Add documentation

### Phase 4: Testing (Week 4)
1. Add test framework
2. Create test cases
3. Add CI/CD
4. Performance testing

## Best Practices

1. Role Organization:
- Keep roles focused
- Use dependencies
- Version control
- Documentation

2. Recipe Management:
- Clear format
- Version control
- Validation
- Testing

3. Development Workflow:
- Consistent environments
- Easy setup
- Quick iteration
- Good documentation

4. Testing Strategy:
- Unit tests
- Integration tests
- Performance tests
- Security checks

## Recommendations

1. Development Setup:
- Use Docker for isolation
- Ansible for configuration
- Clear documentation
- Easy customization

2. Recipe System:
- Simple format
- Version control
- Validation
- Sharing mechanism

3. Testing:
- Automated tests
- CI/CD integration
- Performance metrics
- Security scanning

4. Documentation:
- Setup guides
- Best practices
- Examples
- Troubleshooting

## Next Steps

1. Core Implementation:
- Set up Ansible
- Create base roles
- Add sandbox manager
- Write documentation

2. Language Support:
- Add Python role
- Add Node.js role
- Add Rust role
- Add OLLAMA role

3. Recipe System:
- Create format
- Add parser
- Add validation
- Add examples

4. Testing:
- Set up framework
- Add test cases
- Configure CI/CD
- Add metrics