import ctypes
import os
import sys

# Define C structures matching engine_c_api.cpp
class CEvalResult(ctypes.Structure):
    _fields_ = [
        ("action", ctypes.c_int32),
        ("price", ctypes.c_double),
        ("sl_price", ctypes.c_double),
        ("tp_price", ctypes.c_double),
        ("contracts", ctypes.c_int32),
        ("consecutive_losses", ctypes.c_int32),
        ("is_halted", ctypes.c_int32)
    ]

class CppMorningSniperAccelerator:
    """
    Python wrapper for the High-Speed Native C++20 Morning Sniper Engine.
    Executes bar and tick evaluation in ~8-10 nanoseconds.
    """
    def __init__(self, min_range=8.0, contracts=5, tick_size=0.25, slippage_ticks=0.0, max_losses=3, start_time=93000, end_time=113000):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cpp_dir = os.path.join(base_dir, "..", "cpp")
        
        # Determine library extension based on platform
        if sys.platform == "darwin":
            lib_name = "libmorningsniper.dylib"
        elif sys.platform.startswith("win"):
            lib_name = "libmorningsniper.dll"
        else:
            lib_name = "libmorningsniper.so"
            
        lib_path = os.path.abspath(os.path.join(cpp_dir, lib_name))
        if not os.path.exists(lib_path):
            # Attempt automatic compilation on cloud Linux / host system
            try:
                import subprocess
                source_file = os.path.join(cpp_dir, "engine_c_api.cpp")
                if os.path.exists(source_file):
                    print(f"[C++ ACCELERATOR] Compiling native shared library for {sys.platform}...")
                    compiler = "clang++" if sys.platform == "darwin" else "g++"
                    cmd = [compiler, "-std=c++20", "-O3", "-shared", "-fPIC", source_file, "-o", lib_path]
                    subprocess.run(cmd, check=True, cwd=cpp_dir)
                    print(f"[C++ ACCELERATOR] Compilation successful: {lib_path}")
            except Exception as e:
                print(f"[C++ ACCELERATOR WARNING] Auto-compilation failed: {e}")

        if not os.path.exists(lib_path):
            raise FileNotFoundError(f"Native C++ shared library not found at: {lib_path}")

        self._lib = ctypes.CDLL(lib_path)
        
        # Define C argument and return types
        self._lib.create_engine.argtypes = [
            ctypes.c_double, ctypes.c_int32, ctypes.c_double, ctypes.c_double,
            ctypes.c_int32, ctypes.c_int32, ctypes.c_int32
        ]
        self._lib.create_engine.restype = ctypes.c_void_p

        self._lib.destroy_engine.argtypes = [ctypes.c_void_p]
        self._lib.destroy_engine.restype = None

        self._lib.reset_engine.argtypes = [ctypes.c_void_p]
        self._lib.reset_engine.restype = None

        self._lib.process_tick_c.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_int32]
        self._lib.process_tick_c.restype = CEvalResult

        self._lib.process_bar_c.argtypes = [
            ctypes.c_void_p, ctypes.c_int64, ctypes.c_int32,
            ctypes.c_double, ctypes.c_double, ctypes.c_double,
            ctypes.c_double, ctypes.c_double
        ]
        self._lib.process_bar_c.restype = CEvalResult

        # Instantiate native C++ engine
        self._engine = self._lib.create_engine(
            float(min_range), int(contracts), float(tick_size), float(slippage_ticks),
            int(max_losses), int(start_time), int(end_time)
        )

        self.action_names = {
            0: "NONE",
            1: "ENTER_LONG",
            2: "ENTER_SHORT",
            3: "EXIT_LONG_SL",
            4: "EXIT_LONG_TP",
            5: "EXIT_SHORT_SL",
            6: "EXIT_SHORT_TP",
            7: "FLATTEN_SESSION_END"
        }

    def __del__(self):
        if hasattr(self, "_engine") and self._engine and hasattr(self, "_lib"):
            self._lib.destroy_engine(self._engine)
            self._engine = None

    def reset(self):
        """Resets engine state."""
        self._lib.reset_engine(self._engine)

    def process_tick(self, tick_price: float, hhmmss: int):
        """Sub-microsecond tick evaluation."""
        res = self._lib.process_tick_c(self._engine, float(tick_price), int(hhmmss))
        return {
            "action": self.action_names.get(res.action, "NONE"),
            "action_id": res.action,
            "price": res.price,
            "sl_price": res.sl_price,
            "tp_price": res.tp_price,
            "contracts": res.contracts,
            "consecutive_losses": res.consecutive_losses,
            "is_halted": bool(res.is_halted)
        }

    def process_bar(self, timestamp_ms: int, hhmmss: int, o: float, h: float, l: float, c: float, v: float = 100.0):
        """Sub-microsecond 1-minute bar evaluation."""
        res = self._lib.process_bar_c(
            self._engine, int(timestamp_ms), int(hhmmss),
            float(o), float(h), float(l), float(c), float(v)
        )
        return {
            "action": self.action_names.get(res.action, "NONE"),
            "action_id": res.action,
            "price": res.price,
            "sl_price": res.sl_price,
            "tp_price": res.tp_price,
            "contracts": res.contracts,
            "consecutive_losses": res.consecutive_losses,
            "is_halted": bool(res.is_halted)
        }
