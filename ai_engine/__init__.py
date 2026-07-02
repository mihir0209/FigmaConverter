"""Auto-detect adapter: try OpenCodeAdapter first, then LLMFallbackAdapter."""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_adapter_class():
    """Return the best available adapter class, raised RuntimeError if none."""
    # 1. Try opencode first
    import os
    if os.getenv("OPENCODE_SKIP") != "1":
        try:
            import subprocess
            subprocess.run(
                ["opencode", "--version"],
                capture_output=True, text=True, timeout=3,
            )
            from processors.opencode_adapter import OpenCodeAdapter
            logger.info("Using OpenCodeAdapter (opencode CLI found)")
            return OpenCodeAdapter
        except Exception:
            logger.info("opencode CLI not available, trying fallback")

    # 2. Fallback to llm library
    try:
        import llm  # noqa: F401
        from processors.llm_fallback_adapter import LLMFallbackAdapter
        logger.info("Using LLMFallbackAdapter (llm library)")
        return LLMFallbackAdapter
    except ImportError:
        pass

    # 3. Neither available
    raise RuntimeError(
        "No AI adapter available. "
        "Install opencode (https://opencode.ai) or "
        "pip install llm [llm-anthropic llm-openai]"
    )


# Backward compat: AI_engine is now get_adapter_class (not an instance)
def AI_engine(verbose: bool = False) -> Any:
    cls = get_adapter_class()
    return cls(verbose=verbose)
