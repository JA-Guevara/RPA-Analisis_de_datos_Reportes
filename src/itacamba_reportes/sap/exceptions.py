from __future__ import annotations


class SapAutomationError(Exception):
    pass


class SapConnectionError(SapAutomationError):
    pass


class SapLoginError(SapAutomationError):
    pass


class SapElementNotFoundError(SapAutomationError):
    pass


class SapExportError(SapAutomationError):
    pass
