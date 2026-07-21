# Security Policy

## Supported Versions

Currently supported versions of Nagient:

| Version | Supported          |
| ------- | ------------------ |
| 0.8.x   | :white_check_mark: |
| 0.1.x   | :x:                |

## Reporting a Vulnerability

We take the security of Nagient seriously. If you discover a security vulnerability, please follow these steps:

### 1. Do Not Open a Public Issue

Please **do not** open a public GitHub issue for security vulnerabilities. Public disclosure could put the community at risk.

### 2. Report Privately

Send your vulnerability report to the project maintainers via:
- GitHub Security Advisories (preferred)
- Email to the maintainers listed in `pyproject.toml`

### 3. Include Detailed Information

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)
- Your contact information

### 4. Response Timeline

- **Initial Response:** Within 48 hours
- **Status Update:** Within 7 days
- **Fix Timeline:** Depends on severity (Critical: 7 days, High: 30 days, Medium: 90 days)

## Security Considerations

### Plugin Security

**Bundled Plugins:** All bundled transports and tools are reviewed and maintained by the core team.

**Custom Plugins:** User-provided plugins run with the same privileges as Nagient. Only install plugins from trusted sources.

**Plugin Isolation:** Currently, plugins run in the same process. Future versions may add sandboxing.

### Secrets Management

**Storage:** Secrets are stored in `~/.nagient/secrets.env` and should be protected with appropriate file permissions (0600).

**In Memory:** Secrets are loaded into memory during runtime. The secret broker provides redaction boundaries.

**Transmission:** Secrets are passed to plugins via environment variables or secure channels. Never log or print secrets.

### Workspace Safety

**Bounded Mode (Default):** Limits file operations to the configured workspace root.

**Unsafe Mode:** Removes path restrictions. Use only in trusted environments.

**Protected Paths:** Nagient's own configuration directories are protected from workspace operations.

### Network Security

**HTTPS Only:** Use HTTPS for all external API calls (GitHub, LLM providers, etc.)

**Proxy Support:** Telegram and other transports support HTTP/HTTPS proxies with authentication.

**Certificate Validation:** Always validate TLS certificates. Never disable certificate checks.

### Git Operations

**Credential Handling:** Git credentials are passed via askpass script with environment variables, never in command line arguments.

**Token Storage:** Store tokens in tool secrets, not in git config or workspace files.

**Repository Trust:** Only clone from trusted repositories. Malicious repositories could contain harmful hooks or content.

### Authentication

**Provider Auth:** Each provider (OpenAI, Anthropic, etc.) uses separate credentials stored in secrets.

**Transport Auth:** Each transport (Telegram, webhooks) has its own authentication mechanism.

**Token Rotation:** Regularly rotate API tokens and bot tokens.

### Approval Workflows

**Approval Policies:** Tools declare approval requirements (never, inherit, required, policy).

**High-Risk Operations:** Operations like git push, file deletion, and external API writes require approval.

**Dry-Run Support:** Many tools support dry-run mode to preview changes before execution.

## Best Practices

### For Users

1. **Protect Secrets:** Set `chmod 600 ~/.nagient/secrets.env`
2. **Review Plugins:** Audit custom plugins before installation
3. **Use Bounded Mode:** Keep workspace mode as "bounded" unless necessary
4. **Rotate Tokens:** Regularly update API keys and tokens
5. **Monitor Logs:** Check `~/.nagient/logs/` for suspicious activity
6. **Update Regularly:** Keep Nagient updated to the latest version

### For Plugin Developers

1. **Validate Input:** Always validate and sanitize user input
2. **Declare Permissions:** Accurately declare required permissions
3. **Handle Secrets Safely:** Use the secret broker, never log secrets
4. **Approval Policies:** Set appropriate approval policies for risky operations
5. **Error Handling:** Handle errors gracefully, don't leak sensitive information
6. **Documentation:** Document security requirements and risks

### For Operators

1. **Least Privilege:** Run Nagient with minimal necessary permissions
2. **Isolated Environment:** Consider running in Docker or isolated environment
3. **Network Segmentation:** Restrict network access to required endpoints only
4. **Audit Logging:** Enable and monitor audit logs
5. **Backup Configuration:** Regularly backup `~/.nagient/config.toml` and secrets
6. **Review Approvals:** Carefully review approval requests before accepting

## Known Security Limitations

### Current Limitations

1. **Plugin Isolation:** Plugins run in the same process without sandboxing
2. **Shell Access:** Shell tool provides direct command execution
3. **Workspace Access:** In unsafe mode, full filesystem access is possible
4. **Memory Security:** Secrets exist in process memory unencrypted

### Planned Improvements

- Plugin sandboxing with process isolation
- Enhanced secret encryption at rest
- Audit logging for all operations
- Fine-grained permission system
- Rate limiting for external API calls

## Security Features

### Built-in Protections

✅ **Path Guards:** Workspace manager prevents escaping workspace root  
✅ **Secret Redaction:** Secret broker redacts secrets from logs and errors  
✅ **Approval Gates:** High-risk operations require explicit approval  
✅ **Validation:** Plugin registry validates manifests and configurations  
✅ **Safe Defaults:** Bounded workspace mode, approval policies enabled by default

### Security Tools

- **Preflight Checks:** `nagient preflight` validates configuration before activation
- **Status Monitoring:** `nagient status` shows system health
- **Plugin Inspection:** `nagient transport list` shows all loaded plugins
- **Secret Management:** Secrets stored separately from configuration

## Compliance

### Data Privacy

- **No Telemetry:** Nagient does not send telemetry or usage data
- **Local First:** All data stays local unless you configure external integrations
- **LLM Providers:** Your prompts go to configured LLM providers (OpenAI, Anthropic, etc.)

### License

Nagient is released under the MIT License. See [LICENSE](LICENSE) for details.

## Security Updates

Security updates are released as patch versions (e.g., 0.8.1 → 0.8.2) and documented in the changelog.

Subscribe to GitHub releases to be notified of security updates.

## Additional Resources

- [Architecture and trust boundaries](docs/architecture.md)
- [Plugin development guide](docs/PLUGIN_DEVELOPMENT.md)
- [Configuration and secrets reference](docs/configuration.md)

## Acknowledgments

We appreciate security researchers who responsibly disclose vulnerabilities. Contributors will be acknowledged (with permission) in release notes.

---

*Last Updated: 2026-07-15*  
*Version: 0.8.3*
