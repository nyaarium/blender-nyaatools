# Texture channel flags
supported_flags = {
    "00": True,  # Unused channel
    "cr": True,  # sRGB Color (red)
    "cg": True,  # sRGB Color (green)
    "cb": True,  # sRGB Color (blue)
    "lr": True,  # Linear Color (red)
    "lg": True,  # Linear Color (green)
    "lb": True,  # Linear Color (blue)
    "al": True,  # Alpha
    "nx": True,  # Normal X
    "ng": True,  # Normal +Y (OpenGL)
    "nd": True,  # Normal -Y (DirectX)
    # Normal Z should auto calculated from X and Y
    "he": True,  # Height
    "me": True,  # Metallic
    "sp": True,  # Specular
    "ro": True,  # Roughness
    "sm": True,  # Smoothness
    "ao": True,  # Ambient Occlusion
    "er": True,  # Emission (red)
    "eg": True,  # Emission (green)
    "eb": True,  # Emission (blue)
    "es": True,  # Emission Strength
}

# Texture flags requiring color encoding
color_flags = {
    "cr": True,  # sRGB Color (red)
    "cg": True,  # sRGB Color (green)
    "cb": True,  # sRGB Color (blue)
    "er": True,  # Emission (red)
    "eg": True,  # Emission (green)
    "eb": True,  # Emission (blue)
}
color_aliases = {
    "rgb": True,
    "rgba": True,
    "emission": True,
}

# Alias expansions - maps aliases to their channel components
alias_channels = {
    "rgb": ["cr", "cg", "cb"],
    "rgba": ["cr", "cg", "cb", "al"],
    "linear": ["lr", "lg", "lb"],
    "lineara": ["lr", "lg", "lb", "al"],
    "emission": ["er", "eg", "eb"],
    "normalgl": ["nx", "ng"],
    "normaldx": ["nx", "nd"],
}

# Supported aliases - simple key check
supported_aliases = alias_channels

# Supported image formats
supported_image_types = {
    "dds": True,
    "exr": True,
    "webp": True,
    "png": True,
    "jpg": True,
    "jpeg": True,
    "tga": True,
}


def is_ext_supported(ext: str) -> bool:
    """Check if the file extension is supported."""
    return ext.lower() in supported_image_types


def is_flag_supported(flags: str) -> bool:
    """Check if all texture channel flags in a hyphen-delimited string are supported."""

    flags = flags.strip().lower()

    if flags == "":
        return False

    for flag in flags.split("-"):
        if flag not in supported_flags:
            return False
    return True


def expand_alias(alias: str) -> list:
    """Expand an alias to its component channels."""
    return alias_channels.get(alias, [alias])


def is_alias(alias: str) -> bool:
    """Check if a string is a supported alias."""
    return alias in alias_channels


def is_filename_dtp_formatted(filename: str) -> bool:
    """Check if a filename follows the DTP (Dynamic Texture Packing) naming convention."""
    # Grab filename without path
    filename = filename.split("/")[-1].split("\\")[-1]

    # Grab the extension and check support
    parts = filename.split(".")  # ["image", "rgb", "png"]
    if len(parts) < 2:
        # No extension found
        return False

    ext = parts[-1]
    parts.pop()  # ["image", "rgb"]

    if not is_ext_supported(ext):
        return False

    # Check for flags if they exist
    if 2 <= len(parts):
        flags = parts[-1]
        parts.pop()  # ["image"]

        if flags.lower() in supported_aliases:
            return True

        return is_flag_supported(flags)

    return False


def is_filename_color_encoded(filename: str) -> bool:
    """Check if any channel flag is a color channel."""

    parts = filename.split(".")  # ["image", "rgb", "png"]
    if len(parts) < 2:
        return False

    ext = parts[-1]
    parts.pop()  # ["image", "rgb"]

    if len(parts) < 1:
        return False

    flags = parts[-1]
    parts.pop()  # ["image"]

    if flags.lower() in color_aliases:
        return True

    flag_parts = flags.lower().split("-")
    for flag in flag_parts:
        if flag in color_flags:
            return True

    return False
