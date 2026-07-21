import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageOps, ImageTk, ImageDraw, ImageEnhance
from escpos.printer import Usb
import os
import json
import numpy as np
import usb.core
import libusb_package

# --- HARDWARE CONSTANTS ---
VID, PID = 0xea62, 0x1115
MAX_PRINTER_WIDTH = 448 
CONFIG_FILE = "label_config.json"
BARCODE_RESERVED_HEIGHT = 47

class ThermalLabelStudio(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("Thermal Label Studio v1")
        self.geometry("700x450") 
        self.minsize(700, 450)
        
        self.raw_image = None
        self.preview_tk = None  
        self.batch_barcodes = []
        self._drag_data = {"x": 0, "y": 0}
        
        # State Variables - Using StringVar for all inputs to prevent "" crash
        self.label_w = tk.StringVar(value="320")
        self.label_h = tk.StringVar(value="240")
        self.h_gap = tk.StringVar(value="24")
        self.h_offset = tk.StringVar(value="29")
        self.v_start_offset = tk.StringVar(value="170")
        self.pos_x = tk.IntVar(value=0)
        self.pos_y = tk.IntVar(value=0)
        self.copies = tk.StringVar(value="1")
        self.last_path = tk.StringVar(value="")
        self.use_barcode = tk.BooleanVar(value=False)
        self.use_batch = tk.BooleanVar(value=False)
        self.barcode_data = tk.StringVar(value="123456789012")
        self.dither_mode = tk.StringVar(value="Floyd-Steinberg")
        self.threshold = tk.IntVar(value=128)
        self.img_scale = tk.DoubleVar(value=1.0)
        self.img_contrast = tk.DoubleVar(value=1.0)
        self.img_rotation = tk.DoubleVar(value=0.0)

        self.load_settings()
        self.setup_ui()
        
        if self.last_path.get() and os.path.exists(self.last_path.get()):
            try:
                self.raw_image = Image.open(self.last_path.get()).convert("L")
                self.update_preview()
            except: pass
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.save_settings() # Final save
        self.destroy()

    def safe_get(self, var, default=0, is_float=False):
        """Helper to safely get numeric values from StringVars"""
        try:
            val = var.get()
            if not val: return default
            return float(val) if is_float else int(val)
        except (ValueError, tk.TclError):
            return default

    def setup_ui(self):
        self.grid_columnconfigure(0, minsize=300)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tab_view = ctk.CTkTabview(
            self, 
            width=280, 
            corner_radius=12,
            fg_color="transparent",
            segmented_button_fg_color="#242424",
            segmented_button_selected_color="#2980b9",
            segmented_button_selected_hover_color="#3498db",
            segmented_button_unselected_color="#242424",
            segmented_button_unselected_hover_color="#2b2b2b",
            text_color="#ecf0f1"
        )
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Access internal segmented button directly to force max border radius and padding
        if hasattr(self.tab_view, "_segmented_button"):
            self.tab_view._segmented_button.configure(corner_radius=12)
        
        self.tab_designer = self.tab_view.add("  Designer  ")
        self.tab_config = self.tab_view.add("  Configuration  ")

        # --- DESIGNER TAB ---
        img_frame = self.create_group_frame(self.tab_designer, "Image Controls")
        ctk.CTkButton(img_frame, text="Load Image", height=24, fg_color="#2980b9",
                      command=self.load_image_dialog).grid(row=0, column=0, columnspan=2, pady=(0, 4), sticky="ew")
        
        self.create_slider(img_frame, "Contrast", 0.1, 3.0, self.img_contrast, row=1)
        self.create_slider(img_frame, "Threshold", 0, 255, self.threshold, row=2)
        
        ctk.CTkLabel(img_frame, text="Dither", font=("Arial", 10)).grid(row=3, column=0, sticky="w")
        dither_menu = ctk.CTkOptionMenu(img_frame, variable=self.dither_mode, height=20, font=("Arial", 10),
                                        values=["None", "Random Noise", "Floyd-Steinberg", "Bayer"],
                                        command=lambda _: self.update_preview())
        dither_menu.grid(row=3, column=1, sticky="e", pady=2)

        bc_frame = self.create_group_frame(self.tab_designer, "Barcode")
        ctk.CTkSwitch(bc_frame, text="Enable", variable=self.use_barcode, font=("Arial", 10),
                      command=self.update_preview).grid(row=0, column=0, sticky="w")
        ctk.CTkEntry(bc_frame, textvariable=self.barcode_data, height=20, width=90).grid(row=0, column=1, sticky="e")
        
        ctk.CTkSwitch(bc_frame, text="Batch", variable=self.use_batch, font=("Arial", 10)).grid(row=1, column=0, sticky="w")
        ctk.CTkButton(bc_frame, text="Load .txt", height=20, width=90, font=("Arial", 10),
                      command=self.load_barcode_file).grid(row=1, column=1, sticky="e", pady=2)

        print_frame = self.create_group_frame(self.tab_designer, "Print Job")
        self.create_input(print_frame, "Copies", self.copies, row=0)
        ctk.CTkButton(print_frame, text="PRINT", fg_color="#27ae60", hover_color="#2ecc71", 
                      font=ctk.CTkFont(size=14, weight="bold"), height=40, 
                      command=self.print_job).grid(row=1, column=0, columnspan=2, pady=(8, 0), sticky="ew")

        # --- CONFIG TAB ---
        hw_frame = self.create_group_frame(self.tab_config, "Hardware")
        ctk.CTkButton(hw_frame, text="Align Printer", height=24, fg_color="#d35400", command=self.align_printer).grid(row=0, column=0, columnspan=2, pady=4, sticky="ew")
        self.create_input(hw_frame, "Feed (px)", self.v_start_offset, row=1)
        self.create_input(hw_frame, "H-Offset", self.h_offset, row=2)
        self.create_input(hw_frame, "Gap (px)", self.h_gap, row=3)

        dim_frame = self.create_group_frame(self.tab_config, "Label Size")
        self.create_input(dim_frame, "Width", self.label_w, row=0)
        self.create_input(dim_frame, "Height", self.label_h, row=1)

        # --- INTERACTIVE CANVAS ---
        self.preview_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#121212")
        self.preview_frame.grid(row=0, column=1, sticky="nsew")
        
        self.canvas = tk.Canvas(self.preview_frame, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=20)

        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag_move)
        self.canvas.bind("<MouseWheel>", self.mouse_scroll) # Fallback
        self.canvas.bind("<Button-4>", self.mouse_scroll)   # Linux scroll up
        self.canvas.bind("<Button-5>", self.mouse_scroll)   # Linux scroll down
        
        self.canvas.bind("<Button-3>", self.start_drag)
        self.canvas.bind("<B3-Motion>", self.drag_rotate)
        
        # Overlay for instructions
        self.overlay_frame = ctk.CTkFrame(self.canvas, corner_radius=8, fg_color="#2b2b2b", bg_color="#1a1a1a")
        
        self.overlay_label = ctk.CTkLabel(
            self.overlay_frame, 
            text="L-Click + Drag: Move\nR-Click + Drag: Rotate\nScroll: Scale", 
            font=ctk.CTkFont(size=11), 
            text_color="#b0b0b0",
            justify="left"
        )
        self.overlay_label.pack(padx=10, pady=(8, 2))
        
        self.reset_btn = ctk.CTkButton(
            self.overlay_frame, 
            text="Reset Edits", 
            font=ctk.CTkFont(size=10, weight="bold"),
            width=80, 
            height=20, 
            fg_color="#c0392b", 
            hover_color="#e74c3c",
            command=self.reset_image_edits
        )
        self.reset_btn.pack(padx=10, pady=(2, 8))
        
        # Bind hover events to show/hide the overlay
        self.canvas.bind("<Enter>", self.show_overlay)
        self.canvas.bind("<Leave>", self.hide_overlay)

    def show_overlay(self, event=None):
        self.overlay_frame.place(relx=0.98, rely=0.02, anchor="ne")
        
    def hide_overlay(self, event=None):
        if event and event.widget == self.canvas:
            x, y = event.x, event.y
            if 0 <= x <= self.canvas.winfo_width() and 0 <= y <= self.canvas.winfo_height():
                return
        self.overlay_frame.place_forget()

    def reset_image_edits(self):
        self.pos_x.set(0)
        self.pos_y.set(0)
        self.img_scale.set(1.0)
        self.img_rotation.set(0.0)
        self.img_contrast.set(1.0)
        self.threshold.set(128)
        self.dither_mode.set("Floyd-Steinberg")
        self.update_preview()
        self.save_settings()

    def start_drag(self, event):
        self._drag_data = {"x": event.x, "y": event.y}

    def drag_move(self, event):
        dx, dy = event.x - self._drag_data["x"], event.y - self._drag_data["y"]
        self.pos_x.set(self.pos_x.get() + dx)
        self.pos_y.set(self.pos_y.get() + dy)
        self._drag_data = {"x": event.x, "y": event.y}
        self.update_preview()

    def drag_rotate(self, event):
        dx = event.x - self._drag_data["x"]
        self.img_rotation.set((self.img_rotation.get() + dx) % 360)
        self._drag_data["x"] = event.x
        self.update_preview()

    def mouse_scroll(self, event):
        # Handle both Linux (event.num) and Windows/macOS (event.delta) scroll triggers
        if getattr(event, 'num', 0) == 4 or getattr(event, 'delta', 0) > 0:
            step = 0.05
        elif getattr(event, 'num', 0) == 5 or getattr(event, 'delta', 0) < 0:
            step = -0.05
        else:
            step = 0
            
        if step != 0:
            self.img_scale.set(max(0.1, min(5.0, self.img_scale.get() + step)))
            self.update_preview()
            self.save_settings()

    def create_group_frame(self, parent, title):
        frame = ctk.CTkFrame(parent, corner_radius=4, fg_color="#2b2b2b")
        frame.pack(fill="x", pady=4, padx=6)
        ctk.CTkLabel(frame, text=title.upper(), font=ctk.CTkFont(size=9, weight="bold"), text_color="#3498db").pack(anchor="w", padx=6)
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=6, pady=4)
        inner.grid_columnconfigure(1, weight=1)
        return inner

    def create_input(self, parent, label, var, row):
        ctk.CTkLabel(parent, text=label, font=("Arial", 10)).grid(row=row, column=0, sticky="w")
        ctk.CTkEntry(parent, textvariable=var, width=60, height=20).grid(row=row, column=1, sticky="e", pady=1)
        
        def handle_change(*args):
            self.update_preview()
            self.save_settings() # Saves every time you type/change a value
            
        var.trace_add("write", handle_change)

    def create_slider(self, parent, label, low, high, var, row):
        ctk.CTkLabel(parent, text=label, font=("Arial", 10)).grid(row=row, column=0, sticky="w")
        ctk.CTkSlider(parent, from_=low, to=high, variable=var, width=120, height=12, command=lambda _: self.update_preview()).grid(row=row, column=1, sticky="e")

    def load_image_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
        if path:
            self.raw_image = Image.open(path).convert("L")
            self.last_path.set(path)
            self.update_preview()
            self.save_settings()

    def generate_label_bitmap(self, for_printing=False):
        total_w = self.safe_get(self.label_w, 320)
        total_h = self.safe_get(self.label_h, 240)
        usable_h = max(10, total_h - BARCODE_RESERVED_HEIGHT) if self.use_barcode.get() else total_h
        canvas = Image.new('1', (total_w, usable_h), 1)
        
        if self.raw_image:
            w, h = self.raw_image.size
            new_size = (int(w * self.img_scale.get()), int(h * self.img_scale.get()))
            img = self.raw_image.resize(new_size, Image.Resampling.LANCZOS)
            img = ImageEnhance.Contrast(img).enhance(self.img_contrast.get())
            img = img.rotate(self.img_rotation.get(), expand=True, fillcolor=255)

            mode = self.dither_mode.get()
            thresh = self.threshold.get()
            if mode == "Random Noise":
                arr = np.array(img).astype(float)
                noise = np.random.randint(-128, 128, arr.shape)
                img = Image.fromarray(((arr + noise) > thresh).astype(np.uint8) * 255).convert("1")
            elif mode == "Bayer":
                bayer = np.array([[0,8,2,10],[12,4,14,6],[3,11,1,9],[15,7,13,5]]) * 16
                arr = np.array(img)
                th_map = np.tile(bayer, (arr.shape[0]//4+1, arr.shape[1]//4+1))[:arr.shape[0], :arr.shape[1]]
                img = Image.fromarray((arr > (th_map + (thresh-128))).astype(np.uint8) * 255).convert("1")
            elif mode == "Floyd-Steinberg":
                img = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
            else:
                img = img.point(lambda p: 255 if p > thresh else 0).convert("1")

            canvas.paste(img, (self.pos_x.get(), self.pos_y.get()))

        if not for_printing:
            full = Image.new('1', (total_w, total_h), 1)
            full.paste(canvas, (0, 0))
            if self.use_barcode.get():
                d = ImageDraw.Draw(full)
                d.rectangle([0, usable_h, total_w, total_h], fill=1, outline=0)
                d.text((total_w//2 - 30, usable_h + 15), "|| BARCODE ||", fill=0)
            return full
        return canvas

    def update_preview(self, _=None):
        bitmap = self.generate_label_bitmap(for_printing=False)
        if bitmap:
            preview_disp = bitmap.convert("RGBA")
            self.preview_tk = ImageTk.PhotoImage(preview_disp)
            self.canvas.delete("all")
            cx, cy = 20, 20
            self.canvas.create_rectangle(cx-1, cy-1, cx+bitmap.width+1, cy+bitmap.height+1, outline="#3498db", width=2)
            self.canvas.create_image(cx, cy, anchor="nw", image=self.preview_tk)

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    d = json.load(f)
                    mapping = [
                        ("label_w", self.label_w), ("label_h", self.label_h), 
                        ("pos_x", self.pos_x), ("pos_y", self.pos_y), 
                        ("img_scale", self.img_scale), ("img_rotation", self.img_rotation),
                        ("h_gap", self.h_gap), ("h_offset", self.h_offset), 
                        ("v_start_offset", self.v_start_offset), ("last_path", self.last_path),
                        ("img_contrast", self.img_contrast), ("threshold", self.threshold),
                        ("dither_mode", self.dither_mode), ("use_barcode", self.use_barcode),
                        ("use_batch", self.use_batch), ("barcode_data", self.barcode_data),
                        ("copies", self.copies)
                    ]
                    for key, var in mapping:
                        if key in d: var.set(d[key])
            except: pass

    def save_settings(self):
        d = {
            "label_w": self.label_w.get(), "label_h": self.label_h.get(), 
            "pos_x": self.pos_x.get(), "pos_y": self.pos_y.get(), 
            "img_scale": self.img_scale.get(), "img_rotation": self.img_rotation.get(),
            "h_gap": self.h_gap.get(), "h_offset": self.h_offset.get(),
            "v_start_offset": self.v_start_offset.get(), "last_path": self.last_path.get(),
            "img_contrast": self.img_contrast.get(), "threshold": self.threshold.get(),
            "dither_mode": self.dither_mode.get(), "use_barcode": self.use_barcode.get(),
            "use_batch": self.use_batch.get(), "barcode_data": self.barcode_data.get(),
            "copies": self.copies.get()
        }
        with open(CONFIG_FILE, "w") as f: 
            json.dump(d, f, indent=4)

    def load_barcode_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text", "*.txt")])
        if path:
            with open(path, "r") as f:
                self.batch_barcodes = [l.strip() for l in f if l.strip().isdigit()]
            messagebox.showinfo("Success", f"Loaded {len(self.batch_barcodes)} codes")

    def align_printer(self):
        try:
            backend = libusb_package.get_libusb1_backend()
            p = Usb(VID, PID, backend=backend)
            p._raw(b'\x1D\x0C') 
            p.close()
        except Exception as e: messagebox.showerror("Error", str(e))

    def print_job(self):
        self.save_settings()
        p = None
        try:
            backend = libusb_package.get_libusb1_backend()
            p = Usb(VID, PID, backend=backend)
            cropped_img = self.generate_label_bitmap(for_printing=True)
            items = self.batch_barcodes if (self.use_barcode.get() and self.use_batch.get()) else [self.barcode_data.get()]
            
            copies_num = self.safe_get(self.copies, 1)
            h_off = self.safe_get(self.h_offset, 0)
            h_gap_val = self.safe_get(self.h_gap, 0)

            for item in items:
                for _ in range(copies_num):
                    p._raw(b'\x1b\x61\x00') 
                    full_line = Image.new('1', (MAX_PRINTER_WIDTH, cropped_img.height), 1)
                    full_line.paste(cropped_img, (h_off, 0))
                    p.image(full_line, center=False)
                    
                    if self.use_barcode.get():
                        p._raw(b'\x1b\x61\x01') 
                        p.barcode(item[:12], 'EAN13', 32, 3, '', 'A')
                    
                    if h_gap_val > 0:
                        p.image(Image.new('1', (MAX_PRINTER_WIDTH, h_gap_val), 1), center=False)
        except Exception as e: messagebox.showerror("Print Error", str(e))
        finally: 
            if p: p.close()

if __name__ == "__main__":
    app = ThermalLabelStudio()
    app.mainloop()