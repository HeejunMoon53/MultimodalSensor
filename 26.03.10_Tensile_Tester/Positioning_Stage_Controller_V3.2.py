# =============================================================================
# Project: Positioning Stage Controller (Real-Time UI)
# Author: Heejun Moon
# Date: 2026-03-10
# Description: 
#   3축-5개 스테핑 모터 스테이지 제어 및 모니터링을 위한 실시간 UI 프로그램.
#   수동 조그(Jog) 이동, 캘리브레이션, 시퀀스 프로그래밍 및 하드웨어/소프트웨어 
#   안전 리밋 기능을 지원함.
#
# [Update History]
#   - V3.2 (2026-03-10): 
#       * 설정(Settings) 창 추가 (통신,하드웨어,안전리밋,조그스텝)
#       * 시퀀스 클립보드 리스트 단축키 기능 추가 (Ctrl+C 복사, Ctrl+V 붙여넣기, Delete 다중 삭제)
#   - V3.1 (2026-02-28):
#       * [안전] 리미트 스위치 및 Emergency 기능 추가
# =============================================================================

import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import time
import copy 

# --- [안전 설정 - 하드웨어 리밋)] ---
LIMIT_MIN_MM = -200.0
LIMIT_MAX_MM = 200.0

class TensileTesterRealTimeUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Positioning Stage Controller V3.2")
        self.root.geometry("1100x950")
        
        self.ser = None
        self.sequence_data = [] 
        self.clipboard_data = [] 
        self.editing_index = None
        self.is_running_sequence = False 

        # --- [동적 설정 변수들] ---
        self.baud_rate = tk.IntVar(value=115200)
        self.microstep = tk.IntVar(value=8)
        self.screw_pitch = tk.DoubleVar(value=5.0)  # SFU1605
        self.steps_per_mm = self.calc_steps_per_mm()
        
        # 소프트웨어 리밋 설정
        self.enable_limits = tk.BooleanVar(value=True)
        self.limit_dist_mm = tk.DoubleVar(value=50.0)
        self.limit_speed_mms = tk.DoubleVar(value=10.0)
        
        # Jog 커스텀 버튼 값 설정
        self.jog_val_small = tk.DoubleVar(value=0.1)
        self.jog_val_mid = tk.DoubleVar(value=1.0)
        self.jog_val_large = tk.DoubleVar(value=5.0)
        self.jog_speed_mms = tk.DoubleVar(value=5.0)

        # ==============================
        # 1. 상단 좌표 모니터
        # ==============================
        monitor_frame = tk.Frame(root, bg="#222", padx=10, pady=10)
        monitor_frame.pack(fill="x")
        
        tk.Label(monitor_frame, text="LIVE POSITION (mm):", bg="#222", fg="white", font=("Arial", 10)).pack(side="left", padx=10)
        
        self.pos_labels = {}
        axes = ["XA", "XB", "YA", "YB", "Z"]
        for axis in axes:
            lbl = tk.Label(monitor_frame, text=f"{axis}: 0.000", bg="black", fg="#00ff00", font=("Consolas", 16, "bold"), width=12, relief="sunken", bd=1)
            lbl.pack(side="left", padx=5)
            self.pos_labels[axis] = lbl
            
        # ==============================
        # 2. 연결 및 제어 바
        # ==============================
        top_frame = tk.Frame(root, padx=10, pady=10, bg="#e6e6e6", relief="raised", bd=2)
        top_frame.pack(fill="x")
        
        tk.Label(top_frame, text="Serial Port:", bg="#e6e6e6", font=("Arial", 11, "bold")).pack(side="left", padx=5)
        self.port_combo = ttk.Combobox(top_frame, width=15, font=("Arial", 10))
        self.port_combo.pack(side="left", padx=5)
        
        tk.Button(top_frame, text="⟳", command=self.refresh_ports, width=3).pack(side="left", padx=2)
        self.refresh_ports()
        
        self.btn_connect = tk.Button(top_frame, text="▶ CONNECT", command=self.toggle_connect, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), width=15, relief="raised")
        self.btn_connect.pack(side="left", padx=15)
        self.lbl_status = tk.Label(top_frame, text="Disconnected", fg="red", bg="#e6e6e6", font=("Arial", 10))
        self.lbl_status.pack(side="left", padx=5)

        self.btn_settings = tk.Button(top_frame, text="⚙ Settings", command=self.open_settings, bg="#ddd", font=("Arial", 10, "bold"))
        self.btn_settings.pack(side="right", padx=5)

        self.btn_enable = tk.Button(top_frame, text="Motor LOCKED", bg="orange", command=self.toggle_enable, width=15, font=("Arial", 10, "bold"))
        self.btn_enable.pack(side="right", padx=10)

        self.btn_emg_reset = tk.Button(top_frame, text="EMG NORMAL", bg="gray", fg="white", font=("Arial", 10, "bold"), width=15, command=self.send_emg_reset)
        self.btn_emg_reset.pack(side="right", padx=10)

        self.jog_btns = {ax: {'in': [], 'out': []} for ax in axes}

        # ==============================
        # 3. 탭 구성
        # ==============================
        style = ttk.Style()
        style.configure("TNotebook.Tab", font=("Arial", 11, "bold"), padding=[10, 5])
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=5)

        self.calib_frame = tk.Frame(self.notebook)
        self.notebook.add(self.calib_frame, text="  1. Calibration (Manual)  ")
        self.setup_calibration_tab()

        self.seq_frame = tk.Frame(self.notebook)
        self.notebook.add(self.seq_frame, text="  2. Sequence Program  ")
        self.setup_sequence_tab()

        self.log_text = tk.Text(root, height=7, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 10))
        self.log_text.pack(fill="x", padx=10, pady=5)

        self.update_monitor_loop()

    # --- 계산 함수 ---
    def calc_steps_per_mm(self):
        return (200.0 * self.microstep.get()) / self.screw_pitch.get()

    # --- 설정(Settings) 창 ---
    def open_settings(self):
        set_win = tk.Toplevel(self.root)
        set_win.title("System Settings")
        set_win.geometry("400x500")
        set_win.grab_set() 
        
        # 1. 하드웨어 세팅
        lf_hw = tk.LabelFrame(set_win, text="1. Hardware & Comm Settings", font=("Arial", 10, "bold"), padx=10, pady=10)
        lf_hw.pack(fill="x", padx=10, pady=10)
        
        tk.Label(lf_hw, text="Baud Rate                  ").grid(row=0, column=0, sticky="e", pady=2)
        ttk.Combobox(lf_hw, textvariable=self.baud_rate, values=[9600, 115200, 250000], width=10).grid(row=0, column=1, sticky="w")
        
        tk.Label(lf_hw, text="Motor Microstep         ").grid(row=1, column=0, sticky="e", pady=2)
        ttk.Combobox(lf_hw, textvariable=self.microstep, values=[1, 2, 4, 8, 16, 32], width=10).grid(row=1, column=1, sticky="w")
        
        tk.Label(lf_hw, text="Screw Pitch (mm/rev)  ").grid(row=2, column=0, sticky="e", pady=2)
        tk.Entry(lf_hw, textvariable=self.screw_pitch, width=12).grid(row=2, column=1, sticky="w")
        
        # 2. 소프트웨어 리밋 설정
        lf_limit = tk.LabelFrame(set_win, text="2. Software Safety Limits", font=("Arial", 10, "bold"), padx=10, pady=10)
        lf_limit.pack(fill="x", padx=10, pady=5)
        
        tk.Checkbutton(lf_limit, text="Enable", variable=self.enable_limits, font=("Arial", 9, "bold")).pack(anchor="w", pady=5)
        
        f_l1 = tk.Frame(lf_limit); f_l1.pack(fill="x", pady=2)
        tk.Label(f_l1, text="Maximum Distance (mm)", width=20, anchor="e").pack(side="left")
        tk.Entry(f_l1, textvariable=self.limit_dist_mm, width=10).pack(side="left", padx=5)

        f_l2 = tk.Frame(lf_limit); f_l2.pack(fill="x", pady=2)
        tk.Label(f_l2, text="Maximum Speed (mm/s) ", width=20, anchor="e").pack(side="left")
        tk.Entry(f_l2, textvariable=self.limit_speed_mms, width=10).pack(side="left", padx=5)

        # 3. 조그 버튼 이동량 설정
        lf_jog = tk.LabelFrame(set_win, text="3. Jog Button Steps (mm)", font=("Arial", 10, "bold"), padx=10, pady=10)
        lf_jog.pack(fill="x", padx=10, pady=10)
        
        tk.Label(lf_jog, text="Small (<, >)          ").grid(row=0, column=0, sticky="e", pady=2)
        tk.Entry(lf_jog, textvariable=self.jog_val_small, width=10).grid(row=0, column=1, padx=5)
        
        tk.Label(lf_jog, text="Mid (<<, >>)        ").grid(row=1, column=0, sticky="e", pady=2)
        tk.Entry(lf_jog, textvariable=self.jog_val_mid, width=10).grid(row=1, column=1, padx=5)
        
        tk.Label(lf_jog, text="Large (<<<, >>>)  ").grid(row=2, column=0, sticky="e", pady=2)
        tk.Entry(lf_jog, textvariable=self.jog_val_large, width=10).grid(row=2, column=1, padx=5)

        tk.Label(lf_jog, text="Jog Speed (mm/s) ").grid(row=3, column=0, sticky="e", pady=(10, 2))
        tk.Entry(lf_jog, textvariable=self.jog_speed_mms, width=10, bg="#eef").grid(row=3, column=1, padx=5, pady=(10, 2))

        # 적용 버튼
        tk.Button(set_win, text="Apply", bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), command=lambda: self.apply_settings(set_win)).pack(pady=10)

    def apply_settings(self, window):
        try:
            self.steps_per_mm = self.calc_steps_per_mm()
            self.log(f"[설정 변경] STEPS_PER_MM 업데이트됨: {self.steps_per_mm:.2f}")
            self.update_jog_button_texts()
            window.destroy()
        except Exception as e:
            messagebox.showerror("입력 오류", "숫자를 올바르게 입력해주세요.")

    # --- Calibration Tab ---
    def setup_calibration_tab(self):
        center_frame = tk.Frame(self.calib_frame)
        center_frame.pack(expand=True, fill="both", padx=20, pady=20)
        tk.Label(center_frame, text="Manual Position Adjustment (mm)", font=("Arial", 16, "bold"), fg="#333").pack(pady=(0, 20))
        control_frame = tk.Frame(center_frame); control_frame.pack(anchor="center")
        axes = ["XA", "XB", "YA", "YB", "Z"]
        btn_w, btn_h = 6, 2
        
        for i, axis in enumerate(axes):
            f = tk.LabelFrame(control_frame, text=f" Motor {axis} ", font=("Arial", 11, "bold"), labelanchor="n")
            f.grid(row=i, column=0, padx=10, pady=10, sticky="ew")
            inner = tk.Frame(f); inner.pack(padx=10, pady=5)
            
            def make_jog_cmd(ax, val_var, sign):
                return lambda: self.send_jog_mm(ax, val_var.get() * sign)

            btn_m5 = tk.Button(inner, width=btn_w, height=btn_h, bg="#f0f0f0", command=make_jog_cmd(axis, self.jog_val_large, -1))
            btn_m1 = tk.Button(inner, width=btn_w, height=btn_h, bg="#f0f0f0", command=make_jog_cmd(axis, self.jog_val_mid, -1))
            btn_m01 = tk.Button(inner, width=btn_w, height=btn_h, bg="#f0f0f0", command=make_jog_cmd(axis, self.jog_val_small, -1))
            
            btn_m5.pack(side="left", padx=2); btn_m1.pack(side="left", padx=2); btn_m01.pack(side="left", padx=2)
            self.jog_btns[axis]['in'].extend([btn_m5, btn_m1, btn_m01])
            
            tk.Label(inner, text="   |   ", fg="gray").pack(side="left") 
            
            btn_p01 = tk.Button(inner, width=btn_w, height=btn_h, bg="#f0f0f0", command=make_jog_cmd(axis, self.jog_val_small, 1))
            btn_p1 = tk.Button(inner, width=btn_w, height=btn_h, bg="#f0f0f0", command=make_jog_cmd(axis, self.jog_val_mid, 1))
            btn_p5 = tk.Button(inner, width=btn_w, height=btn_h, bg="#f0f0f0", command=make_jog_cmd(axis, self.jog_val_large, 1))
            
            btn_p01.pack(side="left", padx=2); btn_p1.pack(side="left", padx=2); btn_p5.pack(side="left", padx=2)
            self.jog_btns[axis]['out'].extend([btn_p01, btn_p1, btn_p5])
            
        self.update_jog_button_texts()
        tk.Button(center_frame, text="SET CURRENT POSITION AS ZERO (0.000 mm)", bg="lightblue", height=3, font=("Arial", 12, "bold"), command=self.set_zero).pack(fill="x", padx=100, pady=30)

    def update_jog_button_texts(self):
        v_s = self.jog_val_small.get()
        v_m = self.jog_val_mid.get()
        v_l = self.jog_val_large.get()
        axes = ["XA", "XB", "YA", "YB", "Z"]
        for axis in axes:
            self.jog_btns[axis]['in'][0].config(text=f"<<<")
            self.jog_btns[axis]['in'][1].config(text=f"<<")
            self.jog_btns[axis]['in'][2].config(text=f"<")
            self.jog_btns[axis]['out'][0].config(text=f">")
            self.jog_btns[axis]['out'][1].config(text=f">>")
            self.jog_btns[axis]['out'][2].config(text=f">>>")

    def update_jog_buttons(self, axis, limit_in_hit, limit_out_hit):
        in_state = tk.DISABLED if limit_in_hit else tk.NORMAL
        out_state = tk.DISABLED if limit_out_hit else tk.NORMAL
        in_bg = "#ff8888" if limit_in_hit else "#f0f0f0"
        out_bg = "#ff8888" if limit_out_hit else "#f0f0f0"
        
        for b in self.jog_btns[axis]['in']: b.config(state=in_state, bg=in_bg)
        for b in self.jog_btns[axis]['out']: b.config(state=out_state, bg=out_bg)

    def send_emg_reset(self):
        self.send("RESET_EMG")
        self.log("Emergency Reset Sent. You can manual jog away from limits.")

    # --- Sequence Tab ---
    def setup_sequence_tab(self):
        self.input_frame = tk.LabelFrame(self.seq_frame, text="Add / Edit Sequence Step", font=("Arial", 11, "bold"), padx=10, pady=15)
        self.input_frame.pack(fill="x", padx=10, pady=10)
        tk.Label(self.input_frame, text="Action:", font=("Arial", 10)).pack(side="left", padx=(5, 5))
        self.mode_combo = ttk.Combobox(self.input_frame, width=25, state="readonly", font=("Arial", 10))
        self.mode_combo['values'] = ["1. Symmetric Move", "2. Individual Move", "3. Delay"]
        self.mode_combo.current(0); self.mode_combo.pack(side="left", padx=5)
        self.mode_combo.bind("<<ComboboxSelected>>", self.update_input_line)
        tk.Frame(self.input_frame, width=2, bg="gray").pack(side="left", fill="y", padx=15)
        self.param_frame = tk.Frame(self.input_frame); self.param_frame.pack(side="left", fill="x", expand=True)
        self.update_input_line(None)

        list_frame = tk.LabelFrame(self.seq_frame, text="Action List", font=("Arial", 11, "bold"), padx=10, pady=10, fg="green")
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.seq_tree = ttk.Treeview(list_frame, columns=("No", "Mode", "Desc"), show="headings", height=8)
        self.seq_tree.heading("No", text="#"); self.seq_tree.heading("Mode", text="Type"); self.seq_tree.heading("Desc", text="Parameters")
        self.seq_tree.column("No", width=50, anchor="center"); self.seq_tree.column("Mode", width=150, anchor="center"); self.seq_tree.column("Desc", width=700, anchor="w")
        self.seq_tree.pack(side="left", fill="both", expand=True)
        
        # --- 시퀀스 클립보드 이벤트 바인딩 ---
        self.seq_tree.bind("<Double-1>", self.load_for_edit)
        self.seq_tree.bind("<Control-c>", self.copy_steps)
        self.seq_tree.bind("<Control-v>", self.paste_steps)
        self.seq_tree.bind("<Delete>", lambda e: self.delete_item()) # 단축키 Delete로 삭제

        btn_frame = tk.Frame(list_frame); btn_frame.pack(side="right", fill="y", padx=5)
        tk.Button(btn_frame, text="EDIT", width=5, bg="#ADD8E6", command=lambda: self.load_for_edit(None)).pack(pady=2)
        tk.Button(btn_frame, text="▲", width=5, command=self.move_up).pack(pady=2)
        tk.Button(btn_frame, text="▼", width=5, command=self.move_down).pack(pady=2)
        tk.Button(btn_frame, text="DEL", width=5, bg="#ffcccc", command=self.delete_item).pack(pady=10)
        tk.Button(btn_frame, text="CLR", width=5, bg="red", fg="white", command=self.clear_all).pack(pady=2)
        tk.Button(self.seq_frame, text="▶ RUN SEQUENCE", command=self.run_sequence, bg="#4CAF50", fg="white", font=("Arial", 16, "bold"), height=2).pack(fill="x", padx=10, pady=10)

    # --- 복사 / 붙여넣기 기능 ---
    def copy_steps(self, event=None):
        selected = self.seq_tree.selection()
        if not selected: return
        self.clipboard_data.clear()
        
        for item in selected:
            idx = self.seq_tree.index(item)
            values = self.seq_tree.item(item, "values")
            mode = values[1]
            desc = values[2]
            
            data_copy = copy.deepcopy(self.sequence_data[idx])
            self.clipboard_data.append({'mode': mode, 'desc': desc, 'data': data_copy})
            
        self.log(f"[{len(self.clipboard_data)} Steps Copied]")

    def paste_steps(self, event=None):
        if not self.clipboard_data: return
        
        selected = self.seq_tree.selection()
        # 선택된 항목이 있다면 그 항목 바로 아래에, 없다면 리스트 맨 아래에 삽입
        if selected:
            insert_idx = self.seq_tree.index(selected[-1]) + 1
        else:
            insert_idx = len(self.sequence_data)
            
        for i, clip in enumerate(self.clipboard_data):
            mode = clip['mode']
            desc = clip['desc']
            new_data = copy.deepcopy(clip['data'])
            
            self.sequence_data.insert(insert_idx + i, new_data)
            self.seq_tree.insert("", insert_idx + i, values=(0, mode, desc))
            
        self.renumber()
        self.log(f"[{len(self.clipboard_data)} Steps Pasted]")

    # --- 동적 입력창 ---
    def update_input_line(self, event):
        for widget in self.param_frame.winfo_children(): widget.destroy()
        mode = self.mode_combo.get()
        btn_text = "Update Step" if self.editing_index is not None else "+ Add Step"
        btn_bg = "#87CEFA" if self.editing_index is not None else "#ddd"
        if self.editing_index is not None: tk.Button(self.param_frame, text="Cancel", bg="pink", command=self.cancel_edit).pack(side="right", padx=10)

        if mode.startswith("1."):
            tk.Label(self.param_frame, text="Total X(mm):").pack(side="left")
            self.ent_x = tk.Entry(self.param_frame, width=6); self.ent_x.pack(side="left", padx=2)
            tk.Label(self.param_frame, text="Total Y(mm):").pack(side="left", padx=(10,0))
            self.ent_y = tk.Entry(self.param_frame, width=6); self.ent_y.pack(side="left", padx=2)
            tk.Label(self.param_frame, text="Z(mm):").pack(side="left", padx=(10,0))
            self.ent_z = tk.Entry(self.param_frame, width=6); self.ent_z.pack(side="left", padx=2)
            tk.Label(self.param_frame, text="Speed(mm/s):").pack(side="left", padx=(10,0))
            self.ent_spd = tk.Entry(self.param_frame, width=6); self.ent_spd.insert(0, "5.0"); self.ent_spd.pack(side="left", padx=2)
            tk.Button(self.param_frame, text=btn_text, bg=btn_bg, font=("Arial", 9, "bold"), command=self.add_mode1).pack(side="left", padx=20)
        elif mode.startswith("2."):
            self.ents_indiv = {}
            axes = ["XA", "XB", "YA", "YB", "Z"]
            for ax in axes:
                tk.Label(self.param_frame, text=f"{ax}:", font=("Arial", 8)).pack(side="left")
                e = tk.Entry(self.param_frame, width=5); e.pack(side="left", padx=1); self.ents_indiv[ax] = e
            tk.Label(self.param_frame, text="Speed(mm/s):", font=("Arial", 8)).pack(side="left", padx=(5,0))
            self.ent_spd = tk.Entry(self.param_frame, width=5); self.ent_spd.insert(0,"5.0"); self.ent_spd.pack(side="left", padx=1)
            tk.Button(self.param_frame, text=btn_text, bg=btn_bg, font=("Arial", 9, "bold"), command=self.add_mode2).pack(side="left", padx=15)
        elif mode.startswith("3."):
            tk.Label(self.param_frame, text="Time (ms):").pack(side="left")
            self.ent_delay = tk.Entry(self.param_frame, width=10); self.ent_delay.pack(side="left", padx=5)
            tk.Button(self.param_frame, text=btn_text, bg=btn_bg, font=("Arial", 9, "bold"), command=self.add_mode3).pack(side="left", padx=20)

    def load_for_edit(self, event):
        selected = self.seq_tree.selection()
        if not selected: return
        self.editing_index = self.seq_tree.index(selected[0]); data = self.sequence_data[self.editing_index]
        self.input_frame.config(text=f"EDITING Step #{self.editing_index + 1}", fg="blue")
        if data["type"] == "MOVE" and "Symmetric" in self.seq_tree.item(selected[0], "values")[1]:
            self.mode_combo.current(0); self.update_input_line(None)
            cmds = dict(data["cmds_mm"]) 
            self.ent_x.insert(0, str(abs(cmds["XA"] * 2))); self.ent_y.insert(0, str(abs(cmds["YA"] * 2)))
            self.ent_z.insert(0, str(cmds["Z"])); self.ent_spd.delete(0,'end'); self.ent_spd.insert(0, str(data["spd_mm"]))
        elif data["type"] == "MOVE" and "Individual" in self.seq_tree.item(selected[0], "values")[1]:
            self.mode_combo.current(1); self.update_input_line(None)
            cmds = dict(data["cmds_mm"]) 
            for ax, ent in self.ents_indiv.items(): 
                if ax in cmds: ent.insert(0, str(cmds[ax]))
            self.ent_spd.delete(0,'end'); self.ent_spd.insert(0, str(data["spd_mm"]))
        elif data["type"] == "WAIT":
            self.mode_combo.current(2); self.update_input_line(None)
            self.ent_delay.insert(0, str(data["val"]))

    def cancel_edit(self):
        self.editing_index = None; self.input_frame.config(text="Add Sequence Step", fg="black"); self.update_input_line(None)
    def save_step(self, m, d, dt):
        if self.editing_index is not None:
            self.sequence_data[self.editing_index] = dt; self.seq_tree.item(self.seq_tree.get_children()[self.editing_index], values=(self.editing_index+1, m, d)); self.cancel_edit()
        else:
            self.sequence_data.append(dt); self.seq_tree.insert("", "end", values=(len(self.sequence_data), m, d))
    
    # --- Data 검증 공통 로직 ---
    def check_limits(self, cmds_mm, spd_mm):
        if not self.enable_limits.get(): return True
        if spd_mm > self.limit_speed_mms.get():
            messagebox.showerror("Limit Err", f"속도가 설정 제한({self.limit_speed_mms.get()}mm/s)을 초과했습니다.")
            return False
        for ax, val in cmds_mm:
            if abs(val) > self.limit_dist_mm.get():
                messagebox.showerror("Limit Err", f"축 {ax}의 이동 거리가 제한({self.limit_dist_mm.get()}mm)을 초과했습니다.")
                return False
        return True

    # --- Symmetric Logic ---
    def add_mode1(self):
        try:
            x_mm, y_mm = float(self.ent_x.get() or 0), float(self.ent_y.get() or 0)
            z_mm, s_mm = float(self.ent_z.get() or 0), float(self.ent_spd.get())
            xa_mm, xb_mm = (x_mm/2.0), (x_mm/2.0)
            ya_mm, yb_mm = (y_mm/2.0), (y_mm/2.0)
            
            cmds_mm = [("XA",xa_mm),("XB",xb_mm),("YA",ya_mm),("YB",yb_mm),("Z",z_mm)]
            
            if not self.check_limits(cmds_mm, s_mm): return
            
            desc = f"TotX:{x_mm}mm, TotY:{y_mm}mm, Z:{z_mm}mm @ {s_mm}mm/s"
            data = {"type": "MOVE", "cmds_mm": cmds_mm, "spd_mm": s_mm}
            self.save_step("Symmetric", desc, data)
        except ValueError: messagebox.showerror("Err", "숫자만 입력해주세요")

    # --- Individual Logic ---
    def add_mode2(self):
        try:
            cmds_mm, dl = [], []
            s_mm = float(self.ent_spd.get()) 
            
            for k,v in self.ents_indiv.items():
                if v.get(): 
                    val_mm = float(v.get())
                    cmds_mm.append((k, val_mm))
                    dl.append(f"{k}:{val_mm}")
            
            if not self.check_limits(cmds_mm, s_mm): return
            
            if cmds_mm: 
                desc = ", ".join(dl) + f"mm @ {s_mm}mm/s"
                data = { "type":"MOVE", "cmds_mm":cmds_mm, "spd_mm":s_mm}
                self.save_step("Individual", desc, data)
        except ValueError: messagebox.showerror("Err", "숫자만 입력해주세요")

    def add_mode3(self):
        try: ms=int(self.ent_delay.get()); self.save_step("Delay", f"Wait {ms}ms", {"type":"WAIT","val":ms})
        except: messagebox.showerror("Err", "정수만 입력해주세요")

    # --- 리스트 제어 ---
    def move_up(self):
        s=self.seq_tree.selection()
        for i in s:
            idx=self.seq_tree.index(i)
            if idx>0: self.sequence_data[idx],self.sequence_data[idx-1]=self.sequence_data[idx-1],self.sequence_data[idx]; self.seq_tree.move(i,self.seq_tree.parent(i),idx-1); self.renumber()
    def move_down(self):
        s=self.seq_tree.selection()
        for i in s:
            idx=self.seq_tree.index(i)
            if idx<len(self.sequence_data)-1: self.sequence_data[idx],self.sequence_data[idx+1]=self.sequence_data[idx+1],self.sequence_data[idx]; self.seq_tree.move(i,self.seq_tree.parent(i),idx+1); self.renumber()
    def delete_item(self):
        if self.editing_index is not None: self.cancel_edit()
        s=self.seq_tree.selection()
        for i in reversed(s): idx=self.seq_tree.index(i); del self.sequence_data[idx]; self.seq_tree.delete(i)
        self.renumber()
    def clear_all(self):
        if self.editing_index is not None: self.cancel_edit()
        self.sequence_data=[]; [self.seq_tree.delete(i) for i in self.seq_tree.get_children()]
    def renumber(self): 
        for i,x in enumerate(self.seq_tree.get_children()): v=list(self.seq_tree.item(x,"values")); v[0]=i+1; self.seq_tree.item(x,values=v)

    # --- 실행 ---
    def run_sequence(self):
        if self.btn_emg_reset.cget("bg") == "red":
            messagebox.showerror("Error", "Limit Switch Active! Reset emergency first.")
            return
        if "FREE" in self.btn_enable.cget("text"):
            messagebox.showerror("Error", "Motor is FREE! Please click the yellow button to LOCK motors first.")
            return

        if not self.sequence_data: return
        self.log(">>> START")
        self.is_running_sequence = True 

        if self.ser and self.ser.is_open: self.ser.reset_input_buffer()
        for step in self.sequence_data:
            if not self.is_running_sequence: return 

            if step["type"]=="WAIT":
                ms=step["val"]; self.log(f"Wait {ms}ms..."); self.root.update(); time.sleep(ms/1000.0)
            elif step["type"]=="MOVE":
                cmd, log="ABS", "Move: "
                
                spd_step = int(step["spd_mm"] * self.steps_per_mm)
                
                for ax, pos_mm in step["cmds_mm"]:
                    pos_step = int(pos_mm * self.steps_per_mm)
                    if not (LIMIT_MIN_MM <= pos_mm <= LIMIT_MAX_MM): 
                        messagebox.showerror("Limit",f"{ax} {pos_mm:.2f}mm Err"); self.is_running_sequence = False; return
                    cmd += f":{ax}:{pos_step}:{spd_step}"
                    log += f"{ax}->{pos_mm:.3f}mm "
                
                self.send(cmd); self.log(log); 
                self.wait_done_and_update_pos()
        
        if self.is_running_sequence:
            self.is_running_sequence = False 
            self.log(">>> DONE"); messagebox.showinfo("OK","Finished")

    def wait_done_and_update_pos(self):
        if not self.ser or not self.ser.is_open: return
        last_query = 0
        while True:
            if time.time() - last_query > 0.2:
                self.ser.write("POS?\n".encode()); last_query = time.time()
            if self.ser.in_waiting:
                try: 
                    l=self.ser.readline().decode().strip()
                    if l=="DONE": return
                    elif l.startswith("ALARM:LIMIT"):
                        self.is_running_sequence = False
                        self.btn_emg_reset.config(text="EMERGENCY RESET", bg="red")
                        self.log("LIMIT SWITCH HIT! Sequence Halted.")
                        return
                    elif l.startswith("POS:"): self.update_labels_from_string(l)
                except: pass
            self.root.update(); time.sleep(0.01)

    # --- 백그라운드 업데이트 ---
    def update_monitor_loop(self):
        if self.ser and self.ser.is_open and not self.is_running_sequence:
            try:
                self.ser.write("POS?\n".encode()); time.sleep(0.05)
                if self.ser.in_waiting:
                    while self.ser.in_waiting: 
                        line = self.ser.readline().decode().strip()
                        if line == "ALARM:LIMIT":
                            self.btn_emg_reset.config(text="EMERGENCY RESET", bg="red")
                            self.log("Hardware Limit Hit! Driver Disabled.")
                        elif line == "ALARM:CLEARED":
                            self.btn_emg_reset.config(text="EMG NORMAL", bg="gray")
                            self.log("Limit Cleared. Driver Enabled.")
                        elif line.startswith("POS:"): 
                            self.update_labels_from_string(line)
            except: pass
        self.root.after(500, self.update_monitor_loop)

    def update_labels_from_string(self, line):
        try:
            parts = line.split(":")
            if len(parts) >= 12:
                xa_mm = int(parts[1]) / self.steps_per_mm
                xb_mm = int(parts[2]) / self.steps_per_mm
                ya_mm = int(parts[3]) / self.steps_per_mm
                yb_mm = int(parts[4]) / self.steps_per_mm
                z_mm  = int(parts[5]) / self.steps_per_mm
                
                self.pos_labels["XA"].config(text=f"XA: {xa_mm:.3f}")
                self.pos_labels["XB"].config(text=f"XB: {xb_mm:.3f}")
                self.pos_labels["YA"].config(text=f"YA: {ya_mm:.3f}")
                self.pos_labels["YB"].config(text=f"YB: {yb_mm:.3f}")
                self.pos_labels["Z"].config(text=f"Z: {z_mm:.3f}")

                a0_hit = (int(parts[6]) == 0)
                a1_hit = (int(parts[7]) == 0)
                a2_hit = (int(parts[8]) == 0)
                a3_hit = (int(parts[9]) == 0)
                a4_hit = (int(parts[10])== 0)
                a5_hit = (int(parts[11])== 0)

                self.update_jog_buttons("XA", limit_in_hit=a0_hit, limit_out_hit=a1_hit)
                self.update_jog_buttons("XB", limit_in_hit=a0_hit, limit_out_hit=a1_hit)
                self.update_jog_buttons("YA", limit_in_hit=a2_hit, limit_out_hit=a3_hit)
                self.update_jog_buttons("YB", limit_in_hit=a2_hit, limit_out_hit=a3_hit)
                self.update_jog_buttons("Z", limit_in_hit=a4_hit, limit_out_hit=a5_hit)
                
            elif len(parts) == 6: 
                pass
        except: pass

    # --- 통신 ---
    def refresh_ports(self):
        self.port_combo['values']=[p.device for p in serial.tools.list_ports.comports()]
        if self.port_combo['values']: self.port_combo.current(0)
        
    def toggle_connect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.btn_connect.config(text="▶ CONNECT", bg="#4CAF50", relief="raised")
            self.lbl_status.config(text="Disconnected", fg="red"); self.log("Disconnected")
        else:
            try:
                self.ser=serial.Serial(self.port_combo.get(), self.baud_rate.get(), timeout=0.1); time.sleep(2)
                self.btn_connect.config(text="■ DISCONNECT", bg="#d32f2f", relief="sunken")
                self.lbl_status.config(text="Connected", fg="green"); self.log("Connected")
            except Exception as e: messagebox.showerror("Err",str(e))
            
    def send(self,c): 
        if self.ser and self.ser.is_open: self.ser.write((c+"\n").encode())
    
    def send_jog_mm(self, ax, dist_mm):
        if "FREE" in self.btn_enable.cget("text"):
            self.log(f"[{ax} JOG Blocked] Motor is FREE. Please Lock first.")
            return
            
        if self.enable_limits.get():
            if abs(dist_mm) > self.limit_dist_mm.get():
                messagebox.showerror("Limit Error", f"한 번에 이동 가능한 최대 거리({self.limit_dist_mm.get()}mm)를 초과했습니다.")
                return

        dist_step = int(dist_mm * self.steps_per_mm)
        spd_step = int(self.jog_speed_mms.get() * self.steps_per_mm)
        self.send(f"JOG:{ax}:{dist_step}:{spd_step}")

    def set_zero(self): self.send("ZERO:0"); self.log("Zero Set")
    def toggle_enable(self):
        if "LOCKED" in self.btn_enable.cget("text"): self.send("EN:0"); self.btn_enable.config(text="Motor FREE", bg="yellow")
        else: self.send("EN:1"); self.btn_enable.config(text="Motor LOCKED", bg="orange")
    def log(self,m): self.log_text.insert("end",m+"\n"); self.log_text.see("end")

if __name__ == "__main__":
    root = tk.Tk()
    app = TensileTesterRealTimeUI(root)
    root.mainloop()