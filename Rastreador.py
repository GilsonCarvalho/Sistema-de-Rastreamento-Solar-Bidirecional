import math
import time
import datetime
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ntplib
import numpy as np

# Importação do módulo sun_lo na mesma pasta
from sun_lo import sunpos

# Renderização 3D e Gráficos no Tkinter
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

# Controle de GPIO do Raspberry Pi
try:
    from gpiozero import AngularServo, MCP3008
    HAS_GPIO = True
except (ImportError, NotImplementedError):
    HAS_GPIO = False


# =============================================================================
# INTERFACE GRÁFICA TKINTER
# =============================================================================
class SolarTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Guiamento Solar 3D - Raspberry Pi")
        self.root.geometry("1280x900")

        # Configuração de redimensionamento da janela principal
        self.root.rowconfigure(2, weight=1)
        self.root.columnconfigure(0, weight=1)

        # Variáveis de Configuração da Câmera / Zoom
        self.zoom_scale = 1.3  # Raio da Abóboda

        # Variáveis do Sistema (Default: Maceió)
        self.lat_var = tk.DoubleVar(value=-9.6658)
        self.lng_var = tk.DoubleVar(value=-35.7353)

        self.pin_servo_h = tk.IntVar(value=17)
        self.pin_servo_v = tk.IntVar(value=18)
        self.pin_sensor = tk.IntVar(value=0)

        # Checkbox para leitura automática do sensor
        self.auto_read_power = tk.BooleanVar(value=True)

        # Filtros de Horário para Análise (Potência Instantânea)
        self.start_time_var = tk.StringVar(value="00:00:00")
        self.end_time_var = tk.StringVar(value="23:59:59")

        # Filtros de Horário para Análise (Energia Acumulada)
        self.start_time_acc_var = tk.StringVar(value="00:00:00")
        self.end_time_acc_var = tk.StringVar(value="23:59:59")

        self.azimuth_val = 0.0
        self.elevation_val = 0.0
        self.current_power = 0.0
        self.time_str = "--:--:--"

        # Histórico de Produção
        self.time_history = []
        self.power_history = []
        self.energy_accumulated = []

        self.servo_h = None
        self.servo_v = None

        self.create_menu()
        self.create_widgets()
        self.load_countries()
        self.set_default_maceio()
        self.update_loop()

    def create_menu(self):
        """Cria a barra de menus da aplicação (Menu Bar)"""
        menubar = tk.Menu(self.root)

        # Menu Arquivo
        menu_file = tk.Menu(menubar, tearoff=0)
        menu_file.add_command(label="Salvar Gráfico de Potência Instantânea", command=self.save_inst_chart)
        menu_file.add_command(label="Salvar Gráfico de Energia Acumulada", command=self.save_acc_chart)
        menu_file.add_separator()
        menu_file.add_command(label="Sair", command=self.root.quit)
        menubar.add_cascade(label="Arquivo", menu=menu_file)

        # Menu Ajuda
        menu_help = tk.Menu(menubar, tearoff=0)
        menu_help.add_command(label="Bibliotecas Necessárias", command=self.show_help_libraries)
        menubar.add_cascade(label="Ajuda", menu=menu_help)

        self.root.config(menu=menubar)

    def show_help_libraries(self):
        """Exibe popup informando as bibliotecas Python requeridas pelo projeto"""
        help_text = (
            "Para o funcionamento correto deste sistema, certifique-se de que as seguintes "
            "bibliotecas Python estão instaladas na máquina ou no Raspberry Pi:\n\n"
            "1. matplotlib (Renderização 2D/3D dos gráficos)\n"
            "2. numpy (Cálculos de vetores e superfícies 3D)\n"
            "3. ntplib (Sincronização de horário preciso via rede NTP)\n"
            "4. gpiozero (Controle de servomotores e ADC MCP3008 no Raspberry Pi)\n"
            "5. Pillow (Opcional, para exportação de imagens)\n\n"
            "Comando de instalação recomendado:\n"
            "pip install matplotlib numpy ntplib gpiozero Pillow"
        )
        messagebox.showinfo("Bibliotecas Necessárias", help_text)

    def save_inst_chart(self):
        """Salva a figura do gráfico de potência instantânea em arquivo de imagem"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg"), ("Todos os Arquivos", "*.*")],
            title="Salvar Gráfico de Potência Instantânea"
        )
        if filepath:
            self.fig_inst.savefig(filepath, dpi=300)
            messagebox.showinfo("Sucesso", f"Gráfico salvo com sucesso em:\n{filepath}")

    def save_acc_chart(self):
        """Salva a figura do gráfico de energia acumulada em arquivo de imagem"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg"), ("Todos os Arquivos", "*.*")],
            title="Salvar Gráfico de Energia Acumulada"
        )
        if filepath:
            self.fig_acc.savefig(filepath, dpi=300)
            messagebox.showinfo("Sucesso", f"Gráfico salvo com sucesso em:\n{filepath}")

    def create_widgets(self):
        # 1. PAINEL SUPERIOR: Configurações
        frame_top = ttk.LabelFrame(self.root, text=" Configurações de Localização e Hardware ", padding=6)
        frame_top.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        ttk.Label(frame_top, text="País:").grid(row=0, column=0, sticky=tk.W)
        self.cb_country = ttk.Combobox(frame_top, state="readonly", width=14)
        self.cb_country.grid(row=0, column=1, padx=3)
        self.cb_country.bind("<<ComboboxSelected>>", self.on_country_change)

        ttk.Label(frame_top, text="Estado:").grid(row=0, column=2, sticky=tk.W)
        self.cb_state = ttk.Combobox(frame_top, state="readonly", width=14)
        self.cb_state.grid(row=0, column=3, padx=3)
        self.cb_state.bind("<<ComboboxSelected>>", self.on_state_change)

        ttk.Label(frame_top, text="Cidade:").grid(row=0, column=4, sticky=tk.W)
        self.cb_city = ttk.Combobox(frame_top, state="readonly", width=14)
        self.cb_city.grid(row=0, column=5, padx=3)
        self.cb_city.bind("<<ComboboxSelected>>", self.on_city_change)

        ttk.Label(frame_top, text="Lat:").grid(row=0, column=6, sticky=tk.W)
        ttk.Entry(frame_top, textvariable=self.lat_var, width=8).grid(row=0, column=7, padx=2)

        ttk.Label(frame_top, text="Long:").grid(row=0, column=8, sticky=tk.W)
        ttk.Entry(frame_top, textvariable=self.lng_var, width=8).grid(row=0, column=9, padx=2)

        # Configuração de Pinos GPIO e Checkbox de Leitura Automática
        ttk.Label(frame_top, text="GPIO Servo H:").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(frame_top, textvariable=self.pin_servo_h, width=8).grid(row=1, column=1)

        ttk.Label(frame_top, text="GPIO Servo V:").grid(row=1, column=2, sticky=tk.W)
        ttk.Entry(frame_top, textvariable=self.pin_servo_v, width=8).grid(row=1, column=3)

        ttk.Label(frame_top, text="Pino Sensor:").grid(row=1, column=4, sticky=tk.W)
        ttk.Entry(frame_top, textvariable=self.pin_sensor, width=8).grid(row=1, column=5)

        ttk.Button(frame_top, text="Inicializar GPIO", command=self.setup_gpio).grid(row=1, column=6, columnspan=2, padx=5)

        # Checkbox para habilitar/desabilitar a leitura automática
        chk_auto_read = ttk.Checkbutton(frame_top, text="Leitura Automática de Potência", variable=self.auto_read_power)
        chk_auto_read.grid(row=1, column=8, columnspan=2, sticky=tk.W, padx=5)

        # 2. CARTÕES DE EXIBIÇÃO DE DADOS EM TEMPO REAL
        frame_metrics = ttk.Frame(self.root, padding=4)
        frame_metrics.grid(row=1, column=0, sticky="ew", padx=10, pady=2)

        card_time = ttk.LabelFrame(frame_metrics, text=" Hora (NTP) ", padding=4)
        card_time.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=3)
        self.lbl_time_val = ttk.Label(card_time, text="--:--:--", font=("Consolas", 14, "bold"), foreground="navy")
        self.lbl_time_val.pack()

        card_az = ttk.LabelFrame(frame_metrics, text=" Azimute Solar ", padding=4)
        card_az.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=3)
        self.lbl_az_val = ttk.Label(card_az, text="0.0°", font=("Consolas", 14, "bold"), foreground="green")
        self.lbl_az_val.pack()

        card_el = ttk.LabelFrame(frame_metrics, text=" Elevação Solar ", padding=4)
        card_el.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=3)
        self.lbl_el_val = ttk.Label(card_el, text="0.0°", font=("Consolas", 14, "bold"), foreground="darkorange")
        self.lbl_el_val.pack()

        card_pow = ttk.LabelFrame(frame_metrics, text=" Potência Medida ", padding=4)
        card_pow.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=3)
        self.lbl_pow_val = ttk.Label(card_pow, text="0.0 W", font=("Consolas", 14, "bold"), foreground="red")
        self.lbl_pow_val.pack()

        # 3. PAINEL PRINCIPAL COM ABAS (Expansível)
        self.main_notebook = ttk.Notebook(self.root)
        self.main_notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        # ABA 1: VISUALIZAÇÃO 3D
        self.tab_3d = ttk.Frame(self.main_notebook)
        self.tab_3d.rowconfigure(0, weight=1)
        self.tab_3d.columnconfigure(0, weight=1)
        self.main_notebook.add(self.tab_3d, text=" Simulação 3D do Painel & Abóboda Celeste ")

        self.fig_3d = Figure(figsize=(10, 8), dpi=100)
        self.ax_3d = self.fig_3d.add_subplot(111, projection='3d')
        self.canvas_3d = FigureCanvasTkAgg(self.fig_3d, master=self.tab_3d)
        self.canvas_3d.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        self.canvas_3d.mpl_connect('scroll_event', self.on_scroll_3d)

        # ABA 2: POTÊNCIA INSTANTÂNEA
        self.tab_inst = ttk.Frame(self.main_notebook)
        self.tab_inst.rowconfigure(1, weight=1)
        self.tab_inst.columnconfigure(0, weight=1)
        self.main_notebook.add(self.tab_inst, text=" Gráfico: Potência Instantânea (W) ")

        # Painel Superior de Filtro de Horário
        frame_filter = ttk.Frame(self.tab_inst, padding=4)
        frame_filter.grid(row=0, column=0, sticky="ew", padx=5, pady=2)

        ttk.Label(frame_filter, text="Análise - Hora Inicial (HH:MM:SS):").pack(side=tk.LEFT, padx=3)
        ttk.Entry(frame_filter, textvariable=self.start_time_var, width=10).pack(side=tk.LEFT, padx=3)

        ttk.Label(frame_filter, text="Hora Final (HH:MM:SS):").pack(side=tk.LEFT, padx=3)
        ttk.Entry(frame_filter, textvariable=self.end_time_var, width=10).pack(side=tk.LEFT, padx=3)

        ttk.Button(frame_filter, text="Aplicar Filtro", command=self.render_chart_inst).pack(side=tk.LEFT, padx=8)

        self.fig_inst = Figure(figsize=(10, 8), dpi=100)
        self.ax_inst = self.fig_inst.add_subplot(111)
        self.canvas_inst = FigureCanvasTkAgg(self.fig_inst, master=self.tab_inst)
        self.canvas_inst.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        # ABA 3: ENERGIA ACUMULADA
        self.tab_acc = ttk.Frame(self.main_notebook)
        self.tab_acc.rowconfigure(1, weight=1)
        self.tab_acc.columnconfigure(0, weight=1)
        self.main_notebook.add(self.tab_acc, text=" Gráfico: Energia Acumulada (Wh) ")

        # Painel Superior de Filtro de Horário na Aba de Energia Acumulada
        frame_filter_acc = ttk.Frame(self.tab_acc, padding=4)
        frame_filter_acc.grid(row=0, column=0, sticky="ew", padx=5, pady=2)

        ttk.Label(frame_filter_acc, text="Análise - Hora Inicial (HH:MM:SS):").pack(side=tk.LEFT, padx=3)
        ttk.Entry(frame_filter_acc, textvariable=self.start_time_acc_var, width=10).pack(side=tk.LEFT, padx=3)

        ttk.Label(frame_filter_acc, text="Hora Final (HH:MM:SS):").pack(side=tk.LEFT, padx=3)
        ttk.Entry(frame_filter_acc, textvariable=self.end_time_acc_var, width=10).pack(side=tk.LEFT, padx=3)

        ttk.Button(frame_filter_acc, text="Aplicar Filtro", command=self.render_chart_acc).pack(side=tk.LEFT, padx=8)

        self.fig_acc = Figure(figsize=(10, 8), dpi=100)
        self.ax_acc = self.fig_acc.add_subplot(111)
        self.canvas_acc = FigureCanvasTkAgg(self.fig_acc, master=self.tab_acc)
        self.canvas_acc.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        # Barra de Status
        self.lbl_status = ttk.Label(self.root, text="Inicializando...", font=("Segoe UI", 9))
        self.lbl_status.grid(row=3, column=0, sticky="ew", padx=10, pady=2)

    def on_scroll_3d(self, event):
        if event.button == 'up':
            self.zoom_scale = max(0.6, self.zoom_scale - 0.1)
        elif event.button == 'down':
            self.zoom_scale = min(3.0, self.zoom_scale + 0.1)
        self.render_3d()

    def set_default_maceio(self):
        """Define Maceió - Alagoas - Brazil como padrão nas caixas de seleção"""
        if "Brazil" in self.cb_country['values']:
            self.cb_country.set("Brazil")
            self.on_country_change(None)
            
            if "Alagoas" in self.cb_state['values']:
                self.cb_state.set("Alagoas")
                self.on_state_change(None)
                
                if "Maceió" in self.cb_city['values']:
                    self.cb_city.set("Maceió")
                    self.on_city_change(None)

    # =========================================================================
    # CONEXÃO BANCO DE DADOS E GPIO
    # =========================================================================
    def get_db_connection(self):
        try:
            return sqlite3.connect("worldcities.db")
        except sqlite3.Error:
            return None

    def load_countries(self):
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT country FROM cities ORDER BY country ASC")
            countries = [row[0] for row in cursor.fetchall() if row[0]]
            self.cb_country['values'] = countries
            conn.close()

    def on_country_change(self, event):
        country = self.cb_country.get()
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT admin_name FROM cities WHERE country=? ORDER BY admin_name ASC", (country,))
            states = [row[0] for row in cursor.fetchall() if row[0]]
            self.cb_state['values'] = states
            conn.close()

    def on_state_change(self, event):
        country = self.cb_country.get()
        state = self.cb_state.get()
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT city FROM cities WHERE country=? AND admin_name=? ORDER BY city ASC", (country, state))
            cities = [row[0] for row in cursor.fetchall() if row[0]]
            self.cb_city['values'] = cities
            conn.close()

    def on_city_change(self, event):
        country = self.cb_country.get()
        state = self.cb_state.get()
        city = self.cb_city.get()
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT lat, lng FROM cities WHERE country=? AND admin_name=? AND city=?", (country, state, city))
            row = cursor.fetchone()
            if row:
                self.lat_var.set(row[0])
                self.lng_var.set(row[1])
            conn.close()

    def setup_gpio(self):
        if HAS_GPIO:
            try:
                self.servo_h = AngularServo(self.pin_servo_h.get(), min_angle=0, max_angle=360)
                self.servo_v = AngularServo(self.pin_servo_v.get(), min_angle=0, max_angle=90)
                messagebox.showinfo("Hardware", "Servomotor de rastreamento inicializado com sucesso!")
            except Exception as e:
                messagebox.showerror("Erro GPIO", f"Falha ao iniciar Servos: {e}")
        else:
            messagebox.showwarning("Simulação", "GPIO indisponível. Executando em modo de simulação.")

    def read_power_sensor(self):
        if HAS_GPIO:
            try:
                adc = MCP3008(channel=self.pin_sensor.get())
                return adc.value * 100.0
            except Exception:
                pass
        
        if self.elevation_val > 0:
            return math.sin(math.radians(self.elevation_val)) * 85.0
        return 0.0

    def get_internet_time(self):
        try:
            client = ntplib.NTPClient()
            response = client.request('pool.ntp.org', timeout=1)
            return datetime.datetime.fromtimestamp(response.tx_time, datetime.timezone.utc)
        except Exception:
            return datetime.datetime.now(datetime.timezone.utc)

    # =========================================================================
    # LAÇO PRINCIPAL E RENDERIZAÇÃO 3D
    # =========================================================================
    def update_loop(self):
        now_utc = self.get_internet_time()
        when = [now_utc.year, now_utc.month, now_utc.day, now_utc.hour, now_utc.minute, now_utc.second, 0]
        where = [self.lat_var.get(), self.lng_var.get()]

        self.azimuth_val, self.elevation_val = sunpos(when, where, refract=True)

        if HAS_GPIO and self.servo_h and self.servo_v:
            self.servo_h.angle = self.azimuth_val
            self.servo_v.angle = max(0, min(90, self.elevation_val))

        # Verifica a opção da Checkbox para leitura automática de potência
        if self.auto_read_power.get():
            self.current_power = self.read_power_sensor()
        
        now_local = now_utc.astimezone()
        self.time_str = now_local.strftime("%H:%M:%S")

        self.lbl_time_val.config(text=self.time_str)
        self.lbl_az_val.config(text=f"{self.azimuth_val:.2f}°")
        self.lbl_el_val.config(text=f"{self.elevation_val:.2f}°")
        self.lbl_pow_val.config(text=f"{self.current_power:.2f} W")

        if self.auto_read_power.get():
            self.time_history.append(self.time_str)
            self.power_history.append(self.current_power)
            
            acc = self.energy_accumulated[-1] + (self.current_power / 3600.0) if self.energy_accumulated else 0.0
            self.energy_accumulated.append(acc)

        selected_tab = self.main_notebook.index(self.main_notebook.select())
        if selected_tab == 0:
            self.render_3d()
        elif selected_tab == 1:
            self.render_chart_inst()
        elif selected_tab == 2:
            self.render_chart_acc()

        self.lbl_status.config(text=f"Última Atualização NTP: {now_local.strftime('%d/%m/%Y %H:%M:%S')} | Lat: {self.lat_var.get()} | Lng: {self.lng_var.get()}")

        self.root.after(2000, self.update_loop)

    def render_3d(self):
        self.ax_3d.clear()
        self.ax_3d.set_title("Guiamento Solar com Abóboda Celeste Semiesférica", fontsize=11, fontweight="bold")
        
        R = 1.3

        # Proporção geométrica real para manter raio R na base e na altura
        self.ax_3d.set_box_aspect([1, 1, 0.65])

        # Limites de visualização
        lim = self.zoom_scale
        self.ax_3d.set_xlim([-lim, lim])
        self.ax_3d.set_ylim([-lim, lim])
        self.ax_3d.set_zlim([0, lim * 0.95])

        # Remove eixos e caixas padrão
        self.ax_3d.axis('off')

        # Ajuste de margens manual para não deformar a geometria semiesférica
        self.fig_3d.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=0.92)

        # Grade manual no piso (Z = 0)
        for i in np.linspace(-R, R, 13):
            self.ax_3d.plot([i, i], [-R, R], [0, 0], color='gray', linestyle='-', alpha=0.15, linewidth=1)
            self.ax_3d.plot([-R, R], [i, i], [0, 0], color='gray', linestyle='-', alpha=0.15, linewidth=1)

        # 1. ABÓBODA CELESTE (Semiesfera Isométrica)
        u = np.linspace(0, 2 * np.pi, 50)
        v = np.linspace(0, np.pi / 2, 25)
        x_domo = R * np.outer(np.cos(u), np.sin(v))
        y_domo = R * np.outer(np.sin(u), np.sin(v))
        z_domo = R * np.outer(np.ones(np.size(u)), np.cos(v))

        self.ax_3d.plot_surface(x_domo, y_domo, z_domo, color='skyblue', alpha=0.08, edgecolor='deepskyblue', linewidth=0.25)

        # 2. ROSA DOS VENTOS E PLANO DO CHÃO
        self.ax_3d.plot([-R, R], [0, 0], [0, 0], color='gray', linestyle='--', alpha=0.3)
        self.ax_3d.plot([0, 0], [-R, R], [0, 0], color='gray', linestyle='--', alpha=0.3)
        self.ax_3d.text(0, R*1.05, 0, "Norte", color='green', fontweight='bold', ha='center')
        self.ax_3d.text(0, -R*1.05, 0, "Sul", color='red', fontweight='bold', ha='center')
        self.ax_3d.text(R*1.05, 0, 0, "Leste", color='blue', fontweight='bold', ha='center')
        self.ax_3d.text(-R*1.05, 0, 0, "Oeste", color='purple', fontweight='bold', ha='center')

        # COORDENADAS 3D DO SOL
        az_rad = math.radians(self.azimuth_val)
        el_rad = math.radians(self.elevation_val)

        sun_x = R * math.cos(el_rad) * math.sin(az_rad)
        sun_y = R * math.cos(el_rad) * math.cos(az_rad)
        sun_z = R * math.sin(el_rad)

        center_z = 0.35

        # 3. EXIBIÇÃO DO SOL E LINHA DE INCIDÊNCIA
        if self.elevation_val > 0:
            self.ax_3d.scatter([sun_x], [sun_y], [sun_z], color='gold', s=220, edgecolors='orange', linewidths=1.5, zorder=10)
            self.ax_3d.plot([0, sun_x], [0, sun_y], [center_z, sun_z], color='gold', linestyle='--', linewidth=2.0)

            proj_x = R * 0.6 * math.sin(az_rad)
            proj_y = R * 0.6 * math.cos(az_rad)
            self.ax_3d.plot([0, proj_x], [0, proj_y], [0, 0], color='darkgreen', linestyle='-', linewidth=1.2)
            self.ax_3d.plot([proj_x, sun_x], [proj_y, sun_y], [0, sun_z], color='gray', linestyle=':', linewidth=0.8)

            az_arc = np.linspace(0, az_rad, 20)
            self.ax_3d.plot(0.3 * np.sin(az_arc), 0.3 * np.cos(az_arc), np.zeros_like(az_arc), color='green', linewidth=1.8)

            el_arc = np.linspace(0, el_rad, 20)
            arc_x = 0.5 * np.cos(el_arc) * math.sin(az_rad)
            arc_y = 0.5 * np.cos(el_arc) * math.cos(az_rad)
            arc_z = 0.5 * np.sin(el_arc)
            self.ax_3d.plot(arc_x, arc_y, arc_z, color='orange', linewidth=1.8)

        # 4. MODELO MECÂNICO DO PAINEL SOLAR
        self.ax_3d.plot([0, 0], [0, 0], [0, center_z], color='black', linewidth=4)
        self.ax_3d.scatter([0], [0], [center_z], color='gray', s=80)

        width, height = 0.55, 0.4
        u_x, u_y, u_z = math.cos(az_rad), -math.sin(az_rad), 0
        v_x = -math.sin(el_rad) * math.sin(az_rad)
        v_y = -math.sin(el_rad) * math.cos(az_rad)
        v_z = math.cos(el_rad)

        corners = []
        for dx, dy in [(-width/2, -height/2), (width/2, -height/2), (width/2, height/2), (-width/2, height/2)]:
            cx = dx * u_x + dy * v_x
            cy = dx * u_y + dy * v_y
            cz = center_z + dx * u_z + dy * v_z
            corners.append((cx, cy, cz))

        xs = [c[0] for c in corners] + [corners[0][0]]
        ys = [c[1] for c in corners] + [corners[0][1]]
        zs = [c[2] for c in corners] + [corners[0][2]]
        
        self.ax_3d.plot(xs, ys, zs, color='midnightblue', linewidth=2.5)

        grid_x = np.array([[corners[0][0], corners[1][0]], [corners[3][0], corners[2][0]]])
        grid_y = np.array([[corners[0][1], corners[1][1]], [corners[3][1], corners[2][1]]])
        grid_z = np.array([[corners[0][2], corners[1][2]], [corners[3][2], corners[2][2]]])

        self.ax_3d.plot_surface(grid_x, grid_y, grid_z, color='navy', alpha=0.9, rstride=1, cstride=1, edgecolor='cyan', linewidth=0.6)

        self.canvas_3d.draw()

    def render_chart_inst(self):
        self.ax_inst.clear()
        
        # Filtragem por intervalo de horário estipulado
        filtered_times = []
        filtered_powers = []

        start_str = self.start_time_var.get().strip()
        end_str = self.end_time_var.get().strip()

        for t_str, p_val in zip(self.time_history, self.power_history):
            if start_str <= t_str <= end_str:
                filtered_times.append(t_str)
                filtered_powers.append(p_val)

        if filtered_times:
            self.ax_inst.plot(filtered_times, filtered_powers, color='tab:orange', marker='o', linewidth=1.5, markersize=4)

            # CALCULAR O MÁXIMO COM FOLGA NO TETO (ex: +20% acima do pico)
            max_p = max(filtered_powers)
            y_top = max(max_p * 1.20, 10.0)  # Mínimo de 10W para não ficar achatado se for 0
            self.ax_inst.set_ylim(bottom=0, top=y_top)
        else:
            self.ax_inst.set_ylim(bottom=0, top=100)

        self.ax_inst.set_title("Potência Instantânea Gerada (Watts)")
        self.ax_inst.set_ylabel("Potência (W)")
        self.ax_inst.set_xlabel("Hora")
        self.ax_inst.grid(True, linestyle="--", alpha=0.5)

        # Ajuste de limite máximo de rótulos no Eixo X para evitar sobreposição
        self.ax_inst.xaxis.set_major_locator(ticker.MaxNLocator(nbins=10))
        self.ax_inst.tick_params(axis='x', rotation=30, labelsize=8)
        
        self.fig_inst.tight_layout()
        self.canvas_inst.draw()

    def render_chart_acc(self):
        self.ax_acc.clear()

        # Filtragem por intervalo de horário estipulado para a Energia Acumulada
        filtered_times = []
        filtered_energy = []

        start_str = self.start_time_acc_var.get().strip()
        end_str = self.end_time_acc_var.get().strip()

        for t_str, e_val in zip(self.time_history, self.energy_accumulated):
            if start_str <= t_str <= end_str:
                filtered_times.append(t_str)
                filtered_energy.append(e_val)

        if filtered_times:
            self.ax_acc.plot(filtered_times, filtered_energy, color='tab:green', linewidth=2, marker='o', markersize=3)

            # CALCULAR O MÁXIMO COM FOLGA NO TETO (+20% acima do pico)
            max_e = max(filtered_energy)
            y_top = max(max_e * 1.20, 5.0)  # Mínimo de 5Wh
            self.ax_acc.set_ylim(bottom=0, top=y_top)
        else:
            self.ax_acc.set_ylim(bottom=0, top=50)

        self.ax_acc.set_title("Energia Acumulada Gerada no Dia (Wh)")
        self.ax_acc.set_ylabel("Energia (Wh)")
        self.ax_acc.set_xlabel("Hora")
        self.ax_acc.grid(True, linestyle="--", alpha=0.5)

        # Ajuste de limite máximo de rótulos no Eixo X para evitar sobreposição
        self.ax_acc.xaxis.set_major_locator(ticker.MaxNLocator(nbins=10))
        self.ax_acc.tick_params(axis='x', rotation=30, labelsize=8)
        
        self.fig_acc.tight_layout()
        self.canvas_acc.draw()


if __name__ == "__main__":
    root = tk.Tk()
    app = SolarTrackerApp(root)
    root.mainloop()
