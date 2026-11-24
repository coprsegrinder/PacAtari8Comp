"""Stage 66: the table layout of the core (which table lies where in the ROM and in the RAM `Start` builds).  It now lives in tools/core_tables.py, which derives the tables from the ROM at import;
this module keeps the old name for its users (tests/test_core.py, tools/make_c_tables.py).  Nothing is generated or written any more: no ROM byte is kept in a source file."""
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from core_tables import IMAGES, TABLES  # noqa: E402,F401
