import math

def _nearest_power_of_2(x: float) -> int:
    """Arredonda para a potência de 2 mais próxima."""
    if x <= 1:
        return 1
    return 2 ** round(math.log2(x))
