import json
import streamlit_authenticator as stauth

class AdminUsuarios:
    def __init__(self, archivo_db='usuarios.json'):
        self.archivo_db = archivo_db

    def cargar_config(self):
        try:
            with open(self.archivo_db, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def guardar_config(self, config):
        with open(self.archivo_db, 'w') as f:
            json.dump(config, f, indent=4)

    def agregar_usuario(self, username, name, password_plana):
        config = self.cargar_config()
        if not config: return False, "No existe el archivo DB (usuarios.json)."
        
        if username in config['credentials']['usernames']:
            return False, "El usuario ya existe."
        
        # Encriptar
        hashed_password = stauth.Hasher([password_plana]).generate()[0]
        
        config['credentials']['usernames'][username] = {
            'name': name,
            'password': hashed_password
        }
        self.guardar_config(config)
        return True, "Usuario creado exitosamente."

    def eliminar_usuario(self, username):
        config = self.cargar_config()
        if username in config['credentials']['usernames']:
            del config['credentials']['usernames'][username]
            self.guardar_config(config)
            return True, "Usuario eliminado."
        return False, "Usuario no encontrado."