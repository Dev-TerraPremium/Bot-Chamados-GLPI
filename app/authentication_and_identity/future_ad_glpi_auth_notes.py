"""
Future authentication notes.

This module intentionally does not implement real LDAP, AD or GLPI login.
The future production path should bind channel identities to a GLPI/AD user
through an explicit verification flow, keep session expiration metadata, and
avoid storing passwords inside this application.
"""

