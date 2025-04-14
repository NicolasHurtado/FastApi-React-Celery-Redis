import random
import string
from typing import Dict, Optional

def random_lower_string(length: int = 32) -> str:
    """
    Genera una cadena aleatoria de letras minúsculas.
    
    Args:
        length: Longitud de la cadena a generar
        
    Returns:
        Cadena aleatoria de letras minúsculas
    """
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for _ in range(length))


def random_email() -> str:
    """
    Genera una dirección de correo electrónico aleatoria.
    
    Returns:
        Dirección de correo electrónico aleatoria
    """
    return f"{random_lower_string(8)}@{random_lower_string(6)}.com"


def random_dict(prefix: str = "", count: int = 5) -> Dict[str, str]:
    """
    Genera un diccionario con claves y valores aleatorios.
    
    Args:
        prefix: Prefijo para las claves
        count: Número de elementos en el diccionario
        
    Returns:
        Diccionario con claves y valores aleatorios
    """
    return {
        f"{prefix}{random_lower_string(8)}": random_lower_string(12)
        for _ in range(count)
    }


def compare_dict_subset(dict1: Dict, dict2: Dict) -> bool:
    """
    Comprueba si dict1 es un subconjunto de dict2.
    
    Args:
        dict1: Diccionario a comprobar
        dict2: Diccionario que contendría a dict1
        
    Returns:
        True si todas las claves y valores de dict1 están en dict2 con los mismos valores
    """
    return all(key in dict2 and dict2[key] == val for key, val in dict1.items()) 