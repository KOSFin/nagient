#!/bin/bash
# Quick push script for Nagient v0.8.4
# Run this when network is available

cd /Users/d/Работа\ и\ проекты/nagient

echo "🚀 Pushing Nagient v0.8.4 to origin..."
echo ""

# Push commits and tags
if git push origin main --tags; then
    echo ""
    echo "✅ Successfully pushed to origin!"
    echo ""
    echo "Next steps:"
    echo "  1. Check GitHub Actions: https://github.com/KOSFin/nagient/actions"
    echo "  2. Verify tag: https://github.com/KOSFin/nagient/tags"
    echo "  3. Watch release: https://github.com/KOSFin/nagient/releases"
    echo "  4. Check Docker: docker pull parampo/nagient:0.8.4"
else
    echo ""
    echo "❌ Push failed!"
    echo ""
    echo "Common issues:"
    echo "  - Network connection (403 error)"
    echo "  - Authentication required"
    echo "  - Remote branch protection"
    echo ""
    echo "Try:"
    echo "  - Check network connection"
    echo "  - Verify GitHub credentials"
    echo "  - Use VPN if needed"
    echo "  - Switch to SSH: git remote set-url origin git@github.com:KOSFin/nagient.git"
fi
