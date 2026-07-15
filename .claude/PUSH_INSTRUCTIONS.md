# 🚀 Push Instructions for v0.8.4

## Current Status

✅ **All changes committed locally**
✅ **Version tagged (v0.8.4)**
✅ **Ready to push**
❌ **Push failed due to network issue (403 error)**

## Local Git Status

```bash
Branch: main
Commits ahead: 2
  - 619f482: Main refactoring commit
  - 72fb766: Release notes commit
Tag: v0.8.4 created
Status: All changes committed
```

## How to Push (When Network Available)

### Option 1: Push with Tags

```bash
cd /Users/d/Работа\ и\ проекты/nagient

# Push commits and tags together
git push origin main --tags
```

### Option 2: Push Separately

```bash
cd /Users/d/Работа\ и\ проекты/nagient

# Push commits
git push origin main

# Push tags
git push origin v0.8.4
```

### Option 3: Force Push (If Needed)

```bash
# Only if you need to force push (use with caution)
git push origin main --force --tags
```

## Verification After Push

```bash
# Check remote status
git fetch origin
git status

# Verify tag on remote
git ls-remote --tags origin

# Check GitHub
# Visit: https://github.com/KOSFin/nagient/tags
# Should see v0.8.4 tag

# Check Actions
# Visit: https://github.com/KOSFin/nagient/actions
# Should see auto-tag and release workflows running
```

## Network Troubleshooting

### If 403 Error Persists

1. **Check Proxy Settings:**
   ```bash
   git config --global http.proxy
   git config --global https.proxy
   ```

2. **Try Different Network:**
   - Switch to different WiFi
   - Try mobile hotspot
   - Use VPN if needed

3. **Use SSH Instead of HTTPS:**
   ```bash
   # Check current remote
   git remote -v
   
   # Switch to SSH (if you have SSH keys)
   git remote set-url origin git@github.com:KOSFin/nagient.git
   
   # Try push again
   git push origin main --tags
   ```

4. **Check GitHub Status:**
   - Visit https://www.githubstatus.com/
   - Check if GitHub is having issues

## What Will Happen After Push

### 1. Auto-Tag Workflow
- Detects v0.8.4 tag
- Validates tag format
- Triggers release workflow

### 2. Release Workflow
- Builds Python package
- Builds Docker image
- Publishes to Docker Hub (parampo/nagient:0.8.4)
- Creates GitHub release

### 3. Update Center
- Publishes installers to GitHub Pages
- Updates channel manifests
- Makes v0.8.4 available for installation

### 4. GitHub Release Page
- Automatic release notes from CHANGELOG.md
- Download links for artifacts
- Docker pull command

## Manual Release (If CI/CD Fails)

### Build Package

```bash
cd /Users/d/Работа\ и\ проекты/nagient

# Install build tools
pip install build

# Build package
python -m build

# Verify
ls dist/
# Should see:
#   nagient-0.8.4.tar.gz
#   nagient-0.8.4-py3-none-any.whl
```

### Build Docker Image

```bash
# Build image
docker build -t parampo/nagient:0.8.4 .
docker tag parampo/nagient:0.8.4 parampo/nagient:latest

# Test image
docker run --rm parampo/nagient:0.8.4 nagient --version

# Push to Docker Hub (requires login)
docker login
docker push parampo/nagient:0.8.4
docker push parampo/nagient:latest
```

### Create GitHub Release Manually

1. Go to https://github.com/KOSFin/nagient/releases/new
2. Choose tag: v0.8.4
3. Release title: "v0.8.4 - Manifest-Driven Plugin Architecture"
4. Copy description from `.claude/RELEASE_v0.8.4.md`
5. Upload artifacts from `dist/`
6. Publish release

## Post-Push Checklist

- [ ] Commits pushed to origin/main
- [ ] Tag v0.8.4 visible on GitHub
- [ ] Auto-tag workflow completed successfully
- [ ] Release workflow completed successfully
- [ ] Docker image available: `docker pull parampo/nagient:0.8.4`
- [ ] GitHub release created
- [ ] Release notes visible
- [ ] Installation script works: `curl -fsSL https://nagient.dev/install.sh | bash`
- [ ] Update center shows v0.8.4

## Testing Installation

### Test Docker Install

```bash
# Pull image
docker pull parampo/nagient:0.8.4

# Test version
docker run --rm parampo/nagient:0.8.4 nagient --version
# Should output: 0.8.4

# Test help
docker run --rm parampo/nagient:0.8.4 nagient --help
```

### Test Package Install

```bash
# Create test venv
python3.12 -m venv test-env
source test-env/bin/activate

# Install from PyPI (if published)
pip install nagient==0.8.4

# Or install from local build
pip install dist/nagient-0.8.4-py3-none-any.whl

# Test
nagient --version
nagient --help
```

### Test Script Install

```bash
# Test installation script
curl -fsSL https://nagient.dev/install.sh | bash

# Verify
nagient --version
```

## Documentation Updates

After push is successful:

1. **README badges** - Update version badges if any
2. **Documentation site** - Publish updated docs
3. **PyPI listing** - Update project description if needed
4. **Docker Hub** - Update description with v0.8.4 notes
5. **Community** - Announce release on communication channels

## Rollback (If Needed)

If something goes wrong:

```bash
# Delete remote tag
git push origin :refs/tags/v0.8.4

# Delete local tag
git tag -d v0.8.4

# Revert commits (if needed)
git reset --hard origin/main

# Force push (if needed)
git push origin main --force
```

## Summary

**Ready to push when network is available!**

All changes are committed locally:
- ✅ 2 commits ready
- ✅ v0.8.4 tag created
- ✅ All files staged and committed
- ✅ CHANGELOG updated
- ✅ Version bumped
- ✅ Documentation complete

**Just run:** `git push origin main --tags`

---

*Created: 2026-07-15*  
*Status: Ready to push*  
*Network issue: 403 error (temporary)*
