class HexOnlyError(ValueError):
    """Selected region contains unsupported/non-hexahedral host elements."""


class AmbiguousAxisError(ValueError):
    """Thickness/curve axis cannot be auto-detected and was not supplied explicitly."""


class MesherInputError(ValueError):
    """A user-facing input error (bad CLI argument, missing instance/elset, etc.)."""
