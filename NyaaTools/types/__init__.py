"""
NyaaTools type definitions (PropertyGroups).

These define the data structures stored on Blender objects.
"""

from . import asset_types
from . import avatar_types
from . import prop_types
from . import settings_types

# Re-export for convenience
from .asset_types import NyaaAssetConfig, NyaaAssetMeshEntry
from .asset_types import NyaaExportProfile as NyaaAssetExportProfile
from .asset_types import NyaaBakeImage as NyaaAssetBakeImage

# Legacy types - kept for migration compatibility
from .avatar_types import NyaaAvatarConfig, NyaaAvatarMeshEntry
from .avatar_types import NyaaExportProfile, NyaaBakeImage
from .prop_types import NyaaPropConfig
from .settings_types import NyaaToolsSettings


def register():
    """Register all PropertyGroups. Call from main __init__.py register()."""
    # Register new asset types first
    asset_types.register()
    # Keep avatar types for migration (will read from these during migration)
    avatar_types.register()
    prop_types.register()
    settings_types.register()


def unregister():
    """Unregister all PropertyGroups. Call from main __init__.py unregister()."""
    # Reverse order of registration
    settings_types.unregister()
    prop_types.unregister()
    avatar_types.unregister()
    asset_types.unregister()
