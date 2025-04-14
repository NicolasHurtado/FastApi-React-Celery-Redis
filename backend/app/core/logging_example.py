from app.core.logging import get_logger

# Obtener logger para este módulo 
logger = get_logger("app.ejemplo")

def ejemplo_logging_basico():
    """Ejemplo simple de uso del sistema de logging"""
    
    # Nivel DEBUG - información detallada para depuración
    logger.debug("Mensaje de nivel DEBUG - Datos internos procesados")
    
    # Nivel INFO - confirmación de que las cosas funcionan según lo esperado
    logger.info("Mensaje de nivel INFO - Operación completada correctamente")
    
    # Nivel WARNING - indica que algo inesperado sucedió pero no es un error
    logger.warning("Mensaje de nivel WARNING - Se usó una función deprecada")
    
    # Nivel ERROR - debido a un problema más grave, la aplicación no pudo realizar una función
    logger.error("Mensaje de nivel ERROR - No se pudo conectar a la base de datos")
    
    # Nivel CRITICAL - un error grave que impide que la aplicación continúe funcionando
    logger.critical("Mensaje de nivel CRITICAL - Error fatal en el sistema")
    
    # Registrar excepciones con toda la información de la traza
    try:
        # Operación que provocará una excepción
        resultado = 10 / 0
    except Exception as e:
        logger.exception("Ocurrió una excepción durante la operación")
        
    # Registrar información estructurada usando el parámetro extra
    usuario_id = 12345
    logger.info(f"Usuario {usuario_id} completó la acción", extra={"usuario_id": usuario_id})

if __name__ == "__main__":
    logger.info("Comenzando ejemplo de logging")
    ejemplo_logging_basico()
    logger.info("Ejemplo de logging finalizado") 