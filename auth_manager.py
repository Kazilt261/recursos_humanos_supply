import json
import os
import streamlit_authenticator as stauth

def _data_path(filename: str) -> str:
    data_dir = os.getenv("DATA_DIR", ".")
    return os.path.join(data_dir, filename)

def _ensure_seed_file(dst_path: str, seed_filename: str) -> None:
    # Si el archivo en el disco no existe, lo copiamos desde el repo (seed)
    if os.path.exists(dst_path):
        return
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    try:
        with open(seed_filename, "r", encoding="utf-8") as src:
            content = src.read()
        with open(dst_path, "w", encoding="utf-8") as dst:
            dst.write(content)
    except FileNotFoundError:
        # Si no existe el seed en el repo, lo dejamos y que falle explícito luego
        pass

class AdminUsuarios:
    def __init__(self, archivo_db: str | None = None):
        self.archivo_db = archivo_db or _data_path("usuarios.json")
        _ensure_seed_file(self.archivo_db, "usuarios.json")

    def cargar_config(self):
        try:
            with open(self.archivo_db, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def guardar_config(self, config):
        os.makedirs(os.path.dirname(self.archivo_db), exist_ok=True)
        with open(self.archivo_db, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

    def agregar_usuario(self, username, name, password_plana):
        config = self.cargar_config()
        if not config:
            return False, "No existe el archivo DB (usuarios.json)."

        if username in config["credentials"]["usernames"]:
            return False, "El usuario ya existe."

        hashed_password = stauth.Hasher([password_plana]).generate()[0]
        config["credentials"]["usernames"][username] = {
            "name": name,
            "password": hashed_password,
        }
        self.guardar_config(config)
        return True, "Usuario creado exitosamente."

    def eliminar_usuario(self, username):
        config = self.cargar_config()
        if config and username in config["credentials"]["usernames"]:
            del config["credentials"]["usernames"][username]
            self.guardar_config(config)
            return True, "Usuario eliminado."
        return False, "Usuario no encontrado."
