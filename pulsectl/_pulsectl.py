# -*- coding: utf-8 -*-
from __future__ import print_function


# C Bindings

import os, sys, functools as ft
from ctypes import *


force_str = lambda s, errors='strict': s.decode('utf-8', errors) if isinstance(s, bytes) else s
force_bytes = lambda s, errors='strict': s.encode('utf-8', errors) if isinstance(s, unicode) else s

if sys.version_info.major >= 3:
	class c_str_p_type(object):
		c_type = c_char_p
		def __call__(self, val): return force_str(val)
		def from_param(self, val):
			# int will be interpreted as pointer and segfault in py3
			if isinstance(val, int): raise ArgumentError(type(val))
			return force_bytes(val)
	unicode, c_str_p = str, c_str_p_type()

	import time
	mono_time = time.monotonic

else:
	c_str_p = c_char_p

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


PA_INVALID = 2**32-1

PA_VOLUME_NORM = 0x10000
PA_VOLUME_MAX = 2**32-1 // 2
PA_VOLUME_INVALID = 2**32-1

# pa_sw_volume_from_dB = lambda db:\
# 	min(PA_VOLUME_MAX, int(round(((10.0 ** (db / 20.0)) ** 3) * PA_VOLUME_NORM)))
PA_VOLUME_UI_MAX = 2927386 # pa_sw_volume_from_dB(+11.0)

PA_CHANNELS_MAX = 32
PA_USEC_T = c_uint64

PA_CONTEXT_NOAUTOSPAWN = 0x0001
PA_CONTEXT_NOFAIL = 0x0002

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

PA_ENCODING_ANY = 0
PA_ENCODING_PCM = 1
PA_ENCODING_AC3_IEC61937 = 2
PA_ENCODING_EAC3_IEC61937 = 3
PA_ENCODING_MPEG_IEC61937 = 4
PA_ENCODING_DTS_IEC61937 = 5
PA_ENCODING_MPEG2_AAC_IEC61937 = 6
PA_ENCODING_INVALID = -1

PA_SAMPLE_U8 = 0
PA_SAMPLE_ALAW = 1
PA_SAMPLE_ULAW = 2
PA_SAMPLE_S16LE = 3
PA_SAMPLE_S16BE = 4
PA_SAMPLE_FLOAT32LE = 5
PA_SAMPLE_FLOAT32BE = 6
PA_SAMPLE_S32LE = 7
PA_SAMPLE_S32BE = 8
PA_SAMPLE_S24LE = 9
PA_SAMPLE_S24BE = 10
PA_SAMPLE_S24_32LE = 11
PA_SAMPLE_S24_32BE = 12
PA_SAMPLE_INVALID = -1

PA_STREAM_NOFLAGS = 0x0000
PA_STREAM_START_CORKED = 0x0001
PA_STREAM_INTERPOLATE_TIMING = 0x0002
PA_STREAM_NOT_MONOTONIC = 0x0004
PA_STREAM_AUTO_TIMING_UPDATE = 0x0008
PA_STREAM_NO_REMAP_CHANNELS = 0x0010
PA_STREAM_NO_REMIX_CHANNELS = 0x0020
PA_STREAM_FIX_FORMAT = 0x0040
PA_STREAM_FIX_RATE = 0x0080
PA_STREAM_FIX_CHANNELS = 0x0100
PA_STREAM_DONT_MOVE = 0x0200
PA_STREAM_VARIABLE_RATE = 0x0400
PA_STREAM_PEAK_DETECT = 0x0800
PA_STREAM_START_MUTED = 0x1000
PA_STREAM_ADJUST_LATENCY = 0x2000
PA_STREAM_EARLY_REQUESTS = 0x4000
PA_STREAM_DONT_INHIBIT_AUTO_SUSPEND = 0x8000
PA_STREAM_START_UNMUTED = 0x10000
PA_STREAM_FAIL_ON_SUSPEND = 0x20000
PA_STREAM_RELATIVE_VOLUME = 0x40000
PA_STREAM_PASSTHROUGH = 0x80000

def c_enum_map(**values):
	return dict((v, force_str(k)) for k,v in values.items())

_globals = globals().copy()

PA_STREAM_FLAGS = dict()
PA_ENCODING_MAP, PA_SAMPLE_MAP = dict(), dict()
PA_EVENT_FACILITY_MAP, PA_EVENT_MASK_MAP = dict(), dict()
PA_EVENT_TYPE_MAP = dict(
	(force_str(k), _globals['PA_SUBSCRIPTION_EVENT_{}'.format(k.upper())])
	for k in 'new change remove'.split() )

for k, n in _globals.items():
	if k.startswith('PA_SUBSCRIPTION_EVENT_'):
		if k.endswith('_MASK'): continue
		k = force_str(k[22:].lower())
		if k in PA_EVENT_TYPE_MAP: continue
		assert n & PA_SUBSCRIPTION_EVENT_FACILITY_MASK == n, [k, n]
		PA_EVENT_FACILITY_MAP[k] = n
	elif k.startswith('PA_SUBSCRIPTION_MASK_'):
		PA_EVENT_MASK_MAP[force_str(k[21:].lower())] = n
	elif k.startswith('PA_ENCODING_'): PA_ENCODING_MAP[k[12:].lower()] = n
	elif k.startswith('PA_SAMPLE_'): PA_SAMPLE_MAP[k[10:].lower()] = n
	elif k.startswith('PA_STREAM_'): PA_STREAM_FLAGS[k[10:].lower()] = n

PA_STREAM_FLAGS = c_enum_map(**PA_STREAM_FLAGS)
PA_ENCODING_MAP = c_enum_map(**PA_ENCODING_MAP)
PA_SAMPLE_MAP = c_enum_map(**PA_SAMPLE_MAP)
PA_EVENT_TYPE_MAP = c_enum_map(**PA_EVENT_TYPE_MAP)
PA_EVENT_FACILITY_MAP = c_enum_map(**PA_EVENT_FACILITY_MAP)
PA_EVENT_MASK_MAP = c_enum_map(**PA_EVENT_MASK_MAP)

PA_UPDATE_MAP = c_enum_map(set=0, merge=1, replace=2)
PA_PORT_AVAILABLE_MAP = c_enum_map(unknown=0, no=1, yes=2)
PA_STREAM_STATE_MAP = c_enum_map(unconnected=0, creating=1, ready=2, failed=3, terminated=4)

# These are defined separately as
#  pa_sink_state / pa_source_state, but seem to match.
PA_OBJ_STATE_MAP = c_enum_map(invalid=-1, running=0, idle=1, suspended=2)

del _globals


class PA_MAINLOOP(Structure): pass
class PA_STREAM(Structure): pass
class PA_MAINLOOP_API(Structure): pass
class PA_CONTEXT(Structure): pass
class PA_PROPLIST(Structure): pass
class PA_OPERATION(Structure): pass
class PA_SIGNAL_EVENT(Structure): pass
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

class PA_FORMAT_INFO(Structure):
	_fields_ = [
		('encoding', c_int),
		('proplist', POINTER(PA_PROPLIST)),
	]

class PA_BUFFER_ATTR(Structure):
	_fields_ = [
		('maxlength', c_uint32),
		('tlength', c_uint32),
		('prebuf', c_uint32),
		('minreq', c_uint32),
		('fragsize', c_uint32),
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
		('available', c_int),
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
		('mute', c_int),
		('proplist', POINTER(PA_PROPLIST)),
		('corked', c_int),
		('has_volume', c_int),
		('volume_writable', c_int),
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
		('proplist', POINTER(PA_PROPLIST)),
		('configured_latency', PA_USEC_T),
		('base_volume', c_int),
		('state', c_int),
		('n_volume_steps', c_int),
		('card', c_uint32),
		('n_ports', c_uint32),
		('ports', POINTER(POINTER(PA_PORT_INFO))),
		('active_port', POINTER(PA_PORT_INFO)),
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
		('proplist', POINTER(PA_PROPLIST)),
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
		('proplist', POINTER(PA_PROPLIST)),
		('configured_latency', PA_USEC_T),
		('base_volume', c_int),
		('state', c_int),
		('n_volume_steps', c_int),
		('card', c_uint32),
		('n_ports', c_uint32),
		('ports', POINTER(POINTER(PA_PORT_INFO))),
		('active_port', POINTER(PA_PORT_INFO)),
	]

class PA_CLIENT_INFO(Structure):
	_fields_ = [
		('index', c_uint32),
		('name', c_char_p),
		('owner_module', c_uint32),
		('driver', c_char_p),
	]

class PA_SERVER_INFO(Structure):
	_fields_ = [
		('user_name', c_char_p),
		('host_name', c_char_p),
		('server_version', c_char_p),
		('server_name', c_char_p),
		('sample_spec', PA_SAMPLE_SPEC),
		('default_sink_name', c_char_p),
		('default_source_name', c_char_p),
		('cookie', c_uint32),
		('channel_map', PA_CHANNEL_MAP),
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
		('proplist', POINTER(PA_PROPLIST)),
	]

class PA_MODULE_INFO(Structure):
	_fields_ = [
		('index', c_uint32),
		('name', c_char_p),
		('argument', c_char_p),
		('n_used', c_uint32),
		('auto_unload', c_int),
		('proplist', POINTER(PA_PROPLIST)),
	]

class PA_EXT_STREAM_RESTORE_INFO(Structure):
	_fields_ = [
		('name', c_char_p),
		('channel_map', PA_CHANNEL_MAP),
		('volume', PA_CVOLUME),
		('device', c_char_p),
		('mute', c_int),
	]


class POLLFD(Structure):
	_fields_ = [
		('fd', c_int),
		('events', c_short),
		('revents', c_short),
	]


PA_POLL_FUNC_T = CFUNCTYPE(c_int,
	POINTER(POLLFD),
	c_ulong,
	c_int,
	c_void_p)

PA_SIGNAL_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_MAINLOOP_API),
	POINTER(c_int),
	c_int,
	c_void_p)

PA_STATE_CB_T = CFUNCTYPE(c_int,
	POINTER(PA_CONTEXT),
	c_void_p)

PA_STREAM_NOTIFY_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_STREAM),
	c_void_p)

PA_CLIENT_INFO_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_CONTEXT),
	POINTER(PA_CLIENT_INFO),
	c_int,
	c_void_p)

PA_SERVER_INFO_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_CONTEXT),
	POINTER(PA_SERVER_INFO),
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

PA_CONTEXT_INDEX_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_CONTEXT),
	c_uint32,
	c_void_p)

PA_CONTEXT_SUCCESS_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_CONTEXT),
	c_int,
	c_void_p)

PA_EXT_STREAM_RESTORE_TEST_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_CONTEXT),
	c_uint32,
	c_void_p)

PA_EXT_STREAM_RESTORE_READ_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_CONTEXT),
	POINTER(PA_EXT_STREAM_RESTORE_INFO),
	c_int,
	c_void_p)

PA_CARD_INFO_CB_T = CFUNCTYPE(None,
	POINTER(PA_CONTEXT),
	POINTER(PA_CARD_INFO),
	c_int,
	c_void_p)

PA_MODULE_INFO_CB_T = CFUNCTYPE(None,
	POINTER(PA_CONTEXT),
	POINTER(PA_MODULE_INFO),
	c_int,
	c_void_p)

PA_SUBSCRIBE_CB_T = CFUNCTYPE(c_void_p,
	POINTER(PA_CONTEXT),
	c_int,
	c_int,
	c_void_p)


class LibPulse(object):

	# func_def ::= arg_types_list | (arg_types_list, res_spec) | (res_spec, arg_types_list)
	# res_spec ::= ctypes_restype
	#  | res_proc_func | (ctypes_restype, res_proc_func)
	#  | res_spec_name_str | (ctypes_restype, res_spec_name_str)
	# res_spec_name_str ::= 'int_check_ge0' | 'pa_op' | ...
	func_defs = dict(
		pa_strerror=([c_int], c_str_p),
		pa_runtime_path=([c_str_p], (c_char_p, 'not_null')),
		pa_mainloop_new=(POINTER(PA_MAINLOOP)),
		pa_mainloop_get_api=([POINTER(PA_MAINLOOP)], POINTER(PA_MAINLOOP_API)),
		pa_mainloop_run=([POINTER(PA_MAINLOOP), POINTER(c_int)], c_int),
		pa_mainloop_prepare=([POINTER(PA_MAINLOOP), c_int], 'int_check_ge0'),
		pa_mainloop_poll=([POINTER(PA_MAINLOOP)], 'int_check_ge0'),
		pa_mainloop_dispatch=([POINTER(PA_MAINLOOP)], 'int_check_ge0'),
		pa_mainloop_iterate=([POINTER(PA_MAINLOOP), c_int, POINTER(c_int)], 'int_check_ge0'),
		pa_mainloop_wakeup=[POINTER(PA_MAINLOOP)],
		pa_mainloop_set_poll_func=[POINTER(PA_MAINLOOP), PA_POLL_FUNC_T, c_void_p],
		pa_mainloop_quit=([POINTER(PA_MAINLOOP), c_int]),
		pa_mainloop_free=[POINTER(PA_MAINLOOP)],
		pa_signal_init=([POINTER(PA_MAINLOOP_API)], 'int_check_ge0'),
		pa_signal_new=([c_int, PA_SIGNAL_CB_T, POINTER(PA_SIGNAL_EVENT)]),
		pa_signal_done=None,
		pa_context_errno=([POINTER(PA_CONTEXT)], c_int),
		pa_context_new=([POINTER(PA_MAINLOOP_API), c_str_p], POINTER(PA_CONTEXT)),
		pa_context_set_state_callback=([POINTER(PA_CONTEXT), PA_STATE_CB_T, c_void_p]),
		pa_context_connect=([POINTER(PA_CONTEXT), c_str_p, c_int, POINTER(c_int)], 'int_check_ge0'),
		pa_context_get_state=([POINTER(PA_CONTEXT)], c_int),
		pa_context_disconnect=[POINTER(PA_CONTEXT)],
		pa_context_drain=( 'pa_op',
			[POINTER(PA_CONTEXT), PA_CONTEXT_DRAIN_CB_T, c_void_p] ),
		pa_context_set_default_sink=( 'pa_op',
			[POINTER(PA_CONTEXT), c_str_p, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_set_default_source=( 'pa_op',
			[POINTER(PA_CONTEXT), c_str_p, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_get_sink_input_info_list=( 'pa_op',
			[POINTER(PA_CONTEXT), PA_SINK_INPUT_INFO_CB_T, c_void_p] ),
		pa_context_get_sink_input_info=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, PA_SINK_INPUT_INFO_CB_T, c_void_p] ),
		pa_context_get_sink_info_list=( 'pa_op',
			[POINTER(PA_CONTEXT), PA_SINK_INFO_CB_T, c_void_p] ),
		pa_context_get_sink_info_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, PA_SINK_INFO_CB_T, c_void_p] ),
		pa_context_set_sink_mute_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, c_int, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_suspend_sink_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, c_int, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_set_sink_port_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, c_str_p, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_set_sink_input_mute=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, c_int, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_set_sink_volume_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, POINTER(PA_CVOLUME), PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_set_sink_input_volume=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, POINTER(PA_CVOLUME), PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_move_sink_input_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, c_uint32, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_get_source_output_info=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, PA_SOURCE_OUTPUT_INFO_CB_T, c_void_p] ),
		pa_context_get_source_output_info_list=( 'pa_op',
			[POINTER(PA_CONTEXT), PA_SOURCE_OUTPUT_INFO_CB_T, c_void_p] ),
		pa_context_move_source_output_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, c_uint32, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_set_source_output_volume=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, POINTER(PA_CVOLUME), PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_set_source_output_mute=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, c_int, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_kill_source_output=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_get_source_info_list=( 'pa_op',
			[POINTER(PA_CONTEXT), PA_SOURCE_INFO_CB_T, c_void_p] ),
		pa_context_get_source_info_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, PA_SOURCE_INFO_CB_T, c_void_p] ),
		pa_context_set_source_volume_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, POINTER(PA_CVOLUME), PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_set_source_mute_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, c_int, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_suspend_source_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, c_int, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_set_source_port_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, c_str_p, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_get_client_info_list=( 'pa_op',
			[POINTER(PA_CONTEXT), PA_CLIENT_INFO_CB_T, c_void_p] ),
		pa_context_get_client_info=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, PA_CLIENT_INFO_CB_T, c_void_p] ),
		pa_context_get_server_info=( 'pa_op',
			[POINTER(PA_CONTEXT), PA_SERVER_INFO_CB_T, c_void_p] ),
		pa_operation_unref=([POINTER(PA_OPERATION)], c_int),
		pa_context_get_card_info_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, PA_CARD_INFO_CB_T, c_void_p] ),
		pa_context_get_card_info_list=( 'pa_op',
			[POINTER(PA_CONTEXT), PA_CARD_INFO_CB_T, c_void_p] ),
		pa_context_set_card_profile_by_index=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, c_str_p, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_get_module_info=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, PA_MODULE_INFO_CB_T, c_void_p] ),
		pa_context_get_module_info_list=( 'pa_op',
			[POINTER(PA_CONTEXT), PA_MODULE_INFO_CB_T, c_void_p] ),
		pa_context_load_module=( 'pa_op',
			[POINTER(PA_CONTEXT), c_char_p, c_char_p, PA_CONTEXT_INDEX_CB_T, c_void_p] ),
		pa_context_unload_module=( 'pa_op',
			[POINTER(PA_CONTEXT), c_uint32, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_subscribe=( 'pa_op',
			[POINTER(PA_CONTEXT), c_int, PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_ext_stream_restore_test=( 'pa_op',
			[POINTER(PA_CONTEXT), PA_EXT_STREAM_RESTORE_TEST_CB_T, c_void_p] ),
		pa_ext_stream_restore_read=( 'pa_op',
			[POINTER(PA_CONTEXT), PA_EXT_STREAM_RESTORE_READ_CB_T, c_void_p] ),
		pa_ext_stream_restore_write=( 'pa_op', [
			POINTER(PA_CONTEXT), c_int, POINTER(PA_EXT_STREAM_RESTORE_INFO),
			c_uint, c_int, PA_CONTEXT_SUCCESS_CB_T, c_void_p ] ),
		pa_ext_stream_restore_delete=( 'pa_op',
			[POINTER(PA_CONTEXT), POINTER(c_char_p), PA_CONTEXT_SUCCESS_CB_T, c_void_p] ),
		pa_context_set_subscribe_callback=[POINTER(PA_CONTEXT), PA_SUBSCRIBE_CB_T, c_void_p],
		pa_proplist_new=(POINTER(PA_PROPLIST)),
		pa_proplist_free=[POINTER(PA_PROPLIST)],
		pa_proplist_iterate=([POINTER(PA_PROPLIST), POINTER(c_void_p)], c_str_p),
		pa_proplist_gets=([POINTER(PA_PROPLIST), c_str_p], c_str_p),
		pa_proplist_sets=([POINTER(PA_PROPLIST), c_str_p, c_str_p], 'int_check_ge0'),
		pa_channel_map_init_mono=(
			[POINTER(PA_CHANNEL_MAP)], (POINTER(PA_CHANNEL_MAP), 'not_null') ),
		pa_channel_map_init_stereo=(
			[POINTER(PA_CHANNEL_MAP)], (POINTER(PA_CHANNEL_MAP), 'not_null') ),
		pa_channel_map_snprint=([c_str_p, c_int, POINTER(PA_CHANNEL_MAP)], c_str_p),
		pa_channel_map_parse=(
			[POINTER(PA_CHANNEL_MAP), c_str_p], (POINTER(PA_CHANNEL_MAP), 'not_null') ),
		pa_format_info_snprint=([c_str_p, c_int, POINTER(PA_FORMAT_INFO)], c_str_p),
		pa_format_info_from_string=([c_str_p], POINTER(PA_FORMAT_INFO)),
		pa_format_info_free=[POINTER(PA_FORMAT_INFO)],
		pa_stream_new_extended=(
			[ POINTER(PA_CONTEXT), c_str_p,
				POINTER(POINTER(PA_FORMAT_INFO)), c_uint, POINTER(PA_PROPLIST) ],
			(POINTER(PA_STREAM), 'not_null') ),
		pa_stream_connect_playback=([
			POINTER(PA_STREAM), c_str_p, POINTER(PA_BUFFER_ATTR),
			c_uint, POINTER(PA_CVOLUME), POINTER(PA_STREAM) ], 'int_check_ge0'),
		pa_stream_disconnect=([POINTER(PA_STREAM)], 'int_check_ge0'),
		pa_stream_unref=([POINTER(PA_STREAM)]),
		pa_stream_get_state=([POINTER(PA_STREAM)], c_int),
		pa_stream_set_state_callback=([POINTER(PA_STREAM), PA_STREAM_NOTIFY_CB_T, c_void_p]) )

	class CallError(Exception): pass


	def __init__(self):
		p = CDLL('libpulse.so.0')

		self.funcs = dict()
		for k, spec in self.func_defs.items():
			func, args, res_proc = getattr(p, k), None, None
			if spec:
				if not isinstance(spec, tuple): spec = (spec,)
				for v in spec:
					assert v, [k, spec, v]
					if isinstance(v, list): args = v
					else: res_proc = v
			func_k = k if not k.startswith('pa_') else k[3:]
			self.funcs[func_k] = self._func_wrapper(k, func, args, res_proc)

	def _func_wrapper(self, func_name, func, args=list(), res_proc=None):
		func.restype, func.argtypes = None, args
		if isinstance(res_proc, tuple): func.restype, res_proc = res_proc
		if isinstance(res_proc, str):
			if res_proc.startswith('int_check_'): func.restype = c_int
			elif res_proc == 'pa_op': func.restype = POINTER(PA_OPERATION)
		elif not func.restype and hasattr(res_proc, 'c_type'): func.restype = res_proc.c_type
		elif not func.restype: func.restype, res_proc = res_proc, None

		def _wrapper(*args):
			# print('libpulse call:', func_name, args, file=sys.stderr)
			# sys.stderr.flush()
			res = func(*args)
			if isinstance(res_proc, str):
				assert res_proc in ['int_check_ge0', 'pa_op', 'not_null']
				if (res_proc == 'int_check_ge0' and res < 0)\
						or (res_proc == 'pa_op' and not res)\
						or (res_proc == 'not_null' and not res):
					err = [func_name, args, res]
					if args and isinstance(getattr(args[0], 'contents', None), PA_CONTEXT):
						errno_ = self.context_errno(args[0])
						err.append('{} [pulse errno {}]'.format(self.strerror(errno_), errno_))
					else: err.append('Return value check failed: {}'.format(res_proc))
					raise self.CallError(*err)
			elif res_proc: res = res_proc(res)
			return res

		_wrapper.__name__ = 'libpulse.{}'.format(func_name)
		return _wrapper

	def __getattr__(self, k): return self.funcs[k]

	def return_value(self): return pointer(c_int())

pa = LibPulse()
