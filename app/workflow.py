from .modules.m1_orders.service import resolve
from .modules.m2_substitutions.service import approve
from .modules.m3_windows.service import compile_windows
from .modules.m4_capacity.service import plan
from .modules.m5_allocation.service import allocate
from .modules.m6_reconcile.service import reconcile

TABLES = ('orders','substitutions','windows','trips','stock')
STAGES = (('orders',resolve),('substitutions',approve),('windows',compile_windows),
          ('capacity',plan),('allocation',allocate),('reconcile',reconcile))
