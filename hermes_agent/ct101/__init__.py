"""
CT101 — full native integration with Hermes Agent.

Domain (25 packages, 229 classes, 118 functions), infrastructure (30+
subsystems), C++ core (libtradeengine_core.so: 180 symbols, libultrafast.so:
10 symbols), and the full bot fleet (9+ bot classes + orchestrator + factory).

All code is imported directly — no MCP proxy, no subprocess bridge.  Every
domain module, every infrastructure service, and every C++ binding is
importable from this package.

Usage from any Hermes session (desktop or dashboard):
    from hermes_agent.ct101 import domain, infra, cpp, bots, overview
    overview()          # -> dict of agent/bot/trade/domain counts
    bots.fleet          # -> dict of all bot classes
    cpp.pattern_hash()  # -> sub-µs C++ hash
    domain.risk.EnhancedRiskEngine  # -> live risk engine
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Path setup ───────────────────────────────────────────────────────────────

_CT101_ROOT = Path(os.environ.get("CT101_ROOT", "/home/claude/timeshift/ct101")).resolve()
if str(_CT101_ROOT) not in sys.path:
    sys.path.insert(0, str(_CT101_ROOT))

# ── Environment ──────────────────────────────────────────────────────────────

_ENV_PATH = _CT101_ROOT / ".env"
_env: Dict[str, str] = {}
if _ENV_PATH.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(str(_ENV_PATH))
    except ImportError:
        pass

# ── OpenSSL preload (C++ bridge safety) ─────────────────────────────────────

def _preload_openssl() -> bool:
    """Preload system libcrypto/libssl so the C++ bridge doesn't segfault
    when TensorFlow/LLM libraries have loaded a conflicting libcrypto."""
    try:
        ctypes.CDLL("libcrypto.so.3", mode=ctypes.RTLD_GLOBAL)
        ctypes.CDLL("libssl.so.3", mode=ctypes.RTLD_GLOBAL)
        return True
    except OSError:
        try:
            ctypes.CDLL("libcrypto.so", mode=ctypes.RTLD_GLOBAL)
            ctypes.CDLL("libssl.so", mode=ctypes.RTLD_GLOBAL)
            return True
        except OSError:
            return False

_openssl_loaded = _preload_openssl()

# ═══════════════════════════════════════════════════════════════════════════════
# DOMAIN — every package, every class, every function
# ═══════════════════════════════════════════════════════════════════════════════

class _Domain:
    """Lazy-loaded domain packages. Access any package as an attribute;
    it imports on first use so slow packages (TensorFlow, neuromorphic)
    don't block the module load."""

    _loaded: Dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._loaded:
            return self._loaded[name]
        try:
            mod = __import__(f"domain.{name}", fromlist=[name])
            self._loaded[name] = mod
            return mod
        except Exception as e:
            self._loaded[name] = _ImportError(f"domain.{name}", e)
            return self._loaded[name]

    def __dir__(self) -> List[str]:
        return [
            "agents", "ai_growth", "alpha_generation", "backtesting",
            "bots", "capabilities", "common", "compounding", "events",
            "handlers", "learning", "licensing", "market", "memory",
            "memory_learning", "models", "neuromorphic", "portfolio",
            "regime_detection", "regulatory", "repos", "risk", "routing",
            "runtime", "services", "strategy", "trading",
        ]

    def catalog(self) -> Dict[str, Dict[str, Any]]:
        """AST catalog: every public class/function in every domain package."""
        import ast as _ast
        result: Dict[str, Dict[str, Any]] = {}
        domain_dir = _CT101_ROOT / "domain"
        if not domain_dir.is_dir():
            return result
        for pkg_dir in sorted(domain_dir.iterdir()):
            if not pkg_dir.is_dir() or pkg_dir.name.startswith("_"):
                continue
            classes: List[str] = []
            functions: List[str] = []
            for py_file in sorted(pkg_dir.rglob("*.py")):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    tree = _ast.parse(py_file.read_text())
                    for node in _ast.walk(tree):
                        if isinstance(node, _ast.ClassDef) and not node.name.startswith("_"):
                            classes.append(f"{py_file.stem}.{node.name}")
                        elif isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                            functions.append(f"{py_file.stem}.{node.name}")
                except SyntaxError:
                    pass
            result[pkg_dir.name] = {
                "classes": sorted(set(classes)),
                "functions": sorted(set(functions)),
                "class_count": len(set(c.rsplit(".", 1)[-1] for c in classes)),
                "function_count": len(set(f.rsplit(".", 1)[-1] for f in functions)),
            }
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# INFRASTRUCTURE — every subsystem
# ═══════════════════════════════════════════════════════════════════════════════

class _Infra:
    """Lazy-loaded infrastructure subsystems."""

    _loaded: Dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._loaded:
            return self._loaded[name]
        try:
            mod = __import__(f"infrastructure.{name}", fromlist=[name])
            self._loaded[name] = mod
            return mod
        except Exception as e:
            self._loaded[name] = _ImportError(f"infrastructure.{name}", e)
            return self._loaded[name]

    def __dir__(self) -> List[str]:
        return [
            "agents", "ai", "apis", "auth", "aws", "backtest", "backup",
            "cache", "chat", "cloud", "cloudflare", "common", "config",
            "control", "database", "deployment", "diagnostics", "discovery",
            "error_handling", "exchange", "extensions", "feeds", "gateway",
            "hermes", "mcp", "message_queue", "messaging", "micro",
            "missing", "ml", "monitoring", "network", "ops",
            "orchestration", "persistence", "queue", "runtime", "security",
            "services", "system", "trading", "training", "utils", "websocket",
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# C++ BRIDGE — every binding, every symbol, every indicator
# ═══════════════════════════════════════════════════════════════════════════════
#
# Libraries and their exported symbols:
#   libtradeengine_core.so    — 180 symbols (137 TA-Lib, 23 memory-bridge, 15 core, 5 misc)
#   libta_lib.so              — 1,314 symbols (full TA-Lib)
#   libultrafast.so           — 10 symbols (ultra-fast compute)
#   libbot_wrapper.so         — 10 symbols (bot lifecycle)
#   talib_full.py             — 158 Python-wrapped indicators
#   tradeengine_core_binding  — 18 functions + AWSMemoryBridgeBinding class
#   ultrafast_binding         — 20 functions + DecisionMatrix + UltrafastBinding
#   bot_wrapper_binding       — 5 functions + Bot class
#   cpp_bot_binding           — 1 function + 5 classes (CPPBotWrapper et al)
#

class _CppBridge:
    """Complete C++ bridge — every binding file, every exported function.

    Access patterns:
        cpp.core.pattern_hash(...)         # tradeengine_core_binding functions
        cpp.talib.catalogue()              # 158 TA-Lib indicators
        cpp.talib.call('RSI', ...)         # call any indicator by name
        cpp.ultrafast.calculate_indicators(...)
        cpp.bot_wrapper.create_bot(...)
        cpp.cpp_bot.CPPAcceleratedBot      # bot-level C++ wrapper
        cpp.ready                          # bool
        cpp.status                         # dict with per-module status
    """

    _initialized: bool = False
    _modules: Dict[str, Any] = {}
    _errors: Dict[str, str] = {}
    _indicator_names: List[str] = []

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        micro = _CT101_ROOT / "infrastructure" / "micro"
        sys.path.insert(0, str(micro))

        # ── tradeengine_core_binding (primary C++ bridge) ────────────────
        try:
            import tradeengine_core_binding as _core
            self._modules["core"] = _core
            # Expose module as attribute
            self.__dict__["core"] = _core
            # Convenience aliases for core functions (no collision risk — core is first)
            for _name in ("pattern_hash", "get_confidence_boost", "update_pattern_confidence",
                          "calc_indicators", "find_or_create_pattern", "save_pattern",
                          "get_pattern", "detect_candles", "save_memory_snapshot",
                          "load_memory_snapshot", "initialize", "cleanup", "is_available",
                          "check_available", "get_last_error", "AWSMemoryBridgeBinding"):
                if hasattr(_core, _name):
                    self.__dict__[_name] = getattr(_core, _name)
            try:
                _core.initialize()
            except Exception as e:
                self._errors["core_init"] = str(e)
        except ImportError as e:
            self._errors["core"] = str(e)

        # ── talib_full (158 indicators + catalogue) ─────────────────────
        try:
            import talib_full as _talib
            self._modules["talib"] = _talib
            self.__dict__["talib"] = _talib
            # Convenience: catalogue, call, value_at, scan_all
            for _name in ("catalogue", "call", "value_at", "scan_all", "evaluate",
                          "pattern_score", "available", "defaults", "lookback",
                          "FUNCS", "CDL_NAMES", "INDICATOR_NAMES"):
                if hasattr(_talib, _name):
                    self.__dict__[_name] = getattr(_talib, _name)
            try:
                self._indicator_names = sorted(_talib.catalogue().keys())
            except Exception:
                pass
        except ImportError as e:
            self._errors["talib"] = str(e)

        # ── ultrafast_binding (ultra-fast compute) ───────────────────────
        try:
            import ultrafast_binding as _ultra
            self._modules["ultrafast"] = _ultra
            self.__dict__["ultrafast"] = _ultra
            for _name in ("calculate_indicators", "calculate_indicators_at",
                          "build_decision_matrix", "get_matrix_size", "free_matrix",
                          "read_matrix", "matrix_values", "generate_pattern_hash",
                          "find_or_create_pattern", "update_pattern_confidence",
                          "get_confidence_boost", "save_memory_cache", "load_memory_cache",
                          "is_loaded", "is_available", "DecisionMatrix", "UltrafastBinding",
                          "SIGNATURES", "REQUIRED_SYMBOLS", "INDICATOR_KEYS", "LIB_PATH"):
                if hasattr(_ultra, _name):
                    self.__dict__["uf_" + _name] = getattr(_ultra, _name)
        except ImportError as e:
            self._errors["ultrafast"] = str(e)

        # ── bot_wrapper_binding (bot lifecycle) ──────────────────────────
        try:
            import bot_wrapper_binding as _bw
            self._modules["bot_wrapper"] = _bw
            self.__dict__["bot_wrapper"] = _bw
            for _name in ("Bot", "create_bot", "get_bot", "destroy_all", "live_count",
                          "EXPORTED", "DECLARED_NOT_EXPORTED", "ACTION_NAMES"):
                if hasattr(_bw, _name):
                    self.__dict__[_name] = getattr(_bw, _name)
        except ImportError as e:
            self._errors["bot_wrapper"] = str(e)

        # ── cpp_bot_binding (bot-level C++ wrapper) ──────────────────────
        try:
            from domain.bots.services import cpp_bot_binding as _cbot
            self._modules["cpp_bot"] = _cbot
            self.__dict__["cpp_bot"] = _cbot
            for _name in ("CPPBotWrapper", "CPPAcceleratedBot", "CPPBotBinding",
                          "TradingAction", "MarketRegime", "create_cpp_bot"):
                if hasattr(_cbot, _name):
                    self.__dict__[_name] = getattr(_cbot, _name)
        except ImportError as e:
            self._errors["cpp_bot"] = str(e)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        self._ensure_init()
        # Check instance attributes set during _ensure_init
        if name in self.__dict__:
            return self.__dict__[name]
        raise AttributeError(
            f"C++ bridge has no attribute '{name}'. "
            f"Loaded modules: {list(self._modules)}. "
            f"Errors: {self._errors}"
        )

    @property
    def ready(self) -> bool:
        self._ensure_init()
        return "core" in self._modules and "core_init" not in self._errors

    @property
    def status(self) -> Dict[str, Any]:
        self._ensure_init()
        return {
            "ready": self.ready,
            "modules_loaded": list(self._modules.keys()),
            "errors": dict(self._errors),
            "openssl_preloaded": _openssl_loaded,
            "indicator_count": len(self._indicator_names),
            "library_path": str(_CT101_ROOT / "infrastructure" / "micro" / "libtradeengine_core.so"),
        }

    def catalog(self) -> Dict[str, Any]:
        """Full inventory of every C++ symbol and binding available."""
        self._ensure_init()
        result: Dict[str, Any] = {"modules": {}, "total_functions": 0, "total_classes": 0}
        for mod_name, mod in self._modules.items():
            funcs = [n for n in dir(mod) if callable(getattr(mod, n, None)) and not n.startswith("_")]
            classes = [n for n in dir(mod) if isinstance(getattr(mod, n, None), type) and not n.startswith("_")]
            result["modules"][mod_name] = {
                "functions": sorted(funcs),
                "classes": sorted(classes),
                "function_count": len(funcs),
                "class_count": len(classes),
            }
            result["total_functions"] += len(funcs)
            result["total_classes"] += len(classes)
        result["indicator_count"] = len(self._indicator_names)
        result["indicator_names"] = self._indicator_names
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# BOT FLEET — every bot class, factory, orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

class _BotFleet:
    """Full bot fleet — every bot class, factory, orchestrator, manager.
    Each bot is imported individually; missing deps (flask, torch, etc.)
    are recorded but don't block the bots that can load."""

    _loaded: Dict[str, Any] = {}
    _fleet: Optional[Dict[str, Any]] = None
    _errors: Dict[str, str] = {}
    _init_done: bool = False

    # (import_path, attr, fleet_key)
    _FLEET_SPECS = [
        ("domain.bots.services.bot_factory", "BotFactory", None),
        ("domain.bots.services.cpp_memory_aware_bot", "CppMemoryAwareBot", "cpp_memory_aware"),
        ("domain.bots.services.autonomous_bot", "AutonomousBot", "autonomous"),
        ("domain.bots.services.adaptive_trading_bot", "AdaptiveTradingBot", "adaptive"),
        ("domain.bots.services.momentum_enhanced", "MomentumBot", "momentum"),
        ("domain.bots.services.momentum_turbo_bot", "MomentumTurboBot", "momentum_turbo"),
        ("domain.bots.services.montecarlo_enhanced_bot", "MonteCarloEnhancedBot", "montecarlo"),
        ("domain.bots.services.memory_aware_bot", "MemoryAwareBot", "memory_aware"),
        ("domain.bots.services.basbot_enhanced_orchestrator_production", "BasBotEnhancedOrchestratorProduction", "orchestrator"),
        ("domain.bots.services.bot_manager", "BotManager", None),
        ("domain.bots.services.bot_orchestrator", "BotOrchestrator", None),
        ("domain.bots.services.cpp_bot_binding", "CPPAcceleratedBot", "cpp_accelerated"),
        ("domain.bots.services.cpp_bot_binding", "CPPBotWrapper", None),
        ("domain.bots.services.base_bot", "EnhancedBaseBot", None),
    ]

    def _ensure_loaded(self) -> None:
        if self._init_done:
            return
        self._init_done = True
        self._fleet = {}
        self._loaded = {}
        self._errors = {}
        imported = {}  # module path -> module (cache)

        for module_path, attr, fleet_key in self._FLEET_SPECS:
            if module_path not in imported:
                try:
                    imported[module_path] = __import__(module_path, fromlist=[attr])
                except ImportError as e:
                    self._errors[module_path] = str(e)
                    continue
            mod = imported[module_path]
            try:
                cls = getattr(mod, attr)
            except AttributeError:
                self._errors[f"{module_path}.{attr}"] = "attribute not found"
                continue
            if fleet_key:
                self._fleet[fleet_key] = cls
            self._loaded[attr] = cls

    @property
    def fleet(self) -> Dict[str, Any]:
        self._ensure_loaded()
        return self._fleet

    @property
    def all_classes(self) -> Dict[str, Any]:
        self._ensure_loaded()
        return {**self._fleet, **self._loaded}

    @property
    def errors(self) -> Dict[str, str]:
        self._ensure_loaded()
        return self._errors

    @property
    def count(self) -> int:
        self._ensure_loaded()
        return len(self._fleet)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

class _ImportError:
    """Placeholder for a failed import; raises on attribute access."""
    def __init__(self, name: str, error: Exception):
        self._name = name
        self._error = error

    def __repr__(self) -> str:
        return f"<ImportError: {self._name} — {self._error}>"

    def __bool__(self) -> bool:
        return False

    def __getattr__(self, _name: str) -> Any:
        raise ImportError(f"{self._name} failed to import: {self._error}")


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

domain = _Domain()
infra = _Infra()
cpp = _CppBridge()
bots = _BotFleet()


def overview() -> Dict[str, Any]:
    """One-shot system snapshot: every domain, infra, C++ and bot available."""
    domain_cat = domain.catalog()
    cpp_cat = cpp.catalog()
    total_domain_classes = sum(d["class_count"] for d in domain_cat.values())
    total_domain_funcs = sum(d["function_count"] for d in domain_cat.values())

    return {
        "ct101_root": str(_CT101_ROOT),
        "openssl_preloaded": _openssl_loaded,
        "domain": {
            "packages": len(domain_cat),
            "total_classes": total_domain_classes,
            "total_functions": total_domain_funcs,
        },
        "cpp_bridge": {
            "ready": cpp.ready,
            "modules": list(cpp._modules.keys()),
            "total_functions": cpp_cat["total_functions"],
            "total_classes": cpp_cat["total_classes"],
            "indicator_count": cpp_cat["indicator_count"],
            "errors": cpp._errors,
        },
        "bots": {
            "loaded": bots.count,
            "names": list(bots.fleet.keys()),
            "total_available": len(bots._FLEET_SPECS),
            "errors": bots.errors,
        },
    }


__all__ = [
    "domain", "infra", "cpp", "bots",
    "overview",
]