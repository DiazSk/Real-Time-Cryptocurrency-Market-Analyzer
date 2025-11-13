# Git Workflow

This document describes the branching strategy and Git workflow for this project.

## Branching Strategy

This project uses a **simplified GitHub Flow** with feature branches:

### Branch Types

1. **`main`** - Production-ready code
   - Always stable and deployable
   - Tagged with semantic versions (v0.1.0, v0.2.0, etc.)
   - Protected branch - requires PR for changes

2. **`develop`** - Integration branch
   - Where features get merged before going to main
   - Should always build successfully
   - Weekly merges to main after testing

3. **`feature/*`** - Feature development
   - Created from `develop`
   - Naming: `feature/phase-description`
   - Examples:
     - `feature/phase2-kafka-setup`
     - `feature/phase3-flink-windowing`
     - `feature/phase4-rest-api`

4. **`hotfix/*`** - Emergency fixes
   - Created from `main` for critical bugs
   - Merged back to both `main` and `develop`
   - Example: `hotfix/docker-networking-fix`

---

## Workflow

### Starting a New Feature

```bash
# Update develop branch
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/phase2-kafka-setup

# Work on your feature
git add .
git commit -m "feat: implement Kafka producer"

# Push to remote
git push -u origin feature/phase2-kafka-setup
```

### Merging a Feature

```bash
# Update your feature branch with latest develop
git checkout feature/phase2-kafka-setup
git pull origin develop
git merge develop

# Push changes
git push origin feature/phase2-kafka-setup

# Create Pull Request on GitHub
# After review, merge to develop
```

### Weekly Release to Main

```bash
# After testing develop thoroughly
git checkout main
git merge develop --no-ff
git tag -a v0.2.0 -m "Phase 2: Infrastructure Setup Complete"
git push origin main --tags
```

---

## Commit Message Convention

We follow **Conventional Commits** for clear history:

### Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Build/config changes
- `perf`: Performance improvements

### Examples

```bash
# Feature
git commit -m "feat(kafka): add dual-listener configuration for Docker networking"

# Bug fix
git commit -m "fix(docker): resolve Kafka UI connection issue with internal listeners"

# Documentation
git commit -m "docs: add Phase 2 Day 1-2 setup instructions"

# Refactoring
git commit -m "refactor(producer): simplify CoinGecko API client"
```

---

## Phase-Based Branching

Since this is a phased project:

```
develop
  ├── feature/phase2-week3-docker-setup
  ├── feature/phase2-week4-data-pipeline
  ├── feature/phase3-week5-flink-basics
  ├── feature/phase3-week6-windowing
  └── feature/phase3-week7-state-management
```

Each phase completion merges to `develop`, then to `main` with version tag.

---

## Tags and Versions

### Semantic Versioning: MAJOR.MINOR.PATCH

- **v0.1.0** - Initial setup + Phase 1 (fundamentals)
- **v0.2.0** - Phase 2 complete (infrastructure)
- **v0.3.0** - Phase 3 complete (stream processing)
- **v0.4.0** - Phase 4 complete (API + visualization)
- **v1.0.0** - Final polish, ready for portfolio

### Tagging

```bash
# Annotated tag (recommended)
git tag -a v0.2.0 -m "Phase 2: Kafka + PostgreSQL + Redis infrastructure"

# Push tags
git push origin --tags
```

---

## Pull Request Template

When creating PRs, include:

1. **What changed?** - Brief description
2. **Why?** - Reason for change
3. **Testing** - How you verified it works
4. **Screenshots** - If UI changes
5. **Related Issues** - Link to any issues

---

## Why This Matters for Interviews

Interviewers look for:
- ✅ Clean commit history
- ✅ Descriptive branch names
- ✅ Conventional commit messages
- ✅ Proper use of PRs
- ✅ Version tagging
- ✅ Professional workflow practices

This demonstrates **software engineering maturity** beyond just coding skills!
