from sqlalchemy.ext.declarative import declarative_base
 
# Base declarativa para todos los modelos ORM
# Importa esta Base en tus modelos y en alembic/env.py
Base = declarative_base() 