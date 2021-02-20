#!/usr/bin/env python3
#
# Copyright (c) 2021 Michael Thies
#

import asyncio
import ctypes as c
import enum
import itertools
import time
from functools import partial
from typing import Set, Optional, Dict
from pulsectl._pulsectl import PA_MAINLOOP_API

# References:
# - https://docs.python.org/3.9/library/ctypes.html
# - https://freedesktop.org/software/pulseaudio/doxygen/mainloop-api_8h.html


class pa_mainloop_api(PA_MAINLOOP_API):
    pass


class timeval(c.Structure):
    _fields_ = [
        ('tv_sec', c.c_longlong),
        ('tv_usec', c.c_long),
    ]

    def to_float(self) -> float:
        return self.tv_sec + self.tv_usec / 1e6


PA_IO_EVENT_NULL = 0
PA_IO_EVENT_INPUT = 1
PA_IO_EVENT_OUTPUT = 2
PA_IO_EVENT_HANGUP = 4
PA_IO_EVENT_ERROR = 8

# Typedefs from mainloop.h
pa_defer_event_p = c.c_void_p
pa_defer_event_cb_t = c.CFUNCTYPE(None, c.POINTER(pa_mainloop_api), pa_defer_event_p, c.c_void_p)
pa_defer_event_destroy_cb_t = c.CFUNCTYPE(None, c.POINTER(pa_mainloop_api), pa_defer_event_p, c.c_void_p)
pa_io_event_p = c.c_void_p
pa_io_event_flags = c.c_int
pa_io_event_cb_t = c.CFUNCTYPE(None, c.POINTER(pa_mainloop_api), pa_io_event_p, c.c_int, pa_io_event_flags, c.c_void_p)
pa_io_event_destroy_cb_t = c.CFUNCTYPE(None, c.POINTER(pa_mainloop_api), pa_io_event_p, c.c_void_p)
pa_time_event_p = c.c_void_p
pa_time_event_cb_t = c.CFUNCTYPE(None, c.POINTER(pa_mainloop_api), pa_time_event_p, c.POINTER(timeval), c.c_void_p)
pa_time_event_destroy_cb_t = c.CFUNCTYPE(None, c.POINTER(pa_mainloop_api), pa_time_event_p, c.c_void_p)

# function pointer types of pa_mainloop_api struct
pa_io_new_t = c.CFUNCTYPE(pa_io_event_p, c.POINTER(pa_mainloop_api), c.c_int, pa_io_event_flags, pa_io_event_cb_t,
                          c.c_void_p)
pa_io_enable_t = c.CFUNCTYPE(None, pa_io_event_p, pa_io_event_flags)
pa_io_set_destroy_t = c.CFUNCTYPE(None, pa_io_event_p, pa_io_event_destroy_cb_t)
pa_io_free_t = c.CFUNCTYPE(None, pa_io_event_p)
pa_time_new_t = c.CFUNCTYPE(pa_time_event_p, c.POINTER(pa_mainloop_api), c.POINTER(timeval), pa_time_event_cb_t,
                            c.c_void_p)
pa_time_restart_t = c.CFUNCTYPE(None, pa_time_event_p, c.POINTER(timeval))
pa_time_set_destroy_t = c.CFUNCTYPE(None, pa_time_event_p, pa_time_event_destroy_cb_t)
pa_time_free_t = c.CFUNCTYPE(None, pa_time_event_p)
pa_defer_new_t = c.CFUNCTYPE(pa_defer_event_p, c.POINTER(pa_mainloop_api), pa_defer_event_cb_t, c.c_void_p)
pa_defer_enable_t = c.CFUNCTYPE(None, pa_defer_event_p, c.c_bool)
pa_defer_free_t = c.CFUNCTYPE(None, pa_defer_event_p)
pa_defer_set_destroy_t = c.CFUNCTYPE(None, pa_defer_event_p, pa_defer_event_destroy_cb_t)
pa_quit_t = c.CFUNCTYPE(None, c.POINTER(pa_mainloop_api), c.c_int)

pa_mainloop_api._fields_ = [
    ("userdata", c.c_void_p),  # We use it to store a pointer to the corresponding PythonMainLoop python object
    ("io_new", pa_io_new_t),
    ("io_enable", pa_io_enable_t),
    ("io_free", pa_io_free_t),
    ("io_set_destroy", pa_io_set_destroy_t),
    ("time_new", pa_time_new_t),
    ("time_restart", pa_time_restart_t),
    ("time_free", pa_time_free_t),
    ("time_set_destroy", pa_time_set_destroy_t),
    ("defer_new", pa_defer_new_t),
    ("defer_enable", pa_defer_enable_t),
    ("defer_free", pa_defer_free_t),
    ("defer_set_destroy", pa_defer_set_destroy_t),
    ("quit", pa_quit_t),
]


class PythonMainLoop:
    __slots__ = ('loop', 'io_events', 'time_events', 'defer_events',
                 'api_pointer', 'io_reader_events', 'io_writer_events', 'retval')

    def __init__(self, loop: asyncio.AbstractEventLoop):
        # TODO implement 'on_quit' event callback
        self.loop = loop
        self.io_events: Set["PythonIOEvent"] = set()
        self.defer_events: Set["PythonDeferEvent"] = set()
        self.time_events: Set["PythonTimeEvent"] = set()
        self.io_reader_events: Dict[int, Set[PythonIOEvent]] = {}
        self.io_writer_events: Dict[int, Set[PythonIOEvent]] = {}
        self.api_pointer = c.pointer(self._create_api())
        self.retval: Optional[int] = None

    def _create_api(self) -> pa_mainloop_api:
        result = pa_mainloop_api()
        result.userdata = c.cast(c.pointer(c.py_object(self)), c.c_void_p)
        result.io_new = aio_io_new
        result.io_enable = aio_io_enable
        result.io_free = aio_io_free
        result.io_set_destroy = aio_io_set_destroy
        result.time_new = aio_time_new
        result.time_restart = aio_time_restart
        result.time_free = aio_time_free
        result.time_set_destroy = aio_time_set_destroy
        result.defer_new = aio_defer_new
        result.defer_enable = aio_defer_enable
        result.defer_free = aio_defer_free
        result.defer_set_destroy = aio_defer_set_destroy
        result.quit = aio_quit
        return result

    def register_unregister_io_event(self, event: "PythonIOEvent", reader: bool, writer: bool) -> None:
        if writer:
            if event.fd in self.io_writer_events:
                self.io_writer_events[event.fd].add(event)
            else:
                self.io_writer_events[event.fd] = {event}
                self.loop.add_writer(event.fd, partial(self._io_write_callback, event.fd))
        elif event.fd in self.io_writer_events:
            self.io_writer_events[event.fd].discard(event)
            if not self.io_writer_events[event.fd]:
                del self.io_writer_events[event.fd]
                self.loop.remove_writer(event.fd)

        if reader:
            if event.fd in self.io_reader_events:
                self.io_reader_events[event.fd].add(event)
            else:
                self.io_reader_events[event.fd] = {event}
                self.loop.add_reader(event.fd, partial(self._io_read_callback, event.fd))
        elif event.fd in self.io_reader_events:
            self.io_reader_events[event.fd].discard(event)
            if not self.io_reader_events[event.fd]:
                del self.io_reader_events[event.fd]
                self.loop.remove_reader(event.fd)
        # Python asyncio's API does not allow us to `poll` for HANGUP and ERROR states.
        # However, this does not seem to be an issue, since the pulse client library obviously does not use these flags
        # for io io_events.

    def _io_write_callback(self, fd) -> None:
        for event in tuple(self.io_writer_events.get(fd, ())):
            event.write()

    def _io_read_callback(self, fd) -> None:
        for event in tuple(self.io_reader_events.get(fd, ())):
            event.read()

    def stop(self, retval: int) -> None:
        for event in itertools.chain(self.defer_events, self.io_writer_events, self.time_events):
            event.free()
        self.retval = retval


class PythonIOEvent:
    __slots__ = ('python_main_loop', 'fd', 'callback', 'userdata', 'on_destroy_callback', 'writer', 'reader',
                 'self_pointer')

    def __init__(self, python_main_loop: PythonMainLoop, fd: int, callback: pa_io_event_cb_t,
                 userdata: c.c_void_p) -> None:
        self.python_main_loop = python_main_loop
        self.fd = fd
        self.callback = callback
        self.userdata = userdata
        self.on_destroy_callback: Optional[pa_io_event_destroy_cb_t] = None
        self.writer = False
        self.reader = False
        self.self_pointer: pa_io_event_p = c.cast(c.pointer(c.py_object(self)), pa_io_event_p)
        python_main_loop.io_events.add(self)

    def read(self) -> None:
        self.callback(self.python_main_loop.api_pointer, self.self_pointer.value, self.fd, PA_IO_EVENT_INPUT,
                      self.userdata)

    def write(self) -> None:
        self.callback(self.python_main_loop.api_pointer, self.self_pointer.value, self.fd, PA_IO_EVENT_OUTPUT,
                      self.userdata)

    def free(self) -> None:
        self.python_main_loop.register_unregister_io_event(self, False, False)
        if self.on_destroy_callback is not None:
            self.on_destroy_callback(self.python_main_loop.api_pointer, c.pointer(c.py_object(self)), self.userdata)
        self.python_main_loop.io_events.discard(self)

    def set_destroy(self, callback: pa_io_event_destroy_cb_t) -> None:
        self.on_destroy_callback = callback


class PythonTimeEvent:
    __slots__ = ('python_main_loop', 'callback', 'userdata', 'on_destroy_callback', 'handle', 'self_pointer')

    def __init__(self, python_main_loop: PythonMainLoop, callback: pa_time_event_cb_t, userdata: c.c_void_p) -> None:
        self.python_main_loop = python_main_loop
        self.callback = callback
        self.userdata = userdata
        self.on_destroy_callback: Optional[pa_io_event_destroy_cb_t] = None
        self.handle: Optional[asyncio.TimerHandle] = None
        self.self_pointer: pa_io_event_p = c.cast(c.pointer(c.py_object(self)), pa_io_event_p)
        python_main_loop.time_events.add(self)

    def restart(self, ts: timeval) -> None:
        if self.handle is not None:
            self.handle.cancel()
        self.handle = self.python_main_loop.loop.call_later(
            ts.to_float() - time.time(), self.callback, self.python_main_loop.api_pointer, self.self_pointer.value,
            ts, self.userdata)

    def free(self) -> None:
        if self.on_destroy_callback is not None:
            self.on_destroy_callback(self.python_main_loop.api_pointer, c.pointer(c.py_object(self)), self.userdata)
        if self.handle:
            self.handle.cancel()
        self.python_main_loop.time_events.discard(self)

    def set_destroy(self, callback: pa_io_event_destroy_cb_t) -> None:
        self.on_destroy_callback = callback


class PythonDeferEvent:
    __slots__ = ('python_main_loop', 'callback', 'userdata', 'on_destroy_callback', 'enabled', 'self_pointer', 'handle')

    def __init__(self, python_main_loop: PythonMainLoop, callback: pa_defer_event_cb_t, userdata: c.c_void_p) -> None:
        self.python_main_loop = python_main_loop
        self.callback = callback
        self.userdata = userdata
        self.on_destroy_callback: Optional[pa_io_event_destroy_cb_t] = None
        self.enabled = False
        self.self_pointer: pa_defer_event_p = c.cast(c.pointer(c.py_object(self)), pa_defer_event_p)
        python_main_loop.defer_events.add(self)
        self.handle = None

    def call(self) -> None:
        self.handle = None
        self.callback(self.python_main_loop.api_pointer, self.self_pointer.value, self.userdata)
        if self.enabled and self.handle is None:
            self.handle = self.python_main_loop.loop.call_soon(self.call)

    def enable(self, enable: bool) -> None:
        if enable and self.handle is None:
            self.handle = self.python_main_loop.loop.call_soon(self.call)
        elif not enable and self.handle is not None:
            self.handle.cancel()
            self.handle = None
        self.enabled = enable

    def free(self) -> None:
        self.enable(False)
        if self.on_destroy_callback is not None:
            self.on_destroy_callback(self.python_main_loop.api_pointer, c.pointer(c.py_object(self)), self.userdata)
        self.python_main_loop.defer_events.discard(self)

    def set_destroy(self, callback: pa_io_event_destroy_cb_t) -> None:
        self.on_destroy_callback = callback


@pa_io_new_t
def aio_io_new(main_loop: c.POINTER(pa_mainloop_api), fd: int, flags: int, cb: pa_io_event_cb_t,
               userdata: c.c_void_p) -> int:
    python_main_loop: PythonMainLoop = c.cast(main_loop.contents.userdata, c.POINTER(c.py_object)).contents.value

    event = PythonIOEvent(python_main_loop, fd, cb, userdata)

    reader = bool(flags & PA_IO_EVENT_INPUT)
    writer = bool(flags & PA_IO_EVENT_OUTPUT)
    python_main_loop.register_unregister_io_event(event, reader, writer)
    return c.cast(event.self_pointer, pa_io_event_p).value


@pa_io_enable_t
def aio_io_enable(e: pa_io_event_p, flags: int) -> None:
    event: PythonIOEvent = c.cast(e, c.POINTER(c.py_object)).contents.value

    reader = bool(flags & PA_IO_EVENT_INPUT)
    writer = bool(flags & PA_IO_EVENT_OUTPUT)
    event.python_main_loop.register_unregister_io_event(event, reader, writer)


@pa_io_set_destroy_t
def aio_io_set_destroy(e: pa_io_event_p, cb: pa_io_event_destroy_cb_t) -> None:
    event: PythonIOEvent = c.cast(e, c.POINTER(c.py_object)).contents.value
    event.set_destroy(cb)


@pa_io_free_t
def aio_io_free(e: pa_io_event_p) -> None:
    event: PythonIOEvent = c.cast(e, c.POINTER(c.py_object)).contents.value
    event.free()


@pa_time_new_t
def aio_time_new(main_loop: c.POINTER(pa_mainloop_api), ts: c.POINTER(timeval), cb: pa_io_event_cb_t,
                 userdata: c.c_void_p) -> int:
    python_main_loop: PythonMainLoop = c.cast(main_loop.contents.userdata, c.POINTER(c.py_object)).contents.value
    event = PythonTimeEvent(python_main_loop, cb, userdata)
    event.restart(ts.contents)
    return c.cast(event.self_pointer, pa_time_event_p).value


@pa_time_restart_t
def aio_time_restart(e: pa_time_event_p, ts: c.POINTER(timeval)) -> None:
    event: PythonTimeEvent = c.cast(e, c.POINTER(c.py_object)).contents.value
    event.restart(ts.contents)


@pa_time_set_destroy_t
def aio_time_set_destroy(e: pa_time_event_p, cb: pa_time_event_destroy_cb_t) -> None:
    event: PythonTimeEvent = c.cast(e, c.POINTER(c.py_object)).contents.value
    event.set_destroy(cb)


@pa_time_free_t
def aio_time_free(e: pa_io_event_p) -> None:
    event: PythonTimeEvent = c.cast(e, c.POINTER(c.py_object)).contents.value
    event.free()


@pa_defer_new_t
def aio_defer_new(main_loop: c.POINTER(pa_mainloop_api), cb: pa_defer_event_cb_t, userdata: c.c_void_p) -> int:
    python_main_loop: PythonMainLoop = c.cast(main_loop.contents.userdata, c.POINTER(c.py_object)).contents.value
    event = PythonDeferEvent(python_main_loop, cb, userdata)
    event.enable(True)
    return event.self_pointer.value


@pa_defer_enable_t
def aio_defer_enable(e: pa_defer_event_p, enable: bool) -> None:
    event: PythonDeferEvent = c.cast(e, c.POINTER(c.py_object)).contents.value
    event.enable(enable)


@pa_defer_set_destroy_t
def aio_defer_set_destroy(e: pa_defer_event_p, cb: pa_defer_event_destroy_cb_t) -> None:
    event: PythonDeferEvent = c.cast(e, c.POINTER(c.py_object)).contents.value
    event.set_destroy(cb)


@pa_defer_free_t
def aio_defer_free(e: pa_io_event_p) -> None:
    event: PythonDeferEvent = c.cast(e, c.POINTER(c.py_object)).contents.value
    event.free()


@pa_quit_t
def aio_quit(main_loop: c.POINTER(pa_mainloop_api), retval: int) -> None:
    python_main_loop: PythonMainLoop = c.cast(main_loop.contents.userdata, c.POINTER(c.py_object)).contents.value
    python_main_loop.stop(retval)
