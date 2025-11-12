# Git Workflow Setup Guide

This guide helps you set up the Git branching strategy for the first time.

## Initial Setup

### 1. Configure Commit Message Template

```bash
# Set the commit message template
git config commit.template .gitmessage

# Now every git commit will open with this template
```

### 2. Create Initial Branches

```bash
# Make sure you're on main
git checkout main

# Create develop branch
git checkout -b develop

# Push both branches to remote
git push -u origin main
git push -u origin develop

# Set develop as default branch for new features
git config branch.develop.remote origin
git config branch.develop.merge refs/heads/develop
```

### 3. Create Your First Feature Branch

```bash
# From develop, create feature branch for Phase 2 Week 3
git checkout develop
git checkout -b feature/phase2-week3-docker-setup

# You're now on your feature branch!
```

---

## Making Your First Commit

Now that you're on `feature/phase2-week3-docker-setup`, let's commit Phase 2 Day 1-2 work:

```bash
# Stage all changes
git add .

# Commit with conventional format
git commit -m "feat(kafka): implement dual-listener Docker configuration

- Added Zookeeper, Kafka, and Kafka UI to docker-compose.yml
- Configured dual listeners for internal (29092) and external (9092) access
- Fixed Docker networking issue where Kafka UI couldn't connect to Kafka
- Created test-topic with 3 partitions
- Successfully produced and consumed first test message
- Added comprehensive documentation (README, PHASE2_DAY1-2.md, DOCKER_COMMANDS.md)

Resolves Phase 2, Week 3, Day 1-2 objectives"

# Push to remote
git push -u origin feature/phase2-week3-docker-setup
```

---

## Daily Workflow

### Option 1: Working on Current Feature

```bash
# Continue working on your feature branch
git checkout feature/phase2-week3-docker-setup

# Make changes...

# Commit with conventional format
git commit -m "feat(postgres): add PostgreSQL to docker-compose"

# Push
git push origin feature/phase2-week3-docker-setup
```

### Option 2: Starting New Feature

```bash
# Switch to develop
git checkout develop

# Pull latest changes
git pull origin develop

# Create new feature branch
git checkout -b feature/phase2-week3-postgres-redis

# Work and commit...
```

---

## Merging Feature to Develop

When you complete Day 3-4 (PostgreSQL + Redis):

```bash
# Make sure feature branch is up to date
git checkout feature/phase2-week3-docker-setup
git pull origin develop
git merge develop

# Push any merge commits
git push origin feature/phase2-week3-docker-setup

# Go to GitHub and create a Pull Request
# Title: "feat(phase2): Complete Week 3 Docker Infrastructure Setup"
# Base: develop
# Compare: feature/phase2-week3-docker-setup
```

After creating PR:
1. Review your own changes
2. Merge PR to develop
3. Delete feature branch

---

## Weekly Release to Main

At the end of each week (after completing Day 5-7):

```bash
# Switch to develop
git checkout develop
git pull origin develop

# Merge to main
git checkout main
git pull origin main
git merge develop --no-ff -m "merge: Phase 2 Week 3 complete"

# Tag the release
git tag -a v0.2.1 -m "Phase 2 Week 3: Docker infrastructure with Kafka, PostgreSQL, Redis, and Flink"

# Push everything
git push origin main
git push origin --tags
```

---

## Branch Protection (Optional - Set on GitHub)

For professional workflow, protect your branches:

1. Go to GitHub → Settings → Branches
2. Add rule for `main`:
   - ✅ Require pull request before merging
   - ✅ Require status checks to pass
3. Add rule for `develop`:
   - ✅ Require pull request before merging

This forces you to use PRs, which looks great on your portfolio!

---

## Quick Reference

| Task | Command |
|------|---------|
| Create feature | `git checkout -b feature/name` |
| Switch branches | `git checkout branch-name` |
| Commit | `git commit` (uses template) |
| Push feature | `git push -u origin feature/name` |
| Update from develop | `git pull origin develop` |
| Merge to develop | Create PR on GitHub |
| Tag release | `git tag -a v0.2.0 -m "message"` |

---

## Current Branch Status

After setup, your structure will be:

```
main                                    (v0.1.0 - Initial commit)
  └── develop                           (integration branch)
      └── feature/phase2-week3-docker-setup    (current work)
```

---

## Pro Tips

1. **Commit Often**: Small, focused commits are better than large ones
2. **Descriptive Messages**: Future you will thank present you
3. **Pull Before Push**: Always `git pull` before `git push` to avoid conflicts
4. **Feature Per Branch**: One feature = one branch = one PR
5. **Delete Old Branches**: After merging, delete feature branches to keep things clean

---

## Interview Talking Point

> "I followed a simplified GitHub Flow with feature branches for my crypto analyzer project. Each phase was developed in feature branches that merged to develop via pull requests, then released to main with semantic version tags. This workflow demonstrates professional Git practices including conventional commits, branch protection, and proper release management."

---

**You're now ready to commit with a professional Git workflow!** 🚀
