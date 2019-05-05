from calibre.customize.builtins import plugins

for plugin in plugins:
    if plugin.name == "Output Options":
        plugin.config_widget = (
            "calibre_plugins.kepubout.conversion." "output_config:OutputOptions"
        )
        break
