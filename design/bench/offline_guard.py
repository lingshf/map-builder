# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Offline guard for the S4 benchmarks (D91): any DNS lookup or socket connect raises and is counted."""
import socket

ATTEMPTS = []


def _deny(what):
    def f(*args, **kwargs):
        ATTEMPTS.append((what, repr(args[:2])))
        raise OSError("offline benchmark: network access denied (" + what + ")")
    return f


def install():
    socket.getaddrinfo = _deny("getaddrinfo")
    socket.gethostbyname = _deny("gethostbyname")
    socket.create_connection = _deny("create_connection")
    socket.socket.connect = _deny("connect")
    socket.socket.connect_ex = _deny("connect_ex")


def assert_offline():
    if ATTEMPTS:
        raise SystemExit("network access attempted: %r" % ATTEMPTS)
