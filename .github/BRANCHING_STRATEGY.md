# Branching Strategy & Release Workflow

## Branch Structure

### `main` - Production Branch
- **Purpose**: Production-ready code
- **Protection**: Requires PR approval, passing CI
- **Releases**: Tagged releases (e.g., `v0.1.0`) are published to PyPI
- **Versioning**: Uses semantic version tags

### `dev` - Development Branch  
- **Purpose**: Integration branch for features
- **Testing**: Runs full CI suite
- **Releases**: Automatic dev releases to TestPyPI on push
- **Versioning**: Auto-generated dev versions (e.g., `0.1.1.dev3`)

### `feature/*` - Feature Branches
- **Purpose**: Individual feature development
- **Testing**: Runs CI tests but doesn't build/publish
- **Merge**: PR into `dev` branch
- **Example**: `feature/add-gcs-backend`, `feature/fix-bug-123`

## Workflows

### 1. CI Workflow (`ci.yml`)
**Triggers**: Push to any branch, PRs to main/dev

**Jobs**:
- **test**: Runs tests on Python 3.10, 3.11, 3.12
- **lint**: Runs ruff linter
- **build**: Only on `main` and `dev` branches

### 2. Production Release (`release.yml`)
**Triggers**: 
- Tags matching `v*` (e.g., `v0.1.0`)
- Push to `main` (for CI only)

**Actions**:
- Runs full test suite
- Builds package
- Publishes to PyPI (only on tags)
- Creates GitHub Release with artifacts

### 3. Dev Release (`dev-release.yml`)
**Triggers**: Push to `dev` branch

**Actions**:
- Runs tests
- Builds package with dev version
- Publishes to TestPyPI
- Uploads artifacts

## Release Process

### Development Release (to TestPyPI)
```bash
# Make changes on feature branch
git checkout -b feature/my-feature
# ... make changes ...
git commit -am "Add new feature"
git push origin feature/my-feature

# Create PR to dev
# After approval and merge to dev
# → Automatically publishes to TestPyPI
```

### Production Release (to PyPI)
```bash
# From dev branch, create PR to main
git checkout dev
git pull origin dev
# Create PR dev → main

# After approval and merge to main
git checkout main
git pull origin main

# Tag the release
git tag v0.1.0
git push origin v0.1.0

# → Automatically:
#    - Runs tests
#    - Builds package (version 0.1.0 from tag)
#    - Publishes to PyPI
#    - Creates GitHub Release
```

## Semantic Versioning with setuptools-scm

### How Versions are Generated

**Tagged Release** (on main):
```bash
git tag v0.1.0  →  Version: 0.1.0
git tag v1.2.3  →  Version: 1.2.3
```

**Development Version** (between tags):
```bash
# After v0.1.0, with 5 commits since tag
→ Version: 0.1.1.dev5

# On dev branch, no tags yet
→ Version: 0.1.0.dev0 (fallback)
```

**Check Version**:
```bash
python -c "import datamole; print(datamole.__version__)"
```

## GitHub Secrets Required

Add these in GitHub repo settings → Secrets and variables → Actions:

1. **PYPI_API_TOKEN**: PyPI API token for production releases
   - Get from: https://pypi.org/manage/account/token/
   
2. **TEST_PYPI_API_TOKEN**: TestPyPI API token for dev releases
   - Get from: https://test.pypi.org/manage/account/token/

## Example Workflow

### Feature Development
```bash
# 1. Create feature branch from dev
git checkout dev
git pull origin dev
git checkout -b feature/add-s3-backend

# 2. Develop and commit
# ... make changes ...
git commit -am "Add S3 backend support"
git push origin feature/add-s3-backend

# 3. Create PR to dev
# CI runs tests but doesn't publish

# 4. After approval, merge to dev
# → Auto-publishes to TestPyPI as dev version
```

### Release to Production
```bash
# 1. Create PR from dev to main
git checkout dev
git pull origin dev
# Create PR dev → main

# 2. After approval and merge
git checkout main
git pull origin main

# 3. Tag release
git tag v0.2.0
git push origin v0.2.0

# 4. Automatically happens:
# ✓ CI tests pass
# ✓ Package built with version 0.2.0
# ✓ Published to PyPI
# ✓ GitHub Release created
```

## Benefits

- ✅ **Isolated testing**: Every branch/PR runs tests
- ✅ **Safe development**: Test releases on TestPyPI first
- ✅ **Automated versioning**: No manual version bumps
- ✅ **Clean releases**: Only tagged commits go to PyPI
- ✅ **Feature isolation**: Feature branches don't pollute releases
