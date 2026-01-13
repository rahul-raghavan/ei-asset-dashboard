"""
Configuration for EI ASSET Dashboard

Contains authentication passwords and role definitions.
To change passwords, simply edit the values below.
"""

# =============================================================================
# AUTHENTICATION PASSWORDS
# =============================================================================
# Each password maps to a specific role with access to certain classes

PASSWORDS = {
    "iMBMRmR9lbs": {
        "role": "management",
        "name": "Management",
        "allowed_classes": ["3-A", "4-A", "5-A", "6-A", "7-A", "8-A"],  # All classes
        "description": "Full access to all classes and data"
    },
    "P-6zeiPTWrQ": {
        "role": "elementary",
        "name": "Elementary Program",
        "allowed_classes": ["3-A", "4-A", "5-A"],
        "description": "Access to Classes 3, 4, and 5"
    },
    "9Z-Pv08suVs": {
        "role": "middle",
        "name": "Middle School Program",
        "allowed_classes": ["6-A", "7-A", "8-A"],
        "description": "Access to Classes 6, 7, and 8"
    }
}

# =============================================================================
# ROLE DISPLAY SETTINGS
# =============================================================================

ROLE_COLORS = {
    "management": "#1976d2",    # Blue
    "elementary": "#388e3c",    # Green
    "middle": "#f57c00"         # Orange
}
