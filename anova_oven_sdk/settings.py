# ============================================================================
# Configuration with Dynaconf
# ============================================================================
from dynaconf import Dynaconf, Validator
from pathlib import Path


# Try to find settings file in common locations
def find_settings_file():
    """Find settings file in common locations."""
    possible_paths = [
        "settings.yml",
        "settings.yaml",
        "../settings.yml",
        "../settings.yaml",
        Path.home() / ".anova" / "settings.yml",
    ]

    for path in possible_paths:
        if Path(path).exists():
            return [str(path)]

    # Return empty list if no settings file found (will use env vars/defaults)
    return []


# Initialize Dynaconf settings
settings = Dynaconf(
    envvar_prefix="ANOVA",
    settings_files=find_settings_file(),
    environments=True,
    load_dotenv=True,
    env_switcher="ANOVA_ENV",
    validators=[
        Validator("token", must_exist=True,
                  condition=lambda v: v.startswith("anova-") if v else False,
                  messages={"must_exist": "ANOVA_TOKEN must be set",
                            "condition": "Token must start with 'anova-'"}),
        Validator("ws_url", default="wss://devices.anovaculinary.io"),
        Validator("connection_timeout", default=30.0, gte=1.0),
        Validator("command_timeout", default=10.0, gte=1.0),
        Validator("log_level", default="INFO",
                  is_in=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
        Validator("max_retries", default=3, gte=0, lte=10),
        Validator("supported_accessories", default=["APO"]),
    ]
)

if __name__ == "__main__":
    settings = settings