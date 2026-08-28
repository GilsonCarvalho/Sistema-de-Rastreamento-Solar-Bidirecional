import datetime
import os
import sys
import time
import tkinter as tk
from tkinter import messagebox, ttk
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import pandas as pd
from pvlib import solarposition
import pytz

# ==============================================================================
# CORREÇÃO PARA TELAS 4K / HIGH DPI (Ativa antes de criar qualquer janela)
# ==============================================================================
try:
    if sys.platform.startswith("win"):
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_TRIGGERED
except Exception:
    pass  # Caso não esteja no Windows ou falhe, ignora e segue o padrão

# ==========================================
# CONFIGURAÇÕES INICIAIS DEFAULT (MACEIÓ)
# ==========================================
DEFAULT_CONFIG = {
    "lat": -9.6658,
    "lon": -35.7350,
    "alt": 15,
    "tz": "America/Maceio",
}


class RastreadorSolarApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Simulador de Rastreador Solar MDF 2-Eixos")

        # Define um tamanho inicial generoso, mas responsivo
        self.root.geometry("1400x850")

        # Configura o gerenciador de peso das linhas e colunas para esticar em 4K
        self.root.columnconfigure(0, weight=0)  # Painel de controle fixo na largura
        self.root.columnconfigure(1, weight=1)  # Gráfico 3D expande para ocupar o resto
        self.root.rowconfigure(0, weight=1)

        # Variáveis de estado
        self.animacao_rodando = True
        self.primeira_execucao = True

        # Configuração da UI
        self.criar_painel_controle()
        self.criar_visualizacao_3d()

    def criar_painel_controle(self):
        # Frame principal para controles com padding adaptável
        control_frame = ttk.Frame(self.root, padding="15")
        control_frame.grid(row=0, column=0, sticky="nsew")

        # Estilo para aumentar fontes em telas 4K
        style = ttk.Style()
        style.configure(".", font=("Arial", 11))
        style.configure("Titulo.TLabel", font=("Arial", 13, "bold"))

        ttk.Label(
            control_frame,
            text="Configurações de Localização",
            style="Titulo.TLabel",
        ).pack(pady=15)

        # Latitude, Longitude, Altitude
        row1 = ttk.Frame(control_frame)
        row1.pack(fill=tk.X, pady=5)
        ttk.Label(row1, text="Lat:").pack(side=tk.LEFT)
        self.ent_lat = ttk.Entry(row1, width=10)
        self.ent_lat.insert(0, str(DEFAULT_CONFIG["lat"]))
        self.ent_lat.pack(side=tk.LEFT, padx=5)

        ttk.Label(row1, text="Lon:").pack(side=tk.LEFT, padx=5)
        self.ent_lon = ttk.Entry(row1, width=10)
        self.ent_lon.insert(0, str(DEFAULT_CONFIG["lon"]))
        self.ent_lon.pack(side=tk.LEFT)

        row2 = ttk.Frame(control_frame)
        row2.pack(fill=tk.X, pady=5)
        ttk.Label(row2, text="Alt (m):").pack(side=tk.LEFT)
        self.ent_alt = ttk.Entry(row2, width=10)
        self.ent_alt.insert(0, str(DEFAULT_CONFIG["alt"]))
        self.ent_alt.pack(side=tk.LEFT, padx=5)

        # Fuso Horário
        ttk.Label(
            control_frame, text="Fuso Horário (ex: America/Maceio):"
        ).pack(pady=(10, 0), anchor=tk.W)
        self.ent_tz = ttk.Entry(control_frame, width=25)
        self.ent_tz.insert(0, DEFAULT_CONFIG["tz"])
        self.ent_tz.pack(pady=5, fill=tk.X)

        ttk.Separator(control_frame, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=15
        )

        # Configurações de Tempo
        ttk.Label(
            control_frame, text="Configurações de Tempo", style="Titulo.TLabel"
        ).pack(pady=10)

        self.usar_horario_pc = tk.BooleanVar(value=True)
        self.chk_tempo = ttk.Checkbutton(
            control_frame,
            text="Usar Horário do Computador",
            variable=self.usar_horario_pc,
            command=self.toggle_tempo_manual,
        )
        self.chk_tempo.pack(pady=5, anchor=tk.W)

        # Entrada Manual de Tempo
        self.manual_frame = ttk.LabelFrame(
            control_frame, text="Tempo Manual (DD/MM/AAAA HH:MM)", padding="5"
        )
        self.manual_frame.pack(pady=5, fill=tk.X)

        self.ent_data = ttk.Entry(self.manual_frame, width=12)
        self.ent_data.insert(0, datetime.date.today().strftime("%d/%m/%Y"))
        self.ent_data.pack(side=tk.LEFT, padx=2)

        self.ent_hora = ttk.Entry(self.manual_frame, width=8)
        self.ent_hora.insert(0, datetime.datetime.now().strftime("%H:%M"))
        self.ent_hora.pack(side=tk.LEFT, padx=2)

        self.toggle_tempo_manual()

        # Botão para aplicar
        self.btn_aplicar = ttk.Button(
            control_frame, text="Aplicar e Atualizar", command=self.reiniciar_animacao
        )
        self.btn_aplicar.pack(pady=20, fill=tk.X)

        # Área de log
        self.txt_log = tk.Text(
            control_frame, height=12, width=35, state=tk.DISABLED, font=("Consolas", 10)
        )
        self.txt_log.pack(pady=10, fill=tk.BOTH, expand=True)

    def log(self, mensagem):
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.insert(tk.END, mensagem + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state=tk.DISABLED)

    def toggle_tempo_manual(self):
        estado = tk.DISABLED if self.usar_horario_pc.get() else tk.NORMAL
        for child in self.manual_frame.winfo_children():
            child.configure(state=estado)

    def criar_visualizacao_3d(self):
        # matplotlib se ajustará ao DPI do sistema automaticamente agora
        self.fig = plt.figure(figsize=(8, 8))
        self.ax = self.fig.add_subplot(111, projection="3d")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

    def calcular_posicao_sol(self):
        try:
            lat = float(self.ent_lat.get())
            lon = float(self.ent_lon.get())
            alt = float(self.ent_alt.get())
            tz_str = self.ent_tz.get()

            if self.usar_horario_pc.get():
                dt = datetime.datetime.now()
            else:
                data_str = self.ent_data.get()
                hora_str = self.ent_hora.get()
                dt = datetime.datetime.strptime(
                    f"{data_str} {hora_str}", "%d/%m/%Y %H:%M"
                )

            times = pd.DatetimeIndex([dt]).tz_localize(tz_str)
            sol = solarposition.get_solarposition(times, lat, lon, altitude=alt)
            azimute = sol["azimuth"].values[0]
            elevacao = sol["apparent_elevation"].values[0]

            return dt, azimute, elevacao, tz_str
        except Exception as e:
            messagebox.showerror(
                "Erro de Entrada", f"Falha ao calcular posição do sol:\n{e}"
            )
            self.animacao_rodando = False
            return None, None, None, None

    def desenhar_mecanismo(self, azimute, elevacao, tempo, tz_str):
        elev_atual, azim_atual = self.ax.elev, self.ax.azim
        self.ax.cla()

        lim = 1.5
        self.ax.set_xlim([-lim, lim])
        self.ax.set_ylim([-lim, lim])
        self.ax.set_zlim([0, lim * 1.2])
        self.ax.set_xlabel("Oeste (-) / Leste (+)")
        self.ax.set_ylabel("Sul (-) / Norte (+)")
        self.ax.set_zlabel("Zênite (Altura)")

        titulo = (
            f"Rastreador: {tempo.strftime('%Y-%m-%d %H:%M:%S')} ({tz_str})\n"
            f"Sol: Az={azimute:.1f}°, El={elevacao:.1f}°"
        )
        self.ax.set_title(titulo, fontsize=12)

        # 1. Bússola de Solo
        circle_steps = 100
        angles = np.linspace(0, 2 * np.pi, circle_steps)
        r_ground = 1.2
        self.ax.plot(
            r_ground * np.sin(angles),
            r_ground * np.cos(angles),
            [0] * circle_steps,
            color="gray",
            linestyle="--",
        )
        self.ax.text(
            0, r_ground + 0.1, 0, "N", color="black", fontweight="bold", ha="center"
        )
        self.ax.text(
            0,
            -r_ground - 0.2,
            0,
            "S",
            color="black",
            fontweight="bold",
            ha="center",
        )
        self.ax.text(
            r_ground + 0.1,
            0,
            0,
            "L",
            color="black",
            fontweight="bold",
            ha="center",
        )
        self.ax.text(
            -r_ground - 0.2,
            0,
            0,
            "O",
            color="black",
            fontweight="bold",
            ha="center",
        )

        # 2. Ângulos e Vetores
        az_rad = np.radians(90 - azimute)
        if elevacao < 0:
            elevacao = 0
        el_rad = np.radians(elevacao)

        # Vetor do Sol
        x_sol = np.cos(el_rad) * np.sin(az_rad)
        y_sol = np.cos(el_rad) * np.cos(az_rad)
        z_sol = np.sin(el_rad)

        # 3. CONSTRUÇÃO GEOMÉTRICA DO RASTREADOR (MDF)
        r_base = 0.3
        self.ax.plot(
            r_base * np.sin(angles),
            r_base * np.cos(angles),
            [0.1] * circle_steps,
            color="saddlebrown",
            linewidth=2,
        )

        h_pivo = 0.6
        d_placas = 0.2

        dx = d_placas * np.cos(az_rad)
        dy = -d_placas * np.sin(az_rad)

        # Torres de MDF
        self.ax.plot(
            [dx / 2, dx / 2],
            [dy / 2, dy / 2],
            [0.1, h_pivo],
            color="burlywood",
            linewidth=5,
        )
        self.ax.plot(
            [-dx / 2, -dx / 2],
            [-dy / 2, -dy / 2],
            [0.1, h_pivo],
            color="burlywood",
            linewidth=5,
            label="Torre MDF",
        )

        # Eixo Servo V
        self.ax.plot(
            [dx / 2, -dx / 2],
            [dy / 2, -dy / 2],
            [h_pivo, h_pivo],
            color="silver",
            linewidth=3,
            label="Eixo Servo V",
        )

        # 4. DESENHO DO PAINEL SOLAR CENTRALIZADO E LARGO
        panel_w = 1.2
        panel_h = 0.7

        corners = np.array([
            [-panel_w / 2, -panel_h / 2, 0],
            [panel_w / 2, -panel_h / 2, 0],
            [panel_w / 2, panel_h / 2, 0],
            [-panel_w / 2, panel_h / 2, 0],
        ])

        R_az = np.array([
            [np.cos(az_rad), -np.sin(az_rad), 0],
            [np.sin(az_rad), np.cos(az_rad), 0],
            [0, 0, 1],
        ])

        axis_v = np.array([-np.cos(az_rad), np.sin(az_rad), 0])

        def rotation_matrix_axis(axis, theta):
            axis = axis / np.sqrt(np.dot(axis, axis))
            a = np.cos(theta / 2.0)
            b, c, d = -axis * np.sin(theta / 2.0)
            aa, bb, cc, dd = a * a, b * b, c * c, d * d
            bc, ad, ac, ab, bd, cd = b * c, a * d, a * c, a * b, b * d, c * d
            return np.array([
                [aa + bb - cc - dd, 2 * (bc + ad), 2 * (bd - ac)],
                [2 * (bc - ad), aa + cc - bb - dd, 2 * (cd + ab)],
                [2 * (bd + ac), 2 * (cd - ab), aa + dd - bb - cc],
            ])

        R_el = rotation_matrix_axis(axis_v, -el_rad)
        R_comp = np.dot(R_az, R_el)

        rotated_corners = np.dot(corners, R_comp.T)
        final_corners = rotated_corners + np.array([0, 0, h_pivo])

        # Painel Solar
        self.ax.plot_trisurf(
            final_corners[:, 0],
            final_corners[:, 1],
            final_corners[:, 2],
            color="dodgerblue",
            alpha=0.8,
            label="Painel Solar",
        )

        # Vetor normal
        self.ax.quiver(
            0,
            0,
            h_pivo,
            x_sol * 0.4,
            y_sol * 0.4,
            z_sol * 0.4,
            color="red",
            linewidth=2,
            arrow_length_ratio=0.1,
        )

        # 5. LINHA DO SOL
        dist_sol = lim * 1.1
        self.ax.plot(
            [0, x_sol * dist_sol],
            [0, y_sol * dist_sol],
            [0, z_sol * dist_sol],
            color="gold",
            linestyle="--",
            linewidth=1.5,
            marker="o",
            markersize=10,
            label="Sol",
        )

        self.ax.legend(loc="upper right")

        if self.primeira_execucao:
            self.ax.view_init(elev=25, azim=45)
            self.primeira_execucao = False
        else:
            self.ax.view_init(elev=elev_atual, azim=azim_atual)


    def animar(self, frame):
        if not self.animacao_rodando:
            return

        tempo, azimute, elevacao, tz_str = self.calcular_posicao_sol()
        if tempo:
            self.desenhar_mecanismo(azimute, elevacao, tempo, tz_str)
            self.canvas.draw()

    def reiniciar_animacao(self):
        self.animacao_rodando = True
        tempo, azimute, elevacao, tz_str = self.calcular_posicao_sol()
        if tempo:
            self.log(
                f"Atualizado: Lat={self.ent_lat.get()}, Lon={self.ent_lon.get()}"
            )
            if not hasattr(self, "ani") or self.ani.event_source is None:
                self.ani = FuncAnimation(
                    self.fig, self.animar, interval=1000, cache_frame_data=False
                )


if __name__ == "__main__":
    root = tk.Tk()
    app = RastreadorSolarApp(root)
    app.ani = FuncAnimation(
        app.fig, app.animar, interval=1000, cache_frame_data=False
    )
    root.mainloop()