class DiarioExceptions(Exception):
    """Base class for all exceptions in the Diario module."""
    pass
class DiarioNaoExiste(DiarioExceptions):
    """Raised when the specified Diario does not exist."""
    pass
class DataFutura(DiarioExceptions):
    """Raised when the specified date is in the future."""
    pass
