"""
ETA Estimator for baking operations.

Stores timing scalars scene-wide to estimate future bake times.
Tracks separate scalars for:
- bake_rgb: 3-channel bakes (RGB only)
- bake_rgba: 4-channel bakes (RGB + Alpha + Packing)
- optimize: Optimization/resize pass
"""

import time
import bpy
from bpy.props import FloatProperty
from bpy.types import PropertyGroup


class NyaaBakeTimingScalars(PropertyGroup):
    """
    Scene-stored timing data for ETA estimation.

    Uses exponentially weighted linear regression: time = base + rate * megapixels
    Values decay each update (alpha=0.2), keeping them bounded while adapting to recent data.
    """

    # RGB bake regression data (exponentially weighted)
    rgb_n: FloatProperty(default=0.0)  # Effective sample count (asymptotes to ~5)
    rgb_sum_x: FloatProperty(default=0.0)  # Weighted Σ(megapixels)
    rgb_sum_y: FloatProperty(default=0.0)  # Weighted Σ(time)
    rgb_sum_xx: FloatProperty(default=0.0)  # Weighted Σ(megapixels²)
    rgb_sum_xy: FloatProperty(default=0.0)  # Weighted Σ(time * megapixels)

    # RGBA bake regression data (exponentially weighted)
    rgba_n: FloatProperty(default=0.0)
    rgba_sum_x: FloatProperty(default=0.0)
    rgba_sum_y: FloatProperty(default=0.0)
    rgba_sum_xx: FloatProperty(default=0.0)
    rgba_sum_xy: FloatProperty(default=0.0)


# Influence of each new sample (0.2 = 20% new, 80% old)
# Effective memory ≈ 1/alpha = 5 samples
ETA_ALPHA = 0.2


class ETAEstimator:
    """
    Estimates ETA using linear regression: time = base + rate * megapixels

    This accounts for fixed overhead (base) plus scaling cost (rate).
    """

    def __init__(self, context):
        self.context = context
        self._task_type = None
        self._task_megapixels = 0.0
        self._task_start = 0.0

        # Debug: show loaded regression data
        s = self.scalars
        rgb_base, rgb_rate = self._compute_coefficients("bake_rgb")
        rgba_base, rgba_rate = self._compute_coefficients("bake_rgba")
        print(
            f"[ETA] Loaded: RGB(n={int(s.rgb_n)}, base={rgb_base:.1f}s, rate={rgb_rate:.2f}s/MP) RGBA(n={int(s.rgba_n)}, base={rgba_base:.1f}s, rate={rgba_rate:.2f}s/MP)"
        )

    @property
    def scalars(self) -> NyaaBakeTimingScalars:
        """Get the scene-stored timing data."""
        return self.context.scene.nyaa_bake_timing

    @property
    def is_calibrated(self) -> bool:
        """Check if we have enough data to estimate ETA (need 2+ samples)."""
        s = self.scalars
        return s.rgb_n >= 2 or s.rgba_n >= 2

    def _compute_coefficients(self, task_type: str) -> tuple:
        """
        Compute linear regression coefficients (base, rate) for a task type.

        Returns (base_seconds, rate_per_megapixel) or (0, 0) if insufficient data.
        """
        s = self.scalars

        if task_type == "bake_rgb":
            n, sum_x, sum_y, sum_xx, sum_xy = (
                s.rgb_n,
                s.rgb_sum_x,
                s.rgb_sum_y,
                s.rgb_sum_xx,
                s.rgb_sum_xy,
            )
        elif task_type == "bake_rgba":
            n, sum_x, sum_y, sum_xx, sum_xy = (
                s.rgba_n,
                s.rgba_sum_x,
                s.rgba_sum_y,
                s.rgba_sum_xx,
                s.rgba_sum_xy,
            )
        else:
            return (0.0, 0.0)

        if n < 1:
            return (0.0, 0.0)

        if n < 2:
            # With 1 sample, assume all time is base (conservative)
            return (sum_y, 0.0)

        # Linear regression: y = a + b*x
        # b = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)
        # a = (Σy - b*Σx) / n
        denom = n * sum_xx - sum_x * sum_x
        if abs(denom) < 0.0001:
            # All samples at same resolution, can't determine slope
            return (sum_y / n, 0.0)

        rate = (n * sum_xy - sum_x * sum_y) / denom
        base = (sum_y - rate * sum_x) / n

        # Ensure non-negative (can happen with noisy data)
        base = max(0.0, base)
        rate = max(0.0, rate)

        return (base, rate)

    def start_task(self, task_type: str, megapixels: float):
        """Start timing a task."""
        self._task_type = task_type
        self._task_megapixels = megapixels
        self._task_start = time.perf_counter()

    def end_task(self):
        """End timing and add sample to regression."""
        if self._task_type is None:
            return

        elapsed = time.perf_counter() - self._task_start
        self._add_sample(self._task_type, self._task_megapixels, elapsed)

        self._task_type = None
        self._task_megapixels = 0.0
        self._task_start = 0.0

    def _add_sample(self, task_type: str, megapixels: float, elapsed: float):
        """Add a timing sample with exponential decay of old values."""
        if megapixels <= 0:
            return

        s = self.scalars
        x, y = megapixels, elapsed
        decay = 1.0 - ETA_ALPHA  # 0.8 - old values keep 80%

        if task_type == "bake_rgb":
            # Decay old values, then add new sample
            s.rgb_n = decay * s.rgb_n + 1.0
            s.rgb_sum_x = decay * s.rgb_sum_x + x
            s.rgb_sum_y = decay * s.rgb_sum_y + y
            s.rgb_sum_xx = decay * s.rgb_sum_xx + x * x
            s.rgb_sum_xy = decay * s.rgb_sum_xy + x * y
        elif task_type == "bake_rgba":
            s.rgba_n = decay * s.rgba_n + 1.0
            s.rgba_sum_x = decay * s.rgba_sum_x + x
            s.rgba_sum_y = decay * s.rgba_sum_y + y
            s.rgba_sum_xx = decay * s.rgba_sum_xx + x * x
            s.rgba_sum_xy = decay * s.rgba_sum_xy + x * y

        # Debug
        base, rate = self._compute_coefficients(task_type)
        print(
            f"[ETA] {task_type}: {elapsed:.1f}s @ {megapixels:.2f}MP → base={base:.1f}s, rate={rate:.2f}s/MP (n={s.rgb_n if task_type == 'bake_rgb' else s.rgba_n:.1f})"
        )

    def estimate_task_time(self, task_type: str, megapixels: float) -> float:
        """Estimate time for a task: base + rate * megapixels"""
        base, rate = self._compute_coefficients(task_type)

        if base <= 0 and rate <= 0:
            # No data for this type, try fallback
            other_type = "bake_rgba" if task_type == "bake_rgb" else "bake_rgb"
            other_base, other_rate = self._compute_coefficients(other_type)
            if other_base > 0 or other_rate > 0:
                # Rough estimate: RGBA ≈ 2x RGB
                if task_type == "bake_rgba":
                    base, rate = other_base * 2, other_rate * 2
                else:
                    base, rate = other_base / 2, other_rate / 2

        return base + rate * megapixels

    def estimate_remaining(self, remaining_tasks: list) -> float:
        """Estimate total time for remaining tasks."""
        if not self.is_calibrated:
            return 0.0

        total = 0.0
        for task_type, megapixels in remaining_tasks:
            total += self.estimate_task_time(task_type, megapixels)
        return total

    def format_eta(self, seconds: float) -> str:
        """Format seconds as human-readable ETA string."""
        if seconds <= 0:
            return ""
        if seconds < 60:
            return f"~{int(seconds)}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"~{mins}:{secs:02d}"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"~{hours}:{mins:02d}:00"


def resolution_to_megapixels(width: int, height: int) -> float:
    """Convert resolution to megapixels."""
    return (width * height) / 1_000_000


def is_rgba_format(dtp_format: str) -> bool:
    """Check if a DTP format is RGBA (4 channels)."""
    dtp_format = dtp_format.strip().lower()

    # Known 4-channel aliases
    if dtp_format == "rgba":
        return True

    # Custom format with 4 channels (e.g., "cr-cg-cb-al")
    if "-" in dtp_format:
        parts = dtp_format.split("-")
        return len(parts) == 4

    return False


# Registration
CLASSES = [
    NyaaBakeTimingScalars,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    bpy.types.Scene.nyaa_bake_timing = bpy.props.PointerProperty(
        type=NyaaBakeTimingScalars
    )


def unregister():
    if hasattr(bpy.types.Scene, "nyaa_bake_timing"):
        del bpy.types.Scene.nyaa_bake_timing

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
