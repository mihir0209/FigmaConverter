"""
Model Cache System for AI Engine
Provides shared caching for model discovery across providers
"""

import json
import os
import time
from typing import List, Tuple, Dict, Any, Optional
from pathlib import Path

class SharedModelCache:
    """Shared cache for model discovery across AI providers"""

    def __init__(self, cache_file: str = "model_cache.json", cache_duration: int = 1800):
        self.cache_file = Path(cache_file)
        self.cache_duration = cache_duration  # 30 minutes default
        self.cache = {}
        self.last_save = 0
        self.load_cache()

    def load_cache(self) -> None:
        """Load cache from file if it exists and is valid"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Check if cache is still valid
                cache_time = data.get('timestamp', 0)
                if time.time() - cache_time < self.cache_duration:
                    self.cache = data.get('models', {})
                    print(f"📚 Loaded model cache with {len(self.cache)} entries")
                else:
                    print("📚 Model cache expired, will refresh")
                    self.cache = {}
            else:
                print("📚 No model cache found, will create new one")
                self.cache = {}
        except Exception as e:
            print(f"❌ Error loading model cache: {e}")
            self.cache = {}

    def save_cache(self, models_data: List[str] = None) -> None:
        """Save cache to file"""
        try:
            if models_data:
                # Convert list of "provider|model" strings to cache format
                cache_data = {}
                for item in models_data:
                    if '|' in item:
                        provider, model = item.split('|', 1)
                        if provider not in cache_data:
                            cache_data[provider] = []
                        if model not in cache_data[provider]:
                            cache_data[provider].append(model)

                self.cache = cache_data

            # Save to file
            data = {
                'timestamp': time.time(),
                'models': self.cache
            }

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            self.last_save = time.time()
            print(f"💾 Saved model cache with {len(self.cache)} providers")

        except Exception as e:
            print(f"❌ Error saving model cache: {e}")

    def is_cache_valid(self) -> bool:
        """Check if cache is valid and not expired"""
        if not self.cache:
            return False

        try:
            if self.cache_file.exists():
                cache_time = self.cache_file.stat().st_mtime
                return time.time() - cache_time < self.cache_duration
        except:
            pass

        return False

    def find_providers_for_model(self, model_name: str) -> List[Tuple[str, str]]:
        """Find providers that have the specified model"""
        if not model_name or not self.cache:
            return []

        results = []
        model_lower = model_name.lower()

        for provider, models in self.cache.items():
            for model in models:
                if model_lower in model.lower() or model.lower() in model_lower:
                    results.append((provider, model))

        return results

    def get_cached_models(self, provider: str = None) -> Dict[str, List[str]]:
        """Get cached models, optionally filtered by provider"""
        if provider:
            return {provider: self.cache.get(provider, [])}
        return self.cache.copy()

    def clear_cache(self) -> None:
        """Clear the cache"""
        self.cache = {}
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
            print("🗑️ Model cache cleared")
        except Exception as e:
            print(f"❌ Error clearing cache: {e}")

# Global instance
shared_model_cache = SharedModelCache()