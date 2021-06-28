from calibre.customize.builtins import plugins

for plugin in plugins:
    if plugin.name == "Input Options":
        plugin.config_widget = (
            "calibre_plugins.kepubin.conversion.input_config:InputOptions"
        )
        break
