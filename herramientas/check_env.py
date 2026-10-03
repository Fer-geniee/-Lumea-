import importlib

paquetes = [
    "flask", "flask_cors", "mysql.connector", "dotenv",
    "tensorflow", "tf_keras", "keras", "PIL", "numpy",
]

print(f"{'Paquete':<20}{'Version':<15}{'Instalado'}")
print("-" * 45)
for nombre in paquetes:
    try:
        mod = importlib.import_module(nombre)
        version = getattr(mod, "__version__", "sin atributo __version__")
        print(f"{nombre:<20}{str(version):<15}Sí")
    except ImportError:
        print(f"{nombre:<20}{'—':<15}NO")
