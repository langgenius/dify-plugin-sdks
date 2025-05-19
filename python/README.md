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
dify_plugin>=0.2.0,<0.3.0
```

