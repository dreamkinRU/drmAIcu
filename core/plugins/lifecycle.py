"""Проверки переходов жизненного цикла (§3.1 спецификации)."""
from .models import PluginState

TRANSITIONS = {
    PluginState.DISCOVER: {PluginState.VALIDATE},
    PluginState.VALIDATE: {PluginState.REGISTER, PluginState.ERROR},
    PluginState.REGISTER: {PluginState.AUTHORIZE},
    PluginState.AUTHORIZE: {PluginState.LOAD, PluginState.ERROR},
    PluginState.LOAD: {PluginState.INITIALIZE, PluginState.ERROR},
    PluginState.INITIALIZE: {PluginState.RUNNING, PluginState.ERROR},
    PluginState.RUNNING: {PluginState.STOP, PluginState.DISABLE, PluginState.ERROR, PluginState.UNINSTALL},
    PluginState.STOP: {PluginState.UNINSTALL, PluginState.DISABLE},
    PluginState.DISABLE: {PluginState.UNINSTALL},
    PluginState.ERROR: {PluginState.STOP, PluginState.DISABLE, PluginState.UNINSTALL},
}


def can_transition(src, dst):
    return dst in TRANSITIONS.get(src, set())
