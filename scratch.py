import sys
from pulsectl import pulsectl

pulse = pulsectl.Pulse('t')


print("test")
sys.settrace(pulse.proplist_set(next(filter(lambda x: x.description == 'MySink', pulse.source_list())), "description", "test"))