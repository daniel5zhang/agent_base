def seed_builtin_plugins() -> None:
    """Phase 1 intentionally seeds no business plugins.

    Business plugins such as ask-data, claims, underwriting and approval start in
    phase 2. Keeping this hook preserves the bootstrap path without publishing
    mock business capabilities into the phase-1 database.
    """

    return None
