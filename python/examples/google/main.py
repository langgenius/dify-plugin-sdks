from shai_plugin import ShaiPluginEnv, Plugin

plugin = Plugin(ShaiPluginEnv(MAX_REQUEST_TIMEOUT=30))

if __name__ == "__main__":
    plugin.run()
