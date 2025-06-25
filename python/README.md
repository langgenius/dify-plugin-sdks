# Dify Plugin SDK

A Python SDK for building plugins for Dify.

## Version Management

This SDK follows Semantic Versioning (a.b.c):

- a: Major version - Indicates significant architectural changes or incompatible API modifications
- b: Minor version - Indicates new feature additions while maintaining backward compatibility
- c: Patch version - Indicates backward-compatible bug fixes

### For SDK Users

When depending on this SDK, it's recommended to specify version constraints that:

- Allow patch and minor updates for bug fixes and new features
- Prevent major version updates to avoid breaking changes

Example in your project's dependency management:

```
dify_plugin>=0.3.0,<0.4.0
```

### Manifest Version Reference

For the manifest specification, we've introduced two versioning fields:

- `meta.version` - The version of the manifest specification, designed for backward compatibility. When installing an older plugin to a newer Dify, it's difficult to ensure breaking changes never occur, but at least Dify can detect them through this field. Once an unsupported version is detected, Dify will only use the supported parts of the plugin.
- `meta.minimum_dify_version` - The minimum version of Dify, designed for forward compatibility. When installing a newer plugin to an older Dify, many new features may not be available, but showing the minimum Dify version helps users understand how to upgrade.

#### Meta.Version Reference

| Manifest Version | Description |
|------------------|-------------|
| 0.0.1            | Initial release |

#### Meta.MinimumDifyVersion Reference

| Minimum Dify Version| SDK Version | Description |
|----------------------|-------------|-------------|
| 1.2.0                | 0.2.0         | Support fetching application info |
| 1.4.0                | 0.0.1-beta.49 | Support LLM multimodal output |
| 1.4.0                | 0.3.1         | Support OAuth functionality for plugins |
