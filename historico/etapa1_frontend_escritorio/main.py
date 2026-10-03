import customtkinter as ctk
from PIL import Image
import os

class LumeaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- VENTANA ---
        self.title("LUMEA - Wellness Hub")
        self.geometry("1100x700") #
        self.configure(fg_color="#0B0E14")
        self.angulo = 0 
        self.ruta_planeta = os.path.join(os.path.dirname(__file__), "planeta.png") # Esto nos permite cargar la imagen desde la misma carpeta del script, evitando problemas de rutas relativas al ejecutar desde otro lugar
        
        print(f"Buscando el planeta en: {self.ruta_planeta}")
        try:
            self.img_original = Image.open(self.ruta_planeta)
            print("Archivo encontrado")
        except:
            print("Archivo no encontrado ")
            self.img_original = None

        # --- 1. BARRA SUPERIOR (LOGO) ---
        self.top_bar = ctk.CTkFrame(self, height=60, fg_color="transparent") # Transparente para que se integre con el fondo oscuro
        self.top_bar.pack(fill="x", padx=40, pady=(30, 0)) # Espaciado para que no quede pegado al borde superior
        
        self.logo_label = ctk.CTkLabel(self.top_bar, text="LUMEA",  # Esa función ctk.CTkFont es para crear un objeto de fuente personalizada, lo que nos permite usar la fuente "Inter" con el tamaño y peso que queramos. Esto hace que el logo se vea más profesional y acorde con el diseño moderno que buscamos.
                                       font=ctk.CTkFont(family="Inter", size=24, weight="bold"),
                                       text_color="#FFFFFF")
        self.logo_label.pack(side="left")

        # --- 2. CONTENEDOR PRINCIPAL ---
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=40, pady=20)

        # LADO IZQUIERDO: Texto y el planeta 
        self.left_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.left_frame.pack(side="left", fill="both", expand=True)

        # Slogan dinámico con fuente personalizada y tamaño grande para impacto visual :)
        self.slogan = ctk.CTkLabel(self.left_frame, 
                                   text="Diseña tu vida,\nun hábito a la vez.", 
                                   font=ctk.CTkFont(family="Inter", size=45, weight="bold"),
                                   text_color="white", justify="left")
        self.slogan.place(relx=0.05, rely=0.2, anchor="nw")

        # Planeta animado asomándose # Corregir esto porque no me gustó  
        self.canvas_planeta = ctk.CTkLabel(self.left_frame, text="")
        self.canvas_planeta.place(relx=-0.1, rely=1.0, anchor="sw")

        # LADO DERECHO: TARJETA DE REGISTRO 
        self.right_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.right_container.pack(side="right", fill="both", expand=True)

        # Aquí corregimos el error del para que la tarjeta de inicio no se deforme. 
        self.login_card = ctk.CTkFrame(self.right_container, 
                                       fg_color="#161B22", 
                                       width=380, 
                                       height=450,
                                       corner_radius=25, 
                                       border_width=2, 
                                       border_color="#4f8ef7")
        self.login_card.place(relx=0.5, rely=0.5, anchor="center")
        self.login_card.pack_propagate(False) # Evita que los botones deformen la tarjeta

        # --- CONTENIDO DE LA TARJETA ---
        ctk.CTkLabel(self.login_card, text="Comenzar Viaje", 
                     font=("Inter", 22, "bold"), text_color="white").pack(pady=(40, 25))

        self.user_input = ctk.CTkEntry(self.login_card, placeholder_text="Nombre de usuario",
                                       text_color="white", placeholder_text_color="#8888aa",
                                       height=50, width=300, corner_radius=15,
                                       fg_color="#0D1117", border_color="#30363D")
        self.user_input.pack(pady=10)

        self.btn_entrar = ctk.CTkButton(self.login_card, text="INICIAR EXPERIENCIA", 
                                        height=55, width=300, corner_radius=15,
                                        fg_color="#4f8ef7", hover_color="#3b6dbd",
                                        font=("Inter", 14, "bold"))
        self.btn_entrar.pack(pady=(30, 0))

        # --- 3. INICIAR ANIMACIÓN ---
        if self.img_original:
            self.animar()

    # --- LA FUNCIÓN DE ANIMACIÓN REFINADA ---
    def animar(self):
        if not self.img_original:
            return
        self.angulo = (self.angulo - 0.2) % 360 
        img_rotada = self.img_original.rotate(self.angulo, resample=Image.BICUBIC)
        ctk_img = ctk.CTkImage(light_image=img_rotada, dark_image=img_rotada, size=(500, 500))
        self.canvas_planeta.configure(image=ctk_img)
        self.canvas_planeta.image = ctk_img 
        self.after(16, self.animar)

        
    def ir_a_perfil(self):
        pass

    command = self.btn_entrar.configure(command=self.ir_a_perfil)

if __name__ == "__main__":
    app = LumeaApp()
    app.mainloop()
    