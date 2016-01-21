# -*- coding: utf-8 -*-

# C Bindings

import errno, functools as ft
from ctypes import *


class ResCheckError(Exception): pass

def _check(res, gt0=False, not_null=False):
	if res < 0 or (gt0 and res == 0) or (not_null and res):
		errno_ = get_errno()
		raise ResCheckError(os.strerror(errno_), res, errno_)
	return res

def check(**check_kws):
	return ft.partial(_check, **check_kws)


p = CDLL('libpulse.so.0')

PA_VOLUME_NORM = 65536
PA_CHANNELS_MAX = 32
PA_USEC_T = c_uint64

PA_CONTEXT_UNCONNECTED = 0
PA_CONTEXT_CONNECTING = 1
PA_CONTEXT_AUTHORIZING = 2
PA_CONTEXT_SETTING_NAME = 3
PA_CONTEXT_READY = 4
PA_CONTEXT_FAILED = 5
PA_CONTEXT_TERMINATED = 6

PA_SUBSCRIPTION_MASK_NULL = 0x0000
PA_SUBSCRIPTION_MASK_SINK = 0x0001
PA_SUBSCRIPTION_MASK_SOURCE = 0x0002
PA_SUBSCRIPTION_MASK_SINK_INPUT = 0x0004
PA_SUBSCRIPTION_MASK_SOURCE_OUTPUT = 0x0008
PA_SUBSCRIPTION_MASK_MODULE = 0x0010
PA_SUBSCRIPTION_MASK_CLIENT = 0x0020
PA_SUBSCRIPTION_MASK_SAMPLE_CACHE = 0x0040
PA_SUBSCRIPTION_MASK_SERVER = 0x0080
PA_SUBSCRIPTION_MASK_AUTOLOAD = 0x0100
PA_SUBSCRIPTION_MASK_CARD = 0x0200
PA_SUBSCRIPTION_MASK_ALL = 0x02ff

PA_SUBSCRIPTION_EVENT_SINK = 0x0000
PA_SUBSCRIPTION_EVENT_SOURCE = 0x0001
PA_SUBSCRIPTION_EVENT_SINK_INPUT = 0x0002
PA_SUBSCRIPTION_EVENT_SOURCE_OUTPUT = 0x0003
PA_SUBSCRIPTION_EVENT_MODULE = 0x0004
PA_SUBSCRIPTION_EVENT_CLIENT = 0x0005
PA_SUBSCRIPTION_EVENT_SAMPLE_CACHE = 0x0006
PA_SUBSCRIPTION_EVENT_SERVER = 0x0007
PA_SUBSCRIPTION_EVENT_AUTOLOAD = 0x0008
PA_SUBSCRIPTION_EVENT_CARD = 0x0009
PA_SUBSCRIPTION_EVENT_FACILITY_MASK = 0x000F
PA_SUBSCRIPTION_EVENT_NEW = 0x0000
PA_SUBSCRIPTION_EVENT_CHANGE = 0x0010
PA_SUBSCRIPTION_EVENT_REMOVE = 0x0020
PA_SUBSCRIPTION_EVENT_TYPE_MASK = 0x0030


class PA_MAINLOOP(Structure): pass
class PA_STREAM(Structure): pass
class PA_MAINLOOP_API(Structure): pass
class PA_CONTEXT(Structure): pass
class PA_OPERATION(Structure): pass
class PA_IO_EVENT(Structure): pass


class PA_SAMPLE_SPEC(Structure):
	_fields_ = [
		('format', c_int),
		('rate', c_uint32),
		('channels', c_uint32)
	]


class PA_CHANNEL_MAP(Structure):
	_fields_ = [
		('channels', c_uint8),
		('map', c_int * PA_CHANNELS_MAX)
	]


class PA_CVOLUME(Structure):
	_fields_ = [
		('channels', c_uint8),
		('values', c_uint32 * PA_CHANNELS_MAX)
	]


class PA_PORT_INFO(Structure):
	_fields_ = [
		('name', c_char_p),
		('description', c_char_p),
		('priority', c_uint32),
	]


class PA_SINK_INPUT_INFO(Structure):
	_fields_ = [
		('index', c_uint32),
		('name', c_char_p),
		('owner_module', c_uint32),
		('client', c_uint32),
		('sink', c_uint32),
		('sample_spec', PA_SAMPLE_SPEC),
		('channel_map', PA_CHANNEL_MAP),
		('volume', PA_CVOLUME),
		('buffer_usec', PA_USEC_T),
		('sink_usec', PA_USEC_T),
		('resample_method', c_char_p),
		('driver', c_char_p),
		('mute', c_int)
	]


class PA_SINK_INFO(Structure):
	_fields_ = [
		('name', c_char_p),
		('index', c_uint32),
		('description', c_char_p),
		('sample_spec', PA_SAMPLE_SPEC),
		('channel_map', PA_CHANNEL_MAP),
		('owner_module', c_uint32),
		('volume', PA_CVOLUME),
		('mute', c_int),
		('monitor_source', c_uint32),
		('monitor_source_name', c_char_p),
		('latency', PA_USEC_T),
		('driver', c_char_p),
		('flags', c_int),
		('proplist', POINTER(c_int)),
		('configured_latency', PA_USEC_T),
		('base_volume', c_int),
		('state', c_int),
		('n_volume_steps', c_int),
		('card', c_uint32),
		('n_ports', c_uint32),
		('ports', POINTER(POINTER(PA_PORT_INFO))),
		('active_port', POINTER(PA_PORT_INFO))
	]


class PA_SOURCE_OUTPUT_INFO(Structure):
	_fields_ = [
		('index', c_uint32),
		('name', c_char_p),
		('owner_module', c_uint32),
		('client', c_uint32),
		('source', c_uint32),
		('sample_spec', PA_SAMPLE_SPEC),
		('channel_map', PA_CHANNEL_MAP),
		('buffer_usec', PA_USEC_T),
		('source_usec', PA_USEC_T),
		('resample_method', c_char_p),
		('driver', c_char_p),
		('proplist', POINTER(c_int)),
		('corked', c_int),
		('volume', PA_CVOLUME),
		('mute', c_int),
		('has_volume', c_int),
		('volume_writable', c_int),
	]


class PA_SOURCE_INFO(Structure):
	_fields_ = [
		('name', c_char_p),
		('index', c_uint32),
		('description', c_char_p),
		('sample_spec', PA_SAMPLE_SPEC),
		('channel_map', PA_CHANNEL_MAP),
		('owner_module', c_uint32),
		('volume', PA_CVOLUME),
		('mute', c_int),
		('monitor_of_sink', c_uint32),
		('monitor_of_sink_name', c_char_p),
		('latency', PA_USEC_T),
		('driver', c_char_p),
		('flags', c_int),
		('proplist', POINTER(c_int)),
		('configured_latency', PA_USEC_T),
		('base_volume', c_int),
		('state', c_int),
		('n_volume_steps', c_int),
		('card', c_uint32),
		('n_ports', c_uint32),
		('ports', POINTER(POINTER(PA_PORT_INFO))),
		('active_port', POINTER(PA_PORT_INFO))
	]


class PA_CLIENT_INFO(Structure):
	_fields_ = [
		('index', c_uint32),
		('name', c_char_p),
		('owner_module', c_uint32),
		('driver', c_char_p)
	]


class PA_CARD_PROFILE_INFO(Structure):
	_fields_ = [
		('name', c_char_p),
		('description', c_char_p),
		('n_sinks', c_uint32),
		('n_sources', c_uint32),
		('priority', c_uint32),
	]


class PA_CARD_INFO(Structure):
	_fields_ = [
		('index', c_uint32),
		('name', c_char_p),
		('owner_module', c_uint32),
		('driver', c_char_p),
		('n_profiles', c_uint32),
		('profiles', POINTER(PA_CARD_PROFILE_INFO)),
		('active_profile', POINTER(PA_CARD_PROFILE_INFO)),
		('proplist', POINTER(c_int)),
	]


PA_SIGNAL_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_MAINLOOP_API),
	POINTER(c_int),
	c_int,
	c_void_p)

PA_STATE_CB_T = CFUNCTYPE(c_int,
	POINTER(PA_CONTEXT),
	c_void_p)

PA_CLIENT_INFO_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_CONTEXT),
	POINTER(PA_CLIENT_INFO),
	c_int,
	c_void_p)

PA_SINK_INPUT_INFO_CB_T = CFUNCTYPE(c_int,
	POINTER(PA_CONTEXT),
	POINTER(PA_SINK_INPUT_INFO),
	c_int,
	c_void_p)

PA_SINK_INFO_CB_T = CFUNCTYPE(c_int,
	POINTER(PA_CONTEXT),
	POINTER(PA_SINK_INFO),
	c_int,
	c_void_p)

PA_SOURCE_OUTPUT_INFO_CB_T = CFUNCTYPE(c_int,
	POINTER(PA_CONTEXT),
	POINTER(PA_SOURCE_OUTPUT_INFO),
	c_int,
	c_void_p)

PA_SOURCE_INFO_CB_T = CFUNCTYPE(c_int,
	POINTER(PA_CONTEXT),
	POINTER(PA_SOURCE_INFO),
	c_int,
	c_void_p)

PA_CONTEXT_DRAIN_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_CONTEXT),
	c_void_p)

PA_CONTEXT_SUCCESS_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_CONTEXT),
	c_int,
	c_void_p)

PA_CARD_INFO_CB_T = CFUNCTYPE(None,
	POINTER(PA_CONTEXT),
	POINTER(PA_CARD_INFO),
	c_int,
	c_void_p)

PA_SUBSCRIBE_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_CONTEXT),
	c_int,
	c_int,
	c_void_p)


pa_strerror = p.pa_strerror
pa_strerror.restype = c_char_p
pa_strerror.argtypes = [c_int]

pa_mainloop_new = p.pa_mainloop_new
pa_mainloop_new.restype = POINTER(PA_MAINLOOP)
pa_mainloop_new.argtypes = []

pa_mainloop_get_api = p.pa_mainloop_get_api
pa_mainloop_get_api.restype = POINTER(PA_MAINLOOP_API)
pa_mainloop_get_api.argtypes = [POINTER(PA_MAINLOOP)]

pa_mainloop_run = p.pa_mainloop_run
pa_mainloop_run.restype = c_int
pa_mainloop_run.argtypes = [POINTER(PA_MAINLOOP), POINTER(c_int)]

pa_mainloop_prepare = p.pa_mainloop_prepare
pa_mainloop_prepare.restype = check()
pa_mainloop_prepare.argtypes = [POINTER(PA_MAINLOOP), c_int]

pa_mainloop_poll = p.pa_mainloop_poll
pa_mainloop_poll.restype = check()
pa_mainloop_poll.argtypes = [POINTER(PA_MAINLOOP)]

pa_mainloop_dispatch = p.pa_mainloop_dispatch
pa_mainloop_dispatch.restype = check()
pa_mainloop_dispatch.argtypes = [POINTER(PA_MAINLOOP)]

pa_mainloop_iterate = p.pa_mainloop_iterate
pa_mainloop_iterate.restype = check()
pa_mainloop_iterate.argtypes = [POINTER(PA_MAINLOOP), c_int, POINTER(c_int)]

pa_mainloop_quit = p.pa_mainloop_quit
pa_mainloop_quit.restype = None
pa_mainloop_quit.argtypes = [POINTER(PA_MAINLOOP), c_int]

pa_mainloop_free = p.pa_mainloop_free
pa_mainloop_free.restype = None
pa_mainloop_free.argtypes = [POINTER(PA_MAINLOOP)]

pa_signal_init = p.pa_signal_init
pa_signal_init.restype = check()
pa_signal_init.argtypes = [POINTER(PA_MAINLOOP_API)]

pa_signal_new = p.pa_signal_new
pa_signal_new.restype = None
pa_signal_new.argtypes = [c_int, PA_SIGNAL_CB_T, POINTER(c_int)]

pa_signal_done = p.pa_signal_done
pa_signal_done.restype = None
pa_signal_done.argtypes = []

pa_context_errno = p.pa_context_errno
pa_context_errno.restype = c_int
pa_context_errno.argtypes = [POINTER(PA_CONTEXT)]

pa_context_new = p.pa_context_new
pa_context_new.restype = POINTER(PA_CONTEXT)
pa_context_new.argtypes = [POINTER(PA_MAINLOOP_API), c_char_p]

pa_context_set_state_callback = p.pa_context_set_state_callback
pa_context_set_state_callback.restype = None
pa_context_set_state_callback.argtypes = [
	POINTER(PA_CONTEXT),
	PA_STATE_CB_T,
	c_void_p
]

pa_context_connect = p.pa_context_connect
pa_context_connect.restype = c_int
pa_context_connect.argtypes = [
	POINTER(PA_CONTEXT),
	c_char_p,
	c_int,
	POINTER(c_int)
]

pa_context_get_state = p.pa_context_get_state
pa_context_get_state.restype = c_int
pa_context_get_state.argtypes = [POINTER(PA_CONTEXT)]

pa_context_drain = p.pa_context_drain
pa_context_drain.restype = POINTER(PA_OPERATION)
pa_context_drain.argtypes = [
	POINTER(PA_CONTEXT),
	PA_CONTEXT_DRAIN_CB_T,
	c_void_p
]

pa_context_disconnect = p.pa_context_disconnect
pa_context_disconnect.restype = None
pa_context_disconnect.argtypes = [POINTER(PA_CONTEXT)]

pa_context_get_sink_input_info_list = p.pa_context_get_sink_input_info_list
pa_context_get_sink_input_info_list.restype = POINTER(c_int)
pa_context_get_sink_input_info_list.argtypes = [
	POINTER(PA_CONTEXT),
	PA_SINK_INPUT_INFO_CB_T,
	c_void_p
]

pa_context_get_sink_info_list = p.pa_context_get_sink_info_list
pa_context_get_sink_info_list.restype = POINTER(c_int)
pa_context_get_sink_info_list.argtypes = [
	POINTER(PA_CONTEXT),
	PA_SINK_INFO_CB_T,
	c_void_p
]

pa_context_set_sink_mute_by_index = p.pa_context_set_sink_mute_by_index
pa_context_set_sink_mute_by_index.restype = POINTER(c_int)
pa_context_set_sink_mute_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	c_int,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_suspend_sink_by_index = p.pa_context_suspend_sink_by_index
pa_context_suspend_sink_by_index.restype = POINTER(c_int)
pa_context_suspend_sink_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	c_int,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_set_sink_port_by_index = p.pa_context_set_sink_port_by_index
pa_context_set_sink_port_by_index.restype = POINTER(c_int)
pa_context_set_sink_port_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	c_char_p,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_set_sink_input_mute = p.pa_context_set_sink_input_mute
pa_context_set_sink_input_mute.restype = POINTER(c_int)
pa_context_set_sink_input_mute.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	c_int,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_set_sink_volume_by_index = p.pa_context_set_sink_volume_by_index
pa_context_set_sink_volume_by_index.restype = POINTER(c_int)
pa_context_set_sink_volume_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	POINTER(PA_CVOLUME),
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_set_sink_input_volume = p.pa_context_set_sink_input_volume
pa_context_set_sink_input_volume.restype = POINTER(c_int)
pa_context_set_sink_input_volume.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	POINTER(PA_CVOLUME),
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_move_sink_input_by_index = p.pa_context_move_sink_input_by_index
pa_context_move_sink_input_by_index.restype = POINTER(c_int)
pa_context_move_sink_input_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	c_uint32,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_get_source_output_info = p.pa_context_get_source_output_info
pa_context_get_source_output_info.restype = POINTER(c_int)
pa_context_get_source_output_info.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	PA_SOURCE_OUTPUT_INFO_CB_T,
	c_void_p
]

pa_context_get_source_output_info_list = p.pa_context_get_source_output_info_list
pa_context_get_source_output_info_list.restype = POINTER(c_int)
pa_context_get_source_output_info_list.argtypes = [
	POINTER(PA_CONTEXT),
	PA_SOURCE_OUTPUT_INFO_CB_T,
	c_void_p
]

pa_context_move_source_output_by_index = p.pa_context_move_source_output_by_index
pa_context_move_source_output_by_index.restype = POINTER(c_int)
pa_context_move_source_output_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	c_uint32,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_set_source_output_volume = p.pa_context_set_source_output_volume
pa_context_set_source_output_volume.restype = POINTER(c_int)
pa_context_set_source_output_volume.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	POINTER(PA_CVOLUME),
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_set_source_output_mute = p.pa_context_set_source_output_mute
pa_context_set_source_output_mute.restype = POINTER(c_int)
pa_context_set_source_output_mute.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	c_int,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_kill_source_output = p.pa_context_kill_source_output
pa_context_kill_source_output.restype = POINTER(c_int)
pa_context_kill_source_output.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_get_source_info_by_index = p.pa_context_get_source_info_by_index
pa_context_get_source_info_by_index.restype = POINTER(c_int)
pa_context_get_source_info_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	PA_SOURCE_INFO_CB_T,
	c_void_p
]

pa_context_get_source_info_list = p.pa_context_get_source_info_list
pa_context_get_source_info_list.restype = POINTER(c_int)
pa_context_get_source_info_list.argtypes = [
	POINTER(PA_CONTEXT),
	PA_SOURCE_INFO_CB_T,
	c_void_p
]

pa_context_set_source_volume_by_index = p.pa_context_set_source_volume_by_index
pa_context_set_source_volume_by_index.restype = POINTER(c_int)
pa_context_set_source_volume_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	POINTER(PA_CVOLUME),
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_set_source_volume_by_index = p.pa_context_set_source_volume_by_index
pa_context_set_source_volume_by_index.restype = POINTER(c_int)
pa_context_set_source_volume_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	POINTER(PA_CVOLUME),
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_set_source_mute_by_index = p.pa_context_set_source_mute_by_index
pa_context_set_source_mute_by_index.restype = POINTER(c_int)
pa_context_set_source_mute_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	c_int,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_suspend_source_by_index = p.pa_context_suspend_source_by_index
pa_context_suspend_source_by_index.restype = POINTER(c_int)
pa_context_suspend_source_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	c_int,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_set_source_port_by_index = p.pa_context_set_source_port_by_index
pa_context_set_source_port_by_index.restype = POINTER(c_int)
pa_context_set_source_port_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	c_char_p,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_get_client_info_list = p.pa_context_get_client_info_list
pa_context_get_client_info_list.restype = POINTER(c_int)
pa_context_get_client_info_list.argtypes = [
	POINTER(PA_CONTEXT),
	PA_CLIENT_INFO_CB_T,
	c_void_p
]

pa_context_get_client_info = p.pa_context_get_client_info
pa_context_get_client_info.restype = POINTER(c_int)
pa_context_get_client_info.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	PA_CLIENT_INFO_CB_T,
	c_void_p
]

pa_operation_unref = p.pa_operation_unref
pa_operation_unref.restype = c_int
pa_operation_unref.argtypes = [POINTER(PA_OPERATION)]

pa_context_get_card_info_by_index = p.pa_context_get_card_info_by_index
pa_context_get_card_info_by_index.restype = POINTER(PA_OPERATION)
pa_context_get_card_info_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	PA_CARD_INFO_CB_T,
	c_void_p
]

pa_context_get_card_info_list = p.pa_context_get_card_info_list
pa_context_get_card_info_list.restype = POINTER(PA_OPERATION)
pa_context_get_card_info_list.argtypes = [
	POINTER(PA_CONTEXT),
	PA_CARD_INFO_CB_T,
	c_void_p
]

pa_context_set_card_profile_by_index = p.pa_context_set_card_profile_by_index
pa_context_set_card_profile_by_index.restype = POINTER(PA_OPERATION)
pa_context_set_card_profile_by_index.argtypes = [
	POINTER(PA_CONTEXT),
	c_uint32,
	c_char_p,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_subscribe = p.pa_context_subscribe
pa_context_subscribe.restype = POINTER(PA_OPERATION)
pa_context_subscribe.argtypes = [
	POINTER(PA_CONTEXT),
	c_int,
	PA_CONTEXT_SUCCESS_CB_T,
	c_void_p
]

pa_context_set_subscribe_callback = p.pa_context_set_subscribe_callback
pa_context_set_subscribe_callback.restype = None
pa_context_set_subscribe_callback.argtypes = [
	POINTER(PA_CONTEXT),
	PA_SUBSCRIBE_CB_T,
	c_void_p
]

def pa_return_value(): return pointer(c_int())

def mono_time():
	if not hasattr(mono_time, 'ts'):
		class timespec(Structure):
			_fields_ = [('tv_sec', c_long), ('tv_nsec', c_long)]
		librt = CDLL('librt.so.1', use_errno=True)
		mono_time.get = librt.clock_gettime
		mono_time.get.argtypes = [c_int, POINTER(timespec)]
		mono_time.ts = timespec
	ts = mono_time.ts()
	if mono_time.get(4, pointer(ts)) != 0:
		err = get_errno()
		raise OSError(err, os.strerror(err))
	return ts.tv_sec + ts.tv_nsec * 1e-9
