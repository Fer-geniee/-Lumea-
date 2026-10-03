"""
modules/perfil.py — Pantalla de configuración de perfil

Este módulo es el primero en cargarse si el usuario no tiene perfil.
Recopila: nombre, edad, peso, altura y meta personal.
Calcula: IMC y agua diaria recomendada.

Es el módulo que Isabella construye en la Semana 1.
"""

import customtkinter as ctk
from typing import Callable


METAS = {
    "Quiero verme mejor":          "apariencia",
    "Quiero tener más energía":    "energia",
    "Quiero sentirme segura/o":    "bienestar",
    "Quiero mejorar mi rendimiento deportivo": "deporte",
}

COLORES = {
    "accent":    "#4f8ef7",
    "exito":     "#4caf7d",
    "error":     "#e05252",
    "texto":     "#e8e0f0",
    "texto_sec": "#8888aa",
    "card_bg":   "#1a1a2e",
}


class PantallaPerfilConfig(ctk.CTkFrame):
    """
    Pantalla de configuración/edición del perfil de usuario.
    Se muestra en dos casos:
      1. Primera vez que abre la app (onboarding)
      2. Cuando el usuario va a "Mi perfil" a editar sus datos
    """

    def __init__(self, padre, db, callback_guardado: Callable = None):
        """
        Parámetros:
            padre:             Frame padre (el área de contenido principal)
            db:                Instancia de BaseDatos
            callback_guardado: Función a llamar cuando el perfil se guarda exitosamente
        """
        super().__init__(padre, corner_radius=0, fg_color="transparent")
        self.db = db
        self.callback_guardado = callback_guardado

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._construir_ui()
        self._cargar_datos_existentes()

    def _construir_ui(self):
        """Construye todos los elementos de la pantalla."""

        # Contenedor central con scroll (por si la ventana es pequeña)
        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0
        )
        scroll.grid(row=0, column=0, sticky="nsew", padx=40, pady=30)
        scroll.grid_columnconfigure(0, weight=1)

        # ── Encabezado ──────────────────────────────────────────────────────
        ctk.CTkLabel(
            scroll, text="👤 Tu perfil",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLORES["texto"]
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        ctk.CTkLabel(
            scroll,
            text="Esta información es privada y se guarda solo en tu dispositivo.",
            font=ctk.CTkFont(size=13),
            text_color=COLORES["texto_sec"]
        ).grid(row=1, column=0, sticky="w", pady=(0, 24))

        # ── Formulario ───────────────────────────────────────────────────────
        form = ctk.CTkFrame(scroll, fg_color=COLORES["card_bg"], corner_radius=12)
        form.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        form.grid_columnconfigure((0, 1), weight=1)

        # Nombre
        ctk.CTkLabel(
            form, text="Nombre",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORES["texto_sec"]
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 4))

        self.entry_nombre = ctk.CTkEntry(
            form, placeholder_text="¿Cómo te llamas?",
            height=40, font=ctk.CTkFont(size=14)
        )
        self.entry_nombre.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 16))

        # Edad
        self._campo_label(form, "Edad (años)", row=2, col=0)
        self.entry_edad = ctk.CTkEntry(
            form, placeholder_text="ej. 17",
            height=40, font=ctk.CTkFont(size=14)
        )
        self.entry_edad.grid(row=3, column=0, sticky="ew", padx=(20, 8), pady=(0, 16))

        # Peso
        self._campo_label(form, "Peso (kg)", row=2, col=1)
        self.entry_peso = ctk.CTkEntry(
            form, placeholder_text="ej. 58.5",
            height=40, font=ctk.CTkFont(size=14)
        )
        self.entry_peso.grid(row=3, column=1, sticky="ew", padx=(8, 20), pady=(0, 16))

        # Altura
        self._campo_label(form, "Altura (cm)", row=4, col=0)
        self.entry_altura = ctk.CTkEntry(
            form, placeholder_text="ej. 165",
            height=40, font=ctk.CTkFont(size=14)
        )
        self.entry_altura.grid(row=5, column=0, sticky="ew", padx=(20, 8), pady=(0, 24))

        # ── Sección de resultados IMC (aparece después de llenar datos) ───────
        self.frame_imc = ctk.CTkFrame(form, fg_color="#0f0f1a", corner_radius=8)
        self.frame_imc.grid(row=5, column=1, sticky="ew", padx=(8, 20), pady=(0, 24))

        self.label_imc = ctk.CTkLabel(
            self.frame_imc, text="IMC: —",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORES["accent"]
        )
        self.label_imc.pack(pady=(12, 2))

        self.label_categoria = ctk.CTkLabel(
            self.frame_imc, text="Llena peso y altura",
            font=ctk.CTkFont(size=11),
            text_color=COLORES["texto_sec"]
        )
        self.label_categoria.pack(pady=(0, 12))

        # Escuchar cambios en peso y altura para actualizar IMC en tiempo real
        self.entry_peso.bind("<KeyRelease>", self._actualizar_imc_live)
        self.entry_altura.bind("<KeyRelease>", self._actualizar_imc_live)

        # ── Selector de meta ─────────────────────────────────────────────────
        ctk.CTkLabel(
            form, text="¿Cuál es tu objetivo principal?",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORES["texto_sec"]
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 8))

        self.var_meta = ctk.StringVar(value=list(METAS.keys())[0])

        for i, (label_meta, _) in enumerate(METAS.items()):
            ctk.CTkRadioButton(
                form,
                text=label_meta,
                variable=self.var_meta,
                value=label_meta,
                font=ctk.CTkFont(size=13),
                text_color=COLORES["texto"]
            ).grid(row=7 + i, column=0, columnspan=2, sticky="w", padx=30, pady=4)

        # Espacio inferior del formulario
        ctk.CTkFrame(form, height=16, fg_color="transparent").grid(
            row=7 + len(METAS), column=0
        )

        # ── Mensaje de error / éxito ─────────────────────────────────────────
        self.label_mensaje = ctk.CTkLabel(
            scroll, text="",
            font=ctk.CTkFont(size=13),
            text_color=COLORES["error"]
        )
        self.label_mensaje.grid(row=3, column=0, pady=(0, 8))

        # ── Botón guardar ────────────────────────────────────────────────────
        self.btn_guardar = ctk.CTkButton(
            scroll,
            text="  💾  Guardar perfil",
            height=46,
            corner_radius=10,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLORES["accent"],
            hover_color="#3a7ae0",
            command=self._guardar
        )
        self.btn_guardar.grid(row=4, column=0, sticky="ew", pady=(0, 40))

    def _campo_label(self, parent, texto: str, row: int, col: int):
        """Helper para crear etiquetas de campo de formulario."""
        ctk.CTkLabel(
            parent, text=texto,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORES["texto_sec"]
        ).grid(row=row, column=col, sticky="w",
               padx=(20 if col == 0 else 8, 8 if col == 0 else 20),
               pady=(0, 4))

    def _actualizar_imc_live(self, event=None):
        """Actualiza el display de IMC mientras el usuario escribe."""
        try:
            peso = float(self.entry_peso.get())
            altura = float(self.entry_altura.get())
            if peso > 0 and altura > 0:
                imc, categoria = self.db.calcular_imc(peso, altura)
                self.label_imc.configure(text=f"IMC: {imc}")
                self.label_categoria.configure(text=categoria)
        except ValueError:
            self.label_imc.configure(text="IMC: —")
            self.label_categoria.configure(text="Llena peso y altura")

    def _cargar_datos_existentes(self):
        """Si ya hay un perfil, carga los datos en el formulario."""
        perfil = self.db.obtener_perfil()
        if not perfil:
            return

        self.entry_nombre.insert(0, perfil.get("nombre", ""))
        self.entry_edad.insert(0, str(perfil.get("edad", "")))
        self.entry_peso.insert(0, str(perfil.get("peso_kg", "")))
        self.entry_altura.insert(0, str(perfil.get("altura_cm", "")))

        meta_guardada = perfil.get("meta", "")
        if meta_guardada in METAS:
            self.var_meta.set(meta_guardada)

        self._actualizar_imc_live()

    def _guardar(self):
        """Valida los datos y guarda el perfil en la base de datos."""

        # ── Validaciones ──────────────────────────────────────────────────────
        nombre = self.entry_nombre.get().strip()
        if not nombre:
            self._mostrar_error("Por favor escribe tu nombre.")
            return

        try:
            edad = int(self.entry_edad.get())
            if not (5 <= edad <= 120):
                raise ValueError
        except ValueError:
            self._mostrar_error("La edad debe ser un número entre 5 y 120.")
            return

        try:
            peso = float(self.entry_peso.get())
            if not (20 <= peso <= 300):
                raise ValueError
        except ValueError:
            self._mostrar_error("El peso debe estar entre 20 y 300 kg.")
            return

        try:
            altura = float(self.entry_altura.get())
            if not (100 <= altura <= 250):
                raise ValueError
        except ValueError:
            self._mostrar_error("La altura debe estar entre 100 y 250 cm.")
            return

        meta = self.var_meta.get()

        # ── Guardar ───────────────────────────────────────────────────────────
        exito = self.db.guardar_perfil(nombre, edad, peso, altura, meta)

        if exito:
            self._mostrar_exito(f"¡Perfil guardado! Bienvenida, {nombre} 👋")
            if self.callback_guardado:
                self.after(1000, self.callback_guardado)  # espera 1s y navega
        else:
            self._mostrar_error("Ocurrió un error al guardar. Intenta de nuevo.")

    def _mostrar_error(self, mensaje: str):
        self.label_mensaje.configure(text=f"⚠ {mensaje}", text_color=COLORES["error"])

    def _mostrar_exito(self, mensaje: str):
        self.label_mensaje.configure(text=f"✓ {mensaje}", text_color=COLORES["exito"])


# ─── Para probar este módulo de forma independiente ───────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__file__ + "/../.."))
    from backend.database import BaseDatos

    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.geometry("720x700")
    root.title("Test — Perfil")
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)

    db = BaseDatos()
    pantalla = PantallaPerfilConfig(root, db, callback_guardado=lambda: print("Perfil guardado!"))
    pantalla.grid(row=0, column=0, sticky="nsew")
    root.mainloop()
    