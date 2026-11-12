"""
CT101 x Hermes Agent -- full native integration.

All CT101 domain, infrastructure, C++ and agent code is imported directly.
CT101 root is added to sys.path; .env is loaded; OpenSSL is preloaded.
    from hermes_agent.ct101 import domain, infra, cpp, bots, agents, overview
"""

from __future__ import annotations

import ctypes, os, sys, ast as _ast
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Path ────────────────────────────────────────────────────────────────────

_CT101_ROOT = Path(os.environ.get("CT101_ROOT", "/home/claude/timeshift/ct101")).resolve()
if str(_CT101_ROOT) not in sys.path:
    sys.path.insert(0, str(_CT101_ROOT))

# ── .env ────────────────────────────────────────────────────────────────────

_ENV_PATH = _CT101_ROOT / ".env"
if _ENV_PATH.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(str(_ENV_PATH))
    except ImportError: pass

# ── OpenSSL ─────────────────────────────────────────────────────────────────

try:
    ctypes.CDLL("libcrypto.so.3", mode=ctypes.RTLD_GLOBAL)
    ctypes.CDLL("libssl.so.3", mode=ctypes.RTLD_GLOBAL)
except OSError:
    try:
        ctypes.CDLL("libcrypto.so", mode=ctypes.RTLD_GLOBAL)
        ctypes.CDLL("libssl.so", mode=ctypes.RTLD_GLOBAL)
    except OSError: pass

# ═══════════════════════════════════════════════════════════════════════════════

class _Fail:
    def __init__(self, n, e): self._n = n; self._e = e
    def __bool__(self): return False
    def __repr__(self): return f"<Fail:{self._n}>"
    def __getattr__(self, _): raise ImportError(f"{self._n}: {self._e}")

# ── DOMAIN ──────────────────────────────────────────────────────────────────

class _Domain:
    _d: Dict[str, Any] = {}
    _pkgs = ["agents","ai_growth","alpha_generation","backtesting","bots","capabilities",
             "common","compounding","events","handlers","learning","licensing","market",
             "memory","memory_learning","models","neuromorphic","portfolio",
             "regime_detection","regulatory","repos","risk","routing","runtime",
             "services","strategy","trading"]

    def __getattr__(self, name):
        if name.startswith("_"): raise AttributeError(name)
        if name in self._d: return self._d[name]
        try:
            m = __import__(f"domain.{name}", fromlist=[name])
            self._d[name] = m; return m
        except Exception as e:
            self._d[name] = _Fail(f"domain.{name}", e); return self._d[name]

    def __dir__(self): return self._pkgs

    def catalog(self):
        r = {}
        ddir = _CT101_ROOT / "domain"
        if not ddir.is_dir(): return r
        for pkg in sorted(ddir.iterdir()):
            if not pkg.is_dir() or pkg.name.startswith("_"): continue
            cs, fs = set(), set()
            for f in sorted(pkg.rglob("*.py")):
                if "__pycache__" in str(f): continue
                try:
                    for n in _ast.walk(_ast.parse(f.read_text())):
                        if isinstance(n, _ast.ClassDef) and not n.name.startswith("_"): cs.add(n.name)
                        elif isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and not n.name.startswith("_"): fs.add(n.name)
                except SyntaxError: pass
            r[pkg.name] = {"class_count": len(cs), "function_count": len(fs)}
        return r

# ── INFRASTRUCTURE ──────────────────────────────────────────────────────────

class _Infra:
    _d: Dict[str, Any] = {}
    _mods = ["agents","ai","apis","auth","aws","backtest","backup","cache","chat","cloud",
             "cloudflare","common","config","control","database","deployment","diagnostics",
             "discovery","error_handling","exchange","extensions","feeds","gateway","hermes",
             "mcp","message_queue","messaging","micro","missing","ml","monitoring","network",
             "ops","orchestration","persistence","queue","runtime","security","services",
             "system","trading","training","utils","websocket"]

    def __getattr__(self, name):
        if name.startswith("_"): raise AttributeError(name)
        if name in self._d: return self._d[name]
        try:
            m = __import__(f"infrastructure.{name}", fromlist=[name])
            self._d[name] = m; return m
        except Exception as e:
            self._d[name] = _Fail(f"infrastructure.{name}", e); return self._d[name]

    def __dir__(self): return self._mods

# ── C++ BRIDGE ──────────────────────────────────────────────────────────────

class _CppBridge:
    _init = False; _mods = {}; _errs = {}; _inds = []

    def _ensure(self):
        if self._init: return
        self._init = True
        micro = str(_CT101_ROOT / "infrastructure" / "micro")
        sys.path.insert(0, micro)

        def _L(name, key, aliases):
            try:
                m = __import__(name, fromlist=[name])
                self._mods[key] = m; self.__dict__[key] = m
                for a in aliases:
                    if hasattr(m, a): self.__dict__[a] = getattr(m, a)
            except Exception as e: self._errs[key] = str(e)

        _L("tradeengine_core_binding","core",
           ["pattern_hash","get_confidence_boost","update_pattern_confidence",
            "calc_indicators","find_or_create_pattern","save_pattern","get_pattern",
            "detect_candles","save_memory_snapshot","load_memory_snapshot",
            "initialize","cleanup","is_available","check_available","get_last_error",
            "AWSMemoryBridgeBinding"])
        try:
            if "core" in self._mods: self._mods["core"].initialize()
        except Exception as e: self._errs["core_init"] = str(e)

        _L("talib_full","talib",
           ["catalogue","call","value_at","scan_all","evaluate","pattern_score",
            "available","defaults","lookback","FUNCS","CDL_NAMES","INDICATOR_NAMES"])
        try:
            if "talib" in self._mods: self._inds = sorted(self._mods["talib"].catalogue().keys())
        except Exception: pass

        _L("ultrafast_binding","ultrafast",
           ["calculate_indicators","calculate_indicators_at","build_decision_matrix",
            "get_matrix_size","free_matrix","read_matrix","matrix_values",
            "generate_pattern_hash","is_loaded","is_available",
            "DecisionMatrix","UltrafastBinding","SIGNATURES","REQUIRED_SYMBOLS","INDICATOR_KEYS","LIB_PATH"])

        _L("bot_wrapper_binding","bot_wrapper",
           ["Bot","create_bot","get_bot","destroy_all","live_count",
            "EXPORTED","DECLARED_NOT_EXPORTED","ACTION_NAMES"])

        try:
            from domain.bots.services import cpp_bot_binding as cb
            self._mods["cpp_bot"] = cb; self.__dict__["cpp_bot"] = cb
            for a in ["CPPBotWrapper","CPPAcceleratedBot","CPPBotBinding","TradingAction","MarketRegime","create_cpp_bot"]:
                if hasattr(cb, a): self.__dict__[a] = getattr(cb, a)
        except Exception as e: self._errs["cpp_bot"] = str(e)

    def __getattr__(self, name):
        if name.startswith("_"): raise AttributeError(name)
        self._ensure()
        if name in self.__dict__: return self.__dict__[name]
        raise AttributeError(f"no '{name}'. mods={list(self._mods)} errs={self._errs}")

    @property
    def ready(self): self._ensure(); return "core" in self._mods and "core_init" not in self._errs

    def catalog(self):
        self._ensure()
        r = {"modules": {}, "total_functions": 0, "total_classes": 0}
        for mn, m in self._mods.items():
            f = [n for n in dir(m) if callable(getattr(m,n,None)) and not n.startswith("_")]
            c = [n for n in dir(m) if isinstance(getattr(m,n,None),type) and not n.startswith("_")]
            r["modules"][mn] = {"function_count": len(f), "class_count": len(c)}
            r["total_functions"] += len(f); r["total_classes"] += len(c)
        r["indicator_count"] = len(self._inds)
        return r

# ── BOT FLEET ───────────────────────────────────────────────────────────────

_B = "domain.bots.services"

class _BotFleet:
    _fleet = {}; _loaded = {}; _errors = {}; _done = False

    _S = [
        (_B,"bot_factory","BotFactory",None),
        (_B,"bot_factory","MicrosecondTradingWrapper",None),
        (_B,"bot_factory_enhanced","EnhancedBotFactory",None),
        (_B,"bot_factory_enhanced","BotEnhancement",None),
        (_B,"bot_factory_enhanced","MomentumEnhancement",None),
        (_B,"bot_factory_enhanced","AdaptiveEnhancement",None),
        (_B,"bot_factory_enhanced","AutonomousEnhancement",None),
        (_B,"basbot_enhanced_orchestrator","BasBotEnhancedOrchestrator","orchestrator_core"),
        (_B,"basbot_enhanced_orchestrator_production","BasBotEnhancedOrchestratorProduction","orchestrator"),
        (_B,"bot_manager","BotManager",None),
        (_B,"bot_manager","BotRole",None),
        (_B,"bot_manager","BotDecision",None),
        (_B,"bot_orchestrator","BotOrchestrator",None),
        (_B,"base_bot","EnhancedBaseBot",None),
        (_B,"cpp_memory_aware_bot","CppMemoryAwareBot","cpp_memory_aware"),
        (_B,"cpp_bot_binding","CPPAcceleratedBot","cpp_accelerated"),
        (_B,"cpp_bot_binding","CPPBotWrapper",None),
        (_B,"cpp_bot_binding","CPPBotBinding",None),
        (_B,"cpp_bot_binding","TradingAction",None),
        (_B,"cpp_bot_binding","MarketRegime",None),
        (_B,"cpp_default_bot","CPPDefaultBot","cpp_default"),
        (_B,"autonomous_bot","AutonomousBot","autonomous"),
        (_B,"autonomous_bot","StrategyMetrics",None),
        (_B,"adaptive_trading_bot","AdaptiveTradingBot","adaptive"),
        (_B,"adaptive_trading_bot","AdaptiveMetrics",None),
        (_B,"momentum_enhanced","MomentumBot","momentum"),
        (_B,"momentum_enhanced","MomentumEnhancedBot","momentum_enhanced"),
        (_B,"momentum_turbo_bot","MomentumTurboBot","momentum_turbo"),
        (_B,"momentum_turbo_bot","TurboMetrics",None),
        (_B,"montecarlo_enhanced_bot","MonteCarloEnhancedBot","montecarlo"),
        (_B,"memory_aware_bot","MemoryAwareBot","memory_aware"),
        (_B,"simple_momentum_bot","SimpleMomentumBot","simple_momentum"),
        (_B,"default_bot","DefaultBot","default"),
        (_B,"double_compound_manager","DoubleCompoundManager","double_compound"),
        (_B,"pdt_compliant_manager","PDTCompliantManager","pdt_compliant"),
        (_B,"dqn_wrapper","DQNEnhancedV2Bot","dqn_v2"),
        (_B,"dqn_wrapper","EnhancedDQNBot","dqn_enhanced"),
        (_B,"intelligent_agent","IntelligentAgent","intelligent"),
        (_B,"intelligent_agent","AgentState",None),
        (_B,"intelligent_agent","DecisionContext",None),
        (_B,"intelligent_agent","AgentPerformance",None),
        (_B,"llm_integration","LLMIntegration",None),
        (_B,"agent_factory","AgentFactory",None),
        (_B,"microsecond_trading_service","MicrosecondTradingService",None),
        (_B,"bot_support","MarketSnapshot",None),
        (_B,"bot_support","SyntheticStrategy",None),
    ]

    def _ensure(self):
        if self._done: return
        self._done = True
        imp = {}
        for _, mod, attr, key in self._S:
            full = f"{_B}.{mod}"
            if full not in imp:
                try: imp[full] = __import__(full, fromlist=[attr])
                except Exception as e: self._errors[full] = str(e); continue
            try: cls = getattr(imp[full], attr)
            except AttributeError: self._errors[f"{full}.{attr}"] = "missing"; continue
            if key: self._fleet[key] = cls
            self._loaded[attr] = cls

    @property
    def fleet(self): self._ensure(); return self._fleet
    @property
    def all_classes(self): self._ensure(); return {**self._fleet, **self._loaded}
    @property
    def errors(self): self._ensure(); return self._errors
    @property
    def count(self): self._ensure(); return len(self._fleet)

# ── AGENTS ──────────────────────────────────────────────────────────────────

_AB = "infrastructure.agents"

class _Agents:
    _loaded = {}; _errors = {}; _done = False
    _S = [
        (_AB,"agent_hub",["MCPHubClient","CloudflareClient","ConnectionManager","ManagedSentimentAnalyzer","SentimentAnalyzer"]),
        (_AB,"cluster_ai",["ClusterAI","ClusterAIExtensions","ClusterAIChatRequest"]),
        (_AB,"llm_agent",["LLMAgent"]),
        (_AB,"intelligent_learning_agent",["IntelligentLearningAgent","MarketData","LearningPattern"]),
        (_AB,"master_control_agent",["ConversationContext","AutonomousDecision","LearningInsight"]),
        (_AB,"agent_factory_server",["AgentCreateRequest"]),
        (_AB,"bot_factory_server",["BotCreateRequest"]),
        (_AB,"bot_manager_server",["BotCreateRequest","DoubleCompoundRequest"]),
    ]

    def _ensure(self):
        if self._done: return
        self._done = True
        for _, mod, attrs in self._S:
            full = f"{_AB}.{mod}"
            try:
                m = __import__(full, fromlist=attrs); self._loaded[full] = m
                for a in attrs:
                    if hasattr(m, a): self._loaded[a] = getattr(m, a)
            except Exception as e: self._errors[full] = str(e)

    @property
    def loaded(self): self._ensure(); return self._loaded
    @property
    def errors(self): self._ensure(); return self._errors
    @property
    def count(self): self._ensure(); return len(self._loaded)

# ── PUBLIC ──────────────────────────────────────────────────────────────────

domain = _Domain()
infra = _Infra()
cpp = _CppBridge()
bots = _BotFleet()
agents = _Agents()

def overview():
    dc = domain.catalog(); cc = cpp.catalog()
    return {
        "ct101_root": str(_CT101_ROOT),
        "domain": {"packages": len(dc),
                   "total_classes": sum(d["class_count"] for d in dc.values()),
                   "total_functions": sum(d["function_count"] for d in dc.values())},
        "cpp_bridge": {"ready": cpp.ready, "modules": list(cpp._mods),
                       "total_functions": cc["total_functions"],
                       "total_classes": cc["total_classes"],
                       "indicator_count": cc["indicator_count"], "errors": cpp._errs},
        "bots": {"loaded": bots.count, "names": list(bots.fleet),
                 "total": len(bots._S), "errors": bots.errors},
        "agents": {"loaded": agents.count, "errors": agents.errors},
    }

__all__ = ["domain","infra","cpp","bots","agents","overview"]
