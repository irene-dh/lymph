from lymph.core.components import Component


class Plugin(Component):
    def on_interface_installation(self, interface):
        pass


class Hook(object):
    def __init__(self):
        self.callbacks = []

    def install(self, callback):
        self.callbacks.append(callback)

    def __call__(self, *args, **kwargs):
        for callback in self.callbacks:
            callback(*args, **kwargs)
